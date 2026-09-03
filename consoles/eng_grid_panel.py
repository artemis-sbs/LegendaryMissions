"""Engineering's right-column panel - what replaced the `grid_face` engine widget.

`grid_face` drew one oversized crew glyph and a `^`-separated status string, on the
only FLEX row in that column - so it was also the thing that collapsed at low
resolution, and it spent most of what space it had on the icon. The console owns
that rectangle now.

It is a `gui_tabbed_panel` with three tabs - Selected, Orders, Systems - so each one
gets the WHOLE height of a row that is 587px tall at 1920 and only 227 at 1280x720,
instead of three things sharing it badly. The tab strip is on the LEFT edge on
purpose: 26px out of a 200-268px width costs ~10 percent of the axis that has room,
where a top strip would cost 29px of the axis that collapses.

REVIEW NOTE: build this with `gui_tabbed_panel`, never `gui_info_panel`. Only the
latter writes `page.pending_info_panel`, which is a singleton the left column's info
panel owns - switch it and `gui_info_panel_send_message` and `log_raise` silently
start steering this panel instead. It is also the only one that sets
`default_tab = 1` unconditionally, which IndexErrors on a panel with fewer tabs.
"""

from sbs_utils.helpers import FrameContext, gui_text_escape
from sbs_utils.procedural.gui import (gui_row, gui_text, gui_text_area, gui_list_box,
                                      gui_sub_section)
from sbs_utils.procedural.gui.tabbed_panel import gui_tabbed_panel
from sbs_utils.procedural.gui.icon import gui_icon_name, gui_icon_name_button
from sbs_utils.procedural.gui.icon_sheet import icon_resolve
from sbs_utils.procedural.query import (to_object, to_object_list, to_id, to_blob,
                                        get_grid_selection)
from sbs_utils.procedural.roles import has_role, role
from sbs_utils.procedural.links import linked_to
from sbs_utils.procedural.inventory import get_inventory_value
from sbs_utils.procedural.grid import grid_objects, grid_get_item_theme_data
from sbs_utils.procedural.work_orders import (work_order_rows, work_orders_for,
                                              work_order_bump, work_order_cancel_all,
                                              KIND_REPAIR, KIND_MAINTAIN,
                                              PRIORITY_LOW, PRIORITY_NORMAL,
                                              PRIORITY_HIGH, PRIORITY_CRITICAL)
from sbs_utils.procedural.internal_damage import (grid_node_state, grid_system_states,
                                                  grid_system_signature,
                                                  GRID_WORN_COLOR_DEFAULT,
                                                  GRID_TUNED_COLOR_DEFAULT)
from sbs_utils.procedural.execution import log

# --- tab bookkeeping ---------------------------------------------------------
# Paths must not collide with the info panel's own (message / messages / log / ship /
# mission / hails): $INFO_PATH is a single shared task variable and the standard tab
# functions read it at TICK time.
ENG_TAB_SELECTED = "eng_sel"
ENG_TAB_ORDERS = "eng_orders"
ENG_TAB_SYSTEMS = "eng_systems"

# Where each tab caches the signature it last drew, on the PANEL - so it dies with
# the panel and nothing has to be reset at a mission boundary.
_SIG_ATTR = {ENG_TAB_SELECTED: "_eng_sig_sel",
             ENG_TAB_ORDERS: "_eng_sig_ord",
             ENG_TAB_SYSTEMS: "_eng_sig_sys"}

# The panel's tick contract is 0 = done, 1 = stay, 2 = redraw. NEVER 0 here: 0 sends
# the panel back to its default tab, which would yank the engineer off Orders once a
# second.
TICK_STAY = 1
TICK_REDRAW = 2


def _eng_ship(cid):
    """The ship this console is wired to, or None."""
    ctx = FrameContext.context
    if ctx is None or ctx.sbs is None:
        return None
    try:
        ship = ctx.sbs.get_ship_of_client(cid)
    except Exception:                               # noqa: BLE001
        return None
    return to_id(ship) or None


def _eng_selected(ship_id):
    """The grid node selected on this ship, or None.

    The selection lives on the SHIP's blob (`grid_selected_UID`), not per console, so
    two engineers on one bridge share it - the same thing the grid item list and the
    comms selection beside this panel already do.
    """
    if not ship_id:
        return None
    sel = get_grid_selection(ship_id)
    return sel or None


def _eng_tick(info_panel, path, signature):
    """Redraw a tab only when what it shows has actually moved."""
    attr = _SIG_ATTR[path]
    if signature != getattr(info_panel, attr, None):
        setattr(info_panel, attr, signature)
        return TICK_REDRAW
    return TICK_STAY


def _eng_node_color(node_id):
    """The color a node is currently drawn in, for the header glyph.

    Damcons carry their own team color in inventory; a room or system node reports
    its condition. Falls back to the library's tier constants so a theme that has no
    worn/tuned map still gets a sane glyph rather than a missing one.
    """
    if has_role(node_id, "damcons"):
        return get_inventory_value(node_id, "color", "white")
    state = grid_node_state(node_id)
    if state == "damaged":
        return get_inventory_value(node_id, "damage_color", None) or "Crimson"
    if state == "worn":
        return GRID_WORN_COLOR_DEFAULT
    if state == "tuned":
        return GRID_TUNED_COLOR_DEFAULT
    return get_inventory_value(node_id, "color", "white")


def _eng_header(title, icon_name=None, color=None, note=None):
    """The small subtle glyph plus a name, as the first row of every tab.

    1.5em, not the 2.2em the sketch started at: at gui-2 that would be 53px, a fifth
    of the whole panel on a 720-tall screen, spent on a name.
    """
    gui_row("row-height: 1.5em;")
    if icon_name:
        with gui_sub_section("col-width: 1.4em;"):
            gui_row()
            gui_icon_name(icon_name, color=color or "white")
    # gui_text_escape on every dynamic value: a grid node is named "<name>:<x>,<y>",
    # so its name CONTAINS a colon and would be read as a style property.
    gui_text(f"$text:{gui_text_escape(title)};font:gui-3;")
    if note:
        gui_text(f"$text:{gui_text_escape(note)};font:gui-1;color:#8B85A8;justify:right;")


# --- tab 1: Selected ---------------------------------------------------------
def eng_panel_selected_show(cid, left, top, width, height):
    """What is selected on the interior view, in full."""
    ship_id = _eng_ship(cid)
    node_id = _eng_selected(ship_id)
    node = to_object(node_id) if node_id else None
    if node is None:
        _eng_header("Selected")
        gui_row()
        gui_text_area("$text:(click a room or a team on the interior view);color:#888;")
        return
    is_crew = has_role(node_id, "damcons")
    _eng_header(node.name, "person" if is_crew else "gear",
                _eng_node_color(node_id), "crew" if is_crew else None)
    gui_row()
    # grid_selected_markdown lives in ai/grid_ai.py, next to the damcon status it
    # reads. It is called by BARE NAME on purpose: the loader execs every .py of a
    # mission's addons into ONE shared namespace keyed by the mission dir
    # (mast/mast.py), so siblings cross-call directly - there is no `ai.grid_ai`
    # module to import, and no other LM addon .py imports one.
    gui_text_area(grid_selected_markdown(ship_id, node_id))


def eng_selected_signature(cid):
    """Changes when the Selected tab's content would differ."""
    ship_id = _eng_ship(cid)
    node_id = _eng_selected(ship_id)
    if not node_id:
        return "none"
    return "|".join(str(x) for x in (
        node_id,
        grid_node_state(node_id),
        get_inventory_value(node_id, "last_status", ""),
        get_inventory_value(node_id, "HP", 0),
        len(linked_to(node_id, "work-order")),
    ))


def eng_panel_selected_tick(info_panel):
    return _eng_tick(info_panel, ENG_TAB_SELECTED,
                     eng_selected_signature(info_panel.client_id))


# --- tab 2: Orders -----------------------------------------------------------
def eng_order_rows(ship_id):
    """Every work order on this ship, as row dicts, highest priority first.

    Straight through to the library model, which purges as it reads - so an order on
    a node somebody else already repaired stops being listed instead of sitting there
    as a button that does nothing.
    """
    if not ship_id:
        return []
    return work_order_rows(ship_id)


# The rungs work_order_bump steps between, as words. A number on screen would make
# the engineer do arithmetic to compare two jobs.
_PRIORITY_NAMES = ((PRIORITY_CRITICAL, "critical"), (PRIORITY_HIGH, "high"),
                   (PRIORITY_NORMAL, "normal"), (PRIORITY_LOW, "low"))


def _eng_priority_name(priority):
    """The nearest rung's name, so a mission's own custom number still reads."""
    return min(_PRIORITY_NAMES, key=lambda p: abs(p[0] - priority))[1]


def _eng_order_raise(event=None, sender=None):
    """Nudge an order up a rung. The brain preempts its commit once and the team
    turns around; it does not oscillate, because the new pick is committed too."""
    target = _eng_button_target(sender)
    if target is not None:
        work_order_bump(target, 1)


def _eng_order_drop(event=None, sender=None):
    """Close an order for every team on it - what the row's minus means. Cancelling
    only one team would leave the row on screen with the others still walking."""
    target = _eng_button_target(sender)
    if target is not None:
        work_order_cancel_all(target)


def _eng_button_target(sender):
    """The order id a row's button carries.

    `data` reaches a handler as the widget's own `.data`; the callable form is given
    the sender, so read it from there rather than from a closure the loop would have
    overwritten.
    """
    data = getattr(sender, "data", None) or {}
    return data.get("target")


def _eng_order_item(item, **kwargs):
    """One order: name plus its two buttons, then kind and teams underneath.

    Two lines because one will not hold a name and two buttons at 200px wide.
    Buttons are `gui_icon_button` with `data=`, which is the escape from the
    for-loop handler trap - an `on gui_message` block registered in a loop closes
    over the last iteration's values.

    Sizes the ROWS and returns None, so the listbox calls resize_to_content().
    """
    color = "Crimson" if item["kind"] == KIND_REPAIR else GRID_WORN_COLOR_DEFAULT
    gui_row("row-height: 1.2em;")
    with gui_sub_section("col-width: 1.2em;"):
        gui_row()
        gui_icon_name("wrench" if item["kind"] == KIND_REPAIR else "gear", color=color)
    gui_text(f"$text:{gui_text_escape(item['name'])};font:gui-2;")
    # data= on the button, never an `on gui_message` block in the loop: an inline
    # block captures the loop variable at its LAST value, so every row would act on
    # the last order drawn.
    with gui_sub_section("col-width: 1.1em;"):
        gui_row()
        gui_icon_name_button("arrow-up", color="#9C92E8",
                             data={"target": item["target"]},
                             on_press=_eng_order_raise)
    with gui_sub_section("col-width: 1.1em;"):
        gui_row()
        gui_icon_name_button("minus", color="#9C92E8",
                             data={"target": item["target"]},
                             on_press=_eng_order_drop)
    gui_row("row-height: 1em;")
    teams = ", ".join(item["workers"]) or "unassigned"
    line = f"{item['kind']} - {_eng_priority_name(item['priority'])} - {teams}"
    gui_text(f"$text:{gui_text_escape(line)};font:gui-1;color:#8B85A8;")


def _eng_order_title(items=None, **kwargs):
    _eng_header("Work orders", note=str(len(items or [])))


def eng_panel_orders_show(cid, left, top, width, height):
    """Every work order on the ship, whoever it is assigned to."""
    rows = eng_order_rows(_eng_ship(cid))
    if not rows:
        _eng_header("Work orders", note="0")
        gui_row()
        gui_text_area("$text:(no work orders - select a damaged room to assign one);color:#888;")
        return
    gui_row()
    gui_list_box(rows, "item-gap: 0.2em;", item_template=_eng_order_item,
                 title_template=_eng_order_title, select=False)


def eng_orders_signature(cid):
    rows = eng_order_rows(_eng_ship(cid))
    return ",".join(f"{r['target']}:{r['kind']}:{r['priority']}:{len(r['workers'])}"
                    for r in rows)


def eng_panel_orders_tick(info_panel):
    return _eng_tick(info_panel, ENG_TAB_ORDERS,
                     eng_orders_signature(info_panel.client_id))


# --- tab 3: Systems ----------------------------------------------------------
# The eight coefficients the grid already derives. Engineering has never been able
# to see these and they are what the damage grid is FOR.
ENG_COEFFICIENTS = (
    ("beam", "all_beam_damage_coeff", 0),
    ("tube", "all_tube_damage_coeff", 0),
    ("impulse", "impulse_damage_coeff", 0),
    ("warp", "warp_damage_coeff", 0),
    ("turn", "turn_damage_coeff", 0),
    ("sensor", "sensor_damage_coeff", 0),
    ("shield fwd", "shield_damage_coeff", 0),
    ("shield aft", "shield_damage_coeff", 1),
)


def eng_coefficient_values(ship_id):
    """The derived effectiveness coefficients, as (label, percent) pairs.

    The engine answers None for a blob field nothing has set, so every read is
    coalesced - an unguarded one raises `'NoneType' < int` on a real bridge while
    the mock answers a typed default and looks fine.
    """
    blob = to_blob(ship_id) if ship_id else None
    if blob is None:
        return []
    out = []
    for label, key, idx in ENG_COEFFICIENTS:
        value = blob.get(key, idx)
        if value is None:
            continue
        out.append((label, int(round(float(value) * 100))))
    return out


def eng_panel_systems_show(cid, left, top, width, height):
    """The four system pools as glyphs, their counts, then the coefficients."""
    ship_id = _eng_ship(cid)
    _eng_header("Systems")
    states = grid_system_states(ship_id) if ship_id else []
    if not states:
        gui_row()
        gui_text_area("$text:(no interior data for this ship);color:#888;")
        return
    # The glyph row and the per-pool lines are FIXED height and come first; the
    # coefficient block takes whatever is left. At 1280x720 that block is what gets
    # cut, which is the right thing to lose.
    gui_row("row-height: 2.2em;")
    for state in states:
        gui_icon_name(state["icon"], color=state["color"])
    for state in states:
        gui_row("row-height: 1.2em;")
        gui_text(f"$text:{gui_text_escape(state['role'].upper())};font:gui-1;color:{state['color']};",
                 "col-width: 5em;")
        gui_text(f"$text:{gui_text_escape(_eng_pool_text(state))};font:gui-1;color:#8B85A8;")
    values = eng_coefficient_values(ship_id)
    if not values:
        return
    gui_row()
    body = "\n".join(f"- {label} {pct}%" for label, pct in values)
    gui_text_area("## Effectiveness\n" + body)


def _eng_pool_text(state):
    """`4 ok  2 down` - only the parts that are non-zero."""
    parts = []
    ok = state["total"] - state["hurt"] - state["worn"]
    if state["tuned"] == state["total"]:
        parts.append(f"{state['total']} tuned")
    elif ok:
        parts.append(f"{ok} ok")
    if state["worn"]:
        parts.append(f"{state['worn']} worn")
    if state["hurt"]:
        parts.append(f"{state['hurt']} down")
    return "  ".join(parts)


def eng_panel_systems_tick(info_panel):
    cid = info_panel.client_id
    ship_id = _eng_ship(cid)
    sig = grid_system_signature(ship_id) if ship_id else ""
    sig += "|" + ",".join(f"{pct}" for _, pct in eng_coefficient_values(ship_id))
    return _eng_tick(info_panel, ENG_TAB_SYSTEMS, sig)


# --- the panel ---------------------------------------------------------------
# gear / wrench / gears. Raw sheet indices, because a tab icon is an index in the
# TabbedPanel's own contract - not a name it resolves.
ENG_PANEL_TABS = (
    (ENG_TAB_SELECTED, "gear", eng_panel_selected_show, eng_panel_selected_tick),
    (ENG_TAB_ORDERS, "wrench", eng_panel_orders_show, eng_panel_orders_tick),
    (ENG_TAB_SYSTEMS, "gears", eng_panel_systems_show, eng_panel_systems_tick),
)


def eng_grid_panel(tab=0, icon_size=26):
    """Build Engineering's right-column panel into the CURRENT layout row.

    Args:
        tab (int, optional): which tab opens. Defaults to 0 (Selected).
        icon_size (int, optional): tab strip width in px. Defaults to 26.

    Returns:
        TabbedPanel | None
    """
    items = []
    for path, icon_name, show, tick in ENG_PANEL_TABS:
        index, atlas_key = icon_resolve(icon_name)
        if index is None:
            # An unknown name draws nothing and looks like a dead tab, so say which.
            log(f"no icon named {icon_name!r} for the {path} tab", "gui", "warning")
            index = 0
        items.append({"path": path, "icon": index, "show": show, "hide": None,
                      "tick": tick})
    return gui_tabbed_panel(items, tab=tab, tab_location=0, icon_size=icon_size)
