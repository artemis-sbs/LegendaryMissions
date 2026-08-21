"""What a console opened AS, and the name that follows from it.

Two of these guard behaviour that is only visible with several windows open:

  * `test_only_declared_screens_are_in_the_sets` - the Director is a streaming tool. A
    mainscreen or a crew seat must not become a target; commandeering helm mid-game ruins
    somebody's game.
  * `test_the_fingerprint_ignores_what_a_screen_is_showing` - the player rewrites CONSOLE_TYPE
    every time it changes a screen's item, so watching it would repaint the operator's page
    every dwell, under their hands.

The picker that used to live here - `director_screen_rows`, `director_offer_screens` and the
one-shot pre-tick memory - went with the narrowing to two feeds. A console's declared mode IS
its selection now, so there is nothing left to tick.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_modes
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import director_modes as dm


def _install(roles, inventory):
    roles_mod = types.ModuleType("sbs_utils.procedural.roles")
    roles_mod.role = lambda name: set(roles.get(name, ()))

    inv_mod = types.ModuleType("sbs_utils.procedural.inventory")
    inv_mod.get_inventory_value = lambda cid, key, default=None: inventory.get((cid, key), default)

    def set_inventory_value(cid, key, value):
        inventory[(cid, key)] = value

    inv_mod.set_inventory_value = set_inventory_value

    saved = {}
    for name, mod in (("sbs_utils.procedural.roles", roles_mod),
                      ("sbs_utils.procedural.inventory", inv_mod)):
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    def restore():
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    return restore


class ModeVocabularyTests(unittest.TestCase):
    def test_the_three_modes(self):
        self.assertEqual(dm.director_mode_list(), "Director,Program,Preview")

    def test_a_label_round_trips(self):
        for mode in dm.DIRECTOR_MODES_ALL:
            self.assertEqual(dm.director_mode_for(dm.director_mode_label(mode)), mode)

    def test_an_unknown_mode_is_director(self):
        # The safe default: a console that fails to declare is a control console, not a screen
        # that silently starts carrying the show.
        self.assertEqual(dm.director_mode_for("wibble"), "director")
        self.assertEqual(dm.director_mode_for(None), "director")


class DeclarationTests(unittest.TestCase):
    def setUp(self):
        dm.director_modes_reset()
        self.roles = {"console": {10, 11, 12, 13}}
        self.inventory = {
            (10, "CREW_NAME"): "PROG01",
            (11, "CREW_NAME"): "PROG02",
            (12, "CREW_NAME"): "PRE01",
            (13, "CREW_NAME"): "DIR01",
        }
        self.restore = _install(self.roles, self.inventory)
        dm.director_mode_set(10, "program")
        dm.director_mode_set(11, "program")
        dm.director_mode_set(12, "preview")
        dm.director_mode_set(13, "director")

    def tearDown(self):
        self.restore()
        dm.director_modes_reset()

    def test_a_mode_round_trips(self):
        self.assertEqual(dm.director_mode_of(10), "program")
        self.assertEqual(dm.director_mode_of(12), "preview")
        self.assertEqual(dm.director_mode_of(13), "director")

    def test_an_undeclared_console_is_a_director(self):
        self.roles["console"].add(14)
        self.assertEqual(dm.director_mode_of(14), "director")

    def test_the_screen_sets(self):
        self.assertEqual(dm.director_program_screens(), [10, 11])
        self.assertEqual(dm.director_preview_screens(), [12])

    def test_only_declared_screens_are_in_the_sets(self):
        # An ordinary bridge console never becomes a target, however many there are.
        self.roles["console"].add(99)
        self.assertNotIn(99, dm.director_program_screens())
        self.assertNotIn(99, dm.director_preview_screens())

    def test_the_summary_counts_both_feeds(self):
        self.assertEqual(dm.director_screen_summary(), "2 program, 1 preview")

    def test_the_summary_says_why_nothing_happens(self):
        # "Send does nothing" is the commonest confusion on this console and the reason is
        # invisible otherwise: there is nowhere for the show to go.
        self.inventory.clear()
        self.roles["console"] = set()
        self.assertIn("no screens", dm.director_screen_summary())


class NameTests(unittest.TestCase):
    def setUp(self):
        self.roles = {"console": {10, 11, 12}}
        self.inventory = {}
        self.restore = _install(self.roles, self.inventory)

    def tearDown(self):
        self.restore()

    def test_the_prefix_follows_the_mode(self):
        self.assertEqual(dm.director_screen_suggest_name(99, "program"), "PROG01")
        self.assertEqual(dm.director_screen_suggest_name(99, "preview"), "PRE01")
        self.assertEqual(dm.director_screen_suggest_name(99, "director"), "DIR01")

    def test_numbering_is_per_prefix(self):
        # PROG01 and PRE01 can both exist - they read as different screens, which is the whole
        # point of naming by mode.
        self.inventory[(10, "CREW_NAME")] = "PROG01"
        self.assertEqual(dm.director_screen_suggest_name(99, "program"), "PROG02")
        self.assertEqual(dm.director_screen_suggest_name(99, "preview"), "PRE01")

    def test_it_takes_the_lowest_free_number(self):
        # A screen that left frees its number. Counting consoles instead would keep climbing.
        self.inventory[(10, "CREW_NAME")] = "PROG01"
        self.inventory[(11, "CREW_NAME")] = "PROG03"
        self.assertEqual(dm.director_screen_suggest_name(99, "program"), "PROG02")

    def test_a_console_does_not_block_its_own_number(self):
        self.inventory[(10, "CREW_NAME")] = "PROG01"
        self.assertEqual(dm.director_screen_suggest_name(10, "program"), "PROG01")

    def test_a_persons_name_does_not_take_a_number(self):
        # The prefix scan reads every console's CREW_NAME, and `common_console_select` writes
        # crew names into that same key - so a bridge crew member must not be able to reserve
        # PROG02 by being called something odd.
        self.inventory[(10, "CREW_NAME")] = "Doug"
        self.inventory[(11, "CREW_NAME")] = "PROGRAM 1"
        self.assertEqual(dm.director_screen_suggest_name(99, "program"), "PROG01")


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.inventory = {(10, "CREW_NAME"): "PROG01"}
        self.restore = _install({"console": {10, 11}}, self.inventory)
        dm.director_mode_set(10, "program")

    def tearDown(self):
        self.restore()

    def test_a_new_declaration_moves_it(self):
        before = dm.director_mode_fingerprint()
        dm.director_mode_set(11, "preview")
        self.assertNotEqual(before, dm.director_mode_fingerprint())

    def test_a_rename_moves_it(self):
        before = dm.director_mode_fingerprint()
        self.inventory[(10, "CREW_NAME")] = "Stream Out"
        self.assertNotEqual(before, dm.director_mode_fingerprint())

    def test_the_fingerprint_ignores_what_a_screen_is_showing(self):
        # The player rewrites CONSOLE_TYPE every time a screen changes item. Watching it would
        # repaint the operator's page every dwell, moving the selection under their hands.
        before = dm.director_mode_fingerprint()
        self.inventory[(10, "CONSOLE_TYPE")] = "cinematic"
        self.assertEqual(before, dm.director_mode_fingerprint())


class DeclarationTests(unittest.TestCase):
    """Declared vs defaulted, and the one-shot that carries a setup across the game starting.

    All of this exists because the entry screen became reachable BEFORE the mission starts. A
    streamer opening four windows declares each one early; the server's Start then reroutes
    every client through `game_started_console`, which walks them into their console the
    ordinary way - straight back to the pin screen. Without the resume flag, setting up early
    would buy nothing at all.
    """

    def setUp(self):
        self.inventory = {}
        self.restore = _install({}, self.inventory)

    def tearDown(self):
        self.restore()

    def test_an_undeclared_console_still_reads_as_director(self):
        # director_mode_of DEFAULTS, which is why it cannot answer "has this console chosen".
        self.assertEqual(dm.director_mode_of(10), "director")
        self.assertFalse(dm.director_mode_declared(10))

    def test_declaring_the_default_mode_still_counts_as_declaring(self):
        # THE CASE director_mode_of CANNOT SEE. Choosing "Director" on the entry screen is a
        # real choice and has to be distinguishable from never having been asked.
        dm.director_mode_set(10, "director")
        self.assertTrue(dm.director_mode_declared(10))

    def test_clearing_undeclares(self):
        dm.director_mode_set(10, "program")
        dm.director_mode_clear(10)
        self.assertFalse(dm.director_mode_declared(10))
        self.assertEqual(dm.director_mode_of(10), "director")

    def test_the_resume_is_one_shot(self):
        # Spent by the first entry, so the START REROUTE skips the pin screen and a later
        # re-pick off the console list does not - which is the only way to change a mode.
        self.assertFalse(dm.director_mode_resume_take(10))
        dm.director_mode_resume_arm(10)
        self.assertTrue(dm.director_mode_resume_take(10))
        self.assertFalse(dm.director_mode_resume_take(10))

    def test_cancel_disarms_the_resume_too(self):
        # Otherwise backing out would leave a flag that skips the very screen just cancelled.
        dm.director_mode_set(10, "program")
        dm.director_mode_resume_arm(10)
        dm.director_mode_clear(10)
        self.assertFalse(dm.director_mode_resume_take(10))

    def test_the_resume_is_per_console(self):
        # Four windows, four independent setups. A shared flag would have one window's Start
        # skip another window's pin screen.
        dm.director_mode_resume_arm(10)
        self.assertFalse(dm.director_mode_resume_take(11))
        self.assertTrue(dm.director_mode_resume_take(10))

    def test_a_declared_screen_is_still_in_its_feed_set(self):
        # The declaration is the same key the feed sets read, so arming and spending the
        # resume must not disturb it - a PROG01 that dropped out of director_program_screens
        # when the game started would simply never receive the show.
        self.inventory[(10, "__ROLES__")] = None
        dm.director_mode_set(10, "program")
        dm.director_mode_resume_arm(10)
        dm.director_mode_resume_take(10)
        self.assertTrue(dm.director_mode_declared(10))
        self.assertEqual(dm.director_mode_of(10), "program")


if __name__ == "__main__":
    unittest.main()
