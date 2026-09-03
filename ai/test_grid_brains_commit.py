"""Movement and repair must commit to the SAME target.

Damcons getting stuck on competing work orders. `4de500c` made MOVEMENT commit - a team
holds `blackboard:damage_target` while it is still damaged, instead of recomputing
`grid_closest` every tick and oscillating between two rooms.

The REPAIR half never got the same treatment. It recomputed `grid_closest` at the moment
of repair, so a team ordered to one room could walk there, arrive beside a different
damaged node and repair THAT - closing an order it never held and leaving its own room
untouched.

This is a source-level guard because the behaviour lives in a `.mast` label and the mock
never moves grid objects, so no headless run can drive the arrival. What it pins is the
invariant the bug broke: every leaf that PICKS a damaged node consults the commit before
falling back to the closest.
"""
import os
import re
import unittest

BRAINS = os.path.join(os.path.dirname(__file__), "grid_brains.mast")

#: Labels that choose which damaged node a team acts on. Each must honour the commit.
CHOOSERS = ("ai_fix_damage", "ai_lifeform_move_to_damage")


def label_body(name):
    """The lines of one `=== label`, up to the next top-level label."""
    with open(BRAINS, encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"^=== %s\b(.*?)(?=^=== |\Z)" % re.escape(name), src,
                  re.S | re.M)
    if not m:
        return ""
    # CODE ONLY. These labels carry long comments that quote the very names being
    # checked - the first version of this test failed on its own explanation, matching
    # `grid_closest` inside a comment about grid_closest.
    return chr(10).join(ln.split("#", 1)[0] for ln in m.group(1).splitlines())


class TestBothHalvesCommit(unittest.TestCase):
    def test_every_chooser_exists(self):
        for name in CHOOSERS:
            self.assertTrue(label_body(name), "%s is gone or renamed" % name)

    def test_EACH_READS_THE_COMMIT(self):
        for name in CHOOSERS:
            body = label_body(name)
            self.assertIn("blackboard:damage_target", body,
                          "%s picks a node without consulting the commit" % name)

    def test_and_reads_it_BEFORE_falling_back_to_closest(self):
        """Order matters: consulting the commit after choosing the closest is the bug
        with an extra line in it."""
        for name in CHOOSERS:
            body = label_body(name)
            if "grid_closest" not in body:
                continue
            self.assertLess(body.index("blackboard:damage_target"),
                            body.index("grid_closest"),
                            "%s picks the closest before reading the commit" % name)

    def test_the_fallback_is_still_there(self):
        """Holding a commit that no longer exists would strand a team as surely as
        ignoring it - the closest is the answer when the commit is repaired or gone."""
        for name in CHOOSERS:
            self.assertIn("grid_closest", label_body(name),
                          "%s has no fallback" % name)


if __name__ == "__main__":
    unittest.main()
