"""A boss file with a value the game cannot read is left out of the list, and says why.

Found by the lesson "A Siege boss, part 2". Each of these was lint clean and did something
different, none of it said:

  * `Trigger: enemy_low`            the boss never arrived
  * `Low: forty percent`            the game stopped on the runtime-error page 4 s in
  * `Difficulty: +two`              the same, at the moment the boss arrived
  * `Fleets: three`, `Wave: soon`   the file was unreadable, and the Boss list offered an
                                    entry called "Could not read this document"
  * `Low: 40` (the sign left off)   forty TIMES the raiders: the boss arrived at once

The real scan, against real files in a temp folder standing in for the author's own.

    PYTHONPATH=../sbs_utils python -m unittest maps.test_boss_values
"""
import logging
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import siege_boss as SB

HERE = os.path.dirname(os.path.abspath(__file__))

GOOD = """# [Corsair Queen](corsair_queen)
---
Boss
Trigger: enemies_low
Low: 40%
Flies: 75% Pirate, 25% Kralien
Fleets: 3
Difficulty: +2
Named: Morrigan pirate_brigantine, Badb pirate_strongbow
---
She waits until the raiders thin.
"""


class _Listen(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class BossValueTests(unittest.TestCase):
    def setUp(self):
        self.shared = tempfile.mkdtemp(prefix="lm_boss_values_")
        self.addCleanup(shutil.rmtree, self.shared, ignore_errors=True)
        self._real = (SB.get_mission_dir_filename, SB.siege_boss_shared_folder)
        SB.get_mission_dir_filename = lambda name: os.path.join(HERE, "bosses")
        SB.siege_boss_shared_folder = lambda: self.shared
        self.addCleanup(self._restore)
        self.heard = _Listen()
        log = logging.getLogger("mast.runtime")
        log.addHandler(self.heard)
        self.addCleanup(log.removeHandler, self.heard)

    def _restore(self):
        SB.get_mission_dir_filename, SB.siege_boss_shared_folder = self._real
        SB._bosses = None

    def scan(self, old=None, new=None):
        text = GOOD if old is None else GOOD.replace(old, new)
        if old is not None:
            assert GOOD.count(old) == 1, old
        with open(os.path.join(self.shared, "corsair_queen.amd"), "w", encoding="utf-8") as f:
            f.write(text)
        del self.heard.lines[:]
        return SB.siege_boss_scan(force=True)

    def said(self):
        return [line for line in self.heard.lines if "corsair_queen.amd" in line]

    def test_the_boss_as_written_is_in_the_list_and_nothing_is_said(self):
        bosses = self.scan()
        self.assertIn("Corsair Queen", bosses)
        self.assertEqual(self.said(), [])
        self.assertEqual(SB.siege_boss_low_pct("Corsair Queen"), 0.4)
        self.assertEqual(SB.siege_boss_fleet_count("Corsair Queen"), 3)
        self.assertEqual(SB.siege_boss_difficulty("Corsair Queen", 5), 7)

    def test_every_shipped_boss_is_still_offered(self):
        bosses = self.scan()
        for name in ("Warlord", "Ragnarok", "Infestation", "Continuous"):
            self.assertIn(name, bosses)

    def test_a_value_the_game_cannot_read_leaves_the_boss_out_and_names_the_line(self):
        for old, new in (("Trigger: enemies_low", "Trigger: enemy_low"),
                         ("Low: 40%", "Low: forty percent"),
                         ("Fleets: 3", "Fleets: three"),
                         ("Fleets: 3", "Fleets: -1"),
                         ("Difficulty: +2", "Difficulty: +two"),
                         ("Difficulty: +2", "Difficulty: hard"),
                         ("Difficulty: +2", "Difficulty: 0"),
                         ("Difficulty: +2", "Difficulty: 7.5"),
                         ("Fleets: 3", "Fleets: 3\nWave: soon")):
            with self.subTest(new=new):
                bosses = self.scan(old, new)
                self.assertNotIn("Corsair Queen", bosses)
                self.assertNotIn("Could not read this document", bosses)
                said = self.said()
                self.assertEqual(len(said), 1, said)
                self.assertIn(new.split("\n")[-1], said[0])
                self.assertIn("Warlord", bosses)         # the rest of the list is intact

    def test_values_that_are_fine(self):
        for old, new, check in (
                ("Low: 40%", "Low: 100%", lambda: SB.siege_boss_low_pct("Corsair Queen") == 1.0),
                ("Low: 40%", "Low: 0.4", lambda: SB.siege_boss_low_pct("Corsair Queen") == 0.4),
                ("Fleets: 3", "Fleets: 0", lambda: SB.siege_boss_fleet_count("Corsair Queen") == 0),
                ("Difficulty: +2", "Difficulty: 11",
                 lambda: SB.siege_boss_difficulty("Corsair Queen", 5) == 11),
                ("Difficulty: +2", "Difficulty: -3",
                 lambda: SB.siege_boss_difficulty("Corsair Queen", 5) == 2),
                ("Trigger: enemies_low", "Trigger: Continuous",
                 lambda: SB.siege_boss_trigger("Corsair Queen") == "continuous")):
            with self.subTest(new=new):
                self.assertIn("Corsair Queen", self.scan(old, new))
                self.assertEqual(self.said(), [])
                self.assertTrue(check())

    def test_the_sign_left_off_low_is_still_a_percentage(self):
        self.assertIn("Corsair Queen", self.scan("Low: 40%", "Low: 40"))
        self.assertEqual(SB.siege_boss_low_pct("Corsair Queen"), 0.4)

    def test_a_hook_that_names_no_label_is_left_out_and_said(self):
        """`Hook: corsair_queen_hok` stopped the game on the runtime-error page as the
        boss arrived. The label table is the story's own (`FrameContext.mast.labels`)."""
        from sbs_utils.helpers import FrameContext

        class _Story:
            labels = {"corsair_queen_hook": object(), "biomech_infestation": object()}

        self.addCleanup(setattr, FrameContext, "mast", FrameContext.mast)
        FrameContext.mast = _Story()
        self.scan("Named: Morrigan pirate_brigantine, Badb pirate_strongbow",
                  "Named: Morrigan pirate_brigantine\nHook: corsair_queen_hok")
        del self.heard.lines[:]
        self.assertEqual(SB.siege_boss_hook_ready("Corsair Queen"), "")
        said = [line for line in self.heard.lines if "corsair_queen_hok" in line]
        self.assertEqual(len(said), 1, self.heard.lines)

        self.scan("Named: Morrigan pirate_brigantine, Badb pirate_strongbow",
                  "Named: Morrigan pirate_brigantine\nHook: corsair_queen_hook")
        del self.heard.lines[:]
        self.assertEqual(SB.siege_boss_hook_ready("Corsair Queen"), "corsair_queen_hook")
        self.assertEqual(self.heard.lines, [])

    def test_a_boss_with_no_hook_has_none(self):
        self.scan()
        self.assertEqual(SB.siege_boss_hook_ready("Corsair Queen"), "")
        self.assertEqual(self.said(), [])

    def test_a_file_that_is_not_a_record_at_all_is_not_offered_as_a_boss(self):
        with open(os.path.join(self.shared, "broken.amd"), "w", encoding="utf-8") as f:
            f.write("# [Broken](broken\n---\nBoss\nTrigger enemies_low\n")
        bosses = SB.siege_boss_scan(force=True)
        self.assertNotIn("Could not read this document", bosses)
        self.assertIn("Warlord", bosses)


if __name__ == "__main__":
    unittest.main()
