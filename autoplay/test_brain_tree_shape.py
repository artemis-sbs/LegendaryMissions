"""A leaf under the SEQ root must never `yield fail`.

THE FAILURE THIS PINS IS INVISIBLE. `Brain.run_sequence` returns at the first child that
yields fail, so the remaining children never run that pass - no error, no log, nothing in
coverage to notice, because the leaf that failed DID run.

It shipped: `ai_player_science_select` yielded fail when no hostile was in scan range,
which is exactly the situation when a ship is off at a wreck. Science failed, and comms,
weapons and engineering were skipped entirely - so the ship sat at the wreck with no
weapons target, holding fire. The helm looked fine, because the helm is a Select where
`fail` correctly means "not me, try the next".

So the rule is positional, not moral: inside the helm SEL, `fail` is how a leaf declines.
Inside the SEQ root, `fail` is how a leaf silently disables everything after it. A console
leaf with nothing to do has SUCCEEDED at doing nothing.

Run:
    python -m unittest autoplay.test_brain_tree_shape
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "auto_player_brain.mast")


def _strip_comments(body):
    """Drop `#` comment lines.

    Needed because these leaves EXPLAIN the rule in prose, and a check that greps the raw
    text flags the explanation as the violation.
    """
    return chr(10).join(l for l in body.splitlines() if not l.lstrip().startswith("#"))


def _labels(src):
    """label name -> its body text, for every `=== label` in the file."""
    out = {}
    cur, buf = None, []
    for line in src.splitlines():
        m = re.match(r"^=+\s*(\w+)", line)
        if m:
            if cur:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1), []
        elif cur:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf)
    return out


class BrainTreeShapeTests(unittest.TestCase):
    def setUp(self):
        with open(BRAIN, encoding="utf-8") as f:
            self.src = f.read()
        self.labels = _labels(self.src)

    def _seq_children(self):
        """The leaf names listed directly under the SEQ root in the metadata block."""
        block = self.src[self.src.index("brain:"):self.src.index("```", self.src.index("brain:"))]
        # Children of the SEQ root are at one indent level; the nested SEL's own children
        # are deeper and are allowed to fail.
        return re.findall(r"^    - (ai_player_\w+)", block, re.M)

    def test_the_root_is_a_sequence(self):
        self.assertIn("SEQ:", self.src,
                      "a Select root would let the helm starve every other console")

    def test_sequence_children_never_yield_fail(self):
        """The invariant. A fail here silently skips every later console."""
        children = self._seq_children()
        self.assertTrue(children, "found no SEQ children - has the tree shape changed?")
        for name in children:
            body = self.labels.get(name)
            body = _strip_comments(body) if body else body
            self.assertIsNotNone(body, f"{name} is in the tree but has no label")
            self.assertNotIn("yield fail", body,
                             f"{name} is a direct child of the SEQ root and yields fail, "
                             "which aborts every sibling after it - use `yield success` "
                             "for 'nothing to do'")

    def test_the_helm_leaves_are_allowed_to_fail(self):
        """The other half: inside a Select, fail is how a leaf declines its turn.

        Stated so nobody 'fixes' the helm to match the rule above and turns the priority
        list into a chain where the first leaf always wins.
        """
        self.assertIn("yield fail",
                      _strip_comments(self.labels["ai_player_flee_black_hole"]),
                      "a helm leaf must be able to decline")
