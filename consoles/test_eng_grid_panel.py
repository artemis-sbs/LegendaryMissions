"""Engineering's right-column panel (consoles/eng_grid_panel.py).

This file is not optional. `TabbedPanel.present_panel` wraps every `show()` in a
try/except that only PRINTS the traceback, so a tab that raises renders as an EMPTY
TAB on the console - it looks like a layout problem, never like an error. Calling
each show() directly is the only thing that turns that back into a failure.

The other half is the tick contract: 0 = done, 1 = stay, 2 = redraw, and a 0 sends
the panel back to its default tab. A tab that returns 0 by accident would yank the
engineer off Orders once a second, which is also silent. Every tick is pinned
against every state, including the empty ones.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest consoles.test_eng_grid_panel
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs

# ai/grid_ai.py does a bare `import sbs`, the way every mission module does. The
# engine supplies that; headless, the mock stands in - the mission runner does the
# same thing before it loads a mission.
sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.agent import Agent

from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.roles import add_role
from sbs_utils.procedural.links import link
from sbs_utils.procedural.spawn import grid_spawn, player_spawn
from sbs_utils.procedural.inventory import set_inventory_value
from sbs_utils.procedural import work_orders as W

from consoles import eng_grid_panel as P
from ai import grid_ai as G

# The shared namespace is keyed by LIB_NAME, so `consoles` and `ai` are two separate
# namespaces and a bare-name call between them is a NameError once LM is packaged as
# mastlibs - which is how it ships. eng_grid_panel reaches it through MastGlobals, the
# one table both mastlibs share, so the test registers it there rather than assigning a
# module attribute nothing reads any more.
from sbs_utils.mast.mast_globals import MastGlobals
MastGlobals.globals["grid_selected_markdown"] = G.grid_selected_markdown

CID = 1234


class _FakeMain:
    def __init__(self, page):
        self.page = page


class _FakeGuiTask:
    def __init__(self, page):
        self.main = _FakeMain(page)

    def set_variable(self, *a, **k):
        pass

    def get_variable(self, *a, **k):
        return None

    def compile_and_format_string(self, s):
        return s


class _FakePanel:
    """Stands in for the TabbedPanel a tick is handed. It only ever reads
    `client_id` and carries the per-tab signature attributes."""
    def __init__(self, cid):
        self.client_id = cid


class PanelBase(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        SpaceObject.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(CID))
        self.page = StoryPage()
        self.page.pending_gui = False
        self.page.client_id = CID
        self.page.gui_task = _FakeGuiTask(self.page)
        FrameContext.page = self.page
        self.ship = to_id(player_spawn(0, 0, 0, "Selene", "tsn", "cruiser"))
        mock_sbs.assign_client_to_ship(CID, self.ship)
        self.nodes = []

    def tearDown(self):
        FrameContext.page = None
        FrameContext.context = None
        SpaceObject.clear()

    # --- fixtures ---------------------------------------------------------
    def node(self, x, *roles):
        """A REAL grid object: grid_objects walks the engine's hull map, so a
        stand-in agent would be invisible to the query under test."""
        go = grid_spawn(self.ship, f"node{x}", f"node{x}", x, 0, 12, "white",
                        "#," + ",".join(roles))
        node_id = to_id(go)
        self.nodes.append(node_id)
        return node_id

    def damcon(self, x, name="DC1"):
        go = grid_spawn(self.ship, name, name, x, 0, 80, "slateblue",
                        "crew,damcons,lifeform")
        dc_id = to_id(go)
        set_inventory_value(dc_id, "color", "slateblue")
        set_inventory_value(dc_id, "HP", 6)
        return dc_id

    def select(self, node_id):
        mock_sbs.sim.get_space_object(self.ship).data_set.set(
            "grid_selected_UID", node_id or 0, 0)

    def shows(self):
        return (P.eng_panel_selected_show, P.eng_panel_orders_show,
                P.eng_panel_systems_show)

    def ticks(self):
        return (P.eng_panel_selected_tick, P.eng_panel_orders_tick,
                P.eng_panel_systems_tick)

    def draw_all(self):
        for show in self.shows():
            show(CID, 0, 0, 200, 227)
        # A listbox calls its item_template at PRESENT time, so show() alone never
        # runs a row. Draw them here too, or a raise inside the template is invisible
        # until a real console presents it.
        for item in P.eng_order_rows(self.ship):
            P._eng_order_item(item)


class TestEveryTabDraws(PanelBase):
    """A tab that raises is an EMPTY tab on screen, never an error - so these are
    the only thing standing between a typo and a blank panel nobody can explain."""

    def test_an_empty_ship_draws_every_tab(self):
        self.draw_all()

    def test_nothing_selected_draws_every_tab(self):
        self.node(0, "weapon", "__undamaged__")
        self.select(None)
        self.draw_all()

    def test_a_selected_room_draws_every_tab(self):
        room = self.node(0, "room", "system", "weapon", "__undamaged__")
        self.select(room)
        self.draw_all()

    def test_a_selected_damaged_room_draws_every_tab(self):
        room = self.node(0, "room", "weapon", "__damaged__")
        self.select(room)
        self.draw_all()

    def test_a_selected_damcon_draws_every_tab(self):
        dc = self.damcon(1)
        self.select(dc)
        self.draw_all()

    def test_a_damcon_with_orders_draws_every_tab(self):
        room = self.node(0, "room", "weapon", "__damaged__")
        dc = self.damcon(1)
        link(dc, "work-order", room)
        self.select(dc)
        self.draw_all()

    def test_a_full_set_of_pools_draws_the_systems_tab(self):
        for i, r in enumerate(("weapon", "engine", "sensor", "shield")):
            self.node(i, r, "__undamaged__")
        self.draw_all()


class TestTickNeverReturnsZero(PanelBase):
    """0 means "this tab is done" and sends the panel to its default tab. Nothing
    here may ever return it - not even with no ship and nothing selected."""

    def assert_never_zero(self):
        panel = _FakePanel(CID)
        for tick in self.ticks():
            for _ in range(3):
                self.assertIn(tick(panel), (P.TICK_STAY, P.TICK_REDRAW))

    def test_with_no_grid_and_no_selection(self):
        self.assert_never_zero()

    def test_with_a_selection(self):
        self.select(self.node(0, "room", "weapon", "__damaged__"))
        self.assert_never_zero()

    def test_with_no_ship_at_all(self):
        mock_sbs.assign_client_to_ship(CID, 0)
        self.assert_never_zero()


class TestTickRedrawsOnlyWhenSomethingMoved(PanelBase):
    def test_a_settled_tab_asks_to_stay(self):
        self.select(self.node(0, "room", "weapon", "__damaged__"))
        panel = _FakePanel(CID)
        for tick in self.ticks():
            tick(panel)                                    # first call primes it
            self.assertEqual(tick(panel), P.TICK_STAY)
            self.assertEqual(tick(panel), P.TICK_STAY)

    def test_a_new_selection_asks_for_a_redraw(self):
        first = self.node(0, "room", "weapon", "__damaged__")
        second = self.node(1, "room", "engine", "__undamaged__")
        panel = _FakePanel(CID)
        self.select(first)
        P.eng_panel_selected_tick(panel)
        self.assertEqual(P.eng_panel_selected_tick(panel), P.TICK_STAY)
        self.select(second)
        self.assertEqual(P.eng_panel_selected_tick(panel), P.TICK_REDRAW)

    def test_a_new_work_order_asks_the_orders_tab_to_redraw(self):
        room = self.node(0, "room", "weapon", "__damaged__")
        dc = self.damcon(1)
        panel = _FakePanel(CID)
        P.eng_panel_orders_tick(panel)
        self.assertEqual(P.eng_panel_orders_tick(panel), P.TICK_STAY)
        link(dc, "work-order", room)
        self.assertEqual(P.eng_panel_orders_tick(panel), P.TICK_REDRAW)

    def test_damage_asks_the_systems_tab_to_redraw(self):
        node = self.node(0, "weapon", "__undamaged__")
        panel = _FakePanel(CID)
        P.eng_panel_systems_tick(panel)
        self.assertEqual(P.eng_panel_systems_tick(panel), P.TICK_STAY)
        Agent.get(node).remove_role("__undamaged__")
        add_role(node, "__damaged__")
        self.assertEqual(P.eng_panel_systems_tick(panel), P.TICK_REDRAW)


class TestOrderRows(PanelBase):
    def test_no_orders_is_an_empty_list_not_a_crash(self):
        self.assertEqual(P.eng_order_rows(self.ship), [])
        self.assertEqual(P.eng_order_rows(None), [])

    def test_two_teams_on_one_node_are_ONE_row(self):
        """The row is the ORDER, not the assignment - otherwise a node two teams
        were sent to reads as two jobs."""
        room = self.node(0, "room", "weapon", "__damaged__")
        link(self.damcon(1, "DC1"), "work-order", room)
        link(self.damcon(2, "DC2"), "work-order", room)
        rows = P.eng_order_rows(self.ship)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["workers"], ["DC1", "DC2"])

    def test_a_damaged_node_is_a_repair_and_a_worn_one_is_maintenance(self):
        broken = self.node(0, "room", "weapon", "__damaged__")
        worn = self.node(1, "room", "engine", "__undamaged__", "__worn__")
        set_inventory_value(worn, "wear", 0.8)
        dc = self.damcon(2)
        W.work_order_add(dc, broken)
        W.work_order_add(dc, worn)
        kinds = {r["name"]: r["kind"] for r in P.eng_order_rows(self.ship)}
        self.assertEqual(kinds["node0"], W.KIND_REPAIR)
        self.assertEqual(kinds["node1"], W.KIND_MAINTAIN)

    def test_repairs_sort_above_maintenance_by_default_priority(self):
        """Not a special case in the sort - a repair defaults to NORMAL and
        maintenance to LOW, so the ordinary priority order puts it there."""
        broken = self.node(0, "room", "weapon", "__damaged__")
        worn = self.node(1, "room", "engine", "__undamaged__", "__worn__")
        set_inventory_value(worn, "wear", 0.8)
        dc = self.damcon(2)
        W.work_order_add(dc, worn)
        W.work_order_add(dc, broken)
        self.assertEqual([r["kind"] for r in P.eng_order_rows(self.ship)],
                         [W.KIND_REPAIR, W.KIND_MAINTAIN])

    def test_a_raised_maintenance_order_sorts_above_a_repair(self):
        broken = self.node(0, "room", "weapon", "__damaged__")
        worn = self.node(1, "room", "engine", "__undamaged__", "__worn__")
        set_inventory_value(worn, "wear", 0.8)
        dc = self.damcon(2)
        W.work_order_add(dc, broken)
        W.work_order_add(dc, worn, priority=W.PRIORITY_CRITICAL)
        self.assertEqual([r["kind"] for r in P.eng_order_rows(self.ship)],
                         [W.KIND_MAINTAIN, W.KIND_REPAIR])

    def test_an_order_on_a_deleted_node_stops_being_listed(self):
        """The Orders tab was built to make the leak visible; now the model closes
        it, so a button that does nothing must not survive on screen."""
        from sbs_utils.procedural.grid import grid_delete_object
        room = self.node(0, "room", "weapon", "__damaged__")
        W.work_order_add(self.damcon(1), room)
        self.assertEqual(len(P.eng_order_rows(self.ship)), 1)
        grid_delete_object(self.ship, room)
        self.assertEqual(P.eng_order_rows(self.ship), [])


class TestSelectedMarkdown(PanelBase):
    """gui_text_area rewrites '#', a leading '-', '[...]', backticks and '^'. A node
    name is engine-supplied ("roomname:x,y"), so none of it can be trusted."""

    def test_nothing_selected_reads_as_empty_not_broken(self):
        self.assertIn("nothing selected", G.grid_selected_markdown(self.ship, None))

    def test_the_body_is_ascii(self):
        dc = self.damcon(1)
        body = G.grid_selected_markdown(self.ship, dc)
        body.encode("ascii")          # raises if anything non-ASCII got in

    def test_markdown_significant_characters_are_stripped_from_names(self):
        for hostile in ("[bay]", "deck^2", "back`tick", "-lead", "#head", "a{b}"):
            safe = G._md_safe(hostile)
            for ch in "[]^`":
                self.assertNotIn(ch, safe, f"{ch!r} survived in {safe!r}")
            self.assertFalse(safe.startswith(("-", "#")), safe)

    def test_a_damcon_body_reports_hp_and_orders(self):
        room = self.node(0, "room", "weapon", "__damaged__")
        dc = self.damcon(1)
        link(dc, "work-order", room)
        body = G.grid_selected_markdown(self.ship, dc)
        self.assertIn("HP 6 of 6", body)
        self.assertIn("Orders 1", body)

    def test_a_damaged_room_says_so(self):
        room = self.node(0, "room", "weapon", "__damaged__")
        self.assertIn("DAMAGED", G.grid_selected_markdown(self.ship, room))

    def test_an_assigned_room_names_its_teams(self):
        room = self.node(0, "room", "weapon", "__damaged__")
        link(self.damcon(1, "DC2"), "work-order", room)
        self.assertIn("DC2", G.grid_selected_markdown(self.ship, room))


class TestCoefficients(PanelBase):
    def test_a_ship_with_no_blob_gives_no_rows(self):
        self.assertEqual(P.eng_coefficient_values(None), [])

    def test_a_missing_coefficient_is_skipped_not_crashed(self):
        """The ENGINE answers None for a blob field nothing has set; the mock hands
        back a typed 0 and REFUSES to store None, so it cannot show us this at all.

        That is the shape behind two shipped crashes, so the guard is pinned against
        a blob that answers the way a real bridge does rather than the way the mock
        does. Without the guard this is `float(None)` - a TypeError inside a show(),
        which present_panel swallows into a blank tab."""
        class _EngineLikeBlob:
            def get(self, key, index=0):
                return None if key == "all_beam_damage_coeff" else 1.0

        original = P.to_blob
        P.to_blob = lambda _id: _EngineLikeBlob()
        try:
            values = dict(P.eng_coefficient_values(self.ship))
        finally:
            P.to_blob = original
        self.assertNotIn("beam", values)
        self.assertEqual(values["warp"], 100)


class TestStyleStringSafety(PanelBase):
    """A grid node is named "<name>:<x>,<y>". That colon is a style-property
    separator, so any dynamic value dropped into a `$text:` unescaped silently
    truncates the label - or eats the styling after it."""

    def test_a_node_name_with_a_colon_survives_into_the_widget(self):
        from sbs_utils.procedural.query import to_object
        room = self.node(0, "room", "weapon", "__damaged__")
        node = to_object(room)
        node.name = "impulse:3,4"
        self.select(room)
        drawn = []
        original = P.gui_text
        P.gui_text = lambda props, style=None: drawn.append(props)
        try:
            P.eng_panel_selected_show(CID, 0, 0, 200, 227)
        finally:
            P.gui_text = original
        header = next(p for p in drawn if "impulse" in p)
        # Backtick-quoted, so the parser reads the whole name as the text.
        self.assertIn("$text:`impulse:3,4`;", header)


class TestOrderRowButtons(PanelBase):
    """Per-row buttons carry their own `data`. An `on gui_message` block registered
    in the loop would capture the loop variable at its LAST value, so every row
    would act on the last order drawn - the for-loop handler trap."""

    def rows_and_buttons(self):
        """Draw each row through the listbox's item_template BY HAND.

        A listbox calls its template at PRESENT time, not while the page is being
        built, so driving `eng_panel_orders_show` alone never runs the row at all -
        which is exactly how a raise inside a template stays invisible until a
        console shows it.
        """
        made = []
        original = P.gui_icon_name_button
        P.gui_icon_name_button = (
            lambda name, color=None, style=None, props=None, data=None,
                   on_press=None, is_sub_task=None:
            made.append({"name": name, "data": data, "press": on_press}) or made[-1])
        try:
            for item in P.eng_order_rows(self.ship):
                P._eng_order_item(item)
        finally:
            P.gui_icon_name_button = original
        return made

    def press(self, button):
        class _Sender:
            data = button["data"]
        button["press"](None, _Sender())

    def test_each_row_gets_its_OWN_target(self):
        a = self.node(0, "room", "weapon", "__damaged__")
        b = self.node(1, "room", "engine", "__damaged__")
        dc = self.damcon(2)
        W.work_order_add(dc, a)
        W.work_order_add(dc, b)
        targets = [x["data"]["target"] for x in self.rows_and_buttons()]
        self.assertEqual(sorted(set(targets)), sorted([a, b]),
                         "every button must not point at the last row drawn")

    def test_raise_bumps_only_that_order(self):
        a = self.node(0, "room", "weapon", "__damaged__")
        b = self.node(1, "room", "engine", "__damaged__")
        dc = self.damcon(2)
        W.work_order_add(dc, a)
        W.work_order_add(dc, b)
        buttons = self.rows_and_buttons()
        raise_a = next(x for x in buttons
                       if x["name"] == "arrow-up" and x["data"]["target"] == a)
        before_b = W.work_order_priority(b)
        self.press(raise_a)
        self.assertEqual(W.work_order_priority(a), W.PRIORITY_HIGH)
        self.assertEqual(W.work_order_priority(b), before_b)

    def test_the_minus_closes_the_order_for_EVERY_team(self):
        room = self.node(0, "room", "weapon", "__damaged__")
        dc1, dc2 = self.damcon(1, "DC1"), self.damcon(2, "DC2")
        W.work_order_add(dc1, room)
        W.work_order_add(dc2, room)
        drop = next(x for x in self.rows_and_buttons() if x["name"] == "minus")
        self.press(drop)
        self.assertEqual(W.work_order_workers(room), set())
        self.assertEqual(P.eng_order_rows(self.ship), [])

    def test_a_button_with_no_data_is_a_no_op_not_a_crash(self):
        class _Sender:
            data = None
        P._eng_order_raise(None, _Sender())
        P._eng_order_drop(None, _Sender())


class TestCoefficientColors(PanelBase):
    """The Effectiveness numbers are colored by tier so the pool that is hurting is
    findable without reading eight of them. They must use the SAME four colors the
    glyph row and the grid use - a number that disagrees with the node it came from
    is worse than an uncolored one."""

    def test_the_four_bands(self):
        from sbs_utils.procedural.internal_damage import (GRID_TUNED_COLOR_DEFAULT,
                                                          GRID_WORN_COLOR_DEFAULT)
        self.assertEqual(P._eng_coefficient_color(110), GRID_TUNED_COLOR_DEFAULT)
        self.assertEqual(P._eng_coefficient_color(100), "springgreen")
        self.assertEqual(P._eng_coefficient_color(83), GRID_WORN_COLOR_DEFAULT)
        self.assertEqual(P._eng_coefficient_color(67), "Crimson")
        self.assertEqual(P._eng_coefficient_color(0), "Crimson")

    def test_each_line_carries_its_own_style(self):
        """`$$<style>; <text>` is per-line and bypasses markdown. If the prefix is
        ever malformed the whole area drops to plain text reading "Document syntax
        issue" - a silent, total loss of the colors."""
        from sbs_utils.pages.layout.text_area import TextArea
        area = TextArea("probe", "x")
        for pct in (110, 100, 83, 67):
            line = f"$$color:{P._eng_coefficient_color(pct)};font:gui-2;  - beam {pct}%"
            style, text = area.get_line_style(line, "_")
            self.assertIsInstance(style, dict, f"{line!r} did not parse as a style")
            self.assertIn(P._eng_coefficient_color(pct), style["style"])
            self.assertIn(f"beam {pct}%", text)
            self.assertIn("-", text, "the dash must survive as literal text")

    def test_the_systems_tab_emits_one_styled_line_per_coefficient(self):
        for i, r in enumerate(("weapon", "engine", "sensor", "shield")):
            self.node(i, r, "__undamaged__")
        drawn = []
        original = P.gui_text_area
        P.gui_text_area = lambda props, style=None, **kw: drawn.append(props)
        try:
            P.eng_panel_systems_show(CID, 0, 0, 200, 227)
        finally:
            P.gui_text_area = original
        body = next((d for d in drawn if "Effectiveness" in d), None)
        self.assertIsNotNone(body, "the Effectiveness block was not drawn")
        styled = [ln for ln in body.split("\n") if ln.startswith("$$")]
        self.assertEqual(len(styled), len(P.eng_coefficient_values(self.ship)))


if __name__ == "__main__":
    unittest.main()
