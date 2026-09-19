"""A station's AI wings: how many, launch, land and refit, bingo, and the per-wing menu.

The wings are NOT the hangar's craft - those are player ships a pilot climbs into, and an
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
from sbs_utils.procedural.sides import side_ensure, side_set_relations
from sbs_utils.procedural.space_objects import delete_object, set_pos
from sbs_utils.procedural import orders as O

from hangar import hangar_wing as W

SIZE = W.HANGAR_WING_DEFAULT_SIZE


class _Label:
    name = "wing_order"

    def __init__(self, **meta):
        self.meta = meta

    def get_inventory_value(self, key, default=None):
        return self.meta.get(key, default)


READY = _Label(wing_state="ready")
OUT = _Label(wing_state="out")


class WingBase(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        DeleteQueue.clear()
        clear_shared()
        SpaceObject.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent())
        side_ensure("tsn")
        self.hero = to_id(player_spawn(0, 0, 0, "Hero", "tsn", "tsn_light_cruiser"))
        # A command starbase has two wings; the others one.
        self.base = to_id(npc_spawn(5000, 0, 0, "DS 1", "tsn,station", "starbase_command", "behav_station"))
        self.depot = to_id(npc_spawn(9000, 0, 0, "Depot", "tsn,station", "starbase_industry", "behav_station"))
        self.cruiser = to_id(npc_spawn(1000, 0, 0, "Valiant", "tsn", "tsn_light_cruiser", "behav_npcship"))
        O.orders_caps_provider(W.hangar_wing_caps)
        # Sim time, under the test's control - refit is timed.
        self.now = 100.0
        self._real_now = W._hangar_wing_now
        W._hangar_wing_now = lambda: self.now

    def tearDown(self):
        W._hangar_wing_now = self._real_now
        FrameContext.context = None


class TestHowMany(WingBase):

    def test_A_COMMAND_STARBASE_HAS_TWO_WINGS(self):
        self.assertEqual(["red", "gold"], W.hangar_wing_names(self.base))
        self.assertEqual(SIZE, W.hangar_wing_size(self.base))
        self.assertEqual(2 * SIZE, W.hangar_wing_ready(self.base))
        self.assertEqual(SIZE, W.hangar_wing_ready(self.base, "gold"))

    def test_other_stations_have_one(self):
        self.assertEqual(["red"], W.hangar_wing_names(self.depot))

    def test_a_ship_without_bays_has_none(self):
        self.assertEqual([], W.hangar_wing_names(self.cruiser))

    def test_a_carrier_uses_its_bays(self):
        carrier = to_id(npc_spawn(0, 0, 3000, "Carrier", "tsn", "arvonian_light_carrier", "behav_npcship"))
        self.assertEqual(SIZE, W.hangar_wing_size(carrier))            # 8 bays, capped
        self.assertEqual(["red"], W.hangar_wing_names(carrier))

    def test_a_mission_sets_wings_and_size(self):
        W.hangar_wing_set_size(self.depot, 2, count=3)
        self.assertEqual(["red", "gold", "blue"], W.hangar_wing_names(self.depot))
        self.assertEqual(6, W.hangar_wing_ready(self.depot))
        W.hangar_wing_set_size(self.depot, 0)
        self.assertEqual([], W.hangar_wing_names(self.depot))

    def test_display_names(self):
        self.assertEqual("Red wing", W.hangar_wing_display("red"))
        self.assertEqual("Gold 2 wing", W.hangar_wing_display("gold2"))


class TestLaunchAndLand(WingBase):

    def test_LAUNCHING_ONE_WING_LEAVES_THE_OTHER_IN_THE_BAY(self):
        ids = W.hangar_wing_launch(self.base, wing="red")
        self.assertEqual(SIZE, len(ids))
        self.assertEqual(0, W.hangar_wing_ready(self.base, "red"))
        self.assertEqual(SIZE, W.hangar_wing_ready(self.base, "gold"))
        self.assertEqual(sorted(ids), W.hangar_wing_out(self.base, "red"))
        self.assertEqual([], W.hangar_wing_out(self.base, "gold"))
        for fid in ids:
            self.assertTrue(has_role(fid, "__npc__"))            # an AI can fly it
            self.assertEqual("behav_npcship", to_object(fid).behave_id)
            self.assertEqual(self.base, W.hangar_wing_home(fid))
            self.assertEqual("red", W.hangar_wing_of(fid))

    def test_launch_every_wing(self):
        self.assertEqual(2 * SIZE, len(W.hangar_wing_launch(self.base)))
        self.assertEqual(0, W.hangar_wing_ready(self.base))

    def test_launch_a_few(self):
        self.assertEqual(2, len(W.hangar_wing_launch(self.base, 2, "gold")))
        self.assertEqual(SIZE - 2, W.hangar_wing_ready(self.base, "gold"))

    def test_an_empty_bay_launches_nothing(self):
        W.hangar_wing_launch(self.base, wing="red")
        self.assertEqual([], W.hangar_wing_launch(self.base, wing="red"))

    def test_LANDING_REFITS_INTO_ITS_OWN_WING(self):
        fid = W.hangar_wing_launch(self.base, 1, "gold")[0]
        set_pos(fid, 20000, 0, 0)
        self.assertFalse(W.hangar_wing_land(fid))                   # too far
        set_pos(fid, 5100, 0, 0)
        self.assertTrue(W.hangar_wing_land(fid))
        self.assertEqual(1, W.hangar_wing_refitting(self.base, "gold"))
        self.assertEqual(0, W.hangar_wing_refitting(self.base, "red"))
        self.assertEqual(SIZE - 1, W.hangar_wing_ready(self.base, "gold"))
        self.assertEqual(W.HANGAR_WING_DEFAULT_REFIT, W.hangar_wing_refit_remaining(self.base, "gold"))
        self.now += W.HANGAR_WING_DEFAULT_REFIT
        self.assertEqual(SIZE, W.hangar_wing_ready(self.base, "gold"))

    def test_a_lost_fighter_never_comes_back(self):
        fid = W.hangar_wing_launch(self.base, 1, "red")[0]
        delete_object(fid)
        DeleteQueue.clear()
        self.assertEqual(SIZE - 1, W.hangar_wing_ready(self.base, "red"))

    def test_A_LAUNCH_SETS_BINGO_FUEL(self):
        from sbs_utils.procedural.timers import is_timer_set
        fid = W.hangar_wing_launch(self.base, 1, "red")[0]
        self.assertTrue(is_timer_set(fid, W.HANGAR_WING_BINGO))
        self.assertFalse(W.hangar_wing_is_bingo(fid))

    def test_REASSIGN_MOVES_ONE_WING_ONLY_AND_NOT_ITS_BINGO(self):
        red = W.hangar_wing_launch(self.base, 2, "red")
        gold = W.hangar_wing_launch(self.base, 1, "gold")
        W.hangar_wing_bingo_mark(red[0])
        again = W.hangar_wing_reassign(self.base, "red")
        self.assertIn(red[1], again)
        self.assertNotIn(red[0], again)                             # bingo, heading home
        self.assertNotIn(gold[0], again)                            # another wing
        self.assertEqual(SIZE - 1, len(again))                      # 1 still out + the rest of the bay
        self.assertEqual(0, W.hangar_wing_ready(self.base, "red"))
        self.assertEqual(SIZE - 1, W.hangar_wing_ready(self.base, "gold"))


class TestTheMenu(WingBase):

    def inst(self, label):
        return W.hangar_wing_instances(self.base, label)

    def test_BOTH_WINGS_OFFER_LAUNCH(self):
        self.assertEqual([("red", "Red wing"), ("gold", "Gold wing")], self.inst(READY))
        self.assertEqual([], self.inst(OUT))
        self.assertEqual({"launch"}, O.orders_caps(self.base))

    def test_A_WING_OUT_OFFERS_REASSIGN_THE_OTHER_STILL_LAUNCH(self):
        W.hangar_wing_launch(self.base, 1, "red")
        self.assertEqual([("gold", "Gold wing")], self.inst(READY))
        self.assertEqual([("red", "Red wing")], self.inst(OUT))
        self.assertEqual({"launch", "wing_out"}, O.orders_caps(self.base))

    def test_every_wing_out(self):
        W.hangar_wing_launch(self.base)
        self.assertEqual([], self.inst(READY))
        self.assertEqual({"wing_out"}, O.orders_caps(self.base))

    def test_a_wing_all_in_refit_offers_nothing(self):
        W.hangar_wing_set_size(self.depot, 1)
        fid = W.hangar_wing_launch(self.depot, wing="red")[0]
        set_pos(fid, 9100, 0, 0)
        self.assertTrue(W.hangar_wing_land(fid))
        self.assertEqual(set(), O.orders_caps(self.depot))
        self.now += W.HANGAR_WING_DEFAULT_REFIT
        self.assertEqual({"launch"}, O.orders_caps(self.depot))

    def test_ONE_MENU_ENTRY_PER_WING(self):
        """Through the library's orders_items, the way the comms popup builds it."""
        side_set_relations(side_ensure("tsn"), side_ensure("raider"), mock_sbs.DIPLOMACY.HOSTILE)
        foe = to_id(npc_spawn(5000, 0, 4000, "Raider", "raider", "tsn_light_cruiser", "behav_npcship"))
        launch = _Label(type="objective/orders/launch/attack", display_name="Launch @",
                        valid_for="hostile", requires="launch",
                        instances=W.hangar_wing_instances, wing_state="ready")
        texts = [t for _, _, t in O.orders_items(self.hero, self.base, foe, labels=[launch])]
        self.assertEqual(["Launch Red wing", "Launch Gold wing"], texts)
        keys = [k for _, k, _ in O.orders_items(self.hero, self.base, foe, labels=[launch])]
        self.assertEqual(["red", "gold"], keys)

    def test_no_wing_no_orders(self):
        W.hangar_wing_set_size(self.depot, 0)
        self.assertEqual(set(), O.orders_caps(self.depot))


if __name__ == "__main__":
    unittest.main()
