"""Tests for the BioMech addon lifecycle - the key property is EVOLVE BY RESPAWN:
evolving replaces a hull with a fresh next-stage hull (so its stats come from the new
stage's shipData), rather than swapping art_id on the old hull.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest biomech.test_biomech
"""
import os, sys, unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

from cosmos_dev.mock import sbs as sbs
from tests.reset_helper import reset_mock
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.roles import role

# biomech.py is a sibling submodule of this package (the folder name matches the module
# name, so a bare `import biomech` would resolve to the package, not the module).
from biomech import biomech as BM


class BioMechTests(unittest.TestCase):
    def setUp(self):
        reset_mock(sbs)
        # brain_add resolves string labels via the live MAST task, which the mock has
        # none of; the lifecycle under test is spawn/evolve/count, not the brain tree.
        self._real_brain_add = BM.brain_add
        BM.brain_add = lambda *a, **k: None

    def tearDown(self):
        BM.brain_add = self._real_brain_add

    def test_spawn_sets_role_remembers_roles_and_starts_passive(self):
        bid = BM.biomech_spawn(0, 0, 0, "biomech_a", "biomech, raider")
        o = to_object(bid)
        self.assertTrue(o.has_role("biomech"))
        self.assertTrue(o.has_role("raider"))
        self.assertEqual(BM.get_inventory_value(bid, "biomech:roles", None), "biomech, raider")
        self.assertEqual(BM.get_inventory_value(bid, "biomech:enraged", None), 0)  # passive
        self.assertEqual(BM.biomech_count(), 1)
        self.assertEqual(BM.biomech_stage(o), 0)
        self.assertFalse(BM.biomech_has_stage4())

    def test_enrage_is_bounded_to_radius(self):
        # A hull that gets hit, a near hull inside the aggro radius, a far hull outside.
        hit = BM.biomech_spawn(0, 0, 0, "biomech_a")
        near = BM.biomech_spawn(3000, 0, 0, "biomech_a")   # within 5000
        far = BM.biomech_spawn(50000, 0, 0, "biomech_a")   # well outside
        attacker = 777
        woke = BM.biomech_enrage(hit, attacker, radius=5000)
        self.assertEqual(woke, 2)                          # hit + near only
        self.assertEqual(BM.get_inventory_value(hit, "biomech:enraged", 0), 1)
        self.assertEqual(BM.get_inventory_value(near, "biomech:enraged", 0), 1)
        self.assertEqual(BM.get_inventory_value(far, "biomech:enraged", 0), 0)   # bounded out
        self.assertEqual(BM.get_inventory_value(near, "biomech:target", 0), attacker)

    def test_enrage_flips_only_woken_hulls_to_hostile_side(self):
        # Record side switches; pretend both sides are registered so the guard passes.
        switches = []
        self._real_set_side = BM.side_set_object_side
        self._real_keys = BM.side_keys_set
        BM.side_set_object_side = lambda oid, key: switches.append((oid, key))
        BM.side_keys_set = lambda: {"raider", "biomech"}  # pretend both are registered
        try:
            hit = BM.biomech_spawn(0, 0, 0, "biomech_a")
            near = BM.biomech_spawn(2000, 0, 0, "biomech_a")
            far = BM.biomech_spawn(60000, 0, 0, "biomech_a")
            BM.biomech_enrage(hit, 9, radius=5000)
            switched_ids = {oid for oid, key in switches}
            self.assertIn(hit, switched_ids)
            self.assertIn(near, switched_ids)
            self.assertNotIn(far, switched_ids)               # bounded: far hull untouched
            self.assertTrue(all(key == BM.BIOMECH_ENRAGED_SIDE for _, key in switches))
            # calming switches back to the passive/neutral side
            switches.clear()
            BM.biomech_calm(hit, radius=5000)
            self.assertTrue(switches and all(key == BM.BIOMECH_PASSIVE_SIDE for _, key in switches))
        finally:
            BM.side_set_object_side = self._real_set_side
            BM.side_keys_set = self._real_keys

    def test_enrage_side_switch_is_guarded_when_side_missing(self):
        # Default mock has no registered 'raider' side -> to_side_id None -> no crash.
        bid = BM.biomech_spawn(0, 0, 0, "biomech_a")
        self.assertEqual(BM.biomech_enrage(bid, 1, radius=1000), 1)
        self.assertEqual(BM.get_inventory_value(bid, "biomech:enraged", 0), 1)

    def test_calm_clears_enraged(self):
        a = BM.biomech_spawn(0, 0, 0, "biomech_a")
        b = BM.biomech_spawn(1000, 0, 0, "biomech_a")
        BM.biomech_enrage(a, 5, radius=100000)             # rouse the whole hive
        self.assertEqual(BM.get_inventory_value(b, "biomech:enraged", 0), 1)
        calmed = BM.biomech_calm()
        self.assertEqual(calmed, 2)
        self.assertEqual(BM.get_inventory_value(a, "biomech:enraged", 1), 0)
        self.assertEqual(BM.get_inventory_value(b, "biomech:enraged", 1), 0)

    def test_evolve_carries_enraged_forward(self):
        bid = BM.biomech_spawn(0, 0, 0, "biomech_a")
        BM.biomech_enrage(bid, 42, radius=1000)
        new_id = BM.biomech_evolve()
        self.assertEqual(BM.get_inventory_value(new_id, "biomech:enraged", 0), 1)
        self.assertEqual(BM.get_inventory_value(new_id, "biomech:target", 0), 42)

    def test_evolve_respawns_next_stage_at_same_pos(self):
        # ONE growable hull, so evolve is deterministic.
        old = BM.biomech_spawn(1234, 0, -567, "biomech_a", "biomech, raider")
        oldpos = to_object(old).pos
        new_id = BM.biomech_evolve()

        self.assertNotEqual(new_id, old)                 # a genuinely new hull
        self.assertNotIn(old, role("biomech"))           # old dropped from the role set
        self.assertEqual(BM.biomech_count(), 1)          # 1:1 replacement, not a duplicate
        o = to_object(new_id)
        self.assertEqual(o.art_id, "biomech_b")          # promoted one stage
        self.assertAlmostEqual(o.pos.x, oldpos.x, places=3)
        self.assertAlmostEqual(o.pos.z, oldpos.z, places=3)
        self.assertTrue(o.has_role("biomech") and o.has_role("raider"))  # roles carried

    def test_evolve_climbs_to_stage4_then_stops(self):
        BM.biomech_spawn(0, 0, 0, "biomech_a")
        # a single hull, evolved repeatedly, should reach Stage 4 and then no-op
        for _ in range(3):
            self.assertNotEqual(BM.biomech_evolve(), 0)
        self.assertTrue(BM.biomech_has_stage4())
        self.assertEqual(to_object(next(iter(role("biomech")))).art_id, "biomech_d")
        self.assertEqual(BM.biomech_evolve(), 0)         # nothing left to grow
        self.assertEqual(BM.biomech_count(), 1)          # still just the one hull

    def test_count_tracks_multiple(self):
        for i in range(5):
            BM.biomech_spawn(i * 1000, 0, 0, "biomech_a")
        self.assertEqual(BM.biomech_count(), 5)


if __name__ == "__main__":
    unittest.main()
