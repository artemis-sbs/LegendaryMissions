"""Grav-tether phase 5: the things the tether makes possible once it exists.

Black-hole swing, enemy tethers and the admiral's tug. Each is small on its own - the
primitive and the constraints layer already do the work - which is the point of having
built those first.

Prefixed `lm_tether_`, never `grav_tether_`, so nothing here shadows the library.
"""

from sbs_utils.procedural.execution import log
from sbs_utils.procedural.grav_tether import (grav_tether_involves, grav_tether_lock,
                                              grav_tether_mass, grav_tether_release_any,
                                              grav_tether_sources_of, grav_tether_swing,
                                              grav_tether_tow)
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


def lm_tether_swing_hole(ship, hole, rope=0):
    """Swing on a black hole - the slingshot the mode was invented for.

    The rope is clamped clear of the gravity well, so the orbit is a nerve test rather
    than a delivery service into the hole.
    """
    sid, hid = to_id(ship), to_id(hole)
    if sid is None or hid is None:
        return None
    safe = lm_tether_hole_safe_rope(hid, rope)
    con = grav_tether_swing(hid, sid, safe)
    if con is not None:
        signal_emit("lm_tether_hole_swing", {"SHIP_ID": sid, "HOLE_ID": hid, "ROPE": safe})
    return con


#: How far a ship may be from a hole and still be offered the slingshot.
LM_HOLE_SWING_REACH = 12000


def lm_tether_hole_in_reach(ship, hole, max_dist=LM_HOLE_SWING_REACH):
    """Whether this ship could slingshot on THIS hole right now.

    The range gate is not decoration: `_tick_swing` pulls a ship onto the rope circle from
    any distance at all, so an ungated button would yank a cruiser 40 000u away in to the
    8 000u safe rope. Same reach as `lm_tether_nearest_hole`, so the Weapons menu and the
    cockpit button agree about what is close enough.
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
