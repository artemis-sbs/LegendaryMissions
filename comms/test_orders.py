"""Who a bridge can give orders to.

Reported: "Comms cannot give orders to allied NPCs. It should be able to." The gate was
one role, `prefab_npc_defender`, added in exactly two places - so a SURRENDERED ENEMY got
the orders menu and a genuine ally did not.

The four things worth pinning are the four answers the gate gives, plus the second
blocker nobody would have found until a crew right-clicked an ally and got an empty menu.
"""
import os
import sys
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import cosmos_dev.mock.sbs as mock
sys.modules.setdefault("sbs", mock)
sys.path.insert(0, os.path.dirname(__file__))
import orders as O

from sbs_utils.agent import Agent, clear_shared
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.roles import add_role
from sbs_utils.procedural.sides import side_ensure
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.spaceobject import SpaceObject


class OrdersBase(unittest.TestCase):
    def setUp(self):
        mock.create_new_sim()
        Agent.clear()
        clear_shared()
        SpaceObject.clear()
        FrameContext.context = Context(mock.sim, mock, FakeEvent(1))
        # `side_are_allies` answers False for an UNDECLARED side, so a test without this
        # passes for the wrong reason - everything looks un-orderable.
        side_ensure("tsn")
        side_ensure("klingon")
        self.hero = to_object(player_spawn(0, 0, 0, "Hero", "tsn", "behav_playership"))

    def tearDown(self):
        FrameContext.context = None

    def npc(self, side, name="Ship", roles=""):
        r = side + ("," + roles if roles else "")
        return to_object(npc_spawn(1000, 0, 0, name, r, "tng_fed_nebula",
                                   "behav_npcship"))


class TestTheGate(OrdersBase):
    def test_AN_ALLY_CAN_BE_ORDERED(self):
        """The whole report. This was False for every ally in the game."""
        self.assertTrue(O.lm_can_take_orders(self.hero.id, self.npc("tsn").id))

    def test_an_enemy_cannot(self):
        self.assertFalse(O.lm_can_take_orders(self.hero.id, self.npc("klingon").id))

    def test_the_historic_role_still_works(self):
        """A surrendered enemy carries `prefab_npc_defender` and keeps its menu - that
        path was not wrong, it was just the only one."""
        foe = self.npc("klingon", roles="prefab_npc_defender")
        self.assertTrue(O.lm_can_take_orders(self.hero.id, foe.id))

    def test_A_STORY_SHIP_CAN_OPT_OUT(self):
        """An ally with somewhere to be is not a unit. The Enterprise-C running for the
        rift is allied, orderable by this rule, and the subject of the trial a crew would
        be ordering her out of."""
        ally = self.npc("tsn")
        self.assertTrue(O.lm_can_take_orders(self.hero.id, ally.id))
        O.lm_orders_block(ally)
        self.assertFalse(O.lm_can_take_orders(self.hero.id, ally.id))

    def test_a_player_ship_is_not_orderable(self):
        """Another bridge is not somebody's escort."""
        other = to_object(player_spawn(5000, 0, 0, "Other", "tsn", "behav_playership"))
        self.assertFalse(O.lm_can_take_orders(self.hero.id, other.id))

    def test_nothing_selected_is_not_an_error(self):
        self.assertFalse(O.lm_can_take_orders(self.hero.id, None))


class TestTheOrderList(OrdersBase):
    def test_AN_ALLY_WITH_NO_ORDERS_STILL_GETS_A_MENU(self):
        """The second blocker, and the one that would have shipped. The menu is built
        from a per-ship `give_orders_type` that only the prefabs set, so widening the
        gate alone opens an EMPTY menu on every ally - worse than no menu at all."""
        ally = self.npc("tsn")
        self.assertEqual(O.lm_orders_type(ally.id), O.DEFAULT_ORDERS)

    def test_a_ship_that_has_its_own_keeps_it(self):
        from sbs_utils.procedural.inventory import set_inventory_value
        ally = self.npc("tsn")
        set_inventory_value(ally.id, "give_orders_type", "objective/orders/special")
        self.assertEqual(O.lm_orders_type(ally.id), "objective/orders/special")

    def test_the_default_is_remembered(self):
        """So the popup and the carry-out path agree, rather than one of them looking it
        up again and getting a different answer."""
        ally = self.npc("tsn")
        O.lm_orders_type(ally.id)
        from sbs_utils.procedural.inventory import get_inventory_value
        self.assertEqual(get_inventory_value(ally.id, "give_orders_type", None),
                         O.DEFAULT_ORDERS)


if __name__ == "__main__":
    unittest.main()
