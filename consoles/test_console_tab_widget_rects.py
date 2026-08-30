"""A console that goes to a tab and comes back is the console it was.

THE FIELD REPORT (2026-08-30): "on weapons or helm, click the Upgrades tab and then
click back to the normal tab, and the client console will be hosed - every widget
takes up the whole screen. Repros every time."

A widget-less tab (`gui_activate_console("upgrade")` and nothing else - see
items/item_gui.mast) hands the engine an EMPTY widget list, so every engine widget
this console declares falls off it. The library parks a dropped widget offscreen,
because one left declared keeps drawing against whatever the console last pointed at.
Coming back it has to put each one somewhere, and it used to guess the FULL CONSOLE
for any widget nothing had placed - which on Weapons and Helm was most of them.

This drives the real `layout_widgets.mast` around that round trip and asserts the
console comes back with exactly the rects it left with.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_console_tab_widget_rects
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
from sbs_utils.procedural.gui.navigation import gui_reroute_client
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.spaceobject import SpaceObject

CID = 1

# `harness_tab` is what EVERY widget-less console tab does - the Upgrades tab, Quest,
# Help, Library, Fabricate, Cargo, Hangar, Brain, Debug. Standing in for one of them by
# name would test that addon's plumbing; this tests the transition they all make.
#
# The console name is baked into the source rather than passed as a task variable:
# Gui.push presents immediately, so main has already reached harness_console before a
# test could set one.
def harness_story(console):
    return "\n".join([
        # layout_widgets.mast reads SETTINGS at its top level, and a story that does
        # not compile schedules no task at all. The real one comes from story.mast.
        "shared SETTINGS = {}",
        "import manual_beams_helpers.py",
        "import tether_indicator.py",
        "import layout_widgets.mast",
        "jump harness_console",
        "",
        "== harness_console ==",
        f'    gui_console("{console}")',
        "    await gui()",
        "",
        "== harness_tab ==",
        '    gui_activate_console("upgrade")',
        "    gui_row()",
        '    gui_text("$text:the upgrades tab;")',
        "    await gui()",
        "",
    ])


class ConsolePage(StoryPage):
    story = None


class _Rects:
    """Every send_client_widget_rects this client was given, newest last."""

    def __init__(self):
        self.calls = []

    def install(self):
        self._orig = mock_sbs.send_client_widget_rects

        def _fn(client_id, widget, *coords):
            self.calls.append((client_id, widget, tuple(coords)))
            return self._orig(client_id, widget, *coords)

        mock_sbs.send_client_widget_rects = _fn

    def remove(self):
        mock_sbs.send_client_widget_rects = self._orig

    def clear(self):
        self.calls.clear()

    def latest(self):
        """widget -> the last rect it was given on the console under test."""
        out = {}
        for cid, widget, coords in self.calls:
            if cid == CID:
                out[widget] = coords
        return out

    def not_matching(self, expected):
        """Every rect sent that is not where that widget belongs, in order -
        INCLUDING ones a later call corrected.

        Checking the last rect per widget is not enough: a console that places its
        own widgets re-sends the right rect microseconds later, so a wrong one is
        invisible in `latest()`. It still went to the engine, and on a console that
        does NOT place its widgets nothing corrects it at all.

        Comparing against each widget's OWN rect rather than banning one magic
        value, because on the main screen 3dview really does belong at the full
        console - the reason nobody ever reported that screen.
        """
        return [(w, c) for cid, w, c in self.calls
                if cid == CID and expected.get(w) is not None and c != expected[w]]


class _Base(unittest.TestCase):
    CONSOLE = "weapons"
    HULL = "tsn_light_cruiser"

    def setUp(self):
        clear_shared()
        SpaceObject.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        StoryPage._forget_parked_widgets()
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

        self.rects = _Rects()
        self.rects.install()

        story = MastStory()
        story.basedir = CONSOLES
        errors = story.compile(harness_story(self.CONSOLE), "tabharness", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        ConsolePage.story = story
        FrameContext.mast = story

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append

        self.ship = to_object(player_spawn(0, 0, 0, "Artemis", "tsn", self.HULL))
        mock_sbs.assign_client_to_ship(CID, self.ship.id)

        self.server = ConsolePage()
        Gui.push(0, self.server)
        self.page = ConsolePage()
        Gui.push(CID, self.page)
        self.present()

    def tearDown(self):
        self.rects.remove()
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        StoryPage._forget_parked_widgets()
        ConsolePage.story = None
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

    def enter(self, label):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(CID, "gui_present"))
        gui_reroute_client(CID, label)
        self.present()

    def round_trip(self):
        """console -> a widget-less tab -> console. Returns (before, after)."""
        self.enter("harness_console")
        before = self.rects.latest()
        self.enter("harness_tab")
        self.rects.clear()
        self.enter("harness_console")
        return before, self.rects.latest()


class TestWeaponsTabRoundTrip(_Base):
    CONSOLE = "weapons"

    def test_the_console_places_every_widget_it_declares(self):
        """The premise of the fix. A widget nothing places is one nothing can put
        back, so Weapons leaving six of its list to the engine is what made the
        library guess in the first place."""
        self.enter("harness_console")
        placed = set(self.rects.latest())
        declared = {w for w in self.page.widgets.split("^") if w}
        self.assertTrue(declared, "the console declared no engine widgets")
        self.assertEqual(declared - placed, set(),
                         "declared but never placed - the library would have to guess")

    def test_no_widget_is_moved_anywhere_it_does_not_belong(self):
        """THE REPORT. Every returning widget was un-parked to the FULL CONSOLE,
        so they all landed on top of each other.

        Checked across EVERY rect the return sent, not just the one that stuck:
        now that this console places its own widgets, its ConsoleWidgets re-send
        the right rect in the same frame and would hide a wrong one.
        """
        before, _after = self.round_trip()
        wrong = self.rects.not_matching(before)
        self.assertEqual(wrong, [], f"sent somewhere it does not belong: {wrong}")

    def test_the_console_comes_back_exactly_as_it_left(self):
        before, after = self.round_trip()
        self.assertEqual(after, before)


class TestWeaponsColumnIsPixelStable(_Base):
    """The weapons column is the same column on every screen.

    It used to be the engine's own percentages, so the shield button sat somewhere
    different at every resolution and a 200px hole opened between the camera dial and
    the rest. Pixels do not move; percentages do.
    """
    CONSOLE = "weapons"

    COLUMN = ["main_screen_control", "shield_control", "weap_beam_freq",
              "weap_beam_speed", "weap_torp_conversion"]
    SIZES = [(1600, 900), (1920, 1080), (2560, 1440), (1280, 1024)]

    def _column_px(self, w, h):
        from sbs_utils.helpers import FrameContext
        from sbs_utils.vec import Vec3
        FrameContext.aspect_ratios[CID] = Vec3(w, h, 1)
        self.enter("harness_console")
        rects = self.rects.latest()
        out = {}
        for name in self.COLUMN:
            r = rects.get(name)
            self.assertIsNotNone(r, f"{name} was never placed")
            left, top, right, bottom = r[0], r[1], r[2], r[3]
            # Right-aligned, so x is measured from the screen's right edge.
            out[name] = (round((100 - right) * w / 100, 1), round(top * h / 100, 1),
                         round((right - left) * w / 100, 1),
                         round((bottom - top) * h / 100, 1))
        return out

    def test_the_column_is_the_same_pixels_at_every_resolution(self):
        first = None
        for w, h in self.SIZES:
            got = self._column_px(w, h)
            if first is None:
                first, first_size = got, (w, h)
            else:
                self.assertEqual(got, first,
                                 f"the column moved between {first_size} and {(w, h)}")

    def test_the_column_is_280_wide_and_has_no_hole_in_it(self):
        col = self._column_px(1920, 1080)
        for name, (_x, _y, wide, _tall) in col.items():
            self.assertEqual(wide, 280.0, f"{name} is not the column width")
        # Every row follows the one above it with only a spacer between - the 200px
        # hole the engine's own layout left is what this replaced. The first gap is
        # wider on purpose: the camera dial is a different kind of control from the
        # four below it, and butting them together read as one block.
        gaps = []
        for above, below in zip(self.COLUMN, self.COLUMN[1:]):
            _x, y, _w, tall = col[above]
            gaps.append((f"{above} -> {below}", round(col[below][1] - (y + tall), 1)))
        self.assertEqual([g for _n, g in gaps], [16.0, 8.0, 8.0, 8.0],
                         f"not a clean spacer between every row: {gaps}")

    def test_the_camera_dial_keeps_its_shape(self):
        """280x180. Squash this one and the compass reads as an oval."""
        col = self._column_px(2560, 1440)
        _x, _y, wide, tall = col["main_screen_control"]
        self.assertEqual((wide, tall), (280.0, 180.0))


class TestHelmTabRoundTrip(TestWeaponsTabRoundTrip):
    """Helm is the other console that had engine-placed widgets, and the other one
    named in the report."""
    CONSOLE = "helm"


class TestHelmJumpControls(_Base):
    """A jump ship shows its jump controls on the FIRST layout.

    Reported on a xim_dreadnought: "the initial layout they do not show up, I have to
    change console back and then they show up". The console asked
    `jump_drive_active`, which //shared/signal/grid_interior_built writes once the
    interior has been BUILT - and interiors are built late and asynchronously
    (grid_interior_request defers them so a roster of eight ships is not built three
    times over before anyone picks a map). A console that opened first got "no" and
    nothing told it to ask again.

    These cases build the console COLD - no interior, no blob value - which is the
    state the report describes.
    """
    CONSOLE = "helm"

    def _jump_widgets(self):
        self.enter("harness_console")
        declared = {w for w in self.page.widgets.split("^") if w}
        placed = self.rects.latest()
        return declared, placed

    def _assert_jump(self, present):
        declared, placed = self._jump_widgets()
        for w in ("helm_jump", "quick_jump"):
            self.assertEqual(w in declared, present, f"{w} declared={w in declared}")
            self.assertEqual(placed.get(w) is not None, present,
                             f"{w} placed={placed.get(w)}")

    def test_a_xim_dreadnought_has_them_on_the_first_layout(self):
        self.HULL = "xim_dreadnought"
        self.tearDown(); self.setUp()
        self._assert_jump(True)

    def test_a_xim_scout_has_them_too(self):
        self.HULL = "xim_scout"
        self.tearDown(); self.setUp()
        self._assert_jump(True)

    def test_a_warp_hull_does_not_get_them(self):
        """gui_layout_widget ADDS to the widget list, so placing these
        unconditionally would put a jump drive on a warp ship."""
        self.HULL = "tsn_light_cruiser"
        self.tearDown(); self.setUp()
        self._assert_jump(False)

    def test_a_hull_with_no_drive_at_all_does_not_get_them(self):
        self.HULL = "tsn_fighter"
        self.tearDown(); self.setUp()
        self._assert_jump(False)


class TestMainScreenTabRoundTrip(TestWeaponsTabRoundTrip):
    """The main screen was never reported, because its one engine-placed widget is
    `3dview` and un-parking THAT to the full console happens to look right. It is
    also the screen that meets the un-park most often - it toggles 3dview <-> 2dview
    every time the crew goes Tactical and back."""
    CONSOLE = "mainscreen"


class TestConsolesThatAlreadyPlacedEverything(_Base):
    """Science, Engineering and Comms placed every widget they declared, so they
    could not show the reported failure - and must not start showing one now."""

    def test_science(self):
        self._round_trip_clean("science")

    def test_engineering(self):
        self._round_trip_clean("engineering")

    def test_comms(self):
        self._round_trip_clean("comms")

    def _round_trip_clean(self, console):
        self.CONSOLE = console
        self.tearDown()
        self.setUp()
        before, after = self.round_trip()
        self.assertEqual(self.rects.not_matching(before), [])
        self.assertEqual(after, before)
