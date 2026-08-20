"""Item building: the bridge shot vocabulary, and the overlays an item carries.

There is no framing maths left to test - that was the point of the change. Distances used to
be computed here from a slider; they now come from `viewscreen_framing`, which scales off the
subject's hull radius so a starbase and a fighter both fill the frame. What is left to get
wrong is the vocabulary and the overlay records.

Three of these guard things that fail silently rather than loudly:

  * `test_an_unknown_mode_falls_back` - a mode that is not a mode would otherwise reach the
    player and match no branch, leaving a screen on whatever it had.
  * `test_overlay_fields_match_the_builders` - a field name the overlay builder does not read
    is a text box the operator fills in that does nothing at all.
  * `test_rows_are_unique` - a listbox decides what is selected by comparing ITEMS with `==`,
    so two identical rows select and deselect together.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_shots
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import director_shots as dsh
import director_rundowns as dr


class ModeTests(unittest.TestCase):
    def setUp(self):
        self._real = dsh.director_subject_label
        dsh.director_subject_label = lambda sid: "Artemis" if sid else "none picked"

    def tearDown(self):
        dsh.director_subject_label = self._real

    def test_the_modes_are_the_bridge_vocabulary(self):
        # Dolly / Orbit / Tactical are viewscreen.SHOT_LABELS minus "off" (which is not a shot,
        # it is handing the screen back); chase is the Director's addition.
        self.assertEqual(dsh.director_shot_mode_list(), "Dolly,Orbit,Chase,Tactical")

    def test_a_label_round_trips_to_a_mode(self):
        for mode in dr.DIRECTOR_MODES:
            label = dsh.director_shot_mode_label(mode)
            self.assertEqual(dsh.director_shot_mode_for(label), mode)

    def test_an_unknown_mode_falls_back(self):
        self.assertEqual(dsh.director_shot_mode_for("wibble"), "orbit")
        self.assertEqual(dr.director_item_cam(901, "wibble")["mode"], "orbit")

    def test_an_item_carries_a_mode_and_no_geometry(self):
        item = dsh.director_shot_build(901, "chase")
        self.assertEqual(item["kind"], "cam")
        self.assertEqual(item["mode"], "chase")
        self.assertEqual(item["subject"], 901)
        self.assertNotIn("lens", item)
        self.assertNotIn("move", item)

    def test_no_subject_builds_nothing(self):
        self.assertIsNone(dsh.director_shot_build(None, "orbit"))

    def test_two_modes_on_one_subject_are_two_items(self):
        # The dedupe key is subject+MODE, so an orbit and a chase of the same ship coexist.
        a = dsh.director_shot_build(901, "orbit")
        b = dsh.director_shot_build(901, "chase")
        self.assertNotEqual(dr.director_item_key(a), dr.director_item_key(b))

    def test_the_same_shot_twice_is_one_item(self):
        a = dsh.director_shot_build(901, "orbit")
        b = dsh.director_shot_build(901, "orbit")
        self.assertEqual(dr.director_item_key(a), dr.director_item_key(b))

    def test_console_items_are_one_per_console(self):
        items = dsh.director_shot_console_items(901, ["helm", "science"])
        self.assertEqual([i["kind"] for i in items], ["con", "con"])
        self.assertEqual([i["console"] for i in items], ["helm", "science"])

    def test_console_items_need_a_ship_and_a_console(self):
        self.assertEqual(dsh.director_shot_console_items(None, ["helm"]), [])
        self.assertEqual(dsh.director_shot_console_items(901, []), [])


class BenchTests(unittest.TestCase):
    """The staging bench: what the editor is building, and the fact it restages itself.

    The bench replaced ten `shared cv_ov_*` MAST variables and a twelve-argument builder called
    at ten sites. Every control on the editor restages LIVE - a tick, a preset, a keystroke -
    and a repaint would throw away whatever is half-typed in the next box, so each handler has
    to be one short call that mutates this and pushes.
    """

    def setUp(self):
        dsh.director_stage_reset()

    def tearDown(self):
        dsh.director_stage_reset()

    def test_nothing_ticked_is_no_overlays(self):
        self.assertEqual(dsh.director_stage_overlays(), [])

    def test_several_can_be_on_at_once(self):
        # They occupy different screen slots, so any combination is legal - which is why this
        # is a list and not a single kind.
        dsh.director_stage_toggle("lower_third")
        dsh.director_stage_toggle("banner")
        self.assertEqual([o["kind"] for o in dsh.director_stage_overlays()],
                         ["lower_third", "banner"])

    def test_a_toggle_is_a_toggle(self):
        self.assertTrue(dsh.director_stage_toggle("hero"))
        self.assertTrue(dsh.director_stage_on("hero"))
        self.assertFalse(dsh.director_stage_toggle("hero"))
        self.assertFalse(dsh.director_stage_on("hero"))

    def test_overlay_fields_match_the_builders(self):
        # A field the builder does not read is a text box that silently does nothing. These
        # are the names overlay.py's builders actually look for.
        for kind, _label, _fields in dsh.DIRECTOR_OVERLAY_ROWS:
            dsh.director_stage_toggle(kind)
        by_kind = {o["kind"]: o for o in dsh.director_stage_overlays()}
        self.assertEqual(sorted(by_kind["lower_third"]), ["kind", "line", "name"])
        self.assertEqual(sorted(by_kind["hero"]), ["kind", "subtitle", "title"])
        self.assertEqual(sorted(by_kind["banner"]), ["kind", "text"])
        self.assertEqual(sorted(by_kind["letterbox"]), ["kind", "line"])

    def test_a_row_starts_on_its_first_preset(self):
        # Seeded rather than blank: a director who ticks Lower third and takes the shot should
        # get the ship's name on air, not an empty card that reads as a broken overlay.
        self.assertEqual(dsh.director_stage_field("lower_third", "name"), "<<name>>")

    def test_an_empty_text_still_makes_the_overlay(self):
        # Silently dropping it would look like the checkbox was ignored, and a lower third
        # with no name is a legitimate lower third.
        dsh.director_stage_set_field("lower_third", "name", "")
        dsh.director_stage_set_field("lower_third", "line", "")
        dsh.director_stage_toggle("lower_third")
        self.assertEqual(len(dsh.director_stage_overlays()), 1)

    def test_braces_are_stripped_from_overlay_text(self):
        # A MAST assignment re-runs an assigned STRING through f-string formatting.
        dsh.director_stage_set_field("lower_third", "name", "A{B}")
        self.assertNotIn("{", dsh.director_stage_field("lower_third", "name"))

    def test_the_template_delimiter_survives(self):
        # `<` and `>` are the whole reason the delimiter is what it is - see
        # director_overlays.py. A _plain() that ate them would silently break every preset.
        dsh.director_stage_set_field("banner", "text", "<<name>> - <<class>>")
        self.assertEqual(dsh.director_stage_field("banner", "text"), "<<name>> - <<class>>")

    def test_a_preset_fills_the_row(self):
        dsh.director_stage_apply_preset("lower_third", "Condition")
        self.assertIn("hull", dsh.director_stage_field("lower_third", "line"))

    def test_an_unknown_preset_leaves_the_fields_alone(self):
        before = dsh.director_stage_field("lower_third", "line")
        self.assertFalse(dsh.director_stage_apply_preset("lower_third", "wibble"))
        self.assertEqual(dsh.director_stage_field("lower_third", "line"), before)

    def test_save_round_trips_what_was_typed(self):
        dsh.director_stage_set_field("hero", "title", "<<comms_id>>")
        self.assertEqual(dsh.director_stage_save_preset("hero", "Mine"), "Mine")
        dsh.director_stage_apply_preset("hero", "Ship ID")
        dsh.director_stage_apply_preset("hero", "Mine")
        self.assertEqual(dsh.director_stage_field("hero", "title"), "<<comms_id>>")

    def test_save_needs_a_name(self):
        self.assertIsNone(dsh.director_stage_save_preset("hero", "   "))

    def test_the_item_carries_the_ticked_overlays(self):
        dsh.director_stage_subject(901)
        dsh.director_stage_toggle("lower_third")
        item = dsh.director_stage_item()
        self.assertEqual([o["kind"] for o in item["overlays"]], ["lower_third"])

    def test_no_subject_stages_nothing(self):
        self.assertIsNone(dsh.director_stage_item())

    def test_clearing_the_subject_unstages(self):
        dsh.director_stage_subject(901)
        dsh.director_stage_subject(clear=True)
        self.assertIsNone(dsh.director_stage_item())

    def test_the_mode_follows_the_radio(self):
        dsh.director_stage_subject(901)
        dsh.director_stage_mode_label("Chase")
        self.assertEqual(dsh.director_stage_item()["mode"], "chase")

    def test_the_summary_names_them(self):
        dsh.director_stage_toggle("lower_third")
        dsh.director_stage_toggle("banner")
        self.assertEqual(dsh.director_overlay_summary(dsh.director_stage_overlays()),
                         "Lower third, Top status")


class RowTests(unittest.TestCase):
    def setUp(self):
        dr.director_rundowns_reset()
        self._real = dsh.director_subject_label
        dsh.director_subject_label = lambda sid: "Artemis"

    def tearDown(self):
        dsh.director_subject_label = self._real
        dr.director_rundowns_reset()

    def test_a_row_leads_with_the_mode(self):
        key = dr.director_rundown_new("A")
        dr.director_rundown_add_item(key, dr.director_item_cam(901, "chase", label="Chase - X"))
        labels, _idx = dsh.director_shot_item_rows(key)
        self.assertTrue(labels[0].startswith("chase"), labels)

    def test_a_console_row_says_con(self):
        key = dr.director_rundown_new("A")
        dr.director_rundown_add_item(key, dr.director_item_con(901, "helm"))
        labels, _idx = dsh.director_shot_item_rows(key)
        self.assertTrue(labels[0].startswith("con"), labels)

    def test_a_row_shows_its_overlays(self):
        key = dr.director_rundown_new("A")
        overlays = [{"kind": "lower_third", "name": "", "line": ""}]
        dr.director_rundown_add_item(key, dr.director_item_cam(901, "orbit", label="X",
                                                              overlays=overlays))
        labels, _idx = dsh.director_shot_item_rows(key)
        self.assertIn("Lower third", labels[0])

    def test_rows_are_unique(self):
        key = dr.director_rundown_new("A")
        dr.director_rundown_add_item(key, dr.director_item_cam(901, "orbit", label="Same"))
        dr.director_rundown_add_item(key, dr.director_item_cam(902, "orbit", label="Same"))
        labels, _idx = dsh.director_shot_item_rows(key)
        self.assertEqual(len(labels), len(set(labels)), labels)


if __name__ == "__main__":
    unittest.main()
