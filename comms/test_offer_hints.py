"""The comms selection hint: "DS 1 - 2 jobs".

The one surface here that changes a screen the crew already use, so it is held to the
engine's two rules about a selection title - ASCII, and no `:` or `;`, because the
engine PARSES it as a style-property string rather than drawing it.

    python -m unittest test_offer_hints
"""
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes            # noqa: F401  breaks a circular import
from cosmos_dev.mock import sbs
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.offer import offer_clear, offer_register, offer_record

from offer_hints import lm_comms_offer_title, lm_offer_hint_text, LM_OFFER_TITLE_MAX

STATION = 4242


def _provider(rows):
    def fn(ctx):
        return rows if ctx.get("object_id") == STATION else []
    return fn


class OfferHintTests(unittest.TestCase):
    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        offer_clear()

    def tearDown(self):
        offer_clear()

    def _install(self, *rows):
        offer_register("t", _provider(list(rows)))

    # --- the quiet case, which is most of them --------------------------------
    def test_nothing_on_offer_leaves_the_title_alone(self):
        self.assertEqual(lm_comms_offer_title(1, STATION, "DS 1"), "DS 1")

    def test_a_contact_with_no_offers_is_untouched(self):
        self._install(offer_record("a", "Job"))
        self.assertEqual(lm_comms_offer_title(1, 9999, "Raider"), "Raider")

    # --- counting -------------------------------------------------------------
    def test_one_job_is_singular(self):
        self._install(offer_record("a", "Job"))
        self.assertEqual(lm_comms_offer_title(1, STATION, "DS 1"), "DS 1 - 1 quest")

    def test_several_jobs_are_counted(self):
        self._install(offer_record("a", "A"), offer_record("b", "B"))
        self.assertEqual(lm_comms_offer_title(1, STATION, "DS 1"), "DS 1 - 2 quests")

    def test_pending_offers_do_not_inflate_the_count(self):
        """A POSTING job is listed on the board so the crew know it exists, but it is
        not a reason to hail anybody - and this number answers exactly that question."""
        self._install(offer_record("a", "A"), offer_record("b", "B", pending=True))
        self.assertEqual(lm_offer_hint_text(STATION), "1 quest")

    # --- the engine's rules ---------------------------------------------------
    def test_it_never_emits_a_character_the_engine_parses(self):
        self._install(offer_record("a", "A"))
        out = lm_comms_offer_title(1, STATION, "DS 1")
        self.assertNotIn(":", out)
        self.assertNotIn(";", out)

    def test_it_strips_those_characters_out_of_the_name_too(self):
        self._install(offer_record("a", "A"))
        out = lm_comms_offer_title(1, STATION, "DS 1: Alpha; Base")
        self.assertNotIn(":", out)
        self.assertNotIn(";", out)

    def test_it_is_ascii(self):
        self._install(offer_record("a", "A"))
        lm_comms_offer_title(1, STATION, "DS 1").encode("ascii")

    def test_a_long_name_keeps_its_name_and_drops_the_suffix(self):
        """Knowing WHO you clicked on always beats knowing how many jobs they have."""
        self._install(offer_record("a", "A"))
        long_name = "X" * (LM_OFFER_TITLE_MAX - 2)
        self.assertEqual(lm_comms_offer_title(1, STATION, long_name), long_name)

    def test_a_broken_provider_leaves_the_title_alone(self):
        offer_register("bad", lambda ctx: (_ for _ in ()).throw(RuntimeError("x")))
        self.assertEqual(lm_comms_offer_title(1, STATION, "DS 1"), "DS 1")


if __name__ == "__main__":
    unittest.main()
