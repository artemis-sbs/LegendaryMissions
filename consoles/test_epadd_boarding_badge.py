"""The Boarding Party tile never tells the console it is waiting for that it is full.

A crew party holds a place for everybody on the bridge, so nothing is left on the open
roster - and the tile's badge read "full" on the very console the party was holding a
place for. Seen in the engine, 2026-10-03, on a mission made from the starter template.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_epadd_boarding_badge
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes            # noqa: F401  breaks a circular import
import cosmos_dev.mock.sbs as mock_sbs
from sbs_utils.agent import Agent, clear_shared
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.procedural import boarding as B

from epadd import lm_epadd_boarding

ME = 0x8000000000000001
OTHER = 0x8000000000000002


class _Sim:
    time_tick_counter = 0


class _Page:
    def __init__(self, client_id):
        self.client_id = client_id
        self.console = "engineering"
        self.gui_task = None


class BadgeTests(unittest.TestCase):
    def setUp(self):
        FrameContext.context = Context(_Sim(), mock_sbs, FakeEvent(0, "test"))
        clear_shared()
        B.boarding_clear()
        B._TEAM.clear()
        self.addCleanup(B.boarding_clear)
        self.addCleanup(B._TEAM.clear)
        self.addCleanup(setattr, FrameContext, "page", None)
        FrameContext.page = _Page(ME)

    def invite(self, roster, reserved):
        Agent.SHARED.set_inventory_value(B.INVITE_KEY, {
            "open": True, "title": "The Hulk", "roster": list(roster),
            "reserved": dict(reserved), "ship": 0})

    def test_no_party_says_nothing(self):
        self.assertEqual(lm_epadd_boarding(), "")

    def test_a_place_held_for_this_console_names_the_place(self):
        self.invite([101], {ME: 101})
        self.assertEqual(lm_epadd_boarding(), "The Hulk")

    def test_a_party_with_no_place_for_this_console_is_full(self):
        self.invite([101], {OTHER: 101})
        self.assertEqual(lm_epadd_boarding(), "full")


if __name__ == "__main__":
    unittest.main()
