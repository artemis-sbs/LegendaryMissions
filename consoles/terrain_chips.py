"""The radar chips on Helm and Weapons: one slim row under the zoom control.

Six chips, two kinds:

* `All`, `Threats`, `Friends`, `Bases` pick WHAT CONTACTS the radar draws. The three
  lenses write the ship's `helm_map_filter` / `weapon_map_filter` - the engine's list of
  the ids that console's 2D view draws (engine 1.3.15, `map_filter_set`) - and All is no
  filter. All is exclusive with the lenses, exactly as on Comms and Science: tapping it
  clears them, tapping a lens clears it, and clearing every lens brings it back.
* `Nebulas`, `Asteroids` are SWITCHES on the engine's `<console>_show_nebulas` /
  `<console>_show_asteroids` flags. Lit means shown, which is the engine's default.

TWO LISTBOXES SIDE BY SIDE, one per kind, because the kinds need different widths. Measured
on the engine at gui-1, "Asteroids" is 65.5px and the widest lens label 52.4px, so one
uniform pitch wide enough for "Asteroids" did not fit six chips between the info panel and
Helm's camera dial on a 1024-wide screen, and at 65-69px its last letter wrapped out of
sight. Lenses at 58px and switches at 72px fit in 376px of the 390 there.

WIDER ON A WIDER SCREEN. Those widths are the 1024-wide floor. The room between the info
panel (300px) and the right-hand stack grows with the screen, so the chips scale into it -
up to LM_TERRAIN_SCALE_MAX - and step up to the next font once the chips are wide enough
for its text (gui-2 "Asteroids" is 71.5px). A screen whose size has not been reported yet
gets the floor.

All of it lives on the SHIP, so every helm console on a ship shares one row and every
weapons console another - the chips on each follow whichever of them was tapped last.

What a lens holds is science's answer (`science_chips.lm_sci_chips_sets`): only contacts
this side has identified, so a chip never puts an unscanned contact in a category.

SLIM ON PURPOSE. These are set and forgotten, so they get a thin row that costs the radar
30px rather than a band of their own.

Terrain is never put in the filter: the lenses choose contacts, and the switches alone
decide whether nebulas and asteroids are drawn, lens or no lens. That is the intended rule;
as of the 1.3.15 exe of 2026-10-14 the engine still hides all terrain while a filter is set, which is reported.

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

#: Each chip's width AND pitch at the 1024-wide floor, per group - `col-width` on a
#: horizontal listbox is both. Sized from the engine's own text widths (gui-1): "Threats"
#: 52.4px, "Asteroids" 65.5px.
LM_TERRAIN_CHIP_WIDTH = {"lens": 58, "terrain": 72}

#: The most the chips grow on a wide screen. Past this they would read as a toolbar.
LM_TERRAIN_SCALE_MAX = 1.6

#: At this scale the chips have room for gui-2 (gui-2 "Asteroids" is 71.5px, the
#: terrain pitch here is 90px).
LM_TERRAIN_SCALE_BIG_FONT = 1.25

#: What the row leaves free: the info panel on the left, and on the right Helm's camera
#: dial (still curving in at this height) or Weapons' right-hand column.
LM_TERRAIN_LEFT_PX = 300
LM_TERRAIN_RIGHT_PX = {"helm": 334, "weapon": 290}

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
    ("asteroids", "Asteroids"),
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


def _group_keys(group):
    if group == "lens":
        return ("all",) + LM_TERRAIN_CHIP_LENSES
    if group == "terrain":
        return LM_TERRAIN_CHIP_SWITCHES
    return tuple(key for key, _label in LM_TERRAIN_CHIPS)


def lm_terrain_chips_items(group=None):
    """The chip keys to draw, in order: one group ("lens" / "terrain"), or all six."""
    keys = _group_keys(group)
    return [key for key, _label in LM_TERRAIN_CHIPS if key in keys]


def lm_terrain_chips_scale(client_id=None, console="helm"):
    """How much wider than the 1024-wide floor the chips can be on this client's screen."""
    from sbs_utils.procedural.gui import gui_screen_size, gui_screen_size_known
    if client_id is None or not gui_screen_size_known(client_id):
        return 1.0
    room = (float(gui_screen_size(client_id).x) - LM_TERRAIN_LEFT_PX
            - LM_TERRAIN_RIGHT_PX.get(console, LM_TERRAIN_RIGHT_PX["helm"]))
    floor = sum(_group_px(g, 1.0) for g in ("lens", "terrain"))
    return max(1.0, min(LM_TERRAIN_SCALE_MAX, room / floor))


def _pitch(group, scale):
    return int(LM_TERRAIN_CHIP_WIDTH[group] * scale)


def _group_px(group, scale):
    return _pitch(group, scale) * len(_group_keys(group)) + 4


def lm_terrain_chips_group_px(group, client_id=None, console="helm"):
    """How wide a group's listbox is: its chips at their pitch, plus the box padding."""
    return _group_px(group, lm_terrain_chips_scale(client_id, console))


def lm_terrain_chips_style(group="lens", client_id=None, console="helm"):
    """A group's own style. `col-width` is the chip pitch; the ground stays see-through."""
    pitch = _pitch(group, lm_terrain_chips_scale(client_id, console))
    return f"col-width:{pitch}px;background:{LM_TERRAIN_CHIP_BG};"


def lm_terrain_chips_font(client_id=None):
    """gui-1 at the floor, gui-2 once the chips are wide enough for it. Judged on Helm's
    tighter row so a crew sees the same font on Helm and Weapons."""
    if lm_terrain_chips_scale(client_id, "helm") >= LM_TERRAIN_SCALE_BIG_FONT:
        return "gui-2"
    return "gui-1"


def lm_terrain_chips_template(item):
    """One chip: its label, small."""
    gui_row("row-height: 1fr;")
    label = dict(LM_TERRAIN_CHIPS).get(item, item)
    font = lm_terrain_chips_font(FrameContext.client_id)
    gui_text(f"$text:{label};justify:center;font:{font};")


def _lenses(ship_id, console):
    return [k for k in (get_inventory_value(ship_id, _lens_key(console), None) or ())
            if k in LM_TERRAIN_CHIP_LENSES]


def lm_terrain_chips_selected(client_id, console, group=None):
    """The chips lit for this console's ship: All or its lenses, and the terrain it is
    drawing - one group, or both.

    With no ship to ask, All and the two switches - what the engine draws by default.
    """
    ship_id = _ship(client_id)
    if not ship_id:
        lit = ["all"] + list(LM_TERRAIN_CHIP_SWITCHES)
    else:
        nebulas, asteroids = map_terrain_shown(ship_id, console)
        lit = ((_lenses(ship_id, console) or ["all"])
               + [key for key, on in (("nebulas", nebulas), ("asteroids", asteroids)) if on])
    keys = _group_keys(group)
    return [k for k in lit if k in keys]


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


def lm_terrain_chips_apply(client_id, console, chips, group=None):
    """A chip was tapped in one group (or the old single row): settle All against the
    lenses, remember them on the ship, and write the filter or the flags that group owns."""
    ship_id = _ship(client_id)
    if not ship_id:
        return False
    picked = set(chips.get_selected() or [])
    if group in (None, "lens"):
        lenses = [k for k in LM_TERRAIN_CHIP_LENSES if k in picked]
        if "all" in picked and _lenses(ship_id, console):
            lenses = []                                   # All was just tapped
        keep = set(lenses or ["all"])
        if group is None:
            keep |= picked & set(LM_TERRAIN_CHIP_SWITCHES)
        if keep != picked:
            chips.selected = [k for k in lm_terrain_chips_items(group) if k in keep]
            chips.mark_visual_dirty()
            picked = keep
        set_inventory_value(ship_id, _lens_key(console), lenses)
    if group in (None, "terrain"):
        map_show_terrain(ship_id, console, nebulas="nebulas" in picked,
                         asteroids="asteroids" in picked)
    return lm_terrain_chips_write(client_id, console)


def lm_terrain_chips_follow(client_id, console, chips, group=None):
    """The ship's row moved - another console, or a mission: light the same chips here."""
    want = lm_terrain_chips_selected(client_id, console, group)
    if set(chips.get_selected() or []) != set(want):
        chips.selected = list(want)
        chips.mark_visual_dirty()


def lm_terrain_chips_revision(client_id, console):
    """What an `on change` watches so a lit lens keeps up with the contacts behind it:
    its ids, and nothing at all while no lens is lit."""
    mode, ids = lm_terrain_chips_ids(client_id, console)
    return (mode, tuple(sorted(ids)) if ids else ())
