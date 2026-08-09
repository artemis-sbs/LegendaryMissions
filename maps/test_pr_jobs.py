"""Peacetime job-board spawn-on-accept helpers (maps/mission_helper_functions.py).

pr_job_active drives spawn-on-accept: pr_job_dispatch spawns a job's targets the first tick this
turns True (a player has ACCEPTED the job), so targets never sit in space before the job is taken
on. pr_landmark_by_key pulls one fixed job object (the poacher / the shuttle) out of the parsed
landmarks so the mission can spawn it on accept instead of at shift start.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest maps.test_pr_jobs
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as sbs
from tests.reset_helper import reset_mock
from sbs_utils.agent import Agent
from sbs_utils.mast.mast_node import MastDataObject
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.a2x.spawn import create_enemy
from sbs_utils.procedural.quest import quest_add, QuestState

import mission_helper_functions as MH


class PrLandmarkByKeyTests(unittest.TestCase):
    def _records(self):
        return [MastDataObject({"key": "poacher_lm", "name": "Trawler"}),
                MastDataObject({"key": "mercy_lm", "name": "Shuttle"})]

    def test_finds_by_key(self):
        self.assertEqual(MH.pr_landmark_by_key(self._records(), "mercy_lm").get("name"), "Shuttle")
        self.assertEqual(MH.pr_landmark_by_key(self._records(), "poacher_lm").get("name"), "Trawler")

    def test_missing_key_is_none(self):
        self.assertIsNone(MH.pr_landmark_by_key(self._records(), "nope"))

    def test_empty_and_none_records_safe(self):
        self.assertIsNone(MH.pr_landmark_by_key([], "mercy_lm"))
        self.assertIsNone(MH.pr_landmark_by_key(None, "mercy_lm"))


class PrJobActiveTests(unittest.TestCase):
    def setUp(self):
        reset_mock(sbs)

    def _player(self):
        pid = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="P"))
        Agent.get(pid).add_role("__player__")
        return pid

    def test_no_players_no_quest_is_false(self):
        self.assertFalse(MH.pr_job_active("job_gunnery"))

    def test_idle_job_is_not_active(self):
        pid = self._player()
        quest_add(pid, "job_gunnery", "Gunnery", "", state=QuestState.IDLE,
                  data={"on_signal": {"name": "drone_down", "count": 5}})
        self.assertFalse(MH.pr_job_active("job_gunnery"))

    def test_accepted_job_is_active(self):
        # An ACCEPTED job is stored ACTIVE (the accept->ACTIVE write is covered by the quest-driver
        # anchor test); pr_job_active must detect it, and NOT report an unaccepted sibling active.
        pid = self._player()
        quest_add(pid, "job_gunnery", "Gunnery", "", state=QuestState.ACTIVE,
                  data={"on_signal": {"name": "drone_down", "count": 5}})
        self.assertTrue(MH.pr_job_active("job_gunnery"))
        self.assertFalse(MH.pr_job_active("job_rocks"))

    def test_active_on_any_player(self):
        # Two players; only the second accepts -> the job counts as active (targets spawn once).
        self._player()
        p2 = self._player()
        quest_add(p2, "job_rocks", "Rocks", "", state=QuestState.ACTIVE,
                  data={"on_signal": {"name": "rock_cleared", "count": 4}})
        self.assertTrue(MH.pr_job_active("job_rocks"))


class PrLandmarkFieldTests(unittest.TestCase):
    """`Radius:` is authored on the landmark because the size belongs to the PLACE. A
    radius kept in the mast would be a second place to edit one fact."""

    def _records(self):
        return [MastDataObject({"key": "picket_lm", "name": "Picket Line",
                                "data": {"radius": 2500}}),
                MastDataObject({"key": "mercy_lm", "name": "Shuttle", "data": {}})]

    def test_reads_the_field(self):
        self.assertEqual(MH.pr_landmark_field(self._records(), "picket_lm", "radius"), 2500)

    def test_missing_field_falls_back(self):
        self.assertEqual(MH.pr_landmark_field(self._records(), "mercy_lm", "radius", 900), 900)

    def test_missing_record_falls_back(self):
        self.assertEqual(MH.pr_landmark_field(self._records(), "nope", "radius", 900), 900)
        self.assertEqual(MH.pr_landmark_field(None, "picket_lm", "radius", 900), 900)


class PrPicketCountTests(unittest.TestCase):
    """What counts as "a gun standing on the picket".

    The job pays for guns COVERING A JUNCTION, so this is a question about position,
    side and ownership - never about which hull was used.
    """

    def setUp(self):
        reset_mock(sbs)
        self.ship = self._player()
        self.other = self._player()

    def _player(self):
        pid = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="P"))
        Agent.get(pid).add_role("__player__")
        Agent.get(pid).side = "tsn"
        return pid

    def _tower(self, x, y, z, side="tsn", owner=0):
        # npc_spawn, NOT create_enemy: create_enemy applies an a2x sector offset, so a
        # tower asked for at (0,0,1000) actually lands at (100000,0,99000) and every
        # distance assertion here would be measuring the offset instead of the zone.
        from sbs_utils.procedural.spawn import npc_spawn
        from sbs_utils.procedural.turret import turret_make
        from sbs_utils.procedural.inventory import set_inventory_value
        tid = to_id(npc_spawn(x, y, z, "T", side, "tsn_light_cruiser", "behav_station"))
        turret_make(tid)
        set_inventory_value(tid, "turret:owner", owner)
        return tid

    def test_inside_counts_outside_does_not(self):
        self._tower(0, 0, 1000)
        self.assertEqual(MH.pr_picket_count(0, 0, 0, 2500, self.ship), 1)
        self._tower(0, 0, 9000)
        self.assertEqual(MH.pr_picket_count(0, 0, 0, 2500, self.ship), 1)

    def test_a_mounted_turret_does_not_count(self):
        # A mount rides its host around; it is not an emplacement, and flying one through
        # the zone must not satisfy a picket.
        from sbs_utils.procedural.mount import mount_attach
        from sbs_utils.procedural.spawn import npc_spawn
        host = to_id(npc_spawn(0, 0, 500, "H", "tsn", "tsn_light_cruiser", "behav_npcship"))
        pod = self._tower(0, 0, 600)
        mount_attach(host, pod, (0, 0, 60))
        self.assertEqual(MH.pr_picket_count(0, 0, 0, 2500, self.ship), 0)

    def test_wrong_side_does_not_count(self):
        self._tower(0, 0, 1000, side="raider")
        self.assertEqual(MH.pr_picket_count(0, 0, 0, 2500, self.ship), 0)

    def test_unowned_counts_for_anyone(self):
        # Mission hardware belongs to nobody, and every other peacetime watcher is
        # generous with an unclaimed target.
        self._tower(0, 0, 1000, owner=0)
        self.assertEqual(MH.pr_picket_count(0, 0, 0, 2500, self.ship), 1)
        self.assertEqual(MH.pr_picket_count(0, 0, 0, 2500, self.other), 1)

    def test_another_ships_tower_is_excluded_unless_coop(self):
        self._tower(0, 0, 1000, owner=self.other)
        self.assertEqual(MH.pr_picket_count(0, 0, 0, 2500, self.ship), 0)
        self.assertEqual(MH.pr_picket_count(0, 0, 0, 2500, self.ship, coop=True), 1)
        self.assertEqual(MH.pr_picket_count(0, 0, 0, 2500, self.other), 1)

    def test_a_non_turret_object_never_counts(self):
        from sbs_utils.procedural.spawn import npc_spawn
        npc_spawn(0, 0, 1000, "Bystander", "tsn", "tsn_light_cruiser", "behav_npcship")
        self.assertEqual(MH.pr_picket_count(0, 0, 0, 2500, self.ship), 0)


class PicketAmdContractTests(unittest.TestCase):
    """Pin the AMD contract the mast depends on.

    The mast reads the goal COUNT back out of the AMD to decide how many kit crates to
    drop, and reads the zone out of a landmark. A rename or a retyped number in the .amd
    would silently give the crew the wrong number of crates, or no zone at all.
    """

    def _doc(self):
        from sbs_utils.procedural.amd_doc import document_get_amd_file, amd_section
        from sbs_utils.procedural.amd_mission import amd_mission_data
        path = os.path.join(os.path.dirname(__file__), "peacetime_remastered.amd")
        return document_get_amd_file(path, data_parser=amd_mission_data), amd_section

    def test_job_picket_goal_count_is_authored(self):
        doc, amd_section = self._doc()
        jobs = amd_section(doc, "jobs")
        picket = [c for c in (jobs.get("children") or []) if c.get("key") == "job_picket"]
        self.assertEqual(len(picket), 1, "job_picket must exist under the jobs section")
        sig = (picket[0].get("data") or {}).get("on_signal") or {}
        self.assertEqual(sig.get("name"), "picket_placed")
        self.assertEqual(sig.get("count"), 3, "the crate count is derived from this")

    def test_picket_landmark_has_a_position_and_radius(self):
        from sbs_utils.procedural.amd_landmarks import landmarks_from_section
        doc, amd_section = self._doc()
        recs = landmarks_from_section(amd_section(doc, "landmarks"))
        rec = MH.pr_landmark_by_key(recs, "picket_lm")
        self.assertIsNotNone(rec, "picket_lm landmark must exist")
        self.assertIsNotNone(rec.get("loc"), "the zone needs a Loc")
        self.assertEqual(MH.pr_landmark_field(recs, "picket_lm", "radius"), 2500)

    def test_the_picket_zone_has_no_art(self):
        # Deliberate: landmark_spawn places nothing without Art:, so the zone stays a pure
        # position. A physical buoy would get shot or tethered.
        from sbs_utils.procedural.amd_landmarks import landmarks_from_section
        doc, amd_section = self._doc()
        recs = landmarks_from_section(amd_section(doc, "landmarks"))
        self.assertFalse(MH.pr_landmark_by_key(recs, "picket_lm").get("art"))


if __name__ == "__main__":
    unittest.main()
