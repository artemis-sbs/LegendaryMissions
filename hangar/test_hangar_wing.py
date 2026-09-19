"""A station's AI wing: launch, land, losses, and the `launch` order capability.

The wing is NOT the hangar's craft - those are player ships a pilot climbs into, and an
NPC brain cannot fly a behav_playership. A wing is a count of AI fighters spawned as
behav_npcship on launch and removed again when they land.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest hangar.test_hangar_wing
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs
from sbs_utils.agent import clear_shared
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.roles import has_role
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.procedural.sides import side_ensure
from sbs_utils.procedural.space_objects import delete_object, set_pos
from sbs_utils.procedural import orders as O

from hangar import hangar_wing as W


class WingTests(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        DeleteQueue.clear()
        clear_shared()
        SpaceObject.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent())
        side_ensure("tsn")
        self.hero = to_id(player_spawn(0, 0, 0, "Hero", "tsn", "tsn_light_cruiser"))
        self.base = to_id(npc_spawn(5000, 0, 0, "DS 1", "tsn,station", "starbase_command", "behav_station"))
        self.cruiser = to_id(npc_spawn(1000, 0, 0, "Valiant", "tsn", "tsn_light_cruiser", "behav_npcship"))
        O.orders_caps_provider(W.hangar_wing_caps)
        # Sim time, under the test's control - refit is timed.
        self.now = 100.0
        self._real_now = W._hangar_wing_now
        W._hangar_wing_now = lambda: self.now

    def tearDown(self):
        W._hangar_wing_now = self._real_now
        FrameContext.context = None

    def land_one(self):
        fid = W.hangar_wing_launch(self.base, 1)[0]
        set_pos(fid, 5100, 0, 0)
        self.assertTrue(W.hangar_wing_land(fid))
        return fid

    def test_A_STATION_HAS_A_WING(self):
        self.assertEqual(W.HANGAR_WING_DEFAULT_SIZE, W.hangar_wing_size(self.base))
        self.assertEqual(W.HANGAR_WING_DEFAULT_SIZE, W.hangar_wing_ready(self.base))

    def test_a_ship_without_bays_has_none(self):
        self.assertEqual(0, W.hangar_wing_size(self.cruiser))

    def test_a_carrier_uses_its_bays(self):
        carrier = to_id(npc_spawn(0, 0, 3000, "Carrier", "tsn", "arvonian_light_carrier", "behav_npcship"))
        self.assertEqual(W.HANGAR_WING_DEFAULT_SIZE, W.hangar_wing_size(carrier))   # 8 bays, capped

    def test_LAUNCH_SPAWNS_NPC_FIGHTERS_AND_EMPTIES_THE_BAY(self):
        ids = W.hangar_wing_launch(self.base)
        self.assertEqual(W.HANGAR_WING_DEFAULT_SIZE, len(ids))
        self.assertEqual(0, W.hangar_wing_ready(self.base))
        self.assertEqual(sorted(ids), W.hangar_wing_out(self.base))
        for fid in ids:
            self.assertTrue(has_role(fid, "__npc__"))            # an AI can fly it
            self.assertEqual("behav_npcship", to_object(fid).behave_id)
            self.assertEqual(self.base, W.hangar_wing_home(fid))

    def test_an_empty_bay_launches_nothing(self):
        W.hangar_wing_launch(self.base)
        self.assertEqual([], W.hangar_wing_launch(self.base))

    def test_launch_a_few(self):
        self.assertEqual(2, len(W.hangar_wing_launch(self.base, 2)))
        self.assertEqual(W.HANGAR_WING_DEFAULT_SIZE - 2, W.hangar_wing_ready(self.base))

    def test_LANDING_STARTS_A_REFIT(self):
        fid = W.hangar_wing_launch(self.base, 1)[0]
        set_pos(fid, 20000, 0, 0)
        self.assertFalse(W.hangar_wing_land(fid))                   # too far
        set_pos(fid, 5100, 0, 0)
        self.assertTrue(W.hangar_wing_land(fid))
        self.assertEqual(W.HANGAR_WING_DEFAULT_SIZE - 1, W.hangar_wing_ready(self.base))
        self.assertEqual(1, W.hangar_wing_refitting(self.base))
        self.assertEqual(W.HANGAR_WING_DEFAULT_REFIT, W.hangar_wing_refit_remaining(self.base))

    def test_A_REFITTED_FIGHTER_IS_READY_AGAIN(self):
        self.land_one()
        self.now += W.HANGAR_WING_DEFAULT_REFIT
        self.assertEqual(W.HANGAR_WING_DEFAULT_SIZE, W.hangar_wing_ready(self.base))
        self.assertEqual(0, W.hangar_wing_refitting(self.base))

    def test_a_lost_fighter_never_comes_back(self):
        fid = W.hangar_wing_launch(self.base, 1)[0]
        delete_object(fid)
        DeleteQueue.clear()
        self.assertEqual(W.HANGAR_WING_DEFAULT_SIZE - 1, W.hangar_wing_ready(self.base))

    def test_the_size_can_be_set(self):
        W.hangar_wing_set_size(self.cruiser, 2)
        self.assertEqual(2, W.hangar_wing_ready(self.cruiser))
        W.hangar_wing_set_size(self.base, 0)
        self.assertEqual([], W.hangar_wing_launch(self.base))

    def test_A_STATION_WITH_A_WING_CAN_BE_ORDERED(self):
        self.assertEqual({"launch"}, O.orders_caps(self.base))

    def test_THE_MENU_MORPHS_ONCE_THE_WING_IS_OUT(self):
        """Launch gives way to Reassign / Recall - even with craft still in the bay."""
        W.hangar_wing_launch(self.base, 1)
        self.assertEqual({"wing_out"}, O.orders_caps(self.base))
        W.hangar_wing_launch(self.base)
        self.assertEqual({"wing_out"}, O.orders_caps(self.base))

    def test_a_wing_all_in_refit_offers_nothing(self):
        W.hangar_wing_set_size(self.base, 1)
        self.land_one()
        self.assertEqual(set(), O.orders_caps(self.base))
        self.now += W.HANGAR_WING_DEFAULT_REFIT
        self.assertEqual({"launch"}, O.orders_caps(self.base))

    def test_no_wing_no_launch(self):
        W.hangar_wing_set_size(self.base, 0)
        self.assertEqual(set(), O.orders_caps(self.base))

    def test_A_LAUNCH_SETS_BINGO_FUEL(self):
        from sbs_utils.procedural.timers import is_timer_set
        fid = W.hangar_wing_launch(self.base, 1)[0]
        self.assertTrue(is_timer_set(fid, W.HANGAR_WING_BINGO))
        self.assertFalse(W.hangar_wing_is_bingo(fid))

    def test_REASSIGN_TAKES_THE_FUELED_AND_THE_READY_NOT_THE_BINGO(self):
        out = W.hangar_wing_launch(self.base, 2)
        W.hangar_wing_bingo_mark(out[0])
        again = W.hangar_wing_reassign(self.base)
        self.assertIn(out[1], again)
        self.assertNotIn(out[0], again)
        # the two left in the bay launched too
        self.assertEqual(3, len(again))
        self.assertEqual(0, W.hangar_wing_ready(self.base))


if __name__ == "__main__":
    unittest.main()
