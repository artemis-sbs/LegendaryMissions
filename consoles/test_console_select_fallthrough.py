"""The console picker's FALLTHROUGH chain, pinned.

A MAST label falls through into the next one. `console_selected` resolves the ship, links
the console and schedules the skybox, then simply runs on into `show_console_selected`,
which is what actually opens the console. Nothing says so at either end - the agreement is
the ADJACENCY of two labels in one file.

So inserting an unrelated label between them silently reroutes every console selection into
whatever was inserted. That is not hypothetical: putting the crew Edit Face labels there
sent every client into the avatar editor, including on the reroute when the server presses
Start, and nothing failed and nothing was logged. It looked like the game start was broken.

Static on purpose - it needs no engine, no page and no client, and this is a property of the
file rather than of a run.
"""
import os
import re
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
PICKER = os.path.join(HERE, "common_console_select.mast")

# A top-level label: 2+ `=` at column 0, then the name.
TOP_LABEL = re.compile(r"^={2,}\s*([A-Za-z_]\w*)")


def _lines():
    with open(PICKER, encoding="utf-8") as handle:
        return handle.read().split("\n")


def _top_labels(lines):
    """(name, index) for every top-level label, in file order. Index is 0-based."""
    return [(m.group(1), i) for i, l in enumerate(lines)
            for m in (TOP_LABEL.match(l),) if m]


def _code(lines, start, stop):
    """The runnable lines in a range - blanks and comments dropped."""
    return [l.strip() for l in lines[start:stop]
            if l.strip() and not l.strip().startswith("#")]


class TestPickerFallthrough(unittest.TestCase):
    def setUp(self):
        self.lines = _lines()
        self.labels = _top_labels(self.lines)
        self.names = [n for n, _ in self.labels]

    def test_console_selected_falls_straight_into_show_console_selected(self):
        self.assertIn("console_selected", self.names)
        self.assertIn("show_console_selected", self.names)
        i = self.names.index("console_selected")
        self.assertEqual(
            self.names[i + 1], "show_console_selected",
            "a label was inserted between console_selected and show_console_selected. "
            "MAST falls through, so every console selection now runs THAT instead of "
            "opening the console - silently. Put the new label at the end of the file.")

    def test_the_crew_edit_labels_cannot_be_fallen_into(self):
        """They are only ever reached by the Edit Face button's jump.

        Whatever precedes each must not run on into it: either it is a `//` route (routes do
        not fall through) or it ends in a jump.
        """
        for name, idx in self.labels:
            if not name.startswith("crew_edit"):
                continue
            before = _code(self.lines, 0, idx)
            self.assertTrue(before, name)
            prev = before[-1]
            self.assertTrue(
                prev.startswith("jump ") or prev.startswith("->") or prev.startswith("//"),
                f"{name} can be fallen into - the line above it is {prev!r}, which runs on. "
                "It must follow a jump, an ->END, or a // route.")

    def test_each_crew_edit_label_leaves_deliberately(self):
        """Neither may fall out into whatever follows it either."""
        starts = [i for _n, i in self.labels]
        for pos, (name, idx) in enumerate(self.labels):
            if not name.startswith("crew_edit"):
                continue
            stop = starts[pos + 1] if pos + 1 < len(starts) else len(self.lines)
            body = _code(self.lines, idx + 1, stop)
            self.assertTrue(body, name)
            last = body[-1]
            self.assertTrue(
                last.startswith("jump ") or last.startswith("->"),
                f"{name} ends on {last!r} and would fall into whatever comes next")


if __name__ == "__main__":
    unittest.main()
