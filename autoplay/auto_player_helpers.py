"""Helm arithmetic for the autoplayer's brain tree.

Pure functions, no engine state: the brain leaves stay readable and the numbers stay
testable without spawning anything. Everything a leaf actually WRITES goes through
`sbs_utils.procedural.helm`.

Prefixed `autoplay_` because every top-level def in an addon becomes a MAST global in one
flat, mission-wide namespace, assigned unconditionally with last-loaded winning - so two
addons with a bare `helm_speed_for` would compile clean and fail at runtime in whichever
one lost.
"""


# The distance ladder the console autoplayer uses, kept identical so the A/B compares
# decision STRUCTURE rather than a retuning.
_SPEED_LADDER = ((1000, None), (5000, 1.0), (10000, 2.0), (20000, 3.0), (30000, 4.0))


def autoplay_helm_speed_for(distance):
    """Throttle to close `distance`: creep in close, warp when it is far.

    Below 1000 units the throttle is proportional, so the ship eases in instead of
    arriving at speed and sailing past.
    """
    d = float(distance or 0)
    if d < 1000:
        return max(0.0, d / 1000.0)
    for limit, speed in _SPEED_LADDER:
        if speed is not None and d < limit:
            return speed
    return 5.0


def autoplay_helm_mine_cap(speed, mine_distance):
    """Cap `speed` by how close the nearest mine is.

    A CAP rather than a stop: docking and the weapons standoff already own speed zero, and
    a mid-space halt in a minefield helps nobody. This just keeps the ship slow enough that
    the course deflection below has room to work - at warp 5 a deflection that only starts
    at 2500 units fires far too late.
    """
    d = float(mine_distance or 0)
    if d < 2500:
        cap = 0.5
    elif d < 5000:
        cap = 1.0
    elif d < 8000:
        cap = 2.0
    else:
        return speed
    return min(speed, cap)


def autoplay_helm_deflect(ship_pos, mine_pos, goal, mine_distance):
    """Bend `goal` away from a mine, growing as the mine nears. Returns a Vec3-like.

    Deflection rather than flight: a station ringed by mines has to stay reachable, and
    fleeing a ring means bouncing off it forever. Repulsion scales to zero at 2500 units,
    so this is inert further out.
    """
    d = max(1.0, float(mine_distance or 0))
    scale = (2500.0 - d) / 2500.0
    if scale <= 0:
        return goal
    reach = goal.length() if hasattr(goal, "length") else 0.0
    factor = reach * scale / d
    return goal + (ship_pos - mine_pos) * factor


def autoplay_shields_down(blob):
    """True when every shield facing on `blob` is essentially gone.

    Shields-down is the gate for both a surrender demand and a PShock, so it has to mean
    ALL facings rather than any: a ship with one intact facing is still shielded from
    something. Returns False for a target with no shield data at all - unknown is not
    the same as down.
    """
    if blob is None:
        return False
    count = int(blob.get("shield_count", 0) or 0)
    if count <= 0:
        return False
    for i in range(count):
        mx = blob.get("shield_max_val", i) or 0
        cur = blob.get("shield_val", i) or 0
        if mx > 0 and (cur / mx) >= 0.1:
            return False
    return True


def autoplay_weapon_choice(ship_id, target_id, rng, cluster_size, aoe_safe,
                           shields_down, opener_target, standoff):
    """Pick a weapon, or "none"/"opener". The doctrine ladder, unchanged.

    Kept as one function rather than spread across brain leaves for the reason
    `turret_brains.mast` gives about its own policy: a decision split across nodes that can
    disagree is harder to reason about than one that cannot. `aoe_safe` is the friendly-fire
    veto and gates every area weapon.
    """
    from sbs_utils.procedural.torpedoes import torpedo_get_count_for_ship

    def have(kind):
        try:
            return torpedo_get_count_for_ship(ship_id, kind)[0]
        except Exception:
            return 0

    nuke, emp, homing, pshock = have("Nuke"), have("EMP"), have("Homing"), have("PShock")
    if shields_down and pshock > 0:
        return "PShock"
    if aoe_safe and standoff <= rng <= 10000 and opener_target != target_id \
            and (emp > 0 or nuke > 0):
        return "opener"
    if aoe_safe and cluster_size >= 3 and nuke > 0:
        return "Nuke"
    if aoe_safe and cluster_size == 2 and emp > 0:
        return "EMP"
    if homing > 0:
        return "Homing"
    if aoe_safe and emp > 0:
        return "EMP"
    if aoe_safe and nuke > 0:
        return "Nuke"
    return "none"


def autoplay_set_power_plan(ship_id, boost):
    """Overpower drive and weapons, backing off on low energy and holding hot systems."""
    from sbs_utils.procedural.helm import (helm_eng_controls, helm_energy,
                                           helm_system_heat, helm_set_power)
    energy = helm_energy(ship_id)
    if energy < 250:
        boost = 1.0
    elif energy < 500 and boost > 1.2:
        boost = 1.2
    for _i, label, _sysi in helm_eng_controls(ship_id):
        low = label.lower()
        want = 1.0
        if any(k in low for k in ("impulse", "warp", "maneuver", "jump",
                                  "beam", "torp", "missile")):
            want = boost
        heat = helm_system_heat(ship_id, label)
        if heat > 0.7:
            want = 1.0
        elif heat > 0.5 and want > 1.2:
            want = 1.2
        helm_set_power(ship_id, label, want)


def autoplay_spend_coolant(ship_id):
    """Pour available coolant onto the hottest systems first, never past what we carry."""
    from sbs_utils.procedural.helm import _ds, _num
    ds = _ds(ship_id)
    if ds is None:
        return
    total = _num(ds, "system_coolant_available")
    remaining = total
    for si in range(4):
        heat = _num(ds, "system_cur_heat", si)
        want = int(total * heat) if heat > 0.25 else 0
        want = min(want, remaining)
        ds.set("system_coolant_used", want, si)
        remaining -= want
