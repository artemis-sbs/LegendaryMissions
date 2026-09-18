"""The comms filter chips: what each lens holds, and how taps combine.

The engine hook (`set_comms_list_filter`) does not exist yet, so what can be pinned
today is the SCRIPT half: the id set behind every chip, the side chips, the All/lens
rules, and that the result is handed to the hook the moment the engine has one.

    PYTHONPATH=../../sbs_utils python -m unittest test_comms_chips
"""
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes            # noqa: F401  breaks a circular import
from cosmos_dev.mock import sbs
from sbs_utils.agent import clear_shared
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.gui import GuiClient
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.science import science_set_scan_data
from sbs_utils.procedural.sides import side_ensure
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.spaceobject import SpaceObject

import comms_chips as C

CID = 0x8000000000000001


class _FakeListbox:
    """Just the selection surface lm_comms_chips_normalize touches."""

    def __init__(self, selected):
        self.selected = list(selected)
        self.dirty = 0

    def get_selected(self):
        return list(self.selected)

    def mark_visual_dirty(self):
        self.dirty += 1


class ChipsBase(unittest.TestCase):
    def setUp(self):
        sbs.create_new_sim()
        DeleteQueue.clear()
        clear_shared()
        SpaceObject.clear()
        C.lm_comms_chips_clear()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent(CID))
        side_ensure("tsn")
        side_ensure("kralien")
        from sbs_utils.procedural.sides import side_set_relations
        side_set_relations("tsn", "kralien", sbs.DIPLOMACY.HOSTILE)
        GuiClient(CID)
        self.ship = to_id(player_spawn(0, 0, 0, "Hero", "tsn", "tsn_light_cruiser"))
        sbs.assign_client_to_ship(CID, self.ship)
        self.ally = to_id(npc_spawn(1000, 0, 0, "Valiant", "tsn", "tsn_light_cruiser", "behav_npcship"))
        self.base = to_id(npc_spawn(2000, 0, 0, "DS 1", "tsn,station", "starbase_command", "behav_station"))
        self.foe = to_id(npc_spawn(3000, 0, 0, "Raider", "kralien", "tsn_light_cruiser", "behav_npcship"))
        self.ghost = to_id(npc_spawn(4000, 0, 0, "Contact", "kralien", "tsn_light_cruiser", "behav_npcship"))
        for who in (self.ally, self.base, self.foe):
            science_set_scan_data(self.ship, who, "identified")

    def tearDown(self):
        FrameContext.context = None
        if hasattr(sbs, "set_comms_list_filter"):
            del sbs.set_comms_list_filter

    def sets(self):
        return C.lm_comms_chips_sets(CID, force=True)


class TestTheLenses(ChipsBase):

    def test_all_is_every_contact_but_your_own_ship(self):
        self.assertEqual({self.ally, self.base, self.foe, self.ghost}, self.sets()["all"])

    def test_threats_and_friends_come_from_the_sides(self):
        s = self.sets()
        self.assertEqual({self.foe, self.ghost}, s["threats"])
        self.assertEqual({self.ally, self.base}, s["friends"])

    def test_stations_by_role(self):
        self.assertEqual({self.base}, self.sets()["stations"])

    def test_EACH_SIDE_IN_VIEW_GETS_A_CHIP(self):
        s = self.sets()
        self.assertEqual({self.ally, self.base}, s["side:tsn"])
        self.assertEqual({self.foe, self.ghost}, s["side:kralien"])

    def test_side_chips_follow_the_fixed_ones(self):
        items = C.lm_comms_chips_items(CID)
        self.assertEqual(["all", "threats", "friends", "stations", "jobs", "orders"], items[:6])
        self.assertEqual({"side:tsn", "side:kralien"}, set(items[6:]))

    def test_a_side_with_nothing_in_view_has_no_chip(self):
        side_ensure("arvonian")
        self.assertNotIn("side:arvonian", C.lm_comms_chips_items(CID))

    def test_no_chip_for_hailing_or_unknown(self):
        items = C.lm_comms_chips_items(CID)
        self.assertNotIn("hailing", items)
        self.assertNotIn("unknown", items)

    def test_a_deleted_contact_is_in_no_lens(self):
        from sbs_utils.procedural.space_objects import delete_object
        delete_object(self.foe)
        for key, ids in self.sets().items():
            self.assertNotIn(self.foe, ids, key)

    def test_counts_are_cached_between_recounts(self):
        """Offers run providers per contact, so a chip count is allowed to be a couple
        of seconds old rather than recomputed on every tick of every console."""
        first = C.lm_comms_chips_sets(CID)
        self.assertIs(first, C.lm_comms_chips_sets(CID))


class TestTapping(ChipsBase):

    def tap(self, selected):
        return C.lm_comms_chips_normalize(CID, _FakeListbox(selected))

    def test_the_default_is_all(self):
        self.assertEqual(["all"], C.lm_comms_chips_selected(CID))

    def test_a_lens_replaces_all(self):
        self.assertEqual(["threats"], self.tap(["all", "threats"]))

    def test_lenses_combine(self):
        self.tap(["all", "threats"])
        self.assertEqual(["threats", "stations"], self.tap(["threats", "stations"]))

    def test_tapping_all_clears_the_lenses(self):
        self.tap(["all", "threats"])
        self.assertEqual(["all"], self.tap(["threats", "all"]))

    def test_clearing_the_last_lens_brings_all_back(self):
        self.tap(["all", "threats"])
        self.assertEqual(["all"], self.tap([]))

    def test_a_side_chip_combines_with_a_lens(self):
        self.assertEqual(["stations", "side:kralien"], self.tap(["all", "stations", "side:kralien"]))

    def test_the_listbox_is_corrected_when_it_disagrees(self):
        lb = _FakeListbox(["all", "threats"])
        C.lm_comms_chips_normalize(CID, lb)
        self.assertEqual(["threats"], lb.selected)
        self.assertEqual(1, lb.dirty)


class TestWhatWouldBeShown(ChipsBase):

    def test_all_is_no_filter(self):
        self.assertEqual(("all", None), C.lm_comms_chips_ids(CID))

    def test_a_lens_shows_its_ids(self):
        C.lm_comms_chips_normalize(CID, _FakeListbox(["all", "stations"]))
        self.assertEqual(("show", {self.base}), C.lm_comms_chips_ids(CID))

    def test_a_side_chip_shows_that_side(self):
        C.lm_comms_chips_normalize(CID, _FakeListbox(["all", "side:tsn"]))
        self.assertEqual(("show", {self.ally, self.base}), C.lm_comms_chips_ids(CID))

    def test_lenses_are_a_union(self):
        C.lm_comms_chips_normalize(CID, _FakeListbox(["all", "stations", "side:kralien"]))
        self.assertEqual(("show", {self.base, self.foe, self.ghost}), C.lm_comms_chips_ids(CID))

    def test_no_engine_hook_is_not_an_error(self):
        self.assertFalse(C.lm_comms_chips_apply(CID))

    def test_THE_ENGINE_HOOK_GETS_THE_LENS_WHEN_IT_EXISTS(self):
        calls = []
        sbs.set_comms_list_filter = lambda ship, mode, ids: calls.append((ship, mode, ids))
        C.lm_comms_chips_normalize(CID, _FakeListbox(["all", "threats"]))
        self.assertEqual((self.ship, "show", sorted([self.foe, self.ghost])), calls[-1])


if __name__ == "__main__":
    unittest.main()
