"""Fabrication recipe registry + cargo manifest (fabrication/recipes.py).

Focus is the Sensor Beacon path that regressed: a sensor recipe carries no monster/mode, so a
built sensor entry is just {"kind": "sensor"}. cargo_list must name it "Sensor Beacon" (not
"? / ?") and still expose kind/monster/mode without raising; the program/input parsers stay
correct. The matching deliver/eject fixes are covered end-to-end by LM_TestRange/test_beacon.mast.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest fabrication.test_recipes
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as sbs
from tests.reset_helper import reset_mock
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.a2x.spawn import create_enemy
from sbs_utils.procedural.inventory import set_inventory_value

import recipes as R


class ParseProgramTests(unittest.TestCase):
    def test_kv_pairs(self):
        self.assertEqual(R._parse_program("kind=sensor, beacon_range=medium"),
                         {"kind": "sensor", "beacon_range": "medium"})

    def test_bio(self):
        self.assertEqual(R._parse_program("kind=bio"), {"kind": "bio"})

    def test_empty_and_none(self):
        self.assertEqual(R._parse_program(""), {})
        self.assertEqual(R._parse_program(None), {})


class ParseInputsTests(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(R._parse_inputs("bio_sample x1, salvage x5"),
                         {"bio_sample": 1, "salvage": 5})

    def test_bare_key_is_one(self):
        self.assertEqual(R._parse_inputs("salvage"), {"salvage": 1})


class LoadRecipesAmdTests(unittest.TestCase):
    """The real recipes.amd through the real reader -- the gap that let a runtime error
    ship. The parser tests above feed the loader's helpers a STRING, but the reader hands
    the loader an already-parsed value for every declared field type (Inputs is `counted`,
    Program is `kv`), so the loader was parsing twice: Inputs came out
    {"{'bio_sample':": 1} and Program came out {} silently. Nothing was ever affordable,
    every beacon lost its kind, and `Cost: {'bio_sample': x1` crashed the Fabricate tab
    on the unclosed brace. Load the file, not a hand-made string."""

    @classmethod
    def setUpClass(cls):
        from sbs_utils.procedural.quest import document_get_amd_file
        amd = os.path.join(os.path.dirname(__file__), "recipes.amd")
        with open(amd) as f:
            doc = document_get_amd_file(None, "Recipes", content=f.read())
        R.fabrication_load_recipes_amd(doc)

    def test_every_recipe_loaded(self):
        keys = {r["key"] for r in R.fabrication_recipes()}
        self.assertIn("recipe_beacon_bio", keys)
        self.assertIn("recipe_beacon_sensor", keys)
        self.assertIn("recipe_coolant_cell", keys)

    def test_inputs_are_the_authored_counts(self):
        r = R.fabrication_get_recipe("recipe_beacon_bio")
        self.assertEqual(r["inputs"], {"bio_sample": 1, "salvage": 5})
        self.assertEqual(R.fabrication_get_recipe("recipe_beacon_sensor")["inputs"],
                         {"salvage": 8})

    def test_program_survives_the_read(self):
        self.assertEqual(R.fabrication_get_recipe("recipe_beacon_bio")["program"],
                         {"kind": "bio"})
        # `beacon_range`, never `range`: a program key can end up bound as a MAST
        # variable, and `range` is one of MAST's own globals.
        self.assertEqual(R.fabrication_get_recipe("recipe_beacon_sensor")["program"],
                         {"kind": "sensor", "beacon_range": "medium"})
        self.assertEqual(R.fabrication_get_recipe("recipe_beacon_sensor_long")["program"],
                         {"kind": "sensor", "beacon_range": "long"})

    def test_cost_text_carries_no_braces(self):
        # A MAST `x = f()` re-formats a string result as an f-string, so a `{` in this
        # text is a runtime SyntaxError on the panel that shows it -- not just a typo.
        for r in R.fabrication_recipes():
            text = R.recipe_inputs_text(r)
            self.assertNotIn("{", text, f"{r['key']}: {text!r}")
            self.assertNotIn("}", text, f"{r['key']}: {text!r}")
        self.assertEqual(R.recipe_inputs_text(R.fabrication_get_recipe("recipe_beacon_bio")),
                         "bio_sample x1, salvage x5")

    def test_affordable_reads_real_inventory_keys(self):
        reset_mock(sbs)
        pid = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="P"))
        self.assertFalse(R.fabrication_recipe_affordable(pid, "recipe_coolant_cell"))
        set_inventory_value(pid, "salvage", 4)
        self.assertTrue(R.fabrication_recipe_affordable(pid, "recipe_coolant_cell"))
        self.assertTrue(R.fabrication_recipe_consume(pid, "recipe_coolant_cell"))

    def test_properties_block_binds_its_vars(self):
        r = R.fabrication_get_recipe("recipe_beacon_bio")
        self.assertEqual(R.recipe_property_names(r), ["monster", "mode"])
        self.assertEqual(R.recipe_property_defaults(r),
                         {"monster": "shark", "mode": "attract"})


class CargoListNamingTests(unittest.TestCase):
    def setUp(self):
        reset_mock(sbs)

    def _ship(self, built):
        pid = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="P"))
        set_inventory_value(pid, "beacon_built", built)
        return pid

    def _beacon_rows(self, pid):
        return [r for r in R.cargo_list(pid) if r["ckind"] == "beacon"]

    def test_sensor_beacon_named_plainly(self):
        # A sensor beacon carries no monster/mode; naming it must not read them as "? / ?".
        rows = self._beacon_rows(self._ship([{"kind": "sensor"}]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Sensor Beacon")
        self.assertEqual(rows[0]["kind"], "sensor")
        self.assertIsNone(rows[0]["monster"])
        self.assertIsNone(rows[0]["mode"])

    def test_sensor_beacons_named_apart_by_range(self):
        # Both sensor recipes produce kind "sensor"; only beacon_range tells them apart.
        # Before the recipe's own Program fence was carried into the built entry, the Long
        # Range build produced a bare {"kind": "sensor"} -- so 16 salvage bought a beacon
        # indistinguishable from the 8-salvage one, here and everywhere downstream.
        rows = self._beacon_rows(self._ship([
            {"kind": "sensor", "beacon_range": "medium"},
            {"kind": "sensor", "beacon_range": "long"},
        ]))
        self.assertEqual([r["name"] for r in rows],
                         ["Sensor Beacon", "Sensor Beacon (Long Range)"])
        # ...and the two rows carry distinct cargo indices, which is what Deliver/Eject
        # act on now: a (kind, monster, mode) match cannot separate these two at all.
        self.assertEqual([r["cidx"] for r in rows], [0, 1])

    def test_bio_beacon_named_with_program(self):
        rows = self._beacon_rows(self._ship([{"kind": "bio", "monster": "shark", "mode": "attract"}]))
        self.assertEqual(rows[0]["name"], "Beacon: attract / shark")

    def test_mixed_cargo_one_row_each(self):
        rows = self._beacon_rows(self._ship([
            {"kind": "sensor"},
            {"kind": "bio", "monster": "dragon", "mode": "repel"},
        ]))
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["name"] for r in rows},
                         {"Sensor Beacon", "Beacon: repel / dragon"})

    def test_empty_cargo_no_beacon_rows(self):
        self.assertEqual(self._beacon_rows(self._ship([])), [])


if __name__ == "__main__":
    unittest.main()
