"""Upgrades console tab list (items/items.py) - the catalog view (PRM-33).

The pre-registry upgrades screen told you what each upgrade DOES without owning one.
This tab lost that: it filtered to `have > 0`, so an item you had never found was
invisible along with its description - even though every item label has carried a
`desc` all along.

`items_upgrade_tab_list(ship, include_unowned=True)` lists the whole activatable
catalog, held items first. Trade goods and quest items stay out either way: they are
cargo and carried objectives, not upgrades.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest items.test_upgrade_tab
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as sbs
from tests.reset_helper import reset_mock
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.a2x.spawn import create_enemy
from sbs_utils.procedural.inventory import set_inventory_value

import sbs_utils.procedural.items as CORE
from items.items import items_upgrade_tab_list


class _Label:
    """Stand in for an `item/` metadata label."""

    def __init__(self, **fields):
        self._f = fields

    def get_inventory_value(self, key, defa=None):
        return self._f.get(key, defa)


CATALOG = [
    _Label(key="carapaction_coil", display_text="Carapaction Coil",
           type="item/upgrade/defense", desc="Reinforces shields for a time.",
           consoles="weapons", duration=300),
    _Label(key="haplix_overcharger", display_text="Haplix Overcharger",
           type="item/upgrade/weapons", desc="Overcharges beams for a time.",
           consoles="weapons", duration=300),
    _Label(key="ore", display_text="Ore", type="item/trade/ore", desc="Raw ore."),
    _Label(key="escape-pod", display_text="Escape Pod", type="item/quest/rescue",
           desc="A life-support capsule."),
]


class UpgradeTabCatalogTests(unittest.TestCase):
    def setUp(self):
        reset_mock(sbs)
        self.ship = to_id(create_enemy(0, 0, 0, "kralien_cruiser", name="P"))
        self._real = CORE.labels_get_type
        CORE.labels_get_type = lambda prefix: list(CATALOG)

    def tearDown(self):
        CORE.labels_get_type = self._real

    def _names(self, rows):
        return [r["name"] for r in rows]

    def test_owned_only_is_still_the_default(self):
        """Existing callers must not suddenly get the whole catalog."""
        set_inventory_value(self.ship, "carapaction_coil", 2)
        rows = items_upgrade_tab_list(self.ship)
        self.assertEqual(["Carapaction Coil"], self._names(rows))

    def test_catalog_lists_items_you_do_not_hold(self):
        rows = items_upgrade_tab_list(self.ship, include_unowned=True)
        self.assertIn("Haplix Overcharger", self._names(rows))

    def test_catalog_carries_the_description(self):
        """The whole point: readable without owning one."""
        rows = items_upgrade_tab_list(self.ship, include_unowned=True)
        row = [r for r in rows if r["key"] == "haplix_overcharger"][0]
        self.assertEqual(0, row["have"])
        self.assertIn("Overcharges beams", row["desc"])

    def test_held_items_sort_first(self):
        set_inventory_value(self.ship, "haplix_overcharger", 1)
        rows = items_upgrade_tab_list(self.ship, include_unowned=True)
        self.assertEqual("Haplix Overcharger", self._names(rows)[0],
                         "the ship's own kit must stay at the top of the tab")

    def test_trade_and_quest_stay_out_of_the_catalog(self):
        """Cargo and carried objectives are not upgrades, owned or not."""
        rows = items_upgrade_tab_list(self.ship, include_unowned=True)
        names = self._names(rows)
        self.assertNotIn("Ore", names)
        self.assertNotIn("Escape Pod", names)

    def test_a_quest_item_you_hold_still_stays_out(self):
        """The escape pod is carried, not activatable - it must not appear as an upgrade."""
        set_inventory_value(self.ship, "escape-pod", 1)
        rows = items_upgrade_tab_list(self.ship, include_unowned=True)
        self.assertNotIn("Escape Pod", self._names(rows))


if __name__ == "__main__":
    unittest.main()
