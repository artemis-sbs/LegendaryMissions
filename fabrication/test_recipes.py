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
        self.assertEqual(R._parse_program("kind=sensor, range=medium"),
                         {"kind": "sensor", "range": "medium"})

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
