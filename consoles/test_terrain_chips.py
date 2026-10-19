"""The radar chips on Helm and Weapons: the terrain switches and the contact lenses, that
both belong to the ship, and that each console family has its own.

    PYTHONPATH=../../sbs_utils python -m unittest test_terrain_chips
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
from sbs_utils.procedural.sides import side_ensure, side_set_relations
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.spaceobject import SpaceObject

import terrain_chips as T

CID = 0x8000000000000001
CID2 = 0x8000000000000002


class _Box:
    """The listbox surface the chip code touches."""

    def __init__(self, selected):
        self.selected = list(selected)
        self.dirty = 0

    def get_selected(self):
        return list(self.selected)

    def mark_visual_dirty(self):
        self.dirty += 1


class RadarChipsTest(unittest.TestCase):
    def setUp(self):
        sbs.create_new_sim()
        DeleteQueue.clear()
        clear_shared()
        SpaceObject.clear()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent(CID))
        side_ensure("tsn")
        side_ensure("raider")
        side_set_relations("tsn", "raider", sbs.DIPLOMACY.HOSTILE)
        GuiClient(CID)
        GuiClient(CID2)
        self.ship = to_id(player_spawn(0, 0, 0, "Hero", "tsn", "tsn_light_cruiser"))
        sbs.assign_client_to_ship(CID, self.ship)
        sbs.assign_client_to_ship(CID2, self.ship)
        self.foe = to_id(npc_spawn(1000, 0, 0, "K19", "raider", "tsn_light_cruiser",
                                   "behav_npcship"))
        self.ally = to_id(npc_spawn(2000, 0, 0, "Valiant", "tsn", "tsn_light_cruiser",
                                    "behav_npcship"))
        science_set_scan_data(self.ship, self.foe, {"scan": "A kralien cruiser."})
        science_set_scan_data(self.ship, self.ally, {"scan": "A TSN cruiser."})
        self.ds = sbs.sim.get_space_object(self.ship).data_set

    def tearDown(self):
        FrameContext.context = None

    def flags(self, console):
        return (self.ds.get(f"{console}_show_nebulas", 0),
                self.ds.get(f"{console}_show_asteroids", 0))

    def written(self, console):
        key = f"{console}_map_filter"
        return [self.ds.get(key, i) for i in range(self.ds.num_elements(key))]

    # --- the switches ---------------------------------------------------------

    def test_terrain_is_lit_and_no_lens_is_until_someone_taps(self):
        """The engine draws terrain by default (measured on 1.3.15) and filters nothing."""
        self.assertEqual(T.lm_terrain_chips_selected(CID, "helm"),
                         ["all", "nebulas", "asteroids"])
        self.assertEqual(T.lm_terrain_chips_selected(CID, "weapon"),
                         ["all", "nebulas", "asteroids"])

    def test_a_tap_writes_both_engine_flags(self):
        T.lm_terrain_chips_apply(CID, "helm", _Box(["asteroids"]))
        self.assertEqual(self.flags("helm"), (0, 1))
        T.lm_terrain_chips_apply(CID, "helm", _Box([]))
        self.assertEqual(self.flags("helm"), (0, 0))
        T.lm_terrain_chips_apply(CID, "helm", _Box(["nebulas", "asteroids"]))
        self.assertEqual(self.flags("helm"), (1, 1))

    # --- the lenses -----------------------------------------------------------

    def test_a_lens_writes_that_consoles_map_filter(self):
        T.lm_terrain_chips_apply(CID, "helm", _Box(["threats", "nebulas", "asteroids"]))
        self.assertEqual(self.written("helm"), sorted([self.ship, self.foe]))
        self.assertEqual(self.flags("helm"), (1, 1))

    def test_two_lenses_are_the_union(self):
        T.lm_terrain_chips_apply(CID, "weapon", _Box(["threats", "friends"]))
        self.assertEqual(self.written("weapon"), sorted([self.ship, self.foe, self.ally]))

    def test_all_is_exclusive_with_the_lenses(self):
        # A lens tapped while All is lit puts All out.
        box = _Box(["all", "threats", "nebulas"])
        T.lm_terrain_chips_apply(CID, "helm", box)
        self.assertEqual(box.get_selected(), ["threats", "nebulas"])
        # All tapped while a lens is lit clears the lens, and the filter with it.
        box = _Box(["all", "threats", "nebulas"])
        T.lm_terrain_chips_apply(CID, "helm", box)
        self.assertEqual(box.get_selected(), ["all", "nebulas"])
        self.assertEqual(self.written("helm"), [])
        # Putting the last lens out brings All back rather than leaving nothing lit.
        T.lm_terrain_chips_apply(CID, "helm", _Box(["friends"]))
        box = _Box(["asteroids"])
        T.lm_terrain_chips_apply(CID, "helm", box)
        self.assertEqual(box.get_selected(), ["all", "asteroids"])
        # The switches never knock All or a lens out.
        self.assertEqual(self.flags("helm"), (0, 1))

    def test_no_lens_lit_clears_the_filter(self):
        T.lm_terrain_chips_apply(CID, "helm", _Box(["threats"]))
        T.lm_terrain_chips_apply(CID, "helm", _Box(["nebulas"]))
        self.assertEqual(self.written("helm"), [])

    def test_a_lens_never_lists_an_unscanned_contact(self):
        stranger = to_id(npc_spawn(3000, 0, 0, "U1", "raider", "tsn_light_cruiser",
                                   "behav_npcship"))
        T.lm_terrain_chips_apply(CID, "helm", _Box(["threats"]))
        self.assertNotIn(stranger, self.written("helm"))

    def test_a_lit_lens_keeps_up_with_its_contacts(self):
        T.lm_terrain_chips_apply(CID, "helm", _Box(["threats"]))
        before = T.lm_terrain_chips_revision(CID, "helm")
        late = to_id(npc_spawn(3000, 0, 0, "K20", "raider", "tsn_light_cruiser",
                               "behav_npcship"))
        science_set_scan_data(self.ship, late, {"scan": "Another."})
        self.assertNotEqual(T.lm_terrain_chips_revision(CID, "helm"), before)
        T.lm_terrain_chips_write(CID, "helm")
        self.assertIn(late, self.written("helm"))

    def test_nothing_to_watch_while_no_lens_is_lit(self):
        before = T.lm_terrain_chips_revision(CID, "helm")
        npc_spawn(3000, 0, 0, "K20", "raider", "tsn_light_cruiser", "behav_npcship")
        self.assertEqual(T.lm_terrain_chips_revision(CID, "helm"), before)

    # --- whose they are ---------------------------------------------------------

    def test_helm_and_weapons_do_not_share_a_row(self):
        T.lm_terrain_chips_apply(CID, "helm", _Box(["threats"]))
        self.assertEqual(self.flags("helm"), (0, 0))
        self.assertEqual(self.flags("weapon"), (1, 1))
        self.assertEqual(self.flags("sci"), (1, 1))
        self.assertEqual(self.written("weapon"), [])
        self.assertEqual(self.written("comms"), [])
        self.assertEqual(T.lm_terrain_chips_selected(CID, "weapon"),
                         ["all", "nebulas", "asteroids"])

    # --- the two groups, side by side --------------------------------------------

    def test_the_groups_split_the_row(self):
        self.assertEqual(T.lm_terrain_chips_items("lens"), ["all", "threats", "friends", "bases"])
        self.assertEqual(T.lm_terrain_chips_items("terrain"), ["nebulas", "asteroids"])
        self.assertEqual(dict(T.LM_TERRAIN_CHIPS)["asteroids"], "Asteroids")

    def test_the_groups_fit_between_the_info_panel_and_helms_camera_dial(self):
        """1024 - 300 (info panel) - 334 (dial) = 390px; the engine measured "Asteroids"
        at 65.5px and "Threats" at 52.4px in gui-1, so each needs its pitch."""
        self.assertGreater(T.LM_TERRAIN_CHIP_WIDTH["terrain"], 66)
        self.assertGreater(T.LM_TERRAIN_CHIP_WIDTH["lens"], 53)
        total = T.lm_terrain_chips_group_px("lens") + T.lm_terrain_chips_group_px("terrain")
        self.assertLessEqual(total, 390)

    def test_a_lens_tap_leaves_the_terrain_alone(self):
        T.lm_terrain_chips_apply(CID, "helm", _Box(["nebulas"]), "terrain")
        box = _Box(["all", "friends"])
        T.lm_terrain_chips_apply(CID, "helm", box, "lens")
        self.assertEqual(box.get_selected(), ["friends"])
        self.assertEqual(self.flags("helm"), (1, 0))
        self.assertEqual(self.written("helm"), sorted([self.ship, self.ally]))

    def test_terrain_is_never_put_in_the_filter(self):
        """The filter is for contacts; the switches alone decide terrain. Listing terrain
        to dodge the engine hiding it under a filter is exactly what this must not do."""
        from sbs_utils.procedural.spawn import terrain_spawn
        rock = to_id(terrain_spawn(500, 0, 500, None, "#, asteroid", "plain_asteroid_9",
                                   "behav_asteroid"))
        neb = to_id(terrain_spawn(800, 0, 800, None, "#, nebula", "nebula", "behav_nebula"))
        for lens in (["threats"], ["friends"], ["bases"], ["threats", "friends", "bases"]):
            with self.subTest(lens=lens):
                T.lm_terrain_chips_apply(CID, "helm", _Box(lens), "lens")
                self.assertNotIn(rock, self.written("helm"))
                self.assertNotIn(neb, self.written("helm"))
        self.assertEqual(self.flags("helm"), (1, 1))

    def test_a_terrain_tap_leaves_the_filter_alone(self):
        T.lm_terrain_chips_apply(CID, "helm", _Box(["threats"]), "lens")
        T.lm_terrain_chips_apply(CID, "helm", _Box([]), "terrain")
        self.assertEqual(self.flags("helm"), (0, 0))
        self.assertEqual(self.written("helm"), sorted([self.ship, self.foe]))
        self.assertEqual(T.lm_terrain_chips_selected(CID, "helm", "lens"), ["threats"])
        self.assertEqual(T.lm_terrain_chips_selected(CID, "helm", "terrain"), [])

    def test_each_group_follows_the_ship(self):
        T.lm_terrain_chips_apply(CID, "weapon", _Box(["bases"]), "lens")
        lens, switch = _Box(["all"]), _Box(["nebulas", "asteroids"])
        T.lm_terrain_chips_follow(CID2, "weapon", lens, "lens")
        T.lm_terrain_chips_follow(CID2, "weapon", switch, "terrain")
        self.assertEqual(lens.get_selected(), ["bases"])
        self.assertEqual(switch.dirty, 0)

    # --- wider on a wider screen --------------------------------------------------

    def _screen(self, w, h, known=True):
        from sbs_utils.vec import Vec3
        FrameContext.aspect_ratios[CID] = Vec3(w, h, 0 if known else 99)
        self.addCleanup(FrameContext.aspect_ratios.pop, CID, None)

    def test_an_unreported_screen_gets_the_floor(self):
        self.assertEqual(T.lm_terrain_chips_scale(CID, "helm"), 1.0)
        self.assertEqual(T.lm_terrain_chips_style("terrain", CID, "helm").split(";")[0],
                         "col-width:72px")

    def test_a_1024_screen_gets_the_floor(self):
        self._screen(1024, 768)
        # 390px of room against 384px of chips: the floor, give or take a pixel a chip.
        self.assertLess(T.lm_terrain_chips_scale(CID, "helm"), 1.05)
        self.assertEqual(T.lm_terrain_chips_font(CID), "gui-1")

    def test_a_wide_screen_grows_the_chips_up_to_the_cap(self):
        self._screen(1920, 1080)
        self.assertEqual(T.lm_terrain_chips_scale(CID, "helm"), T.LM_TERRAIN_SCALE_MAX)
        self.assertEqual(T.lm_terrain_chips_style("terrain", CID, "helm").split(";")[0],
                         "col-width:115px")
        self.assertEqual(T.lm_terrain_chips_font(CID), "gui-2")

    def test_the_chips_never_outgrow_the_room(self):
        """Whatever the width, both groups fit between the info panel and the dial."""
        for w in (1024, 1100, 1180, 1280, 1600, 1920, 2560):
            self._screen(w, 1080)
            for console in ("helm", "weapon"):
                total = (T.lm_terrain_chips_group_px("lens", CID, console)
                         + T.lm_terrain_chips_group_px("terrain", CID, console))
                room = w - T.LM_TERRAIN_LEFT_PX - T.LM_TERRAIN_RIGHT_PX[console]
                with self.subTest(width=w, console=console):
                    self.assertLessEqual(total, room)

    def test_the_bigger_font_waits_for_room_for_it(self):
        """gui-2 "Asteroids" is 71.5px: not before the terrain pitch is past it."""
        self._screen(1100, 768)
        self.assertEqual(T.lm_terrain_chips_font(CID), "gui-1")

    def test_a_second_console_on_the_ship_follows(self):
        T.lm_terrain_chips_apply(CID, "weapon", _Box(["friends", "nebulas"]))
        other = _Box(["all", "nebulas", "asteroids"])
        T.lm_terrain_chips_follow(CID2, "weapon", other)
        self.assertEqual(other.get_selected(), ["friends", "nebulas"])
        self.assertEqual(other.dirty, 1)
        # ...and is left alone once it agrees.
        T.lm_terrain_chips_follow(CID2, "weapon", other)
        self.assertEqual(other.dirty, 1)


if __name__ == "__main__":
    unittest.main()
