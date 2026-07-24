"""Quest lifecycle overlay directives: accept/complete/fail fire overlays, in both
the declared-reference form (`complete_overlay: key` -> overlay_amd) and the inline
form (`on_complete: <kind> <text>`).

    PYTHONPATH=../sbs_utils python -m unittest quests.test_quest_overlay
"""
import os, sys, unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # break a circular import
from cosmos_dev.mock import sbs as sbs
from tests.reset_helper import reset_mock
from sbs_utils.agent import Agent
from sbs_utils.procedural.quest import quest_add, QuestState

import quest_driver as QD

SH = Agent.SHARED_ID


class QuestOverlayDirectiveTests(unittest.TestCase):
    def setUp(self):
        reset_mock(sbs)
        self.amd = []          # (key, to, overrides)
        self.trans = []        # (slot, kind, content)
        self._saved = (QD.overlay_amd, QD._show_transient, QD.signal_emit, QD.comms_broadcast)
        QD.overlay_amd = lambda key, to=None, **kw: self.amd.append((key, to, kw))
        QD._show_transient = lambda slot, kind, to, seconds, content: self.trans.append((slot, kind, content))
        QD.signal_emit = lambda name, data=None: None
        QD.comms_broadcast = lambda *a, **k: None

    def tearDown(self):
        QD.overlay_amd, QD._show_transient, QD.signal_emit, QD.comms_broadcast = self._saved

    def _kinds(self):
        return [(k, c) for (s, k, c) in self.trans]

    def test_complete_reference_form_fires_amd(self):
        quest_add(SH, "rescue", "Rescue", "", state=QuestState.ACTIVE,
                  data={"complete_overlay": "convoy_saved"})
        QD.quest_mark_complete(SH, "rescue")
        self.assertIn("convoy_saved", [k for (k, _to, _kw) in self.amd])

    def test_complete_inline_form_fires_kind_with_text(self):
        quest_add(SH, "rescue2", "Rescue", "", state=QuestState.ACTIVE,
                  data={"on_complete": "hero CONVOY SAVED"})
        QD.quest_mark_complete(SH, "rescue2")
        self.assertTrue(any(k == "hero" and c.get("title") == "CONVOY SAVED"
                            for k, c in self._kinds()))

    def test_accept_inline_toast(self):
        quest_add(SH, "job", "Job", "", state=QuestState.IDLE,
                  data={"on_accept": "toast New job"})
        QD.quest_mark_active(SH, "job")
        self.assertTrue(any(k == "toast" and c.get("text") == "New job"
                            for k, c in self._kinds()))

    def test_fail_inline_banner(self):
        quest_add(SH, "def", "Defense", "", state=QuestState.ACTIVE,
                  data={"on_fail": "banner Convoy lost"})
        QD.quest_mark_failed(SH, "def")
        self.assertTrue(any(k == "banner" and c.get("text") == "Convoy lost"
                            for k, c in self._kinds()))

    def test_inline_overlay_keyword_references_declared(self):
        quest_add(SH, "q", "Q", "", state=QuestState.ACTIVE,
                  data={"on_complete": "overlay ch1"})
        QD.quest_mark_complete(SH, "q")
        self.assertIn("ch1", [k for (k, _to, _kw) in self.amd])

    def test_both_forms_together(self):
        quest_add(SH, "both", "Both", "", state=QuestState.ACTIVE,
                  data={"complete_overlay": "big_card", "on_complete": "toast done"})
        QD.quest_mark_complete(SH, "both")
        self.assertIn("big_card", [k for (k, _to, _kw) in self.amd])
        self.assertTrue(any(k == "toast" and c.get("text") == "done" for k, c in self._kinds()))

    def test_space_authoring_also_works(self):
        # `On complete:` (space) parses to key "on complete"; must still fire
        quest_add(SH, "sp", "Sp", "", state=QuestState.ACTIVE,
                  data={"on complete": "hero SPACED"})
        QD.quest_mark_complete(SH, "sp")
        self.assertTrue(any(k == "hero" and c.get("title") == "SPACED" for k, c in self._kinds()))

    def test_no_directive_fires_nothing(self):
        quest_add(SH, "plain", "Plain", "", state=QuestState.ACTIVE, data={"reward": {"credits": 1}})
        QD.quest_mark_complete(SH, "plain")
        self.assertEqual(self.amd, [])
        self.assertEqual(self.trans, [])


if __name__ == "__main__":
    unittest.main()
