"""The boarding addon wires a built ruin to the crew, with nothing written per mission.

`eva_wiring.mast` is routes only, so this compiles the REAL file through MAST's own
`import` and sends it the signals the library and the items addon send:

  * `relic_built` - emitted by `relic_spawn` itself, not faked - starts the proximity pass,
    and a ruin with the ship at its door is offered at once;
  * a ruin the ship is nowhere near is NOT offered (it used to be, from across the map);
  * `eva_relics_auto(False)` is the opt-out;
  * `item_collected` for the ruin's piece sends the quest signal `<relic>_taken` - the
    half that was missing, because a piece reeled in from a suit is deleted inside the
    ruin and never leaves it - with or without the newer `item_id` on the signal.

Three harness rules, each of which fails silently (see `fabrication/test_fabricate_panel`):
compile through `import` with `story.basedir` set, park LAST, and push a SERVER page -
every route here is `//shared/signal`, which only client 0 runs.

    PYTHONPATH=../sbs_utils python -m unittest boarding.test_eva_wiring
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

BOARDING = os.path.dirname(os.path.abspath(__file__))

from sbs_utils.agent import Agent
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.gui import Gui
from sbs_utils.handlerhooks import reset_mission_state
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the route nodes)
import sbs_utils.mast_sbs.mast_sbs_procedural  # noqa: F401  (what makes eva_relic_* MAST globals)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural import amd_relics as R
from sbs_utils.procedural import boarding as B
from sbs_utils.procedural import eva as E
from sbs_utils.procedural import eva_relics as W
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.signal import signal_emit, signal_observe, signal_unobserve
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.tickdispatcher import TickDispatcher

HARNESS_STORY = "\n".join([
    "import eva_wiring.mast",
    "gui_text('$text:harness;')",
    "await gui()",
    "",
])

RUIN = """# [Mission](mission)

## [Relics](relics)

### [The Hollow](hollow)
---
Loc: 0, 0, 20000
---

### [The Mouth](mouth)
---
Relic: hollow
Chamber: 0, 0, 0, 900
---

### [the way in](hollow_door)
---
Relic: hollow
Point: -600, 0, 0
Roles: entrance
---

### [the cradle](hollow_cradle)
---
Relic: hollow
Point: 300, 0, 0
Roles: relic_piece
Item: beacon_core
---
"""

AT_THE_DOOR = (-2000.0, 0.0, 20000.0)
FAR = (-40000.0, 0.0, -40000.0)


class WiringPage(StoryPage):
    story = None


class _Base(unittest.TestCase):
    ship_at = AT_THE_DOOR
    auto = None

    def setUp(self):
        reset_mission_state()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        DeleteQueue.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)

        story = MastStory()
        story.basedir = BOARDING
        errors = story.compile(HARNESS_STORY, "evawiring", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        WiringPage.story = story
        FrameContext.mast = story

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append

        self.quest = []
        signal_observe(self._watch)

        self.server = WiringPage()
        Gui.push(0, self.server)
        self.present()

        if self.auto is not None:
            W.eva_relics_auto(self.auto)
        self.ship = to_object(player_spawn(*self.ship_at, "Artemis", "tsn",
                                           "tsn_light_cruiser"))
        R.relics_load("ruin.amd", content=RUIN)
        # THE PRODUCTION EMIT: `relic_spawn` sends `relic_built` itself.
        self.assertIsNotNone(R.relic_spawn("hollow", walls=False, atmosphere=False,
                                           marker=False))
        self.present(2)

    def tearDown(self):
        signal_unobserve(self._watch)
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        WiringPage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        reset_mission_state()
        FrameContext.context = None

    def _watch(self, name, data=None):
        if name == "quest_signal":
            self.quest.append((data or {}).get("SIGNAL_NAME"))

    def present(self, n=1):
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                           FakeEvent(0, "gui_present"))
            self.server.gui_state = "repaint"
            self.server.present(FakeEvent(0, "gui_present"))
            TickDispatcher.dispatch_tick()
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def emit(self, name, data):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        signal_emit(name, data)
        self.present(2)


class ARuinAtTheDoor(_Base):
    def test_every_route_is_server_only(self):
        with open(os.path.join(BOARDING, "eva_wiring.mast"), encoding="utf-8") as f:
            routes = [line for line in f.read().split("\n") if line.startswith("//")]
        self.assertEqual(len(routes), 4, routes)
        for line in routes:
            self.assertTrue(line.startswith("//shared/signal/"),
                            f"{line} would run once per console")

    def test_building_it_offers_it_and_opens_a_crew_party(self):
        offer = E.eva_offered()
        self.assertIsNotNone(offer, "relic_built must reach //shared/signal/relic_built")
        self.assertEqual(offer["relic"], "hollow")
        invite = B.boarding_invitation()
        self.assertIsNotNone(invite)
        self.assertEqual(invite["ship"], self.ship.id)
        self.assertEqual(invite["title"], "The Hollow")

    def test_a_second_relic_built_is_the_same_offer_and_party(self):
        invite = B.boarding_invitation()
        self.emit("relic_built", {"RELIC_KEY": "hollow", "RELIC_VOLUME": "hollow",
                                  "RELIC_NAME": "The Hollow"})
        self.assertIs(B.boarding_invitation(), invite)
        self.assertEqual(E.eva_offered()["relic"], "hollow")

    def test_the_piece_collected_sends_taken_once(self):
        pid = R.relic_pieces("hollow")[0]
        self.emit("item_collected", {"holder_id": self.ship.id, "key": "beacon_core",
                                     "qty": 1, "item_id": pid})
        self.assertEqual(self.quest, ["hollow_taken"])
        self.emit("item_collected", {"holder_id": self.ship.id, "key": "beacon_core",
                                     "qty": 1, "item_id": pid})
        self.assertEqual(self.quest, ["hollow_taken"])

    def test_an_older_items_addon_without_the_id_still_sends_it(self):
        self.emit("item_collected", {"holder_id": self.ship.id, "key": "beacon_core",
                                     "qty": 1})
        self.assertEqual(self.quest, ["hollow_taken"])

    def test_an_ordinary_pickup_sends_nothing(self):
        self.emit("item_collected", {"holder_id": self.ship.id, "key": "salvage",
                                     "qty": 3, "item_id": to_id(self.ship)})
        self.assertEqual(self.quest, [])

    def test_going_out_with_no_side_stories_is_not_an_error(self):
        self.emit("eva_went_out", {"EVA_CLIENT": 0, "EVA_WHO": None, "EVA_SUIT": 1,
                                   "EVA_RELIC": "hollow"})
        self.emit("eva_place_scene", {"EVA_CLIENT": 0, "EVA_RELIC": "hollow",
                                      "EVA_POINT": "hollow_door", "EVA_SCENE": "x",
                                      "EVA_CHANNEL": "c"})


class ARuinAcrossTheMap(_Base):
    ship_at = FAR

    def test_it_is_not_offered_until_the_ship_gets_there(self):
        self.assertIsNone(E.eva_offered())
        self.assertIsNone(B.boarding_invitation())
        self.assertEqual(W.eva_relics_count(), 1, "the pass must be running")
        from sbs_utils.vec import Vec3
        self.ship.pos = Vec3(*AT_THE_DOOR)
        for _ in range(4):
            self.present()
        self.assertEqual(E.eva_offered()["relic"], "hollow")


class WiredByHand(_Base):
    auto = False

    def test_auto_off_offers_nothing_and_starts_no_pass(self):
        self.assertIsNone(E.eva_offered())
        self.assertEqual(W.eva_relics_count(), 0)

    def test_the_mission_opens_it_itself(self):
        self.assertTrue(W.eva_relic_open("hollow"))
        self.assertEqual(E.eva_offered()["relic"], "hollow")


if __name__ == "__main__":
    unittest.main()
