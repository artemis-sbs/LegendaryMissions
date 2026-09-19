"""Station kinds: the composition, which hull a kind spawns, and its fighter loadout.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest station_kinds.test_station_kinds
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs
from sbs_utils.agent import clear_shared
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural import ship_data as SD
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.roles import has_role
from sbs_utils.procedural.sides import side_ensure

from station_kinds import station_kinds as K   # the module, not the addon folder
from hangar import hangar_wing as W

MEDIA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")


class KindBase(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        DeleteQueue.clear()
        clear_shared()
        SpaceObject.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent())
        side_ensure("tsn")
        side_ensure("raider")
        SD.extra_reset()
        SD.extra_ship_data_force(None)

    def tearDown(self):
        SD.extra_ship_data_force(None)
        SD.extra_reset()
        FrameContext.context = None

    def scaled_on(self):
        """EXTRA_SHIP_DATA on and the kind hulls handed to the engine (the mock takes them)."""
        SD.extra_ship_data_force(True)
        real = SD._find_extra_root
        SD._find_extra_root = lambda folder, name: os.path.join(MEDIA, folder)
        try:
            self.assertTrue(K.station_kinds_declare_ships())
        finally:
            SD._find_extra_root = real


class TestComposition(KindBase):

    def counts(self, n):
        kinds = K.station_kind_composition(n, random.Random(7))
        return {k: kinds.count(k) for k in K.station_kind_list()}, kinds

    def test_THREE_BASES(self):
        c, kinds = self.counts(3)
        self.assertEqual({"command": 1, "industrial": 1, "science": 1, "civil": 0}, c)
        self.assertEqual(14, K.station_kind_fighters(kinds))

    def test_ELEVEN_BASES_FIELD_FAR_FEWER_FIGHTERS(self):
        c, kinds = self.counts(11)
        self.assertEqual({"command": 3, "industrial": 3, "science": 3, "civil": 2}, c)
        self.assertEqual(42, K.station_kind_fighters(kinds))       # was up to 11 x 14

    def test_always_the_asked_count(self):
        for n in range(0, 16):
            self.assertEqual(n, len(K.station_kind_composition(n, random.Random(n))))

    def test_at_least_one_command(self):
        for n in range(1, 16):
            self.assertIn("command", K.station_kind_composition(n, random.Random(n)))


class TestHull(KindBase):

    def test_EXTRA_OFF_EVERY_KIND_IS_THE_RACE_STARBASE(self):
        for kind in K.station_kind_list():
            self.assertEqual("starbase_kralien", K.station_kind_hull("kralien", kind), kind)

    def test_EXTRA_ON_A_KIND_IS_ITS_SCALED_HULL(self):
        self.scaled_on()
        self.assertTrue(K.station_kind_scaled_live())
        self.assertEqual("starbase_kralien", K.station_kind_hull("kralien", "command"))
        self.assertEqual("starbase_kralien_industrial", K.station_kind_hull("kralien", "industrial"))
        self.assertEqual("starbase_arvonian_civil", K.station_kind_hull("arvonian", "civil"))

    def test_terran_kinds_are_the_real_hulls(self):
        self.assertEqual("starbase_science", K.station_kind_hull("terran", "science"))
        self.assertEqual("starbase_civil", K.station_kind_hull("terran", "civil"))

    def test_A_RESKIN_WINS_UNSCALED(self):
        self.scaled_on()
        real = SD.art_key_for
        SD.art_key_for = lambda key: "starbase_command" if key == "starbase_kralien" else key
        try:
            self.assertEqual("starbase_command", K.station_kind_hull("kralien", "science"))
        finally:
            SD.art_key_for = real

    def test_a_race_with_no_starbase(self):
        self.assertIsNone(K.station_kind_hull("ximni", "command"))

    def test_THE_SCALED_HULLS_ARE_SMALLER_AND_NOT_STATIONS(self):
        self.scaled_on()
        base = SD.get_ship_data_for("starbase_kralien")
        sci = SD.get_ship_data_for("starbase_kralien_science")
        self.assertLess(sci["meshscale"], base["meshscale"])
        self.assertLess(sci["hullpoints"], base["hullpoints"])
        self.assertLess(sci["shields"][0], base["shields"][0])
        # Never "station" in the ship data - race_station_hulls must not pick them up.
        from sbs_utils.procedural.races import race_station_hull
        self.assertEqual("starbase_kralien", race_station_hull("kralien"))


class TestSpawn(KindBase):

    def spawn(self, race, kind):
        return K.station_kind_spawn(0, 0, 0, race, kind, "Base", "raider, enemy, station")

    def wings(self, sid):
        return [W.hangar_wing_size(sid, w) for w in W.hangar_wing_names(sid)]

    def test_EACH_KIND_GETS_ITS_OWN_WINGS(self):
        self.assertEqual([4, 4], self.wings(self.spawn("arvonian", "command")))   # not 14 bays
        self.assertEqual([4], self.wings(self.spawn("kralien", "industrial")))
        self.assertEqual([2], self.wings(self.spawn("kralien", "science")))
        self.assertEqual([], self.wings(self.spawn("kralien", "civil")))

    def test_the_kind_is_a_role(self):
        sid = self.spawn("kralien", "science")
        self.assertTrue(has_role(sid, "station_science"))
        self.assertTrue(has_role(sid, "station"))

    def test_spawns_the_scaled_hull_when_live(self):
        self.scaled_on()
        sid = self.spawn("torgoth", "industrial")
        self.assertEqual("starbase_torgoth_industrial", to_object(sid).art_id)


class TestGeneratedFile(unittest.TestCase):
    """The media file the engine reads - the rules it has and PyYAML does not."""

    def test_THE_ENGINE_CAN_READ_IT(self):
        from sbs_utils.fs import load_yaml_string
        path = os.path.join(MEDIA, "stations", "extraShipData_station_kinds.yaml")
        text = open(path, encoding="utf-8").read()
        self.assertTrue(text.endswith("\n"))
        self.assertTrue(SD._looks_like_hjson(text))
        entries = load_yaml_string(text)["#ship-list"]
        self.assertEqual(12, len(entries))
        for e in entries:
            for field in ("hull_port_sets", "shields", "hullpoints", "artfileroot", "torpedostart"):
                self.assertIn(field, e, e.get("key"))
            self.assertNotIn("station", e["roles"])


if __name__ == "__main__":
    unittest.main()
