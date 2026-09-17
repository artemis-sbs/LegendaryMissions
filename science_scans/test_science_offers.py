"""The offer line Science reads on a contact that has work.

Comms can only say "2 jobs" once the crew have already selected that contact there.
Science is where a bridge finds out what is out there at all, so a contact with open work
should say so on a scan.

The wording is load-bearing: a tab is a STORED string, so a scan taken before a job
appeared is genuinely out of date. The line says "at last scan" rather than giving a bare
count, because a number that might be stale and does not admit it is worse than no number.

    python -m unittest test_science_offers
"""
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes            # noqa: F401  breaks a circular import
from cosmos_dev.mock import sbs
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.offer import offer_clear, offer_register, offer_record

from science_offers import (lm_science_offer_line, lm_science_offers_push,
                            LM_OFFER_SCAN_TAB)

STATION = 4242


def _provider(rows):
    def fn(ctx):
        return rows if ctx.get("object_id") == STATION else []
    return fn


class OfferLineTests(unittest.TestCase):
    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        offer_clear()

    def tearDown(self):
        offer_clear()

    def _install(self, *rows):
        offer_register("t", _provider(list(rows)))

    def test_nothing_on_offer_says_nothing(self):
        self.assertEqual(lm_science_offer_line(STATION), "")

    def test_one_job_is_singular(self):
        self._install(offer_record("a", "A"))
        self.assertIn("1 job.", lm_science_offer_line(STATION))

    def test_several_are_counted(self):
        self._install(offer_record("a", "A"), offer_record("b", "B"))
        self.assertIn("2 jobs.", lm_science_offer_line(STATION))

    def test_pending_offers_are_not_counted(self):
        """Something else has to hand you a POSTING job, so it is not a reason to fly
        over and hail anybody - which is exactly what this line is telling you to do."""
        self._install(offer_record("a", "A"), offer_record("b", "B", pending=True))
        self.assertIn("1 job.", lm_science_offer_line(STATION))

    def test_it_admits_it_may_be_stale(self):
        """THE POINT. A tab is written once at scan time and never re-rendered, so a
        bare count would quietly lie after the next job is granted."""
        self._install(offer_record("a", "A"))
        self.assertIn("at last scan", lm_science_offer_line(STATION))

    def test_it_says_what_to_do_about_it(self):
        self._install(offer_record("a", "A"))
        self.assertIn("Hail", lm_science_offer_line(STATION))

    def test_it_is_ascii(self):
        self._install(offer_record("a", "A"))
        lm_science_offer_line(STATION).encode("ascii")

    def test_an_unscanned_contact_is_not_written(self):
        """The scan itself will carry the line - writing before one would put intel on
        a contact the crew have not earned it on."""
        self._install(offer_record("a", "A"))
        self.assertFalse(lm_science_offers_push(1, STATION))

    def test_a_missing_object_is_not_written(self):
        self._install(offer_record("a", "A"))
        self.assertFalse(lm_science_offers_push(1, 999999))

    def test_the_tab_is_intel_not_scan(self):
        """`scan` is always present and carries the object's own description, so writing
        there would displace a mission's authored prose."""
        self.assertEqual(LM_OFFER_SCAN_TAB, "intel")


if __name__ == "__main__":
    unittest.main()
