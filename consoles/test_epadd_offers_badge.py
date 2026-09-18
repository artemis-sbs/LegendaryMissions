"""The Quests tile's badge: how many jobs are on offer that nobody has taken.

Until this existed the tile carried no reading at all, so a crew could sit in front of
the PADD with three jobs waiting and nothing on screen said so. The badge is the quietest
possible answer - it never interrupts, it is simply there when there is something.

    python -m unittest test_epadd_offers_badge
"""
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes            # noqa: F401  breaks a circular import
from cosmos_dev.mock import sbs
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.offer import offer_clear, offer_register

from epadd import lm_epadd_offers


class EpaddOffersBadgeTests(unittest.TestCase):
    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        offer_clear()

    def tearDown(self):
        offer_clear()

    # Which quest STATES become offers is the library's rule and is pinned in
    # sbs_utils/tests/test_offer_quest_provider.py. This file is about the reading.
    def test_quiet_when_there_is_nothing(self):
        """A tile saying '0 available' is worse than a tile saying nothing."""
        self.assertEqual(lm_epadd_offers(), "")

    def test_counts_available_jobs(self):
        offer_register("t", lambda ctx: _rows(2))
        self.assertEqual(lm_epadd_offers(), "2 available")

    def test_singular_still_reads_as_a_count(self):
        offer_register("t", lambda ctx: _rows(1))
        self.assertEqual(lm_epadd_offers(), "1 available")

    def test_pending_offers_are_not_counted(self):
        """A POSTING job is listed so you know it exists, but somebody else has to hand
        it to you - so it is not something you can act on, and the badge promises action."""
        from sbs_utils.procedural.offer import offer_record
        offer_register("t", lambda ctx: [
            offer_record("a", "Takeable"),
            offer_record("b", "Posted", pending=True),
        ])
        self.assertEqual(lm_epadd_offers(), "1 available")

    def test_it_is_ascii(self):
        offer_register("t", lambda ctx: _rows(3))
        lm_epadd_offers().encode("ascii")        # raises if not

    def test_a_broken_provider_costs_only_its_own_rows(self):
        """The badge is computed on every tile of every build, so a provider having a
        bad day must not take the reading down with it."""
        def bad(ctx):
            raise RuntimeError("boom")
        offer_register("bad", bad)
        offer_register("good", lambda ctx: _rows(1))
        self.assertEqual(lm_epadd_offers(), "1 available")

    def test_it_never_raises(self):
        offer_register("bad", lambda ctx: (_ for _ in ()).throw(ValueError("x")))
        self.assertEqual(lm_epadd_offers(), "")


def _rows(n):
    from sbs_utils.procedural.offer import offer_record
    return [offer_record(f"k{i}", f"Job {i}") for i in range(n)]


if __name__ == "__main__":
    unittest.main()


class QuestAppReachesTheFlightDeck(unittest.TestCase):
    """The Quests app must be available where a sortie is actually taken.

    THE REGISTRATION WAS NEVER THE GATE. The app is registered for every ship console
    (`consoles=None`), which looks like it covers the hangar - but `gui_app_list` honours
    a route's own `if` above the registration, and `//gui/app/quest` tests
    `quest_is_console_enabled(CONSOLE_SELECT)`. That list named six bridge consoles and
    neither the hangar nor the cockpit, so the one place a pilot takes a job was the one
    place the Quests tile did not exist.

    Pinned because it fails in complete silence: no tile, no log line, and the app list
    looks correct from the registration alone.
    """

    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        from sbs_utils.procedural.quest import quest_consoles_clear
        quest_consoles_clear()

    def _enable_as_lm_does(self):
        from sbs_utils.procedural.quest import quest_console_enable
        quest_console_enable("helm,weapons,science,engineering,comms,mainscreen,"
                             "hangar,cockpit")

    def test_the_flight_deck_can_see_quests(self):
        from sbs_utils.procedural.quest import quest_is_console_enabled
        self._enable_as_lm_does()
        self.assertTrue(quest_is_console_enabled("hangar"))

    def test_the_cockpit_can_too(self):
        """A pilot in the seat reaches the PADD by its one button; the app still has to
        be willing to appear there."""
        from sbs_utils.procedural.quest import quest_is_console_enabled
        self._enable_as_lm_does()
        self.assertTrue(quest_is_console_enabled("cockpit"))

    def test_the_bridge_consoles_are_unchanged(self):
        from sbs_utils.procedural.quest import quest_is_console_enabled
        self._enable_as_lm_does()
        for c in ("helm", "weapons", "science", "engineering", "comms", "mainscreen"):
            self.assertTrue(quest_is_console_enabled(c), c)

    def test_it_is_still_a_list_not_everything(self):
        """Enabling the hangar must not turn the gate off - a console nobody named still
        gets no tile."""
        from sbs_utils.procedural.quest import quest_is_console_enabled
        self._enable_as_lm_does()
        self.assertFalse(quest_is_console_enabled("nav"))
