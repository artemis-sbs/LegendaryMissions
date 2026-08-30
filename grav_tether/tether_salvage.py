"""Tow a hulk home and it becomes salvage.

Phase 2 of GRAV_TETHER_PLAN.md - the payoff that makes towing worth doing. A derelict
is worth nothing where it lies; drag it to a friendly station and it is worth materials.

VALUE COMES FROM MASS, which is why this waits on the constraints layer: the same number
that decides how much the haul costs you decides what it pays. A heavy freighter is a
slow, vulnerable trip AND the big payout, so the risk and the reward are the same fact
rather than two dials to balance against each other.

Salvage lands in the plain `salvage` inventory key - the one item pickups credit and the
Fabricator spends - so a towed hulk, a wreck pickup and a station purchase all end up in
one place and need no reconciliation.

Prefixed `lm_tether_`, not `grav_tether_`, so nothing here shadows the library primitive.
"""

from sbs_utils.procedural.execution import log
from sbs_utils.procedural.grav_tether import (grav_tether_involves, grav_tether_mass,
                                              grav_tether_release_any,
                                              grav_tether_sources_of)
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.roles import any_role, has_any_role, role
from sbs_utils.procedural.sides import side_are_friendly
from sbs_utils.procedural.signal import signal_emit
from sbs_utils.procedural.space_objects import closest, delete_object
from sbs_utils.tickdispatcher import TickDispatcher

#: Roles that make an object worth towing home. A mission marks its own wrecks with any
#: of these; nothing here has to know what the mission called them.
LM_SALVAGE_ROLES = "derelict,wreck,hulk,salvage_hulk"

#: What a capital ship's Weapons hold-click may get hold of. An ALLOWLIST, and that is
#: the point: the menu used to choose its mode by a BLACKLIST - "anything that is not a
#: pickup, a station, a rock or an NPC gets a rigid Grav Lock" - which handed a gunner a
#: rigid lock on every nebula, mine, marker, GM camera rig, and on every BLACK HOLE. A
#: lock on a hole makes the hole the LOAD: it reels onto the hull, the library caps the
#: ship to impulse so it cannot warp away, and the lethal-proximity watch in
#: collisions/collision.mast explodes anything within 500u. A new terrain type now has
#: to be added here deliberately instead of falling into a rigid grab by default.
#:
#: It lives HERE, beside LM_SALVAGE_ROLES, because towing a hulk home is what the list is
#: for and an addon .py cannot import a sibling addon .py at runtime - so the salvage
#: roles are spelled once, in the module that owns them.
LM_TETHER_HAULABLE = "station,asteroid,__npc__," + LM_SALVAGE_ROLES


def lm_tether_haulable(target):
    """Whether a capital ship may tow or lock this object."""
    tid = to_id(target)
    return tid is not None and has_any_role(tid, LM_TETHER_HAULABLE)

#: Salvage units per unit of hull mass. A 12-mass freighter is worth ~18 - a real haul
#: against the 3-6 a wreck pickup drops.
LM_SALVAGE_PER_MASS = 1.5

#: How close to the station counts as delivered. Generous, because the tow is the job -
#: making a crew thread a hulk through a docking port is a different game.
LM_SALVAGE_DELIVER_RANGE = 1200

_LM_SALVAGE_TICK = [None]


def lm_tether_salvage_hulks():
    """Every object currently worth towing home."""
    return any_role(LM_SALVAGE_ROLES)


def lm_tether_salvage_value(hulk):
    """What this hulk pays, from its mass. Always at least 1 - a hulk is never worthless."""
    hid = to_id(hulk)
    if hid is None:
        return 0
    return max(1, int(grav_tether_mass(hid) * LM_SALVAGE_PER_MASS + 0.5))


def lm_tether_salvage_award(ship, units):
    """Add salvage to a ship's hold, under the key the Fabricator already spends."""
    sid = to_id(ship)
    if sid is None or units <= 0:
        return 0
    have = get_inventory_value(sid, "salvage", 0) or 0
    set_inventory_value(sid, "salvage", have + int(units))
    return have + int(units)


def lm_tether_salvage_station_for(hulk, hauler=0):
    """The nearest station in delivery range that will BUY this hulk, or None.

    Friendliness is judged against the HAULER, not the hulk. A derelict is civilian
    scrap - its own diplomacy is meaningless, and testing it meant no station was ever
    friendly to anything, so nothing was ever delivered. The question the mechanic
    actually asks is "will this dock pay ME".

    max_dist is passed at 2x and the real distance checked after, because `closest`
    narrows with a box of WIDTH max_dist - asking for the range you want gets half it.
    """
    hid, sid = to_id(hulk), to_id(hauler)
    if hid is None:
        return None
    found = closest(hid, set(role("station")), LM_SALVAGE_DELIVER_RANGE * 2)
    if found is None or found.distance > LM_SALVAGE_DELIVER_RANGE:
        return None
    if sid and not side_are_friendly(sid, found.id):
        return None
    return found.id


def lm_tether_salvage_deliver(hulk, station, ship=0):
    """Cash in a hulk at a station: award the tower, consume the hulk, announce it."""
    hid, stid, sid = to_id(hulk), to_id(station), to_id(ship)
    if hid is None:
        return 0
    units = lm_tether_salvage_value(hid)
    if sid:
        lm_tether_salvage_award(sid, units)
    grav_tether_release_any(hid)
    # Deferred delete: freeing the hull synchronously while a tether tick may still be
    # holding its id is the use-after-free this codebase has been bitten by before.
    delete_object(hid)
    # Credit any `Done when: tow <role>` quest the hauler is running. Declarative, so a
    # rescue or an escort is authored in AMD rather than each mission inventing its own
    # signal name for "I got it home".
    if sid:
        try:
            from sbs_utils.procedural.quest_driver import quest_on_tow
            quest_on_tow(sid, hid)
        except Exception:
            pass
    signal_emit("lm_tether_salvage_delivered",
                {"HULK_ID": hid, "STATION_ID": stid, "SHIP_ID": sid, "UNITS": units})
    log(f"salvage delivered: {units} units", "grav_tether")
    return units


def lm_tether_salvage_tick(t=None):
    """Watch tethered hulks for arrival at a friendly station.

    Only TETHERED hulks: a wreck that happens to drift near a station has not been
    salvaged by anyone, and paying for that would make the mechanic a lottery.
    """
    for hid in list(lm_tether_salvage_hulks()):
        if not grav_tether_involves(hid):
            continue
        haulers = grav_tether_sources_of(hid)
        hauler = haulers[0] if haulers else 0
        station = lm_tether_salvage_station_for(hid, hauler)
        if station is None:
            continue
        lm_tether_salvage_deliver(hid, station, hauler)


def lm_tether_salvage_start():
    """Begin watching. Call at story TOP LEVEL; idempotent."""
    if _LM_SALVAGE_TICK[0] is None:
        _LM_SALVAGE_TICK[0] = TickDispatcher.do_interval(lm_tether_salvage_tick, 1)
    return True


def lm_tether_salvage_stop():
    """Stop watching (tests, mission reset)."""
    t = _LM_SALVAGE_TICK[0]
    if t is not None:
        try:
            t.stop()
        except Exception:
            pass
    _LM_SALVAGE_TICK[0] = None
