"""What Science reads on an enemy's STATUS tab, and who keeps it true.

The tab used to be a placeholder - "Dynamic properties will appear in this area" - with
one exception: an elite charging an ability spliced a countdown into it from inside the
ability's own loop. That arrangement had the ability writing the console, so the line
only ever appeared for the four abilities that had a loop, was written once per player
ship for a value the engine keeps per SIDE, and was never taken down again.

So this module owns the line instead, and there is exactly one of it:

    condition [+ tell [+ " in M:SS"]]

The **condition** is read off the target's own blob every time - shields down, a system
hurt, or nothing wrong. The **tell** is whatever a system elsewhere has declared true
right now (`science_status_tell` on the ship, with an optional timer to count down); the
elite abilities set it while they charge. Nothing is ever spliced into a previous
version of the line: the text is rebuilt from those two sources, so a stale line cannot
survive a rebuild and no sentinel string is needed to recognize one.

A tab is a STORED string, not a live render - `+ "status": <scan>` writes once, when the
scan completes, and re-selecting a contact never re-runs it. Keeping it current is
therefore a push, from `science_status_tick` (a second) and from a `science_status_dirty`
signal when something wants the change immediately. The registry only holds ships a
science officer has actually scanned, so the walk is over a handful of contacts.
"""
from sbs_utils.procedural.inventory import get_inventory_value
from sbs_utils.procedural.query import (get_data_set_value, object_exists, to_id,
                                        to_object)
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.science import (science_has_scan_data,
                                          science_update_scan_data)
from sbs_utils.procedural.timers import get_time_remaining, is_timer_finished

#: The four systems the engine tracks, in `system_damage` index order (sbs.SHPSYS).
SCIENCE_SYSTEMS = ("weapons", "engines", "sensors", "shield generators")

#: Shield facets, in `shield_val` index order.
SCIENCE_FACETS = ("forward", "aft")

#: The inventory keys anything may set to put a line on a ship's status tab. A contract
#: rather than a call, so the addon that sets one does not have to be loaded with this.
SCIENCE_TELL_KEY = "science_status_tell"
SCIENCE_TELL_TIMER_KEY = "science_status_tell_timer"

SCIENCE_STATUS_OK = "Ready for combat."

# target_id -> {"sides": set, "line": str, "sys": tuple, "shield": tuple}
_tracked = {}


def science_status_clear_all():
    """Forget every tracked contact. Mission reload and tests."""
    _tracked.clear()


def _readings(id_or_obj):
    """(system damage fractions, shield fractions) for a ship, each 0.0-1.0.

    Every read is coalesced. The engine answers None for a field it never set - a real
    bridge would raise on the first comparison where the mock's typed defaults hide it.
    """
    ship_id = to_id(id_or_obj)
    systems = []
    for index in range(len(SCIENCE_SYSTEMS)):
        most = get_data_set_value(ship_id, "system_max_damage", index, default=0) or 0
        hurt = get_data_set_value(ship_id, "system_damage", index, default=0) or 0
        systems.append(min(1.0, hurt / most) if most > 0 else 0.0)
    shields = []
    for index in range(len(SCIENCE_FACETS)):
        most = get_data_set_value(ship_id, "shield_max_val", index, default=0) or 0
        now = get_data_set_value(ship_id, "shield_val", index, default=0) or 0
        shields.append(min(1.0, now / most) if most > 0 else 1.0)
    return tuple(systems), tuple(shields)


def science_condition_text(id_or_obj):
    """The resting line: the worst thing currently true about this ship, in words.

    The verb comes from the DELTA against the last reading, not from the reading alone.
    Nothing in this mission repairs an NPC's systems, so a flat "repairing its engines"
    would be a standing lie; "repairing" is only said when the damage is actually
    falling, which is what a Science officer watching the number would see.
    """
    ship_id = to_id(id_or_obj)
    if ship_id is None or not object_exists(ship_id):
        return ""
    systems, shields = _readings(ship_id)
    was = _tracked.get(ship_id)
    old_systems = was.get("sys") if was else None
    old_shields = was.get("shield") if was else None

    worst = max(range(len(systems)), key=lambda i: systems[i]) if systems else None
    if worst is not None and systems[worst] > 0:
        name = SCIENCE_SYSTEMS[worst]
        mending = old_systems is not None and systems[worst] < old_systems[worst]
        if mending:
            return f"Repairing damage to its {name}."
        return f"Its {name} are damaged."

    weakest = min(range(len(shields)), key=lambda i: shields[i]) if shields else None
    if weakest is not None and shields[weakest] < 0.99:
        name = SCIENCE_FACETS[weakest]
        rising = old_shields is not None and shields[weakest] > old_shields[weakest]
        if rising:
            return f"Rebuilding its {name} shields."
        if shields[weakest] <= 0.01:
            return f"Its {name} shields are down."
        return f"Its {name} shields are weakened."

    return SCIENCE_STATUS_OK


def science_status_tell(id_or_obj):
    """The declared line, with its countdown, or "" when nothing is charging."""
    ship_id = to_id(id_or_obj)
    tell = get_inventory_value(ship_id, SCIENCE_TELL_KEY, None)
    if not tell:
        return ""
    timer = get_inventory_value(ship_id, SCIENCE_TELL_TIMER_KEY, None)
    if not timer or is_timer_finished(ship_id, timer):
        return str(tell)
    seconds = int(get_time_remaining(ship_id, timer) or 0)
    if seconds <= 0:
        return str(tell)
    return f"{tell} - {seconds}s"


def science_status_text(id_or_obj):
    """The whole line, rebuilt from source. Plain ASCII, and never any braces - MAST
    re-runs f-string formatting on an assigned string, so a brace here would raise at
    the caller's assignment rather than here."""
    parts = [science_condition_text(id_or_obj), science_status_tell(id_or_obj)]
    return " ".join(p for p in parts if p)


def science_status_track(target, origin):
    """Remember that this side is looking at this ship, so its line is kept current.

    Called from the status tab's own scan, which means the registry only ever holds
    contacts somebody actually scanned.
    """
    target_id = to_id(target)
    origin_obj = to_object(origin)
    if target_id is None or origin_obj is None:
        return
    side = getattr(origin_obj, "side", None)
    if side is None:
        return
    entry = _tracked.setdefault(target_id, {"sides": set(), "line": None,
                                            "sys": None, "shield": None})
    entry["sides"].add(side)
    entry["line"] = science_status_text(target_id)
    entry["sys"], entry["shield"] = _readings(target_id)


def science_status_push(id_or_obj):
    """Write the line, if it moved, to every side that has scanned this ship.

    Once per SIDE, because that is how the engine stores it - `science_update_scan_data`
    indexes the target's blob by the scanning ship's side, so a loop over player ships
    wrote the same slot N times. And only where a status scan already exists: pushing to
    a side that never scanned would hand it intelligence it did not earn.
    """
    target_id = to_id(id_or_obj)
    entry = _tracked.get(target_id)
    if entry is None:
        return False
    if not object_exists(target_id):
        _tracked.pop(target_id, None)
        return False
    line = science_status_text(target_id)
    entry["sys"], entry["shield"] = _readings(target_id)
    if line == entry["line"]:
        return False
    entry["line"] = line
    wrote = False
    for origin in _scanners(target_id, entry):
        science_update_scan_data(origin, target_id, line, "status")
        wrote = True
    return wrote


def _scanners(target_id, entry):
    """One live ship per side that has scanned this target - the origin
    `science_update_scan_data` needs to reach that side's copy of the blob."""
    found = []
    covered = set()
    for player_id in role("__player__"):
        player = to_object(player_id)
        side = getattr(player, "side", None) if player is not None else None
        if side is None or side in covered or side not in entry["sides"]:
            continue
        if science_has_scan_data(player_id, target_id, "status"):
            covered.add(side)
            found.append(player_id)
    return found


def science_status_tick():
    """Keep every tracked contact's line current. Returns how many were rewritten."""
    wrote = 0
    for target_id in list(_tracked.keys()):
        if not object_exists(target_id):
            _tracked.pop(target_id, None)
            continue
        if science_status_push(target_id):
            wrote += 1
    return wrote
