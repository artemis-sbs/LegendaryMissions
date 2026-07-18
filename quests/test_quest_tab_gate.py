"""Tests for Quests-tab action-control gating (Accept/Abandon/Engage per console).

The tab DISPLAYS everywhere it is enabled, but WHICH console may act is gated:
Accept/Abandon on QUEST_ACCEPT_CONSOLES (default comms+admiral), Engage on
QUEST_ENGAGE_CONSOLES (default helm) and only once the job is ACTIVE. A quest can
override either list for itself (the AMD `Accept On:` / `Engage On:` labels).
quest_tab_controls_gate resolves buttons-vs-text; on a disallowed console the buttons
are replaced with text naming who can act.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest quests.test_quest_tab_gate
"""
import os, sys, unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # import first to break a circular import
from cosmos_dev.mock import sbs as sbs
from tests.reset_helper import reset_mock
from sbs_utils.agent import Agent
from sbs_utils.procedural.quest import quest_add, quest_set_key, QuestState
from sbs_utils.procedural.a2x.spawn import create_enemy
from sbs_utils.procedural.query import to_id
from sbs_utils.mast.mast_node import MastDataObject
from sbs_utils.procedural.amd_quest import amd_console_list, amd_quest_facts

import quest_driver as QD

ACCEPT = "comms,admiral"
ENGAGE = "helm"


class QuestTabGateTests(unittest.TestCase):
    def setUp(self):
        reset_mock(sbs)
        self.player = to_id(create_enemy(0, 0, 0, "kralien_cruiser", name="P"))

    def _job(self, key, state, data=None):
        """Grant a quest and return the log-row-shaped item the tab passes to the gate."""
        quest_add(self.player, key, key, "", state=state, data=(data or {}))
        return MastDataObject({"agent_id": self.player, "key": key, "state": int(state)})

    def _gate(self, console, item, engage_enabled=False):
        return QD.quest_tab_controls_gate(console, item, ACCEPT, engage_enabled, ENGAGE)

    # --- Accept/Abandon console gate (mission default) -----------------------
    def test_accept_console_shows_buttons(self):
        item = self._job("j", QuestState.IDLE)
        g = self._gate("comms", item)
        self.assertTrue(g["show_accept"])
        self.assertFalse(g["show_abandon"])
        self.assertEqual(g["hint"], "")

    # --- Accept/Abandon are STATE gated --------------------------------------
    def test_accept_only_for_idle(self):
        self.assertTrue(self._gate("comms", self._job("i", QuestState.IDLE))["show_accept"])
        self.assertFalse(self._gate("comms", self._job("a", QuestState.ACTIVE))["show_accept"])
        self.assertFalse(self._gate("comms", self._job("c", QuestState.COMPLETE))["show_accept"])
        self.assertFalse(self._gate("comms", self._job("f", QuestState.FAILED))["show_accept"])

    def test_abandon_only_for_active(self):
        self.assertFalse(self._gate("comms", self._job("i", QuestState.IDLE))["show_abandon"])
        self.assertTrue(self._gate("comms", self._job("a", QuestState.ACTIVE))["show_abandon"])
        self.assertFalse(self._gate("comms", self._job("c", QuestState.COMPLETE))["show_abandon"])
        self.assertFalse(self._gate("comms", self._job("f", QuestState.FAILED))["show_abandon"])

    def test_completed_failed_show_no_controls(self):
        for st in (QuestState.COMPLETE, QuestState.FAILED):
            g = self._gate("comms", self._job("q" + str(int(st)), st), engage_enabled=True)
            self.assertFalse(g["show_accept"])
            self.assertFalse(g["show_abandon"])
            self.assertFalse(g["show_engage"])
            self.assertEqual(g["hint"], "")

    def test_admiral_also_allowed(self):
        item = self._job("j", QuestState.IDLE)
        self.assertTrue(self._gate("admiral", item)["show_accept"])

    def test_non_accept_console_shows_text(self):
        item = self._job("j", QuestState.IDLE)
        g = self._gate("helm", item)
        self.assertFalse(g["show_accept"])
        self.assertIn("Comms", g["hint"])
        self.assertIn("Admiral", g["hint"])

    def test_empty_default_allows_any_console(self):
        item = self._job("j", QuestState.IDLE)
        g = QD.quest_tab_controls_gate("weapons", item, "", False, ENGAGE)
        self.assertTrue(g["show_accept"])

    # --- Engage gate ---------------------------------------------------------
    def test_engage_helm_active_shows(self):
        item = self._job("j", QuestState.ACTIVE)
        g = self._gate("helm", item, engage_enabled=True)
        self.assertTrue(g["show_engage"])

    def test_engage_helm_not_active_hint(self):
        item = self._job("j", QuestState.IDLE)
        g = self._gate("helm", item, engage_enabled=True)
        self.assertFalse(g["show_engage"])
        self.assertIn("Accept this job", g["hint"])

    def test_engage_disabled_never_shows(self):
        item = self._job("j", QuestState.ACTIVE)
        self.assertFalse(self._gate("helm", item, engage_enabled=False)["show_engage"])

    def test_non_engage_console_no_engage_and_no_engage_hint(self):
        # comms is an accept console; engage is helm-only. An ACTIVE job on comms shows the
        # Abandon control and no Engage control, and must NOT nag about engaging.
        item = self._job("j", QuestState.ACTIVE)
        g = self._gate("comms", item, engage_enabled=True)
        self.assertFalse(g["show_engage"])
        self.assertTrue(g["show_abandon"])
        self.assertNotIn("engag", g["hint"].lower())

    # --- Per-quest override --------------------------------------------------
    def test_per_quest_accept_override_adds_console(self):
        # A science-specific job: accept enabled on science, disabled on comms.
        item = self._job("sci_job", QuestState.IDLE, {"accept_consoles": ["science"]})
        self.assertTrue(self._gate("science", item)["show_accept"])
        self.assertFalse(self._gate("comms", item)["show_accept"])

    def test_per_quest_engage_override(self):
        item = self._job("wj", QuestState.ACTIVE, {"engage_consoles": ["weapons"]})
        self.assertTrue(self._gate("weapons", item, engage_enabled=True)["show_engage"])
        self.assertFalse(self._gate("helm", item, engage_enabled=True)["show_engage"])

    # --- Header / no selection shows no action controls ----------------------
    def test_header_item_shows_no_controls(self):
        header = QD.gui_list_box_header("Ship", data={})
        g = self._gate("comms", header, engage_enabled=True)
        self.assertFalse(g["show_accept"])
        self.assertFalse(g["show_abandon"])
        self.assertFalse(g["show_engage"])

    def test_none_item_shows_no_controls(self):
        g = self._gate("comms", None, engage_enabled=True)
        self.assertFalse(g["show_accept"])
        self.assertFalse(g["show_abandon"])
        self.assertFalse(g["show_engage"])

    # --- Signature changes only when availability changes --------------------
    def test_signature_stable_across_same_gate_quests(self):
        a = self._job("a", QuestState.IDLE)
        b = self._job("b", QuestState.IDLE)
        self.assertEqual(self._gate("comms", a)["sig"], self._gate("comms", b)["sig"])

    def test_signature_changes_for_console_specific_quest(self):
        plain = self._job("plain", QuestState.IDLE)
        sci = self._job("sci", QuestState.IDLE, {"accept_consoles": ["science"]})
        self.assertNotEqual(self._gate("science", plain)["sig"], self._gate("science", sci)["sig"])

    # --- Live-refresh state signature ----------------------------------------
    def test_state_sig_changes_on_state_change(self):
        self._job("j", QuestState.IDLE)
        s1 = QD.quest_tab_state_sig(0, self.player)
        quest_set_key(self.player, "j", "state", QuestState.ACTIVE)
        self.assertNotEqual(s1, QD.quest_tab_state_sig(0, self.player))

    def test_state_sig_changes_on_add_and_reveal(self):
        self._job("secret", QuestState.SECRET)
        s1 = QD.quest_tab_state_sig(0, self.player)
        self._job("new", QuestState.IDLE)              # a new quest appears
        s2 = QD.quest_tab_state_sig(0, self.player)
        self.assertNotEqual(s1, s2)
        quest_set_key(self.player, "secret", "state", QuestState.ACTIVE)  # revealed
        self.assertNotEqual(s2, QD.quest_tab_state_sig(0, self.player))

    def test_state_sig_stable_when_unchanged(self):
        self._job("j", QuestState.ACTIVE)
        self.assertEqual(QD.quest_tab_state_sig(0, self.player),
                         QD.quest_tab_state_sig(0, self.player))

    # --- AMD label parsing ---------------------------------------------------
    def test_amd_console_list(self):
        self.assertEqual(amd_console_list("comms, admiral"), ["comms", "admiral"])
        self.assertEqual(amd_console_list("Helm"), ["helm"])
        self.assertEqual(amd_console_list("comms admiral"), ["comms", "admiral"])

    def test_amd_accept_engage_labels(self):
        h = amd_quest_facts()
        data = {}
        h(data, "accept on", "comms, admiral")
        h(data, "engage on", "Helm")
        self.assertEqual(data["accept_consoles"], ["comms", "admiral"])
        self.assertEqual(data["engage_consoles"], ["helm"])


if __name__ == "__main__":
    unittest.main()
