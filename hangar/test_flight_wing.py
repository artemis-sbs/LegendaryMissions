"""The Flight Wing: one quest holder per side, shared by the flight deck and the cockpit.

A pilot's console is assigned to the CARRIER while on the flight deck, so the quest
screens listed the carrier's patrol quests. The hangar names the side's Flight Wing as
the console's holder instead.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest hangar.test_flight_wing
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs
from sbs_utils.agent import Agent, clear_shared
from sbs_utils.gui import GuiClient
from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.procedural.sides import side_ensure
from sbs_utils.procedural.quest import quest_add
from sbs_utils.procedural import quest_driver as QD

# `hangar` alone is the ADDON FOLDER (a namespace package); the module is inside it.
from hangar import hangar as H

PILOT_A = 0x8080000000000001
PILOT_B = 0x8080000000000002


class FlightWingTests(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        clear_shared()
        SpaceObject.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent())
        GuiClient(PILOT_A)
        GuiClient(PILOT_B)
        side_ensure("tsn")
        side_ensure("kralien")
        self.carrier = to_id(player_spawn(0, 0, 0, "Carrier", "tsn", "tsn_light_cruiser"))
        quest_add(self.carrier, "patrol", "Carrier Patrol", "")

    def tearDown(self):
        QD.quest_holder_clear(PILOT_A)
        QD.quest_holder_clear(PILOT_B)
        FrameContext.context = None

    def _available(self, cid):
        return [r.get("title") for r in QD.quest_offers_tab_items(cid, self.carrier, "hangar")
                if QD._quest_offer_row(r) is not None]

    def test_one_wing_per_side_shared_by_its_pilots(self):
        a = H.hangar_use_flight_wing(PILOT_A, "tsn")
        b = H.hangar_use_flight_wing(PILOT_B, self.carrier)    # an object on the side works too
        self.assertIsNotNone(a)
        self.assertEqual(a, b)
        self.assertNotEqual(a, H.hangar_flight_wing("kralien"))
        self.assertTrue(Agent.get(a).has_role("__flight_wing__"))

    def test_the_flight_deck_does_not_list_the_carriers_quests(self):
        self.assertEqual(self._available(PILOT_A), ["Carrier Patrol"])   # the bug, before
        H.hangar_use_flight_wing(PILOT_A, "tsn")
        self.assertEqual(self._available(PILOT_A), [])

    def test_a_wing_quest_reaches_every_pilot_of_the_side(self):
        wing = H.hangar_flight_wing("tsn")
        quest_add(wing, "cover", "Cover the Convoy", "")
        H.hangar_use_flight_wing(PILOT_A, "tsn")
        H.hangar_use_flight_wing(PILOT_B, "tsn")
        self.assertEqual(self._available(PILOT_A), ["Cover the Convoy"])
        self.assertEqual(self._available(PILOT_B), ["Cover the Convoy"])

    def test_no_side_means_the_ship_is_used(self):
        H.hangar_use_flight_wing(PILOT_A, "tsn")
        self.assertIsNone(H.hangar_use_flight_wing(PILOT_A, "no_such_side"))
        self.assertEqual(self._available(PILOT_A), ["Carrier Patrol"])


if __name__ == "__main__":
    unittest.main()
