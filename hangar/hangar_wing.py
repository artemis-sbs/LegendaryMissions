"""A station's AI WING - the fighters it launches when a bridge orders it to.

The hangar's own craft cannot do this: they are player ships (player_spawn,
behav_playership), there for a pilot to climb into, and the engine only steers an NPC
brain's `target_pos` on a behav_npcship. So a wing is a separate thing - a COUNT of AI
fighters a station or carrier holds, spawned as NPC ships when it launches and removed
again when they come home. The hangar's player craft are never touched.

    ready     craft in the bay, fueled and armed (starts at the wing size)
    out       live fighters flying for this host
    refit     landed, being refueled and rearmed - ready again after HANGAR_WING_REFIT
    lost      none of those - a fighter destroyed out there simply never comes back

BINGO. A fighter launches with HANGAR_WING_ENDURANCE seconds of fuel. When it runs out,
the `hangar_wing_bingo` timer signal sends it home (hangar_wing.mast) whatever it was
doing, and a Reassign no longer picks it up. It refits on landing.

The comms menu MORPHS with the wing's state: `launch` while the bay has ready craft and
nothing is out, `wing_out` once anything is flying - Launch gives way to Reassign and
Recall.

Wing size: a mission's `hangar_wing_size` inventory override, else the HANGAR_WING_SIZE
setting for a station, else a carrier's `baycount` (capped by the same setting), else 0.

Every function is prefixed `hangar_wing_` - one flat MAST namespace.
"""
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_id, to_object, object_exists
from sbs_utils.procedural.roles import has_role, role
from sbs_utils.procedural.ship_data import get_ship_data_for
from sbs_utils.procedural.spawn import npc_spawn

#: Role every wing fighter carries.
HANGAR_WING_ROLE = "hangar_wing"

#: Wing size when neither the mission nor the setting says otherwise.
HANGAR_WING_DEFAULT_SIZE = 4

#: Hull when the host's side has no fighter of its own.
HANGAR_WING_FALLBACK_HULL = "tsn_fighter"

#: How close a returning fighter must be to land.
HANGAR_WING_DOCK_DISTANCE = 800

#: Seconds of fuel a fighter launches with (HANGAR_WING_ENDURANCE setting).
HANGAR_WING_DEFAULT_ENDURANCE = 180

#: Seconds a landed fighter spends refueling and rearming (HANGAR_WING_REFIT setting).
HANGAR_WING_DEFAULT_REFIT = 60

#: The timer, and the signal it emits, when a fighter hits bingo fuel.
HANGAR_WING_BINGO = "hangar_wing_bingo"

_READY = "hangar_wing_ready"
_SIZE = "hangar_wing_size"
_HOME = "hangar_wing_home"
_REFIT = "hangar_wing_refit"          # sim-second times at which each refit completes
_IS_BINGO = "hangar_wing_is_bingo"


def _hangar_wing_setting(key="HANGAR_WING_SIZE", default=HANGAR_WING_DEFAULT_SIZE):
    try:
        from sbs_utils.procedural.settings import settings_get_defaults
        v = settings_get_defaults().get(key, default)
        return max(0, int(v))
    except Exception:                                   # noqa: BLE001
        return default


def _hangar_wing_now():
    from sbs_utils.helpers import FrameContext
    return FrameContext.sim_seconds or 0


def hangar_wing_size(host):
    """How many AI fighters `host` holds when full."""
    hid = to_id(host)
    so = to_object(hid)
    if so is None:
        return 0
    override = get_inventory_value(hid, _SIZE, None)
    if override is not None:
        return max(0, int(override))
    cap = _hangar_wing_setting()
    if has_role(hid, "station"):
        return cap
    entry = get_ship_data_for(getattr(so, "_ship_data_key", None)) or {}
    bays = entry.get("baycount") or 0
    return min(int(bays), cap) if bays else 0


def hangar_wing_set_size(host, size):
    """Give a host a wing of `size` (0 removes it) and fill its bay."""
    hid = to_id(host)
    if hid is None:
        return 0
    set_inventory_value(hid, _SIZE, max(0, int(size)))
    set_inventory_value(hid, _READY, max(0, int(size)))
    set_inventory_value(hid, _REFIT, [])
    return int(size)


def hangar_wing_ready(host):
    """Fighters in the bay, fueled and armed. Starts full; a refit that has finished
    becomes ready here."""
    hid = to_id(host)
    if hid is None:
        return 0
    ready = get_inventory_value(hid, _READY, None)
    if ready is None:
        ready = hangar_wing_size(hid)
        set_inventory_value(hid, _READY, ready)
    refit = list(get_inventory_value(hid, _REFIT, None) or [])
    if refit:
        now = _hangar_wing_now()
        done = [t for t in refit if t <= now]
        if done:
            ready += len(done)
            set_inventory_value(hid, _READY, ready)
            set_inventory_value(hid, _REFIT, [t for t in refit if t > now])
    return ready


def hangar_wing_refitting(host):
    """Fighters landed and still refueling / rearming."""
    hid = to_id(host)
    if hid is None:
        return 0
    hangar_wing_ready(hid)                  # promote finished refits first
    return len(get_inventory_value(hid, _REFIT, None) or [])


def hangar_wing_refit_remaining(host):
    """Seconds until the next refit completes, or 0."""
    hid = to_id(host)
    if hid is None or not hangar_wing_refitting(hid):
        return 0
    return max(0, int(min(get_inventory_value(hid, _REFIT, [])) - _hangar_wing_now()))


def hangar_wing_out(host):
    """Ids of the live fighters flying for `host`."""
    hid = to_id(host)
    if hid is None:
        return []
    return sorted(f for f in role(HANGAR_WING_ROLE)
                  if object_exists(f) and get_inventory_value(f, _HOME, None) == hid)


def hangar_wing_is_bingo(fighter):
    """Has this fighter hit bingo fuel (and so is heading home, whatever it is told)?"""
    fid = to_id(fighter)
    return bool(fid) and bool(get_inventory_value(fid, _IS_BINGO, False))


def hangar_wing_bingo_mark(fighter):
    """Mark a fighter as out of fuel. hangar_wing.mast then sends it home."""
    fid = to_id(fighter)
    if fid:
        set_inventory_value(fid, _IS_BINGO, True)
    return fid


def hangar_wing_assigned(host):
    """The fighters out AND still able to fight - not on bingo. What a Reassign moves."""
    return [f for f in hangar_wing_out(host) if not hangar_wing_is_bingo(f)]


def hangar_wing_home(fighter):
    """The host a wing fighter belongs to, or None."""
    fid = to_id(fighter)
    return get_inventory_value(fid, _HOME, None) if fid else None


def hangar_wing_hull(host):
    """The fighter hull for `host`'s side, or the fallback."""
    from sbs_utils.procedural.ship_data import filter_ship_data_by_side
    so = to_object(host)
    side = getattr(so, "side", None) if so is not None else None
    try:
        keys = filter_ship_data_by_side(None, side, "fighter", ret_key_only=True) or []
    except Exception:                                   # noqa: BLE001
        keys = []
    # Prefer a real fighter over a bomber; either way the first of the side's own.
    fighters = [k for k in keys if "bomber" not in k]
    return (fighters or keys or [HANGAR_WING_FALLBACK_HULL])[0]


def hangar_wing_launch(host, count=None):
    """Launch up to `count` ready fighters (all of them by default), fueled for
    HANGAR_WING_ENDURANCE seconds. Returns their ids - the caller gives them their
    orders. [] when nothing is ready."""
    from sbs_utils.procedural.timers import set_timer
    hid = to_id(host)
    so = to_object(hid)
    if so is None:
        return []
    ready = hangar_wing_ready(hid)
    n = ready if count is None else min(int(count), ready)
    if n <= 0:
        return []
    side = getattr(so, "side", None) or "tsn"
    hull = hangar_wing_hull(hid)
    endurance = _hangar_wing_setting("HANGAR_WING_ENDURANCE", HANGAR_WING_DEFAULT_ENDURANCE)
    pos = so.pos
    ids = []
    for i in range(n):
        # Fanned out around the host so they do not spawn inside each other.
        off = (i - (n - 1) / 2.0) * 150
        name = f"{so.name} Wing {i + 1}"
        fid = to_id(npc_spawn(pos.x + off, pos.y, pos.z + 300, name,
                              f"{side},fighter,{HANGAR_WING_ROLE}", hull, "behav_npcship"))
        if fid is None:
            continue
        set_inventory_value(fid, _HOME, hid)
        # Fuel. The timer's signal is what brings it home - see hangar_wing.mast.
        set_timer(fid, HANGAR_WING_BINGO, seconds=endurance, signal=HANGAR_WING_BINGO)
        ids.append(fid)
    set_inventory_value(hid, _READY, ready - len(ids))
    return ids


def hangar_wing_reassign(host):
    """The fighters a Reassign sends at a new target: every one still out and fueled,
    plus whatever is ready in the bay, launched now. Returns their ids."""
    return hangar_wing_assigned(host) + hangar_wing_launch(host)


def hangar_wing_land(fighter):
    """Land a returning fighter if it is close enough to home: it leaves the map and goes
    into refit, ready again after HANGAR_WING_REFIT seconds. Returns True when it landed.
    A fighter whose home is gone stays out."""
    from sbs_utils.procedural.space_objects import delete_object
    import sbs
    fid = to_id(fighter)
    hid = hangar_wing_home(fid)
    if not fid or not hid or not object_exists(fid) or not object_exists(hid):
        return False
    if sbs.distance_id(fid, hid) > HANGAR_WING_DOCK_DISTANCE:
        return False
    delete_object(fid)
    refit = list(get_inventory_value(hid, _REFIT, None) or [])
    refit.append(_hangar_wing_now() + _hangar_wing_setting("HANGAR_WING_REFIT", HANGAR_WING_DEFAULT_REFIT))
    set_inventory_value(hid, _REFIT, refit)
    return True


def hangar_wing_caps(object_id):
    """The orders-capability provider - and what makes the menu morph:

        launch     craft ready in the bay and none out  -> Launch wing / to protect
        wing_out   any fighter out                      -> Reassign wing / Recall wing

    A host whose whole wing is refitting has neither, so it offers no wing order until a
    fighter is ready again.
    """
    if hangar_wing_out(object_id):
        return ["wing_out"]
    if hangar_wing_ready(object_id) > 0:
        return ["launch"]
    return []


try:
    from sbs_utils.procedural.orders import orders_caps_provider
    orders_caps_provider(hangar_wing_caps)
except ImportError:                                     # an sbslib without orders
    pass
