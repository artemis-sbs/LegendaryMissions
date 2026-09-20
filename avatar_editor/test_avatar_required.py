"""A required feature cannot be switched off in the editor.

`FACE_FEATURES` calls clothing optional, which is right in general - the game is full of
civilians, and the modding tool this was ported from builds them. It is wrong for a bridge
officer: switching the uniform off does not make a variation of that person, it makes a
stranger at the helm. So the CALLER says which features are not optional here
(`av_required: Clothes`), and the editor turns them on and draws no checkbox for them.

The label is "Clothes" because the redrawn sheets dropped the separate Uniform feature.
A stale label would not fail anywhere - it would match nothing and silently protect
nothing, which is exactly what this test exists to catch.

Static: it reads the .mast. The editor is a GUI page and its behavior on screen needs the
real thing, but the two halves of this rule are both single lines that are easy to lose in
an edit - the enable pass and the checkbox guard.

    python -m unittest test_avatar_required
"""
import os
import re
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
EDITOR = os.path.join(HERE, "avatar_editor.mast")
PICKER = os.path.join(os.path.dirname(HERE), "consoles", "common_console_select.mast")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestRequiredFeatures(unittest.TestCase):
    def setUp(self):
        self.editor = _read(EDITOR)

    def test_the_metadata_declares_the_field(self):
        """Metadata values are injected as task variables, so an editor opened WITHOUT one
        must still find the name defined - a bare name is a NameError, and a failing
        expression ends the command rather than skipping it."""
        self.assertRegex(self.editor, r"(?m)^av_required:")

    def test_a_required_feature_is_turned_on(self):
        self.assertIn("av_enables[i] = True", self.editor)

    def test_it_is_re_applied_when_the_race_changes(self):
        """The race picker rebuilds the feature list and its enables from scratch, so the
        pass has to run again before it paints - otherwise changing race quietly takes the
        uniform off."""
        race_handler = self.editor.split("on gui_message(race_pick):")[1].split("\n\n")[0]
        self.assertIn("jump avatar_editor_required", race_handler)

    def test_a_required_feature_draws_no_checkbox(self):
        """The checkbox is the control that could switch it off. The SLIDER stays - which
        uniform you wear is still a choice."""
        self.assertIn('if "optional" in widget and str(label).lower() not in av_required_list:',
                      self.editor)

    def test_the_enable_pass_runs_before_the_paint(self):
        """Inline labels fall through, so `--- avatar_editor_required` has to sit between
        the setup and the paint or the first build shows an un-forced face."""
        required = self.editor.index("--- avatar_editor_required")
        paint = self.editor.index("--- avatar_editor_paint")
        self.assertLess(required, paint)


class TestTheCrewFlowAsksForIt(unittest.TestCase):
    def test_the_console_picker_requires_a_uniform(self):
        picker = _read(PICKER)
        self.assertIn('av_required = "Clothes"', picker)

    def test_coming_back_changes_only_the_face(self):
        """`crew_edit_done` used to clear the picked person too, and with them the name and
        rank the line was showing - so editing an avatar renamed the console. Building a face
        for somebody does not stop them being that person. Only the portrait goes, because a
        photograph and a built face answer the same question."""
        picker = _read(PICKER)
        block = picker.split("===== crew_edit_done =====")[1].split("jump crew_edit_identity")[0]
        self.assertIn("crew_face = AVATAR_FACE", block)
        self.assertIn('crew_portrait = ""', block)
        self.assertNotIn('crew_pick = ""', block)
        self.assertNotIn('crew_name = ""', block)

    def test_it_hands_the_editor_the_face_on_screen(self):
        """`crew_face` holds only what this human built for themselves and is empty for
        nearly everybody - which is exactly who reaches for the editor. The seat's own face
        lives in the preview, so the editor has to be given that."""
        picker = _read(PICKER)
        block = picker.split("===== crew_edit_avatar =====")[1].split("jump avatar_editor_show")[0]
        self.assertIn("av_face = crew_ident.face", block)
        self.assertIn("console_crew_identity(", block)


if __name__ == "__main__":
    unittest.main()
