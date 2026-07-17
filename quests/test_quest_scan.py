"""Tests for declarative quest science-scan content (the `Reveals:`/reveal_scan feature).

A quest with on_scan + reveal_scan makes its target scannable and supplies the scan
text, so a survey/clue scan needs no hand-authored //science route. Also covers the
on_scan distinct-target dedup.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest quests.test_quest_scan
"""
import os, sys, unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # import first to break a circular import
from cosmos_dev.mock import sbs as sbs
from tests.reset_helper import reset_mock
from sbs_utils.agent import Agent
from sbs_utils.procedural.quest import quest_add, quest_get_state, QuestState
from sbs_utils.procedural.a2x.spawn import create_enemy
from sbs_utils.procedural.query import to_id

import quest_driver as QD

SH = Agent.SHARED_ID


class QuestScanTests(unittest.TestCase):
    def setUp(self):
        reset_mock(sbs)
        # a "player" ship that owns the quest, and two anomaly targets
        self.player = to_id(create_enemy(0, 0, 0, "kralien_cruiser", name="P"))
        self.a1 = to_id(create_enemy(100, 0, 0, "kralien_cruiser", name="A1"))
        self.a2 = to_id(create_enemy(200, 0, 0, "kralien_cruiser", name="A2"))
        Agent.get(self.a1).add_role("anomaly")
        Agent.get(self.a2).add_role("anomaly")

    def _grant(self, count=2):
        quest_add(self.player, "survey", "Anomaly Survey", "",
                  state=QuestState.ACTIVE,
                  data={"on_scan": {"role": "anomaly", "count": count},
                        "reveal_scan": "A stable subspace distortion."})

    def test_enabled_only_for_matching_reveal_target(self):
        self._grant()
        # anomaly with a reveal quest -> scannable; a non-anomaly -> not
        self.assertTrue(QD.quest_scan_enabled(self.player, self.a1))
        self.assertFalse(QD.quest_scan_enabled(self.player, self.player))

    def test_scan_text_is_the_reveal(self):
        self._grant()
        self.assertEqual(QD.quest_scan_text(self.player, self.a1),
                         "A stable subspace distortion.")

    def test_no_reveal_no_enable(self):
        # on_scan WITHOUT reveal_scan must not make the object quest-scannable
        quest_add(self.player, "plain", "Plain", "",
                  state=QuestState.ACTIVE,
                  data={"on_scan": {"role": "anomaly", "count": 1}})
        self.assertFalse(QD.quest_scan_enabled(self.player, self.a1))
        self.assertEqual(QD.quest_scan_text(self.player, self.a1), "")

    def test_distinct_targets_advance_then_complete(self):
        self._grant(count=2)
        QD.quest_on_scan(self.player, self.a1)
        self.assertEqual(quest_get_state(self.player, "survey"), QuestState.ACTIVE)
        QD.quest_on_scan(self.player, self.a2)
        self.assertEqual(quest_get_state(self.player, "survey"), QuestState.COMPLETE)

    def test_rescanning_same_target_does_not_overcount(self):
        self._grant(count=2)
        QD.quest_on_scan(self.player, self.a1)
        QD.quest_on_scan(self.player, self.a1)   # same target again
        QD.quest_on_scan(self.player, self.a1)
        # still needs a DISTINCT second target
        self.assertEqual(quest_get_state(self.player, "survey"), QuestState.ACTIVE)
        QD.quest_on_scan(self.player, self.a2)
        self.assertEqual(quest_get_state(self.player, "survey"), QuestState.COMPLETE)


if __name__ == "__main__":
    unittest.main()
