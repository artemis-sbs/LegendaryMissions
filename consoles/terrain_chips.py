"""The radar chips on Helm and Weapons: one slim row under the zoom control.

Six chips, two kinds:

* `All`, `Threats`, `Friends`, `Bases` pick WHAT CONTACTS the radar draws. The three
  lenses write the ship's `helm_map_filter` / `weapon_map_filter` - the engine's list of
  the ids that console's 2D view draws (engine 1.3.15, `map_filter_set`) - and All is no
  filter. All is exclusive with the lenses, exactly as on Comms and Science: tapping it
  clears them, tapping a lens clears it, and clearing every lens brings it back.
* `Nebulas`, `Rocks` (asteroids) are SWITCHES on the engine's `<console>_show_nebulas` /
  `<console>_show_asteroids` flags. Lit means shown, which is the engine's default.

All of it lives on the SHIP, so every helm console on a ship shares one row and every
weapons console another - the chips on each follow whichever of them was tapped last.

What a lens holds is science's answer (`science_chips.lm_sci_chips_sets`): only contacts
this side has identified, so a chip never puts an unscanned contact in a category.

SLIM ON PURPOSE. These are set and forgotten, so they get a thin row that costs the radar
30px rather than a band of their own.

KNOWN ENGINE LIMITS (1.3.15, measured): while a lens is lit the engine draws only what it
lists, so terrain is hidden whatever its switch says; and clearing a filter empties the
blob but the view keeps the last list, so un-lighting the last lens does not bring
everything back. The clear is still what this sends - it is what a fixed engine honors.

Prefixed `lm_terrain_` because every top-level function here becomes a MAST global in one
flat, mission-wide namespace. A leading underscore is private to this file.
"""
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui import gui_row, gui_text
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.map_filter import (map_filter_set, map_filter_clear,
                                             map_show_terrain, map_terrain_shown)
from sbs_utils.procedural.query import to_id, object_exists

#: The row's height. Thin: a label and a highlight, not a touch target the size of a tab.
LM_TERRAIN_CHIP_ROW_PX = 30

#: Each chip's width AND pitch - `col-width` on a horizontal listbox is both. Six of
#: them fit between the info panel and Helm's camera dial on a 1024-wide screen.
LM_TERRAIN_CHIP_WIDTH = "65px"

#: See-through on purpose: the selection highlight is drawn on the same layer, and an
#: opaque ground hides which chips are selected.
LM_TERRAIN_CHIP_BG = "#0E151D80"

#: The chips, in order.
LM_TERRAIN_CHIPS = (
    ("all", "All"),
    ("threats", "Threats"),
    ("friends", "Friends"),
    ("bases", "Bases"),
    ("nebulas", "Nebulas"),
    # "Rocks", not "Asteroids": the engine keeps ~20px of a text cell back (measured on a
    # 1024-wide client, at 65px and again at 69px), so the full word lost its last letter
    # at any width six chips can have here. The key is still the engine's word.
    ("asteroids", "Rocks"),
)

#: The chips that are lists of contacts.
LM_TERRAIN_CHIP_LENSES = ("threats", "friends", "bases")

#: The chips that are engine flags. Keys are map_show_terrain's own argument names.
LM_TERRAIN_CHIP_SWITCHES = ("nebulas", "asteroids")


def _ship(client_id):
    ctx = FrameContext.context
    if ctx is None or ctx.sbs is None:
        return None
    try:
        ship_id = to_id(ctx.sbs.get_ship_of_client(client_id)) or None
    except Exception:                                   # noqa: BLE001
        return None
    return ship_id if ship_id and object_exists(ship_id) else None


def _lens_key(console):
    return f"lm_radar_lenses_{console}"


def lm_terrain_chip_row_px():
    """The row's height, as a MAST global so the layout and this module cannot drift."""
    return LM_TERRAIN_CHIP_ROW_PX


def lm_terrain_chips_items():
    """The chip keys to draw, in order."""
    return [key for key, _label in LM_TERRAIN_CHIPS]


def lm_terrain_chips_style():
    """The row's own style. `col-width` is the chip pitch; the ground stays see-through."""
    return f"col-width:{LM_TERRAIN_CHIP_WIDTH};background:{LM_TERRAIN_CHIP_BG};"


def lm_terrain_chips_template(item):
    """One chip: its label, small."""
    gui_row("row-height: 1fr;")
    label = dict(LM_TERRAIN_CHIPS).get(item, item)
    gui_text(f"$text:{label};justify:center;font:gui-1;")


def _lenses(ship_id, console):
    return [k for k in (get_inventory_value(ship_id, _lens_key(console), None) or ())
            if k in LM_TERRAIN_CHIP_LENSES]


def lm_terrain_chips_selected(client_id, console):
    """The chips lit for this console's ship: All or its lenses, and the terrain it is
    drawing.

    With no ship to ask, All and the two switches - what the engine draws by default.
    """
    ship_id = _ship(client_id)
    if not ship_id:
        return ["all"] + list(LM_TERRAIN_CHIP_SWITCHES)
    nebulas, asteroids = map_terrain_shown(ship_id, console)
    return ((_lenses(ship_id, console) or ["all"])
            + [key for key, on in (("nebulas", nebulas), ("asteroids", asteroids)) if on])


def lm_terrain_chips_ids(client_id, console):
    """(mode, ids) for this ship's lenses: ("show", ids), or ("all", None) for no filter."""
    ship_id = _ship(client_id)
    lenses = _lenses(ship_id, console) if ship_id else []
    if not lenses:
        return "all", None
    from science_chips import lm_sci_chips_sets
    sets = lm_sci_chips_sets(client_id)
    ids = set()
    for k in lenses:
        ids |= sets.get(k, set())
    return "show", ids


def lm_terrain_chips_write(client_id, console):
    """Write the ship's lenses to its `<console>_map_filter`: cleared when none is lit.
    Unchanged lists are not re-sent (the library skips them)."""
    ship_id = _ship(client_id)
    if not ship_id:
        return False
    mode, ids = lm_terrain_chips_ids(client_id, console)
    if mode == "all":
        map_filter_clear(ship_id, console)
    else:
        map_filter_set(ship_id, ids, console)
    return True


def lm_terrain_chips_apply(client_id, console, chips):
    """A chip was tapped: settle All against the lenses, remember the lenses on the ship,
    then write filter and flags."""
    ship_id = _ship(client_id)
    if not ship_id:
        return False
    picked = set(chips.get_selected() or [])
    lenses = [k for k in LM_TERRAIN_CHIP_LENSES if k in picked]
    if "all" in picked and _lenses(ship_id, console):
        lenses = []                                   # All was just tapped
    keep = set(lenses or ["all"]) | (picked & set(LM_TERRAIN_CHIP_SWITCHES))
    if keep != picked:
        chips.selected = [k for k in lm_terrain_chips_items() if k in keep]
        chips.mark_visual_dirty()
        picked = keep
    set_inventory_value(ship_id, _lens_key(console), lenses)
    map_show_terrain(ship_id, console, nebulas="nebulas" in picked,
                     asteroids="asteroids" in picked)
    return lm_terrain_chips_write(client_id, console)


def lm_terrain_chips_follow(client_id, console, chips):
    """The ship's row moved - another console, or a mission: light the same chips here."""
    want = lm_terrain_chips_selected(client_id, console)
    if set(chips.get_selected() or []) != set(want):
        chips.selected = list(want)
        chips.mark_visual_dirty()


def lm_terrain_chips_revision(client_id, console):
    """What an `on change` watches so a lit lens keeps up with the contacts behind it:
    its ids, and nothing at all while no lens is lit."""
    mode, ids = lm_terrain_chips_ids(client_id, console)
    return (mode, tuple(sorted(ids)) if ids else ())
