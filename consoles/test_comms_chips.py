"""The comms filter chips: what each lens holds, and how taps combine.

The id set behind every chip, the side chips, the All/lens rules, that an UNSCANNED
contact leaks into nothing (no count, no side chip, no filter), and that the selection
lands in the ship's `comms_map_filter` engine data set.

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

    def sets(self):
        return C.lm_comms_chips_sets(CID, force=True)


class TestTheLenses(ChipsBase):

    def test_all_is_every_known_contact_but_your_own_ship(self):
        self.assertEqual({self.ally, self.base, self.foe}, self.sets()["all"])

    def test_threats_and_friends_come_from_the_sides(self):
        s = self.sets()
        self.assertEqual({self.foe}, s["threats"])
        self.assertEqual({self.ally, self.base}, s["friends"])

    def test_stations_by_role(self):
        self.assertEqual({self.base}, self.sets()["stations"])

    def test_EACH_SIDE_IN_VIEW_GETS_A_CHIP(self):
        s = self.sets()
        self.assertEqual({self.ally, self.base}, s["side:tsn"])
        self.assertEqual({self.foe}, s["side:kralien"])

    def test_side_chips_follow_the_fixed_ones(self):
        items = C.lm_comms_chips_items(CID)
        self.assertEqual(["all", "threats", "friends", "stations", "jobs", "orders", "favorites"], items[:7])
        self.assertEqual({"side:tsn", "side:kralien"}, set(items[7:]))

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
        self.assertEqual(("show", {self.base, self.foe}), C.lm_comms_chips_ids(CID))


class TestTheEngineFilter(ChipsBase):
    """The selection is written to the SHIP's `comms_map_filter` data set."""

    def written(self):
        ds = sbs.sim.get_space_object(self.ship).data_set
        n = ds.num_elements("comms_map_filter")
        return [ds.get("comms_map_filter", i) for i in range(n)]

    def test_A_LENS_WRITES_ITS_IDS_AND_THE_SHIP(self):
        C.lm_comms_chips_normalize(CID, _FakeListbox(["all", "threats"]))
        self.assertEqual(sorted([self.ship, self.foe]), self.written())

    def test_all_clears_the_filter(self):
        C.lm_comms_chips_normalize(CID, _FakeListbox(["all", "threats"]))
        C.lm_comms_chips_normalize(CID, _FakeListbox(["threats", "all"]))
        self.assertEqual([], self.written())

    def test_an_empty_lens_shows_only_the_ship(self):
        """Empty means "no filter" to the engine; the ship is always listed anyway."""
        C.lm_comms_chips_normalize(CID, _FakeListbox(["all", "orders"]))
        self.assertEqual([self.ship], self.written())


class TestUnknownsLeakNothing(ChipsBase):
    """`ghost` (kralien) has not been scanned. Nothing on the chip bar may reveal it."""

    def test_AN_UNSCANNED_CONTACT_IS_IN_NO_LENS(self):
        for key, ids in self.sets().items():
            self.assertNotIn(self.ghost, ids, key)

    def test_an_unscanned_contact_is_not_in_the_filter(self):
        C.lm_comms_chips_normalize(CID, _FakeListbox(["all", "threats"]))
        mode, ids = C.lm_comms_chips_ids(CID)
        self.assertNotIn(self.ghost, ids)

    def test_A_SIDE_HAS_NO_CHIP_UNTIL_ONE_OF_ITS_SHIPS_IS_SCANNED(self):
        side_ensure("arvonian")
        spy = to_id(npc_spawn(5000, 0, 0, "Blip", "arvonian", "tsn_light_cruiser", "behav_npcship"))
        C.lm_comms_chips_sets(CID, force=True)
        self.assertNotIn("side:arvonian", C.lm_comms_chips_items(CID))
        science_set_scan_data(self.ship, spy, "identified")
        C.lm_comms_chips_sets(CID, force=True)
        self.assertIn("side:arvonian", C.lm_comms_chips_items(CID))

    def test_THE_ALL_CHIP_SHOWS_NO_COUNT(self):
        texts = []
        import sbs_utils.procedural.gui.text as T
        import sbs_utils.procedural.gui.row as R
        orig_t, orig_r = T.gui_text, R.gui_row
        T.gui_text = lambda props, *a, **k: texts.append(props)
        R.gui_row = lambda *a, **k: None
        try:
            C.lm_comms_chips_template("all")
            C.lm_comms_chips_template("threats")
        finally:
            T.gui_text, R.gui_row = orig_t, orig_r
        self.assertTrue(texts[0].startswith("$text:All;"), texts[0])
        self.assertTrue(texts[1].startswith("$text:Threats 1;"), texts[1])


class TestFavorites(ChipsBase):
    """The star toggles the console's comms selection as a favorite; the Favorites chip
    shows them. Favorites live on the SHIP, so every console on it shares them."""

    def select(self, target):
        from sbs_utils.procedural.query import set_comms_selection
        set_comms_selection(self.ship, target)

    def test_STARRING_THE_SELECTION_MAKES_IT_A_FAVORITE(self):
        self.select(self.foe)
        self.assertTrue(C.lm_comms_chips_toggle_favorite(CID))
        self.assertEqual({self.foe}, C.lm_comms_chips_sets(CID)["favorites"])

    def test_starring_again_removes_it(self):
        self.select(self.foe)
        C.lm_comms_chips_toggle_favorite(CID)
        self.assertFalse(C.lm_comms_chips_toggle_favorite(CID))
        self.assertEqual(set(), C.lm_comms_chips_sets(CID)["favorites"])

    def test_nothing_selected_stars_nothing(self):
        self.select(0)
        self.assertFalse(C.lm_comms_chips_toggle_favorite(CID))
        self.assertEqual(set(), C.lm_comms_chips_favorites(self.ship))

    def test_AN_UNSCANNED_CONTACT_IS_NOT_STARRABLE(self):
        self.select(self.ghost)                     # kralien, never scanned
        self.assertFalse(C.lm_comms_chips_toggle_favorite(CID))
        self.assertEqual(set(), C.lm_comms_chips_favorites(self.ship))
        self.assertEqual("#3A4552", C.lm_comms_chips_star_look(CID)[1])   # the dim, idle star

    def test_a_contact_becomes_starrable_once_scanned(self):
        self.select(self.ghost)
        science_set_scan_data(self.ship, self.ghost, "identified")
        self.assertTrue(C.lm_comms_chips_toggle_favorite(CID))

    def test_your_own_ship_is_not_starrable(self):
        self.select(self.ship)
        self.assertFalse(C.lm_comms_chips_toggle_favorite(CID))

    def test_the_star_shows_the_state(self):
        self.select(self.foe)
        self.assertEqual("lm.star_outline", C.lm_comms_chips_star_look(CID)[0])
        C.lm_comms_chips_toggle_favorite(CID)
        self.assertEqual(("lm.star", "#F2C14E"), C.lm_comms_chips_star_look(CID))
        self.select(0)
        self.assertEqual("lm.star_outline", C.lm_comms_chips_star_look(CID)[0])
        self.assertNotEqual("#F2C14E", C.lm_comms_chips_star_look(CID)[1])

    def test_a_deleted_favorite_is_not_in_the_chip(self):
        from sbs_utils.procedural.space_objects import delete_object
        self.select(self.foe)
        C.lm_comms_chips_toggle_favorite(CID)
        delete_object(self.foe)
        self.assertEqual(set(), C.lm_comms_chips_sets(CID, force=True)["favorites"])

    def test_the_favorites_chip_is_a_lens(self):
        self.select(self.base)
        C.lm_comms_chips_toggle_favorite(CID)
        C.lm_comms_chips_normalize(CID, _FakeListbox(["all", "favorites"]))
        self.assertEqual(("show", {self.base}), C.lm_comms_chips_ids(CID))


if __name__ == "__main__":
    unittest.main()
