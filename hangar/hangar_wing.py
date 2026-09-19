"""A station's AI WINGS - the fighters it launches when a bridge orders it to, or when it
runs itself.

The hangar's own craft cannot do this: they are player ships (player_spawn,
behav_playership), there for a pilot to climb into, and the engine only steers an NPC
brain's `target_pos` on a behav_npcship. So a wing is a separate thing - a COUNT of AI
fighters a station or carrier holds, spawned as NPC ships when it launches and removed
again when they come home. The hangar's player craft are never touched.

BAYS decide everything. A host's bays are its interior GRID's `fighter` + `shuttle` slots
(the same data hangar.mast reads to stock a station's hangar), else its ship-data
`baycount`. Stock stations: command 8, industry 8, science 4, kralien 4; civil, skaraan and
torgoth none; the arvonian base 14 from baycount. Bays are split into wings of up to
HANGAR_WING_SIZE, the last wing taking the remainder - so a command starbase flies Red 4
and Gold 4, and a station with no bays has no wing at all.

A host's wings are named by color - Red, Gold, Blue, Green, Silver, Black - so they cannot
be confused with the Alpha / Bravo science markers. Each wing is launched, reassigned and
recalled on its own, with its own fuel and refit:

    ready     craft in the bay, fueled and armed (starts at the wing's size)
    out       live fighters flying for this wing
    refit     landed, being refueled and rearmed - ready again after HANGAR_WING_REFIT
    lost      none of those - a fighter destroyed out there simply never comes back

BINGO. A fighter launches with HANGAR_WING_ENDURANCE seconds of fuel. When it runs out,
the `hangar_wing_bingo` timer signal sends it home (hangar_wing.mast) whatever it was
doing, and a Reassign no longer picks it up. It refits on landing.

FIGHTERS are a `fighter` hull of the host hull's ORIGIN (Terran -> tsn_fighter, Arvonian
-> arvonian_fighter); an origin with none (Kralien, Skaraan, Torgoth) falls back to
tsn_fighter, said once per host.

AUTONOMY. A station whose side - and every side allied to it - has no crew runs its own
wings (hangar_wing_brain.mast, hangar_wing_think below); a crew can hand a station to it
("Act on your own"). See hangar_wing_is_autonomous for the whole rule.

Every function is prefixed `hangar_wing_` - one flat MAST namespace.
"""
import math

from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_id, to_object, object_exists
from sbs_utils.procedural.roles import has_role, role
from sbs_utils.procedural.ship_data import get_ship_data_for
from sbs_utils.procedural.spawn import npc_spawn

#: Role every wing fighter carries.
HANGAR_WING_ROLE = "hangar_wing"

#: Most fighters in one wing (HANGAR_WING_SIZE setting).
HANGAR_WING_DEFAULT_SIZE = 4

#: Wing names, in order. A host with more wings than this is clamped to this many.
HANGAR_WING_NAMES = ("Red", "Gold", "Blue", "Green", "Silver", "Black")

#: Hull when the host's origin has no fighter of its own.
HANGAR_WING_FALLBACK_HULL = "tsn_fighter"

#: How close a returning fighter must be to land.
HANGAR_WING_DOCK_DISTANCE = 800

#: Seconds of fuel a fighter launches with (HANGAR_WING_ENDURANCE setting).
HANGAR_WING_DEFAULT_ENDURANCE = 180

#: Seconds a landed fighter spends refueling and rearming (HANGAR_WING_REFIT setting).
HANGAR_WING_DEFAULT_REFIT = 60

#: The timer, and the signal it emits, when a fighter hits bingo fuel.
HANGAR_WING_BINGO = "hangar_wing_bingo"

#: Roles that force a station's autonomy on / off, whatever its side.
HANGAR_WING_AUTONOMOUS_ROLE = "autonomous"
HANGAR_WING_MANUAL_ROLE = "manual_wing"

#: Autonomous doctrine. The station counts as attacked for this long after a hit, a hostile
#: this close to an ally makes it worth covering, and the area must be clear this long
#: before the wings are called home.
HANGAR_WING_ATTACKED_SECONDS = 20
HANGAR_WING_COVER_DISTANCE = 3000
HANGAR_WING_CLEAR_SECONDS = 15

_SIZE = "hangar_wing_size"
_COUNT = "hangar_wing_count"
_BAYS = "hangar_wing_bays"
_HOME = "hangar_wing_home"
_WING = "hangar_wing_key"             # which of its host's wings a fighter flies with
_IS_BINGO = "hangar_wing_is_bingo"
_DELEGATED = "hangar_wing_delegated"
_ATTACKED_AT = "hangar_wing_attacked_at"
_ATTACKER = "hangar_wing_attacker"
_CLEAR_SINCE = "hangar_wing_clear_since"
_NEXT_THINK = "hangar_wing_next_think"
_HULL_WARNED = "hangar_wing_hull_warned"


def _ready_key(wing):
    return f"hangar_wing_ready:{wing}"


def _refit_key(wing):
    return f"hangar_wing_refit:{wing}"   # sim-second times at which each refit completes


def _target_key(wing):
    return f"hangar_wing_target:{wing}"  # what the autonomous brain last sent this wing at


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


def _hull_key(so):
    return getattr(so, "_ship_data_key", None) or getattr(so, "art_id", None)


# --- how many ------------------------------------------------------------------------

def hangar_wing_bays(host):
    """Bays: the hull's grid `fighter` + `shuttle` slots, else ship-data `baycount`, else
    0. Read once per host and kept - the grid lookup is not free."""
    hid = to_id(host)
    so = to_object(hid)
    if so is None:
        return 0
    cached = get_inventory_value(hid, _BAYS, None)
    if cached is not None:
        return cached
    key = _hull_key(so)
    bays = 0
    # The GRID only for a station. Player-class hulls carry hangar bays in their grid too
    # (for the crew's own craft), so reading it for every ship would put a wing on any NPC
    # cruiser built on one. A ship's wing comes from its ship-data baycount - a carrier.
    if has_role(hid, "station"):
        try:
            from sbs_utils.procedural.internal_damage import grid_count_grid_data
            bays = (grid_count_grid_data(key, "fighter", 0) or 0) + (grid_count_grid_data(key, "shuttle", 0) or 0)
        except Exception:                               # noqa: BLE001
            bays = 0
    if not bays:
        entry = get_ship_data_for(key) or {}
        bays = int(entry.get("baycount") or 0)
    set_inventory_value(hid, _BAYS, bays)
    return bays


def hangar_wing_count(host):
    """How many wings `host` has: a per-host override, else HANGAR_WING_COUNTS by hull,
    else the bays split into wings of HANGAR_WING_SIZE. 0 with no bays."""
    hid = to_id(host)
    so = to_object(hid)
    if so is None:
        return 0
    if get_inventory_value(hid, _SIZE, None) == 0:
        return 0                                        # size 0 removes the wings, whatever the count
    override = get_inventory_value(hid, _COUNT, None)
    if override is not None:
        return max(0, min(int(override), len(HANGAR_WING_NAMES)))
    custom = _hangar_wing_settings().get("HANGAR_WING_COUNTS", None)
    if isinstance(custom, dict) and _hull_key(so) in custom:
        try:
            return max(0, min(int(custom[_hull_key(so)]), len(HANGAR_WING_NAMES)))
        except (TypeError, ValueError):
            pass
    bays = hangar_wing_bays(hid)
    per = _hangar_wing_setting("HANGAR_WING_SIZE", HANGAR_WING_DEFAULT_SIZE)
    if bays <= 0 or per <= 0:
        return 0
    return min(math.ceil(bays / per), len(HANGAR_WING_NAMES))


def hangar_wing_names(host):
    """The keys of `host`'s wings, in order: "red", "gold", ..."""
    return [HANGAR_WING_NAMES[i].lower() for i in range(hangar_wing_count(host))]


def hangar_wing_size(host, wing=None):
    """Fighters in a wing when full. A per-host override sizes every wing; otherwise each
    wing is HANGAR_WING_SIZE and the LAST one takes what is left of the bays. No wing
    named: the first wing's size."""
    hid = to_id(host)
    if to_object(hid) is None:
        return 0
    override = get_inventory_value(hid, _SIZE, None)
    if override is not None:
        return max(0, int(override))
    names = hangar_wing_names(hid)
    if not names:
        return 0
    per = _hangar_wing_setting("HANGAR_WING_SIZE", HANGAR_WING_DEFAULT_SIZE)
    idx = names.index(wing) if wing in names else 0
    if idx < len(names) - 1:
        return per
    left = hangar_wing_bays(hid) - per * (len(names) - 1)
    # A count forced above what the bays hold still gets full wings.
    return max(1, min(per, left)) if left > 0 else per


def hangar_wing_display(wing):
    """"red" -> "Red wing"."""
    return f"{str(wing or '').capitalize()} wing"


def hangar_wing_set_size(host, size, count=None):
    """Give a host `count` wings of `size` fighters (size 0 removes them) and fill every
    bay. `count` None keeps the host's current number of wings."""
    hid = to_id(host)
    if hid is None:
        return 0
    if count is not None:
        set_inventory_value(hid, _COUNT, max(0, int(count)))
    set_inventory_value(hid, _SIZE, max(0, int(size)))
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
        ready = hangar_wing_size(hid, wing)
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


def hangar_wing_lost(host, wing=None):
    """Fighters destroyed for good: the wing's full size less what is ready, refitting and
    out. Losses are permanent - nothing rebuilds a fighter - so this only ever grows."""
    hid = to_id(host)
    if hid is None:
        return 0
    lost = 0
    for w in _wings(hid, wing):
        have = _ready_one(hid, w) + len(get_inventory_value(hid, _refit_key(w), None) or []) \
            + len(hangar_wing_out(hid, w))
        lost += max(0, hangar_wing_size(hid, w) - have)
    return lost


def hangar_wing_scan_text(host, exact=True):
    """What a science scan of the host's hangar shows - one line per wing. Empty when it
    has no wings. ASCII, and never a brace (MAST f-string formats the assignment).

    `exact` - your own or an allied base - gives the counts. An ENEMY base is an estimate:
    how strong each wing is and what it is doing, never the exact refit state, so a scan
    tells a crew a base is weakened without timing its next launch for them.
    """
    hid = to_id(host)
    lines = []
    for w in hangar_wing_names(hid):
        size = hangar_wing_size(hid, w)
        ready, refit = _ready_one(hid, w), hangar_wing_refitting(hid, w)
        out, lost = len(hangar_wing_out(hid, w)), hangar_wing_lost(hid, w)
        name = hangar_wing_display(w)
        if size and lost >= size:
            lines.append(f"{name}: destroyed." if not exact
                         else f"{name}: lost - all {size} fighters destroyed.")
        elif exact:
            lines.append(f"{name}: {ready} ready, {out} out, {refit} refitting, {lost} lost.")
        else:
            if lost == 0:
                strength = "full strength"
            elif lost * 2 < size:
                strength = "under strength"
            else:
                strength = "badly depleted"
            if out and ready:
                state = "partly airborne"
            elif out:
                state = "airborne"
            elif refit and not ready:
                state = "rearming"
            else:
                state = "in the bay"
            lines.append(f"{name}: {strength}, {state}.")
    return "\n".join(lines)


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
    """The fighter hull for `host`: a `fighter` hull of the same ORIGIN as the host's hull
    (a fighter before a bomber), else the fallback - said once per host."""
    from sbs_utils.procedural.ship_data import get_ship_data
    so = to_object(host)
    if so is None:
        return HANGAR_WING_FALLBACK_HULL
    origin = str((get_ship_data_for(_hull_key(so)) or {}).get("origin", "") or "").lower()
    fighters, bombers = [], []
    for entry in (get_ship_data() or {}).get("#ship-list", []) or []:
        roles = [r.strip() for r in str(entry.get("roles", "")).split(",")]
        if "fighter" not in roles:
            continue
        if str(entry.get("origin", "") or "").lower() != origin:
            continue
        (bombers if "bomber" in roles else fighters).append(entry.get("key"))
    found = [k for k in fighters + bombers if k]
    if found:
        return found[0]
    if origin and not get_inventory_value(so.id, _HULL_WARNED, False):
        set_inventory_value(so.id, _HULL_WARNED, True)
        from sbs_utils.procedural.execution import log
        log(f"hangar wing: no fighter hull of origin '{origin}' for {so.name} - "
            f"launching {HANGAR_WING_FALLBACK_HULL}", "hangar", "warning")
    return HANGAR_WING_FALLBACK_HULL


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
    label = wing.capitalize()
    names = hangar_wing_names(hid)
    pos = so.pos
    # Each wing launches from its own lane so two wings do not spawn inside each other.
    lane = 300 + 250 * (names.index(wing) if wing in names else 0)
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


# --- autonomy ------------------------------------------------------------------------

def _same_or_allied(a, b):
    from sbs_utils.procedural.sides import side_are_allies, to_side_id
    try:
        sa = to_side_id(a, warn=False)
        if sa is not None and sa == to_side_id(b, warn=False):
            return True
        return bool(side_are_allies(a, b))
    except Exception:                                   # noqa: BLE001
        return False


def hangar_wing_side_is_crewed(host):
    """Is there a crew - a player ship or an admiral - on the host's side or an allied
    side? Hangar craft are not counted: they drop `__player__` when parked."""
    hid = to_id(host)
    for crew in role("__player__") | role("admiral"):
        if crew != hid and object_exists(crew) and _same_or_allied(hid, crew):
            return True
    return False


def hangar_wing_delegate(host, on=True):
    """A crew hands the station to its own AI (on) or takes it back (off)."""
    hid = to_id(host)
    if hid:
        set_inventory_value(hid, _DELEGATED, bool(on))
    return bool(on)


def hangar_wing_is_delegated(host):
    hid = to_id(host)
    return bool(hid) and bool(get_inventory_value(hid, _DELEGATED, False))


def hangar_wing_is_autonomous(host):
    """Does this host run its own wings? In order:

        no wings                        no
        role `manual_wing`              no
        role `autonomous`               yes
        a crew delegated it             yes
        HANGAR_WING_AUTONOMOUS false    no
        otherwise                       yes when no crew is on its side or an allied one
    """
    hid = to_id(host)
    if hid is None or not hangar_wing_names(hid):
        return False
    if has_role(hid, HANGAR_WING_MANUAL_ROLE):
        return False
    if has_role(hid, HANGAR_WING_AUTONOMOUS_ROLE) or hangar_wing_is_delegated(hid):
        return True
    setting = _hangar_wing_settings().get("HANGAR_WING_AUTONOMOUS", True)
    if isinstance(setting, str):
        setting = setting.strip().lower() in ("true", "yes", "on", "1")
    if not setting:
        return False
    return not hangar_wing_side_is_crewed(hid)


def hangar_wing_note_attacked(host, attacker=None):
    """Record that the station was hit (a //damage/object route calls this)."""
    hid = to_id(host)
    if hid:
        set_inventory_value(hid, _ATTACKED_AT, _hangar_wing_now())
        set_inventory_value(hid, _ATTACKER, to_id(attacker) or 0)


def _hangar_wing_difficulty():
    try:
        from sbs_utils.procedural.execution import get_shared_variable
        return max(1, min(11, int(get_shared_variable("DIFFICULTY", 5) or 5)))
    except Exception:                                   # noqa: BLE001
        return 5


def hangar_wing_reaction(host=None):
    """Seconds between the station's decisions: faster at higher DIFFICULTY."""
    fixed = _hangar_wing_settings().get("HANGAR_WING_REACTION", None)
    if fixed is not None:
        return max(1, int(fixed))
    return max(3, 14 - _hangar_wing_difficulty())


def hangar_wing_radius(host=None):
    """How far out the station reacts to a hostile: wider at higher DIFFICULTY."""
    fixed = _hangar_wing_settings().get("HANGAR_WING_RADIUS", None)
    if fixed is not None:
        return max(500, int(fixed))
    return 5000 + 500 * _hangar_wing_difficulty()


def _hangar_wing_hostiles(hid, radius):
    """Enemy ships, fighters and player ships within `radius`, nearest first."""
    from sbs_utils.procedural.space_objects import broad_test_around
    from sbs_utils.procedural.sides import side_are_enemies
    from sbs_utils.procedural.roles import any_role
    import sbs
    near = broad_test_around(hid, radius * 2, radius * 2, 0xf0) & any_role("ship,fighter,__player__")
    out = []
    for oid in near:
        if oid == hid or not object_exists(oid):
            continue
        if not side_are_enemies(hid, oid):
            continue
        d = sbs.distance_id(hid, oid)
        if d <= radius:
            out.append((d, oid))
    return [oid for _, oid in sorted(out)]


def _hangar_wing_ally_under_threat(hid, radius, hostiles):
    """An allied NPC (not the host, not a wing fighter) within `radius` with a hostile
    close to it - the ship most worth covering, or None."""
    import sbs
    best, best_d = None, None
    for oid in role("__npc__"):
        if oid == hid or has_role(oid, HANGAR_WING_ROLE) or not object_exists(oid):
            continue
        if not _same_or_allied(hid, oid) or sbs.distance_id(hid, oid) > radius:
            continue
        for h in hostiles:
            d = sbs.distance_id(oid, h)
            if d <= HANGAR_WING_COVER_DISTANCE and (best_d is None or d < best_d):
                best, best_d = oid, d
    return best


def hangar_wing_think(host):
    """One autonomous decision pass - the policy, in one place. Returns the actions for
    hangar_wing_brain.mast to carry out with the SAME objective labels a crew's orders use:

        ("attack",   wing, target)   launch the wing at a hostile
        ("protect",  wing, ally)     launch the wing to escort an ally under threat
        ("reassign", wing, target)   the wing's target is gone: onto the next hostile
        ("recall",   wing, None)     all clear: bring it home

    Doctrine "defend + reserve": with two or more wings the LAST is a reserve, launched
    only while the station itself is under attack. Paced by hangar_wing_reaction(); a call
    before the next decision is due returns []. Also sets the station's turret mounts to
    weapons free while hostiles are in range, hold fire when clear.
    """
    from sbs_utils.procedural.orders import orders_stance_set, orders_mounted_turrets
    hid = to_id(host)
    if hid is None or not object_exists(hid):
        return []
    now = _hangar_wing_now()
    if now < (get_inventory_value(hid, _NEXT_THINK, 0) or 0):
        return []
    set_inventory_value(hid, _NEXT_THINK, now + hangar_wing_reaction(hid))

    names = hangar_wing_names(hid)
    if not names:
        return []
    radius = hangar_wing_radius(hid)
    hostiles = _hangar_wing_hostiles(hid, radius)
    reserve = names[-1] if len(names) >= 2 else None
    attacked_at = get_inventory_value(hid, _ATTACKED_AT, None)
    attacked = attacked_at is not None and now - attacked_at <= HANGAR_WING_ATTACKED_SECONDS
    attacker = get_inventory_value(hid, _ATTACKER, 0)
    if not (attacker and object_exists(attacker)):
        attacker = None
    has_mounts = bool(orders_mounted_turrets(hid))

    actions = []
    if not hostiles:
        since = get_inventory_value(hid, _CLEAR_SINCE, None)
        if since is None:
            set_inventory_value(hid, _CLEAR_SINCE, now)
        elif now - since >= HANGAR_WING_CLEAR_SECONDS:
            for wing in names:
                if hangar_wing_assigned(hid, wing):
                    actions.append(("recall", wing, None))
                    set_inventory_value(hid, _target_key(wing), 0)
        if has_mounts:
            orders_stance_set(hid, "hold")
        return actions

    set_inventory_value(hid, _CLEAR_SINCE, None)
    if has_mounts:
        orders_stance_set(hid, "free")
    nearest = hostiles[0]
    ally = _hangar_wing_ally_under_threat(hid, radius, hostiles)
    for wing in names:
        if hangar_wing_assigned(hid, wing):
            # Out and fueled: keep it on a live target.
            target = get_inventory_value(hid, _target_key(wing), 0)
            if not (target and object_exists(target)):
                actions.append(("reassign", wing, nearest))
                set_inventory_value(hid, _target_key(wing), nearest)
            continue
        if not (_ready_one(hid, wing) > 0 and not hangar_wing_out(hid, wing)):
            continue
        if wing == reserve and not attacked:
            continue                                    # the reserve stays home
        if wing == reserve:
            target = attacker or nearest
            actions.append(("attack", wing, target))
        elif ally is not None:
            actions.append(("protect", wing, ally))
            target = ally
            ally = None                                 # one wing covers it
        else:
            target = nearest
            actions.append(("attack", wing, target))
        set_inventory_value(hid, _target_key(wing), target)
    return actions


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
        # The counts ride in the entry's text, so a crew sees a wing wear down:
        # "Launch Red wing (3/4)", "Recall Red wing (2 out)". Losses are permanent.
        if state == "out":
            flying = len(hangar_wing_out(hid, wing))
            if flying:
                out.append((wing, f"{hangar_wing_display(wing)} ({flying} out)"))
        elif _wing_can_launch(hid, wing):
            out.append((wing, f"{hangar_wing_display(wing)} "
                              f"({_ready_one(hid, wing)}/{hangar_wing_size(hid, wing)})"))
    return out


def hangar_wing_caps(object_id):
    """The orders-capability provider:

        launch           some wing has craft ready and none out
        wing_out         some wing has fighters out
        wing_delegable   it has wings and is waiting for a crew's orders
        wing_delegated   a crew handed it to its own AI

    A host can have both launch and wing_out - one wing on patrol, one in the bay. One whose
    every wing is refitting has neither, so it offers no wing order until one is ready.
    """
    wings = hangar_wing_names(object_id)
    if not wings:
        return []
    caps = []
    if any(_wing_can_launch(object_id, w) for w in wings):
        caps.append("launch")
    if hangar_wing_out(object_id):
        caps.append("wing_out")
    if hangar_wing_is_delegated(object_id):
        caps.append("wing_delegated")
    elif not hangar_wing_is_autonomous(object_id):
        caps.append("wing_delegable")
    return caps


try:
    from sbs_utils.procedural.orders import orders_caps_provider
    orders_caps_provider(hangar_wing_caps)
except ImportError:                                     # an sbslib without orders
    pass
