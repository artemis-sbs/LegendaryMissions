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


if __name__ == "__main__":
    unittest.main()
