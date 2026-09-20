"""The avatar editor's REAL .mast compiles and builds a screen, for every race.

`test_avatar_required` is static - it reads the file and checks two lines are present.
That cannot see the thing most likely to break after the 2026-09 face-sheet redraw: the
editor's control loop now has a DROPDOWN branch for features that carry names, and a
branch that is never executed is a branch nobody has tested. A headless mission run does
not reach it either - `--test` never enters a console page, so the editor's coverage
there is exactly zero.

So this compiles the shipped file, runs `avatar_editor_show` for each of the six races,
and asserts the page actually emitted controls and a face. A MAST runtime error inside a
GUI build is otherwise silent: the screen just comes up empty.

    PYTHONPATH=../sbs_utils python -m unittest avatar_editor.test_avatar_editor_runs
"""

from sbs_utils.fs import test_set_exe_dir

test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils import faces
from sbs_utils.agent import clear_shared
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the gui nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.spaceobject import SpaceObject

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import avatar_helper  # noqa: E402

# Register EVERY public function the helper defines, the way the addon loader does for an
# `import avatar_helper.py` line. Listing them by name here drifted the moment the editor
# grew a new one, and the failure is a runtime NameError inside a GUI build - which in the
# engine is a blank screen, not an error.
for _name in dir(avatar_helper):
    if _name.startswith("_"):
        continue
    _fn = getattr(avatar_helper, _name)
    if callable(_fn) and getattr(_fn, "__module__", None) == avatar_helper.__name__:
        MastGlobals.import_python_function(_fn)
MastGlobals.import_python_module("sbs_utils.faces")

CID = 1


class EditorPage(StoryPage):
    story = None


class _Emitted:
    """Everything the page sent during a present, by widget kind."""

    KINDS = ("send_gui_text", "send_gui_slider", "send_gui_dropdown",
             "send_gui_checkbox", "send_gui_face", "send_gui_button")

    def __init__(self):
        self.by_kind = {k: [] for k in self.KINDS}
        self._orig = {}

    def install(self):
        for name in self.KINDS:
            orig = getattr(mock_sbs, name, None)
            if orig is None:
                continue
            self._orig[name] = orig
            setattr(mock_sbs, name, self._recorder(name, orig))

    def remove(self):
        for name, fn in self._orig.items():
            setattr(mock_sbs, name, fn)

    def _recorder(self, name, orig):
        def _fn(*args, **kwargs):
            # args[3] is the style/value payload for every send_gui_* in this family.
            self.by_kind[name].append(args[3] if len(args) > 3 else None)
            return orig(*args, **kwargs)
        return _fn


def _editor_source():
    with open(os.path.join(HERE, "avatar_editor.mast"), encoding="utf-8") as f:
        return f.read()


class TestEditorRuns(unittest.TestCase):
    def setUp(self):
        clear_shared()
        SpaceObject.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

        self.emitted = _Emitted()
        self.emitted.install()

        self.story = MastStory()
        errors = self.story.compile(_editor_source(), "avatar_editor", self.story)
        self.assertEqual(errors, [], f"avatar_editor.mast does not compile: {errors}")
        self.story.compiler_errors = []
        EditorPage.story = self.story
        FrameContext.mast = self.story

        self.errors = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.errors.append

    def tearDown(self):
        self.emitted.remove()
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        FrameContext.mast = None

    def _face_on_screen(self, page):
        """The face string the preview widget is actually showing.

        Read off the widget rather than out of a shared variable: this is the thing the
        player looks at, and it is what a repaint has to have updated.
        """
        for entry in page.tag_map.values():
            item = entry[0] if isinstance(entry, tuple) else entry
            if type(item).__name__ == "Face":
                return str(item.value)
        return ""

    def _press(self, page, text):
        """Press the named button and let the page settle, the way the engine does."""
        from sbs_utils.pages.layout.layout import Dirty
        tag = None
        for t, entry in page.tag_map.items():
            item = entry[0] if isinstance(entry, tuple) else entry
            if type(item).__name__ == "Button" and text in str(getattr(item, "value", "")):
                tag = str(t)
        self.assertIsNotNone(tag, f"no {text!r} button on the page")
        page.on_message(FakeEvent(client_id=CID, tag="gui_message", sub_tag=tag))
        Dirty.represent_dirty()
        for _ in range(3):
            Gui.present(FakeEvent(CID, "gui_present"))

    def _run(self, race):
        """Open the editor on one race and let the page present a few frames.

        `start_label` / `start_data` is the seam StoryPage already offers for starting a
        GUI task somewhere other than main - the same one the web-page routes use - so
        this drives the editor exactly the way the picker does rather than reaching past
        it into the scheduler.
        """
        page = EditorPage()
        page.start_label = "avatar_editor_show"
        page.start_data = {"av_race": race, "av_required": ""}
        Gui.push(CID, page)
        page.start_story(CID)
        for _ in range(6):
            Gui.present(FakeEvent(CID, "gui_present"))
        return page

    def test_every_race_builds_a_screen(self):
        for race in ("terran", "skaraan", "kralien", "torgoth", "ximni", "arvonian"):
            with self.subTest(race=race):
                self.setUp()
                try:
                    self._run(race)
                    self.assertEqual(self.errors, [],
                                     f"{race}: MAST runtime error in the editor")
                    self.assertTrue(self.emitted.by_kind["send_gui_face"],
                                    f"{race}: no face preview was drawn")
                finally:
                    self.tearDown()

    def test_a_short_named_list_is_a_dropdown(self):
        """Body is two options - Masculine / Feminine - so it reads best as a dropdown."""
        self._run("terran")
        self.assertEqual(self.errors, [])
        drops = " | ".join(str(d) for d in self.emitted.by_kind["send_gui_dropdown"])
        self.assertIn("Masculine", drops)
        self.assertIn("Feminine", drops)

    def test_a_long_named_list_is_a_slider_that_still_shows_the_name(self):
        """The owner's call: a dropdown over ten entries is unusable in the engine, and
        the skin palette is 39 tones.

        So a long named list becomes a slider - but a bare 0..38 slider is worse than the
        dropdown was, because nothing tells you which tone you are on. The label beside it
        carries "Feature: Name" and is rewritten as the slider moves. Both halves matter;
        this pins both.
        """
        self._run("terran")
        self.assertEqual(self.errors, [])
        texts = " | ".join(str(t) for t in self.emitted.by_kind["send_gui_text"])
        drops = " | ".join(str(d) for d in self.emitted.by_kind["send_gui_dropdown"])
        for feature, a_name in (("Eyes", "Open"), ("Mouth", "Neutral"),
                                ("Skin Tone", "none"), ("Hair Tone", "none")):
            # Eyes opens on "Open" because a new avatar starts from the race's NEUTRAL
            # expression, not from index 0 - index 0 is "Angry".
            with self.subTest(feature=feature):
                self.assertIn(f"{feature}: {a_name}", texts,
                              f"{feature} lost its name label")
                self.assertNotIn(a_name, drops,
                                 f"{feature} is still being drawn as a dropdown")
        self.assertTrue(self.emitted.by_kind["send_gui_slider"], "no sliders were drawn")

    def test_the_name_label_follows_its_own_row(self):
        """Every row's handler is compiled in the same loop, so a directly-referenced
        label widget would resolve to the LAST row's and every slider would rename the
        bottom one. The reference travels through `data` instead; this checks the rows
        really do carry distinct labels rather than all showing the same feature."""
        self._run("terran")
        labeled = [str(t) for t in self.emitted.by_kind["send_gui_text"]
                    if ": " in str(t) and "$text" in str(t)]
        features = {s.split(":")[0] for s in
                    [x.split("`")[1] for x in labeled if "`" in x]}
        self.assertGreaterEqual(len(features), 3,
                                f"rows are not carrying their own labels: {labeled}")

    def test_moving_the_slider_renames_the_label(self):
        """The whole point of the slider-plus-name: drag it and the NAME keeps up.

        Rendering the label once proves nothing - it is written at build time, so a broken
        handler still shows a correct label until you touch it. This drives a real slider
        change and reads back what the page re-sent.

        Two things the harness has to do that a present() alone does not:
        `page.on_message` is the dispatch a GuiClient performs (Gui.on_message routes
        through Gui.clients, which a bare Gui.push here does not populate), and
        `Dirty.represent_dirty()` is what actually re-sends a changed widget - the engine
        calls it once per frame after the handlers run. Without it the label updates in
        the tree and nothing goes out, which looks exactly like a dead handler.
        """
        from sbs_utils.pages.layout.layout import Dirty

        page = self._run("terran")
        sliders = [(str(tag), entry[0]) for tag, entry in page.tag_map.items()
                   if type(entry[0]).__name__ == "Slider"]
        self.assertTrue(sliders, "no slider on the page to drive")
        # The LAST slider is Hair Tone: features are emitted in FACE_FEATURES order and
        # the two tone controls come last. It is one of the named ones.
        tag, _widget = sliders[-1]

        self.emitted.by_kind["send_gui_text"].clear()
        ev = FakeEvent(client_id=CID, tag="gui_message", sub_tag=tag)
        ev.sub_float = 7.0          # not a constructor arg; legal before freeze()
        page.on_message(ev)
        Dirty.represent_dirty()

        resent = [str(t) for t in self.emitted.by_kind["send_gui_text"]]
        self.assertEqual(self.errors, [], "the slider handler raised")
        self.assertTrue(resent, "moving the slider re-sent no text - the label is dead")
        self.assertIn("Hair Tone:", " | ".join(resent),
                      f"the wrong label was rewritten: {resent}")
        # Only its OWN row. Every row's handler is compiled in the same loop, so a
        # directly-referenced label widget would resolve to the LAST row's and one slider
        # would rename somebody else's control. The reference goes through `data` instead.
        self.assertEqual(len(resent), 1,
                         f"one slider rewrote {len(resent)} labels: {resent}")


    def test_randomize_keeps_the_race_and_changes_the_face(self):
        """Randomize rolls everything BUT the race.

        Pressing it is the only way to find out: its handler jumps back through the
        required-features pass and repaints, and a jump that lands in the wrong place
        looks identical to one that works until somebody presses it.
        """
        page = self._run("terran")
        seen = set()
        for _i in range(12):
            self._press(page, "Randomize")
            self.assertEqual(self.errors, [], "Randomize raised")
            face = self._face_on_screen(page)
            parsed = faces.parse_face(face)
            self.assertIsNotNone(parsed, f"Randomize produced an unreadable face: {face}")
            self.assertEqual(parsed["race"], "terran", "Randomize changed the race")
            seen.add(face)
        self.assertGreater(len(seen), 1, "Randomize produced the same face every time")

    def test_randomize_respects_a_required_feature(self):
        """A caller can mark a feature not-optional here - the console picker marks
        Clothes, because a bridge officer out of uniform is a stranger at the helm. A
        roll must not undo that."""
        page = EditorPage()
        page.start_label = "avatar_editor_show"
        page.start_data = {"av_race": "terran", "av_required": "Clothes"}
        Gui.push(CID, page)
        page.start_story(CID)
        for _ in range(6):
            Gui.present(FakeEvent(CID, "gui_present"))
        for roll in range(8):
            self._press(page, "Randomize")
            with self.subTest(roll=roll):
                self.assertEqual(self.errors, [])
                face = self._face_on_screen(page)
                self.assertTrue(faces.face_in_uniform(face),
                                f"a roll took the uniform off: {face}")


class TestChoiceHelpers(unittest.TestCase):
    """The two helpers the dropdown branch leans on, including what they do when asked
    something they do not recognize - the editor must not die on a stale label."""

    def test_style_shows_the_current_pick(self):
        style = avatar_helper.avatar_editor_choice_style(["Angry", "Open", "Soft"], 1)
        self.assertIn("text: Open", style)
        self.assertIn("list: Angry, Open, Soft", style)

    def test_style_carries_no_braces(self):
        # MAST re-runs an assigned string through f-string formatting, so a '{' handed
        # back from Python is a SyntaxError reported against the CALLER's line.
        for race, feats in faces.FACE_FEATURES.items():
            for f in feats:
                if not f.get("names"):
                    continue
                style = avatar_helper.avatar_editor_choice_style(f["names"], 0)
                with self.subTest(race=race, feature=f["label"]):
                    self.assertNotIn("{", style)
                    self.assertNotIn("}", style)

    def test_index_round_trips_every_stock_name(self):
        for race, feats in faces.FACE_FEATURES.items():
            for f in feats:
                names = f.get("names")
                if not names:
                    continue
                for i, name in enumerate(names):
                    with self.subTest(race=race, feature=f["label"], name=name):
                        self.assertEqual(
                            avatar_helper.avatar_editor_choice_index(names, name), i)

    def test_an_unknown_label_falls_back_rather_than_raising(self):
        self.assertEqual(avatar_helper.avatar_editor_choice_index(["A", "B"], "Z"), 0)
        self.assertEqual(avatar_helper.avatar_editor_choice_index([], "Z"), 0)
        self.assertEqual(avatar_helper.avatar_editor_choice_style([], 3), "text: ;list: ")


if __name__ == "__main__":
    unittest.main()
