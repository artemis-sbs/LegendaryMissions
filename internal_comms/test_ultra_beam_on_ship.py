"""The Ultra-Beam is on the player's own ship, beside its Comms Badge.

It used to appear only with NOTHING selected on comms. Now selecting your own ship shows
both "Comms Badge" (the crew aboard) and "Ultra-Beam" (contacts with no host), and a
contact's "Back" returns to the list it was opened from - contacts go Back to
//comms/comms_badge either way, so the ship remembers which list that means.

Drives the real player_internal.mast: reads the comms buttons the engine would be sent
and presses them.

    PYTHONPATH=../sbs_utils python -m unittest internal_comms.test_ultra_beam_on_ship
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs
sys.modules.setdefault("sbs", mock_sbs)

HERE = os.path.dirname(os.path.abspath(__file__))

from sbs_utils.agent import Agent, clear_shared
from sbs_utils.consoledispatcher import ConsoleDispatcher
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.lifeform import lifeform_spawn
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.routes import follow_route_select_comms
from sbs_utils.procedural.sides import side_ensure
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.spaceobject import SpaceObject

CID = 1

# Two contacts with their own menus, gated the way LM's TSN Command now is. Both go Back
# to //comms/comms_badge, as every LM contact does.
HARNESS_STORY = '''import player_internal.mast
gui_text("$text:harness;")
await gui()

//comms/test_advisor if has_role(COMMS_ORIGIN_ID, '__player__') and COMMS_SELECTED_ID in (0, COMMS_ORIGIN_ID)
    + "Back" //comms/comms_badge
    + "Advise"

//comms/test_doctor if has_role(COMMS_ORIGIN_ID, '__player__') and COMMS_SELECTED_ID == COMMS_ORIGIN_ID
    + "Back" //comms/comms_badge
    + "Report"
'''


def _library_defaults(table):
    return {k: [cb for cb in v if not hasattr(cb, "__self__")]
            for k, v in table.items() if k[0] == 0 and isinstance(v, list)}


import sbs_utils.procedural.comms, sbs_utils.procedural.science, sbs_utils.procedural.popup  # noqa: E401,F401
_SELECT_DEFAULTS = _library_defaults(ConsoleDispatcher._dispatch_select)
_MESSAGE_DEFAULTS = _library_defaults(ConsoleDispatcher._dispatch_messages)


class HarnessPage(StoryPage):
    story = None


class UltraBeamBase(unittest.TestCase):
    def setUp(self):
        # Routes live in dispatchers, not in the story; drop the previous test's, keep the
        # library's own import-time handlers (see comms/test_drag_orders.py).
        from sbs_utils.handlerhooks import reset_mission_state
        reset_mission_state()
        for k, v in _SELECT_DEFAULTS.items():
            ConsoleDispatcher._dispatch_select[k] = list(v)
        for k, v in _MESSAGE_DEFAULTS.items():
            ConsoleDispatcher._dispatch_messages[k] = list(v)
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        DeleteQueue.clear()
        clear_shared()
        SpaceObject.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)
        side_ensure("tsn")

        self.buttons = []
        self._orig_btn = mock_sbs.send_comms_button_info
        self._orig_sel = mock_sbs.send_comms_selection_info
        mock_sbs.send_comms_button_info = lambda ship, color, text, tag: self.buttons.append((text, tag))
        mock_sbs.send_comms_selection_info = lambda ship, face, color, title: self.buttons.clear()

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append

        story = MastStory()
        story.basedir = HERE
        errors = story.compile(HARNESS_STORY, "ultraharness", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        HarnessPage.story = story
        FrameContext.mast = story

        self.ship = to_object(player_spawn(0, 0, 0, "Hero", "tsn", "tsn_light_cruiser"))
        mock_sbs.assign_client_to_ship(CID, self.ship.id)
        # host None = no ship = the Ultra-Beam; host = the ship = its Comms Badge
        self.advisor = lifeform_spawn("Advisor", "", "tsn", None, path="//comms/test_advisor")
        self.doctor = lifeform_spawn("Doctor", "", "tsn", self.ship.id, path="//comms/test_doctor")

        self.server = HarnessPage()
        Gui.push(0, self.server)
        self.page = HarnessPage()
        Gui.push(CID, self.page)
        self.present()

    def tearDown(self):
        mock_sbs.send_comms_button_info = self._orig_btn
        mock_sbs.send_comms_selection_info = self._orig_sel
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        HarnessPage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        FrameContext.context = None
        SpaceObject.clear()

    def present(self, n=2):
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "gui_present"))
            self.server.gui_state = "repaint"
            self.server.present(FakeEvent(0, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(CID, "gui_present"))
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def select(self, selected_id):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(CID, "select_space_object"))
        follow_route_select_comms(self.ship.id, selected_id)
        self.selected = selected_id
        self.present()

    def texts(self):
        return [t for t, _g in self.buttons]

    def press(self, text):
        tags = [g for t, g in self.buttons if t == text]
        self.assertTrue(tags, f"no comms button {text!r}: {self.texts()}")
        ev = FakeEvent(client_id=CID, tag="press_comms_button", sub_tag=tags[0],
                       origin_id=self.ship.id, selected_id=self.selected)
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, ev)
        ConsoleDispatcher.dispatch_message(ev, "comms_target_UID")
        self.present()


class TestOnTheShip(UltraBeamBase):

    def test_THE_SHIP_OFFERS_BOTH(self):
        self.select(self.ship.id)
        self.assertIn("Ultra-Beam", self.texts())
        self.assertIn("Comms Badge", self.texts())

    def test_the_ultra_beam_lists_the_hostless_contacts(self):
        self.select(self.ship.id)
        self.press("Ultra-Beam")
        self.assertIn("Advisor", self.texts())
        self.assertNotIn("Doctor", self.texts())

    def test_the_comms_badge_still_lists_the_crew(self):
        self.select(self.ship.id)
        self.press("Comms Badge")
        self.assertIn("Doctor", self.texts())
        self.assertNotIn("Advisor", self.texts())

    def test_a_contact_opens_from_the_ship(self):
        self.select(self.ship.id)
        self.press("Ultra-Beam")
        self.press("Advisor")
        self.assertIn("Advise", self.texts())

    def test_BACK_RETURNS_TO_THE_ULTRA_BEAM(self):
        """A contact goes Back to //comms/comms_badge. On the ship that list would be the
        crew - the wrong one - unless the ship remembers where the crew came from."""
        self.select(self.ship.id)
        self.press("Ultra-Beam")
        self.press("Advisor")
        self.press("Back")
        self.assertIn("Advisor", self.texts())
        self.assertNotIn("Doctor", self.texts())

    def test_and_the_crew_list_after_visiting_the_ultra_beam(self):
        """The remembered list resets at the ship's root, so Comms Badge is the crew again."""
        self.select(self.ship.id)
        self.press("Ultra-Beam")
        self.press("Back")
        self.press("Comms Badge")
        self.assertIn("Doctor", self.texts())
        self.assertNotIn("Advisor", self.texts())


class TestWithNothingSelected(UltraBeamBase):
    """Unchanged: the Ultra-Beam with nothing selected, and its Back."""

    def test_the_ultra_beam_is_still_offered(self):
        self.select(0)
        self.assertIn("Ultra-Beam", self.texts())
        self.assertNotIn("Comms Badge", self.texts())

    def test_back_from_a_contact_is_the_ultra_beam(self):
        self.select(0)
        self.press("Ultra-Beam")
        self.press("Advisor")
        self.press("Back")
        self.assertIn("Advisor", self.texts())


if __name__ == "__main__":
    unittest.main()
