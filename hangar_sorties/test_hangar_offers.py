"""Sortie orders as OFFERS, rather than a board on one screen.

The sortie board used to be a list and a briefing sharing the whole lower third of the
flight deck, which made a sortie the one kind of work you could see from exactly ONE
console - and only after walking to it. As an offer it is in the PADD, reachable from any
console and from the cockpit, and the flight deck gets its band back.

    python -m unittest test_hangar_offers
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
from sbs_utils.procedural.offer import offer_clear, offer_providers, offers

import hangar_board as HB

CID = 91


def _ctx(**kw):
    base = {"client_id": CID, "ship_id": 0, "object_id": None, "console": None}
    base.update(kw)
    return MastDataObject(base)


#: One fighter order and one shuttle order, in the shape `hangar_quests_for` reads: AMD
#: nodes are plain dicts with a `key`, `display_text` and a parsed `data` fence.
DOC = MastDataObject({"children": [
    {"key": "patrol", "display_text": "Picket Patrol", "description": "Fly the line.",
     "data": {"cockpit": "fighter", "objective": "Hold the picket"}},
    {"key": "ferry", "display_text": "Ferry Run", "description": "Carry it over.",
     "data": {"cockpit": "shuttle", "objective": "Deliver the crate"}},
    {"key": "any_job", "display_text": "Odd Job", "description": "Whatever.",
     "data": {"objective": "Something"}},
]})


class _Base(unittest.TestCase):
    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        offer_clear()
        set_shared_variable("HANGAR_QUEST_DOC", DOC)
        self._craft = None
        self._real = HB.hangar_offer_craft
        HB.hangar_offer_craft = lambda cid: self._craft

    def tearDown(self):
        HB.hangar_offer_craft = self._real
        offer_clear()
        set_shared_variable("HANGAR_QUEST_DOC", None)


class ProviderTests(_Base):
    def test_it_registers(self):
        HB.hangar_offers_register()
        self.assertIn("hangar", offer_providers())

    def test_no_craft_means_no_sorties(self):
        """An order is offered for a SPECIFIC cockpit, so without one there is nothing to
        offer - and a tile listing sorties nobody can take is worse than no tile."""
        self._craft = None
        self.assertEqual(HB.hangar_offer_provider(_ctx()), [])

    def test_no_doc_means_no_sorties(self):
        """The ordinary state of a mission that does not use sorties at all."""
        set_shared_variable("HANGAR_QUEST_DOC", None)
        self._craft = 5
        self.assertEqual(HB.hangar_offer_provider(_ctx()), [])

    def test_a_per_object_question_has_no_sortie_answer(self):
        """An order is held by a cockpit, not by the thing you clicked on."""
        self._craft = 5
        self.assertEqual(HB.hangar_offer_provider(_ctx(object_id=99)), [])

    def test_the_rows_are_offers(self):
        self._craft = 5
        rows = HB.hangar_offer_provider(_ctx())
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r.get("kind"), "sortie")
            # NOT app="quest": a sortie is not a quest until it is assigned, so
            # that click went to a list which could not contain it.
            self.assertIsNone(r.get("app"))
            self.assertTrue(callable(r.get("take")))
            self.assertTrue(str(r.get("key")).startswith("sortie:"))

    def test_the_key_names_the_CLIENT_and_the_order(self):
        """Keyed on the CLIENT, like the ownership.

        Two pilots offered the same order must not collide - but ONE pilot swapping
        fighters must not mint a second key for an order they already hold, which is
        what keying on the craft did.
        """
        self._craft = 5
        a = {r.get("key") for r in HB.hangar_offer_provider(_ctx())}
        self._craft = 6
        b = {r.get("key") for r in HB.hangar_offer_provider(_ctx())}
        self.assertEqual(a, b, "changing craft minted new keys for the same orders")
        other = {r.get("key") for r in HB.hangar_offer_provider(_ctx(client_id=CID + 1))}
        self.assertFalse(a & other, "two clients produced the same offer key")

    def test_it_carries_what_the_launch_needs(self):
        self._craft = 5
        row = HB.hangar_offer_provider(_ctx())[0]
        self.assertEqual(row.get("data").get("craft"), 5)
        self.assertTrue(row.get("data").get("sortie"))

    def test_it_says_where_to_take_it(self):
        self._craft = 5
        row = HB.hangar_offer_provider(_ctx())[0]
        self.assertIn("Hangar", row.get("where"))
        row.get("where").encode("ascii")

    def test_it_reaches_the_registry(self):
        """The whole point - a sortie in the same list as every other kind of work."""
        HB.hangar_offers_register()
        self._craft = 5
        kinds = {r.get("kind") for r in offers(client_id=CID)}
        self.assertIn("sortie", kinds)

    def test_a_broken_craft_lookup_does_not_take_the_board_down(self):
        """offer._run_provider guards this, but the provider is what a bad link hits."""
        HB.hangar_offers_register()

        def boom(cid):
            raise RuntimeError("no link")

        HB.hangar_offer_craft = boom
        self.assertEqual(offers(client_id=CID), [])


class TheDeckSelectionCountsTests(unittest.TestCase):
    """The flight deck is where a sortie is CHOSEN, and it was the one console that
    offered none.

    A craft has two sources and only one existed: in the cockpit it is a dedicated link
    set at launch, but on the deck nothing is launched yet - the pilot has only picked a
    row, and that selection lives in the screen's MAST task scope where no Python
    provider can reach it. So the deck reported no craft, offered no sorties, and
    `//gui/app/offers if ... offer_count_here() > 0` then hid the whole tile. The symptom
    is an app that simply is not there.
    """

    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        from sbs_utils.gui import GuiClient
        GuiClient(CID)
        offer_clear()
        set_shared_variable("HANGAR_QUEST_DOC", DOC)
        HB.hangar_offers_register()

    def tearDown(self):
        offer_clear()
        set_shared_variable("HANGAR_QUEST_DOC", None)

    def test_nothing_picked_offers_nothing(self):
        from sbs_utils.procedural.offer import offer_count
        self.assertEqual(offer_count(client_id=CID), 0)

    def test_picking_a_craft_makes_the_tile_appear(self):
        """THE BUG, as a number: the route condition is `offer_count_here() > 0`."""
        from sbs_utils.procedural.inventory import set_inventory_value
        from sbs_utils.procedural.offer import offer_count
        set_inventory_value(CID, HB.HANGAR_RIDE_KEY, 777)
        self.assertGreater(offer_count(client_id=CID), 0)

    def test_the_offer_is_for_the_craft_that_was_picked(self):
        from sbs_utils.procedural.inventory import set_inventory_value
        from sbs_utils.procedural.offer import offers
        set_inventory_value(CID, HB.HANGAR_RIDE_KEY, 777)
        rows = [r for r in offers(client_id=CID) if r.get("kind") == "sortie"]
        self.assertTrue(rows)
        self.assertEqual(rows[0].get("data").get("craft"), 777)

    def test_a_launched_craft_still_wins(self):
        """In the seat the dedicated link is the truth; the deck pick is the fallback."""
        from sbs_utils.procedural.inventory import set_inventory_value
        set_inventory_value(CID, HB.HANGAR_RIDE_KEY, 777)
        real = HB.hangar_offer_craft
        try:
            self.assertEqual(HB.hangar_offer_craft(CID), 777)
        finally:
            HB.hangar_offer_craft = real


class TakingASortieTests(unittest.TestCase):
    """A JOB BELONGS TO THE CLIENT, and getting that wrong made the feature look broken.

    `quest_tab_items` reads exactly three agents - the shared story agent, the CLIENT and
    the console's SHIP. A sortie granted to the CRAFT is displayed by nothing at all
    while the pilot is on the flight deck, because there the console is assigned to the
    dock rather than to the fighter. The order existed, it ticked, and no screen showed
    it. The old code survived only because it granted at LAUNCH, when the craft IS the
    console's ship.

    So: take it as the client, and check it from the DECK - `ship_id` set to the dock,
    which is the case that was broken.
    """

    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        from sbs_utils.gui import GuiClient
        GuiClient(CID)
        offer_clear()
        set_shared_variable("HANGAR_QUEST_DOC", DOC)
        HB.hangar_offers_register()
        from sbs_utils.procedural.a2x.spawn import create_enemy
        from sbs_utils.procedural.query import to_id
        from sbs_utils.procedural.inventory import set_inventory_value
        self.craft = to_id(create_enemy(0, 0, 0, "kralien_cruiser", name="F1"))
        self.dock = to_id(create_enemy(500, 0, 0, "kralien_cruiser", name="Carrier"))
        set_inventory_value(CID, HB.HANGAR_RIDE_KEY, self.craft)

    def tearDown(self):
        offer_clear()
        set_shared_variable("HANGAR_QUEST_DOC", None)

    def _sortie(self, key="patrol"):
        """A SPECIFIC order. `offers()` sorts by title, so rows[0] is whichever sorts
        first rather than the one an assertion names."""
        for r in offers(client_id=CID):
            if r.get("kind") == "sortie" and (r.get("data") or {}).get("sortie") == key:
                return r
        return None

    def _tab_rows(self, ship_id):
        from sbs_utils.procedural.gui import gui_list_box_is_header
        from sbs_utils.procedural.quest_driver import quest_tab_items
        return [(i.get("group"), i.get("title"))
                for i in quest_tab_items(CID, ship_id)
                if not gui_list_box_is_header(i)]

    def test_a_taken_sortie_SHOWS_UP_on_the_flight_deck(self):
        """THE BUG, and the whole point of the feature. The console's ship here is the
        DOCK - the craft has not launched - which is exactly where it used to vanish."""
        HB.hangar_take_sortie(CID, self._sortie())
        rows = self._tab_rows(self.dock)
        self.assertIn(("You", "Picket Patrol"), rows,
                      "the order is held by nobody the Quests tab reads: %s" % rows)

    def test_it_is_held_by_the_client_not_the_craft(self):
        from sbs_utils.procedural.quest import quest_get_state
        HB.hangar_take_sortie(CID, self._sortie())
        self.assertEqual(int(quest_get_state(CID, "patrol")), 1)
        self.assertEqual(int(quest_get_state(self.craft, "patrol")), 0)

    def test_it_follows_the_pilot_into_the_cockpit(self):
        """Held by the client, so it is still there once they are flying the craft."""
        HB.hangar_take_sortie(CID, self._sortie())
        self.assertIn(("You", "Picket Patrol"), self._tab_rows(self.craft))

    def test_a_taken_sortie_leaves_the_board(self):
        HB.hangar_take_sortie(CID, self._sortie("patrol"))
        self.assertIsNone(self._sortie("patrol"))
        self.assertIsNotNone(self._sortie("any_job"),
                             "taking one order removed the rest")

    def test_taking_moves_the_generation_so_the_board_repaints(self):
        """The row used to stay on screen, which reads as the press not having worked."""
        from sbs_utils.procedural.offer import offer_generation
        before = offer_generation()
        HB.hangar_take_sortie(CID, self._sortie())
        self.assertNotEqual(before, offer_generation())

    def test_changing_craft_does_not_re_offer_a_taken_order(self):
        """The key is the CLIENT's, like the ownership - keyed on the craft, a pilot who
        swapped fighters was offered the same order again under a second key."""
        from sbs_utils.procedural.inventory import set_inventory_value
        HB.hangar_take_sortie(CID, self._sortie())
        set_inventory_value(CID, HB.HANGAR_RIDE_KEY, self.dock)
        self.assertIsNone(self._sortie("patrol"))

    def test_taking_nonsense_is_false_not_a_crash(self):
        self.assertFalse(HB.hangar_take_sortie(CID, None))
        self.assertFalse(HB.hangar_take_sortie(CID, {"data": {}}))

    def test_no_client_takes_nothing(self):
        self.assertFalse(HB.hangar_take_sortie(None, self._sortie()))


if __name__ == "__main__":
    unittest.main()
