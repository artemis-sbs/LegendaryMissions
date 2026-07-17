"""Florbin suspect-trail generator invariants (maps/mission_helper_functions.py::fb_generate_case).

fb_generate_case replaced ~400 lines of brute-force per-scenario/per-ship trail building in
florbin_case.mast. These tests pin the mystery invariants the mission depends on, over many seeds:

  1. Exactly ONE tracked suspect is the kidnapper.
  2. The kidnapper carries the ambassador container (clue0 == kclue) in one cargo3 hold-goods slot
     (index 6/8/10/12); no OTHER suspect's holds contain clue0 -> the bio hold-scan matches on
     exactly that ship.
  3. clue0 is a real container name from clue_list[0:20] (never empty).
  4. The kidnapper's interview report carries the paired narrative clue (clue1); the other two
     tracked reports carry clue2 / clue3, never clue1.
  5. Each tracked suspect gets two distinct DS-2..5 stops tagged clue{N}A / clue{N}B.
  6. Each tracked suspect has a non-empty interview report.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest maps.test_florbin_case
"""
import os
import sys
import json
import random
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
# Register the mock as `sbs` so importing mission_helper_functions (which does `import sbs`) resolves.
from cosmos_dev.mock import sbs as _mock_sbs  # noqa: F401

import mission_helper_functions as MH

# Report templates carrying the slots the generator fills. Kept local so the test does not depend on
# AMD parsing; the {clue}/{newname} slots are what invariant 4 / the rename twist assert against.
TEMPLATES = {
    "report_stop": "STOP {ship}: unloaded {unloaded}; loaded {loaded}. manifest:^^{holds}",
    "report_stop_clue": "STOP {ship}: unloaded {unloaded}; loaded {loaded}. manifest:^^{holds}^^NOTE: {clue}",
    "report_rename": "STOP {ship}: unloaded {unloaded}; loaded {loaded}. manifest:^^{holds}^^RENAME: {newname}",
}

_SHIPNAMES = os.path.join(os.path.dirname(__file__), "..", "prefabs", "shipnames.json")
SHIP_DATA = json.load(open(_SHIPNAMES, encoding="utf-8"))
CONTAINERS = set(c["container"] for c in SHIP_DATA["clue_list"])


def _pick_clues(rng):
    """Mirror the MAST clue pick: clue0/clue1 as a PAIR from clue_list[0:20], clue2/clue3 after."""
    pool = list(SHIP_DATA["clue_list"])
    kc = pool.pop(rng.randint(0, 19))
    clue0 = kc["container"]
    clue1 = kc["clue"]
    clue2 = pool.pop(rng.randint(0, len(pool) - 1))["clue"]
    clue3 = pool.pop(rng.randint(0, len(pool) - 1))["clue"]
    return clue0, [clue1, clue2, clue3]


def _generate(seed, n_tracked=3, n_decoy=2):
    rng = random.Random(seed)
    clue0, clues = _pick_clues(rng)
    pools = MH.fb_pools(SHIP_DATA)  # fresh COPIES every call
    case = MH.fb_generate_case(pools, clue0, clues, TEMPLATES, rng,
                               n_tracked=n_tracked, n_decoy=n_decoy)
    return case, clue0, clues


HOLD_IDX = MH.FB_HOLD_GOODS_IDX  # [6, 8, 10, 12]


def _kidnapper(case):
    kids = [s for s in case["suspects"] if s["kidnapper"]]
    return kids


def _holds_contain(cargo, value):
    return [gi for gi in HOLD_IDX if gi < len(cargo) and cargo[gi] == value]


class FlorbinCaseInvariants(unittest.TestCase):
    SEEDS = list(range(20))

    def test_inv1_exactly_one_kidnapper(self):
        for seed in self.SEEDS:
            case, _, _ = _generate(seed)
            kids = _kidnapper(case)
            self.assertEqual(len(kids), 1, f"seed {seed}: expected 1 kidnapper, got {len(kids)}")
            self.assertTrue(kids[0]["tracked"], f"seed {seed}: kidnapper must be a tracked suspect")

    def test_inv2_kidnapper_carries_container_uniquely(self):
        for seed in self.SEEDS:
            case, clue0, _ = _generate(seed)
            kid = _kidnapper(case)[0]
            self.assertEqual(kid["kclue"], clue0)
            hit = _holds_contain(kid["cargo3"], clue0)
            self.assertEqual(len(hit), 1,
                             f"seed {seed}: kidnapper cargo3 must hold clue0 in exactly one hold slot, got {hit}")
            self.assertIn(hit[0], HOLD_IDX)
            # No OTHER suspect's holds contain clue0.
            for s in case["suspects"]:
                if s is kid:
                    continue
                self.assertEqual(_holds_contain(s["cargo3"], clue0), [],
                                 f"seed {seed}: decoy {s['orig_name']} must NOT hold clue0")
                self.assertEqual(s["kclue"], clue0)  # every suspect knows the search target

    def test_inv3_container_is_real(self):
        for seed in self.SEEDS:
            _, clue0, _ = _generate(seed)
            self.assertTrue(clue0)
            self.assertNotEqual(clue0, "Empty")
            self.assertIn(clue0, CONTAINERS, f"seed {seed}: clue0 must be a real clue_list container")
            # Disjoint from trade goods -> a decoy hold can never accidentally equal clue0.
            self.assertNotIn(clue0, set(SHIP_DATA["tradegoods"]))

    def test_inv4_reports_carry_the_right_clue(self):
        for seed in self.SEEDS:
            case, _, clues = _generate(seed)
            clue1, clue2, clue3 = clues
            tracked = [s for s in case["suspects"] if s["tracked"]]
            kid = _kidnapper(case)[0]
            self.assertIn(clue1, kid["report"], f"seed {seed}: kidnapper report must carry clue1")
            decoy_reports = [s["report"] for s in tracked if not s["kidnapper"]]
            for rep in decoy_reports:
                self.assertNotIn(clue1, rep, f"seed {seed}: a decoy report must NOT carry clue1")
            # clue2 and clue3 are each used once across the two non-kidnapper tracked reports.
            joined = "\n".join(decoy_reports)
            self.assertIn(clue2, joined, f"seed {seed}: clue2 must appear in a decoy report")
            self.assertIn(clue3, joined, f"seed {seed}: clue3 must appear in a decoy report (no dead clue3)")

    def test_inv5_tracked_stops_tagged(self):
        for seed in self.SEEDS:
            case, _, _ = _generate(seed)
            for i, s in enumerate(s for s in case["suspects"] if s["tracked"]):
                self.assertEqual(s["clueA"], f"clue{i+1}A", f"seed {seed}: bad clueA for tracked {i}")
                self.assertEqual(s["clueB"], f"clue{i+1}B", f"seed {seed}: bad clueB for tracked {i}")
                s1, s2 = s["stops"][0], s["stops"][1]
                self.assertNotEqual(s1, s2, f"seed {seed}: tracked {i} two stops must differ")
                self.assertIn(s1, [2, 3, 4, 5])
                self.assertIn(s2, [2, 3, 4, 5])

    def test_inv6_tracked_reports_nonempty(self):
        for seed in self.SEEDS:
            case, _, _ = _generate(seed)
            for s in case["suspects"]:
                if s["tracked"]:
                    self.assertTrue(s["report"] and s["report"].strip(),
                                    f"seed {seed}: tracked {s['orig_name']} needs a report")
                else:
                    self.assertIsNone(s["report"])

    def test_cargo_snapshots_shape(self):
        # cargo1/2/3 keep holds 1-4 present (indices 5..12) so fb_holds + the hold-scan never crash.
        for seed in self.SEEDS:
            case, _, _ = _generate(seed)
            for s in case["suspects"]:
                for key in ("cargo1", "cargo2", "cargo3"):
                    cargo = s[key]
                    self.assertGreaterEqual(len(cargo), 13, f"seed {seed}: {key} lost holds")
                    self.assertEqual(cargo[0], s["orig_name"] if key != "cargo3" else s["cur_name"])
                # fb_holds renders 4 hold lines.
                self.assertEqual(MH.fb_holds(s["cargo3"]).count("Hold "), 4)

    def test_determinism(self):
        a, _, _ = _generate(7)
        b, _, _ = _generate(7)
        self.assertEqual([s["orig_name"] for s in a["suspects"]],
                         [s["orig_name"] for s in b["suspects"]])
        self.assertEqual(a["kidnapper_index"], b["kidnapper_index"])

    def test_kidnapper_varies_across_seeds(self):
        # The kidnapper is not pinned to ship 1 (varied among the tracked ships).
        idxs = set(_generate(seed)[0]["kidnapper_index"] for seed in range(40))
        self.assertGreater(len(idxs), 1, "kidnapper index should vary across seeds")

    def test_fb_fill_missing_slot_is_blank(self):
        self.assertEqual(MH.fb_fill("a {x} b {y}", {"x": "1"}), "a 1 b ")
        self.assertEqual(MH.fb_fill("", {"x": "1"}), "")


if __name__ == "__main__":
    unittest.main()
