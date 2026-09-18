"""The comms filter chips - one horizontal row above the comms 2D view.

A chip is a LENS on the contact list: Threats, Friends, Stations, Jobs, Can order, then
one chip per SIDE that has contacts in view. Each one is a set of ids the SCRIPT computes
from data the engine never sees (sides, roles, offers, who takes orders), with a live
count on the chip.

Tap chips to combine them (a contact shows if ANY selected lens has it). All resets.
No chip for unscanned contacts: the 2D view does not show unknowns, so there is nothing
to hide.

THE ENGINE CANNOT FILTER THE LIST YET. `lm_comms_chips_apply` computes the id set and
hands it to `sbs.set_comms_list_filter(ship, mode, ids)` IF the engine has it - a
placeholder name for a hook that does not exist today. Until it does, the chips choose
and count but the engine's list is unchanged.

Prefixed `lm_comms_chips_` because every top-level function here is a MAST global in
one flat, mission-wide namespace.
"""
from sbs_utils.helpers import FrameContext
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.procedural.gui.viewscreen import viewscreen_home_ship
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import object_exists, to_object
from sbs_utils.procedural.roles import role, has_role
from sbs_utils.procedural.sides import (side_are_allies, side_are_enemies, to_side_id,
                                        side_get_display_name)

# key, label - the fixed chips, in rail order. Side chips follow them, keyed
# "side:<side key>".
_CHIPS = [
    ("all", "All"),
    ("threats", "Threats"),
    ("friends", "Friends"),
    ("stations", "Stations"),
    ("jobs", "Jobs"),
    ("orders", "Can order"),
]
_LABELS = dict(_CHIPS)
_SIDE = "side:"

#: Seconds between recounts. Offers run their providers per contact, so counting every
#: tick on every comms console is not free; a chip count a couple of seconds old is fine.
_RECOUNT_SECONDS = 2.0

# client_id -> (sim_seconds, {key: set(ids)})
_SETS = {}

_SELECTED_KEY = "lm_comms_chips"


def lm_comms_chips_items(client_id):
    """The chip keys, in rail order - the listbox's items. The fixed chips, then one per
    side with contacts in view, ordered by the side's name."""
    sets = lm_comms_chips_sets(client_id)
    sides = sorted((k for k in sets if k.startswith(_SIDE)), key=_chip_label)
    return [k for k, _ in _CHIPS] + sides


def _chip_label(key):
    if key.startswith(_SIDE):
        side = key[len(_SIDE):]
        return side_get_display_name(side) or side
    return _LABELS.get(key, key)


def _can_order(ship_id, other_id):
    # LM's comms addon owns the rule; the consoles addon must not depend on it loading.
    fn = MastGlobals.globals.get("lm_can_take_orders")
    if fn is None:
        return False
    try:
        return bool(fn(ship_id, other_id))
    except Exception:                                   # noqa: BLE001
        return False


def _compute(client_id, ship_id):
    from sbs_utils.procedural.offer import offer_count
    contacts = [i for i in (role("__npc__") | role("__player__"))
                if i != ship_id and object_exists(i)]
    my_side = to_side_id(ship_id, warn=False)
    sets = {k: set() for k, _ in _CHIPS}
    for i in contacts:
        sets["all"].add(i)
        side = getattr(to_object(i), "side", None)
        if side:
            sets.setdefault(_SIDE + side, set()).add(i)
        if side_are_enemies(ship_id, i):
            sets["threats"].add(i)
        elif my_side is not None and (to_side_id(i, warn=False) == my_side or side_are_allies(ship_id, i)):
            # Your own side is not "allied" by link - it is simply yours.
            sets["friends"].add(i)
        if has_role(i, "station"):
            sets["stations"].add(i)
        if _can_order(ship_id, i):
            sets["orders"].add(i)
        try:
            if offer_count(client_id=client_id, ship_id=ship_id, object_id=i) > 0:
                sets["jobs"].add(i)
        except Exception:                               # noqa: BLE001
            pass
    return sets


def lm_comms_chips_sets(client_id, force=False):
    """{chip key: set of contact ids} for this console, recounted at most every couple
    of seconds. Empty sets when the console has no ship."""
    ship_id = viewscreen_home_ship(client_id)
    now = FrameContext.sim_seconds or 0
    cached = _SETS.get(client_id)
    # `0 <=`: sim time restarts with a mission, so a clock that went BACKWARDS is stale.
    if (not force and cached is not None and cached[1] == ship_id
            and 0 <= now - cached[0] < _RECOUNT_SECONDS):
        return cached[2]
    if not ship_id or not object_exists(ship_id):
        sets = {k: set() for k, _ in _CHIPS}
    else:
        sets = _compute(client_id, ship_id)
    _SETS[client_id] = (now, ship_id, sets)
    return sets


def lm_comms_chips_revision(client_id):
    """What an `on change` watches: which chips there are and their counts. Changes
    only when a count does, or a side comes into or leaves view."""
    sets = lm_comms_chips_sets(client_id)
    return tuple(sorted((k, len(v)) for k, v in sets.items()))


def lm_comms_chips_template(item):
    """One chip: its label and live count, centered."""
    from sbs_utils.procedural.gui.row import gui_row
    from sbs_utils.procedural.gui.text import gui_text
    sets = lm_comms_chips_sets(FrameContext.client_id)
    n = len(sets.get(item, ()))
    # The chip's WIDTH is the listbox's `col-width` (layout_widgets.mast); this row just
    # fills it.
    gui_row("row-height: 1fr;")
    gui_text(f"$text:{_chip_label(item)} {n};justify:center;font:gui-2;")


def lm_comms_chips_selected(client_id):
    """The chips this console has selected (defaults to All)."""
    sel = get_inventory_value(client_id, _SELECTED_KEY, None)
    return list(sel) if sel else ["all"]


def lm_comms_chips_normalize(client_id, lb):
    """Keep the selection sensible after a tap, then apply it.

    All is exclusive with the lenses: tapping All clears them, tapping a lens clears All,
    clearing every lens brings All back.
    """
    before = set(lm_comms_chips_selected(client_id))
    picked = set(lb.get_selected() or [])
    now = [k for k in lm_comms_chips_items(client_id) if k in picked]
    lenses = [k for k in now if k != "all"]
    if "all" in now and "all" not in before:
        lenses = []                                   # All was just tapped
    keep = lenses or ["all"]
    if keep != now:
        lb.selected = list(keep)
        lb.mark_visual_dirty()
    set_inventory_value(client_id, _SELECTED_KEY, keep)
    lm_comms_chips_apply(client_id)
    return keep


def lm_comms_chips_ids(client_id):
    """(mode, ids) for this console's selection: ("show", ids), or ("all", None) for no
    filter. A side chip whose side has left view contributes nothing."""
    sel = lm_comms_chips_selected(client_id)
    sets = lm_comms_chips_sets(client_id)
    lenses = [k for k in sel if k != "all"]
    if not lenses:
        return "all", None
    ids = set()
    for k in lenses:
        ids |= sets.get(k, set())
    return "show", ids


def lm_comms_chips_apply(client_id):
    """Push this console's lens to the engine - IF the engine can take it.

    `set_comms_list_filter` is a PLACEHOLDER for an engine hook that does not exist yet;
    without it this only records what would be shown.
    """
    mode, ids = lm_comms_chips_ids(client_id)
    set_inventory_value(client_id, "lm_comms_chips_filter", (mode, sorted(ids) if ids else []))
    sbs = FrameContext.context.sbs if FrameContext.context else None
    hook = getattr(sbs, "set_comms_list_filter", None)
    if hook is None:
        return False
    ship_id = viewscreen_home_ship(client_id)
    if mode == "all":
        hook(ship_id, "all", [])
    else:
        hook(ship_id, mode, sorted(ids))
    return True


def lm_comms_chips_refresh(client_id, lb):
    """Counts moved: redraw the chips' own rows (not the page) and re-apply the lens,
    since the ids behind a lens change with them."""
    lb.items = lm_comms_chips_items(client_id)
    lm_comms_chips_apply(client_id)


def lm_comms_chips_clear():
    """Forget every console's cached counts (reset_mission_state / tests)."""
    _SETS.clear()
