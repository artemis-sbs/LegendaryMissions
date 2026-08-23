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
                                              grav_tether_set_tow_energy_cost)
from sbs_utils.procedural.media import media_read_relative_file
from sbs_utils.procedural.query import to_id, to_object

#: What an unlisted hull weighs. A fighter is 1, so this is "about a corvette" - heavy
#: enough that an unknown hull is not free to drag, light enough not to pin a ship.
LM_TETHER_MASS_DEFAULT = 3.0

#: Throttle above which a target cannot be grabbed. 0.5 means a ship at more than half
#: impulse shrugs you off, so in combat you cripple engines FIRST and then tether -
#: which is what ties this to the rest of the Weapons console.
LM_TETHER_GRAB_SPEED = 0.5

#: Energy per tick per unit of towed mass. At ~10Hz, towing a 12-mass freighter costs
#: about 2.4 energy/second - a real bill on a long haul, survivable on a short one.
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
    grav_tether_set_grab_speed_limit(LM_TETHER_GRAB_SPEED)
    grav_tether_set_tow_energy_cost(LM_TETHER_TOW_ENERGY)
    return len(_LM_MASSES)


def lm_tether_mass(id_or_obj):
    """What this object weighs, by hull. Unlisted hulls warn ONCE and use the default.

    Warning once per hull rather than per call is the point: a silent fallback is how
    "everything weighs the same" hides, and a warning every tick is how a real one gets
    scrolled past.
    """
    so = to_object(to_id(id_or_obj))
    if so is None:
        return LM_TETHER_MASS_DEFAULT
    art = getattr(so, "art_id", None) or ""
    if art in _LM_MASSES:
        return _LM_MASSES[art]
    if art and art not in _LM_WARNED:
        _LM_WARNED.add(art)
        log(f"no tether mass for hull '{art}' - using {LM_TETHER_MASS_DEFAULT}; "
            f"add it to grav_tether/tether_mass.yaml", "grav_tether", "warning")
    return LM_TETHER_MASS_DEFAULT


def lm_tether_mass_count():
    """How many hulls the table knows. For tests and diagnostics."""
    return len(_LM_MASSES)
