"""The offers digest: one quiet line when the work on offer CHANGES.

This is the only PUSH in the whole discovery feature, so it carries the whole burden of
not becoming the noise the feature exists to remove. Three things are pinned here:

* it says nothing when nothing moved,
* it never raises a panel, and
* it yields to a voice without SPENDING that voice's budget.

    python -m unittest test_offer_digest
"""
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes            # noqa: F401  breaks a circular import
from cosmos_dev.mock import sbs
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.offer import offer_clear, offer_register, offer_record
from sbs_utils.procedural import log_panel as LP
from sbs_utils.procedural.gui import log_panel_gui as LPG
from sbs_utils.procedural import announce as AN
from sbs_utils.gui import GuiClient

import offer_digest as D

CID = 101


def _rows(*titles, kind="job"):
    return [offer_record(f"k{t}", t, kind=kind) for t in titles]


class DigestTextTests(unittest.TestCase):
    def test_every_kind_is_a_quest_to_the_player(self):
        """One word for players: a job, a sortie and a contact are all quests."""
        t = D.lm_offer_digest_text(_rows("A", "B") + _rows("C", kind="contact"), [])
        self.assertIn("3 quests", t)
        self.assertNotIn("job", t)
        self.assertNotIn("contact", t)

    def test_one_is_singular(self):
        self.assertIn("1 quest.", D.lm_offer_digest_text(_rows("A"), []))

    def test_it_names_what_is_new(self):
        t = D.lm_offer_digest_text(_rows("A", "B"), _rows("B"))
        self.assertIn("New: B", t)

    def test_it_names_at_most_two(self):
        t = D.lm_offer_digest_text(_rows("A", "B", "C"), _rows("A", "B", "C"))
        self.assertNotIn("C.", t.split("New:")[1])

    def test_it_is_ascii(self):
        D.lm_offer_digest_text(_rows("A"), []).encode("ascii")


class DigestDecisionTests(unittest.TestCase):
    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        # The digest remembers what a console was last told in CLIENT INVENTORY, so the
        # client has to be a real agent - an id alone has nowhere to write to.
        GuiClient(CID)
        offer_clear()
        LP.log_clear()
        AN.announce_traffic_reset()
        self.current = list(_rows("Patrol"))
        offer_register("t", lambda ctx: self.current)

    def tearDown(self):
        offer_clear()
        AN.announce_traffic_reset()

    def _due(self, now=0):
        return D.lm_offer_digest_due(CID, now=now)[0]

    def test_it_speaks_the_first_time(self):
        self.assertIsNotNone(self._due())

    def test_it_says_nothing_when_nothing_moved(self):
        """A digest repeating the same number is exactly the spam this replaces."""
        self.assertIsNotNone(D.lm_offer_digest_send(CID, now=0))
        self.assertIsNone(D.lm_offer_digest_send(CID, now=10_000))

    def test_it_speaks_again_when_the_set_changes(self):
        D.lm_offer_digest_send(CID, now=0)
        self.current = list(_rows("Patrol", "Escort"))
        text = D.lm_offer_digest_send(CID, now=10_000)
        self.assertIsNotNone(text)
        self.assertIn("Escort", text)

    def test_the_floor_holds_it_back(self):
        D.lm_offer_digest_send(CID, now=0)
        self.current = list(_rows("Patrol", "Escort"))
        self.assertIsNone(D.lm_offer_digest_send(CID, now=D.LM_OFFER_DIGEST_FLOOR - 1))
        self.assertIsNotNone(D.lm_offer_digest_send(CID, now=D.LM_OFFER_DIGEST_FLOOR + 1))

    def test_an_empty_board_is_not_news(self):
        """'There is no work' is not something anybody needs telling."""
        self.current = []
        self.assertIsNone(D.lm_offer_digest_send(CID, now=0))
        self.assertEqual(LP.log_entries(CID) or [], [])

    def test_an_empty_board_is_still_REMEMBERED(self):
        """...so the next job to appear counts as new rather than being swallowed."""
        D.lm_offer_digest_send(CID, now=0)
        self.current = []
        D.lm_offer_digest_send(CID, now=10_000)
        self.current = list(_rows("Patrol"))
        text = D.lm_offer_digest_send(CID, now=20_000)
        self.assertIsNotNone(text)
        self.assertIn("New: Patrol", text)

    # --- the speech budget ----------------------------------------------------
    def test_it_yields_to_a_voice(self):
        """A line arriving underneath a character talking is a line nobody reads."""
        AN.announce_note_traffic(0)
        self.assertIsNone(self._due(now=1))

    def test_it_speaks_once_the_voice_has_finished(self):
        from sbs_utils.procedural.urge import URGE_GLOBAL_FLOOR
        AN.announce_note_traffic(0)
        self.assertIsNotNone(self._due(now=URGE_GLOBAL_FLOOR + 1))

    def test_it_does_NOT_spend_the_speech_budget(self):
        """It took no screen, so it owes the budget nothing - stamping the clock here
        would mute a character for the next 20 seconds for the sake of a log line."""
        before = AN.announce_last_traffic()
        D.lm_offer_digest_send(CID, now=0)
        self.assertEqual(AN.announce_last_traffic(), before)

    # --- THE RULE -------------------------------------------------------------
    def test_it_never_raises_a_panel(self):
        calls = []
        real = LPG.log_raise
        LPG.log_raise = lambda *a, **kw: calls.append(a)
        try:
            D.lm_offer_digest_send(CID, now=0)
        finally:
            LPG.log_raise = real
        self.assertEqual(calls, [])

    def test_it_files_the_line_where_the_console_will_see_it(self):
        D.lm_offer_digest_send(CID, now=0)
        self.assertEqual(len(LP.log_entries(CID) or []), 1)

    def test_the_dial_turns_it_off(self):
        from sbs_utils.procedural.execution import set_shared_variable
        set_shared_variable("OFFER_DIGEST_ENABLED", False)
        try:
            self.assertIsNone(self._due())
        finally:
            set_shared_variable("OFFER_DIGEST_ENABLED", True)


if __name__ == "__main__":
    unittest.main()
