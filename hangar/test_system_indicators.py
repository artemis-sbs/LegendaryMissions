"""The cockpit's system lights (hangar/hangar.py).

The lights must be a READ of the damage grid, never a second opinion: a node carries
`__damaged__` or `__undamaged__` and the grid draws it in the theme's colors, so these
tests pin that the row uses those roles and those colors and that it only names pools
the craft actually has.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest hangar.test_system_indicators
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs
from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.grid import grid_get_grid_current_theme
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.roles import add_role, remove_role
from sbs_utils.procedural.spawn import grid_spawn, player_spawn

# `hangar` alone is the ADDON FOLDER (a namespace package); the module is inside it.
from hangar import hangar as H


def _grid_node(ship_id, x, y, *roles):
    """A REAL grid object. `grid_objects` walks the engine's hull map, not a link, so a
    stand-in agent would be invisible to exactly the query under test."""
    go = grid_spawn(ship_id, "node", "node", x, y, 12, "white", "#," + ",".join(roles))
    return to_id(go)


class _GridBase(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        SpaceObject.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent())
        self.ship = to_id(player_spawn(0, 0, 0, "Selene", "tsn", "fighter"))
        self.nodes = []
        theme = grid_get_grid_current_theme()
        self.ok = (theme.get("colors") or {}).get("system", "springgreen")
        self.hurt = (theme.get("damage_colors") or {}).get("default", "Crimson")

    def tearDown(self):
        FrameContext.context = None
        SpaceObject.clear()

    def build(self, *pools):
        """pools: (role, undamaged_count, damaged_count). Ids come back in build order,
        so self.nodes[0] is the first node of the first pool."""
        self.nodes = getattr(self, "nodes", [])
        x = len(self.nodes)
        for role_name, well, sick in pools:
            for _ in range(well):
                self.nodes.append(_grid_node(self.ship, x, 0, role_name, "__undamaged__"))
                x += 1
            for _ in range(sick):
                self.nodes.append(_grid_node(self.ship, x, 0, role_name, "__damaged__"))
                x += 1

    def roles(self, states):
        return [s["role"] for s in states]


class SystemStateTests(_GridBase):
    def test_a_craft_with_no_grid_gets_no_lights(self):
        self.assertEqual(H.hangar_system_states(self.ship), [])

    def test_only_pools_the_craft_ACTUALLY_HAS_get_a_light(self):
        """A fighter with no shield rooms must not carry a permanently-green shield
        light for a system it cannot lose."""
        self.build(("weapon", 2, 0), ("engine", 2, 0))
        self.assertEqual(self.roles(H.hangar_system_states(self.ship)),
                         ["weapon", "engine"])

    def test_the_order_is_fixed_so_the_row_never_reshuffles(self):
        self.build(("shield", 1, 0), ("weapon", 1, 0), ("sensor", 1, 0), ("engine", 1, 0))
        self.assertEqual(self.roles(H.hangar_system_states(self.ship)),
                         ["weapon", "engine", "sensor", "shield"])

    def test_an_intact_pool_draws_in_the_theme_SYSTEM_color(self):
        self.build(("engine", 3, 0))
        self.assertEqual(H.hangar_system_states(self.ship)[0]["color"], self.ok)

    def test_ONE_damaged_node_is_enough_to_light_the_system(self):
        """Partial damage is still damage - the pilot should not have to lose a pool
        before the light admits it."""
        self.build(("engine", 3, 1))
        state = H.hangar_system_states(self.ship)[0]
        self.assertEqual(state["color"], self.hurt)
        self.assertEqual((state["hurt"], state["total"]), (1, 4))

    def test_it_reads_the_SAME_roles_the_grid_draws_from(self):
        self.build(("weapon", 1, 0))
        node = self.nodes[0]
        self.assertEqual(H.hangar_system_states(self.ship)[0]["color"], self.ok)
        remove_role(node, "__undamaged__")
        add_role(node, "__damaged__")
        self.assertEqual(H.hangar_system_states(self.ship)[0]["color"], self.hurt)

    def test_repair_puts_the_light_back(self):
        self.build(("sensor", 0, 1))
        node = self.nodes[0]
        self.assertEqual(H.hangar_system_states(self.ship)[0]["color"], self.hurt)
        remove_role(node, "__damaged__")
        add_role(node, "__undamaged__")
        self.assertEqual(H.hangar_system_states(self.ship)[0]["color"], self.ok)


class SignatureTests(_GridBase):
    """`on change hangar_system_signature(...)` is what repaints the row, so the
    signature has to move on exactly the events the row cares about and no others."""

    def test_it_moves_when_a_node_is_damaged(self):
        self.build(("engine", 2, 0))
        before = H.hangar_system_signature(self.ship)
        remove_role(self.nodes[0], "__undamaged__")
        add_role(self.nodes[0], "__damaged__")
        self.assertNotEqual(before, H.hangar_system_signature(self.ship))

    def test_it_holds_still_when_nothing_happened(self):
        """It is polled per cockpit per tick; a signature that churned would repaint
        the console under the pilot every frame."""
        self.build(("engine", 2, 1), ("weapon", 1, 0))
        self.assertEqual(H.hangar_system_signature(self.ship),
                         H.hangar_system_signature(self.ship))

    def test_a_craft_with_no_grid_has_an_empty_signature(self):
        self.assertEqual(H.hangar_system_signature(self.ship), "")


class RowUpdateTests(_GridBase):
    class _FakeIcon:
        def __init__(self):
            self.color = None
            self.is_hidden_by_script = False

        def mark_value_dirty(self, force_layout=False):
            pass

    def test_it_recolors_in_place_rather_than_rebuilding(self):
        self.build(("weapon", 1, 0), ("engine", 1, 0))
        widgets = [self._FakeIcon(), self._FakeIcon()]
        self.assertTrue(H.hangar_system_row_update(widgets, self.ship))
        self.assertEqual([w.color for w in widgets], [self.ok, self.ok])
        remove_role(self.nodes[0], "__undamaged__")
        add_role(self.nodes[0], "__damaged__")
        H.hangar_system_row_update(widgets, self.ship)
        self.assertEqual([w.color for w in widgets], [self.hurt, self.ok])

    def test_a_changed_POOL_COUNT_refuses_so_the_caller_repaints(self):
        """Recoloring a row that no longer matches would paint one system's state onto
        another's glyph - silently, and only after a craft swap."""
        self.build(("weapon", 1, 0))
        widgets = [self._FakeIcon()]
        self.assertTrue(H.hangar_system_row_update(widgets, self.ship))
        self.build(("engine", 1, 0))
        self.assertFalse(H.hangar_system_row_update(widgets, self.ship))

    def test_nothing_drawn_is_not_an_error(self):
        self.assertFalse(H.hangar_system_row_update(None, self.ship))
