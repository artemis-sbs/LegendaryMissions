"""Grav-tether phase 5: the things the tether makes possible once it exists.

Black-hole swing, enemy tethers and the admiral's tug. Each is small on its own - the
primitive and the constraints layer already do the work - which is the point of having
built those first.

Prefixed `lm_tether_`, never `grav_tether_`, so nothing here shadows the library.
"""

import math

from sbs_utils.tickdispatcher import TickDispatcher
from sbs_utils.procedural.execution import log
from sbs_utils.procedural.internal_damage import grid_damage_system
from sbs_utils.procedural.orbit import (orbit_capture, orbit_is, orbit_release,
                                        orbit_swept_of)
from sbs_utils.procedural.particles import particle_charge_start, particle_charge_stop
from sbs_utils.procedural.grav_tether import (grav_tether_involves, grav_tether_lock,
                                              grav_tether_mass, grav_tether_release_any,
                                              grav_tether_sources_of, grav_tether_tow)
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import object_exists, to_id, to_object
from sbs_utils.procedural.roles import has_any_role, role
from sbs_utils.procedural.signal import signal_emit
from sbs_utils.procedural.space_objects import closest, closest_in_front
from sbs_utils.procedural.timers import is_timer_finished, set_timer

# ---------------------------------------------------------------------------------
# Black-hole swing
# ---------------------------------------------------------------------------------

#: How far outside a hole's gravity radius a swing rope must sit. A slingshot round a
#: black hole should be a nerve test, not a suicide: inside the gravity radius the hole's
#: own pull and the lethal-proximity ticker take over and the tether is irrelevant.
LM_HOLE_SAFE_MARGIN = 1.6

#: Fallback gravity radius when a hole does not report one (terrain_spawn_black_hole's
#: own default).
LM_HOLE_DEFAULT_GRAVITY = 1500


def lm_tether_hole_gravity(hole):
    """A hole's gravity radius, or the spawner's default."""
    hid = to_id(hole)
    so = to_object(hid) if hid else None
    if so is None:
        return LM_HOLE_DEFAULT_GRAVITY
    try:
        r = so.data_set.get("gravity_radius", 0)
    except Exception:
        r = None
    return float(r) if r else LM_HOLE_DEFAULT_GRAVITY


def lm_tether_hole_safe_rope(hole, wanted=0):
    """The shortest rope that keeps a swing clear of a hole's gravity well.

    Returns whichever is LONGER: what the pilot asked for, or the safe minimum. The
    tether should never be the thing that drops someone into a black hole - if a pilot
    wants to fly closer they can do it without a rope.
    """
    return max(float(wanted or 0), lm_tether_hole_gravity(hole) * LM_HOLE_SAFE_MARGIN)


#: How fast the hole throws you, in units/sec.
#:
#: A player hull's own ceiling is warp 5 - the engine bar stops there (helm.THROTTLE_MAX)
#: and that is 180 + 4*450 = 1980 u/s. So this is about TWICE anything a drive can do,
#: which is the whole reason to use a gravity well instead of flying: the wide arc is
#: 25,000u, six seconds this way and nearly thirteen at warp 5, burning warp energy all
#: the way.
LM_HOLE_SLING_SPEED = 4000.0

#: How far round the hole a slingshot carries you. Half a turn - in one side and out the
#: far side, which is the thing that was asked for.
LM_HOLE_SLING_ARC = math.pi

#: A close pass, as a fraction of the hole's gravity radius. INSIDE the well (a standard
#: LM hole pulls from 5000 at strength 4), so the engine's own gravity fights the carrier
#: the whole way - and still six times the 500u radius at which the lethal watch explodes
#: you, so the maneuver itself never drops anyone in.
LM_HOLE_CLOSE_MARGIN = 0.6

#: Before a ship can sling again. Every other LM ability pays in time rather than power,
#: and this one is deliberately free of any energy cost.
LM_HOLE_SLING_COOLDOWN = 60

#: How often the arc is checked for completion. The ENGINE flies the ship between our
#: passes (see sbs_utils.procedural.orbit); this only decides when to let go.
LM_HOLE_SLING_TICK = 0.1

_LM_SLING_CLOSE = "sling:close"
_lm_sling_task = None


def lm_tether_hole_close_rope(hole):
    """The radius of a CLOSE pass - inside the well, and much faster for it."""
    return lm_tether_hole_gravity(hole) * LM_HOLE_CLOSE_MARGIN


def lm_tether_sling_ready(ship):
    """Whether this ship's slingshot has recharged. True if it has never used one."""
    sid = to_id(ship)
    return sid is not None and is_timer_finished(sid, "lm_hole_sling")


def lm_tether_sling_is(ship):
    """Whether this ship is mid-slingshot right now."""
    return orbit_is(to_id(ship))


def lm_tether_slingshot_hole(ship, hole, radius=0):
    """Throw `ship` half way round `hole` and let go on the far side.

    The hole does not tow you and you do not tow it. An invisible carrier flies the arc
    and the ENGINE holds the ship welded into its frame every frame, so the curve is the
    engine's own motion rather than something this script re-points ten times a second.
    That is sbs_utils.procedural.orbit, which also takes the helm for the duration and
    hands it back - and which charges nothing, so the maneuver is free by construction.

    `radius` defaults to a WIDE pass, clamped clear of the gravity well. Pass
    `lm_tether_hole_close_rope(hole)` for the fast, dangerous one.
    """
    sid, hid = to_id(ship), to_id(hole)
    if sid is None or hid is None:
        return None
    if orbit_is(sid) or not lm_tether_sling_ready(sid):
        return None
    safe = lm_tether_hole_safe_rope(hid)
    arc_radius = float(radius) if radius else safe
    # release_on_undock=False: a ship that flew here is undocked the whole time, and the
    # default would end the arc on its first tick.
    carrier = orbit_capture(sid, hid, radius=arc_radius, speed=LM_HOLE_SLING_SPEED,
                            release_on_undock=False)
    if carrier is None:
        return None
    close = arc_radius < safe
    set_inventory_value(sid, _LM_SLING_CLOSE, close)
    set_timer(sid, "lm_hole_sling", seconds=LM_HOLE_SLING_COOLDOWN,
              signal="lm_tether_sling_ready")
    so = to_object(sid)
    if so is not None:
        particle_charge_start(
            so, seconds=LM_HOLE_SLING_ARC * arc_radius / LM_HOLE_SLING_SPEED)
    _lm_sling_ensure_tick()
    signal_emit("lm_tether_sling_start",
                {"SHIP_ID": sid, "HOLE_ID": hid, "ROPE": arc_radius, "CLOSE": close})
    return carrier


def _lm_sling_ensure_tick():
    """Arm the completion tick, re-arming across a mission restart.

    A restart clears the TickDispatcher but not this module global, so a cached handle to
    a task that no longer exists would mean the NEXT slingshot never gets a tick and the
    ship rode its carrier forever - the reused-interpreter trap, which only shows from run
    2 onward. Whenever this is the first live sling there cannot be a live task worth
    keeping, so drop whatever is cached and arm a fresh one.
    """
    global _lm_sling_task
    if _lm_sling_task is not None and len([s for s in role("__player__") if orbit_is(s)]) <= 1:
        try:
            _lm_sling_task.stop()
        except Exception:
            pass
        _lm_sling_task = None
    if _lm_sling_task is None:
        _lm_sling_task = TickDispatcher.do_interval(_lm_sling_tick, LM_HOLE_SLING_TICK)


def _lm_sling_tick(t=None):
    """Let go of anything that has come all the way round.

    Guarded per ship: an exception in a TickDispatcher callback does not stop here. It
    aborts every other task scheduled that tick and lands in the handler's catch-all,
    which pauses the sim behind an error page that raises again on Resume.
    """
    global _lm_sling_task
    live = 0
    for sid in [s for s in role("__player__") if orbit_is(s)]:
        try:
            swept = orbit_swept_of(sid)
            if swept is None:
                continue
            if swept < LM_HOLE_SLING_ARC:
                live += 1
                continue
            lm_tether_sling_finish(sid)
        except Exception as ex:
            log(f"slingshot: releasing {sid}: {ex}", "grav_tether", "error")
            try:
                orbit_release(sid)
            except Exception:
                pass
    if live == 0 and _lm_sling_task is not None:
        _lm_sling_task.stop()
        _lm_sling_task = None


def lm_tether_sling_finish(ship):
    """Out the far side: hand the helm back, flash, and bill a close pass."""
    sid = to_id(ship)
    if sid is None:
        return
    close = get_inventory_value(sid, _LM_SLING_CLOSE, False)
    orbit_release(sid)
    set_inventory_value(sid, _LM_SLING_CLOSE, False)
    so = to_object(sid)
    if so is not None:
        particle_charge_stop(so)
    if close:
        # A close pass is inside the well. The engine's own pull fighting the carrier is
        # the real danger, and the mock does not simulate it at all - so the strain is
        # also charged here, deterministically, where a headless test can see it.
        grid_damage_system(sid)
    signal_emit("lm_tether_sling_done", {"SHIP_ID": sid, "CLOSE": bool(close)})


#: How far a ship may be from a hole and still be offered the slingshot. The tether's own
#: reach: you can catch a gravity well from anywhere on or inside the arc you would ride.
LM_HOLE_SWING_REACH = 8000


def lm_tether_hole_in_reach(ship, hole, max_dist=LM_HOLE_SWING_REACH):
    """Whether this ship could slingshot on THIS hole right now.

    The range gate is not decoration: orbit_capture places a ship on its circle from any
    distance at all, so an ungated button would haul a cruiser 40 000u away in to the
    8 000u arc. Same reach as `lm_tether_nearest_hole`, so the Weapons menu and the cockpit
    button agree about what is close enough.
    """
    sid, hid = to_id(ship), to_id(hole)
    if sid is None or hid is None or not has_any_role(hid, "black_hole"):
        return False
    so, ho = to_object(sid), to_object(hid)
    if so is None or ho is None:
        return False
    dx, dy, dz = so.pos.x - ho.pos.x, so.pos.y - ho.pos.y, so.pos.z - ho.pos.z
    return (dx * dx + dy * dy + dz * dz) <= float(max_dist) * float(max_dist)


def lm_tether_nearest_hole(ship, max_dist=LM_HOLE_SWING_REACH):
    """The nearest black hole a ship could anchor on."""
    sid = to_id(ship)
    if sid is None:
        return None
    found = closest(sid, set(role("black_hole")), max_dist * 2)
    if found is None or found.distance > max_dist:
        return None
    return found.id


# ---------------------------------------------------------------------------------
# Enemy tethers
# ---------------------------------------------------------------------------------

#: How long a pinned ship must fight before it can break a hostile tether. Long enough
#: to be a real problem, short enough that being tethered is never the end of your game.
LM_TETHER_BREAK_SECONDS = 8

#: Throttle a pinned ship must hold to be counted as pulling against the beam. You break
#: free by burning hard away, not by sitting still - so the counter-play is an action.
LM_TETHER_BREAK_THROTTLE = 0.9


def lm_tether_enemy_grab(npc, target, rope=600):
    """An NPC pins a target with a tether. Returns the connection, or None.

    Deliberately routed through the ordinary tow, so every rule a player lives under
    applies to the NPC too: it cannot grab a ship above the speed limit, mass decides who
    actually gets dragged, and a hard hit shakes it loose.
    """
    nid, tid = to_id(npc), to_id(target)
    if nid is None or tid is None:
        return None
    if grav_tether_involves(tid):
        return None                     # already held - do not stack beams on one victim
    con = grav_tether_tow(nid, tid, rope)
    if con is not None:
        set_timer(tid, "tether_pinned", seconds=LM_TETHER_BREAK_SECONDS)
        signal_emit("lm_tether_pinned", {"SHIP_ID": tid, "BY_ID": nid})
    return con


def lm_tether_break_free(ship):
    """Counter-play: burn hard away and you tear loose.

    Requires BOTH the burn and the time - so it is something the crew does, not something
    that happens to them, and a pinned ship is never simply stuck.

    Returns True if it broke free this call.
    """
    sid = to_id(ship)
    if sid is None or not grav_tether_involves(sid):
        return False
    so = to_object(sid)
    if so is None:
        return False
    try:
        thr = so.data_set.get("playerThrottle", 0) or 0
    except Exception:
        thr = 0
    if float(thr) < LM_TETHER_BREAK_THROTTLE:
        set_timer(sid, "tether_pinned", seconds=LM_TETHER_BREAK_SECONDS)
        return False                    # not pulling - the clock restarts
    if not is_timer_finished(sid, "tether_pinned"):
        return False
    grav_tether_release_any(sid)
    signal_emit("lm_tether_broke_free", {"SHIP_ID": sid})
    return True


# ---------------------------------------------------------------------------------
# Admiral tug
# ---------------------------------------------------------------------------------

def lm_tether_admiral_tug(admiral, target, x, y, z, rope=400):
    """Reposition something from the strategic map by DRAGGING it, not teleporting it.

    A teleport is an edit; a tug is an event everyone can see coming, which is what makes
    it usable in front of players. The admiral's camera becomes the puller and flies to
    the destination, so the object follows under its own physics.
    """
    aid, tid = to_id(admiral), to_id(target)
    if aid is None or tid is None or not object_exists(tid):
        return None
    from sbs_utils.procedural.space_objects import target_pos
    con = grav_tether_tow(aid, tid, rope)
    if con is None:
        return None
    target_pos(aid, x, y, z, 1.0)
    signal_emit("lm_tether_admiral_tug", {"ADMIRAL_ID": aid, "TARGET_ID": tid})
    return con


def lm_tether_admiral_drop(admiral):
    """Let go of whatever the admiral is tugging."""
    aid = to_id(admiral)
    if aid is None:
        return False
    if not grav_tether_involves(aid):
        return False
    grav_tether_release_any(aid)
    return True
