"""`document_link_to`: a `[Text](ref://key)` link in a Help/Library topic selects that
topic in the list beside it (documents/document_screen.py).

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest documents.test_document_link
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from sbs_utils.mast.mast_node import MastDataObject
from sbs_utils.procedural.gui.listbox import gui_list_box_header

import document_screen as D


class _List:
    """The one thing the handler touches on the list box: its value."""
    value = None


class TestDocumentLink(unittest.TestCase):
    def setUp(self):
        self.helm = MastDataObject({"key": "helm", "display_text": "Helm"})
        self.eng = MastDataObject({"key": "consoles/engineering", "display_text": "Engineering"})
        root = MastDataObject({"key": "consoles", "display_text": "Console Stations"})
        self.document = [gui_list_box_header("Console Stations", False, 1, True, root),
                         self.helm, self.eng, None]
        self.lst = _List()
        self.go = D.document_link_to(self.lst, self.document)

    def test_a_link_selects_its_topic(self):
        self.go("helm", None)
        self.assertIs(self.lst.value, self.helm)

    def test_a_nested_key_matches_on_its_last_part(self):
        self.go("engineering", None)
        self.assertIs(self.lst.value, self.eng)

    def test_a_header_topic_is_selected_by_its_data(self):
        self.go("consoles", None)
        self.assertEqual(self.lst.value.get("display_text"), "Console Stations")

    def test_an_unknown_key_changes_nothing(self):
        self.lst.value = self.helm
        self.go("no_such_topic", None)
        self.assertIs(self.lst.value, self.helm)

    def test_every_help_link_points_at_a_real_topic(self):
        """A link to a key no topic has is a dead click in the game - catch it here."""
        import re
        here = os.path.dirname(__file__)
        with open(os.path.join(here, "help_docs.amd"), encoding="utf-8") as f:
            text = f.read()
        keys = set(re.findall(r"^#+ \[[^\]]*\]\(([^?)]+)", text, re.M))
        links = re.findall(r"^\[[^\]]+\]\(ref://([^)]+)\)", text, re.M)
        self.assertTrue(links, "the help document has no links to check")
        for key in links:
            self.assertIn(key, keys, f"ref://{key} points at no topic")


if __name__ == "__main__":
    unittest.main()
