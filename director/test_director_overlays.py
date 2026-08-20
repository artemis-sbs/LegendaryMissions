"""Overlay templates: the `<<token>>` resolver, and the presets that fill it in.

Three of these guard decisions that are easy to undo by accident and expensive when undone:

  * `test_the_delimiter_survives_plain` - `<` and `>` are the delimiter precisely because every
    other candidate is eaten on the path to the screen. A `_plain()` that started stripping
    them would silently break every preset, and the failure would be a blank card, not an error.
  * `test_an_unknown_token_stays_literal` - the missing-key-safe contract `amd_fill` settled on.
    A typo shows up on air as `<<shpi>>` and is obvious; raising would blank the whole card.
  * `test_a_preset_name_cannot_break_the_picker` - a preset label reaches the wire as one entry
    of `list: a,b,c;`, so a comma in it becomes two entries and the picker then holds a name
    that matches no preset.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_overlays
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import director_overlays as ov


class _Blob:
    def __init__(self, values=None):
        self._values = dict(values or {})

    def get(self, key, index=0):
        return self._values.get((key, index), self._values.get(key))


class _Obj:
    """Only what a token function actually reaches for."""

    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "")
        self.side_display = kwargs.get("side_display", "")
        self.race = kwargs.get("race", "")
        self.comms_id = kwargs.get("comms_id", "")
        self.ship_data_key = kwargs.get("ship_data_key", "")
        self.data_set = _Blob(kwargs.get("blob"))


def _install(objects, roles=None, ship_names=None, hull_percent=None):
    """Point the sim-facing imports at a fake world.

    They are imported INSIDE each token function, so a stub module in sys.modules is what
    reaches them - patching a module attribute would not.
    """
    query_mod = types.ModuleType("sbs_utils.procedural.query")
    query_mod.to_object = lambda oid: objects.get(oid)

    roles_mod = types.ModuleType("sbs_utils.procedural.roles")
    roles_mod.get_role_list = lambda oid: list((roles or {}).get(oid, ()))

    data_mod = types.ModuleType("sbs_utils.procedural.ship_data")
    data_mod.get_ship_name = lambda key: (ship_names or {}).get(key, "")

    pages_mod = types.ModuleType("sbs_utils.procedural.gui.viewscreen_pages")
    pages_mod.viewscreen_hull_percent = lambda oid: (hull_percent or {}).get(oid)

    saved = {}
    for name, mod in (("sbs_utils.procedural.query", query_mod),
                      ("sbs_utils.procedural.roles", roles_mod),
                      ("sbs_utils.procedural.ship_data", data_mod),
                      ("sbs_utils.procedural.gui.viewscreen_pages", pages_mod)):
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    def restore():
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    return restore


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.objects = {
            901: _Obj(name="Artemis", side_display="TSN", race="terran",
                      comms_id="Artemis (TSN)", ship_data_key="tsn_light_cruiser",
                      blob={("shield_val", 0): 50, ("shield_max_val", 0): 100,
                            ("shield_val", 1): 25, ("shield_max_val", 1): 100}),
            902: _Obj(name="Rock", race="no origin"),
        }
        self.restore = _install(
            self.objects,
            roles={901: ["__player__", "#", "flagship"]},
            ship_names={"tsn_light_cruiser": "Light Cruiser"},
            hull_percent={901: 87.4})

    def tearDown(self):
        self.restore()

    def test_the_headline_case(self):
        # "Use the selected ship's name and the ship_data name" - the request this exists for.
        self.assertEqual(ov.director_overlay_resolve("<<name>>", 901), "Artemis")
        self.assertEqual(ov.director_overlay_resolve("<<class>>", 901), "Light Cruiser")

    def test_a_blob_hull_name_overrides_ship_data(self):
        # That is the override a science scan shows; a mission that set it meant it.
        self.objects[901].data_set = _Blob({("hull_name", 0): "Q-Ship"})
        self.assertEqual(ov.director_overlay_resolve("<<class>>", 901), "Q-Ship")

    def test_side_race_and_comms_id(self):
        self.assertEqual(ov.director_overlay_resolve("<<side>>", 901), "TSN")
        self.assertEqual(ov.director_overlay_resolve("<<race>>", 901), "terran")
        self.assertEqual(ov.director_overlay_resolve("<<comms_id>>", 901), "Artemis (TSN)")

    def test_role_skips_the_engines_own_bookkeeping(self):
        # Showing `__player__` on air would be worse than showing nothing.
        self.assertEqual(ov.director_overlay_resolve("<<role>>", 901), "flagship")

    def test_hull_and_shields(self):
        self.assertEqual(ov.director_overlay_resolve("<<hull>>", 901), "87%")
        self.assertEqual(ov.director_overlay_resolve("<<shields>>", 901), "50% / 25%")

    def test_several_tokens_in_one_line(self):
        self.assertEqual(ov.director_overlay_resolve("<<name>> - <<class>>", 901),
                         "Artemis - Light Cruiser")

    def test_a_fallback_covers_what_cannot_resolve(self):
        # A rock has no hull class. Without the fallback the lower third's second line is blank
        # and reads as a broken overlay.
        self.assertEqual(ov.director_overlay_resolve("<<class|contact>>", 902), "contact")

    def test_no_origin_counts_as_unresolved(self):
        # `race` falls back to the literal "no origin", which reads as a bug on air.
        self.assertEqual(ov.director_overlay_resolve("<<race|unknown>>", 902), "unknown")

    def test_no_fallback_is_an_empty_string(self):
        self.assertEqual(ov.director_overlay_resolve("<<class>>", 902), "")

    def test_no_subject_takes_the_fallback(self):
        self.assertEqual(ov.director_overlay_resolve("<<name|nobody>>", None), "nobody")

    def test_a_vanished_subject_takes_the_fallback(self):
        self.assertEqual(ov.director_overlay_resolve("<<name|gone>>", 999), "gone")

    def test_an_unknown_token_stays_literal(self):
        # Missing-key-safe, like amd_fill: a typo is visible on air rather than blanking the
        # card, and it names itself.
        self.assertEqual(ov.director_overlay_resolve("hi <<shpi>>", 901), "hi <<shpi>>")

    def test_plain_text_passes_through(self):
        self.assertEqual(ov.director_overlay_resolve("RED ALERT", 901), "RED ALERT")

    def test_a_stray_single_angle_is_not_a_token(self):
        # The delimiter is DOUBLED so "<5%" can never match.
        self.assertEqual(ov.director_overlay_resolve("hull <5%", 901), "hull <5%")

    def test_the_delimiter_survives_plain(self):
        # If `_plain` ever started stripping `<` and `>`, every preset would break silently.
        self.assertEqual(ov._plain("<<name>>"), "<<name>>")

    def test_braces_are_still_stripped(self):
        # Both before and after substitution - a ship literally named `Foo{bar}` would
        # otherwise reach gui_text and be f-string evaluated there.
        self.assertNotIn("{", ov.director_overlay_resolve("a {b} c", 901))
        self.objects[901].name = "Foo{bar}"
        self.assertNotIn("{", ov.director_overlay_resolve("<<name>>", 901))

    def test_empty_text_is_empty(self):
        self.assertEqual(ov.director_overlay_resolve("", 901), "")
        self.assertEqual(ov.director_overlay_resolve(None, 901), "")

    def test_fields_resolve_and_kind_passes_through(self):
        out = ov.director_overlay_resolve_fields(
            {"kind": "lower_third", "name": "<<name>>", "line": "<<class>>"}, 901)
        self.assertEqual(out, {"kind": "lower_third", "name": "Artemis",
                               "line": "Light Cruiser"})

    def test_every_advertised_token_resolves(self):
        # The help line names them, so each one has to actually be wired up.
        for token in ov.director_overlay_tokens():
            text = "<<" + token + ">>"
            self.assertNotEqual(ov.director_overlay_resolve(text, 901), text, token)


class PresetTests(unittest.TestCase):
    def setUp(self):
        ov.director_overlay_presets_reset()

    def tearDown(self):
        ov.director_overlay_presets_reset()

    def test_every_kind_ships_with_presets(self):
        for kind in ov.DIRECTOR_OVERLAY_FIELDS:
            labels, keys = ov.director_overlay_preset_rows(kind)
            self.assertTrue(labels, kind)
            self.assertEqual(len(labels), len(keys), kind)

    def test_a_builtin_fills_the_right_fields(self):
        fields = ov.director_overlay_preset_fields("lower_third", "Ship ID")
        self.assertEqual(sorted(fields), ["line", "name"])

    def test_a_preset_only_holds_its_own_kinds_fields(self):
        # A hero preset filling `name`/`line` would put text in boxes that are not on screen.
        for kind, fields in ov.DIRECTOR_OVERLAY_FIELDS.items():
            for _key, label, values in ov._BUILTIN.get(kind, ()):
                self.assertEqual(sorted(values), sorted(fields), (kind, label))

    def test_saving_adds_to_the_picker(self):
        ov.director_overlay_preset_save("hero", "Mine", {"title": "<<name>>", "subtitle": "x"})
        labels, _keys = ov.director_overlay_preset_rows("hero")
        self.assertIn("Mine", labels)
        self.assertEqual(ov.director_overlay_preset_fields("hero", "Mine")["title"], "<<name>>")

    def test_saving_over_a_name_replaces_it(self):
        # An operator tweaking a preset means to change it, not to accumulate "Mine (2)".
        ov.director_overlay_preset_save("hero", "Mine", {"title": "a", "subtitle": ""})
        ov.director_overlay_preset_save("hero", "Mine", {"title": "b", "subtitle": ""})
        labels, _keys = ov.director_overlay_preset_rows("hero")
        self.assertEqual(labels.count("Mine"), 1)
        self.assertEqual(ov.director_overlay_preset_fields("hero", "Mine")["title"], "b")

    def test_a_save_only_keeps_the_kinds_own_fields(self):
        ov.director_overlay_preset_save("banner", "B", {"text": "t", "subtitle": "junk"})
        self.assertEqual(sorted(ov.director_overlay_preset_fields("banner", "B")), ["text"])

    def test_a_preset_name_cannot_break_the_picker(self):
        # It reaches the wire as one entry of `list: a,b,c;`.
        label = ov.director_overlay_preset_save("banner", "Red, White; Blue", {"text": "t"})
        self.assertEqual(label, "Red White Blue")
        # And it is still findable under the name it was actually stored as.
        self.assertEqual(ov.director_overlay_preset_fields("banner", label)["text"], "t")
        self.assertIn(label, ov.director_overlay_preset_list("banner").split(","))

    def test_a_nameless_save_is_refused(self):
        self.assertIsNone(ov.director_overlay_preset_save("banner", "   ", {"text": "t"}))

    def test_an_unknown_kind_is_refused(self):
        self.assertIsNone(ov.director_overlay_preset_save("wibble", "X", {}))

    def test_labels_are_unique(self):
        # A dropdown and a listbox both resolve a selection by comparing DISPLAY TEXT, so two
        # identical entries are indistinguishable.
        ov.director_overlay_preset_save("lower_third", "Ship ID", {"name": "a", "line": "b"})
        labels, _keys = ov.director_overlay_preset_rows("lower_third")
        self.assertEqual(len(labels), len(set(labels)), labels)

    def test_the_list_property_is_comma_separated(self):
        labels, _keys = ov.director_overlay_preset_rows("hero")
        self.assertEqual(ov.director_overlay_preset_list("hero"), ",".join(labels))

    def test_delete_removes_a_saved_one(self):
        ov.director_overlay_preset_save("hero", "Mine", {"title": "a", "subtitle": ""})
        self.assertTrue(ov.director_overlay_preset_delete("hero", "Mine"))
        self.assertNotIn("Mine", ov.director_overlay_preset_rows("hero")[0])

    def test_reset_forgets_saved_presets_but_not_builtins(self):
        # PER MISSION: cosmos_dev reuses one interpreter across run_next_mission, so an
        # uncleared module dict is the classic "works on run 1, stale on run 2".
        ov.director_overlay_preset_save("hero", "Mine", {"title": "a", "subtitle": ""})
        ov.director_overlay_presets_reset()
        labels, _keys = ov.director_overlay_preset_rows("hero")
        self.assertNotIn("Mine", labels)
        self.assertIn("Ship ID", labels)

    def test_an_unknown_label_is_no_fields_not_a_crash(self):
        self.assertEqual(ov.director_overlay_preset_fields("hero", "wibble"), {})

    def test_the_help_line_is_ascii(self):
        # Engine-rendered strings are ASCII only.
        ov.director_overlay_token_help().encode("ascii")


if __name__ == "__main__":
    unittest.main()
