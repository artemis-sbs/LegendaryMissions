"""The queue, as a LIST you can act on - Move up and Cancel per entry.

The readout is a text area, and a text area cannot hold a button. So the queue gets its
own listbox under it: one row per entry, with the two controls that make a queue a queue
rather than a status display.

TOUCH GAPS ARE THE POINT OF THIS FILE. Move up and Cancel sit side by side and do opposite
things - one is a small correction, the other destroys work the ship has already spent
sensor time on - so a fat finger landing between them must not hit Cancel. Three measures,
all of them deliberate:

* the two icons are separated by a `LM_SCI_QL_GAP_EM` DEAD COLUMN - empty space that
  belongs to NEITHER button, so a press landing in it hits nothing. This, not the size
  of the icons, is where the safety lives: small icons with a generous horizontal gap
  beat big buttons pressed against each other.
* padding would not do the same job, because padding still belongs to a button and
  still takes the press;
* Cancel is the OUTERMOST control, against the edge, so a gesture that overshoots it
  leaves the panel entirely instead of landing on something else destructive.

MOVE UP, not move to front: reordering a queue is usually a small correction, and a
button that leaps to the head cannot be undone with the same button.

FIXED HEIGHT, sized for `LM_SCI_QL_ROWS` entries and scrolling past them. A listbox row
count cannot change the box after the page is built - the layout reads its row height once
- so the box is a constant and the list scrolls, exactly as the tab stack is a constant and
the rows fill it.

Prefixed `lm_sci_` because every top-level function here becomes a MAST global in one flat,
mission-wide namespace. A leading underscore is private to this file.
"""
from sbs_utils.helpers import FrameContext, gui_text_escape
from sbs_utils.procedural.gui import gui_row, gui_text, gui_blank
from sbs_utils.procedural.gui.icon import gui_icon_name
from sbs_utils.procedural.gui.message import gui_message_callback
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.execution import log

from science_queue import (lm_sci_queue_list, lm_sci_queue_side, lm_sci_queue_remove,
                           lm_sci_queue_move_up, lm_sci_queue_revision)
from science_tabs import lm_sci_tabs_ship

#: One entry. A touch target, but the controls on it are icons rather than words, so it
#: does not need the height two labelled buttons wanted.
LM_SCI_QL_ROW_EM = 2.2

#: The DEAD COLUMN between the two icons. Not padding - padding belongs to a button and
#: still takes the press. This is empty space that belongs to neither, and it is where
#: the touch safety actually lives: the icons themselves can be small - and are, at half
#: the width a labelled button wanted - as long as the HORIZONTAL distance between them
#: is generous. This is deliberately WIDER than an icon.
LM_SCI_QL_GAP_EM = 1.6

#: Each icon. Half what a labelled button wanted, because the icons are not the touch
#: target the gap is protecting - the ROW is the vertical target and the DEAD COLUMN is
#: the horizontal one. At this size the gap is wider than either glyph, which is the
#: relationship that matters: a press that misses an icon lands in space belonging to
#: nothing rather than on the control next to it.
LM_SCI_QL_ICON_EM = 1.0

#: Space between rows, so a press meant for one entry cannot land on its neighbour.
LM_SCI_QL_ITEM_GAP_EM = 0.3

#: How many entries the box SHOWS. The rest scroll.
LM_SCI_QL_ROWS = 5

#: What a listbox spends on its own chrome beyond the rows it shows.
_LISTBOX_CHROME_EM = 1.2

_DIM = "#8B85A8"
_LABEL = "#5B6D7F"
_ACTIVE = "#45D3E6"
_WARN = "#F2B32C"
_DANGER = "#FF6B6B"

#: Hover only - a click region, not a permanent frame.
_HOVER = "#FFFFFF33"


def lm_sci_ql_box_height():
    """`row-height` for the queue box - enough to SHOW that many entries.

    Computed rather than written into the layout so the row height, the gap, the count
    and the chrome allowance cannot drift apart.
    """
    tall = (LM_SCI_QL_ROWS * LM_SCI_QL_ROW_EM
            + (LM_SCI_QL_ROWS - 1) * LM_SCI_QL_ITEM_GAP_EM + _LISTBOX_CHROME_EM)
    return f"{tall:.2f}em"


def lm_sci_ql_box_style():
    """The listbox's own style. Paired with :func:`lm_sci_ql_box_height` - the gap is in
    both, which is why they share the constant."""
    return f"item-gap: {LM_SCI_QL_ITEM_GAP_EM}em;"


def lm_sci_ql_items(client_id):
    """One item per queue entry, in queue order, head first."""
    ship_id = lm_sci_tabs_ship(client_id)
    side = lm_sci_queue_side(ship_id) if ship_id else None
    if not side:
        return []
    out = []
    for i, entry in enumerate(lm_sci_queue_list(side)):
        target = to_object(entry["target"])
        origin = to_object(entry["origin"])
        out.append({
            "index": i,
            "side": side,
            "target": entry["target"],
            "tab": entry["tab"],
            "pct": int(entry["pct"]),
            "name": getattr(target, "name", None) or "unknown",
            "asked": getattr(origin, "name", None) or "?",
        })
    return out


def lm_sci_ql_revision(client_id):
    """What an `on change` watches: the entries and the head's progress."""
    ship_id = lm_sci_tabs_ship(client_id)
    side = lm_sci_queue_side(ship_id) if ship_id else None
    return lm_sci_queue_revision(side)


def lm_sci_ql_refresh(client_id, box):
    """Re-fill the list in place. `.items = ...`, never a repaint - a repaint would tear
    down the listbox and the handlers attached to it."""
    box.items = lm_sci_ql_items(client_id)


def lm_sci_ql_press_up(data):
    """Move up was pressed. ONE REQUIRED PARAMETER on purpose.

    `gui_button` calls a Python `on_press` with NOTHING unless it declares a required
    parameter, and with the widget's `data` when it declares one. `data=` on the button,
    never a closure over the loop variable: an inline handler registered in a loop
    captures the LAST iteration's values, so every row would move the last entry.
    """
    data = data or {}
    if not data.get("side") or not data.get("target"):
        return False
    moved = lm_sci_queue_move_up(data["side"], data["target"], data.get("tab", "scan"))
    if moved:
        log(f"queue: moved {data.get('tab')} on {data.get('target')} up", "science")
    return moved


def lm_sci_ql_press_cancel(data):
    """Cancel was pressed - the entry leaves the queue."""
    data = data or {}
    if not data.get("side") or not data.get("target"):
        return False
    dropped = lm_sci_queue_remove(data["side"], data["target"], data.get("tab", "scan"))
    if dropped:
        log(f"queue: cancelled {data.get('tab')} on {data.get('target')}", "science")
    return dropped


def _click_wire(widget, tag, data, handler):
    """Make any widget clickable without chrome, and route its press.

    `click_text` is what makes a column emit a click region; it is set in PYTHON because
    `click_text:;` in a style string is dropped by the parser (an empty value answers
    None), which leaves the widget inert.

    THE TAG COMES FROM THE LISTBOX ROW. `LayoutListbox._on_message` only walks its rows
    when `sub_tag.startswith(self.tag_prefix)`, and a widget left to mint its own click
    tag produces `__click:{tag}` - that leading prefix fails the gate and the press is
    dropped. Deriving from the row's own tag keeps the prefix.
    """
    if widget is None or tag is None:
        return widget
    widget.click_tag = tag
    widget.click_text = ""
    widget.click_background = _HOVER
    # A Python closure per row, not a MAST `on` block in a loop: an inline handler
    # registered in a loop captures the LAST iteration's values, so every row would act
    # on the last entry. This closure is built fresh per row and binds `data`.
    gui_message_callback(widget, lambda event, sender: handler(data))
    return widget


def lm_sci_ql_press_select(data):
    """The entry's NAME was pressed - select that contact.

    A queue is a list of things you are interested in, so the name is the obvious handle
    for "show me that one". Selecting from here saves hunting the contact down on the
    radar, which is the whole reason it is worth being clickable.
    """
    data = data or {}
    client_id, target = data.get("cid"), data.get("target")
    if client_id is None or not target:
        return False
    ship_id = lm_sci_tabs_ship(client_id)
    if not ship_id:
        return False
    from sbs_utils.procedural.query import set_science_selection
    set_science_selection(ship_id, target)
    log(f"queue: selected {target} from the queue", "science")
    return True


def _icon_action(icon, color, tag, data, handler):
    """A clickable icon with NO BUTTON CHROME, wired the way a listbox expects.

    `click_text` makes a widget emit a click region; the region is what you press, and no
    frame or fill is drawn around it. Two reasons that beats a button here: the engine
    draws button chrome OUTSIDE the rect it was given, so a framed icon eats into the dead
    column that is this row's whole safety argument; and two bare glyphs with space
    between them read as two separate things, which is what they are.

    THE TAG HAS TO COME FROM THE LISTBOX. `LayoutListbox._on_message` only walks its row
    sections when `sub_tag.startswith(self.tag_prefix)`, and a widget left to mint its own
    click tag produces `__click:{tag}` - the prefix form - which does NOT start with the
    listbox prefix, so the press is dropped. The listbox hands the template its row's
    click tag (`{row}:__click`) in `kwargs`, and deriving from that keeps the prefix. This
    is the same route `console_select_template` takes.

    Two icons on one row need two tags, so each derives its own suffix. A row's identity
    is its tag: share one and the last icon drawn answers for both, and Cancel fires when
    Move up is pressed.

    `click_text` is set in PYTHON, not in a style string: `click_text:;` - the empty value
    - is dropped by the style parser (`style_def.get` answers None), so the column never
    emits a region and the icon is inert.
    """
    widget = gui_icon_name(icon, color=color,
                           style=f"col-width: {LM_SCI_QL_ICON_EM}em;")
    return _click_wire(widget, tag, data, handler)


def lm_sci_ql_template(item, **kwargs):
    """One queue entry: what it is, then Move up, a dead gap, then Cancel."""
    head = item.get("index") == 0
    color = _ACTIVE if head else _DIM
    detail = f"{item.get('pct')}%" if head else "waiting"
    data = {"side": item.get("side"), "target": item.get("target"),
            "tab": item.get("tab"), "cid": FrameContext.client_id}

    # THE ROW'S CLICK TAG, handed in by the listbox - the same route
    # `console_select_template` takes. It is `{listbox}:{row}:__click`, so anything
    # derived from it still starts with the listbox prefix, which is what
    # `LayoutListbox._on_message` gates on. A widget left to mint its own produces
    # `__click:{tag}` and that leading prefix fails the gate, so the press is dropped.
    #
    # None on the measuring pass, so a missing tag means "sizing, not wiring".
    base = kwargs.get("click_tag")
    sec = kwargs.get("section")
    if sec is not None:
        # The ROW itself must not be pressable: selection is only switched on to get the
        # tag, and a row that highlights on touch would look like an action it is not.
        sec.click_text = None
        sec.click_tag = None
    gui_row(f"row-height: {LM_SCI_QL_ROW_EM}em;")
    label = f"{item.get('name')}  {item.get('tab')}"
    # THE NAME SELECTS. A queue is a list of contacts you already care about, so it is
    # the fastest way back to one - no hunting it down on the radar.
    name_widget = gui_text(f"$text:{gui_text_escape(label)};color:{color};font:gui-2;"
                           f"overflow:shrink;", "col-width: 1fr;")
    _click_wire(name_widget, f"{base}:sel" if base else None,
                data, lm_sci_ql_press_select)
    gui_text(f"$text:{gui_text_escape(detail)};color:{color};font:gui-1;justify:right;",
             "col-width: 3.5em;")

    # The HEAD cannot move up, so it gets a blank of the same width rather than a dead
    # control: one that is present and does nothing is worse than one that is not there,
    # and keeping the width means Cancel does not shift position between rows.
    # THE TAG BASE COMES FROM THE ROW SECTION, not from `kwargs["click_tag"]`.
    #
    # A listbox only hands the template a row click tag when it has SELECTION - this one
    # is `select=False`, so that kwarg is None on every pass and wiring off it silently
    # produced inert icons. The row's SECTION is always there, and its tag is
    # `{listbox}:{row}:sec`, which starts with the listbox prefix - which is the property
    # that matters, because `LayoutListbox._on_message` only walks its rows when
    # `sub_tag.startswith(self.tag_prefix)`. A widget left to mint its own click tag
    # produces `__click:{tag}`, and that leading prefix is exactly what fails the gate.
    if head:
        gui_blank(1, f"col-width: {LM_SCI_QL_ICON_EM}em;")
    else:
        _icon_action("arrow-up", _WARN, f"{base}:up" if base else None,
                     data, lm_sci_ql_press_up)

    # THE DEAD COLUMN, and the whole point of the layout. The icons are small; what keeps
    # a fat finger off Cancel is the HORIZONTAL distance between them, which belongs to
    # neither control, so a press that lands in it hits nothing at all.
    gui_blank(1, f"col-width: {LM_SCI_QL_GAP_EM}em;")

    _icon_action("cross-box", _DANGER, f"{base}:x" if base else None,
                 data, lm_sci_ql_press_cancel)


def lm_sci_show_for_tab(client_id, panel_row, queue_row):
    """Show the readout or the queue, never both.

    The queue belongs to the QUEUE TAB. `Row.show()` marks the layout dirty, so the row
    that stays takes the whole space rather than sharing it with a hidden one - which is
    why this is two rows toggled rather than one row rebuilt: rebuilding a plain
    sub-section out of band allocates new tags and leaves the old fill painted under it.
    """
    from science_panel import lm_sci_panel_effective_tab
    from science_tabs import LM_SCI_QUEUE_TAB
    on_queue = lm_sci_panel_effective_tab(client_id) == LM_SCI_QUEUE_TAB
    if panel_row is not None:
        panel_row.show(not on_queue)
    if queue_row is not None:
        queue_row.show(on_queue)
    return on_queue


def lm_sci_ql_empty_text():
    """What to say when there is nothing queued - never an empty box."""
    return f"$text:(nothing queued);color:{_DIM};"
