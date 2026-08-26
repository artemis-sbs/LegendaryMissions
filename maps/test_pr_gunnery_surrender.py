"""A condemned hulk that SURRENDERS qualifies, the same as one that is destroyed.

The gunnery range spawns exactly as many hulks as the goal counts, and the hulks squawk
hostile IFF so the library's standard raider-surrender comms works on them. Before this,
only `//damage/destroy` paid: a crew that talked a hulk down lost the target (a surrendered
ship is flown home and deleted) and got nothing for it, so a single surrender made the job
impossible to finish - with no error anywhere to say why.

The route body is sliced out of `peacetime_remastered.mast` rather than copied here, so the
test cannot pass against a mission that has drifted.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest maps.test_pr_gunnery_surrender
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import re
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils.agent import clear_shared
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast_sbs import mast_sbs_procedural  # noqa: F401  (MAST globals)
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.quest import QuestState, quest_add, quest_get_key
from sbs_utils.procedural.roles import add_role, has_role
from sbs_utils.procedural.signal import signal_emit, signal_register
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.spaceobject import SpaceObject

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_MAST = os.path.join(HERE, "peacetime_remastered.mast")

SIGNAL = "ship_surrendered"

# A route fires on the SERVER task, so main has to still be alive when the signal lands -
# hence the idle loop.
_MAIN = """---prg_test_idle
    await delay_sim(60)
    jump prg_test_idle

"""


def _route(name):
    """The named shared-signal route, verbatim from the map, up to the next column-0 label."""
    with open(MAP_MAST, encoding="utf-8") as handle:
        source = handle.read()
    match = re.search(r"^//shared/signal/" + name + r"\b.*?(?=^(?://|=|@))",
                      source, re.S | re.M)
    assert match is not None, f"route //shared/signal/{name} not found in the map"
    return match.group(0)


class TestSurrenderedHulkCounts(unittest.TestCase):
    def setUp(self):
        clear_shared()
        SpaceObject.clear()
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

        self.story = MastStory()
        errors = self.story.compile(_MAIN + _route(SIGNAL), "prg", self.story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        FrameContext.mast = self.story

        self.errors = []
        self._orig_rte = MastScheduler.on_runtime_error
        # StoryScheduler OVERRIDES `runtime_error`, so patching it on MastScheduler
        # binds a method nothing calls and the assertion below is vacuous. The
        # class-level `on_runtime_error` seam is what the story scheduler actually
        # fires (and is what cosmos_dev's verdict uses).
        MastScheduler.on_runtime_error = self.errors.append

        Gui.clients = {}
        Gui.widget_list_sent = {}
        StoryPage.story = self.story
        self.page = StoryPage()
        Gui.push(0, self.page)
        self._present()
        self._register_route()

        self.ship = player_spawn(0, 0, 0, "Patrol", "tsn", "tsn_light_cruiser")
        add_role(self.ship.id, "__player__")
        self.hulk = npc_spawn(1500, 0, 0, "Condemned Hulk", "raider, target_drone",
                              "cargo_ship", "behav_npcship")
        # The gunnery job as the map grants it: one signal per hulk cleared.
        quest_add(self.ship.id, "job_gunnery", "Gunnery", "", state=QuestState.ACTIVE,
                  data={"on_signal": {"name": "drone_down", "count": 5}})

    def _register_route(self):
        # The compiler appends the route's `signal_register` to the END of main - past the
        # idle loop that keeps this cut-down main alive, so it would never be reached here.
        # Run the same registration by hand, on main's task, exactly as it would.
        label = next(name for name in self.story.labels
                     if name.startswith("__route__shared/signal/" + SIGNAL))
        FrameContext.task = self.page.story_scheduler.tasks[0]
        signal_register(SIGNAL, label, True)
        FrameContext.task = None

    def _present(self):
        mock_sbs.sim._time_tick_counter += 30
        self.page.gui_state = "repaint"
        self.page.present(FakeEvent(0, "gui_present"))

    def tearDown(self):
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        StoryPage.story = None
        FrameContext.page = None
        FrameContext.mast = None
        FrameContext.task = None
        FrameContext.context = None
        SpaceObject.clear()

    def _surrender(self, ship_id, to_id):
        signal_emit(SIGNAL, {"SHIP_ID": ship_id, "SURRENDER_TO_ID": to_id})
        self._present()

    def _progress(self):
        return quest_get_key(self.ship.id, "job_gunnery", "progress", 0) or 0

    def test_a_surrendered_hulk_credits_the_crew_that_talked_it_down(self):
        self._surrender(self.hulk.id, self.ship.id)
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")
        self.assertEqual(self._progress(), 1,
                         "a hulk that struck its colors must count toward the drill")

    def test_the_hulk_stops_being_a_target_so_it_cannot_pay_twice(self):
        # It stays on the map until it is flown home; shooting it afterwards must not bank
        # a second credit through //damage/destroy.
        self._surrender(self.hulk.id, self.ship.id)
        self.assertFalse(has_role(self.hulk.id, "target_drone"))

    def test_an_ordinary_raider_surrendering_pays_nothing(self):
        raider = npc_spawn(2000, 0, 0, "Raider", "raider", "cargo_ship", "behav_npcship")
        self._surrender(raider.id, self.ship.id)
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")
        self.assertEqual(self._progress(), 0,
                         "only the gunnery range's hulks count toward the drill")


if __name__ == "__main__":
    unittest.main()
