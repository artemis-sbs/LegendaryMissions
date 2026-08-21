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
        for kind, _label, _fields in dsh.director_overlay_kinds():
            dsh.director_stage_toggle(kind)
        by_kind = {o["kind"]: o for o in dsh.director_stage_overlays()}
        self.assertEqual(sorted(by_kind["lower_third"]), ["kind", "line", "name"])
        self.assertEqual(sorted(by_kind["hero"]), ["kind", "subtitle", "title"])
        self.assertEqual(sorted(by_kind["banner"]), ["kind", "text"])
        self.assertEqual(sorted(by_kind["letterbox"]), ["kind", "line"])
        self.assertEqual(sorted(by_kind["lower_third_portrait"]),
                         ["kind", "line", "name", "ship"])
        self.assertEqual(sorted(by_kind["credits"]), ["entries", "kind", "title"])

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


class BindBenchTests(unittest.TestCase):
    """The bench's THREE subject modes, and the item each one builds."""

    def setUp(self):
        dsh.director_stage_reset()
        self._real_stage = dsh.director_stage_restage
        dsh.director_stage_restage = lambda: None
        self._real_label = dsh.director_subject_label
        dsh.director_subject_label = lambda sid: "Artemis" if sid else "none picked"

    def tearDown(self):
        dsh.director_stage_restage = self._real_stage
        dsh.director_subject_label = self._real_label
        dsh.director_stage_reset()

    def test_it_starts_fixed(self):
        # Every rundown authored before bindings existed means "the object I clicked", so a
        # bench that defaulted to a binding would silently change what Add had always done.
        self.assertEqual(dsh.director_stage_bind(), "")
        self.assertFalse(dsh.director_stage_is_overlay_only())

    def test_fixed_builds_a_camera_item_on_the_clicked_object(self):
        dsh.director_stage_subject(901)
        item = dsh.director_stage_item()
        self.assertEqual(item["kind"], "cam")
        self.assertEqual(item["subject"], 901)

    def test_a_binding_wins_over_the_clicked_object(self):
        # The click is still on the bench - it is what the operator was looking at - but a
        # bound item must not carry it, or every one of them would be a fixed shot in disguise.
        dsh.director_stage_subject(901)
        dsh.director_stage_bind("<<selected_id>>")
        self.assertEqual(dsh.director_stage_item()["subject"], "<<selected_id>>")

    def test_a_binding_needs_no_click_at_all(self):
        dsh.director_stage_bind("<<selected_id>><<weapons_selection>>")
        item = dsh.director_stage_item()
        self.assertIsNotNone(item)
        self.assertEqual(item["kind"], "cam")

    def test_none_builds_an_overlay_only_item(self):
        dsh.director_stage_subject(901)
        dsh.director_stage_bind(None, set_it=True)
        dsh.director_stage_toggle("hero")
        item = dsh.director_stage_item()
        self.assertEqual(item["kind"], "ovl")
        self.assertNotIn("subject", item)

    def test_an_overlay_only_item_with_no_overlays_is_nothing(self):
        # It would show literally nothing on air, which reads as a broken beat rather than an
        # empty one. cv_edit_add reports the summary instead of adding it.
        dsh.director_stage_bind(None, set_it=True)
        self.assertIsNone(dsh.director_stage_item())

    def test_setting_none_needs_the_flag(self):
        # None is a VALUE here, not "no argument given". Without the flag a bare call is a
        # read, which is what every status line wants.
        dsh.director_stage_bind("<<selected_id>>")
        self.assertEqual(dsh.director_stage_bind(None), "<<selected_id>>")
        self.assertIsNone(dsh.director_stage_bind(None, set_it=True))

    def test_the_picker_label_round_trips(self):
        dsh.director_stage_bind_set_label("Selection > weapons target")
        self.assertEqual(dsh.director_stage_bind(),
                         "<<selected_id>><<weapons_selection>>")
        self.assertEqual(dsh.director_stage_bind_label(), "Selection > weapons target")

    def test_the_summary_says_which_mode_it_is_in(self):
        self.assertIn("click something", dsh.director_stage_summary())
        dsh.director_stage_bind("<<selected_id>>")
        self.assertIn("nothing selected yet", dsh.director_stage_summary())
        dsh.director_stage_bind(None, set_it=True)
        self.assertIn("tick at least one overlay", dsh.director_stage_summary())


class KindPickerTests(unittest.TestCase):
    """The overlay vocabulary as data, and the single field editor that reads it."""

    def setUp(self):
        dsh.director_stage_reset()
        self._real_stage = dsh.director_stage_restage
        dsh.director_stage_restage = lambda: None

    def tearDown(self):
        dsh.director_stage_restage = self._real_stage
        dsh.director_stage_reset()

    def test_the_kinds_come_from_one_table(self):
        from director_overlays import DIRECTOR_OVERLAY_KINDS
        self.assertEqual(dsh.director_overlay_kinds(), DIRECTOR_OVERLAY_KINDS)

    def test_the_speaker_and_credits_kinds_are_offered(self):
        # The two the four-row editor could not reach, and the reason it stopped being four
        # hand-written rows.
        kinds = [k for k, _l, _f in dsh.director_overlay_kinds()]
        self.assertIn("lower_third_portrait", kinds)
        self.assertIn("credits", kinds)

    def test_the_picker_labels_survive_a_list_property(self):
        # They reach the wire as one `list: a,b,c;`, so a comma makes two entries and a
        # semicolon ends the property early.
        for label in dsh.director_overlay_kind_labels():
            self.assertNotIn(",", label)
            self.assertNotIn(";", label)

    def test_the_selection_is_the_enabled_set(self):
        dsh.director_stage_set_kinds(["Hero", "Letterbox"])
        self.assertEqual([o["kind"] for o in dsh.director_stage_overlays()],
                         ["hero", "letterbox"])
        # A REPLACE, not a toggle: an untick is a row leaving the selection and has no event.
        dsh.director_stage_set_kinds(["Hero"])
        self.assertEqual([o["kind"] for o in dsh.director_stage_overlays()], ["hero"])

    def test_an_unknown_label_is_dropped_not_stored(self):
        dsh.director_stage_set_kinds(["Hero", "nonsense"])
        self.assertEqual(dsh.director_stage_on_labels(), ["Hero"])

    def test_the_on_labels_round_trip_for_a_repaint(self):
        dsh.director_stage_set_kinds(["Hero", "Letterbox"])
        dsh.director_stage_set_kinds(dsh.director_stage_on_labels())
        self.assertEqual([o["kind"] for o in dsh.director_stage_overlays()],
                         ["hero", "letterbox"])

    def test_editing_is_separate_from_ticking(self):
        # Writing the hero card before ticking it is ordinary. One widget meaning both would
        # jump the boxes on every tick.
        dsh.director_stage_edit_kind("hero")
        dsh.director_stage_set_kinds(["Letterbox"])
        self.assertEqual(dsh.director_stage_edit_kind(), "hero")

    def test_the_editor_always_has_a_kind(self):
        self.assertIn(dsh.director_stage_edit_kind(),
                      [k for k, _l, _f in dsh.director_overlay_kinds()])

    def test_the_fields_follow_the_edited_kind(self):
        dsh.director_stage_edit_kind("banner")
        self.assertEqual(dsh.director_stage_edit_fields(), ["text"])
        self.assertEqual(dsh.director_stage_edit_field_name(1), "")
        dsh.director_stage_edit_kind("lower_third_portrait")
        self.assertEqual(dsh.director_stage_edit_fields(), ["name", "line", "ship"])

    def test_no_kind_has_more_fields_than_the_editor_unrolls(self):
        # The MAST unrolls DIRECTOR_OVERLAY_MAX_FIELDS rows by hand, because an on gui_message
        # in a loop captures the loop variable at its last value. A kind with more fields than
        # that would have a box the operator could never reach, silently.
        from director_overlays import DIRECTOR_OVERLAY_MAX_FIELDS
        self.assertEqual(DIRECTOR_OVERLAY_MAX_FIELDS, 3)
        for _kind, _label, fields in dsh.director_overlay_kinds():
            self.assertLessEqual(len(fields), DIRECTOR_OVERLAY_MAX_FIELDS)

    def test_writing_a_field_positionally_lands_on_the_right_name(self):
        dsh.director_stage_edit_kind("hero")
        dsh.director_stage_edit_set_field(1, "the subtitle")
        self.assertEqual(dsh.director_stage_field("hero", "subtitle"), "the subtitle")

    def test_writing_past_the_end_is_a_no_op(self):
        dsh.director_stage_edit_kind("banner")
        self.assertFalse(dsh.director_stage_edit_set_field(2, "nowhere"))

    def test_two_kinds_in_one_slot_are_reported(self):
        # A slot holds ONE card, and Lower third and Speaker both default to `lower_third`.
        # Nothing on screen would otherwise explain the one that vanished.
        dsh.director_stage_set_kinds(["Lower third", "Speaker"])
        self.assertEqual(dsh.director_overlay_slot_clash(dsh.director_stage_overlays()),
                         ["Speaker"])
        self.assertIn("hidden behind", dsh.director_stage_summary())

    def test_kinds_in_different_slots_do_not_clash(self):
        dsh.director_stage_set_kinds(["Lower third", "Hero", "Top status"])
        self.assertEqual(dsh.director_overlay_slot_clash(dsh.director_stage_overlays()), [])


class RecallTests(unittest.TestCase):
    """Loading an existing item back onto the bench - the inverse of director_stage_item.

    ROUND-TRIP IS THE WHOLE TEST. Anything `director_stage_item` can build,
    `director_stage_load` has to be able to take back apart, or Replace writes a beat that is
    subtly not the one the operator was looking at.
    """

    def setUp(self):
        dsh.director_stage_reset()
        self._real_stage = dsh.director_stage_restage
        dsh.director_stage_restage = lambda: None

    def tearDown(self):
        dsh.director_stage_restage = self._real_stage
        dsh.director_stage_reset()

    def _round_trip(self, item):
        dsh.director_stage_load(item)
        return dsh.director_stage_item()

    def test_a_fixed_camera_item_round_trips(self):
        item = dr.director_item_cam(901, "chase", label="x", hold=7, distance=3500,
                                    overlays=[{"kind": "hero", "title": "T", "subtitle": ""}])
        got = self._round_trip(item)
        self.assertEqual(got["subject"], 901)
        self.assertEqual(got["mode"], "chase")
        self.assertEqual(got["hold"], 7)
        self.assertEqual(got["distance"], 3500)
        self.assertEqual(got["overlays"], [{"kind": "hero", "title": "T", "subtitle": ""}])

    def test_a_bound_camera_item_round_trips(self):
        item = dr.director_item_cam("<<selected_id>><<weapons_selection>>", "orbit")
        self.assertEqual(self._round_trip(item)["subject"],
                         "<<selected_id>><<weapons_selection>>")

    def test_an_overlay_only_item_round_trips(self):
        item = dr.director_item_overlay(overlays=[{"kind": "banner", "text": "hi"}])
        got = self._round_trip(item)
        self.assertEqual(got["kind"], "ovl")
        self.assertEqual(got["overlays"], [{"kind": "banner", "text": "hi"}])

    def test_a_console_item_ticks_its_station(self):
        # The bench is where the Console tab keeps its answer now, which is what makes a
        # console item recallable at all.
        item = dr.director_item_con("<<selected_id>>", "weapons")
        dsh.director_stage_load(item)
        self.assertEqual(dsh.director_stage_consoles(), ["weapons"])
        self.assertEqual(dsh.director_stage_console_items()[0]["console"], "weapons")

    def test_recalling_two_console_items_builds_the_set_up(self):
        # A replace would make each recall clear the last, so three beats could never be
        # rebuilt into the one press that made them.
        dsh.director_stage_load(dr.director_item_con(901, "helm"))
        dsh.director_stage_load(dr.director_item_con(901, "science"))
        self.assertEqual(dsh.director_stage_consoles(), ["helm", "science"])

    def test_templates_come_back_as_TEMPLATES(self):
        # Resolving on the way in would bake the currently selected ship's name into a beat
        # written to follow whatever it is pointed at - and it would not show until air.
        item = dr.director_item_cam(901, "orbit",
                                    overlays=[{"kind": "lower_third", "name": "<<name>>",
                                               "line": "<<class>>"}])
        got = self._round_trip(item)
        self.assertEqual(got["overlays"][0]["name"], "<<name>>")

    def test_the_ticked_set_is_REPLACED_by_a_load(self):
        # The item is the answer to "what does this beat carry", so a kind it does not carry
        # has to come off - otherwise Replace would keep furniture the beat never had.
        dsh.director_stage_set_kinds(["Hero", "Letterbox"])
        dsh.director_stage_load(dr.director_item_cam(
            901, "orbit", overlays=[{"kind": "banner", "text": "x"}]))
        self.assertEqual([o["kind"] for o in dsh.director_stage_overlays()], ["banner"])

    def test_the_editor_opens_on_a_kind_the_beat_carries(self):
        dsh.director_stage_edit_kind("hero")
        dsh.director_stage_load(dr.director_item_cam(
            901, "orbit", overlays=[{"kind": "letterbox", "line": "x"}]))
        self.assertEqual(dsh.director_stage_edit_kind(), "letterbox")

    def test_loading_nothing_is_a_no_op(self):
        self.assertFalse(dsh.director_stage_load(None))


class DistanceTests(unittest.TestCase):
    """An explicit lens distance: 0 is automatic, and the slider seeds from the framing."""

    def setUp(self):
        dsh.director_stage_reset()
        self._real_stage = dsh.director_stage_restage
        dsh.director_stage_restage = lambda: None
        self._real_auto = dsh.director_stage_distance_auto
        dsh.director_stage_distance_auto = lambda: 1440

    def tearDown(self):
        dsh.director_stage_restage = self._real_stage
        dsh.director_stage_distance_auto = self._real_auto
        dsh.director_stage_reset()

    def test_it_starts_automatic(self):
        # The hand-built sliders were deleted because a FIXED distance framed a starbase and a
        # fighter equally badly. An item that never touches this behaves as it always did.
        self.assertEqual(dsh.director_stage_distance(), 0)

    def test_the_display_seeds_from_the_framing(self):
        # A bare 0 is a number whose scale the operator has to discover; 1440 for a fighter is
        # somewhere to nudge from.
        self.assertEqual(dsh.director_stage_distance_display(), 1440)
        self.assertIn("automatic", dsh.director_stage_distance_label())

    def test_committing_one_stops_the_seeding(self):
        dsh.director_stage_distance(3500)
        self.assertEqual(dsh.director_stage_distance_display(), 3500)
        self.assertIn("3500", dsh.director_stage_distance_label())

    def test_auto_hands_it_back(self):
        dsh.director_stage_distance(3500)
        dsh.director_stage_distance_auto_set()
        self.assertEqual(dsh.director_stage_distance(), 0)
        self.assertEqual(dsh.director_stage_distance_display(), 1440)

    def test_zero_and_rubbish_both_mean_automatic(self):
        for value in (0, -50, "wibble", ""):
            dsh.director_stage_distance(value)
            self.assertEqual(dsh.director_stage_distance(), 0, value)

    def test_the_item_carries_it(self):
        dsh.director_stage_subject(901)
        dsh.director_stage_distance(3500)
        self.assertEqual(dsh.director_stage_item()["distance"], 3500)

    def test_an_automatic_item_carries_no_distance(self):
        dsh.director_stage_subject(901)
        self.assertIsNone(dsh.director_stage_item()["distance"])


class ConsoleBenchTests(unittest.TestCase):
    """The Console tab shares the Stage's bench - there is no second answer to which ship."""

    def setUp(self):
        dsh.director_stage_reset()
        self._real_stage = dsh.director_stage_restage
        dsh.director_stage_restage = lambda: None

    def tearDown(self):
        dsh.director_stage_restage = self._real_stage
        dsh.director_stage_reset()

    def test_items_take_the_bench_subject(self):
        dsh.director_stage_subject(901)
        dsh.director_stage_consoles(["helm", "science"])
        items = dsh.director_stage_console_items()
        self.assertEqual([i["ship"] for i in items], [901, 901])

    def test_a_binding_passes_through_AS_AUTHORED(self):
        # Baking whatever is selected right now would turn "the selected ship's helm" into
        # "Artemis's helm" at the moment Add was pressed.
        dsh.director_stage_bind("<<selected_id>>")
        dsh.director_stage_consoles(["helm"])
        self.assertEqual(dsh.director_stage_console_items()[0]["ship"], "<<selected_id>>")

    def test_overlay_only_makes_no_console_items(self):
        dsh.director_stage_bind(None, set_it=True)
        dsh.director_stage_consoles(["helm"])
        self.assertEqual(dsh.director_stage_console_items(), [])
        self.assertIn("overlays only", dsh.director_stage_console_problem())

    def test_no_ticks_is_a_stated_problem(self):
        dsh.director_stage_subject(901)
        self.assertIn("tick at least one", dsh.director_stage_console_problem())

    def test_a_binding_with_nothing_selected_is_NOT_a_problem(self):
        # The items are perfectly good and play the moment something is selected - refusing
        # would stop an operator building a rundown before the mission starts.
        dsh.director_stage_bind("<<selected_id>>")
        dsh.director_stage_consoles(["helm"])
        self.assertEqual(dsh.director_stage_console_problem(), "")


if __name__ == "__main__":
    unittest.main()
