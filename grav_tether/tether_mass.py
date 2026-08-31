"""Ship mass for the grav-tether constraints layer.

The library ships the MECHANISM (who drags whom, how much a haul costs) and leaves the
NUMBERS to a mission, because "what does a freighter weigh" is a game-balance question.
This installs LM's answer: `tether_mass.yaml`, seeded from hullpoints and hand-corrected
where mass and toughness disagree.

Prefixed `lm_tether_`, not `grav_tether_`: an addon function with the library's prefix
would shadow the primitive it is built on.
"""

from sbs_utils.fs import load_yaml_string
from sbs_utils.procedural.execution import log
from sbs_utils.procedural.grav_tether import (grav_tether_set_grab_speed_limit,
                                              grav_tether_set_mass_fn,
                                              grav_tether_set_pull_bonus_fn,
                                              grav_tether_set_range_limit,
                                              grav_tether_set_tow_energy_cost)
from sbs_utils.procedural.media import media_read_relative_file
from sbs_utils.procedural.inventory import get_inventory_value
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.timers import is_timer_finished

#: What an unlisted hull weighs. A fighter is 1, so this is "about a corvette" - heavy
#: enough that an unknown hull is not free to drag, light enough not to pin a ship.
LM_TETHER_MASS_DEFAULT = 3.0

#: What a floating collectible weighs. A quarter of a fighter: light enough that reeling
#: one costs nothing worth measuring, and NOT zero, because grav_tether_mass reads
#: anything <= 0 as "unknown" and hands back its own default.
#:
#: A RULE and not a yaml entry, and that is the point: every pickup in the game comes from
#: the library's `item_spawn`, but its ART is whatever `type: item/...` label declared it
#: - a registry that is open by design, so a table of pickup arts would be permanently one
#: mission behind and would log a "no tether mass" warning for each new one.
#:
#: Two live bugs this fixes. A cruiser reeling a canister paid 0.35 of its throttle AND
#: turn, for picking up a crate. Worse, a tsn_fighter is mass 1 against the pickup's old
#: default of 3, which is over MASS_REVERSE_RATIO - so the beam FLIPPED and reeled the
#: fighter onto the canister, capped to impulse the whole way.
LM_TETHER_PICKUP_MASS = 0.25

#: How much a Heavy Tug Rig multiplies a ship's pull. Bought at a station, permanent.
#:
#: FOUR, so a rigged hull and a four-ship team read the same on every number the beam
#: computes - the same ratio, the same lag, the same strain word. NOT the same on
#: endurance, and that difference is the point rather than an oversight: the power bill is
#: split between the ships actually on the beam, so four hulls each pay a quarter while
#: one rigged hull pays all of it. The rig makes you pull harder; it does not give you a
#: bigger tank, and on a haul heavy enough to be power-limited four ships still win.
LM_TETHER_TUG_BONUS = 4.0

#: What a Tug Rig Mk I is worth while its window runs. Found, temporary, and weaker.
#:
#: 2.5 rather than the obvious 2.0, and the reason is arithmetic rather than taste. Tow
#: drag saturates at a ratio of DRAG_FLOOR/DRAG_AT_EQUAL_MASS = 2.14, so on the standard
#: haul - a mass-3 light cruiser dragging a mass-16 liner - a 2x rig only takes the ratio
#: from 5.33 to 2.67 and the drag penalty does not move at all; the crew pays for the item
#: and the ship feels identical. 2.5 lands at 2.13, a hair under the floor, so the drag
#: eases and the strain word drops from "heavy" to "light". It is still comfortably worse
#: than the Heavy rig, which reaches 1.33 and a drag of 0.47.
LM_TETHER_TUG_MK1_BONUS = 2.5

#: Throttle above which a target cannot be grabbed. 0.5 means a ship at more than half
#: impulse shrugs you off, so in combat you cripple engines FIRST and then tether -
#: which is what ties this to the rest of the Weapons console.
LM_TETHER_GRAB_SPEED = 0.5

#: How far a capital ship's tether can reach to open, and the distance past which a live
#: one snaps (1.5x, the library default).
#:
#: TWICE a fighter's 4000u nose cone, and about five times beam range - a tether is a
#: utility beam, so you can get hold of something well before you could shoot it. It is
#: also exactly a standard hole's gravity_radius * LM_HOLE_SAFE_MARGIN, i.e. the radius of
#: a wide slingshot arc, so "you can catch a gravity well from anywhere on or inside the
#: arc you would ride" needs no second number.
#:
#: Before this there was NO reach at all on the Weapons hold-click: a gunner could tow
#: something 30,000u off the tactical picture.
LM_TETHER_REACH = 8000

#: Energy per tick per unit of towed mass. The tether tick fires ~7.5 times a sim-second
#: in-engine, so towing a 12-mass freighter costs about 1.8 energy/second - a real bill on
#: a long haul, survivable on a short one. Shared across everyone on the beam, so calling
#: in a second tug halves what each of you pays rather than doubling the fleet's bill.
LM_TETHER_TOW_ENERGY = 0.02

# NOTE: the "a hit this big shakes the tether loose" threshold is NOT here. It is the
# only one of these numbers a .mast file reads, and a module-level constant is never a
# MAST global - only functions are exported - so naming it here read fine in Python and
# raised `NameError: LM_TETHER_BREAK_DAMAGE is not defined` in the //damage/object route
# the first time anyone shot a ship that was towing. It lives in __init__.mast as
# `default shared LM_TETHER_BREAK_DAMAGE`, which is also where a mission can retune it.

_LM_MASSES = {}
_LM_WARNED = set()


def lm_tether_load_masses():
    """Read tether_mass.yaml and install LM's mass table. Call at story TOP LEVEL."""
    global _LM_MASSES
    try:
        text = media_read_relative_file("tether_mass.yaml")
        data = load_yaml_string(text) or {}
        _LM_MASSES = {str(k): float(v) for k, v in (data.get("masses") or {}).items()}
    except Exception as e:
        log("tether masses not loaded: " + str(e), "grav_tether", "warning")
        _LM_MASSES = {}
    grav_tether_set_mass_fn(lm_tether_mass)
    grav_tether_set_pull_bonus_fn(lm_tether_pull_bonus)
    grav_tether_set_grab_speed_limit(LM_TETHER_GRAB_SPEED)
    grav_tether_set_range_limit(LM_TETHER_REACH)
    grav_tether_set_tow_energy_cost(LM_TETHER_TOW_ENERGY)
    return len(_LM_MASSES)


def lm_tether_mass(id_or_obj):
    """What this object weighs, by hull. Unlisted hulls warn ONCE and use the default.

    Warning once per hull rather than per call is the point: a silent fallback is how
    "everything weighs the same" hides, and a warning every tick is how a real one gets
    scrolled past.

    A PICKUP is answered before the table is consulted - see LM_TETHER_PICKUP_MASS.

    Keyed on the `item_key` inventory value rather than on the `item` role, though both
    are stamped by the same call. A role is a string any mission can hang on anything,
    and `item_spawn` puts the item KEY into the role string too - so an item someone names
    `hulk` would answer to a role test meant for salvage. `item_key` is set by
    `item_spawn` and by nothing else.

    It cannot collide with the salvage payout, which reads this same function:
    `lm_tether_salvage_value` only ever asks about objects carrying LM_SALVAGE_ROLES
    (derelict/wreck/hulk/salvage_hulk), and those are npc_spawned, so they carry no
    `item_key` and never reach this branch.
    """
    oid = to_id(id_or_obj)
    so = to_object(oid)
    if so is None:
        return LM_TETHER_MASS_DEFAULT
    if get_inventory_value(oid, "item_key", None) is not None:
        return LM_TETHER_PICKUP_MASS
    art = getattr(so, "art_id", None) or ""
    if art in _LM_MASSES:
        return _LM_MASSES[art]
    if art and art not in _LM_WARNED:
        _LM_WARNED.add(art)
        log(f"no tether mass for hull '{art}' - using {LM_TETHER_MASS_DEFAULT}; "
            f"add it to grav_tether/tether_mass.yaml", "grav_tether", "warning")
    return LM_TETHER_MASS_DEFAULT


def lm_tether_pull_bonus(id_or_obj):
    """How much this ship counts for when HAULING. Two tiers of tug rig, best one wins.

    4x with a Heavy Tug Rig fitted (bought, permanent), 2.5x while a Tug Rig Mk I is still
    running (found, expiring), 1.0 with neither.

    THEY STACK, and that is a fix rather than generosity. item_activate decrements a
    consumable BEFORE it runs the effect, so under a best-one-wins rule a crew that owns
    the permanent rig destroys any Mk I they activate for no benefit at all - and neither
    the GUI nor the server route can refuse the press, because by the time anything knows
    the effect is inert the item is already spent. Every scattered Mk I would be trash
    specifically for the crews most likely to want one. Each rig contributes what it is
    worth on its own, so both fitted reads 5.5.

    THE MK I'S WINDOW IS A TIMER, NOT A FLAG, and the timer IS the effect. Nothing in the
    library undoes a consumable whose effect is not a modifier, so an item that set a flag
    would be permanent by accident - which is exactly what prefab_item_secret_codecase
    does today. Reading the window instead means there is no state to clean up, nothing to
    leak past a ship's death, and nothing for a mission reload to leave behind.

    is_timer_finished answers True for a timer that was never set, so a ship that never
    fitted one falls straight through to 1.0. The guard fails closed.

    Separate from lm_tether_mass on purpose. Mass also decides whether a Grav Lock
    reverses onto you, what you cost somebody else to tow, and - through
    lm_tether_salvage_value - what your own wreck pays. A towing rig should change none
    of those; folding the bonus into mass would make better gear quietly raise the price
    of your own hulk, which is a bug nobody would trace back to the rig.
    """
    sid = to_id(id_or_obj)
    if sid is None:
        return 1.0
    bonus = 1.0
    if get_inventory_value(sid, "grav_tug_rig_fitted", 0):
        bonus += LM_TETHER_TUG_BONUS - 1.0
    if not is_timer_finished(sid, "tug_rig_mk1"):
        bonus += LM_TETHER_TUG_MK1_BONUS - 1.0
    return bonus


def lm_tether_mass_count():
    """How many hulls the table knows. For tests and diagnostics."""
    return len(_LM_MASSES)
