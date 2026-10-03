"""An author's Siege boss lives where an update cannot delete it.

Bosses were found only in the running mission's `maps/bosses/`, and `sbs fetch` deletes and
re-extracts a mission folder - so a boss an author dropped into LegendaryMissions was gone
after the next update. Siege now also reads `<missions>/common_data/bosses/`, beside the
saves.

The real scan, against real files in two temp folders standing in for the two places.

    PYTHONPATH=../sbs_utils python -m unittest maps.test_boss_shared_folder
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
SHIPPED = os.path.join(HERE, "bosses")

MINE = """# [{display}]({key})
---
Boss
Trigger: enemies_low
Low: 50%
Fleets: 2
Named: Morrigan kralien_dreadnought
---
A boss of the author's own.
"""


class _Listen(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class SharedFolderTests(unittest.TestCase):
    def setUp(self):
        self.shared = tempfile.mkdtemp(prefix="lm_shared_bosses_")
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

    def mine(self, file_name, display, key="mine"):
        with open(os.path.join(self.shared, file_name), "w", encoding="utf-8") as f:
            f.write(MINE.format(display=display, key=key))

    def scan(self):
        return SB.siege_boss_scan(force=True)

    def test_the_shipped_bosses_are_still_found(self):
        self.assertIn("Warlord", self.scan())

    def test_a_boss_in_the_shared_folder_is_in_the_list(self):
        self.mine("corsair_queen.amd", "Corsair Queen")
        self.assertIn("Corsair Queen", self.scan())
        self.assertIn("Corsair Queen", SB.siege_boss_list())

    def test_its_config_is_read_like_any_other(self):
        self.mine("corsair_queen.amd", "Corsair Queen")
        self.scan()
        self.assertEqual(SB.siege_boss_fleet_count("Corsair Queen"), 2)
        self.assertEqual(SB.siege_boss_low_pct("Corsair Queen"), 0.5)
        self.assertEqual(SB.siege_boss_named("Corsair Queen"),
                         [("Morrigan", "kralien_dreadnought")])

    def test_an_authors_boss_with_a_taken_name_wins_and_says_so(self):
        self.mine("my_warlord.amd", "Warlord", key="my_warlord")
        bosses = self.scan()
        self.assertEqual(bosses["Warlord"].get("key"), "my_warlord")
        said = [l for l in self.heard.lines if "my_warlord.amd" in l and "Warlord" in l]
        self.assertEqual(len(said), 1)

    def test_an_empty_shared_folder_changes_nothing(self):
        with_none = sorted(self.scan())
        shipped = sorted(f for f in os.listdir(SHIPPED) if f.endswith(".amd"))
        self.assertEqual(len(with_none), len(shipped))
        self.assertEqual(self.heard.lines, [])

    def test_a_missing_shared_folder_is_not_an_error(self):
        shutil.rmtree(self.shared)
        self.assertIn("Warlord", self.scan())

    def test_a_file_that_is_not_amd_is_ignored(self):
        with open(os.path.join(self.shared, "notes.txt"), "w") as f:
            f.write("not a boss")
        self.assertEqual(len(self.scan()),
                         len([f for f in os.listdir(SHIPPED) if f.endswith(".amd")]))


class TheFolderIsBesideTheSavesTests(unittest.TestCase):
    def test_it_is_under_common_data(self):
        folder = SB.siege_boss_shared_folder()
        self.assertEqual(os.path.basename(folder), "bosses")
        self.assertEqual(os.path.basename(os.path.dirname(folder)), "common_data")

    def test_it_is_not_inside_the_mission(self):
        folder = os.path.normcase(os.path.abspath(SB.siege_boss_shared_folder()))
        mission = os.path.normcase(os.path.abspath(os.path.dirname(HERE)))
        self.assertFalse(folder.startswith(mission + os.sep))


if __name__ == "__main__":
    unittest.main()
