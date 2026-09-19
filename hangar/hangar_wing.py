"""A station's AI WINGS - the fighters it launches when a bridge orders it to.

The hangar's own craft cannot do this: they are player ships (player_spawn,
behav_playership), there for a pilot to climb into, and the engine only steers an NPC
brain's `target_pos` on a behav_npcship. So a wing is a separate thing - a COUNT of AI
fighters a station or carrier holds, spawned as NPC ships when it launches and removed
again when they come home. The hangar's player craft are never touched.

A host has one or more WINGS, named by color - Red, Gold, Blue, Green, Silver, Black -
so they cannot be confused with the Alpha / Bravo science markers. Each wing is launched,
reassigned and recalled on its own, with its own fuel and refit:

    ready     craft in the bay, fueled and armed (starts at the wing size)
    out       live fighters flying for this wing
    refit     landed, being refueled and rearmed - ready again after HANGAR_WING_REFIT
    lost      none of those - a fighter destroyed out there simply never comes back

BINGO. A fighter launches with HANGAR_WING_ENDURANCE seconds of fuel. When it runs out,
the `hangar_wing_bingo` timer signal sends it home (hangar_wing.mast) whatever it was
doing, and a Reassign no longer picks it up. It refits on landing.

THE MENU is one entry per wing (sbs_utils orders_items / `instances:`): a wing with craft
ready and none out offers Launch; a wing with fighters out offers Reassign and Recall.

HOW MANY. Wings: a mission's `hangar_wing_set_size(host, size, count)`, else the
HANGAR_WING_COUNTS setting by hull key, else the table below, else 1. Fighters per wing:
the same override, else HANGAR_WING_SIZE for a station, else a carrier's `baycount`
(capped by HANGAR_WING_SIZE), else 0.

Every function is prefixed `hangar_wing_` - one flat MAST namespace.
"""
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_id, to_object, object_exists
from sbs_utils.procedural.roles import has_role, role
from sbs_utils.procedural.ship_data import get_ship_data_for
from sbs_utils.procedural.spawn import npc_spawn

#: Role every wing fighter carries.
HANGAR_WING_ROLE = "hangar_wing"

#: Fighters per wing when neither the mission nor the setting says otherwise.
HANGAR_WING_DEFAULT_SIZE = 4

#: Wings per hull when neither the mission nor HANGAR_WING_COUNTS says otherwise.
#: Anything not listed has one.
HANGAR_WING_DEFAULT_COUNTS = {"starbase_command": 2, "starbase_arvonian": 2}

#: Wing names, in order. A host with more wings than this reuses them numbered.
HANGAR_WING_NAMES = ("Red", "Gold", "Blue", "Green", "Silver", "Black")

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

_SIZE = "hangar_wing_size"
_COUNT = "hangar_wing_count"
_HOME = "hangar_wing_home"
_WING = "hangar_wing_key"             # which of its host's wings a fighter flies with
_IS_BINGO = "hangar_wing_is_bingo"


def _ready_key(wing):
    return f"hangar_wing_ready:{wing}"


def _refit_key(wing):
    return f"hangar_wing_refit:{wing}"   # sim-second times at which each refit completes


def _hangar_wing_settings():
    try:
        from sbs_utils.procedural.settings import settings_get_defaults
        return settings_get_defaults() or {}
    except Exception:                                   # noqa: BLE001
        return {}


def _hangar_wing_setting(key, default):
    try:
        return max(0, int(_hangar_wing_settings().get(key, default)))
    except (TypeError, ValueError):
        return default


def _hangar_wing_now():
    from sbs_utils.helpers import FrameContext
    return FrameContext.sim_seconds or 0


# --- how many ------------------------------------------------------------------------

def hangar_wing_size(host):
    """Fighters per wing when full."""
    hid = to_id(host)
    so = to_object(hid)
    if so is None:
        return 0
    override = get_inventory_value(hid, _SIZE, None)
    if override is not None:
        return max(0, int(override))
    cap = _hangar_wing_setting("HANGAR_WING_SIZE", HANGAR_WING_DEFAULT_SIZE)
    if has_role(hid, "station"):
        return cap
    entry = get_ship_data_for(getattr(so, "_ship_data_key", None)) or {}
    bays = entry.get("baycount") or 0
    return min(int(bays), cap) if bays else 0


def hangar_wing_count(host):
    """How many wings `host` has. 0 when it holds no fighters at all."""
    hid = to_id(host)
    so = to_object(hid)
    if so is None or hangar_wing_size(hid) <= 0:
        return 0
    override = get_inventory_value(hid, _COUNT, None)
    if override is not None:
        return max(0, int(override))
    key = getattr(so, "_ship_data_key", None)
    table = dict(HANGAR_WING_DEFAULT_COUNTS)
    custom = _hangar_wing_settings().get("HANGAR_WING_COUNTS", None)
    if isinstance(custom, dict):
        table.update(custom)
    try:
        return max(0, int(table.get(key, 1)))
    except (TypeError, ValueError):
        return 1


def hangar_wing_names(host):
    """The keys of `host`'s wings, in order: "red", "gold", ..."""
    out = []
    for i in range(hangar_wing_count(host)):
        base = HANGAR_WING_NAMES[i % len(HANGAR_WING_NAMES)]
        n = i // len(HANGAR_WING_NAMES)
        out.append(base.lower() if n == 0 else f"{base.lower()}{n + 1}")
    return out


def hangar_wing_display(wing):
    """"red" -> "Red wing", "red2" -> "Red 2 wing"."""
    wing = str(wing or "")
    name = wing.rstrip("0123456789")
    num = wing[len(name):]
    return f"{name.capitalize()}{' ' + num if num else ''} wing"


def hangar_wing_set_size(host, size, count=None):
    """Give a host `count` wings of `size` fighters (0 removes them) and fill every bay.
    `count` None keeps the host's current number of wings."""
    hid = to_id(host)
    if hid is None:
        return 0
    set_inventory_value(hid, _SIZE, max(0, int(size)))
    if count is not None:
        set_inventory_value(hid, _COUNT, max(0, int(count)))
    for wing in hangar_wing_names(hid):
        set_inventory_value(hid, _ready_key(wing), max(0, int(size)))
        set_inventory_value(hid, _refit_key(wing), [])
    return int(size)


# --- per-wing state ------------------------------------------------------------------

def _wings(host, wing):
    """The wing keys a call applies to: one, or all of them."""
    return [wing] if wing else hangar_wing_names(host)


def _ready_one(hid, wing):
    ready = get_inventory_value(hid, _ready_key(wing), None)
    if ready is None:
        ready = hangar_wing_size(hid)
        set_inventory_value(hid, _ready_key(wing), ready)
    refit = list(get_inventory_value(hid, _refit_key(wing), None) or [])
    if refit:
        now = _hangar_wing_now()
        done = [t for t in refit if t <= now]
        if done:
            ready += len(done)
            set_inventory_value(hid, _ready_key(wing), ready)
            set_inventory_value(hid, _refit_key(wing), [t for t in refit if t > now])
    return ready


def hangar_wing_ready(host, wing=None):
    """Fighters in the bay, fueled and armed - in one wing, or all of them. A bay starts
    full; a refit that has finished becomes ready here."""
    hid = to_id(host)
    if hid is None:
        return 0
    return sum(_ready_one(hid, w) for w in _wings(hid, wing))


def hangar_wing_refitting(host, wing=None):
    """Fighters landed and still refueling / rearming."""
    hid = to_id(host)
    if hid is None:
        return 0
    n = 0
    for w in _wings(hid, wing):
        _ready_one(hid, w)                  # promote finished refits first
        n += len(get_inventory_value(hid, _refit_key(w), None) or [])
    return n


def hangar_wing_refit_remaining(host, wing=None):
    """Seconds until the next refit completes, or 0."""
    hid = to_id(host)
    if hid is None or not hangar_wing_refitting(hid, wing):
        return 0
    times = [t for w in _wings(hid, wing) for t in (get_inventory_value(hid, _refit_key(w), None) or [])]
    return max(0, int(min(times) - _hangar_wing_now())) if times else 0


def hangar_wing_out(host, wing=None):
    """Ids of the live fighters flying for `host` - for one wing, or all of them."""
    hid = to_id(host)
    if hid is None:
        return []
    return sorted(f for f in role(HANGAR_WING_ROLE)
                  if object_exists(f) and get_inventory_value(f, _HOME, None) == hid
                  and (wing is None or get_inventory_value(f, _WING, None) == wing))


def hangar_wing_of(fighter):
    """Which wing a fighter flies with, or None."""
    fid = to_id(fighter)
    return get_inventory_value(fid, _WING, None) if fid else None


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


def hangar_wing_assigned(host, wing=None):
    """The fighters out AND still able to fight - not on bingo. What a Reassign moves."""
    return [f for f in hangar_wing_out(host, wing) if not hangar_wing_is_bingo(f)]


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


# --- launch, reassign, land ------------------------------------------------------------

def _launch_one(hid, so, wing, count):
    from sbs_utils.procedural.timers import set_timer
    ready = _ready_one(hid, wing)
    n = ready if count is None else min(int(count), ready)
    if n <= 0:
        return []
    side = getattr(so, "side", None) or "tsn"
    hull = hangar_wing_hull(hid)
    endurance = _hangar_wing_setting("HANGAR_WING_ENDURANCE", HANGAR_WING_DEFAULT_ENDURANCE)
    label = hangar_wing_display(wing).replace(" wing", "")
    pos = so.pos
    # Each wing launches from its own side of the host so two wings do not collide.
    lane = 300 + 250 * hangar_wing_names(hid).index(wing) if wing in hangar_wing_names(hid) else 300
    ids = []
    for i in range(n):
        off = (i - (n - 1) / 2.0) * 150
        fid = to_id(npc_spawn(pos.x + off, pos.y, pos.z + lane, f"{so.name} {label} {i + 1}",
                              f"{side},fighter,{HANGAR_WING_ROLE}", hull, "behav_npcship"))
        if fid is None:
            continue
        set_inventory_value(fid, _HOME, hid)
        set_inventory_value(fid, _WING, wing)
        # Fuel. The timer's signal is what brings it home - see hangar_wing.mast.
        set_timer(fid, HANGAR_WING_BINGO, seconds=endurance, signal=HANGAR_WING_BINGO)
        ids.append(fid)
    set_inventory_value(hid, _ready_key(wing), ready - len(ids))
    return ids


def hangar_wing_launch(host, count=None, wing=None):
    """Launch up to `count` ready fighters (all by default) from one wing, or from every
    wing. Each is fueled for HANGAR_WING_ENDURANCE seconds. Returns their ids - the caller
    gives them their orders."""
    hid = to_id(host)
    so = to_object(hid)
    if so is None:
        return []
    ids = []
    for w in _wings(hid, wing):
        left = None if count is None else count - len(ids)
        if left is not None and left <= 0:
            break
        ids += _launch_one(hid, so, w, left)
    return ids


def hangar_wing_reassign(host, wing=None):
    """The fighters a Reassign sends at a new target: every one of the wing still out and
    fueled, plus whatever of it is ready in the bay, launched now. Returns their ids."""
    return hangar_wing_assigned(host, wing) + hangar_wing_launch(host, wing=wing)


def hangar_wing_land(fighter):
    """Land a returning fighter if it is close enough to home: it leaves the map and goes
    into its wing's refit, ready again after HANGAR_WING_REFIT seconds. Returns True when
    it landed. A fighter whose home is gone stays out."""
    from sbs_utils.procedural.space_objects import delete_object
    import sbs
    fid = to_id(fighter)
    hid = hangar_wing_home(fid)
    wing = hangar_wing_of(fid)
    if not fid or not hid or not object_exists(fid) or not object_exists(hid):
        return False
    if sbs.distance_id(fid, hid) > HANGAR_WING_DOCK_DISTANCE:
        return False
    delete_object(fid)
    if wing:
        refit = list(get_inventory_value(hid, _refit_key(wing), None) or [])
        refit.append(_hangar_wing_now() + _hangar_wing_setting("HANGAR_WING_REFIT", HANGAR_WING_DEFAULT_REFIT))
        set_inventory_value(hid, _refit_key(wing), refit)
    return True


# --- what the order menu sees ----------------------------------------------------------

def _wing_can_launch(hid, wing):
    return _ready_one(hid, wing) > 0 and not hangar_wing_out(hid, wing)


def hangar_wing_instances(host, label=None):
    """The `instances:` provider for the wing orders: `[(wing, "Red wing")]` for every
    wing this order applies to right now. The label's `wing_state:` picks which:

        ready   craft ready in the bay and none out  (Launch)
        out     fighters out                         (Reassign, Recall)
    """
    hid = to_id(host)
    state = label.get_inventory_value("wing_state", "ready") if label is not None else "ready"
    out = []
    for wing in hangar_wing_names(hid):
        if state == "out":
            ok = bool(hangar_wing_out(hid, wing))
        else:
            ok = _wing_can_launch(hid, wing)
        if ok:
            out.append((wing, hangar_wing_display(wing)))
    return out


def hangar_wing_caps(object_id):
    """The orders-capability provider:

        launch     some wing has craft ready and none out
        wing_out   some wing has fighters out

    A host can have both - one wing on patrol, one in the bay. One whose every wing is
    refitting has neither, so it offers no wing order until a fighter is ready again.
    """
    caps = []
    wings = hangar_wing_names(object_id)
    if any(_wing_can_launch(object_id, w) for w in wings):
        caps.append("launch")
    if hangar_wing_out(object_id):
        caps.append("wing_out")
    return caps


try:
    from sbs_utils.procedural.orders import orders_caps_provider
    orders_caps_provider(hangar_wing_caps)
except ImportError:                                     # an sbslib without orders
    pass
