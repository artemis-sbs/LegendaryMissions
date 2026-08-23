"""The Weapons console really does show a tether, through the real console file.

`test_tether_indicator.py` measures the two BUILDERS. This drives the console around
them - the actual `manual_weapons.mast`, entered the way a console enters it - because
the wiring is its own failure surface and none of it shows up in a builder test:

  * `manual_tether_partner` has to resolve as a MAST global. It is a plain Python
    function in an addon file, and only functions get exported - the exact trap that
    took `LM_TETHER_BREAK_DAMAGE` down.
  * `manual_weapons_tether` has to be REACHED. It is the last label in the file and is
    only ever jumped to; a `jump` to a label nothing defines is not a compile error, so
    a typo there is silent until a crew tows something.
  * the called-shot panel has to keep the square when it wants it, and the tow has to
    still be named in the strip when it does.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_manual_weapons_tether_panel
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

from sbs_utils.agent import clear_shared
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers gui/route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural import grav_tether as gt
from sbs_utils.procedural.gui.navigation import gui_reroute_client
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.spaceobject import SpaceObject

CID = 1

# Imports first, so each file's routes register in its own main. `import <x>.py` is what
# makes the helpers' functions MAST globals - the same call the addon loader makes.
#
# The panel is scheduled as a GUI SUB-TASK, which is how the real console runs it
# (`route_gui_navigate("normal_weap", manual_weapons_start)` at the top of
# manual_weapons.mast). Rerouting the GUI task straight INTO the panel instead looks like
# it works - the task lands on the right label and nothing errors - and draws nothing at
# all, because the panel only ever fills REGIONS and never builds the page they hang off.
# `harness_open` stands in for the console's own `gui_console("weapons")` + `await gui()`.
HARNESS_STORY = "\n".join([
    "import manual_beams_helpers.py",
    "import tether_indicator.py",
    "import manual_weapons.mast",
    "jump harness_open",
    "",
    "== harness_open ==",
    "    gui_row()",
    "    gui_text('$text:harness;')",
    "    gui_sub_task_schedule(manual_weapons_start)",
    "    await gui()",
    "",
])


class WeapPage(StoryPage):
    story = None


class _Emitted:
    def __init__(self):
        self.texts = []
        self.images = []

    def install(self):
        self._orig = {}
        for name, sink in (("send_gui_text", self.texts),
                           ("send_gui_image", self.images)):
            self._orig[name] = getattr(mock_sbs, name)
            setattr(mock_sbs, name, self._rec(sink, self._orig[name]))

    def remove(self):
        for name, fn in self._orig.items():
            setattr(mock_sbs, name, fn)

    def _rec(self, sink, orig):
        def _fn(client_id, parent, tag, props, left, top, right, bottom):
            sink.append((tag, props or ""))
            return orig(client_id, parent, tag, props, left, top, right, bottom)
        return _fn

    def clear(self):
        self.texts.clear()
        self.images.clear()

    def text_with(self, needle):
        return [p for _t, p in self.texts if needle in p]

    def image_with(self, needle):
        return [p for _t, p in self.images if needle in p]


class _Base(unittest.TestCase):
    def setUp(self):
        clear_shared()
        SpaceObject.clear()
        gt.grav_tether_clear_all()
        gt.grav_tether_set_attach_policy(None)
        gt.grav_tether_set_grab_speed_limit(None)
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

        self.emitted = _Emitted()
        self.emitted.install()

        story = MastStory()
        story.basedir = CONSOLES
        errors = story.compile(HARNESS_STORY, "weapharness", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        WeapPage.story = story
        FrameContext.mast = story

        self.rte = []
        self._orig_rte = MastScheduler.runtime_error
        MastScheduler.runtime_error = lambda s, message: self.rte.append(message)

        self.ship = to_object(player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser"))
        self.load = to_object(npc_spawn(1500, 0, 0, "Ore Hauler", "tsn",
                                        "tsn_light_cruiser", "behav_npcship"))
        self.foe = to_object(npc_spawn(800, 0, 0, "Raider", "raider",
                                       "tsn_light_cruiser", "behav_npcship"))
        mock_sbs.assign_client_to_ship(CID, self.ship.id)

        self.server = WeapPage()
        Gui.push(0, self.server)
        self.page = WeapPage()
        Gui.push(CID, self.page)
        self.present()

    def tearDown(self):
        self.emitted.remove()
        MastScheduler.runtime_error = self._orig_rte
        gt.grav_tether_clear_all()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        WeapPage.story = None
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
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def open_panel(self):
        """Re-enter the console's entry label, which re-runs the BUILDER.

        A present() only re-emits the tree the page already has, so a test that changes
        state and presents sees the panel from before the change.
        """
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(CID, "gui_present"))
        gui_reroute_client(CID, "harness_open")
        self.emitted.clear()
        self.present()

    def target(self, obj):
        """What the weapons console has locked. `weapon_target_UID` is where the shared
        do_select stores it, and `get_weapons_selection` is what reads it back."""
        self.ship.data_set.set("weapon_target_UID", to_id(obj), 0)

    def manual_on(self, on=True):
        self.ship.set_inventory_value("MANUAL_BEAMS_ON", on)


class TestTheConsoleShowsTheTow(_Base):
    def test_no_tether_no_readout(self):
        self.open_panel()
        self.assertEqual(self.emitted.text_with("grav-tether"), [])
        self.assertEqual(self.emitted.text_with("`TOW`"), [])

    def test_towing_puts_the_load_in_the_square(self):
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.open_panel()
        self.assertTrue(self.emitted.text_with("grav-tether engaged"),
                        "the strip did not say the tether was engaged")
        self.assertTrue(self.emitted.text_with("`TOW`"), "no mode word")
        self.assertTrue(self.emitted.text_with("`Ore Hauler`"), "the load is not named")
        self.assertTrue(self.emitted.image_with("image: ships/"),
                        "no silhouette in the square")

    def test_letting_go_takes_the_readout_with_it(self):
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.open_panel()
        self.assertTrue(self.emitted.text_with("`TOW`"))
        gt.grav_tether_release_any(self.ship)
        self.open_panel()
        self.assertEqual(self.emitted.text_with("`TOW`"), [])

    def test_the_called_shot_panel_keeps_the_square_but_still_names_the_tow(self):
        # Both apply at once: a gunner working a raider in beam range while the ship tows
        # a hulk. The square is the thing being actively worked; the tow moves to the
        # strip rather than disappearing.
        self.manual_on()
        self.target(self.foe)
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.open_panel()
        self.assertTrue(self.emitted.text_with("`weapons`"),
                        "the called-shot bands should own the square here")
        self.assertEqual(self.emitted.text_with("`TOW`"), [],
                         "the tether square must not draw over the called-shot panel")
        self.assertTrue(self.emitted.text_with("TOW Ore Hauler"),
                        "the tow was left completely unsaid")

    def test_the_readout_appears_without_reopening_the_console(self):
        """The `on change manual_tether_signature` watcher, pinned.

        Nobody reopens a console after pressing a button. Without the watcher the square
        would stay empty until the panel's own 3 second ticker came round, which reads as
        a tether that did not engage.
        """
        self.open_panel()
        self.assertEqual(self.emitted.text_with("`TOW`"), [])
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.emitted.clear()
        self.present()
        self.assertTrue(self.emitted.text_with("`TOW`"),
                        "the panel did not repaint when the tether engaged")
        gt.grav_tether_release_any(self.ship)
        self.emitted.clear()
        self.present()
        self.assertEqual(self.emitted.text_with("`TOW`"), [],
                         "the panel did not repaint when the tether let go")

    def test_manual_on_with_nothing_in_range_gives_the_square_to_the_tether(self):
        # Manual is on but there is no lock, so the called-shot panel minimizes - which
        # is every path into manual_weapons_minimize, and the one this hangs off.
        self.manual_on()
        self.target(0)
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.open_panel()
        self.assertTrue(self.emitted.text_with("`TOW`"),
                        "an empty square should have gone to the tether")


if __name__ == "__main__":
    unittest.main()
