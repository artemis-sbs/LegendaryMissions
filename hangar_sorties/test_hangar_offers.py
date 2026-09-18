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
            self.assertEqual(r.get("app"), "quest")
            self.assertTrue(str(r.get("key")).startswith("sortie:"))

    def test_the_key_names_the_craft_AND_the_order(self):
        """Two pilots are offered the same order; their offers must not collide."""
        self._craft = 5
        a = {r.get("key") for r in HB.hangar_offer_provider(_ctx())}
        self._craft = 6
        b = {r.get("key") for r in HB.hangar_offer_provider(_ctx())}
        self.assertFalse(a & b, "two craft produced the same offer key")

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


if __name__ == "__main__":
    unittest.main()
