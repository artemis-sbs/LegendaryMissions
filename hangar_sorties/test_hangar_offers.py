"""Sorties are ordinary quests.

A sortie used to be a separate kind of thing - not a quest until taken, published by its
own offer provider with its own "take". That gave players a second name and a second
path for one idea. Now picking a craft grants that craft's orders to the PILOT as untaken
quests: they are listed under Available Quests, accepted there like any other quest, and
then sit on the Quests tab.

    PYTHONPATH=../../sbs_utils python -m unittest test_hangar_offers
"""
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes            # noqa: F401  breaks a circular import
from cosmos_dev.mock import sbs
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.mast.mast_node import MastDataObject
from sbs_utils.procedural.execution import set_shared_variable
from sbs_utils.procedural.offer import offer_clear
from sbs_utils.procedural.quest import quest_get_state, QuestState
from sbs_utils.procedural import quest_driver as QD

import hangar_board as HB

CID = 0x8080000000000001


#: One fighter order, one shuttle order and one for any craft, in the shape
#: `hangar_quests_for` reads: AMD nodes with a `key`, `display_text` and a `data` fence.
DOC = MastDataObject({"children": [
    {"key": "patrol", "display_text": "Picket Patrol", "description": "Fly the line.",
     "data": {"cockpit": "fighter", "objective": "Hold the picket"}},
    {"key": "ferry", "display_text": "Ferry Run", "description": "Carry it over.",
     "data": {"cockpit": "shuttle", "objective": "Deliver the crate"}},
    {"key": "any_job", "display_text": "Odd Job", "description": "Whatever.",
     "data": {"objective": "Something"}},
]})


class SortiesAreQuestsTests(unittest.TestCase):
    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        from sbs_utils.gui import GuiClient
        GuiClient(CID)
        offer_clear()
        set_shared_variable("HANGAR_QUEST_DOC", DOC)
        from sbs_utils.procedural.a2x.spawn import create_enemy
        from sbs_utils.procedural.query import to_id
        from sbs_utils.procedural.roles import add_role
        self.fighter = to_id(create_enemy(0, 0, 0, "kralien_cruiser", name="F1"))
        self.shuttle = to_id(create_enemy(200, 0, 0, "kralien_cruiser", name="S1"))
        add_role(self.shuttle, "shuttle")
        self.dock = to_id(create_enemy(500, 0, 0, "kralien_cruiser", name="Carrier"))

    def tearDown(self):
        offer_clear()
        set_shared_variable("HANGAR_QUEST_DOC", None)

    def _state(self, key):
        return int(quest_get_state(CID, key) or 0)

    def _titles(self, items):
        return [r.get("title") for r in items if QD._quest_offer_row(r) is not None]

    def _available(self, ship_id):
        return self._titles(QD.quest_offers_tab_items(CID, ship_id, "hangar"))

    def _taken(self, ship_id):
        return self._titles(QD.quest_tab_items(CID, ship_id))

    # --- granting -----------------------------------------------------------------
    def test_picking_a_fighter_offers_its_orders_as_quests(self):
        HB.hangar_offer_sorties(CID, self.fighter)
        self.assertEqual(sorted(self._available(self.dock)), ["Odd Job", "Picket Patrol"])
        self.assertEqual(self._taken(self.dock), [], "nothing is on Quests until accepted")

    def test_they_are_held_by_the_pilot_not_the_craft(self):
        """The Quests screens read the shared agent, the CLIENT and the console's ship;
        on the deck the ship is the dock, so an order on the craft would show nowhere."""
        HB.hangar_offer_sorties(CID, self.fighter)
        self.assertEqual(self._state("patrol"), int(QuestState.IDLE))
        self.assertIsNone(__import__("sbs_utils.procedural.quest", fromlist=["quest_get"])
                          .quest_get(self.fighter, "patrol"))

    def test_granting_twice_is_harmless(self):
        HB.hangar_offer_sorties(CID, self.fighter)
        HB.hangar_offer_sorties(CID, self.fighter)
        self.assertEqual(sorted(self._available(self.dock)), ["Odd Job", "Picket Patrol"])

    def test_no_doc_or_no_craft_grants_nothing(self):
        set_shared_variable("HANGAR_QUEST_DOC", None)
        self.assertEqual(HB.hangar_offer_sorties(CID, self.fighter), 0)
        set_shared_variable("HANGAR_QUEST_DOC", DOC)
        self.assertEqual(HB.hangar_offer_sorties(CID, None), 0)
        self.assertEqual(self._available(self.dock), [])

    # --- accepting -------------------------------------------------------------------
    def test_accepting_moves_it_to_quests_and_it_goes_with_the_pilot(self):
        HB.hangar_offer_sorties(CID, self.fighter)
        row = next(r for r in QD.quest_offers_tab_items(CID, self.dock, "hangar")
                   if QD._quest_offer_row(r) is not None and r.get("title") == "Picket Patrol")
        QD.quest_tab_accept(row, CID)
        self.assertEqual(self._state("patrol"), int(QuestState.ACTIVE))
        self.assertNotIn("Picket Patrol", self._available(self.dock))
        self.assertIn("Picket Patrol", self._taken(self.dock), "seen from the deck")
        self.assertIn("Picket Patrol", self._taken(self.fighter), "and from the cockpit")

    # --- changing craft --------------------------------------------------------------
    def test_switching_craft_swaps_the_untaken_orders(self):
        HB.hangar_offer_sorties(CID, self.fighter)
        HB.hangar_offer_sorties(CID, self.shuttle)
        self.assertEqual(sorted(self._available(self.dock)), ["Ferry Run", "Odd Job"])

    def test_switching_craft_keeps_an_accepted_order(self):
        HB.hangar_offer_sorties(CID, self.fighter)
        QD._quest_offer_take(CID, {"data": {"quest_agent_id": CID, "quest_id": "patrol"}})
        HB.hangar_offer_sorties(CID, self.shuttle)
        self.assertEqual(self._state("patrol"), int(QuestState.ACTIVE))
        self.assertIn("Picket Patrol", self._taken(self.dock))


if __name__ == "__main__":
    unittest.main()
