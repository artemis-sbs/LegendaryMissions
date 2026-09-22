"""Engineering's View tab (consoles/eng_view.py).

These four settings used to be comms buttons on the EPad, a grid object spawned at
`icon_scale 0.01` whose only job was to carry them. The EPad is gone; what must not
be lost with it is the behavior - the same `icon_index` / `icon_scale` writes the old
`epad_*` labels made.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_eng_view
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (first, to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.inventory import set_inventory_value
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.spawn import grid_spawn, player_spawn
from sbs_utils.spaceobject import SpaceObject

from consoles import eng_view as V
from consoles.test_eng_grid_panel import _FakeGuiTask

CID = 77


class ViewBase(unittest.TestCase):
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

    def tearDown(self):
        FrameContext.page = None
        FrameContext.context = None
        SpaceObject.clear()

    def node(self, x, *roles):
        return to_id(grid_spawn(self.ship, f"node{x}", f"node{x}", x, 0, 12,
                                "white", "#," + ",".join(roles)))

    def blob(self, node_id):
        return to_object(node_id).data_set


class TestTheStylesStillDoWhatTheEPadDid(ViewBase):
    def test_room_icons_writes_icon_index_and_half_scale(self):
        room = self.node(1, "room")
        set_inventory_value(room, "icon_index", 42)
        set_inventory_value(room, "icon_scale", 1)
        V.lm_eng_view_apply_rooms(self.ship, "icons")
        self.assertEqual(self.blob(room).get("icon_index", 0), 42)
        self.assertAlmostEqual(self.blob(room).get("icon_scale", 0), 0.5)

    def test_room_circles_writes_the_simple_icon_and_quarter_scale(self):
        room = self.node(1, "room")
        set_inventory_value(room, "simple_icon_index", 7)
        set_inventory_value(room, "icon_scale", 1)
        V.lm_eng_view_apply_rooms(self.ship, "circles")
        self.assertEqual(self.blob(room).get("icon_index", 0), 7)
        self.assertAlmostEqual(self.blob(room).get("icon_scale", 0), 0.25)

    def test_system_diamonds_writes_the_simple_icon(self):
        sysnode = self.node(1, "system")
        set_inventory_value(sysnode, "simple_icon_index", 9)
        set_inventory_value(sysnode, "icon_scale", 1)
        V.lm_eng_view_apply_systems(self.ship, "diamonds")
        self.assertEqual(self.blob(sysnode).get("icon_index", 0), 9)

    def test_a_node_declaring_no_icon_gets_the_pools_fallback(self):
        """97 for rooms, 12 for systems - straight from the epad_* labels."""
        room = self.node(1, "room")
        sysnode = self.node(2, "system")
        V.lm_eng_view_apply_rooms(self.ship, "icons")
        V.lm_eng_view_apply_systems(self.ship, "icons")
        self.assertEqual(self.blob(room).get("icon_index", 0), 97)
        self.assertEqual(self.blob(sysnode).get("icon_index", 0), 12)

    def test_rooms_and_systems_do_not_touch_each_other(self):
        room = self.node(1, "room")
        sysnode = self.node(2, "system")
        # `circles` reads simple_icon_index, not icon_index - set the key the style
        # under test actually consults.
        set_inventory_value(room, "simple_icon_index", 42)
        set_inventory_value(sysnode, "icon_index", 43)
        # NOT "is 0": a grid object's blob carries the icon it was SPAWNED with, so
        # the question is whether applying one pool MOVED the other, not what an
        # untouched node happens to hold.
        before = self.blob(sysnode).get("icon_index", 0)
        V.lm_eng_view_apply_rooms(self.ship, "circles")
        self.assertEqual(self.blob(sysnode).get("icon_index", 0), before,
                         "applying rooms wrote to a system node")
        self.assertEqual(self.blob(room).get("icon_index", 0), 42,
                         "the room pool was not written")


class TestTheStyleIsPerShip(ViewBase):
    """Two engineers on one bridge must not see the interior drawn two ways."""

    def test_the_style_is_remembered(self):
        V.lm_eng_view_apply_rooms(self.ship, "circles")
        self.assertEqual(V.lm_eng_view_room_style(self.ship), "circles")

    def test_a_second_console_on_the_same_ship_reads_the_same_style(self):
        V.lm_eng_view_apply_systems(self.ship, "diamonds")
        mock_sbs.assign_client_to_ship(CID + 1, self.ship)
        self.assertEqual(V.lm_eng_view_system_style(self.ship), "diamonds")

    def test_the_defaults_are_icons(self):
        self.assertEqual(V.lm_eng_view_room_style(self.ship), "icons")
        self.assertEqual(V.lm_eng_view_system_style(self.ship), "icons")

    def test_a_junk_style_falls_back_rather_than_raising(self):
        set_inventory_value(self.ship, V.ROOM_STYLE_KEY, "hexagons")
        self.assertEqual(V.lm_eng_view_room_style(self.ship), "icons")

    def test_applying_a_junk_style_keeps_the_current_one(self):
        V.lm_eng_view_apply_rooms(self.ship, "circles")
        V.lm_eng_view_apply_rooms(self.ship, "hexagons")
        self.assertEqual(V.lm_eng_view_room_style(self.ship), "circles")


class TestTheTabRepaintsWhenAStyleMoves(ViewBase):
    """THE FIELD REPORT, three rounds of it - ending in a screenshot of one button
    showing two labels at once (`idodes>>`, icons drawn over circles).

    A widget re-sent into a region out of band paints wrong. `Button.value` says so
    in a comment that predates all of this:

        # Quirk, this should just be a visual update, but when in a
        # section/region it paints wrong.

    So the button does not repaint itself (CycleButton.mark_value_dirty) and the TAB
    repaints instead, via `TabbedPanel.present`, which brackets with
    send_gui_clear/send_gui_complete. That bracket is the only update a region takes,
    and it is what every other control in this panel already relies on.
    """

    class _Panel:
        def __init__(self, cid):
            self.client_id = cid

    def test_a_changed_style_asks_for_a_repaint(self):
        panel = self._Panel(CID)
        V.lm_eng_view_tick(panel)
        V.lm_eng_view_apply_rooms(self.ship, "circles")
        self.assertEqual(V.lm_eng_view_tick(panel), 2,
                         "nothing repaints the tab - the new label never appears")

    def test_a_settled_tab_asks_to_stay(self):
        panel = self._Panel(CID)
        V.lm_eng_view_tick(panel)
        self.assertEqual(V.lm_eng_view_tick(panel), 1)

    def test_a_repaint_is_asked_for_ONCE_per_change(self):
        """Returning 2 every tick would rebuild the tab forever."""
        panel = self._Panel(CID)
        V.lm_eng_view_tick(panel)
        V.lm_eng_view_apply_systems(self.ship, "diamonds")
        self.assertEqual(V.lm_eng_view_tick(panel), 2)
        self.assertEqual(V.lm_eng_view_tick(panel), 1)

    def test_the_tick_never_returns_zero(self):
        panel = self._Panel(CID)
        for _ in range(3):
            self.assertNotEqual(V.lm_eng_view_tick(panel), 0)
        mock_sbs.assign_client_to_ship(CID, 0)
        self.assertNotEqual(V.lm_eng_view_tick(panel), 0)

    def test_the_tab_does_not_park_widgets_on_the_page(self):
        """Inside a tab's show() `FrameContext.page` is a throwaway `SubPage`
        (`TabbedPanel.present_panel`), so anything parked there is gone by the time a
        tick looks for it - measured as `parked buttons: [None, None]`."""
        V.lm_eng_view_show(CID, 0, 0, 230, 400)
        parked = [a for a in dir(self.page) if "button" in a.lower()
                  and a.startswith("_lm_eng_view")]
        self.assertEqual(parked, [])


class TestTheControlIsACycleButton(ViewBase):
    """This tab has worn three controls. These stop the two rejected ones returning.

    * `gui_radio` renders each option as `send_gui_checkbox` - a checkbox glyph per
      option, wrong semantic for an exclusive choice and wrong for a finger.
    * A chip rail is a horizontal listbox: one touch target per option, a poor
      trade in a 230px column.

    The chips were also reported as not toggling. That was `lm_eng_view_tick`
    rebuilding the tab on every press, not the chips - see TestTheTabNeverRedrawsItself.
    """

    def _draw(self):
        V.lm_eng_view_show(CID, 0, 0, 230, 400)
        self.page.present(FakeEvent(CID, "gui_present"))

    def test_the_tab_builds_no_checkbox(self):
        sent = []
        orig = mock_sbs.send_gui_checkbox
        mock_sbs.send_gui_checkbox = lambda *a, **k: sent.append(a)
        try:
            self._draw()
        finally:
            mock_sbs.send_gui_checkbox = orig
        self.assertEqual(sent, [], "the View tab is drawing checkboxes again")

    def test_the_tab_builds_no_listbox(self):
        """A chip rail would show up as a slider or per-item click regions; the
        listbox class itself is the cheaper thing to watch for."""
        from sbs_utils.pages.widgets.layout_listbox import LayoutListbox
        made = []
        orig = LayoutListbox.__init__

        def _spy(self, *a, **k):
            made.append(self)
            return orig(self, *a, **k)

        LayoutListbox.__init__ = _spy
        try:
            self._draw()
        finally:
            LayoutListbox.__init__ = orig
        self.assertEqual(made, [], "the View tab is back to chips")

    def test_it_builds_one_cycle_button_per_pool(self):
        from sbs_utils.pages.layout.cycle_button import CycleButton
        made = []
        orig = CycleButton.__init__

        def _spy(self, *a, **k):
            made.append(self)
            return orig(self, *a, **k)

        CycleButton.__init__ = _spy
        try:
            self._draw()
        finally:
            CycleButton.__init__ = orig
        self.assertEqual(len(made), 2, "one control per pool, no more")
        self.assertEqual([b.states for b in made],
                         [list(V.ROOM_STYLES), list(V.SYSTEM_STYLES)])

    def test_the_buttons_open_on_the_style_in_force(self):
        from sbs_utils.pages.layout.cycle_button import CycleButton
        V.lm_eng_view_apply_rooms(self.ship, "circles")
        V.lm_eng_view_apply_systems(self.ship, "diamonds")
        made = []
        orig = CycleButton.__init__

        def _spy(self, *a, **k):
            made.append(self)
            return orig(self, *a, **k)

        CycleButton.__init__ = _spy
        try:
            self._draw()
        finally:
            CycleButton.__init__ = orig
        self.assertEqual([b.state for b in made], ["circles", "diamonds"])

    def test_both_pools_offer_exactly_two_styles(self):
        """A cycle button stays the right control while the choice is small; past a
        handful, cycling to the far end is worse than a dropdown."""
        self.assertEqual(len(V.ROOM_STYLES), 2)
        self.assertEqual(len(V.SYSTEM_STYLES), 2)

    def test_every_state_label_is_ascii(self):
        for label in list(V.ROOM_STYLES) + list(V.SYSTEM_STYLES):
            label.encode("ascii")


class TestPressingItChangesTheView(ViewBase):
    """The whole loop: press -> the ship's style moves -> the interior nodes follow."""

    def _buttons(self):
        from sbs_utils.pages.layout.cycle_button import CycleButton
        made = []
        orig = CycleButton.__init__

        def _spy(self, *a, **k):
            made.append(self)
            return orig(self, *a, **k)

        CycleButton.__init__ = _spy
        try:
            V.lm_eng_view_show(CID, 0, 0, 230, 400)
            self.page.present(FakeEvent(CID, "gui_present"))
        finally:
            CycleButton.__init__ = orig
        return made

    def _press(self, button):
        """Press it the way a press actually reaches this widget.

        The handler is attached with `gui_message_callback`, so it hangs off the
        LAYOUT item as `on_message_cb`, and `Column.on_message` invokes it and
        returns. The page's other half - the runtime node it looks up in `tag_map`
        (`maststorypage.py:1575-1582`) - is INERT for this widget, because
        `gui_cycle_button` was given no `on_press`. This asserts that rather than
        assuming it: if somebody moves the handler to `on_press` later, the widget
        stops being driven this way and this test should say so.
        """
        registry = self.page.pending_tag_map or self.page.tag_map or {}
        entry = registry.get(button.tag)
        self.assertIsNotNone(entry, "the button was never registered on the page")
        layout_item, runtime_node = entry
        self.assertIs(layout_item, button)
        self.assertTrue(runtime_node is None or runtime_node.is_inert(),
                        "the live handler moved to on_press - press through the page")
        self.assertIsNotNone(getattr(button, "on_message_cb", None),
                             "no callback attached - a press would do nothing")
        event = FakeEvent(CID, "gui_message")
        event.sub_tag = button.tag
        button.on_message(event)

    def test_a_press_cycles_the_ships_room_style(self):
        self.node(1, "room")
        rooms, _systems = self._buttons()
        self._press(rooms)
        self.assertEqual(V.lm_eng_view_room_style(self.ship), "circles")

    def test_two_presses_come_back_to_where_it_started(self):
        self.node(1, "room")
        rooms, _systems = self._buttons()
        self._press(rooms)
        self._press(rooms)
        self.assertEqual(V.lm_eng_view_room_style(self.ship), "icons")

    def test_a_press_redraws_the_interior_nodes(self):
        room = self.node(1, "room")
        set_inventory_value(room, "simple_icon_index", 7)
        set_inventory_value(room, "icon_scale", 1)
        rooms, _systems = self._buttons()
        self._press(rooms)
        self.assertEqual(self.blob(room).get("icon_index", 0), 7)

    def test_the_room_button_does_not_move_the_system_style(self):
        self.node(1, "room")
        self.node(2, "system")
        rooms, _systems = self._buttons()
        self._press(rooms)
        self.assertEqual(V.lm_eng_view_system_style(self.ship), "icons")


if __name__ == "__main__":
    unittest.main()
