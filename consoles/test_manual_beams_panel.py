"""The Manual Beams called-shot panel draws what it says it draws.

The panel's whole design rests on one thing that cannot be eyeballed reliably: two
absolutely-positioned regions that declare the SAME rect, so a label lands exactly on
the bar it belongs to. Nothing else in the layout engine puts one widget over another,
so if those two rects ever stop agreeing the panel silently goes crooked - the bars stay
where they are and the words slide off them.

So this measures the actual rects the page emits, not the strings that ask for them, and
checks the three things that would be wrong without anyone noticing:

  * every band's label sits inside its own band's bar
  * the fill is bottom-anchored and its height tracks the health it claims to show
  * clicking a band arms THAT system, and only that one

It also pins the two guards in `manual_beams_health` (engine `None`, and the overshoot
the called-shot route creates by growing `system_damage` geometrically), because both are
invisible in an ordinary headless run.
"""

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

# The helper does `import sbs`, which only resolves inside the engine or under the
# mission runner. Bind it before the import so the module under test is the real one.
sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils.agent import clear_shared
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the gui/route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.spaceobject import SpaceObject

import manual_beams_helpers as mb

CID = 1

# The story under test is deliberately tiny: the panel builders are the subject, and the
# console around them is not. `target_id` and the flags are pushed in as globals.
STORY = """
gui_region(manual_beams_area())
mb_panel_bars()
gui_region(manual_beams_label_area())
mb_panel_labels()
await gui()
"""


class PanelPage(StoryPage):
    story = None


class _Emitted:
    """Every rect the page sent this present, by kind."""

    def __init__(self):
        self.images = []       # (tag, props, l, t, r, b)
        self.texts = []
        self.clicks = []

    def install(self):
        self._orig = {}
        for name, sink in (("send_gui_image", self.images),
                           ("send_gui_text", self.texts),
                           ("send_gui_clickregion", self.clicks)):
            self._orig[name] = getattr(mock_sbs, name)
            setattr(mock_sbs, name, self._recorder(sink, self._orig[name]))

    def remove(self):
        for name, fn in self._orig.items():
            setattr(mock_sbs, name, fn)

    def _recorder(self, sink, orig):
        def _fn(client_id, parent, tag, props, left, top, right, bottom):
            sink.append((tag, props, left, top, right, bottom))
            return orig(client_id, parent, tag, props, left, top, right, bottom)
        return _fn

    def clear(self):
        self.images.clear()
        self.texts.clear()
        self.clicks.clear()

    def text_with(self, needle):
        return [t for t in self.texts if needle in (t[1] or "")]

    def click_named(self, tag):
        return [c for c in self.clicks if c[0] == tag]


_STATE = {"target": 0, "armed": None, "hit": False}


def mb_panel_bars():
    mb.manual_beams_bars(_STATE["target"], _STATE["hit"])


def mb_panel_labels():
    mb.manual_beams_labels(_STATE["target"], _STATE["armed"], _STATE["hit"])


MastGlobals.import_python_function(mb_panel_bars)
MastGlobals.import_python_function(mb_panel_labels)
MastGlobals.import_python_function(mb.manual_beams_area)
MastGlobals.import_python_function(mb.manual_beams_label_area)


class _Base(unittest.TestCase):
    def setUp(self):
        clear_shared()
        SpaceObject.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

        self.ship = npc_spawn(0, 0, 0, "Shooter", "tsn", "tsn_light_cruiser",
                              "behav_npcship")
        self.target = npc_spawn(2000, 0, 0, "Target", "raider", "tsn_light_cruiser",
                                "behav_npcship")
        _STATE["target"] = self.target.id
        _STATE["armed"] = None
        _STATE["hit"] = False

        self.emitted = _Emitted()
        self.emitted.install()

        story = MastStory()
        errors = story.compile(STORY, "mbpanel", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        PanelPage.story = story
        FrameContext.mast = story

        self.errors = []
        self._orig_rte = MastScheduler.on_runtime_error
        # StoryScheduler OVERRIDES `runtime_error`, so patching it on MastScheduler
        # binds a method nothing calls and the assertion below is vacuous. The
        # class-level `on_runtime_error` seam is what the story scheduler actually
        # fires (and is what cosmos_dev's verdict uses).
        MastScheduler.on_runtime_error = self.errors.append

        self.page = None

    def build(self, n=1):
        """(Re)build the panel from the CURRENT state and record what it draws.

        A repaint re-emits the layout tree it already has; it does not re-run the
        builder. The console rebuilds through `gui_rebuild(region)` on its ticker, so a
        test that wants to see the panel respond to a change has to build it again -
        which here means a fresh page, the smallest thing that runs the builders twice.
        """
        Gui.clients = {}
        Gui.widget_list_sent = {}
        self.page = PanelPage()
        Gui.push(CID, self.page)
        self.present(n)
        return self.page

    def tearDown(self):
        self.emitted.remove()
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        PanelPage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        FrameContext.context = None
        SpaceObject.clear()

    def present(self, n=1):
        """Draw once, recording only the LAST frame.

        Every repaint re-emits the whole panel, so recording several frames would count
        each widget once per frame and say nothing about what is on screen.
        """
        for _ in range(max(0, n - 1)):
            mock_sbs.sim._time_tick_counter += 30
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(CID, "gui_present"))
        self.emitted.clear()
        mock_sbs.sim._time_tick_counter += 30
        self.page.gui_state = "repaint"
        self.page.present(FakeEvent(CID, "gui_present"))
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")

    def set_health(self, obj, pcts):
        """pcts keyed by SHPSYS. Capacity 100 so a percent is a damage count."""
        for system, pct in pcts.items():
            obj.data_set.set("system_max_damage", 100.0, system)
            obj.data_set.set("system_damage", 100.0 - pct, system)

    def click(self, click_tag):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(CID, "gui_message"))
        Gui.on_message(FakeEvent(client_id=CID, tag="gui_message", sub_tag=click_tag))


class TestHealth(_Base):
    def test_percent_is_share_remaining(self):
        self.set_health(self.target, {mock_sbs.SHPSYS.WEAPONS: 60})
        self.assertEqual(
            mb.manual_beams_health(self.target.id, mock_sbs.SHPSYS.WEAPONS), 60)

    def test_overshoot_clamps_to_zero_not_negative(self):
        # The called-shot route grows system_damage by *1.35 and only THEN compares it
        # to the max, so a dying system reports more damage than it has capacity for.
        # Unclamped that is a negative bar, which the layout draws as an inverted rect.
        self.target.data_set.set("system_max_damage", 4.0, mock_sbs.SHPSYS.ENGINES)
        self.target.data_set.set("system_damage", 9.0, mock_sbs.SHPSYS.ENGINES)
        self.assertEqual(
            mb.manual_beams_health(self.target.id, mock_sbs.SHPSYS.ENGINES), 0)

    def test_no_capacity_reads_full_not_wrecked(self):
        # A hull nothing has declared a capacity for is unknown, not destroyed.
        self.target.data_set.set("system_max_damage", 0.0, mock_sbs.SHPSYS.SENSORS)
        self.assertEqual(
            mb.manual_beams_health(self.target.id, mock_sbs.SHPSYS.SENSORS), 100)

    def test_a_target_that_is_gone_is_zero(self):
        self.assertEqual(mb.manual_beams_health(0, mock_sbs.SHPSYS.WEAPONS), 0)


class TestPanelGeometry(_Base):
    def _band_rect(self, name):
        """The band's label rect - the text the player reads is the band, as far as
        'is this lined up' is concerned."""
        hits = self.emitted.text_with(f"$text:`{name}`;")
        self.assertEqual(len(hits), 1, f"expected one {name!r} label, got {len(hits)}")
        return hits[0][2:]

    def test_each_label_sits_inside_its_own_bar(self):
        """The whole point of the two-region design. A label that drifts off its bar is
        the failure this panel cannot survive, and it cannot be seen in a diff."""
        self.set_health(self.target, {mock_sbs.SHPSYS.WEAPONS: 100,
                                      mock_sbs.SHPSYS.SENSORS: 100,
                                      mock_sbs.SHPSYS.ENGINES: 100})
        self.build()
        for name, system, tag in mb.MB_SYSTEMS:
            _l, top, _r, bottom = self._band_rect(name)
            fills = [i for i in self.emitted.images
                     if mb.MB_FILL_GOOD in (i[1] or "")]
            covering = [f for f in fills if f[3] <= top + 0.01 and f[5] >= bottom - 0.01]
            self.assertTrue(covering,
                            f"{name}: label {top}..{bottom} is on no full bar")

    def test_the_fill_is_bottom_anchored_and_tracks_health(self):
        self.set_health(self.target, {mock_sbs.SHPSYS.WEAPONS: 100,
                                      mock_sbs.SHPSYS.SENSORS: 50,
                                      mock_sbs.SHPSYS.ENGINES: 0})
        self.build()
        # weapons full, sensors half, engines empty - and the half one has to hang off
        # the BOTTOM of its band, not the top.
        _l, w_top, _r, w_bottom = self._band_rect("weapons")
        _l, s_top, _r, s_bottom = self._band_rect("sensors")

        full = [i for i in self.emitted.images if mb.MB_FILL_GOOD in (i[1] or "")]
        self.assertEqual(len(full), 1, "only weapons should be in the good band")
        half = [i for i in self.emitted.images if mb.MB_FILL_HURT in (i[1] or "")]
        self.assertEqual(len(half), 1, "only sensors should be in the hurt band")

        band_h = w_bottom - w_top
        self.assertAlmostEqual(full[0][5] - full[0][3], band_h, delta=band_h * 0.15)
        self.assertAlmostEqual(half[0][5] - half[0][3], band_h / 2, delta=band_h * 0.15)
        # Bottom-anchored: the half bar ends where its band ends.
        self.assertAlmostEqual(half[0][5], s_bottom, delta=band_h * 0.15)
        self.assertGreater(half[0][3], s_top, "a half bar must not start at the top")

        # An empty system draws no fill at all rather than a zero-height rect.
        self.assertEqual(
            [i for i in self.emitted.images if mb.MB_FILL_BAD in (i[1] or "")], [])

    def test_the_percent_is_shown_and_the_name_does_not_move_with_it(self):
        self.set_health(self.target, {mock_sbs.SHPSYS.WEAPONS: 100})
        self.build()
        wide = self._band_rect("weapons")
        self.assertTrue(self.emitted.text_with("$text:`100%`;"))

        self.set_health(self.target, {mock_sbs.SHPSYS.WEAPONS: 7})
        self.build()
        narrow = self._band_rect("weapons")
        self.assertTrue(self.emitted.text_with("$text:`7%`;"))
        self.assertEqual(wide, narrow, "the name moved when the number changed width")

    def test_every_band_is_its_own_click_target(self):
        self.build()
        for _name, _system, tag in mb.MB_SYSTEMS:
            self.assertEqual(len(self.emitted.click_named(tag)), 1,
                             f"no click region for {tag}")

    def test_the_armed_band_is_the_only_one_highlighted(self):
        _STATE["armed"] = mock_sbs.SHPSYS.SENSORS
        self.build()
        armed = self.emitted.text_with("$text:`sensors`;")[0][1]
        other = self.emitted.text_with("$text:`weapons`;")[0][1]
        self.assertIn(mb.MB_TEXT_ARMED, armed)
        self.assertNotIn(mb.MB_TEXT_ARMED, other)


class TestHitFlash(_Base):
    def test_hit_covers_the_square_and_lands_in_the_middle_band(self):
        self.set_health(self.target, {mock_sbs.SHPSYS.WEAPONS: 100,
                                      mock_sbs.SHPSYS.SENSORS: 100,
                                      mock_sbs.SHPSYS.ENGINES: 100})
        self.build()
        _l, sensors_top, _r, sensors_bottom = self.emitted.text_with(
            "$text:`sensors`;")[0][2:]

        _STATE["hit"] = True
        self.build()
        # The band labels are gone; one word, and its CENTER is inside the vertical span
        # the sensors band occupied - which is what "centered" means here, the engine
        # centering a single line in the rect it is given.
        self.assertEqual(self.emitted.text_with("$text:`weapons`;"), [])
        hit = self.emitted.text_with("$text:`HIT`;")
        self.assertEqual(len(hit), 1)
        _l, top, _r, bottom = hit[0][2:]
        self.assertGreater((top + bottom) / 2, sensors_top)
        self.assertLess((top + bottom) / 2, sensors_bottom)

    def test_the_flash_keeps_every_click_region_exactly_where_it_was(self):
        """The panel's hit targets must not move or vanish when the flash comes up.

        The engine's `weapon_2d_view` runs underneath this whole panel, and a band's
        click region is the only thing absorbing a click over it. When the flash drew
        three plain rows instead of the bands, the square had NO click regions for two
        seconds - a click during the flash went through to the 2d view, selected empty
        space, and dropped the weapons lock. `target_id` then read 0 and the panel
        minimized itself, which looks like "the panel disappears after a hit".
        """
        self.build()
        before = {c[0]: c[2:] for c in self.emitted.clicks}

        _STATE["hit"] = True
        self.build()
        during = {c[0]: c[2:] for c in self.emitted.clicks}

        for _name, _system, tag in mb.MB_SYSTEMS:
            self.assertIn(tag, during, f"{tag} has no click region during the flash")
            self.assertEqual(before[tag], during[tag],
                             f"{tag} moved when the flash came up")

    def test_a_band_still_arms_while_the_flash_is_up(self):
        mock_sbs.assign_client_to_ship(CID, self.ship.id)
        _STATE["hit"] = True
        self.build()
        self.click("mb_engines")
        self.assertEqual(get_inventory_value(self.ship.id, "MANUAL_SYSTEM"),
                         mock_sbs.SHPSYS.ENGINES)


class TestArming(_Base):
    def test_a_click_arms_that_system_and_no_other(self):
        mock_sbs.assign_client_to_ship(CID, self.ship.id)
        self.build()
        self.click("mb_sensors")
        self.assertEqual(get_inventory_value(self.ship.id, "MANUAL_SYSTEM"),
                         mock_sbs.SHPSYS.SENSORS)

    def test_an_unrelated_click_arms_nothing(self):
        """A section's callback is invoked for EVERY message the client sends, not only
        the ones carrying its tag, so the handler filters. Without the filter, ticking
        the Manual checkbox armed all three systems at once."""
        mock_sbs.assign_client_to_ship(CID, self.ship.id)
        self.build()
        self.click("some_other_widget")
        self.assertIsNone(get_inventory_value(self.ship.id, "MANUAL_SYSTEM"))

    def test_switching_system_throws_away_a_won_critical(self):
        mock_sbs.assign_client_to_ship(CID, self.ship.id)
        self.build()
        set_inventory_value(self.ship.id, "MANUAL_SYSTEM", mock_sbs.SHPSYS.WEAPONS)
        set_inventory_value(self.ship.id, "MANUAL_LAST_PICK", mock_sbs.SHPSYS.WEAPONS)
        set_inventory_value(self.ship.id, "MANUAL_CRITICAL_HIT", self.target.id)

        self.click("mb_engines")
        self.assertIsNone(get_inventory_value(self.ship.id, "MANUAL_CRITICAL_HIT"))
        self.assertEqual(get_inventory_value(self.ship.id, "MANUAL_SYSTEM"),
                         mock_sbs.SHPSYS.ENGINES)

    def test_a_click_repaints_every_manual_console(self):
        from sbs_utils.procedural.execution import get_shared_variable
        mock_sbs.assign_client_to_ship(CID, self.ship.id)
        self.build()
        before = get_shared_variable("manual_beams_version", 0) or 0
        self.click("mb_weapons")
        self.assertGreater(get_shared_variable("manual_beams_version", 0), before)


class TestMastCallsResolve(unittest.TestCase):
    """Every `manual_beams_*` the console calls is a public function in the helper.

    The helper's functions become MAST globals because `consoles/__init__.mast` says
    `import manual_beams_helpers.py`. That registration is all-or-nothing and completely
    silent: a rename, a typo, or a leading underscore does not fail the compile, it fails
    the first time a player opens the weapons console, as `name '...' is not defined`.
    Headless never enters a console (gui 0/9), so nothing else in the suite can see it.

    Static on purpose - no engine, no page, no mission boot.
    """

    def setUp(self):
        import os
        import re
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "manual_weapons.mast"), encoding="utf-8") as f:
            mast = f.read()
        # Comments in .mast are `#`; a name mentioned in prose is not a call.
        code = chr(10).join(l for l in mast.splitlines() if not l.strip().startswith("#"))
        self.called = set(re.findall(r"(manual_beams_[a-z0-9_]*)\s*\(", code))
        with open(os.path.join(here, "manual_beams_helpers.py"), encoding="utf-8") as f:
            helper = f.read()
        self.defined = set(re.findall(r"^def\s+([a-z_][a-z0-9_]*)", helper, re.M))
        with open(os.path.join(here, "__init__.mast"), encoding="utf-8") as f:
            init = f.read()
        self.imported = set(re.findall(r"^import\s+(\S+)\.py\s*$", init, re.M))

    def test_the_helper_is_imported_by_the_addon(self):
        self.assertIn("manual_beams_helpers", self.imported,
                      "consoles/__init__.mast does not import the helper, so none of "
                      "its functions are MAST globals")

    def test_every_call_has_a_definition(self):
        self.assertTrue(self.called, "found no manual_beams_* calls to check")
        missing = sorted(self.called - self.defined)
        self.assertEqual(missing, [], f"called from MAST but not defined: {missing}")

    def test_nothing_called_from_mast_is_private(self):
        # A leading underscore is skipped by the registration since 2026-08-16.
        private = sorted(n for n in self.called if n.startswith("_"))
        self.assertEqual(private, [])


if __name__ == "__main__":
    unittest.main()
