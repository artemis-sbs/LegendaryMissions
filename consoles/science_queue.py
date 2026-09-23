"""The scan queue, owned by script and shared across a SIDE.

The engine keeps its own queue, advances it by distance, and publishes only the head of
it in the scanning ship's blob (`cur_scan_ID` / `cur_scan_type` / `cur_scan_percent`).
There is no script API to read the rest, add to it, cancel or reorder - `sbs` exposes
`send_comms_button_info` and friends and nothing named `send_science_*` at all - so a
console cannot show a queue it cannot see.

This is the prototype's answer: keep the queue ourselves. An entry is (target, tab), the
head is the one advancing, and completing one pops it so the next starts. When an entry
lands we call `science_ensure_scan`, which synthesizes the real `science_scan_complete`
event through the promise machinery - the same path Legendary's auto-scan already ships
on - so mission `//science` routes run exactly as they would after a player-driven scan.

WHY PER SIDE, not per ship: the scan TEXT is already stored per side. `science_set_scan_data`
writes `target_blob.set(tab, msg, origin.side)`, which is why one console scanning a contact
marks it known for the whole fleet. A queue keyed per ship would therefore let two science
officers on two ships spend sensor time on a result they both already share.

WHAT THIS IS NOT: the engine's timing. A forced completion is instant, so the delay below
is ours, modelled on the engine's documented rule (rate falls off with range beyond the
scanner's own sensor range) rather than measured against it. That is the honest cost of
owning the queue, and it is why this lives behind a setting.

Prefixed `lm_sci_` because every top-level function here becomes a MAST global in one flat,
mission-wide namespace. A leading underscore is private to this file.
"""
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.query import to_object, to_id, object_exists
from sbs_utils.procedural.science import science_ensure_scan, science_get_scan_data
from sbs_utils.procedural.execution import log

#: The beat's reference time. Only a unit for the rate arithmetic now - what a scan
#: actually costs comes from the delays below, or from the engine's own fields.
LM_SCI_SCAN_SECONDS = 8.0

#: FALLBACKS, used only when the engine does not publish its own scan delays.
#: Point-blank, and at the ship's own sensor range. A contact beyond that range keeps
#: getting slower on the same line, up to LM_SCI_SCAN_SLOWEST.
LM_SCI_CLOSEST_SECONDS = 3.0
LM_SCI_FARTHEST_SECONDS = 20.0

#: Hard bounds on the result. Never instant - an instant scan is not a decision, and the
#: queue only reads as a resource if the head takes long enough to see. Never endless -
#: a scan that cannot finish reads as a bug rather than as distance.
LM_SCI_SCAN_FASTEST = 2.0
LM_SCI_SCAN_SLOWEST = 60.0

#: Never slower than this multiple of the close-range time, or a distant contact reads
#: as hung rather than slow. At 0.2 the longest a scan can take is 5x the base.
LM_SCI_SCAN_MIN_RATE = 0.2

#: Never faster than this, so a contact alongside is quick rather than instant - an
#: instant scan is not a decision, and the queue only reads as a resource if the head
#: takes long enough to see. At 3.0 the shortest a scan can take is a third of the base.
LM_SCI_SCAN_MAX_RATE = 3.0

#: Engineering's sensor efficiency multiplies the scan rate: powering sensors up makes
#: science faster, letting them burn makes it slower. `sensor_damage_coeff` is the same
#: derived coefficient Engineering's own Systems tab shows, so the two consoles are
#: reading one number - and it can exceed 1.0 when a pool is TUNED, which is what makes
#: overpowering sensors worth doing.
LM_SCI_SENSOR_COEFF_KEY = "sensor_damage_coeff"

#: Floor for that multiplier. Wrecked sensors should hurt, not stop the console dead -
#: a scan that can never finish reads as a bug rather than as damage.
LM_SCI_SENSOR_COEFF_MIN = 0.25

#: Used when a ship's blob has no `ship_base_scan_range` - the engine answers None for a
#: field nothing has set, and an unguarded read raises `'NoneType' < int` on a real bridge
#: while the mock answers a typed default and looks fine.
LM_SCI_DEFAULT_SCAN_RANGE = 25000.0

#: {side: [ {"target": id, "tab": str, "origin": id, "pct": float} ]}, head first.
_queues = {}

#: Bumped on every structural change, so an `on change` repaints without diffing the list.
_revision = 0

#: Sim time of the last tick, so the beat does not depend on being called at a fixed rate.
_last_tick = None


def _bump():
    global _revision
    _revision += 1


def _side_of(origin):
    """The side a scan is credited to, or None. An origin with no side cannot own scan
    data - the blob is indexed BY side, so an empty one writes to a slot nothing reads."""
    obj = to_object(origin)
    side = getattr(obj, "side", None) if obj is not None else None
    return side or None


def lm_sci_queue_side(origin):
    """Public form of the side lookup, so MAST and the panel agree on the key."""
    return _side_of(origin)


def lm_sci_queue_list(side):
    """This side's queue, head first. Entry 0 is the one actually scanning."""
    return list(_queues.get(side, ()))


def lm_sci_queue_revision(side=None):
    """What an `on change` watches. The head's percent is included, so a progress bar
    moves without every other console repainting on it."""
    q = _queues.get(side or "", ())
    head_pct = int(q[0]["pct"]) if q else -1
    return (_revision, len(q), head_pct)


def lm_sci_queue_add(origin, target, tab="scan"):
    """Queue `tab` on `target` for the side `origin` belongs to. True if it was added.

    Queuing the same (target, tab) twice is a no-op rather than a duplicate entry, and
    an already-scanned tab is never queued - pressing it is a navigation, not a request.
    """
    side = _side_of(origin)
    origin_id, target_id = to_id(origin), to_id(target)
    if not side or not origin_id or not target_id:
        return False
    if not object_exists(target_id) or not object_exists(origin_id):
        return False
    if lm_sci_queue_is_scanned(origin_id, target_id, tab):
        return False
    q = _queues.setdefault(side, [])
    if any(e["target"] == target_id and e["tab"] == tab for e in q):
        return False
    q.append({"target": target_id, "tab": tab, "origin": origin_id, "pct": 0.0})
    _bump()
    return True


def lm_sci_queue_remove(side, target, tab="scan"):
    """Drop a queued scan. Removing the HEAD simply promotes the next entry."""
    q = _queues.get(side)
    if not q:
        return False
    target_id = to_id(target)
    keep = [e for e in q if not (e["target"] == target_id and e["tab"] == tab)]
    if len(keep) == len(q):
        return False
    _queues[side] = keep
    _bump()
    return True


def lm_sci_queue_move_to_front(side, target, tab="scan"):
    """Jump an entry ahead of everything else this side asked for."""
    q = _queues.get(side)
    if not q:
        return False
    target_id = to_id(target)
    for i, e in enumerate(q):
        if e["target"] == target_id and e["tab"] == tab:
            if i == 0:
                return False
            # Restart it: a partial percent earned at the back of the queue is not
            # sensor time the ship actually spent, because only the head advances.
            e["pct"] = 0.0
            q.insert(0, q.pop(i))
            _bump()
            return True
    return False


def lm_sci_queue_move_up(side, target, tab="scan"):
    """Swap an entry with the one ahead of it. True if it moved.

    One place, not to the front: a science officer reordering a queue is making a small
    correction, and a button that leaps to the head is hard to undo with the same button.
    """
    q = _queues.get(side)
    if not q:
        return False
    target_id = to_id(target)
    for i, e in enumerate(q):
        if e["target"] == target_id and e["tab"] == tab:
            if i == 0:
                return False
            # The entry that gives up the head gives up its progress with it: only the
            # head advances, so percent earned there is not time the new head has spent.
            q[i - 1]["pct"] = 0.0
            e["pct"] = 0.0
            q[i - 1], q[i] = q[i], q[i - 1]
            _bump()
            return True
    return False


def lm_sci_queue_position(side, target, tab="scan"):
    """1-based position in the queue, or 0 when it is not queued. 1 is the active scan."""
    target_id = to_id(target)
    for i, e in enumerate(_queues.get(side, ())):
        if e["target"] == target_id and e["tab"] == tab:
            return i + 1
    return 0


def lm_sci_queue_percent(side, target, tab="scan"):
    """Progress of this entry, 0-100. Only the head advances, so anything behind it
    reads 0 by construction rather than by accident."""
    target_id = to_id(target)
    for e in _queues.get(side, ()):
        if e["target"] == target_id and e["tab"] == tab:
            return int(e["pct"])
    return 0


def lm_sci_queue_is_scanned(origin, target, tab="scan"):
    """Does this side already hold data on this tab?

    Delegates to the library rather than keeping a parallel record, so a scan forced by a
    mission (`science_ensure_scan`, an auto-scan, a scripted reveal) counts exactly as
    much as one this queue ran.
    """
    text = science_get_scan_data(origin, target, tab)
    return not (text is None or text == "" or text == "no data" or text == "Default Scan")


def lm_sci_scan_seconds(origin_id, target_id):
    """How long a scan of this contact takes from here, in seconds. None if unknowable.

    The numbers live here; the SHAPE lives in science_scan_time, which prefers the
    engine's own `closest_scan_delay` / `farthest_scan_delay` and divides by the hull's
    and Engineering's sensor coefficients.
    """
    from science_scan_time import lm_sci_scan_time_compute
    return lm_sci_scan_time_compute(origin_id, target_id,
                    LM_SCI_CLOSEST_SECONDS, LM_SCI_FARTHEST_SECONDS,
                    LM_SCI_SCAN_FASTEST, LM_SCI_SCAN_SLOWEST,
                    LM_SCI_DEFAULT_SCAN_RANGE)


def _scan_rate(origin_id, target_id):
    """The beat's multiplier, derived FROM the time so the two cannot disagree.

    `lm_sci_queue_tick` advances `100 / LM_SCI_SCAN_SECONDS * rate` per second, so a rate
    of `LM_SCI_SCAN_SECONDS / seconds` makes the scan take exactly `seconds`.
    """
    seconds = lm_sci_scan_seconds(origin_id, target_id)
    if not seconds:
        return None
    return LM_SCI_SCAN_SECONDS / seconds


def lm_sci_queue_tick():
    """Advance the head of every side's queue. Returns how many scans completed.

    Driven off sim seconds rather than a fixed step, so the beat's own period can change
    without changing how long a scan takes.
    """
    global _last_tick
    now = FrameContext.sim_seconds
    if now is None:
        return 0
    dt = 0.0 if _last_tick is None else max(0.0, now - _last_tick)
    _last_tick = now
    if not _queues or dt <= 0.0:
        return 0

    completed = 0
    for side in list(_queues.keys()):
        q = _queues.get(side) or []
        # Drop entries whose target or scanner has died, wherever they sit in the queue.
        alive = [e for e in q if object_exists(e["target"]) and object_exists(e["origin"])]
        if len(alive) != len(q):
            _bump()
        if not alive:
            _queues.pop(side, None)
            continue
        _queues[side] = alive
        head = alive[0]
        # Somebody else may have revealed this tab while it sat in the queue.
        if lm_sci_queue_is_scanned(head["origin"], head["target"], head["tab"]):
            alive.pop(0)
            _bump()
            continue
        rate = _scan_rate(head["origin"], head["target"])
        if rate is None:
            alive.pop(0)
            _bump()
            continue
        head["pct"] += (100.0 / LM_SCI_SCAN_SECONDS) * rate * dt
        if head["pct"] < 100.0:
            continue
        alive.pop(0)
        _bump()
        science_ensure_scan(head["origin"], head["target"], head["tab"])
        completed += 1
        log(f"scan complete {head['tab']} on {head['target']} for {side}", "science")
    return completed


def lm_sci_queue_clear():
    """Forget every queue. The mission reset calls this; tests use it between cases."""
    global _last_tick
    _queues.clear()
    _last_tick = None
    _bump()


def _queue_probe():
    """Total entries held, for the reset ledger."""
    return sum(len(v) for v in _queues.values())


# Module-level per-mission state must declare itself, or a second run inherits it and the
# bug only shows from run 2 onward. handlerhooks owns the ledger; importing it lazily keeps
# this module importable by a plain unit test that never starts a mission.
try:
    from sbs_utils.handlerhooks import register_reset_state
    register_reset_state("lm.science_queue", _queue_probe)
except Exception:                                       # noqa: BLE001
    pass
