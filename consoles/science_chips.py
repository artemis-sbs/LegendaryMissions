"""Science's filter chips - one horizontal row UNDER the 2D view.

THIS DOES NOT FILTER ANYTHING YET, and that is deliberate. It is here so the shape can be
looked at and argued with on a real bridge before anyone asks the engine for the hook that
would make it work. Two separate things are missing, and neither is script's to fix:

* the contact LIST is `science_sorted_list`, an engine widget with no content API at all -
  `sbs` exposes `send_comms_*` and `send_grid_*` and nothing named `send_science_*`;
* the 2D MAP has no science equivalent of `comms_map_filter_set`, which is a data_set key
  on the player ship that the engine reads. One key, already proven on comms.

So selecting a chip remembers the selection, redraws the rail, and stops. The counts are
REAL - computed from the sim, not typed in - because a rail of invented numbers would
prove nothing about whether the idea reads well.

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
from sbs_utils.procedural.query import to_object, to_id, to_object_list
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
    """{chip: set of contact ids}, with unknowns already excluded.

    Computed from the sim so the counts are true. `all` is absent by construction: it has
    no count, so it needs no membership.
    """
    ship_id = _ship(client_id)
    if not ship_id:
        return {}
    threats, friends, bases, civilian = set(), set(), set(), set()
    for obj in to_object_list(role("__npc__")):
        if obj is None:
            continue
        oid = obj.get_id()
        # NEVER count a contact this side has not scanned.
        if science_is_unknown(ship_id, oid):
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
            "civilian": civilian}


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


def lm_sci_chips_selected(client_id):
    """The chips this console has selected. Defaults to All."""
    sel = get_inventory_value(client_id, _SELECTED_KEY, None)
    return list(sel) if sel else ["all"]


def lm_sci_chips_normalize(client_id, chips):
    """All is exclusive: picking it clears the rest, picking anything else clears All.

    Remembered per client, because two science consoles on one bridge are looking for
    different things.
    """
    selected = list(chips.get_selected() or [])
    previous = lm_sci_chips_selected(client_id)
    if "all" in selected and "all" not in previous and len(selected) > 1:
        selected = ["all"]
    elif len(selected) > 1 and "all" in selected:
        selected = [s for s in selected if s != "all"]
    if not selected:
        selected = ["all"]
    set_inventory_value(client_id, _SELECTED_KEY, selected)
    if list(chips.get_selected() or []) != selected:
        chips.selected = selected
    return selected


def lm_sci_chips_revision(client_id):
    """What an `on change` watches. Tracks MEMBERS, not just counts: a contact swapped for
    another keeps every count the same but is still a different answer."""
    sets = lm_sci_chips_sets(client_id)
    return tuple(sorted((k, tuple(sorted(v))) for k, v in sets.items()))


def lm_sci_chips_refresh(client_id, chips):
    """Re-label the rail in place. `.items = ...` from an `on change`, never a repaint -
    a repaint would tear down the listbox and the handlers attached to it."""
    chips.items = lm_sci_chips_items(client_id)
