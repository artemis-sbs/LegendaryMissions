"""Tests for the quest end-game core: mission (parent) aggregation, end_win/
end_lose, and the symmetric fail-triggers (fail_on_signal / fail_on_all_dead).

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest quests.test_quest_end_game
"""
import os, sys, unittest

# make quest_driver.py (this folder) importable
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


class QuestEndGameTests(unittest.TestCase):
    def setUp(self):
        reset_mock(sbs)
        self.events = []
        # capture signals (game_over etc.) without a live MAST scheduler
        self._real_emit = QD.signal_emit
        QD.signal_emit = lambda name, data=None: self.events.append((name, data))

    def tearDown(self):
        QD.signal_emit = self._real_emit

    def _game_overs(self):
        return [d for n, d in self.events if n == "game_over"]

    def _mission(self):
        quest_add(SH, "mission", "Repel the Siege", "",
                  state=QuestState.ACTIVE,
                  data={"end_win": True, "end_lose": True, "lose_text": "The bases fell."})
        quest_add(SH, "clear", "Clear raiders", "",
                  state=QuestState.ACTIVE,
                  data={"parent": "mission", "required": True,
                        "on_kill": {"role": "raider", "count": 1}})
        quest_add(SH, "hold", "Hold the line", "",
                  state=QuestState.ACTIVE,
                  data={"parent": "mission", "critical": True,
                        "fail_on_signal": {"name": "base_lost"}})

    def _raider(self):
        rid = to_id(create_enemy(0, 0, 0, "kralien_cruiser", name="R"))
        Agent.get(rid).add_role("raider")
        return rid

    def test_required_child_wins_the_mission(self):
        self._mission()
        QD.quest_on_kill_shared(self._raider())
        self.assertEqual(int(quest_get_state(SH, "clear")), int(QuestState.COMPLETE))
        self.assertEqual(int(quest_get_state(SH, "mission")), int(QuestState.COMPLETE))
        gos = self._game_overs()
        self.assertEqual(len(gos), 1)
        self.assertTrue(gos[0]["WIN"])

    def test_critical_child_loses_the_mission(self):
        self._mission()
        QD.quest_on_signal("base_lost")
        self.assertEqual(int(quest_get_state(SH, "hold")), int(QuestState.FAILED))
        self.assertEqual(int(quest_get_state(SH, "mission")), int(QuestState.FAILED))
        gos = self._game_overs()
        self.assertEqual(len(gos), 1)
        self.assertFalse(gos[0]["WIN"])
        self.assertEqual(gos[0]["TEXT"], "The bases fell.")

    def test_unrelated_signal_does_not_end_game(self):
        self._mission()
        QD.quest_on_signal("some_other_thing")
        self.assertEqual(int(quest_get_state(SH, "mission")), int(QuestState.ACTIVE))
        self.assertEqual(self._game_overs(), [])

    def test_fail_on_all_dead_only_on_last(self):
        quest_add(SH, "escort", "Protect convoy", "",
                  state=QuestState.ACTIVE,
                  data={"end_lose": True, "fail_on_all_dead": {"role": "convoy"}})
        c1 = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="C1"))
        c2 = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="C2"))
        Agent.get(c1).add_role("convoy")
        Agent.get(c2).add_role("convoy")
        QD.quest_fail_on_all_dead(c1)   # one dies, one remains
        self.assertEqual(int(quest_get_state(SH, "escort")), int(QuestState.ACTIVE))
        Agent.get(c1).remove_role("convoy")
        QD.quest_fail_on_all_dead(c2)   # the last one is dying now
        self.assertEqual(int(quest_get_state(SH, "escort")), int(QuestState.FAILED))
        self.assertEqual(len(self._game_overs()), 1)

    def test_shared_quest_credit_reward_no_side_crash(self):
        # A SHARED quest (Agent.SHARED_ID has no .side) with a credits reward must
        # complete without crashing on ship.side - the siege boss "Defeat the
        # Warlord" (Pays: 500 credits) case. Reward is simply skipped (no side).
        quest_add(SH, "warlord", "Defeat the Warlord", "", state=QuestState.ACTIVE,
                  data={"on_kill": {"role": "warlord", "count": 1}, "reward": {"credits": 500}})
        wl = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="W"))
        Agent.get(wl).add_role("warlord")
        QD.quest_on_kill_shared(wl)
        self.assertEqual(int(quest_get_state(SH, "warlord")), int(QuestState.COMPLETE))

    def _make_side(self, key):
        from sbs_utils.agent import get_story_id
        s = Agent(); s.id = get_story_id(); s.add(); s.add_role("__side__")
        s.set_inventory_value("side_key", key)
        s.set_inventory_value("side_name", key)
        return s

    def test_on_kill_hostile_gate(self):
        # A general "destroy N enemies" quest: hostile=true counts only diplomatic
        # enemies, so a neutral/ceasefired ship (still combat-tagged) does NOT count.
        from sbs_utils.procedural.sides import side_set_relations
        self._make_side("tsn"); self._make_side("raider"); self._make_side("civ")
        side_set_relations("tsn", "raider", sbs.DIPLOMACY.HOSTILE)
        side_set_relations("tsn", "civ", sbs.DIPLOMACY.NEUTRAL)
        killer = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="K"))
        ko = Agent.get(killer); ko.add_role("__player__"); ko.side = "tsn"
        quest_add(killer, "hunt", "Hunt enemies", "", state=QuestState.ACTIVE,
                  data={"on_kill": {"hostile": True, "count": 1}})
        neutral = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="C"))
        no = Agent.get(neutral); no.add_role("raider"); no.side = "civ"   # neutral, still tagged
        QD.quest_on_kill(killer, neutral)
        self.assertEqual(int(quest_get_state(killer, "hunt")), int(QuestState.ACTIVE))
        foe = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="F"))
        fo = Agent.get(foe); fo.add_role("raider"); fo.side = "raider"
        QD.quest_on_kill(killer, foe)
        self.assertEqual(int(quest_get_state(killer, "hunt")), int(QuestState.COMPLETE))

    def test_on_kill_roles_any_of(self):
        killer = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="K2"))
        Agent.get(killer).add_role("__player__")
        quest_add(killer, "hunt2", "Hunt types", "", state=QuestState.ACTIVE,
                  data={"on_kill": {"roles": ["raider", "warlord"], "count": 1}})
        victim = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="V"))
        Agent.get(victim).add_role("warlord")   # matches one of the listed roles
        QD.quest_on_kill(killer, victim)
        self.assertEqual(int(quest_get_state(killer, "hunt2")), int(QuestState.COMPLETE))

    def test_penalty_removes_items_on_fail(self):
        ship = to_id(create_enemy(0, 0, 0, "tsn_light_cruiser", name="P"))
        Agent.get(ship).add_role("__player__")
        from sbs_utils.procedural.inventory import set_inventory_value, get_inventory_value
        set_inventory_value(ship, "tech", 5)
        quest_add(ship, "job", "Risky job", "", state=QuestState.ACTIVE,
                  data={"penalty": {"items": {"tech": 2}}})
        QD.quest_mark_failed(ship, "job")
        self.assertEqual(int(quest_get_state(ship, "job")), int(QuestState.FAILED))
        self.assertEqual(get_inventory_value(ship, "tech", 0), 3)


if __name__ == "__main__":
    unittest.main()
