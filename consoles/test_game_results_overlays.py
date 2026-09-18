"""The results screen arrives on a CLEAN console.

An overlay belongs to the console, not to the page, and the page survives the
`gui_task_jump` into the results screen - so `present_all` re-draws whatever the
slots still hold. Before the fix, the last quest's hero card, a sticky HUD, the
letterbox bars and any toast all sat on top of the game results.

The transient ones are the worst: they dismiss on a TickDispatcher timer, and the
route's own `sim_pause()` stops the ticks, so a card raised in the last seconds of
the game stayed up for as long as the results were on screen.

This runs the REAL route out of `game_results.mast` against a real page carrying a
real overlay. Measured against the pre-fix file, both assertions failed.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_game_results_overlays
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

CONSOLES = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CONSOLES)

from sbs_utils.agent import Agent, clear_shared
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers gui/route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.execution import set_shared_variable
from sbs_utils.procedural.gui.overlay import overlay_banner, overlay_hero, overlay_hud
from sbs_utils.procedural.signal import signal_emit
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.spaceobject import SpaceObject

import results_helpers

CID = 1

for _n in dir(results_helpers):
    _f = getattr(results_helpers, _n)
    if callable(_f) and not _n.startswith("_") and getattr(_f, "__module__", "") == "results_helpers":
        MastGlobals.import_python_function(_f)

# The import first so the route's signal_register lands in main; the park last so
# main stays alive for the route to jump the GUI task out of.
HARNESS_STORY = "\n".join([
    "import game_results.mast",
    "gui_text('$text:harness;')",
    "await gui()",
    "",
])


class ResultsPage(StoryPage):
    story = None


class _Base(unittest.TestCase):
    def setUp(self):
        clear_shared()
        SpaceObject.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

        story = MastStory()
        story.basedir = CONSOLES
        errors = story.compile(HARNESS_STORY, "resultsharness", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        ResultsPage.story = story
        FrameContext.mast = story
        self.story = story

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append

        # `sim` is a SHARED VARIABLE, not a global - cosmos_event_handler publishes it
        # every event. game_results.mast reads `sim.time_tick_counter` in its own main.
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)

        self.ship = player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser")
        mock_sbs.assign_client_to_ship(CID, self.ship.id)

        self.server = ResultsPage()
        Gui.push(0, self.server)
        self.page = ResultsPage()
        Gui.push(CID, self.page)
        self.present()

        # What the route reads. START_TEXT and GAME_ENDED are the mission's own end
        # state; RESULTS_SAVED short-circuits save_game_results_yaml so the test does
        # not write a yaml file into the missions folder; SETTINGS is read by the
        # second show_game_results route's condition.
        set_shared_variable("START_TEXT", "Mission accomplished")
        set_shared_variable("GAME_ENDED", False)
        set_shared_variable("RESULTS_SAVED", True)
        set_shared_variable("SETTINGS", {})
        set_shared_variable("DIFFICULTY", 5)
        # Task variables the real console flow carries in. Seeded shared here so
        # show_game_results_gui builds: the point is that the screen arrives, and a
        # screen whose GUI task died would empty the slots for the wrong reason.
        set_shared_variable("CONSOLE_SELECT", "helm")
        set_shared_variable("WORLD_SELECT", None)

    def tearDown(self):
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        ResultsPage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        FrameContext.context = None
        SpaceObject.clear()

    def present(self, n=1):
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            self.server.gui_state = "repaint"
            self.server.present(FakeEvent(0, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(CID, "gui_present"))

    def slots_with_content(self):
        overlays = getattr(self.page, "overlays", None)
        if overlays is None:
            return []
        return [name for name, slot in overlays.slots.items()
                if getattr(slot, "content", None) is not None]

    def end_the_game(self):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(0, "signal"))
        FrameContext.task = self.server.story_scheduler.tasks[0]
        signal_emit("show_game_results", None)
        self.present()


class TestTheResultsScreenArrivesClean(_Base):
    def test_a_hero_card_does_not_survive_the_game_ending(self):
        """The reported bug: the last quest's card, on top of the results."""
        overlay_hero("Quest complete", to=CID)
        self.present()
        self.assertTrue(self.slots_with_content(), "the card never went up")

        self.end_the_game()
        self.assertEqual(self.slots_with_content(), [])

    def test_nor_does_a_sticky_hud(self):
        """A HUD has no timer at all - it is up until something takes it down."""
        overlay_hud([["Objective", "Survive"]], to=CID)
        self.present()
        self.assertTrue(self.slots_with_content())

        self.end_the_game()
        self.assertEqual(self.slots_with_content(), [])

    def test_nor_a_transient_banner_whose_timer_the_pause_stopped(self):
        """`seconds=` dismisses on a TickDispatcher timer, and the route's own
        `sim_pause()` stops the ticks - so this one would never lift itself."""
        overlay_banner("30 seconds to fallback", to=CID, seconds=5)
        self.present()
        self.assertTrue(self.slots_with_content())

        self.end_the_game()
        self.assertEqual(self.slots_with_content(), [])

    def test_the_route_still_ran(self):
        """The clear is FIRST in the route, so a test that only proved the slots were
        empty would also pass against a route that died on its first line."""
        overlay_hero("Quest complete", to=CID)
        self.present()
        self.end_the_game()
        self.assertEqual(self.slots_with_content(), [])
        self.assertTrue(Agent.SHARED.get_inventory_value("GAME_ENDED", False))
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")


class TestTheTabChips(_Base):
    """The results tabs are a single-select horizontal listbox of chips."""

    def chips(self):
        from sbs_utils.pages.widgets.layout_listbox import LayoutListbox
        found = []

        def walk(n):
            if isinstance(n, LayoutListbox) and n.horizontal:
                found.append(n)
            for a in ("rows", "columns", "children", "layouts"):
                for c in getattr(n, a, []) or []:
                    walk(c)
        for lay in self.page.layouts:
            walk(lay)
        self.assertEqual(1, len(found), "expected one chip strip")
        return found[0]

    def tap(self, key):
        lb = self.chips()
        slot = [s.item_index for s in lb.sections if lb.items[s.item_index]["key"] == key][0]
        slot = [i for i, s in enumerate(lb.sections) if s.item_index == slot][0]
        ev = FakeEvent(client_id=CID, tag="gui_message", sub_tag=f"{lb.tag_prefix}:{slot}:__click")
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, ev)
        Gui.on_message(ev)
        self.present(3)

    def test_THE_TABS_ARE_CHIPS_AND_SUMMARY_IS_SELECTED(self):
        self.end_the_game()
        lb = self.chips()
        self.assertEqual(["summary", "fleet", "airwing", "quests", "enemies"],
                         [it["key"] for it in lb.items])
        self.assertEqual("summary", lb.get_value()["key"])
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def test_TAPPING_A_CHIP_SWITCHES_THE_TAB(self):
        self.end_the_game()
        self.tap("fleet")
        lb = self.chips()                  # rebuilt: a new strip, the new tab selected
        self.assertEqual("fleet", lb.get_value()["key"])
        self.tap("summary")
        self.assertEqual("summary", self.chips().get_value()["key"])
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def test_ALL_FIVE_FIT_WITHOUT_A_SLIDER_AT_1024(self):
        """The band is only 5% of the screen tall; an overflowing horizontal list draws a
        slider that would take most of that height."""
        self.end_the_game()
        lb = self.chips()
        self.assertEqual(5, len(lb.sections))
        self.assertEqual(0, lb.extra_slot_count)

    def test_list_tabs_carry_a_count(self):
        self.end_the_game()
        by_key = {it["key"]: it["count"] for it in self.chips().items}
        self.assertEqual(1, by_key["fleet"])          # the one player ship
        self.assertIsNone(by_key["summary"])
        self.assertIsNone(by_key["enemies"])


if __name__ == "__main__":
    unittest.main()
