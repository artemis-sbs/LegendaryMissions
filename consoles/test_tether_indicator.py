"""The grav-tether readout says what is on the beam, and shares the square honestly.

Three things here cannot be eyeballed and are the whole reason the panel exists:

  * the SILHOUETTE is the load's art, not the ship's own - draw the wrong end of the
    beam and the panel is confidently wrong rather than merely missing
  * the mode word tracks WHICH END we are on - towing and being towed are one registry
    entry and opposite experiences, and a swing puts the player on the pulled end
  * the words land inside the square they are labelling, because this borrows the
    called-shot panel's two-regions-one-rect trick and inherits its one failure mode

It also pins the repaint signature: it has to change when the beam changes and NOT when
the range does, or the console tears itself down every tick.
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

# Both helpers do `import sbs`, which only resolves inside the engine or under the
# mission runner. Bind it before the imports so the modules under test are the real ones.
sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils.agent import clear_shared
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the gui/route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural import grav_tether as gt
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.spaceobject import SpaceObject

import manual_beams_helpers as mb
import tether_indicator as ti

CID = 1

# The console around the panel is not the subject; the two builders are. `_STATE` stands
# in for the ship the console is on, exactly as the called-shot panel's test does it.
STORY = """
gui_region(manual_beams_area())
mt_panel_bars()
gui_region(manual_beams_label_area())
mt_panel_labels()
await gui()
"""

_STATE = {"ship": 0}


def mt_panel_bars():
    ti.manual_tether_bars(_STATE["ship"])


def mt_panel_labels():
    ti.manual_tether_labels(_STATE["ship"])


MastGlobals.import_python_function(mt_panel_bars)
MastGlobals.import_python_function(mt_panel_labels)
MastGlobals.import_python_function(mb.manual_beams_area)
MastGlobals.import_python_function(mb.manual_beams_label_area)


class _Emitted:
    """Every rect the page sent this present, by kind."""

    def __init__(self):
        self.images = []
        self.texts = []

    def install(self):
        self._orig = {}
        for name, sink in (("send_gui_image", self.images),
                           ("send_gui_text", self.texts)):
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

    def text_with(self, needle):
        return [t for t in self.texts if needle in (t[1] or "")]

    def image_with(self, needle):
        return [i for i in self.images if needle in (i[1] or "")]


class PanelPage(StoryPage):
    story = None


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

        self.ship = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        self.load = npc_spawn(1500, 0, 0, "Ore Hauler", "tsn", "tsn_light_cruiser",
                              "behav_npcship")
        _STATE["ship"] = self.ship.id

        self.emitted = _Emitted()
        self.emitted.install()

        story = MastStory()
        errors = story.compile(STORY, "mtpanel", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        PanelPage.story = story
        FrameContext.mast = story

        self.errors = []
        self._orig_rte = MastScheduler.runtime_error
        MastScheduler.runtime_error = lambda s, message: self.errors.append(message)

        self.page = None

    def tearDown(self):
        self.emitted.remove()
        MastScheduler.runtime_error = self._orig_rte
        gt.grav_tether_clear_all()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        PanelPage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        FrameContext.context = None
        SpaceObject.clear()

    def build(self):
        """Run the builders and record what they drew.

        A repaint re-emits the tree it already has rather than re-running the builder, so
        seeing the panel respond to a change means building it again - a fresh page is
        the smallest thing that does that.
        """
        Gui.clients = {}
        Gui.widget_list_sent = {}
        self.page = PanelPage()
        Gui.push(CID, self.page)
        self.emitted.clear()
        mock_sbs.sim._time_tick_counter += 30
        self.page.gui_state = "repaint"
        self.page.present(FakeEvent(CID, "gui_present"))
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")
        return self.page


class TestWhatItSays(_Base):
    def test_a_free_ship_has_nothing_to_report(self):
        self.assertEqual(ti.manual_tether_partner(self.ship.id), 0)
        self.assertEqual(ti.manual_tether_word(self.ship.id), "")
        self.assertEqual(ti.manual_tether_suffix(self.ship.id), "")
        self.assertEqual(ti.manual_tether_signature(self.ship.id), "")

    def test_towing_names_the_load_and_the_mode(self):
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.assertEqual(ti.manual_tether_partner(self.ship.id), self.load.id)
        self.assertEqual(ti.manual_tether_word(self.ship.id), "TOW")
        self.assertEqual(ti.manual_tether_name(self.ship.id), "Ore Hauler")
        self.assertIn("TOW Ore Hauler", ti.manual_tether_suffix(self.ship.id))

    def test_the_pulled_end_never_reads_as_the_puller(self):
        # A hostile beam pins the player: the same registry entry, and the word has to
        # say which end this is or the readout claims the crew grabbed their attacker.
        gt.grav_tether_tow(self.load, self.ship, 500)
        self.assertEqual(ti.manual_tether_word(self.ship.id), "TOWED")
        self.assertEqual(ti.manual_tether_word(self.load.id), "TOW")

    def test_a_swing_reads_as_a_swing_from_the_cockpit(self):
        gt.grav_tether_swing(self.load, self.ship, 800)
        self.assertEqual(ti.manual_tether_word(self.ship.id), "SWING")
        self.assertEqual(ti.manual_tether_word(self.load.id), "ANCHOR")

    def test_the_range_is_the_distance_to_the_load(self):
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.assertEqual(ti.manual_tether_range(self.ship.id), "1500")

    def test_a_long_name_is_cut_rather_than_pushing_the_range_off(self):
        self.load.name = "Extremely Long Freighter Name"
        self.load.comms_id = self.load.name
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.assertLessEqual(len(ti.manual_tether_name(self.ship.id)),
                             ti.MT_NAME_CHARS)

    def test_braces_in_a_name_are_stripped(self):
        # The name lands in an f-string; a brace arriving from data is a SyntaxError
        # reported against the line that DISPLAYS it, which reads as a panel bug.
        self.load.name = "Pod {7}"
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.assertNotIn("{", ti.manual_tether_name(self.ship.id))


class TestRepaintSignature(_Base):
    def test_it_changes_when_the_beam_does(self):
        before = ti.manual_tether_signature(self.ship.id)
        gt.grav_tether_tow(self.ship, self.load, 500)
        towing = ti.manual_tether_signature(self.ship.id)
        self.assertNotEqual(before, towing)
        gt.grav_tether_release_any(self.ship)
        self.assertEqual(ti.manual_tether_signature(self.ship.id), before)

    def test_it_does_not_change_as_the_load_drifts(self):
        # Range is deliberately out: in it, this fires every tick and the console tears
        # the panel down under the gunner's hands.
        gt.grav_tether_tow(self.ship, self.load, 500)
        before = ti.manual_tether_signature(self.ship.id)
        self.load.pos = mock_sbs.vec3(4000, 0, 0)
        self.assertEqual(ti.manual_tether_signature(self.ship.id), before)


class TestTheSquare(_Base):
    def test_the_silhouette_is_the_LOAD_not_our_own_hull(self):
        # Both hulls here are the same art on purpose - the check is that the panel asked
        # for the load's art by the load's id, which is the end that can be got wrong.
        self.load.data_set.set("art_id", "", 0)
        gt.grav_tether_tow(self.ship, self.load, 500)
        from sbs_utils.procedural.ship_data import ship_art_image
        expected = ship_art_image(self.load.id)
        self.build()
        self.assertTrue(expected, "the test hull has no flat art to draw")
        # The page normalizes `background-image:` to the engine's `image:` prop.
        self.assertTrue(self.emitted.image_with(f"image: {expected};"),
                        "the square did not draw the load's art")

    def test_the_mode_word_and_the_name_land_inside_the_square(self):
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.build()
        art = self.emitted.image_with("image: ships/")
        self.assertTrue(art, "no art rect to measure against")
        _t, _p, sq_l, sq_top, sq_r, sq_bottom = art[0]
        for needle in ("`TOW`", "`Ore Hauler`", "`1500`"):
            hits = self.emitted.text_with(f"$text:{needle};")
            self.assertEqual(len(hits), 1, f"expected one {needle} label")
            _t, _p, left, top, right, bottom = hits[0]
            self.assertGreaterEqual(top, sq_top - 0.01, f"{needle} above the square")
            self.assertLessEqual(bottom, sq_bottom + 0.01, f"{needle} below the square")
            self.assertGreaterEqual(left, sq_l - 0.01, f"{needle} left of the square")
            self.assertLessEqual(right, sq_r + 0.01, f"{needle} right of the square")

    def test_the_middle_band_is_left_clear_for_the_hull(self):
        # The widest part of a top-down sprite. Scrimming it would defeat the point of
        # drawing one, so exactly two scrims - top band and bottom band.
        gt.grav_tether_tow(self.ship, self.load, 500)
        self.build()
        scrims = self.emitted.image_with(f"color: {ti.MT_SCRIM};")
        self.assertEqual(len(scrims), 2, "expected a scrim on the top and bottom bands")

    def test_a_load_with_no_art_still_draws_a_readable_square(self):
        # A cargo pod has no flat sprite, and `ship_art_image` answers None for it. The
        # mode word has to carry the square rather than sit on a bright empty panel.
        orig = ti.ship_art_image
        ti.ship_art_image = lambda *a, **k: None
        try:
            gt.grav_tether_tow(self.ship, self.load, 500)
            self.build()
        finally:
            ti.ship_art_image = orig
        self.assertEqual(self.emitted.image_with("image: ships/"), [])
        self.assertTrue(self.emitted.image_with(ti.MT_NO_ART.split(":")[1].strip(" ;")),
                        "the fallback panel was not drawn")
        self.assertTrue(self.emitted.text_with("$text:`TOW`;"))


if __name__ == "__main__":
    unittest.main()
