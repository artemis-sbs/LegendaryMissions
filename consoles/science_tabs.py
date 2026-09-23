"""Science's scan tabs - what replaces the `science_data_tabs` engine widget.

`science_data_tabs` is the same kind of rectangle `grid_control` was on Engineering: the
console can hand it a size and nothing else. No scroll, no row height, no styling, and a
tab set taller than the box is cut off. At its declared 70px it holds five tabs, and an
object that declares six loses one with no indication that it did.

So this is the `eng_grid_buttons` move applied to science. A listbox scrolls, so however
many tabs an object declares none are lost; a row is a real touch target rather than 14px;
and a row can carry a color, which is how a tab reports its own scan state without a
second surface.

WHAT A PRESS DOES, decided entirely by whether that tab holds data:

* scanned    - navigate. The panel shows that tab.
* unscanned  - queue it. One press, no sub-menu, no confirmation.
* queued     - nothing. It is already asked for and has no data yet.

The buttons do not manage the queue. Cancelling and reordering happen on the Queue tab,
which is the last row and behaves like any other tab.

Prefixed `lm_sci_` because every top-level function here becomes a MAST global in one flat,
mission-wide namespace. A leading underscore is private to this file.
"""
from sbs_utils.helpers import FrameContext, gui_text_escape
from sbs_utils.procedural.gui import gui_button, gui_row, gui_text
from sbs_utils.procedural.query import to_object, to_id, to_blob, get_science_selection
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.execution import log

from science_queue import (lm_sci_queue_add, lm_sci_queue_is_scanned, lm_sci_queue_list,
                           lm_sci_queue_position, lm_sci_queue_percent,
                           lm_sci_queue_revision, lm_sci_queue_side)

#: One row per tab, tall enough to hit. Matches Engineering's orders box.
LM_SCI_TAB_ROW_EM = 2.2

#: Space between rows.
LM_SCI_TAB_GAP_EM = 0.2

#: What a listbox spends on its own chrome beyond the rows it shows. Measured on
#: Engineering's box, which is the same widget at the same row height.
_LISTBOX_CHROME_EM = 1.2

#: How many rows the box SHOWS before scrolling. The panel below takes whatever is left,
#: so this decides the column's split - the whole reason the engine widget had to go.
#: Six covers scan/status/intel/bio/mat plus Queue, which is every stock tab set.
LM_SCI_TAB_ROWS_TALL = 6
LM_SCI_TAB_ROWS_SHORT = 4

#: Screen height at or above which the box shows LM_SCI_TAB_ROWS_TALL.
LM_SCI_TAB_TALL_SCREEN_PX = 1000

#: The row that opens the shared queue. Not a scan tab - it is spelled out here so the
#: panel and the press handler cannot disagree about the name. This is the KEY, compared
#: against everywhere; the crew never sees it.
LM_SCI_QUEUE_TAB = "Queue"

#: What that row is LABELLED. "Queue" alone reads as a verb sitting under "Queue Scan" -
#: queue what? - which is the exact ambiguity the other labels just lost. "In Queue" is a
#: place, and pressing it takes you there, so it obeys the same rule as the rest: the
#: label says what the press does.
LM_SCI_QUEUE_LABEL = "In Queue"

#: Where this console's current tab is remembered. Per CLIENT, not per ship: two science
#: consoles on one bridge look at different contacts and different tabs.
_TAB_KEY = "lm_sci_tab"

_DIM = "#8B85A8"
_SCANNED = "#5BE08E"
_ACTIVE = "#45D3E6"
_QUEUED = "#F2B32C"

# NO STATE ICON. A glyph in a leading column on every row reads as a CHECKBOX or a radio
# button - something you tick, with a state you own - and these rows are neither: they are
# a menu, and their state is the scan's, not yours. The suffix and the colour already say
# it (DONE / SCANNING 41% / QUEUED 2), so the glyph only added a wrong affordance.

# --- the floating stack, over the 2D view ---------------------------------------------
#
# A MAST panel CAN sit on top of an engine 2D view. Weapons already does it: Manual Beams
# declares `gui_region("area: ...")` over `weapon_2d_view` and draws the called-shot square
# there (consoles/manual_beams_helpers.py, mounted in manual_weapons.mast). The rule that
# an engine widget must not SHARE A ROW with MAST controls is about flow layout, where the
# engine paints at its own size over its neighbours - an absolute region is a different
# mechanism and is not subject to it.
#
# The tabs sit in the console's lower LEFT and come and go with the selection, which is
# what a comms menu does. That band is the dead space under the left column's info panel
# and log tail, so the stack is an overlay in mechanism but costs no content: it is beside
# the map, not on it.
#
# ONE CAUTION carried over from Manual Beams anyway: a click that lands on such a panel but
# NOT on a widget falls through to whatever is beneath, and over a 2D view that means
# selecting empty space and dropping the selection - which reads as "the panel vanished
# when I clicked it". The region keeps an opaque background and the rows have no gaps, so
# the panel stays solid wherever it is placed.

#: Left edge of the console, not of the view. The tabs live in the empty band under the
#: left column's info panel and log tail - that column is 280px wide and its two rows
#: (the panel at `400px-3em`, the tail at `4em`) end around 510px, leaving the rest of it
#: dark. Putting the stack there costs nothing and occludes nothing.
LM_SCI_STACK_X_PX = 8

#: The stack's width, kept inside the 280px column so it never covers the 2D view.
#: Wide enough for "SCANNING 100%" beside the longest stock tab name.
LM_SCI_STACK_W_PX = 284

#: One row, in px rather than em: an absolute `area:` is all-px so no font is in the path
#: when the region's height is computed from the row count.
LM_SCI_STACK_ROW_PX = 30

#: Header row naming the contact, since the stack no longer sits beside it.
LM_SCI_STACK_HEAD_PX = 26

#: What the region spends on its own padding.
LM_SCI_STACK_PAD_PX = 8

#: Over the view. Backdrops paint at 1000, so the panel's own fill needs to be above it.
LM_SCI_STACK_LAYER = 1500

#: The panel's ground. Opaque, so a click cannot fall through to the 2D view.
LM_SCI_STACK_BG = "#0E151DEE"


#: The most rows the box is ever sized for: scan/status/intel/mat/bio plus Queue, which
#: is every stock tab set, plus one spare. An object declaring more scrolls off the top
#: rather than resizing the box - see lm_sci_stack_height_px.
LM_SCI_STACK_MAX_ROWS = 7


def lm_sci_stack_height_px(client_id=None):
    """The box's height - a CONSTANT, not a function of how many rows there are today.

    A region's `area:` is read when the region is pushed, and reassigning `.style` on a
    live one does not reliably re-lay-it-out: the stack simply did not grow when a
    contact declared more tabs. So the box is sized once for the most rows it will ever
    hold and never changes, and the LOOK of it growing comes from the rows themselves -
    each carries its own opaque ground, and a flex spacer above them pins them to the
    bottom of the box. Fewer rows means more transparent space above, which is invisible.
    """
    return (LM_SCI_STACK_HEAD_PX + LM_SCI_STACK_MAX_ROWS * LM_SCI_STACK_ROW_PX
            + LM_SCI_STACK_PAD_PX)


#: Bottom edge, as a percentage. Short of the screen bottom so the stack sits in the band
#: the reference shot marks rather than jammed against the edge.
LM_SCI_STACK_BOTTOM_PCT = 88


def lm_sci_stack_area(client_id=None):
    """The absolute area for the stack - the console's lower LEFT.

    It grows UPWARD from a fixed base, the way a comms menu does, so the base is where
    the eye learns to look and a long tab set never pushes the first row off screen. Even
    at six rows it stops well clear of the ship-data block above.

    All-px on the x axis, the way Manual Beams does it, so the rect cannot move when the
    font does; the y is percent-minus-px, which is the same form Manual Beams uses.
    """
    height = lm_sci_stack_height_px(client_id)
    return (f"area: {LM_SCI_STACK_X_PX}px, {LM_SCI_STACK_BOTTOM_PCT}-{height}px, "
            f"{LM_SCI_STACK_X_PX + LM_SCI_STACK_W_PX}px, {LM_SCI_STACK_BOTTOM_PCT};")


def lm_sci_stack_style(client_id=None):
    """The region's own style: its area, raised, and NO ground.

    The ground is on each ROW instead. A ground here would paint the whole fixed box,
    including the empty space above a short stack - which is exactly the "it does not
    grow" look this is avoiding.
    """
    return lm_sci_stack_area(client_id) + f"layer: {LM_SCI_STACK_LAYER};"


def lm_sci_stack_visible(client_id):
    """Does the stack have anything to say? It comes and goes with the selection, like a
    comms menu - but the Queue row alone is reason enough to stay up."""
    return len(lm_sci_tabs_items(client_id)) > 0


def lm_sci_stack_header(client_id):
    """What the header row says: the contact the tabs are about."""
    _ship_id, target_id = lm_sci_tabs_pair(client_id)
    target = to_object(target_id) if target_id else None
    if target is None:
        return "SCAN QUEUE"
    return str(getattr(target, "name", None) or "unknown")


def lm_sci_tabs_rows_shown(client_id=None):
    """How many tab rows this console shows - fewer on a short screen.

    Reads the CLIENT's screen, not the server's: two consoles on one bridge can be
    different sizes and the one that matters is the one being drawn.
    """
    from sbs_utils.gui import get_client_aspect_ratio
    if client_id is None:
        client_id = FrameContext.client_id
    ar = get_client_aspect_ratio(client_id)
    height = getattr(ar, "y", 0) or 0
    if height >= LM_SCI_TAB_TALL_SCREEN_PX:
        return LM_SCI_TAB_ROWS_TALL
    # A client that has not reported its size answers 1024x768 - short, the safer guess.
    return LM_SCI_TAB_ROWS_SHORT


def lm_sci_tabs_box_height(client_id=None):
    """`row-height` for the tab box - enough to SHOW that many rows.

    Computed rather than written into the layout, so the row height, the gap, the count
    and the chrome allowance cannot drift apart.
    """
    rows = lm_sci_tabs_rows_shown(client_id)
    tall = (rows * LM_SCI_TAB_ROW_EM + (rows - 1) * LM_SCI_TAB_GAP_EM + _LISTBOX_CHROME_EM)
    return f"{tall:.2f}em"


def lm_sci_tabs_box_style():
    """The listbox's own style. Paired with :func:`lm_sci_tabs_box_height` - the gap is in
    both, which is why they share the constant."""
    return f"item-gap: {LM_SCI_TAB_GAP_EM}em;"


def lm_sci_tabs_ship(client_id):
    """The ship this console is wired to, or None."""
    ctx = FrameContext.context
    if ctx is None or ctx.sbs is None:
        return None
    try:
        ship = ctx.sbs.get_ship_of_client(client_id)
    except Exception:                                   # noqa: BLE001
        return None
    return to_id(ship) or None


def lm_sci_tabs_pair(client_id):
    """(ship, selected contact) - the pair every tab decision is keyed on."""
    ship_id = lm_sci_tabs_ship(client_id)
    if not ship_id:
        return None, None
    return ship_id, (get_science_selection(ship_id) or None)


def lm_sci_tabs_declared(target_id):
    """The tabs this object declares, `scan` always first.

    `scan_type_list` is written by the science promise as a comma-separated string, and
    `science_set_scan_data` leaves `scan` OUT of it - so it is prepended here rather than
    trusted to be present. The engine answers None for a field nothing has set, which is
    why the read is coalesced before it is split.
    """
    blob = to_blob(target_id) if target_id else None
    if blob is None:
        return ["scan"]
    raw = str(blob.get("scan_type_list", 0) or "")
    tabs = [t.strip() for t in raw.split(",") if t.strip() and t.strip() != "scan"]
    return ["scan"] + tabs


def lm_sci_tab_state(ship_id, target_id, tab):
    """One of `scanned`, `scanning`, `queued`, `idle`."""
    if lm_sci_queue_is_scanned(ship_id, target_id, tab):
        return "scanned"
    side = lm_sci_queue_side(ship_id)
    position = lm_sci_queue_position(side, target_id, tab) if side else 0
    if position == 1:
        return "scanning"
    if position > 1:
        return "queued"
    return "idle"


def lm_sci_tab_display(tab):
    """A tab's name as the crew reads it. Tab names are lowercase keys; this is a label."""
    return str(tab).title()


def _row_for(ship_id, target_id, tab, current):
    """One tab row.

    THE LABEL SAYS WHAT THE PRESS DOES, which is not the same thing on every row:

    * unscanned - `Queue Scan`. The press queues a scan; it does not take you anywhere,
      so naming the destination would be a lie about the button.
    * everything else - `Scan`. The press navigates to that tab, so the label is the
      place, not a verb.

    And a scanned tab carries NO suffix. `Scan DONE` said the same thing twice: a tab
    that is simply there, in its ordinary colour, alongside one that reads `Queue Scan`,
    is already telling you which of the two has data. A suffix earns its place only when
    it says something the label cannot - a queue position, a percentage.
    """
    state = lm_sci_tab_state(ship_id, target_id, tab)
    side = lm_sci_queue_side(ship_id)
    name = lm_sci_tab_display(tab)
    label, detail = name, ""
    if state == "scanned":
        color = _ACTIVE if tab == current else "white"
    elif state == "scanning":
        color = _ACTIVE
        detail = f"SCANNING {lm_sci_queue_percent(side, target_id, tab)}%"
    elif state == "queued":
        color = _QUEUED
        detail = f"QUEUED {lm_sci_queue_position(side, target_id, tab)}"
    else:
        color = "white"
        label = f"Queue {name}"
    return {"tab": tab, "label": label, "state": state, "detail": detail,
            "color": color}


def lm_sci_tabs_items(client_id):
    """The rows to draw: one per declared tab, then the shared Queue."""
    ship_id, target_id = lm_sci_tabs_pair(client_id)
    if not ship_id:
        return []
    current = lm_sci_tabs_current(client_id)
    rows = []
    if target_id:
        for tab in lm_sci_tabs_declared(target_id):
            rows.append(_row_for(ship_id, target_id, tab, current))
    side = lm_sci_queue_side(ship_id)
    depth = len(lm_sci_queue_list(side)) if side else 0
    rows.append({"tab": LM_SCI_QUEUE_TAB, "label": LM_SCI_QUEUE_LABEL, "state": "queue",
                 "detail": str(depth) if depth else "",
                 "color": _QUEUED if depth else _DIM})
    return rows


def lm_sci_tabs_revision(client_id):
    """What an `on change` watches. The selection is in it, so picking a different
    contact repaints even when the two tab sets happen to be the same words."""
    ship_id, target_id = lm_sci_tabs_pair(client_id)
    side = lm_sci_queue_side(ship_id) if ship_id else None
    return (target_id, lm_sci_tabs_current(client_id),
            tuple(lm_sci_tabs_declared(target_id)) if target_id else (),
            lm_sci_queue_revision(side))


def lm_sci_tabs_current(client_id):
    """Which tab this console is showing. Defaults to `scan`, which every object has."""
    return get_inventory_value(client_id, _TAB_KEY, "scan") or "scan"


def lm_sci_tabs_set_current(client_id, tab):
    """Remember the tab this console is on, and TELL THE ENGINE.

    The engine learns which scan tab is active from `science_data_tabs`, and this console
    does not have one - so with nothing publishing it, `science_data_freq` had no reason
    to show anything. The scanning ship's `cur_scan_ID` / `cur_scan_type` are where the
    engine's own queue publishes exactly that pair, so this writes them when the tab
    changes.

    A HYPOTHESIS, and worth flagging: the band readout not drawing on a scanned hostile
    with the status tab open is what points here. If it now draws, this is why. Writing
    these is harmless either way - nothing else on this console reads them, our own queue
    keeps its progress privately, and other consoles get an honest "what science is
    looking at" they do not have today.

    `cur_scan_percent` is deliberately NOT written: it means a scan IN PROGRESS, and
    showing a tab that already has data is not one.
    """
    set_inventory_value(client_id, _TAB_KEY, tab)
    lm_sci_publish_active_tab(client_id, tab)


def lm_sci_publish_active_tab(client_id, tab=None):
    """Publish (selected contact, current tab) to the scanning ship's blob."""
    ship_id, target_id = lm_sci_tabs_pair(client_id)
    ship = to_object(ship_id) if ship_id else None
    if ship is None:
        return False
    if tab is None:
        tab = lm_sci_tabs_current(client_id)
    if tab == LM_SCI_QUEUE_TAB:
        # The queue is not a scan tab - say "nothing selected" rather than name it.
        ship.data_set.set("cur_scan_ID", 0, 0)
        ship.data_set.set("cur_scan_type", "", 0)
        return True
    ship.data_set.set("cur_scan_ID", target_id or 0, 0)
    ship.data_set.set("cur_scan_type", str(tab), 0)
    return True


def lm_sci_tabs_press(data):
    """A row was pressed. ONE REQUIRED PARAMETER on purpose.

    `gui_button` calls a Python `on_press` with NOTHING unless it declares a required
    parameter, and with the widget's `data` when it declares one. A handler written
    `def press(event=None, sender=None)` is handed nothing and silently does nothing.

    `data=` on the button, never a closure over the loop variable: an inline handler
    registered in a loop captures the LAST iteration's values, so every row would fire
    the last tab.
    """
    data = data or {}
    client_id = data.get("cid")
    tab = data.get("tab")
    if client_id is None or not tab:
        return False
    if tab == LM_SCI_QUEUE_TAB:
        lm_sci_tabs_set_current(client_id, tab)
        return True
    ship_id, target_id = lm_sci_tabs_pair(client_id)
    if not ship_id or not target_id:
        return False
    state = lm_sci_tab_state(ship_id, target_id, tab)
    if state == "scanned":
        lm_sci_tabs_set_current(client_id, tab)
        return True
    if state == "idle":
        added = lm_sci_queue_add(ship_id, target_id, tab)
        if added:
            log(f"queued {tab} on {target_id}", "science")
        return added
    # scanning or queued: already asked for, and there is nothing to show yet.
    return False


def lm_sci_tabs_template(item, **kwargs):
    """One tab: a full-width button carrying its label and its state.

    The ROW is a real `gui_button`, not a selectable listbox row: a listbox built with
    `select=False` ignores clicks outright, and selection semantics are the wrong shape
    here anyway - a queued tab must be pressable-looking yet inert, which a selection
    cannot express.
    """
    color = item.get("color") or "white"
    # NO GAP between rows. A click that lands on the panel but not on a widget falls
    # through to whatever is beneath it, and over a 2D view that means selecting empty
    # space and dropping the selection - which reads as the panel vanishing when clicked.
    gui_row(f"row-height: {LM_SCI_STACK_ROW_PX}px;")
    label = item.get("label") or ""
    detail = item.get("detail") or ""
    text = f"{label}    {detail}" if detail else label
    # gui_text_escape on the label: a tab name is author-written (an object declares its
    # own tabs), and a colon in one would otherwise be read as a style property.
    gui_button(f"$text:{gui_text_escape(text)};color:{color};font:gui-2;justify:left;"
               f"layer:{LM_SCI_STACK_LAYER};background:{LM_SCI_STACK_BG};",
               data={"tab": item.get("tab"), "cid": FrameContext.client_id},
               on_press=lm_sci_tabs_press)


def lm_sci_stack_show(client_id):
    """Draw the floating stack into the CURRENT region.

    Rows are drawn directly rather than through a listbox: the region is sized from the
    row count, so there is nothing to scroll past, and a listbox would add its own
    chrome and background over the view. The stack is short by construction - a stock
    object declares at most five tabs plus Queue.
    """
    rows = lm_sci_tabs_items(client_id)
    if not rows:
        return
    # A FLEX row first, with no ground, so everything below it is pushed to the BOTTOM of
    # the fixed box. This is what makes a two-row stack sit where a six-row stack's last
    # two rows would, instead of floating at the top of an empty rectangle.
    gui_row()
    gui_blank()
    gui_row(f"row-height: {LM_SCI_STACK_HEAD_PX}px;")
    gui_text(f"$text:{gui_text_escape(lm_sci_stack_header(client_id))};"
             f"color:{_ACTIVE};font:gui-2;layer:{LM_SCI_STACK_LAYER};"
             f"background:{LM_SCI_STACK_BG};")
    for item in rows:
        lm_sci_tabs_template(item)


#: The engine's contact list, brought back as a TRANSIENT widget.
LM_SCI_OBJECT_LIST = "science_sorted_list"


def lm_sci_object_list_wanted(client_id):
    """Should the contact list be on screen? Only when nothing is selected.

    Selection is the one thing the list is for, so once a contact is picked the list has
    done its job and the readout wants the space. With nothing selected the readout says
    "(no contact selected)" and the space is otherwise dead - which is exactly when a
    list of contacts is the most useful thing that could be there.
    """
    _ship_id, target_id = lm_sci_tabs_pair(client_id)
    return not target_id


#: Where the contact list sits: the bottom of the 30%-wide right column, in PERCENT.
#: Given as numbers rather than taken from a layout placeholder on purpose - see
#: lm_sci_object_list_place.
LM_SCI_LIST_LEFT = 70.0
LM_SCI_LIST_TOP = 56.0
LM_SCI_LIST_WIDTH = 30.0
LM_SCI_LIST_HEIGHT = 36.5


def lm_sci_object_list_place(client_id, wanted=None):
    """Show or hide the contact list. Returns True when it is on screen.

    BY RECT ONLY - the widget is NEVER handed to `gui_layout_widget`. That is the whole
    trick, and getting it wrong is what made the list "always showing": a layout
    placeholder re-sends its widget's rect on every build, so it fights any rect an
    `on change` handler sends and wins. With no placeholder there is nothing to fight,
    and a rect sent from a handler simply stands.

    This is how the info panel hosts an engine widget in a tab - `gui_panel_widget_show`
    / `gui_panel_widget_hide` are rect sends and nothing more. The widget still has to be
    DECLARED (the library's science console list already declares it); declaring is what
    makes the engine draw it, the rect is only where.
    """
    if wanted is None:
        wanted = lm_sci_object_list_wanted(client_id)
    from sbs_utils.procedural.gui.tabbed_panel import (gui_panel_widget_show,
                                                       gui_panel_widget_hide)
    args = (client_id, LM_SCI_LIST_LEFT, LM_SCI_LIST_TOP,
            LM_SCI_LIST_WIDTH, LM_SCI_LIST_HEIGHT, LM_SCI_OBJECT_LIST)
    if wanted:
        gui_panel_widget_show(*args)
        return True
    gui_panel_widget_hide(*args)
    return False


# THE ENGINE'S BAND READOUT CANNOT BE DRIVEN FROM HERE - engine-confirmed 2026-09-22.
#
# `science_data_freq` was brought back the same way the contact list was (declared, then
# positioned by rect) and never drew, on a scanned hostile with the status tab open.
# Three things were tried and none of them was it:
#
#   1. showing it by rect on the status tab - right condition, nothing on screen;
#   2. keeping `science_data` DECLARED but parked, in case the one feeds the other;
#   3. publishing the active tab as `cur_scan_ID` / `cur_scan_type` on the scanning
#      ship - the pair the engine's own queue uses - in case it simply did not know
#      which tab was open.
#
# The last is the most likely shape of the real answer: the engine learns the active tab
# from `science_data_tabs`, and a console that replaces that widget has NO supported way
# to say which tab it is on. That is an engine ask, not a script problem, and it is
# adjacent to the known TODO that `ConsoleDispatcher` discards the tab from
# `science_data_tabs`'s own event.
#
# Until then the status tab draws the bands itself - see science_panel.

def lm_sci_tabs_empty_text():
    """What to say when there is nothing to press - never an empty box."""
    return f"$text:(select a contact to scan);color:{_DIM};"
