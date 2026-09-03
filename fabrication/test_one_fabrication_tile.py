"""One Fabrication tile, and it lists everything craftable.

There were two: `//gui/app/fabricate` reading the AMD recipe registry, and
`//gui/app/fabrication` reading item-def `craft_cost` metadata. Both were registered as
ePADD apps, so Engineering carried two tiles for one idea - and in LegendaryMissions and
the TNG missions the second one was EMPTY, since nothing there declares craft_cost.

Deleting the old path was not an option: StormsBeacon's craftables are item defs with
`craft_cost`. So the two sources merged instead. `craft_cost: 8` says exactly what
`Inputs: salvage x8` says, which is what makes it a translation.
"""
import os
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import recipes as R


class _Label:
    """An item def, as `items_get_list()` hands one over."""

    def __init__(self, **fields):
        self.fields = fields

    def get_inventory_value(self, key, default=None):
        return self.fields.get(key, default)


class MergeBase(unittest.TestCase):
    def setUp(self):
        self._saved = dict(R._RECIPES)
        R._RECIPES.clear()
        self._items = []
        self._orig = R._item_craftables
        R._item_craftables = lambda: self._derived()

    def tearDown(self):
        R._item_craftables = self._orig
        R._RECIPES.clear()
        R._RECIPES.update(self._saved)

    def _derived(self):
        out = []
        for lbl in self._items:
            key = lbl.get_inventory_value("key")
            cost = int(lbl.get_inventory_value("craft_cost", 0) or 0)
            if not key or cost <= 0:
                continue
            out.append({"key": key, "name": key, "output": key,
                        "inputs": {"salvage": cost},
                        "time": int(lbl.get_inventory_value("craft_time", 30) or 30),
                        "build_at": "", "program": {}, "properties": {},
                        "defaults": {}, "desc": ""})
        return out

    def item(self, key, craft_cost=0, craft_time=30):
        self._items.append(_Label(key=key, craft_cost=craft_cost,
                                  craft_time=craft_time))


class TestTheMerge(MergeBase):
    def test_AN_ITEM_CRAFTABLE_IS_LISTED(self):
        """StormsBeacon's shape: an item def with a salvage cost and nothing else."""
        self.item("coil", craft_cost=10)
        keys = [r["key"] for r in R.fabrication_recipes()]
        self.assertIn("coil", keys)

    def test_the_cost_becomes_a_salvage_input(self):
        self.item("coil", craft_cost=10, craft_time=45)
        r = next(x for x in R.fabrication_recipes() if x["key"] == "coil")
        self.assertEqual(r["inputs"], {"salvage": 10})
        self.assertEqual(r["time"], 45)
        self.assertEqual(r["output"], "coil")     # the item IS the output

    def test_an_item_with_no_cost_is_not_a_recipe(self):
        """Most items are not craftable; the old screen listed only those with a cost."""
        self.item("rock", craft_cost=0)
        self.assertEqual(R.fabrication_recipes(), [])

    def test_AN_AMD_RECIPE_WINS_ON_A_KEY_CLASH(self):
        """A mission that wrote a real recipe has said more about it than its item def
        can - multi-input costs, a build_at, properties."""
        R.fabrication_add_recipe("coil", output="coil",
                                 inputs={"salvage": 4, "bio_sample": 1}, time=12)
        self.item("coil", craft_cost=999, craft_time=999)
        matches = [r for r in R.fabrication_recipes() if r["key"] == "coil"]
        self.assertEqual(len(matches), 1, "listed twice")
        self.assertEqual(matches[0]["inputs"], {"salvage": 4, "bio_sample": 1})

    def test_both_sources_appear_together(self):
        R.fabrication_add_recipe("beacon", output="Beacon", inputs={"salvage": 8})
        self.item("coil", craft_cost=10)
        keys = sorted(r["key"] for r in R.fabrication_recipes())
        self.assertEqual(keys, ["beacon", "coil"])


class TestTheItemWalkItself(unittest.TestCase):
    """The REAL `_item_craftables`, not the stand-in the merge tests use.

    Those patch it out to test the merging, so without this the extraction - which is
    the half that touches the item system - would be covered by nothing.
    """

    def setUp(self):
        from sbs_utils.procedural import items
        self._orig = items.items_get_list
        self.items_mod = items

    def tearDown(self):
        self.items_mod.items_get_list = self._orig

    def given(self, labels):
        self.items_mod.items_get_list = lambda: labels

    def test_it_reads_the_cost_and_the_time_off_the_item(self):
        self.given([_Label(key="coil", craft_cost=10, craft_time=45)])
        got = R._item_craftables()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["inputs"], {"salvage": 10})
        self.assertEqual(got[0]["time"], 45)

    def test_a_missing_time_falls_back_to_thirty(self):
        self.given([_Label(key="coil", craft_cost=10)])
        self.assertEqual(R._item_craftables()[0]["time"], 30)

    def test_NO_STORY_IS_NOT_AN_ERROR(self):
        """`items_get_list` reaches into the label registry, which does not exist in a
        unit test or before a story compiles. A panel must not take the console down for
        asking too early."""
        def boom():
            raise RuntimeError("no story loaded")
        self.items_mod.items_get_list = boom
        self.assertEqual(R._item_craftables(), [])

    def test_and_neither_is_an_answer_that_is_not_a_list(self):
        """Found by getting the test above wrong: the iteration used to sit OUTSIDE the
        guard, so anything non-iterable coming back raised past it."""
        self.items_mod.items_get_list = lambda: 7
        self.assertEqual(R._item_craftables(), [])

    def test_a_junk_item_is_skipped_not_fatal(self):
        class Bad:
            def get_inventory_value(self, key, default=None):
                raise ValueError("nope")
        self.given([Bad(), _Label(key="coil", craft_cost=5)])
        self.assertEqual([r["key"] for r in R._item_craftables()], ["coil"])


class TestOnlyOneTileIsRegistered(unittest.TestCase):
    def test_the_padd_offers_one_fabrication_app(self):
        here = os.path.dirname(__file__)
        mast = os.path.join(here, "..", "consoles", "epadd.mast")
        with open(mast, encoding="utf-8") as f:
            src = f.read()
        self.assertIn('gui_app_register("fabricate"', src)
        self.assertNotIn('gui_app_register("fabrication"', src,
                         "two Fabrication tiles again")


if __name__ == "__main__":
    unittest.main()
