"""A race the operator has turned off cannot be PICKED for a fleet (GWQ-12).

The playtest report was "Skaraan show up even when they aren't NPC races". The pick ran
through `_fleet_can_raid`, which asked only "does this race have a fleet ladder
registered" - and a THEATER roster is not the NPC_RACES setting. The stock `legendary`
theater rosters skaraan, so the single thing keeping skaraan out of a TNG game was that
its ladder happens to be registered behind the same setting, in another addon's
top-level code, under a load order that is not deterministic.

These tests hold the rule where it belongs: ask the setting.
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
# `map_common` does `from fleet import fleet_spawn` - a mastlib's files sit FLAT beside
# each other, so the addon folder itself has to be importable, not just its parent.
sys.path.insert(0, _HERE)

from sbs_utils.fs import test_set_exe_dir  # noqa: E402

test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401,E402  (first, to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs  # noqa: F401,E402  (installs itself as sys.modules['sbs'])
from sbs_utils.procedural import fleet_tables  # noqa: E402
from sbs_utils.procedural.settings import settings_get_defaults  # noqa: E402

import fleets.map_common as map_common  # noqa: E402


_LADDER = [[["skaraan_defiler"]]]


class FleetRaceGateTest(unittest.TestCase):
    def setUp(self):
        self._tables = dict(fleet_tables._TABLES)
        self._warned = set(fleet_tables._NO_TABLE_WARNED)
        self.settings = settings_get_defaults()
        self._npc = self.settings.get("NPC_RACES")
        # Both races have a ladder, so the ladder gate can never be what decides.
        fleet_tables.fleet_table_register("skaraan", _LADDER, "test")
        fleet_tables.fleet_table_register("kralien", _LADDER, "test")

    def tearDown(self):
        fleet_tables._TABLES.clear()
        fleet_tables._TABLES.update(self._tables)
        fleet_tables._NO_TABLE_WARNED.clear()
        fleet_tables._NO_TABLE_WARNED.update(self._warned)
        if self._npc is None:
            self.settings.pop("NPC_RACES", None)
        else:
            self.settings["NPC_RACES"] = self._npc

    def test_a_race_off_the_npc_list_cannot_raid(self):
        self.settings["NPC_RACES"] = "Kralien, Torgoth"
        can_raid = map_common._fleet_can_raid()
        self.assertFalse(can_raid("skaraan"),
                         "skaraan was pickable with a registered ladder but NPC_RACES off")
        self.assertTrue(can_raid("kralien"))

    def test_the_ladder_being_registered_is_not_enough(self):
        """The exact GWQ-12 shape: ladder present, setting says no."""
        self.settings["NPC_RACES"] = "Klingon, Romulan, Cardassian, Kazon, Orion, Dominion"
        self.assertTrue(fleet_tables.fleet_table_has("skaraan"))
        self.assertFalse(map_common._fleet_can_raid()("skaraan"))

    def test_case_and_spacing_do_not_matter(self):
        self.settings["NPC_RACES"] = "  kralien ,  SKARAAN  "
        can_raid = map_common._fleet_can_raid()
        self.assertTrue(can_raid("Skaraan"))
        self.assertTrue(can_raid("KRALIEN"))

    def test_an_empty_setting_means_no_restriction(self):
        """The setting's own contract. Getting this backwards would empty every mission
        that has never named a race - a far worse bug than the one being fixed."""
        self.settings["NPC_RACES"] = ""
        self.assertTrue(map_common._fleet_can_raid()("skaraan"))

    def test_the_caller_s_own_eligible_still_applies(self):
        self.settings["NPC_RACES"] = "Kralien, Skaraan"
        can_raid = map_common._fleet_can_raid(lambda r: r != "skaraan")
        self.assertFalse(can_raid("skaraan"))
        self.assertTrue(can_raid("kralien"))

    def test_a_race_with_no_ladder_still_cannot_raid(self):
        """The original half of the gate must survive the new one."""
        self.settings["NPC_RACES"] = "Kralien, Breen"
        self.assertFalse(map_common._fleet_can_raid()("breen"))


if __name__ == "__main__":
    unittest.main()
