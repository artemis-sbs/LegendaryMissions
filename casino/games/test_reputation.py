"""Tests for bar_reputation (pure helpers - no sbs needed)."""
import os, sys, random, unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bar_reputation as rep


class TestReputation(unittest.TestCase):
    def test_blend(self):
        self.assertAlmostEqual(rep.blended_truth_odds(0.9, None), 0.9)
        # 0.6*0.9 + 0.4*0.1 = 0.54 + 0.04 = 0.58
        self.assertAlmostEqual(rep.blended_truth_odds(0.9, 0.1), 0.58)
        self.assertEqual(rep.blended_truth_odds(2.0, None), 1.0)   # clamped

    def test_trust_label(self):
        self.assertEqual(rep.trust_label(0.95), "trusted")
        self.assertEqual(rep.trust_label(0.65), "reliable")
        self.assertEqual(rep.trust_label(0.45), "so-so")
        self.assertEqual(rep.trust_label(0.05), "unreliable")

    def test_seed_and_adjust(self):
        ghost = {"call_sign": "Ghost"}
        self.assertEqual(rep.patron_seed_base_rep(ghost, "ghost"), 0.9)
        # idempotent - second seed doesn't reset
        ghost["reputation"] = 0.7
        self.assertEqual(rep.patron_seed_base_rep(ghost, "ghost"), 0.7)
        self.assertAlmostEqual(rep.patron_rep_adjust(ghost, -0.3), 0.4)
        self.assertEqual(rep.patron_rep_adjust(ghost, -5), 0.0)     # clamped
        self.assertEqual(rep.patron_trust_label({"reputation": 0.85}), "trusted")

    def test_rumor_roll_weighted(self):
        # a rep-1.0 patron always tells the truth; rep-0.0 never does
        r = random.Random(1)
        always = {"reputation": 1.0}
        never = {"reputation": 0.0}
        self.assertTrue(all(rep.patron_rumor_is_true(always, rng=r) for _ in range(50)))
        self.assertFalse(any(rep.patron_rumor_is_true(never, rng=r) for _ in range(50)))

    def test_ou_stub(self):
        self.assertIsNone(rep.patron_ou_standing({"call_sign": "Ghost"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
