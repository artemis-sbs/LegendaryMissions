"""Fighter grav-tether: the nose is the cursor.

A manual click-select is wrong in a cockpit, so a pilot gets ONE button. It runs a
forward-cone query, and then either acts immediately (the target says what to do) or
synthesizes a popup on the auto-picked target so the pilot can choose - Path B from
GRAV_TETHER_PLAN.md, which consumes no select channel at all. Comms, weapons and science
selects stay free.

Functions are prefixed `lm_tether_`, NOT `grav_tether_`: addon functions land in the same
flat MAST namespace as the library, so a `grav_tether_*` name here would shadow the
primitive it is built on (`sbs lint` ns-shadows-library).
"""

from sbs_utils.helpers import FakeEvent, FrameContext
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.popup import start_popup_selected
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.roles import any_role, has_any_role, role
from sbs_utils.procedural.space_objects import closest_in_front
from sbs_utils.procedural.grav_tether import (grav_tether_involves, grav_tether_lock,
                                              grav_tether_reel, grav_tether_release_any,
                                              grav_tether_swing, grav_tether_tow)

#: How far ahead a pilot can reach.
#:
#: NOTE this is a REAL 4000, and the old inline call asked for 8000 and did not get it:
#: `closest(max_dist=D)` narrows the candidate set with `broad_test_around(D, D)`, a box
#: of WIDTH D - so it only ever reaches D/2. 4000 therefore preserves exactly today's
#: feel while meaning what it says. Raise it deliberately, not by accident.
LM_TETHER_RANGE = 4000

#: Half-angle of the nose cone. Wide enough to forgive a cockpit, narrow enough that
#: "what I am pointing at" is unambiguous to the pilot.
LM_TETHER_CONE = 40

#: What a fighter may grab. `#` is the invisible-marker role (cameras, GM rigs).
LM_TETHER_TARGETS = "__npc__,item,upgrade,station,asteroid"

#: Where the cycle position lives, per ship.
_LM_TETHER_CYCLE = "tether:cycle"


def lm_tether_candidates(ship):
    """Everything this fighter could tether, before the cone and the range."""
    sid = to_id(ship)
    if sid is None:
        return set()
    return any_role(LM_TETHER_TARGETS) - role("#") - {sid}


def lm_tether_acquire(ship, skip=0):
    """The skip-th nearest tetherable object in the nose cone, or None.

    `skip` is what makes "Cycle target" possible: the popup re-runs this with skip+1 to
    walk outward through the cone rather than re-picking the same rock.

    Calls the library's `closest_in_front` repeatedly rather than re-implementing the cone
    test, dropping each hit before looking again - and hands it a COPY every time, because
    `closest` narrows the set it is given in place.
    """
    sid = to_id(ship)
    if sid is None:
        return None
    cands = lm_tether_candidates(sid)
    found = None
    for _ in range(int(skip) + 1):
        if not cands:
            return None
        found = closest_in_front(sid, set(cands), LM_TETHER_RANGE, LM_TETHER_CONE)
        if found is None:
            return None
        cands.discard(found.id)
    return found


def lm_tether_cycle_reset(ship):
    """Start cycling from the nearest again (on release, or on a fresh press)."""
    sid = to_id(ship)
    if sid is not None:
        set_inventory_value(sid, _LM_TETHER_CYCLE, 0)


def lm_tether_cycle_next(ship):
    """Advance to the next candidate in the cone and return it, wrapping at the end.

    Wrapping matters: a pilot cycling past the last rock should come back round rather
    than find the button dead.
    """
    sid = to_id(ship)
    if sid is None:
        return None
    nxt = (get_inventory_value(sid, _LM_TETHER_CYCLE, 0) or 0) + 1
    found = lm_tether_acquire(sid, nxt)
    if found is None:
        nxt = 0
        found = lm_tether_acquire(sid, 0)
    set_inventory_value(sid, _LM_TETHER_CYCLE, nxt)
    return found


def lm_tether_best_action(target):
    """The one obvious thing to do with this target, or None if it is a choice.

    Ambiguity is the whole reason the popup exists: a pod is a pickup and a rock is an
    anchor, but a derelict freighter could be a tow OR a rigid lock, and only the pilot
    knows which. Returning None is what opens the menu.
    """
    tid = to_id(target)
    if tid is None:
        return None
    if has_any_role(tid, "item,upgrade"):
        return "reel"
    if has_any_role(tid, "asteroid"):
        return "swing"
    return None


def lm_tether_apply(ship, target, action):
    """Do it. One place, so the button and the popup cannot drift apart."""
    sid, tid = to_id(ship), to_id(target)
    if sid is None or tid is None:
        return None
    if action == "reel":
        grav_tether_reel(sid, tid)
    elif action == "swing":
        # The ANCHOR is the target and the pulled body is the fighter - the only mode
        # where the ship is the thing on the end of the rope.
        grav_tether_swing(tid, sid, 800)
    elif action == "lock":
        grav_tether_lock(sid, tid)
    else:
        grav_tether_tow(sid, tid, 500)
    return action


def lm_tether_open_popup(ship, target):
    """Synthesize the popup on an auto-picked target (Path B).

    No select channel is consumed: the event is fabricated here rather than coming from a
    click, so comms/weapons/science selects are untouched. `sub_tag` decides the route
    family - "tether" opens `//popup/tether`.
    """
    sid, tid = to_id(ship), to_id(target)
    if sid is None or tid is None:
        return None
    # parent_id as well as selected_id: the popup takes its TITLE from the parent (that
    # is the object a real hold-click was on), so without it a synthesized menu came up
    # headed "Location" instead of naming what the nose had found.
    ev = FakeEvent(client_id=(FrameContext.client_id or 0), tag="popup",
                   sub_tag="tether", origin_id=sid, selected_id=tid, parent_id=tid)
    return start_popup_selected(ev)


def lm_tether_press(ship):
    """The whole one-button interaction.

    Tethered      -> release (toggle, press/press - momentum preserved for the slingshot).
    Unambiguous   -> act at once; making a pilot confirm "yes, swing on the rock" is a
                     menu for the sake of a menu.
    Otherwise     -> open the popup on what the nose found.

    Returns a short string for the caller to log/report: released / <action> / popup /
    nothing.
    """
    sid = to_id(ship)
    if sid is None:
        return "nothing"
    if grav_tether_involves(sid):
        grav_tether_release_any(sid)
        lm_tether_cycle_reset(sid)
        return "released"
    lm_tether_cycle_reset(sid)
    found = lm_tether_acquire(sid, 0)
    if found is None:
        return "nothing"
    action = lm_tether_best_action(found.id)
    if action is not None:
        lm_tether_apply(sid, found.id, action)
        return action
    lm_tether_open_popup(sid, found.id)
    return "popup"


def lm_tether_target_name(target):
    """A short label for the popup title line."""
    so = to_object(to_id(target))
    if so is None:
        return "target"
    return getattr(so, "name", None) or "target"
