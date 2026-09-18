"""Spawning hangar craft for a ship that is not there fails QUIETLY.

`hangar_craft_spawn` read `so.origin` with no check, so a docked id that was not a
live ship raised `'NoneType' object has no attribute 'origin'` - reported against the
CALLER's MAST line, which reads as correct (seen in a2x cruiser_tournament). And
`hangar_random_craft_spawn` fed `random.choice` an empty list for a ship that carries
no craft of the asked type. Both now log a warning and return None.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest hangar.test_hangar_craft_spawn
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs
from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.procedural.space_objects import delete_object

# `hangar` alone is the ADDON FOLDER (a namespace package); the module is inside it.
from hangar import hangar as H


class TestCraftSpawnForAMissingShip(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        SpaceObject.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent())

    def tearDown(self):
        FrameContext.context = None

    def test_NONE_IS_NOT_A_CRASH(self):
        with mock.patch.object(H, "log") as log:
            self.assertIsNone(H.hangar_craft_spawn(None, {"key": "tsn_shuttle", "type": "shuttle"}))
        self.assertTrue(log.called)
        self.assertIn("not a live ship", log.call_args[0][0])

    def test_a_deleted_ship_is_not_a_crash(self):
        ship = to_id(player_spawn(0, 0, 0, "Gone", "tsn", "tsn_light_cruiser"))
        delete_object(ship)
        with mock.patch.object(H, "log"):
            self.assertIsNone(H.hangar_random_craft_spawn(ship, "shuttle"))

    def test_NO_CRAFT_OF_THAT_TYPE_IS_NOT_A_CRASH(self):
        ship = to_id(player_spawn(0, 0, 0, "Hero", "tsn", "tsn_light_cruiser"))
        with mock.patch.object(H, "hangar_get_ship_data_keys",
                               return_value=[{"key": "tsn_fighter", "type": "fighter"}]), \
                mock.patch.object(H, "log") as log:
            self.assertIsNone(H.hangar_random_craft_spawn(ship, "shuttle"))
        self.assertIn("carries no shuttle", log.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
