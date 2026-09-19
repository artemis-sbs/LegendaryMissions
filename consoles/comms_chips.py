"""The comms filter chips - one horizontal row above the comms 2D view.

A chip is a LENS on the contact list: Threats, Friends, Stations, Jobs, Can order,
Markers, Favorites, then one chip per SIDE that has contacts in view. Each one is a set of ids the SCRIPT computes
from data the engine never sees (sides, roles, offers, who takes orders), with a live
count on the chip.

Tap chips to combine them (a contact shows if ANY selected lens has it). All resets.

UNKNOWN CONTACTS ARE NEVER COUNTED. A contact this ship has not scanned is in no lens,
so no count, side chip or filter can tell the crew it is there or what it is. All has
NO count for the same reason: All clears the filter, so the map shows unknowns too, and
any number on it would either disagree with the map or give them away.

`lm_comms_chips_apply` writes the selection to the ship's `comms_map_filter` engine data
set (`comms_map_filter_set` / `_clear`), so the comms 2D map shows only the lens. It is
per SHIP: every comms console on it shares one filter, and the last tap wins.

Prefixed `lm_comms_chips_` because every top-level function here is a MAST global in
one flat, mission-wide namespace.
"""
from sbs_utils.helpers import FrameContext
try:
    from sbs_utils.spaceobject import SELECTION_ROLE
except ImportError:                                     # an sbslib older than the role
    SELECTION_ROLE = "__selection__"
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.procedural.gui.viewscreen import viewscreen_home_ship
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import object_exists, to_object, get_comms_selection
from sbs_utils.procedural.roles import role, has_role
from sbs_utils.procedural.science import science_is_unknown
from sbs_utils.procedural.comms import comms_map_filter_set, comms_map_filter_clear
from sbs_utils.procedural.sides import (side_are_allies, side_are_enemies, to_side_id,
                                        side_get_display_name)

# key, label - the fixed chips, in rail order. Side chips follow them, keyed
# "side:<side key>".
_CHIPS = [
    ("all", "All"),
    ("threats", "Threats"),
    ("friends", "Friends"),
    ("stations", "Stations"),
    ("jobs", "Quests"),
    ("orders", "Can order"),
    ("markers", "Markers"),
    ("favorites", "Favorites"),
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
    favorites = lm_comms_chips_favorites(ship_id)
    sets = {k: set() for k, _ in _CHIPS}
    for i in contacts:
        # An unscanned contact joins no lens - its side, role and count are exactly what
        # the crew does not know yet.
        if science_is_unknown(ship_id, i):
            continue
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
        if i in favorites:
            sets["favorites"].add(i)
        try:
            if offer_count(client_id=client_id, ship_id=ship_id, object_id=i) > 0:
                sets["jobs"].add(i)
        except Exception:                               # noqa: BLE001
            pass
    # MARKERS are every behav_selection object - map, nebula, relic and order markers.
    # They are map furniture, not contacts: drawn on radar for everyone, so they skip the
    # unscanned rule and join no other lens. A marker that is still DARK (a relic marker
    # nobody has reached, `unselectable` set) is hidden, so it is not counted either.
    for i in role(SELECTION_ROLE):
        obj = to_object(i)
        if obj is None or i == ship_id:
            continue
        if obj.data_set.get("unselectable", 0):
            continue
        # Only NAMED markers: a nameless one (a boundary helper, a relic barrier) is
        # nothing a crew could pick out of a list.
        if not str(getattr(obj, "name", "") or "").strip():
            continue
        sets["markers"].add(i)
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
    only when a count does, or a side comes into or leaves view.

    Tracks the lens MEMBERS, not just counts: a contact swapped for another keeps every
    count the same but must still re-apply the filter."""
    sets = lm_comms_chips_sets(client_id)
    return tuple(sorted((k, tuple(sorted(v))) for k, v in sets.items() if k != "all"))


def lm_comms_chips_template(item):
    """One chip: its label and live count, centered."""
    from sbs_utils.procedural.gui.row import gui_row
    from sbs_utils.procedural.gui.text import gui_text
    # The chip's WIDTH is the listbox's `col-width` (layout_widgets.mast); this row just
    # fills it.
    gui_row("row-height: 1fr;")
    if item == "all":
        # No count on All: see the module docstring.
        gui_text(f"$text:{_chip_label(item)};justify:center;font:gui-2;")
        return
    sets = lm_comms_chips_sets(FrameContext.client_id)
    n = len(sets.get(item, ()))
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
    """Write this console's lens to its ship's `comms_map_filter`: cleared for All, the
    lens's ids otherwise. Unchanged sets are not re-sent (the library skips them)."""
    mode, ids = lm_comms_chips_ids(client_id)
    set_inventory_value(client_id, "lm_comms_chips_filter", (mode, sorted(ids) if ids else []))
    ship_id = viewscreen_home_ship(client_id)
    if not ship_id or not object_exists(ship_id):
        return False
    if mode == "all":
        comms_map_filter_clear(ship_id)
    else:
        comms_map_filter_set(ship_id, ids)
    return True


def lm_comms_chips_refresh(client_id, lb):
    """Counts moved: redraw the chips' own rows (not the page) and re-apply the lens,
    since the ids behind a lens change with them."""
    lb.items = lm_comms_chips_items(client_id)
    lm_comms_chips_apply(client_id)


# FAVORITES are kept on the SHIP, so the whole crew shares one list - whoever starred a
# contact, every comms console on that ship sees it in the Favorites chip.
_FAV_KEY = "lm_comms_favorites"

#: The star is LM's own art (media/epadd/icons.png, registered in epadd.mast): the
#: built-in sheet has only a rank badge. Filled = a favorite, outline = not.
_STAR_ON = "lm.star"
_STAR_OFF = "lm.star_outline"


def lm_comms_chips_favorites(ship_id):
    """The contact ids this ship has starred."""
    return set(get_inventory_value(ship_id, _FAV_KEY, None) or ())


def lm_comms_chips_star_target(client_id):
    """What the star acts on: the console's comms selection, when it is another object
    this ship has SCANNED. An unknown contact is not starrable - the star would be a
    lens on something the crew cannot identify, and it could never show in the
    Favorites chip anyway (unknowns are in no lens)."""
    ship_id = viewscreen_home_ship(client_id)
    sel = get_comms_selection(ship_id) if ship_id else 0
    if not sel or sel == ship_id or not object_exists(sel):
        return ship_id, 0
    if science_is_unknown(ship_id, sel):
        return ship_id, 0
    return ship_id, sel


def lm_comms_chips_toggle_favorite(client_id):
    """Star or unstar the console's comms selection. Returns the new state (False when
    there is nothing to star)."""
    ship_id, sel = lm_comms_chips_star_target(client_id)
    if not sel:
        return False
    favs = lm_comms_chips_favorites(ship_id)
    if sel in favs:
        favs.discard(sel)
    else:
        favs.add(sel)
    set_inventory_value(ship_id, _FAV_KEY, sorted(favs))
    # Every console on the ship recounts now rather than in a couple of seconds.
    for cid in list(_SETS):
        if _SETS[cid][1] == ship_id:
            del _SETS[cid]
    return sel in favs


def lm_comms_chips_star_look(client_id):
    """(icon name, color) for the star: a gold filled star when the selection is a
    favorite, an outline when it is not, a near-invisible outline when nothing
    starrable is selected."""
    ship_id, sel = lm_comms_chips_star_target(client_id)
    if not sel:
        return _STAR_OFF, "#3A4552"
    if sel in lm_comms_chips_favorites(ship_id):
        return _STAR_ON, "#F2C14E"
    return _STAR_OFF, "#8A9AAB"


def lm_comms_chips_star_button(client_id, style):
    """Build the star: an image button showing the current look."""
    from sbs_utils.procedural.gui.icon import gui_icon_name_button
    name, color = lm_comms_chips_star_look(client_id)
    return gui_icon_name_button(name, color=color, style=style)


def lm_comms_chips_star_show(client_id, star):
    """Bring a built star up to date - in place, only that one image is re-sent."""
    from sbs_utils.procedural.gui.icon import gui_icon_rename
    name, color = lm_comms_chips_star_look(client_id)
    return gui_icon_rename(star, name, color)


def lm_comms_chips_star_revision(client_id):
    """What an `on change` watches to repaint the star: the selection and its state."""
    ship_id, sel = lm_comms_chips_star_target(client_id)
    return (sel, sel in lm_comms_chips_favorites(ship_id) if sel else False)


def lm_comms_chips_clear():
    """Forget every console's cached counts (reset_mission_state / tests)."""
    _SETS.clear()
