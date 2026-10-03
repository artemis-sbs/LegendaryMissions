"""The shipped boss files lint clean, and the two first-boss mistakes do not.

Runs against the REAL `lm_amd.py` declaration and the REAL files in `maps/bosses/`, because
a library test that registers its own `named_hulls` field proves the rule and nothing
about whether LM's `Named:` is actually held to it.

    PYTHONPATH=../sbs_utils python -m unittest maps.test_boss_lint
"""
import glob
import os
import shutil
import tempfile
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

from sbs_utils.procedural.amd_lint import amd_lint
from sbs_utils.procedural.amd_schema import (amd_vocabulary_snapshot,
                                             amd_vocabulary_restore)
from sbs_utils.procedural.amd_vocab import load_mission_vocabulary

LM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOSSES = os.path.join(LM, "maps", "bosses")
BOSS_CODES = ("hull-name-shape", "unknown-hull", "duplicate-boss-name")


class BossLintTests(unittest.TestCase):
    # ONCE PER CLASS, not per test. `lm_amd.py` registers its fields when it is imported,
    # and a module is only imported once per process - so a per-test restore takes the
    # vocabulary away and the next test's load cannot put it back.
    @classmethod
    def setUpClass(cls):
        cls._snap = amd_vocabulary_snapshot()
        load_mission_vocabulary(LM)

    @classmethod
    def tearDownClass(cls):
        amd_vocabulary_restore(cls._snap)

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="lm_boss_lint_")
        for path in glob.glob(os.path.join(BOSSES, "*.amd")):
            shutil.copy(path, self.folder)

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def _boss_findings(self, path):
        return [f for f in amd_lint(file_path=path) if f.code in BOSS_CODES]

    def _copy_of_warlord(self, name, edit=None):
        with open(os.path.join(BOSSES, "warlord.amd"), encoding="utf-8") as f:
            text = f.read()
        if edit:
            old, new = edit
            self.assertIn(old, text)
            text = text.replace(old, new)
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_every_shipped_boss_is_clean(self):
        shipped = sorted(glob.glob(os.path.join(BOSSES, "*.amd")))
        self.assertGreaterEqual(len(shipped), 4)
        for path in shipped:
            self.assertEqual(self._boss_findings(path), [], os.path.basename(path))

    def test_a_warlord_copied_and_not_renamed_is_flagged(self):
        copy = self._copy_of_warlord("corsair_queen.amd")
        got = self._boss_findings(copy)
        self.assertEqual([f.code for f in got], ["duplicate-boss-name"])
        self.assertIn("warlord.amd", got[0].message)

    def test_a_two_word_flagship_name_is_flagged(self):
        copy = self._copy_of_warlord(
            "corsair_queen.amd",
            edit=("# [Warlord](warlord)", "# [Corsair Queen](corsair_queen)"))
        with open(copy, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Named: Warlord kralien_dreadnought", text)
        with open(copy, "w", encoding="utf-8") as f:
            f.write(text.replace("Named: Warlord kralien_dreadnought",
                                 "Named: Iron Duke kralien_dreadnought"))
        got = self._boss_findings(copy)
        self.assertEqual([f.code for f in got], ["hull-name-shape"])
        self.assertIn("Iron_Duke kralien_dreadnought", got[0].message)

    def test_a_properly_renamed_copy_is_clean(self):
        copy = self._copy_of_warlord(
            "corsair_queen.amd",
            edit=("# [Warlord](warlord)", "# [Corsair Queen](corsair_queen)"))
        self.assertEqual(self._boss_findings(copy), [])


if __name__ == "__main__":
    unittest.main()
