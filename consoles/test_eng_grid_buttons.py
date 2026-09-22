"""Engineering's grid orders (consoles/eng_grid_buttons.py).

These are the SAME //comms/grid buttons `grid_control` drew - the routes, the expansion
and the press path are untouched. What changed is who draws them, so what these pin is
the seam: the right rows, the right colours and icons, and a press that carries the
button's own INDEX rather than the row's position.

That index is the whole risk. A button hidden by its `if`, or a `*` already used, is
skipped when drawing but still consumes an index, because `set_buttons` enumerates before
it filters. Send a row number and the engineer orders the wrong repair.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_eng_grid_buttons
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
from sbs_utils.procedural import comms as C
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.spawn import grid_spawn, player_spawn
from sbs_utils.spaceobject import SpaceObject

from consoles import eng_grid_buttons as B
from consoles.test_eng_grid_panel import _FakeGuiTask

CID = 991


class _FakeButton:
    def __init__(self, message, color=None, code=None, used=False):
        self.message = message
        self.color = color
        self.code = code
        self._used = used

    def should_present(self, id_tuple):
        return not self._used


class _FakeTask:
    def __init__(self, truths=None):
        self.truths = truths or {}

    def format_string(self, s):
        return s

    def eval_code(self, code):
        return self.truths.get(code, True)


def _em_of(style):
    """The em part of a box height, which may carry a pixel trim.

    `lm_eng_buttons_box_height` returns "13.00em" on a tall screen and
    "8.20em-10px" on a short one - a real length expression, not concatenation. These
    tests reason in ems, so the trim is split off rather than parsed by `[:-2]`.

    Returns:
        (em, trim_px)
    """
    trim = 0.0
    if "-" in style:
        style, _, px = style.partition("-")
        trim = float(px.removesuffix("px"))
    return float(style.removesuffix("em")), trim


class _Base(unittest.TestCase):
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
        self.promises = C.__dict__["__comms_promises"]
        self.promises.clear()

    def tearDown(self):
        self.promises.clear()
        FrameContext.page = None
        FrameContext.context = None
        SpaceObject.clear()

    def node(self, x=1):
        """A selectable grid node, and select it on the ship the way the console does."""
        node_id = to_id(grid_spawn(self.ship, f"node{x}", f"node{x}", x, 0, 12,
                                   "white", "#,room"))
        mock_sbs.sim.get_space_object(self.ship).data_set.set(
            "grid_selected_UID", node_id, 0)
        return node_id

    def menu(self, node_id, buttons, task=None):
        """An open grid interaction for (ship, node)."""
        class _Prom:
            expanded_buttons = buttons
            path = "comms/grid"
        prom = _Prom()
        prom.task = task or _FakeTask()

        class _Task:
            def get_variable(self, name):
                return prom if name == "BUTTON_PROMISE" else None

        self.promises[(self.ship, node_id)] = _Task()
        return prom


class TheRowsAreTheMenu(_Base):
    def test_the_open_menu_becomes_rows(self):
        self.menu(self.node(), [_FakeButton("do work order now"),
                                _FakeButton("cancel work order")])
        self.assertEqual([r["label"] for r in B.lm_eng_buttons_items(CID)],
                         ["do work order now", "cancel work order"])

    def test_nothing_selected_is_no_rows(self):
        self.assertEqual(B.lm_eng_buttons_items(CID), [])

    def test_a_selection_with_no_open_menu_is_no_rows(self):
        self.node()
        self.assertEqual(B.lm_eng_buttons_items(CID), [])

    def test_a_console_with_no_ship_is_no_rows(self):
        mock_sbs.assign_client_to_ship(CID, 0)
        self.assertEqual(B.lm_eng_buttons_items(CID), [])

    def test_a_hidden_button_is_not_drawn_but_keeps_its_index(self):
        """THE TRAP, at the console's own seam."""
        node = self.node()
        self.menu(node, [_FakeButton("first"),
                         _FakeButton("hidden", code="no"),
                         _FakeButton("third")],
                  task=_FakeTask({"no": False}))
        rows = B.lm_eng_buttons_items(CID)
        self.assertEqual([r["label"] for r in rows], ["first", "third"])
        self.assertEqual([r["index"] for r in rows], [0, 2])


class PressingARow(_Base):
    def _tap(self):
        from sbs_utils.consoledispatcher import ConsoleDispatcher
        seen = []
        orig = ConsoleDispatcher.dispatch_message
        ConsoleDispatcher.dispatch_message = staticmethod(
            lambda event, console: seen.append(event))
        self.addCleanup(lambda: setattr(ConsoleDispatcher, "dispatch_message", orig))
        return seen

    def test_a_press_sends_the_buttons_own_index(self):
        node = self.node()
        self.menu(node, [_FakeButton("first"),
                         _FakeButton("hidden", code="no"),
                         _FakeButton("third")],
                  task=_FakeTask({"no": False}))
        rows = B.lm_eng_buttons_items(CID)
        seen = self._tap()
        # the SECOND drawn row - index 2, not 1
        B.lm_eng_buttons_press({"index": rows[1]["index"], "cid": CID})
        self.assertEqual(seen[0].sub_tag, "2", "a row number was pressed, not an index")

    def test_a_press_names_the_ship_and_the_selected_node(self):
        node = self.node()
        self.menu(node, [_FakeButton("go")])
        seen = self._tap()
        B.lm_eng_buttons_press({"index": 0, "cid": CID})
        self.assertEqual((seen[0].origin_id, seen[0].selected_id), (self.ship, node))

    def test_pressing_with_nothing_selected_does_nothing(self):
        seen = self._tap()
        self.assertFalse(B.lm_eng_buttons_press({"index": 0, "cid": CID}))
        self.assertEqual(seen, [])

    def test_a_press_with_no_data_does_nothing(self):
        """`gui_button` hands a callable its data only when the callable declares a
        REQUIRED parameter. If that contract is ever broken this arrives as None, and
        it must not raise."""
        self.assertFalse(B.lm_eng_buttons_press(None))

    def test_the_handler_takes_exactly_one_required_parameter(self):
        """The contract that makes data arrive at all. Declare none - the house idiom
        of a closure with bound defaults - and gui_button calls it with nothing."""
        import inspect
        params = inspect.signature(B.lm_eng_buttons_press).parameters.values()
        required = [p for p in params if p.default is inspect.Parameter.empty]
        self.assertEqual(len(required), 1, "gui_button would not hand it the data")


class TheRowsRedrawWhenTheMenuMoves(_Base):
    def test_a_settled_menu_reports_the_same_revision(self):
        self.menu(self.node(), [_FakeButton("a")])
        self.assertEqual(B.lm_eng_buttons_revision(CID), B.lm_eng_buttons_revision(CID))

    def test_a_condition_flipping_moves_the_revision(self):
        task = _FakeTask({"cond": True})
        self.menu(self.node(), [_FakeButton("a"), _FakeButton("b", code="cond")],
                  task=task)
        before = B.lm_eng_buttons_revision(CID)
        task.truths["cond"] = False
        self.assertNotEqual(B.lm_eng_buttons_revision(CID), before)

    def test_selecting_a_different_node_moves_the_revision(self):
        """Two nodes can offer menus with identical words - the selection is part of
        the revision so the list still repaints."""
        first = self.node(1)
        self.menu(first, [_FakeButton("set rally point")])
        before = B.lm_eng_buttons_revision(CID)
        second = self.node(2)
        self.menu(second, [_FakeButton("set rally point")])
        self.assertNotEqual(B.lm_eng_buttons_revision(CID), before)

    def test_nothing_selected_has_a_stable_revision(self):
        self.assertEqual(B.lm_eng_buttons_revision(CID), B.lm_eng_buttons_revision(CID))


class WhatARowLooksLike(_Base):
    def test_an_icon_and_colour_come_from_the_format_block(self):
        self.menu(self.node(), [_FakeButton("Fix now", color="red icon:wrench")])
        row = B.lm_eng_buttons_items(CID)[0]
        self.assertEqual((row["color"], row["icon"]), ("red", "wrench"))

    def test_a_plain_button_is_white_with_no_icon(self):
        self.menu(self.node(), [_FakeButton("Workout")])
        row = B.lm_eng_buttons_items(CID)[0]
        self.assertEqual((row["color"], row["icon"]), ("white", None))

    def test_the_row_is_a_touch_target(self):
        """The guarantee that replaced 'the box is big enough' - which the engine
        widget could never promise, and which is why a tall menu was cut off."""
        self.assertGreaterEqual(B.LM_ENG_BUTTON_ROW_EM * 24, 44)

    def test_the_TEMPLATE_puts_the_items_index_on_the_button(self):
        """The wiring the press tests do NOT cover.

        Those hand-build the data dict and call the handler directly, so they pass
        even if the template sends a constant - which is exactly what happened when
        this was checked. The index has to be followed from the item, through the
        template, onto the widget.
        """
        captured = []
        orig = B.gui_button
        B.gui_button = lambda props, **kw: captured.append(kw.get("data")) or None
        try:
            B.lm_eng_buttons_template({"index": 7, "label": "third",
                                       "color": "white", "icon": None})
        finally:
            B.gui_button = orig
        self.assertEqual(len(captured), 1, "the row drew no button to press")
        self.assertEqual(captured[0].get("index"), 7,
                         "the button does not carry its item's index")

    def test_the_TEMPLATE_puts_this_console_on_the_button(self):
        """Two engineers press their own console's menu, so the row must carry the
        client it was drawn for."""
        captured = []
        orig = B.gui_button
        B.gui_button = lambda props, **kw: captured.append(kw.get("data")) or None
        try:
            # FrameContext.client_id is read-only - it comes from the Context the
            # fixture set, which is this console.
            B.lm_eng_buttons_template({"index": 0, "label": "a",
                                       "color": "white", "icon": None})
        finally:
            B.gui_button = orig
        self.assertEqual(captured[0].get("cid"), CID)

    def test_a_label_is_quoted_exactly_once(self):
        """FROM A BRIDGE: "the buttons have backticks".

        `gui_text_escape` quotes, and `Button.value` quotes what it is given - so a
        label run through both came out double-quoted and the engine drew the marks.
        Button now leaves already-quoted text alone (as Text always did); this checks
        the rendered props from THIS template, not the library rule in isolation.
        """
        captured = []
        orig = B.gui_button
        B.gui_button = lambda props, **kw: captured.append(props) or None
        try:
            B.lm_eng_buttons_template({"index": 0, "label": "do work order now",
                                       "color": "white", "icon": None})
        finally:
            B.gui_button = orig
        from sbs_utils.pages.layout.button import Button
        value = Button("t", captured[0]).value
        self.assertIn("$text:`do work order now`", value)
        self.assertNotIn("``", value)

    def test_a_label_with_a_colon_is_not_read_as_a_style(self):
        captured = []
        orig = B.gui_button
        B.gui_button = lambda props, **kw: captured.append(props) or None
        try:
            B.lm_eng_buttons_template({"index": 0, "label": "Fix now: Reactor",
                                       "color": "red", "icon": None})
        finally:
            B.gui_button = orig
        from sbs_utils.pages.layout.button import Button
        value = Button("t", captured[0]).value
        self.assertIn("Fix now: Reactor", value)
        self.assertNotIn("``", value)

    def test_the_template_draws_without_raising(self):
        """A template that raises inside a listbox renders as an empty row, never an
        error - the same reason eng_grid_panel's tabs are all drawn in a test."""
        for item in ({"index": 0, "label": "plain", "color": "white", "icon": None},
                     {"index": 1, "label": "iconed", "color": "red", "icon": "wrench"},
                     {"index": 2, "label": "bad icon", "color": "red", "icon": "nope"},
                     {"index": 3, "label": "has: a colon", "color": "white", "icon": None},
                     {"index": 4, "label": "", "color": None, "icon": None}):
            B.lm_eng_buttons_template(item)

    def test_the_empty_state_says_something(self):
        self.assertTrue(B.lm_eng_buttons_empty_text().strip())


class TheRowCountFollowsTheScreen(_Base):
    """Three rows on a short screen, five on a tall one.

    At 1280x720 the whole tool column is only ~619px, so five rows of orders left the
    read-out panel 278px. Three leave it ~393px. The orders box is the fixed part of
    that column and the panel takes the rest, so this number IS the split.
    """

    def _at(self, w, h):
        from sbs_utils.helpers import FrameContext
        from sbs_utils.vec import Vec3
        FrameContext.aspect_ratios[CID] = Vec3(w, h, 1)
        return B.lm_eng_buttons_rows_shown(CID)

    def test_a_short_screen_gets_the_short_count(self):
        self.assertEqual(self._at(1280, 720), B.LM_ENG_BUTTON_ROWS_SHORT)

    def test_a_tall_screen_gets_the_tall_count(self):
        self.assertEqual(self._at(1920, 1080), B.LM_ENG_BUTTON_ROWS_TALL)

    def test_the_threshold_is_inclusive(self):
        """`>= 1000` - stated, because "1000 or more" and "more than 1000" differ by
        exactly the screens people actually run."""
        self.assertEqual(self._at(1600, B.LM_ENG_BUTTON_TALL_SCREEN_PX),
                         B.LM_ENG_BUTTON_ROWS_TALL)
        self.assertEqual(self._at(1600, B.LM_ENG_BUTTON_TALL_SCREEN_PX - 1),
                         B.LM_ENG_BUTTON_ROWS_SHORT)

    def test_1600x900_is_short_and_2560x1440_is_tall(self):
        """The two sizes either side of the line that people really use."""
        self.assertEqual(self._at(1600, 900), B.LM_ENG_BUTTON_ROWS_SHORT)
        self.assertEqual(self._at(2560, 1440), B.LM_ENG_BUTTON_ROWS_TALL)

    def test_a_client_that_has_not_reported_its_size_gets_the_short_count(self):
        """get_client_aspect_ratio answers 1024x768 with z=99 for a console that has
        not told us yet. Too few rows leaves the panel roomy; too many squeeze it on a
        screen that cannot afford it."""
        from sbs_utils.helpers import FrameContext
        FrameContext.aspect_ratios.pop(CID, None)
        self.assertEqual(B.lm_eng_buttons_rows_shown(CID), B.LM_ENG_BUTTON_ROWS_SHORT)

    def test_the_box_grows_with_the_count(self):
        short = self._at(1280, 720) and B.lm_eng_buttons_box_height(CID)
        tall_rows = self._at(1920, 1080)
        tall = B.lm_eng_buttons_box_height(CID)
        self.assertLess(_em_of(short)[0], _em_of(tall)[0])
        self.assertEqual(tall_rows, B.LM_ENG_BUTTON_ROWS_TALL)


class TheBoxIsNoTallerThanItNeeds(_Base):
    """FROM A BRIDGE: a visible band of empty box under the last button.

    The chrome allowance is what a listbox spends beyond the rows it shows. It was a
    full row plus a gap (2.4em), which left that band; it is 1.2em now and the
    read-out panel above has the difference - 29px at 1280x720, measured.

    The allowance can only be tuned by eye, so what a test can hold is that it still
    SHOWS the rows it claims. Too small and a row silently disappears.
    """

    def _rows_for(self, w, h):
        from sbs_utils.helpers import FrameContext
        from sbs_utils.vec import Vec3
        FrameContext.aspect_ratios[CID] = Vec3(w, h, 1)
        want = B.lm_eng_buttons_rows_shown(CID)
        tall_em, _trim = _em_of(B.lm_eng_buttons_box_height(CID))
        return want, tall_em

    def test_a_short_screen_trims_the_box_and_the_panel_gets_it(self):
        """10px off the box on a 720-tall console, and nowhere else.

        That screen is the only one where the split is tight - the whole tool column
        is ~619px - so the last pixels are worth more to the read-out panel than to a
        box that already fits its three rows. Measured through the real layout: the
        listbox resolves to 186.8px where 8.20em alone is 196.8px.
        """
        from sbs_utils.helpers import FrameContext
        from sbs_utils.vec import Vec3
        FrameContext.aspect_ratios[CID] = Vec3(1280, 720, 1)
        _em, trim = _em_of(B.lm_eng_buttons_box_height(CID))
        self.assertEqual(trim, B.LM_ENG_BUTTON_SHORT_TRIM_PX)

        FrameContext.aspect_ratios[CID] = Vec3(1920, 1080, 1)
        _em, trim = _em_of(B.lm_eng_buttons_box_height(CID))
        self.assertEqual(trim, 0, "a tall screen has room and must not be trimmed")

    def test_the_box_is_not_a_whole_row_bigger_than_its_rows(self):
        """What "there is space" looked like: a full spare row of empty box."""
        for w, h in ((1280, 720), (1920, 1080)):
            want, tall_em = self._rows_for(w, h)
            content = want * B.LM_ENG_BUTTON_ROW_EM + (want - 1) * B.LM_ENG_BUTTON_GAP_EM
            with self.subTest(size=(w, h)):
                self.assertLess(tall_em - content, B.LM_ENG_BUTTON_ROW_EM,
                                "the box has a spare row of empty space in it")

    def test_the_box_still_has_room_for_its_rows(self):
        """The other side: the allowance must not be trimmed until a row drops off.
        `test_the_orders_box_SHOWS_the_rows_it_claims` proves it on the real console;
        this states the arithmetic floor."""
        for w, h in ((1280, 720), (1920, 1080)):
            want, tall_em = self._rows_for(w, h)
            content = want * B.LM_ENG_BUTTON_ROW_EM + (want - 1) * B.LM_ENG_BUTTON_GAP_EM
            with self.subTest(size=(w, h)):
                self.assertGreaterEqual(tall_em, content)


if __name__ == "__main__":
    unittest.main()
