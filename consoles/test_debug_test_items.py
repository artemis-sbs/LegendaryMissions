"""The debug console's "Test Items" plan.

What is worth pinning is not the code but the PROMISE the button makes: drop every
non-upgrade item, and drop enough of the Fabricator's raw materials to build a few
beacons. Both halves have failed silently before - `Test Upgrades` next door still
hardcodes nine keys and has missed `hacking_virus` since it was added, and the beacon
materials themselves shipped named-by-a-recipe-but-produced-by-nothing (PRM-13, see
fabrication/test_inputs_have_a_source.py).

Registry is stubbed rather than booted: the plan's job is to read whatever is registered,
so a fake registry tests it more honestly than a real one, and stays sub-second.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_debug_test_items
"""
import unittest

from sbs_utils.procedural import items as items_mod

from consoles.debug import debug_test_item_plan


class _Label:
    """The two calls debug_test_item_plan makes on a label."""

    def __init__(self, key, type_):
        self._v = {"key": key, "type": type_}

    def get_inventory_value(self, name, default=None):
        return self._v.get(name, default)


# One of each shape LegendaryMissions actually registers.
REGISTRY = [
    _Label("carapaction_coil", "item/upgrade/defense"),
    _Label("haplix_overcharger", "item/upgrade/weapons"),
    _Label("salvage", "item/resource/salvage"),
    _Label("bio_sample", "item/resource/bio"),
    _Label("hidens_powercell", "item/resource/energy"),
    _Label("hacking_virus", "item/trap/hack"),
    _Label("escape-pod", "item/quest/rescue"),
    _Label("ore", "item/trade/ore"),
    _Label("turret_kit_beam", "item/deployable/turret"),
    _Label("torp_bay", "item/loadout/weapons"),
]


class TestDebugTestItemPlan(unittest.TestCase):
    def setUp(self):
        self._all = items_mod.items_get_list
        self._cat = items_mod.items_of_category
        items_mod.items_get_list = lambda: list(self.registry)
        items_mod.items_of_category = lambda c: [
            l for l in self.registry
            if c in l.get_inventory_value("type", "").split("/")]
        self.registry = list(REGISTRY)

    def tearDown(self):
        items_mod.items_get_list = self._all
        items_mod.items_of_category = self._cat

    def totals(self, plan):
        out = {}
        for d in plan:
            out[d["key"]] = out.get(d["key"], 0) + d["qty"]
        return out

    def test_upgrades_are_left_to_the_other_button(self):
        keys = self.totals(debug_test_item_plan())
        self.assertNotIn("carapaction_coil", keys)
        self.assertNotIn("haplix_overcharger", keys)

    def test_every_other_registered_item_is_dropped(self):
        keys = self.totals(debug_test_item_plan())
        for k in ("salvage", "bio_sample", "hidens_powercell", "hacking_virus",
                  "escape-pod", "ore", "turret_kit_beam", "torp_bay"):
            self.assertIn(k, keys, f"{k} is registered but the plan never drops it")

    def test_enough_materials_for_a_few_beacons(self):
        """The actual promise. Costs are from fabrication/recipes.amd."""
        got = self.totals(debug_test_item_plan())
        # 3x Sensor (8) + 1x Sensor Long (16) + 2x Bio (5 + 1 bio_sample) + Coolant (4)
        self.assertGreaterEqual(got["salvage"], 3 * 8 + 16 + 2 * 5 + 4)
        self.assertGreaterEqual(got["bio_sample"], 2)

    def test_bulk_arrives_as_caches_not_as_sixty_objects(self):
        plan = debug_test_item_plan()
        salvage = [d for d in plan if d["key"] == "salvage"]
        self.assertLessEqual(len(salvage), 4, "one object per unit is the grind qty= exists to remove")
        self.assertTrue(all(d["qty"] > 1 for d in salvage))

    def test_non_bulk_items_drop_one_each(self):
        plan = debug_test_item_plan()
        for d in plan:
            if d["key"] not in ("salvage", "bio_sample"):
                self.assertEqual(d["qty"], 1)

    def test_materials_come_first(self):
        """They are what the button is for, so they land nearest the ship."""
        plan = debug_test_item_plan()
        first = {d["key"] for d in plan[:len(plan) - 6]}
        self.assertEqual(first, {"salvage", "bio_sample"})

    def test_fabrication_addon_absent_is_not_an_error(self):
        """A mission without the fabrication addon has no salvage to offer."""
        self.registry = [l for l in REGISTRY
                         if l.get_inventory_value("key") not in ("salvage", "bio_sample")]
        keys = self.totals(debug_test_item_plan())
        self.assertNotIn("salvage", keys)
        self.assertIn("ore", keys)

    def test_quantities_are_tunable(self):
        got = self.totals(debug_test_item_plan(salvage=10, bio=1, cache=5))
        self.assertEqual(got["salvage"], 10)
        self.assertEqual(got["bio_sample"], 1)


if __name__ == "__main__":
    unittest.main()
