"""The generic science route hands scan text over as a LITERAL.

Scan text registered with `science_define_scan_amd` is an author's prose. The route used
to assign it to a variable and send it through `<scan>`, each of which re-reads a string
as a format string: a `{pilot}` the object's inventory did not fill was a NameError
against this addon, the tab was never stored, and `{SCIENCE_SELECTED.name}` written in a
scan record was run.

The behavior is pinned in sbs_utils (`tests/test_scan_results_literal.py`) and was proved
end to end by a mission with such a record under `mission_runner --test`. This pins the
ROUTE, which is where it regresses: five tabs, each calling `scan_results(...,
literal=True)`, none going back through a variable or a `<scan>` block.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest science_scans.test_science_scan_literal
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TABS = ("scan", "status", "intel", "mat", "bio")


def _route():
    with open(os.path.join(HERE, "science.mast"), encoding="utf-8") as f:
        text = f.read()
    start = text.index("//science if science_has_scan_def(SCIENCE_SELECTED_ID)")
    end = text.index("//enable/science", start)          # the next route in the file
    return text[start:end]


class GenericRouteTests(unittest.TestCase):
    def test_every_tab_hands_its_text_over_as_a_literal(self):
        route = _route()
        for tab in TABS:
            want = 'scan_results(science_scan_tab(SCIENCE_SELECTED_ID, "%s"), literal=True)' % tab
            self.assertEqual(route.count(want), 1, tab)

    def test_no_tab_goes_back_through_a_variable_or_a_scan_block(self):
        route = _route()
        self.assertIsNone(re.search(r"^\s*\w+\s*=\s*science_scan_tab\(", route, re.M))
        self.assertNotIn("<scan>", route)


if __name__ == "__main__":
    unittest.main()
