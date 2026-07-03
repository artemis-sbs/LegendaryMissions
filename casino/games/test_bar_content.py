"""Tests for bar_content - the bar.amd loader (patrons, rumors, chatter).

The extraction logic is tested against a synthetic parsed tree (hermetic, no
sbs). When sbs_utils is importable (the standard sibling dev layout) the real
bar.amd is also parsed end-to-end so authoring mistakes are caught.
"""
import os, sys, random, unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bar_content as bc

# Make the real bar.amd parseable if sbs_utils sits where the dev harness expects.
_SBS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "sbs_utils"))
if os.path.isdir(_SBS) and _SBS not in sys.path:
    sys.path.insert(0, _SBS)
try:
    from sbs_utils.procedural.quest import document_get_amd_file
    _HAVE_AMD = True
except Exception:
    _HAVE_AMD = False

_BAR_AMD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bar.amd"))


class _FakeFaces:
    """Stand-in for the MAST faces module; returns a tag so we can assert kind."""
    def random_torgoth(self):        return "torgoth"
    def random_terran_male(self):    return "terran_male"
    def random_terran_female(self):  return "terran_female"
    def random_terran(self):         return "terran"


def _synthetic_doc():
    """A minimal parsed-AMD tree in the shape document_get_amd_file produces."""
    return {
        "key": "__root__",
        "children": [
            {"key": "barkeep", "display_text": "Bitters",
             "data": {"call_sign": "Bitters", "face_kind": "torgoth_male", "reliability": 0.55},
             "children": [
                 {"key": "barkeep_r1", "description": "  A tip.\n", "data": {"intel": "Paid off."}},
             ]},
            {"key": "ghost", "display_text": "Ghost",
             "data": {"call_sign": "Ghost", "face_kind": "terran_female", "reliability": 0.9},
             "children": []},
            {"key": "chatter", "data": {"lines": ["one", "two"]}},
        ],
    }


class TestBarContentSynthetic(unittest.TestCase):
    def setUp(self):
        bc.bar_set_doc(_synthetic_doc())

    def test_patrons_exclude_chatter(self):
        keys = [p["key"] for p in bc.bar_patrons()]
        self.assertEqual(keys, ["barkeep", "ghost"])

    def test_patron_fields(self):
        p = bc.bar_patrons()[0]
        self.assertEqual(p["call_sign"], "Bitters")
        self.assertEqual(p["face_kind"], "torgoth_male")
        self.assertEqual(p["reliability"], 0.55)

    def test_base_rep(self):
        self.assertEqual(bc.patron_base_rep("ghost"), 0.9)
        self.assertIsNone(bc.patron_base_rep("nobody"))

    def test_rumor_pool_strips_and_reads_intel(self):
        pool = bc.patron_rumor_pool("barkeep")
        self.assertEqual(pool, [{"tip": "A tip.", "intel": "Paid off."}])
        self.assertTrue(bc.patron_has_rumors("barkeep"))
        self.assertFalse(bc.patron_has_rumors("ghost"))

    def test_pick_rumor(self):
        self.assertIsNone(bc.pick_rumor("ghost"))
        r = bc.pick_rumor("barkeep", rng=random.Random(0))
        self.assertEqual(r["tip"], "A tip.")

    def test_chatter(self):
        self.assertEqual(bc.bar_chatter_lines(), ["one", "two"])

    def test_build_pilots_maps_faces(self):
        pilots = bc.bar_build_pilots(_FakeFaces())
        self.assertEqual(set(pilots), {"barkeep", "ghost"})
        self.assertEqual(pilots["barkeep"]["face"], "torgoth")
        self.assertEqual(pilots["ghost"]["face"], "terran_female")
        self.assertEqual(pilots["barkeep"]["reliability"], 0.55)

    def test_chatter_default_when_no_doc(self):
        bc.bar_set_doc(None)
        self.assertTrue(len(bc.bar_chatter_lines()) >= 1)
        self.assertEqual(bc.bar_patrons(), [])


@unittest.skipUnless(_HAVE_AMD, "sbs_utils not importable - skipping real bar.amd parse")
class TestRealBarAmd(unittest.TestCase):
    def setUp(self):
        with open(_BAR_AMD, "r") as f:
            content = f.read()
        bc.bar_set_doc(document_get_amd_file(None, "Bar", content=content))

    def test_patrons(self):
        keys = [p["key"] for p in bc.bar_patrons()]
        self.assertEqual(keys, ["barkeep", "cogs", "ghost"])

    def test_reliabilities(self):
        self.assertEqual(bc.patron_base_rep("barkeep"), 0.55)
        self.assertEqual(bc.patron_base_rep("cogs"), 0.8)
        self.assertEqual(bc.patron_base_rep("ghost"), 0.9)

    def test_rumor_counts(self):
        self.assertEqual(len(bc.patron_rumor_pool("barkeep")), 2)
        self.assertEqual(len(bc.patron_rumor_pool("cogs")), 2)
        self.assertEqual(len(bc.patron_rumor_pool("ghost")), 3)

    def test_rumor_shape(self):
        for r in bc.patron_rumor_pool("ghost"):
            self.assertTrue(r["tip"])
            self.assertTrue(r["intel"])
            self.assertNotIn("\n", r["tip"])

    def test_chatter(self):
        self.assertEqual(len(bc.bar_chatter_lines()), 5)

    def test_build_pilots(self):
        pilots = bc.bar_build_pilots(_FakeFaces())
        self.assertEqual(pilots["barkeep"]["face"], "torgoth")
        self.assertEqual(pilots["cogs"]["face"], "terran_male")
        self.assertEqual(pilots["ghost"]["face"], "terran_female")


if __name__ == "__main__":
    unittest.main(verbosity=2)
