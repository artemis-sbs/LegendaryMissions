"""The queue list: its two actions, and the gaps that keep them apart.

Move up and Cancel sit side by side and do opposite things - one is a small correction,
the other destroys sensor time the ship has already spent. So the spacing is not styling,
it is the safety property, and it is asserted here rather than eyeballed.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_science_queue_list
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

CONSOLES = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CONSOLES)

from sbs_utils.helpers import Context, FakeEvent, FrameContext     # noqa: E402
from sbs_utils.procedural.query import to_object                   # noqa: E402
from sbs_utils.procedural.sides import side_ensure                 # noqa: E402
from sbs_utils.procedural.spawn import npc_spawn, player_spawn     # noqa: E402
from sbs_utils.spaceobject import SpaceObject                      # noqa: E402

import science_queue as sq                                         # noqa: E402
import science_queue_list as ql                                    # noqa: E402

CID = 1


class QueueListTest(unittest.TestCase):
    def setUp(self):
        SpaceObject.clear()
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        side_ensure("tsn")
        side_ensure("raider")
        sq.lm_sci_queue_clear()
        self.ship = to_object(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        self.a = to_object(npc_spawn(1000, 0, 0, "K19", "raider",
                                     "tsn_light_cruiser", "behav_npcship"))
        self.b = to_object(npc_spawn(2000, 0, 0, "L01", "raider",
                                     "tsn_light_cruiser", "behav_npcship"))
        mock_sbs.assign_client_to_ship(CID, self.ship.id)
        sq.lm_sci_queue_add(self.ship, self.a, "scan")
        sq.lm_sci_queue_add(self.ship, self.b, "scan")
        sq.lm_sci_queue_add(self.ship, self.b, "status")

    def tearDown(self):
        sq.lm_sci_queue_clear()
        FrameContext.context = None
        SpaceObject.clear()

    # --- touch safety -------------------------------------------------------

    def test_the_two_buttons_are_separated_by_a_dead_column(self):
        """Padding still belongs to a button and still takes the press. Only empty space
        belonging to neither is a real gap."""
        self.assertGreater(ql.LM_SCI_QL_GAP_EM, 0.5,
                           "the gap between Move up and Cancel is too small to protect "
                           "against a fat finger")

    def test_a_row_is_a_real_touch_target(self):
        self.assertGreaterEqual(ql.LM_SCI_QL_ROW_EM, 2.2,
                                "a queue row must be at least as tall as a tab row")

    def test_rows_are_separated_so_a_press_cannot_hit_the_neighbour(self):
        self.assertGreater(ql.LM_SCI_QL_ITEM_GAP_EM, 0.0)

    def test_the_box_shows_what_it_says_it_shows(self):
        """The height, the gap and the row count are one calculation, so they cannot
        drift apart."""
        height = ql.lm_sci_ql_box_height()
        self.assertTrue(height.endswith("em"), height)
        expected = (ql.LM_SCI_QL_ROWS * ql.LM_SCI_QL_ROW_EM
                    + (ql.LM_SCI_QL_ROWS - 1) * ql.LM_SCI_QL_ITEM_GAP_EM)
        self.assertGreaterEqual(float(height[:-2]), expected)

    def test_the_gap_is_wider_than_an_icon(self):
        """The relationship that actually protects Cancel.

        Small icons with a generous horizontal gap beat big buttons pressed together: the
        dead column belongs to neither control, so a press that misses an icon lands in
        space belonging to nothing rather than on the control next to it. Pinned as a
        RATIO rather than an absolute, so shrinking the glyphs again cannot quietly
        shrink the protection with them.
        """
        self.assertGreaterEqual(ql.LM_SCI_QL_GAP_EM, ql.LM_SCI_QL_ICON_EM,
                                "the dead column must be at least as wide as an icon")

    def test_the_row_is_the_vertical_touch_target(self):
        """The icons are not the target - the row is, and it stays finger-sized however
        small the glyphs get."""
        self.assertGreaterEqual(ql.LM_SCI_QL_ROW_EM, 2.0)
        self.assertLess(ql.LM_SCI_QL_ICON_EM, ql.LM_SCI_QL_ROW_EM,
                        "an icon taller than its row cannot be what was intended")

    # --- which tab it belongs to --------------------------------------------

    def test_the_queue_list_is_shown_only_on_the_queue_tab(self):
        class _Row:
            def __init__(self): self.shown = None
            def show(self, v): self.shown = v
        import science_tabs as st
        panel, queue = _Row(), _Row()
        st.lm_sci_tabs_set_current(CID, st.LM_SCI_QUEUE_TAB)
        self.assertTrue(ql.lm_sci_show_for_tab(CID, panel, queue))
        self.assertTrue(queue.shown)
        self.assertFalse(panel.shown)

    def test_the_readout_is_shown_on_every_other_tab(self):
        class _Row:
            def __init__(self): self.shown = None
            def show(self, v): self.shown = v
        import science_tabs as st
        from sbs_utils.procedural.query import set_science_selection
        from sbs_utils.procedural.science import science_set_scan_data
        set_science_selection(self.ship, self.a)
        science_set_scan_data(self.ship, self.a, {"scan": "seen"})
        st.lm_sci_tabs_set_current(CID, "scan")
        panel, queue = _Row(), _Row()
        ql.lm_sci_show_for_tab(CID, panel, queue)
        self.assertFalse(queue.shown, "the queue must not sit under every tab")

    # --- the name selects ---------------------------------------------------

    def test_pressing_a_queue_name_selects_that_contact(self):
        """A queue is a list of contacts you already care about, so the name is the
        fastest way back to one - no hunting it down on the radar."""
        from sbs_utils.procedural.query import get_science_selection
        import science_tabs as st
        entry = ql.lm_sci_ql_items(CID)[1]
        self.assertTrue(ql.lm_sci_ql_press_select({"cid": CID, "target": entry["target"]}))
        self.assertEqual(get_science_selection(self.ship), entry["target"])

    def test_selecting_from_the_queue_leaves_the_queue_alone(self):
        """The name SELECTS - it does not cancel, reorder or start anything."""
        before = [(e["target"], e["tab"]) for e in sq.lm_sci_queue_list("tsn")]
        entry = ql.lm_sci_ql_items(CID)[1]
        ql.lm_sci_ql_press_select({"cid": CID, "target": entry["target"]})
        self.assertEqual(before,
                         [(e["target"], e["tab"]) for e in sq.lm_sci_queue_list("tsn")])

    def test_a_select_press_with_no_data_does_nothing(self):
        self.assertFalse(ql.lm_sci_ql_press_select(None))
        self.assertFalse(ql.lm_sci_ql_press_select({"cid": CID}))

    # --- the actions --------------------------------------------------------

    def test_move_up_swaps_with_the_entry_ahead(self):
        items = ql.lm_sci_ql_items(CID)
        third = items[2]
        ql.lm_sci_ql_press_up({"side": third["side"], "target": third["target"],
                               "tab": third["tab"]})
        self.assertEqual([i["tab"] for i in ql.lm_sci_ql_items(CID)][1], "status")

    def test_move_up_is_one_place_not_to_the_front(self):
        items = ql.lm_sci_ql_items(CID)
        third = items[2]
        ql.lm_sci_ql_press_up({"side": third["side"], "target": third["target"],
                               "tab": third["tab"]})
        head = ql.lm_sci_ql_items(CID)[0]
        self.assertEqual(head["target"], self.a.id,
                         "the head must not change when a later entry moves up one")

    def test_the_head_cannot_move_up(self):
        head = ql.lm_sci_ql_items(CID)[0]
        self.assertFalse(ql.lm_sci_ql_press_up(
            {"side": head["side"], "target": head["target"], "tab": head["tab"]}))

    def test_cancel_removes_that_entry_only(self):
        items = ql.lm_sci_ql_items(CID)
        victim = items[1]
        before = len(items)
        self.assertTrue(ql.lm_sci_ql_press_cancel(
            {"side": victim["side"], "target": victim["target"], "tab": victim["tab"]}))
        after = ql.lm_sci_ql_items(CID)
        self.assertEqual(len(after), before - 1)
        self.assertNotIn((victim["target"], victim["tab"]),
                         [(i["target"], i["tab"]) for i in after])

    def test_cancelling_the_head_promotes_the_next(self):
        head = ql.lm_sci_ql_items(CID)[0]
        ql.lm_sci_ql_press_cancel({"side": head["side"], "target": head["target"],
                                   "tab": head["tab"]})
        new_head = ql.lm_sci_ql_items(CID)[0]
        self.assertNotEqual(new_head["target"], head["target"])

    def test_a_press_with_no_data_does_nothing(self):
        """`gui_button` hands a handler NOTHING unless it declares a required parameter -
        a handler that quietly acted on a default would act on the wrong row."""
        self.assertFalse(ql.lm_sci_ql_press_up(None))
        self.assertFalse(ql.lm_sci_ql_press_cancel(None))
        self.assertEqual(len(ql.lm_sci_ql_items(CID)), 3)

    # --- the rows themselves ------------------------------------------------

    def test_only_the_head_reports_progress(self):
        items = ql.lm_sci_ql_items(CID)
        self.assertEqual(items[0]["index"], 0)
        self.assertTrue(all(i["pct"] == 0 for i in items[1:]))

    def test_the_revision_moves_when_the_queue_does(self):
        before = ql.lm_sci_ql_revision(CID)
        head = ql.lm_sci_ql_items(CID)[0]
        ql.lm_sci_ql_press_cancel({"side": head["side"], "target": head["target"],
                                   "tab": head["tab"]})
        self.assertNotEqual(before, ql.lm_sci_ql_revision(CID))

    def test_an_empty_queue_says_so(self):
        sq.lm_sci_queue_clear()
        self.assertEqual(ql.lm_sci_ql_items(CID), [])
        self.assertIn("nothing queued", ql.lm_sci_ql_empty_text())


if __name__ == "__main__":
    unittest.main()
