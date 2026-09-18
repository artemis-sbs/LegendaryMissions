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
        # A delete is deferred to the end of the handler, which a test never reaches - so
        # a deleted id stays "pending" and, once the fresh sim hands the same id out again,
        # object_exists says the NEW object is gone.
        from sbs_utils.delete_queue import DeleteQueue
        DeleteQueue.clear()
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


class TestDragOrderRecord(OrdersBase):
    """Drag to order: the target has to survive from the drag to the menu, and must never
    come back once it is stale."""

    def setUp(self):
        super().setUp()
        self.unit = self.npc("tsn", "Unit")
        self.foe = self.npc("klingon", "Foe")

    def test_the_target_is_remembered_for_that_unit(self):
        O.lm_drag_orders_set(self.hero.id, self.unit.id, self.foe.id)
        self.assertEqual(self.foe.id, O.lm_drag_orders_target(self.hero.id, self.unit.id))

    def test_not_for_a_different_unit(self):
        """A record is for ONE unit - comms on another ally must not inherit it."""
        other = self.npc("tsn", "Other")
        O.lm_drag_orders_set(self.hero.id, self.unit.id, self.foe.id)
        self.assertEqual(0, O.lm_drag_orders_target(self.hero.id, other.id))

    def test_A_DELETED_TARGET_IS_NO_TARGET(self):
        from sbs_utils.procedural.space_objects import delete_object
        O.lm_drag_orders_set(self.hero.id, self.unit.id, self.foe.id)
        delete_object(self.foe.id)
        self.assertEqual(0, O.lm_drag_orders_target(self.hero.id, self.unit.id))

    def test_a_deleted_unit_is_no_target(self):
        from sbs_utils.procedural.space_objects import delete_object
        O.lm_drag_orders_set(self.hero.id, self.unit.id, self.foe.id)
        delete_object(self.unit.id)
        self.assertEqual(0, O.lm_drag_orders_target(self.hero.id, self.unit.id))

    def test_clear_forgets_it(self):
        O.lm_drag_orders_set(self.hero.id, self.unit.id, self.foe.id)
        O.lm_drag_orders_clear(self.hero.id)
        self.assertEqual(0, O.lm_drag_orders_target(self.hero.id, self.unit.id))

    def test_two_bridges_do_not_overwrite_each_other(self):
        other_bridge = to_object(player_spawn(5000, 0, 0, "Other", "tsn", "behav_playership"))
        foe2 = self.npc("klingon", "Foe2")
        O.lm_drag_orders_set(self.hero.id, self.unit.id, self.foe.id)
        O.lm_drag_orders_set(other_bridge.id, self.unit.id, foe2.id)
        self.assertEqual(self.foe.id, O.lm_drag_orders_target(self.hero.id, self.unit.id))
        self.assertEqual(foe2.id, O.lm_drag_orders_target(other_bridge.id, self.unit.id))


if __name__ == "__main__":
    unittest.main()
