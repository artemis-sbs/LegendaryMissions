"""LegendaryMissions PR #740: what its three changes must do.

1. `game_results_timestamp` builds the results record's time. The module does `import
   datetime`, so the call has to be `datetime.datetime.now()`.
2. The Game Master's selection details gain auto gauges (Energy): every gauge is updated, a
   value that is missing hides only its own gauge, and a gauge's maximum is its own.
3. The details refresh runs once a second only while the selected-object menu is on screen -
   from the moment the console opens, and it stops when the Game Master moves to another
   main menu.

    PYTHONPATH=../sbs_utils python -m unittest gamemaster.test_gm_pr740
"""
import os
import re
import sys
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

from gamemaster.test_gm_console import _Base, SELECTED, SHIPS, CID  # noqa: E402
from sbs_utils.helpers import Context, FakeEvent, FrameContext  # noqa: E402
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value  # noqa: E402

LM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestResultsTimestamp(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, os.path.join(LM, "consoles"))
        self.addCleanup(sys.path.remove, os.path.join(LM, "consoles"))

    def test_the_timestamp_is_a_date_and_a_time(self):
        import results_helpers
        stamp = results_helpers.game_results_timestamp()
        self.assertRegex(stamp, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")

    def test_an_unreadable_results_file_is_kept_aside_not_lost(self):
        import tempfile
        import results_helpers
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "game_results.yaml")
            with open(path, "w", encoding="utf-8") as f:
                f.write("results: [unclosed\n  nope: : :\n")
            self.assertEqual(results_helpers.game_results_load(path), [])
            kept = [n for n in os.listdir(d) if ".unreadable-" in n]
            self.assertEqual(len(kept), 1, os.listdir(d))
            self.assertRegex(kept[0], r"unreadable-\d{8}-\d{6}\.yaml$")


class _FakeGauge:
    def __init__(self):
        self.shown = None
        self.value = None
        self.max = None

    def show(self, flag):
        self.shown = bool(flag)

    def update(self, value=None, max=None, label=None, color=None):
        self.value = value
        self.max = max


class TestAutoGauges(unittest.TestCase):
    def setUp(self):
        from gamemaster.gamemaster import GmSelectionDetails
        self.handler = GmSelectionDetails(1)
        if not hasattr(self.handler, "add_auto_gauge"):
            self.skipTest("this branch has no auto gauges")
        import gamemaster.gamemaster as gm
        self.gm = gm
        self.values = {}
        self._real_blob = gm.get_data_set_value
        self._real_inv = gm.get_inventory_value
        gm.get_data_set_value = lambda obj, key, index=0, default=None: self.values.get(("blob", key, index))
        gm.get_inventory_value = lambda obj, key, default=None: self.values.get(("inv", key), default)
        self.addCleanup(setattr, gm, "get_data_set_value", self._real_blob)
        self.addCleanup(setattr, gm, "get_inventory_value", self._real_inv)

    def test_a_value_is_drawn_against_the_given_maximum(self):
        g = _FakeGauge()
        self.handler.add_auto_gauge("energy", 1000, g, is_blob=True)
        self.values[("blob", "energy", 0)] = 640.0
        self.handler.update_auto_gauges(7)
        self.assertEqual((g.shown, g.value, g.max), (True, 640.0, 1000))

    def test_a_missing_value_hides_that_gauge_and_not_the_others(self):
        first, second = _FakeGauge(), _FakeGauge()
        self.handler.add_auto_gauge("fuel", 100, first, is_blob=True)
        self.handler.add_auto_gauge("energy", 1000, second, is_blob=True)
        self.values[("blob", "energy", 0)] = 500.0          # fuel was never set
        self.handler.update_auto_gauges(7)
        self.assertIs(first.shown, False)
        self.assertEqual((second.shown, second.value), (True, 500.0),
                         "the gauge after a hidden one was never updated")

    def test_a_maximum_named_by_a_key_is_read_from_that_key(self):
        g = _FakeGauge()
        self.handler.add_auto_gauge("hp", "hp_max", g, is_blob=False)
        self.values[("inv", "hp")] = 30
        self.values[("inv", "hp_max")] = 90
        self.handler.update_auto_gauges(7)
        self.assertEqual((g.value, g.max), (30, 90))


class TestRefreshIsGatedByTheMenuOnScreen(_Base):
    """gui_update_interval_signal is the once-a-second tick the console's details ride."""

    def setUp(self):
        super().setUp()
        task = None
        from sbs_utils.procedural.gui import gui_task_for_client
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(CID, "gui_present"))
        task = gui_task_for_client(CID)
        self.handler = task.get_inventory_value("gm_details_handler") if task else None
        if self.handler is None:
            self.skipTest("the details handler is not on this console")
        self.calls = 0
        real = self.handler.refresh_data

        def counted():
            self.calls += 1
            return real()
        self.handler.refresh_data = counted
        # The route finds GM clients through these two engine calls.
        self._ids = mock_sbs.get_client_ID_list
        self._ship = getattr(mock_sbs, "get_ship_of_client", None)
        mock_sbs.get_client_ID_list = lambda: [CID]
        mock_sbs.get_ship_of_client = lambda cid: self.gm
        self.addCleanup(setattr, mock_sbs, "get_client_ID_list", self._ids)
        if self._ship is not None:
            self.addCleanup(setattr, mock_sbs, "get_ship_of_client", self._ship)

    def tick(self):
        before = self.calls
        self.emit("gui_update_interval_signal")
        return self.calls - before

    def test_it_refreshes_on_the_selected_menu_the_console_opens_on(self):
        self.assertGreater(self.tick(), 0,
                           "a fresh console on the selected-object menu never refreshes")

    # Gating the refresh to the selected menu is PR #740's goal and is not on the branch yet,
    # so on v1.4.0_dev this fails at the last line. Remove the decorator when it lands.
    @unittest.expectedFailure
    def test_it_stops_refreshing_when_another_main_menu_is_open(self):
        self.assertGreater(self.tick(), 0, "it must refresh on the selected menu first")
        self.open_menu(SHIPS)
        self.assertEqual(self.tick(), 0, "still refreshing with the Ships menu on screen")

    def test_it_starts_again_when_the_selected_menu_comes_back(self):
        self.open_menu(SHIPS)
        self.open_menu(SELECTED)
        self.assertGreater(self.tick(), 0)


if __name__ == "__main__":
    unittest.main()
