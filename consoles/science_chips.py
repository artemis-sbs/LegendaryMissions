"""Science's filter chips - one horizontal row UNDER the 2D view.

A chip is a LENS on the 2D map: selecting one writes the ship's `sci_map_filter`, the
engine's list of the ids `science_2d_view` draws (engine 1.3.15, `map_filter_set`). The
filter lives on the SHIP, so the selection does too - every science console on a ship
shows the same chips lit, because they are all looking at the same map.

The contact LIST is still out of reach: `science_sorted_list` is an engine widget with no
content API, which is why this console shows it only while nothing is selected.

TERRAIN IS A SWITCH, NOT A LENS. It drives `sci_show_nebulas` / `sci_show_asteroids`, so
it sits beside All and the lenses rather than among them: All with Terrain off is the whole
picture minus the rocks. Terrain is never put in the filter - the filter is for contacts,
and the switch alone decides whether terrain is drawn. (That is the intended rule; as of the 1.3.15 exe of 2026-10-14 the engine still hides all terrain while a filter is set, which is reported.)

The counts are REAL - computed from the sim, not typed in.

BELOW THE VIEW, NOT OVER IT. An absolute region could float it on the map the way the tab
stack does, but a filter is a persistent control rather than a transient menu, and the row
it costs is worth more than the map pixels it would cover. The 2D view's row is flex, so
adding a fixed row under it resizes the view with no arithmetic.

COUNTS EXCLUDE UNKNOWNS, and three chips carry no count at all. A number on `All`,
`Unscanned` or `Terrain` would tell the crew how many contacts they have not identified,
which is exactly the information the scan gate exists to withhold.

Prefixed `lm_sci_` because every top-level function here becomes a MAST global in one flat,
mission-wide namespace. A leading underscore is private to this file.
"""
from sbs_utils.helpers import FrameContext, gui_text_escape
from sbs_utils.procedural.gui import gui_row, gui_text
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.map_filter import map_filter_set, map_filter_clear, map_show_terrain
from sbs_utils.procedural.query import to_object, to_id, to_object_list, object_exists
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.science import science_is_unknown
from sbs_utils.procedural.sides import side_are_enemies, side_are_allies

#: The rail's own height. A chip is a touch target, like a tab row.
LM_SCI_CHIP_ROW_PX = 56

#: Each chip's width AND pitch - `col-width` on a horizontal listbox is both.
LM_SCI_CHIP_WIDTH = "6em"

#: See-through on purpose: the selection highlight is drawn on the same layer, and an
#: opaque ground hides which chips are selected.
LM_SCI_CHIP_BG = "#0E151D80"

#: Chips that must never show a number, because the number would count unknowns.
LM_SCI_CHIP_NO_COUNT = ("all", "unscanned", "terrain")

#: The rail, in order. Keys are internal; labels are what the crew reads.
LM_SCI_CHIPS = (
    ("all", "All"),
    ("threats", "Threats"),
    ("friends", "Friends"),
    ("bases", "Bases"),
    ("civilian", "Civilian"),
    ("unscanned", "Unscanned"),
    ("terrain", "Terrain"),
)

#: The chips that are lists of contacts. All and Terrain are not.
LM_SCI_CHIP_LENSES = ("threats", "friends", "bases", "civilian", "unscanned")

_SELECTED_KEY = "lm_sci_chips"


def _ship(client_id):
    ctx = FrameContext.context
    if ctx is None or ctx.sbs is None:
        return None
    try:
        return to_id(ctx.sbs.get_ship_of_client(client_id)) or None
    except Exception:                                   # noqa: BLE001
        return None


def lm_sci_chips_sets(client_id):
    """{chip: set of contact ids}.

    Computed from the sim so the counts are true. Every chip but `unscanned` holds only
    contacts this side has identified; `unscanned` holds the rest, and never shows a
    count. `all` and `terrain` are absent by construction: neither is a list of ids.
    """
    ship_id = _ship(client_id)
    if not ship_id:
        return {}
    threats, friends, bases, civilian, unscanned = set(), set(), set(), set(), set()
    for obj in to_object_list(role("__npc__") | role("__player__")):
        if obj is None:
            continue
        oid = obj.get_id()
        if oid == ship_id:
            continue
        # NEVER count a contact this side has not scanned.
        if science_is_unknown(ship_id, oid):
            unscanned.add(oid)
            continue
        if obj.has_role("station"):
            bases.add(oid)
        elif side_are_enemies(ship_id, oid):
            threats.add(oid)
        elif side_are_allies(ship_id, oid):
            friends.add(oid)
        else:
            # A side pair is NEUTRAL until a relation is declared, so without this bucket
            # a known civilian is in no chip at all and reachable only through All - which
            # reads as the rail having lost it.
            civilian.add(oid)
    return {"threats": threats, "friends": friends, "bases": bases,
            "civilian": civilian, "unscanned": unscanned}


def lm_sci_chip_row_px():
    """The rail's height, as a MAST global so the layout and this module cannot drift."""
    return LM_SCI_CHIP_ROW_PX


def lm_sci_chips_items(client_id):
    """The chip keys to draw, in rail order."""
    return [key for key, _label in LM_SCI_CHIPS]


def _label_for(key):
    for k, label in LM_SCI_CHIPS:
        if k == key:
            return label
    return key


def lm_sci_chips_template(item):
    """One chip: its label, and a live count unless counting would leak."""
    # The chip's WIDTH is the listbox's `col-width`; this row just fills it.
    gui_row("row-height: 1fr;")
    label = _label_for(item)
    if item in LM_SCI_CHIP_NO_COUNT:
        gui_text(f"$text:{gui_text_escape(label)};justify:center;font:gui-2;")
        return
    sets = lm_sci_chips_sets(FrameContext.client_id)
    count = len(sets.get(item, ()))
    gui_text(f"$text:{gui_text_escape(label)} {count};justify:center;font:gui-2;")


def lm_sci_chips_style():
    """The rail's own style. `col-width` is the chip pitch; the ground stays see-through."""
    return f"col-width:{LM_SCI_CHIP_WIDTH};background:{LM_SCI_CHIP_BG};"


def _owner(client_id):
    """Where the selection is kept: the SHIP, because the filter is the ship's. A console
    with no ship yet keeps its own until it has one."""
    return _ship(client_id) or client_id


def lm_sci_chips_selected(client_id):
    """The chips lit on this console's ship. Defaults to All, with terrain shown."""
    sel = get_inventory_value(_owner(client_id), _SELECTED_KEY, None)
    return list(sel) if sel else ["all", "terrain"]


def lm_sci_chips_normalize(client_id, chips):
    """Keep the selection sensible after a tap, then apply it.

    All is exclusive with the lenses: tapping All clears them, tapping a lens clears All,
    clearing every lens brings All back. Terrain is a switch of its own and rides along
    with either.
    """
    before = set(lm_sci_chips_selected(client_id))
    picked = set(chips.get_selected() or [])
    lenses = [k for k in LM_SCI_CHIP_LENSES if k in picked]
    if "all" in picked and "all" not in before:
        lenses = []                                   # All was just tapped
    keep = lenses or ["all"]
    if "terrain" in picked:
        keep = keep + ["terrain"]
    if set(keep) != picked:
        chips.selected = list(keep)
        chips.mark_visual_dirty()
    set_inventory_value(_owner(client_id), _SELECTED_KEY, keep)
    lm_sci_chips_apply(client_id)
    return keep


def lm_sci_chips_ids(client_id):
    """(mode, ids) for this ship's selection: ("show", ids), or ("all", None) for no
    filter."""
    sets = lm_sci_chips_sets(client_id)
    lenses = [k for k in lm_sci_chips_selected(client_id) if k in LM_SCI_CHIP_LENSES]
    if not lenses:
        return "all", None
    ids = set()
    for k in lenses:
        ids |= sets.get(k, set())
    return "show", ids


def lm_sci_chips_apply(client_id):
    """Write the selection to the ship: `sci_map_filter` cleared for All or set to the
    lenses' ids, and the two terrain flags from the Terrain chip. Unchanged lists are not
    re-sent (the library skips them)."""
    ship_id = _ship(client_id)
    if not ship_id or not object_exists(ship_id):
        return False
    mode, ids = lm_sci_chips_ids(client_id)
    if mode == "all":
        map_filter_clear(ship_id, "sci")
    else:
        map_filter_set(ship_id, ids, "sci")
    terrain = "terrain" in lm_sci_chips_selected(client_id)
    map_show_terrain(ship_id, "sci", nebulas=terrain, asteroids=terrain)
    return True


def lm_sci_chips_revision(client_id):
    """What an `on change` watches. Tracks MEMBERS, not just counts: a contact swapped for
    another keeps every count the same but is still a different answer."""
    sets = lm_sci_chips_sets(client_id)
    return tuple(sorted((k, tuple(sorted(v))) for k, v in sets.items()))


def lm_sci_chips_refresh(client_id, chips):
    """Counts moved: re-label the rail in place and re-apply the lens, since the ids
    behind it moved with them. `.items = ...`, never a repaint - a repaint would tear
    down the listbox and the handlers attached to it."""
    chips.items = lm_sci_chips_items(client_id)
    lm_sci_chips_apply(client_id)


def lm_sci_chips_follow(client_id, chips):
    """Another console on this ship changed the selection: light the same chips here."""
    want = lm_sci_chips_selected(client_id)
    if set(chips.get_selected() or []) != set(want):
        chips.selected = list(want)
        chips.mark_visual_dirty()
