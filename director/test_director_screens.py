"""Ship rows, and the selection contract that survives a repaint.

The grouping, the program-target marking and the screen fingerprint that used to live here went
with the narrowing to a streaming tool - they are `director_modes.py` now, and tested there.

Two of these guard failures that are invisible in a log and only ever show on screen:

  * `test_duplicate_ship_names_are_deduped` - a listbox decides what is selected by comparing
    ITEMS with `==`, so two rows reading the same string select and DESELECT together, and one
    selection reports two indices.
  * `test_restore_reselects_by_id` - a repaint builds a NEW listbox whose items are new string
    objects. The ids are the only thing that survives; the labels do not.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_screens
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import director_screens as ds


class _Obj:
    def __init__(self, name):
        self.name = name


def _install(roles, objects):
    """Point the sim-facing imports at a fake world.

    They are imported INSIDE each function, so a stub module in sys.modules is what reaches
    them - patching a module attribute would not.
    """
    roles_mod = types.ModuleType("sbs_utils.procedural.roles")
    roles_mod.role = lambda name: set(roles.get(name, ()))

    def any_role(spec):
        out = set()
        for part in spec.split(","):
            out |= set(roles.get(part.strip(), ()))
        return out

    roles_mod.any_role = any_role

    query_mod = types.ModuleType("sbs_utils.procedural.query")
    query_mod.to_object = lambda oid: objects.get(oid)

    saved = {}
    for name, mod in (("sbs_utils.procedural.roles", roles_mod),
                      ("sbs_utils.procedural.query", query_mod)):
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    def restore():
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    return restore


class ShipRowTests(unittest.TestCase):
    def setUp(self):
        self.roles = {"__player__": {903, 901, 902, 904},
                      "director_cam": {902}, "director_screen_cam": {904}}
        self.objects = {901: _Obj("Artemis"), 902: _Obj(""), 903: _Obj("Intrepid"),
                        904: _Obj("")}
        self.restore = _install(self.roles, self.objects)

    def tearDown(self):
        self.restore()

    def test_both_cam_kinds_are_excluded(self):
        # A console's own cam and a program screen's cam are both player-spawned objects that
        # had __player__ stripped. Neither is a ship anyone wants to film.
        _labels, ids = ds.director_ship_rows()
        self.assertEqual(ids, [901, 903])

    def test_rows_are_sorted_and_stable(self):
        # role() returns a SET: without a total order the rows shuffle on every repaint and the
        # operator's eye has nothing to hold on to.
        self.assertEqual(ds.director_ship_rows(), ds.director_ship_rows())

    def test_duplicate_ship_names_are_deduped(self):
        self.objects[903] = _Obj("Artemis")
        labels, _ids = ds.director_ship_rows()
        self.assertEqual(len(labels), len(set(labels)), labels)

    def test_an_unnamed_ship_still_gets_a_row(self):
        self.roles["__player__"].add(905)
        self.objects[905] = _Obj("")
        labels, ids = ds.director_ship_rows()
        self.assertIn(905, ids)
        self.assertTrue(any("unnamed" in l for l in labels), labels)

    def test_a_vanished_object_is_skipped(self):
        self.roles["__player__"].add(999)          # in the role, but no object
        _labels, ids = ds.director_ship_rows()
        self.assertNotIn(999, ids)


class SafeTextTests(unittest.TestCase):
    def test_braces_are_removed(self):
        # A MAST assignment re-runs an assigned STRING through f-string formatting, so a brace
        # arriving from a ship name raises a SyntaxError blamed on the panel.
        self.assertNotIn("{", ds._plain("Art{emis}"))
        self.assertNotIn("}", ds._plain("Art{emis}"))

    def test_backticks_are_removed(self):
        # A backtick is the $text: quoting delimiter and would end the quote early.
        self.assertNotIn("`", ds._plain("Ar`temis"))

    def test_status_line_is_never_empty(self):
        self.assertEqual(ds.director_status_line(""), "Ready.")
        self.assertEqual(ds.director_status_line(None), "Ready.")


class SelectionTests(unittest.TestCase):
    """The repaint contract, without a page: save ids, restore by id."""

    class _LB:
        def __init__(self, items, selected_index=None):
            self.unfiltered_items = list(items)
            self._sel_idx = selected_index or []
            self.selected = []

        def get_selected_index(self):
            return list(self._sel_idx)

        def get_selected(self):
            return list(self.selected)

        def get_selection_hint(self):
            return "hint"

    def test_header_slots_are_skipped(self):
        lb = self._LB(["h", "a", "b"], selected_index=[0, 2])
        self.assertEqual(ds.director_selected_ids(lb, [None, 11, 12]), [12])

    def test_none_listbox_is_empty_not_a_crash(self):
        # The FIRST build has no previous listbox to read.
        self.assertEqual(ds.director_selected_ids(None, None), [])
        self.assertEqual(ds.director_selected_items(None), [])
        self.assertIsNone(ds.director_selection_hint(None))

    def test_first_id_falls_back(self):
        lb = self._LB(["h", "row-a"], selected_index=[])
        self.assertEqual(ds.director_first_id(lb, [None, 11], fallback=7), 7)
        lb2 = self._LB(["h", "row-a"], selected_index=[1])
        self.assertEqual(ds.director_first_id(lb2, [None, 11], fallback=7), 11)

    def test_restore_reselects_by_id(self):
        lb = self._LB(["h", "row-a", "row-b"])
        ds.director_restore_ids(lb, [None, 11, 12], [12])
        self.assertEqual(lb.selected, ["row-b"])

    def test_restore_of_a_vanished_id_selects_nothing(self):
        # A console that disconnected between builds. Ordinary, not an error.
        lb = self._LB(["h", "row-a"])
        ds.director_restore_ids(lb, [None, 11], [999])
        self.assertEqual(lb.selected, [])

    def test_restore_items_matches_by_value(self):
        lb = self._LB(["helm", "science", "comms"])
        ds.director_restore_items(lb, ["comms", "helm"])
        self.assertEqual(lb.selected, ["helm", "comms"])


if __name__ == "__main__":
    unittest.main()
