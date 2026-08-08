"""Every recipe input must name a REGISTERED item - or the recipe cannot be built.

This is the check that was missing when Peacetime Remastered shipped an impossible job
(PRM-13). `Sensor Beacon` wanted `salvage x8` and `Bio Beacon` wanted `bio_sample x1`, and
NEITHER was an item: nothing spawned one, no market stocked one, nothing granted one. The
fabricator could only ever spend a material that did not exist, so three jobs asking for a
beacon could not be completed, and every unit test here passed the whole time - because
they all test PARSING, and the strings parsed fine.

An item existing is what makes a material obtainable at all: item pickups credit the
holder's inventory under the item's own key (the key the fabricator reads), and any item
with a positive price is stocked by every station market.

Deliberately STATIC - it reads the repo's files rather than booting a sim, so it stays
sub-second and cannot be defeated by a mission that happens not to load an addon.

    PYTHONPATH=../sbs_utils python -m unittest fabrication.test_inputs_have_a_source
"""
import os
import re
import unittest

LM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# `type: item/<category>/...` followed (within its metadata fence) by `key: <k>`.
_ITEM_BLOCK = re.compile(
    r"type:\s*item/[^\n]*\n(?:[^\n]*\n){0,12}?\s*key:\s*([A-Za-z0-9_]+)")
_INPUTS = re.compile(r"^\s*Inputs:\s*(.+)$", re.MULTILINE)
_ONE_INPUT = re.compile(r"([A-Za-z0-9_]+)\s*x\s*\d+")


def _registered_item_keys():
    keys = set()
    for root, _dirs, files in os.walk(LM):
        if "__pycache__" in root or os.sep + "." in root:
            continue
        for f in files:
            if not f.endswith((".mast", ".amd")):
                continue
            path = os.path.join(root, f)
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            keys.update(_ITEM_BLOCK.findall(text))
    return keys


def _recipe_inputs():
    """{input key: [recipe files]} across every recipe fence in the repo."""
    wanted = {}
    for root, _dirs, files in os.walk(LM):
        if "__pycache__" in root:
            continue
        for f in files:
            if not f.endswith(".amd"):
                continue
            path = os.path.join(root, f)
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if "Output:" not in text:
                continue                       # not a recipe document
            for line in _INPUTS.findall(text):
                for key in _ONE_INPUT.findall(line):
                    wanted.setdefault(key, []).append(os.path.relpath(path, LM))
    return wanted


class RecipeInputsAreObtainableTests(unittest.TestCase):
    def test_the_scan_found_something(self):
        """Guards the premise: a regex that silently matches nothing would make the real
        test below pass forever."""
        self.assertIn("salvage", _registered_item_keys())
        self.assertIn("salvage", _recipe_inputs())

    def test_every_recipe_input_is_a_registered_item(self):
        items = _registered_item_keys()
        wanted = _recipe_inputs()
        missing = {k: v for k, v in wanted.items() if k not in items}
        self.assertEqual({}, missing,
                         "recipe inputs that no item defines - unobtainable, so the "
                         "recipe cannot be built and any job needing it is impossible: "
                         f"{missing}")


if __name__ == "__main__":
    unittest.main()
