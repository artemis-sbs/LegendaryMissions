"""Engineering's grid orders - what replaced the `grid_control` engine widget.

`grid_control` is an engine widget the console can only hand a rectangle to. No scroll,
no row height, no styling, and a menu taller than the box is simply cut off - which is
what made the right-hand column impossible to plan. At its old hard 200px it was 33px a
button at every resolution, measured.

The buttons are not the engine's. They come from grid comms - the `//comms/grid/*` routes
in `grid_comms/damcons.mast`, `rooms.mast`, `marker.mast` and `ai/grid_brains.mast` - and
nothing about that changes here. This is a second way to draw and press what already
exists: `comms_grid_buttons` reads them, `comms_grid_press` presses one, and the engine
widget is parked on this console only.

WHAT THIS BUYS: a listbox scrolls, so however many buttons a selection offers, none are
cut off; rows are a real touch target rather than whatever fits; and a button can carry a
colour and an icon.

AN ICON comes from the button's own format block and needs no new syntax - the block
already accepts anything:

    + [red icon:wrench] "Fix now"
    + [icon:person] "Workout"

Prefixed `lm_eng_buttons_` because every top-level function here becomes a MAST global in
one flat, mission-wide namespace. (A leading underscore is private to this file since
2026-09-22 - but only the PUBLIC ones need the prefix.)
"""
from sbs_utils.helpers import FrameContext, gui_text_escape
from sbs_utils.procedural.comms import (comms_grid_buttons, comms_grid_press,
                                        comms_grid_revision)
from sbs_utils.procedural.gui import gui_button, gui_row, gui_sub_section
from sbs_utils.procedural.gui.icon import gui_icon_name
from sbs_utils.procedural.gui.icon_sheet import icon_resolve
from sbs_utils.procedural.query import get_grid_selection, to_id
from sbs_utils.procedural.execution import log

#: One row per button, tall enough to hit.
LM_ENG_BUTTON_ROW_EM = 2.2

#: Space between rows.
LM_ENG_BUTTON_GAP_EM = 0.2

_DIM = "#8B85A8"

#: How many rows the box SHOWS, by screen height. It sits at the bottom of the tool
#: column at a fixed height and the read-out panel above takes whatever is left, so
#: this decides the split - which is the whole reason the engine widget had to go.
#: `grid_control` could only be handed a rectangle and packed however many buttons it
#: had into it, so the column could not be planned; a listbox shows this many and
#: SCROLLS the rest, so nothing is ever cut off however long the menu gets.
#:
#: Fewer on a short screen. At 1280x720 the whole tool column is only ~619px, so five
#: rows of orders left the read-out panel 278px; three leave it ~393px. On a tall
#: screen there is room for five, which covers every stock menu without scrolling (a
#: damcon offers five, a room four, a marker five).
LM_ENG_BUTTON_ROWS_TALL = 5
LM_ENG_BUTTON_ROWS_SHORT = 3

#: Screen height at or above which the box shows LM_ENG_BUTTON_ROWS_TALL.
LM_ENG_BUTTON_TALL_SCREEN_PX = 1000

#: What a listbox spends on its own chrome, beyond the rows it shows. MEASURED, not
#: derived, and in em rather than "one row" so it can be tuned by eye: at a full row
#: plus a gap (2.4em) there was a visible band of empty box under the last button, so
#: it is half that and the panel above has the difference.
_LISTBOX_CHROME_EM = 1.2

#: Trimmed off the box on a SHORT screen only, and given to the panel above.
#: A 720-tall console is the one place the split is actually tight - the whole tool
#: column is ~619px there - so the last few pixels are worth more to the read-out than
#: to the box, which already fits its three rows without them.
LM_ENG_BUTTON_SHORT_TRIM_PX = 10


def lm_eng_buttons_rows_shown(client_id=None):
    """How many order rows this console shows - 3 on a short screen, 5 on a tall one.

    Reads the CLIENT's screen, not the server's: two consoles on one bridge can be
    different sizes, and the one that matters is the one being drawn.
    """
    from sbs_utils.gui import get_client_aspect_ratio
    if client_id is None:
        client_id = FrameContext.client_id
    ar = get_client_aspect_ratio(client_id)
    height = getattr(ar, "y", 0) or 0
    if height >= LM_ENG_BUTTON_TALL_SCREEN_PX:
        return LM_ENG_BUTTON_ROWS_TALL
    # A client that has not reported its size yet answers 1024x768 with z=99 - short,
    # which is the safer guess: too few rows leaves the panel roomy, too many squeeze
    # it on a screen that cannot afford it.
    return LM_ENG_BUTTON_ROWS_SHORT


def lm_eng_buttons_box_height(client_id=None):
    """`row-height` for the orders box - enough to SHOW that many rows.

    Computed rather than written into the layout so the row height, the gap, the count
    and the chrome allowance cannot drift apart: change any one and the box still
    shows what it says.
    """
    rows = lm_eng_buttons_rows_shown(client_id)
    tall = (rows * LM_ENG_BUTTON_ROW_EM + (rows - 1) * LM_ENG_BUTTON_GAP_EM
            + _LISTBOX_CHROME_EM)
    if rows == LM_ENG_BUTTON_ROWS_SHORT:
        # `em-px` is a real length expression, the same form the console's own
        # `area:0,50+8px,...` uses - not string concatenation.
        return f"{tall:.2f}em-{LM_ENG_BUTTON_SHORT_TRIM_PX}px"
    return f"{tall:.2f}em"


def lm_eng_buttons_box_style():
    """The listbox's own style. Paired with :func:`lm_eng_buttons_box_height` - the gap
    is in both, which is why they share the constant."""
    return f"item-gap: {LM_ENG_BUTTON_GAP_EM}em;"


def lm_eng_buttons_ship(client_id):
    """The ship this console is wired to, or None."""
    ctx = FrameContext.context
    if ctx is None or ctx.sbs is None:
        return None
    try:
        ship = ctx.sbs.get_ship_of_client(client_id)
    except Exception:                                   # noqa: BLE001
        return None
    return to_id(ship) or None


def lm_eng_buttons_pair(client_id):
    """(ship, selected grid node) - the pair a grid interaction is keyed on.

    The selection lives on the SHIP's blob (`grid_selected_UID`), which is why every
    engineering console on a bridge sees the same menu.
    """
    ship_id = lm_eng_buttons_ship(client_id)
    if not ship_id:
        return None, None
    return ship_id, (get_grid_selection(ship_id) or None)


def lm_eng_buttons_items(client_id):
    """The rows to draw: whatever the grid menu is offering for this selection."""
    ship_id, node_id = lm_eng_buttons_pair(client_id)
    if not ship_id or not node_id:
        return []
    return comms_grid_buttons(ship_id, node_id)


def lm_eng_buttons_revision(client_id):
    """What an `on change` watches. Includes the selection, so picking a different
    room repaints even when the two menus happen to offer the same words."""
    ship_id, node_id = lm_eng_buttons_pair(client_id)
    if not ship_id or not node_id:
        return (None, None)
    return (node_id, comms_grid_revision(ship_id, node_id))


def lm_eng_buttons_press(data):
    """A row was pressed. ONE REQUIRED PARAMETER on purpose.

    `gui_button` calls a Python `on_press` with NOTHING unless it declares a required
    parameter, and with the widget's `data` when it declares one (`call_press_handler`).
    The house idiom - a closure with bound defaults - declares none, so a handler
    written `def press(event=None, sender=None)` is handed nothing and silently does
    nothing. That cost this session an afternoon once already.

    `data["index"]` is the button's position in the UNFILTERED list, NOT the row's
    position: a button hidden by its `if`, or a `*` already used, is skipped when
    drawing but still consumes an index. Passing a row number runs the wrong order.
    """
    data = data or {}
    client_id = data.get("cid")
    index = data.get("index")
    ship_id, node_id = lm_eng_buttons_pair(client_id)
    if not ship_id or not node_id or index is None:
        return False
    return comms_grid_press(ship_id, node_id, index, client_id)


def lm_eng_buttons_template(item, **kwargs):
    """One order: its icon, if it declared one, then a button carrying its label.

    The ROW is a real `gui_button`, not a selectable listbox row: a listbox built with
    `select=False` ignores clicks outright (`LayoutListbox.on_click` returns early),
    and selection semantics are the wrong shape for a menu anyway - pressing an order
    is an action, not a choice that stays made.

    `data=` on the button, never a closure over the loop variable: an inline handler
    registered in a loop captures the LAST iteration's values, so every row would fire
    the last order.
    """
    color = item.get("color") or "white"
    icon = item.get("icon")
    gui_row(f"row-height: {LM_ENG_BUTTON_ROW_EM}em;")
    if icon:
        index, _atlas = icon_resolve(icon)
        if index is None:
            # An unknown name draws NOTHING and reads as a dead row, so say which.
            log(f"no icon named {icon!r} on grid button {item.get('label')!r}",
                "gui", "warning")
        else:
            with gui_sub_section("col-width: 1.6em;"):
                gui_row()
                gui_icon_name(icon, color=color)
    # gui_text_escape on the label: a button's text is author-written, and a colon in
    # it would otherwise be read as a style property.
    gui_button(f"$text:{gui_text_escape(item.get('label') or '')};color:{color};"
               f"font:gui-2;justify:left;",
               data={"index": item.get("index"), "cid": FrameContext.client_id},
               on_press=lm_eng_buttons_press)


def lm_eng_buttons_empty_text():
    """What to say when there is nothing to press - never an empty box."""
    return f"$text:(select a room or a team to give orders);color:{_DIM};"
