"""How long a scan takes - engine numbers first, constants only as a stand-in.

Split out of `science_queue` because it is the part most likely to be wrong, and the part
worth reading on its own: everything here is either a field the engine owns or a
deliberate fallback, and the difference is marked.

THE SHAPE IS THE ENGINE'S. The scanning ship's blob carries `closest_scan_delay` and
`farthest_scan_delay` - scan times at zero range and at the ship's own sensor range - and
this interpolates between them by distance. Nothing in the tree writes those fields, so on
a bridge where the engine does not either, the constants in `science_queue` stand in. What
does not change either way is that range drives the cost, which is the engine's documented
rule.

TWO COEFFICIENTS THEN DIVIDE IT, because both mean "sensors working better":

* `scan_strength_coeff` - per HULL, from shipData. A science ship should out-scan a
  freighter, and this is the field that says so.
* `sensor_damage_coeff` - per SHIP and live, from Engineering's grid. The same number
  Engineering's Systems tab shows, so powering sensors up speeds science's scans and
  letting them burn slows them. It can exceed 1.0 when the pool is TUNED, which is what
  makes overpowering sensors worth doing - one number, two consoles, and a reason for
  those two officers to talk to each other.

Prefixed `lm_sci_` because every top-level function here becomes a MAST global in one
flat, mission-wide namespace. A leading underscore is private to this file.
"""
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.query import to_object, to_id

#: Engineering's live sensor efficiency.
LM_SCI_SENSOR_COEFF_KEY = "sensor_damage_coeff"

#: Wrecked sensors should HURT, not stop the console dead: a scan that can never finish
#: reads as a bug rather than as damage.
LM_SCI_SENSOR_COEFF_MIN = 0.25

#: The hull's own scanning strength, from shipData.
LM_SCI_STRENGTH_COEFF_KEY = "scan_strength_coeff"

#: The engine's own scan times, if it publishes them.
LM_SCI_CLOSEST_DELAY_KEY = "closest_scan_delay"
LM_SCI_FARTHEST_DELAY_KEY = "farthest_scan_delay"


def _written(obj, key):
    """Did anything actually write this field?

    ZERO MEANS "NEVER SET", NOT "ZERO". The engine answers a typed default for a field
    nothing has written and the mock answers 0.0 for every coefficient - so reading one
    literally would multiply a scan time by zero, or divide by it. Worse here than in a
    readout: a console that silently never finishes a scan reads as broken rather than
    as damaged.
    """
    if obj is None:
        return False
    value = obj.data_set.get(key, 0)
    return value is not None and float(value) > 0.0


def _coeff(obj, key, floor=None):
    """A blob coefficient as a multiplier, 1.0 when it was never populated."""
    if not _written(obj, key):
        return 1.0
    value = float(obj.data_set.get(key, 0))
    return max(floor, value) if floor is not None else value


def lm_sci_sensor_coeff(ship_id):
    """Engineering's sensor efficiency as a scan multiplier. 1.0 when unknown."""
    return _coeff(to_object(ship_id), LM_SCI_SENSOR_COEFF_KEY, LM_SCI_SENSOR_COEFF_MIN)


def lm_sci_hull_scan_coeff(ship_id):
    """The hull's own scanning strength. 1.0 when unknown."""
    return _coeff(to_object(ship_id), LM_SCI_STRENGTH_COEFF_KEY)


def lm_sci_scan_time_compute(origin_id, target_id, closest_default, farthest_default,
                        fastest, slowest, default_range):
    """Seconds for `origin` to scan `target`. None when it cannot be worked out.

    NOT named `lm_sci_scan_seconds`: every top-level function in an addon `.py` becomes a
    MAST global in ONE flat, mission-wide namespace, assigned unconditionally with no
    warning - so two files defining that name collide, last loaded wins, and the caller
    gets whichever signature it did not expect. That is exactly what happened here
    (`takes 2 positional arguments but 7 were given`). `science_queue` owns the short
    name; this is the computation behind it.

    The fallback numbers come from `science_queue`, which owns them; this module owns the
    SHAPE and the choice to prefer the engine's fields over them.
    """
    origin, target = to_object(origin_id), to_object(target_id)
    if origin is None or target is None:
        return None
    ctx = FrameContext.context
    if ctx is None or ctx.sbs is None:
        return None
    try:
        dist = max(1.0, float(ctx.sbs.distance_id(to_id(origin_id), to_id(target_id))))
    except Exception:                                   # noqa: BLE001
        return None

    rng = float(origin.data_set.get("ship_base_scan_range", 0) or 0.0) or default_range
    closest = (float(origin.data_set.get(LM_SCI_CLOSEST_DELAY_KEY, 0))
               if _written(origin, LM_SCI_CLOSEST_DELAY_KEY) else closest_default)
    farthest = (float(origin.data_set.get(LM_SCI_FARTHEST_DELAY_KEY, 0))
                if _written(origin, LM_SCI_FARTHEST_DELAY_KEY) else farthest_default)

    # Linear in distance, and NOT clamped at sensor range: a contact at twice the range
    # is twice as far along the line, so closing on something always buys time. The cap
    # is on the RESULT instead, which keeps a very distant contact slow rather than
    # unscannable without making every far contact cost the same.
    seconds = closest + (farthest - closest) * (dist / rng)
    seconds /= lm_sci_hull_scan_coeff(origin_id)
    seconds /= lm_sci_sensor_coeff(origin_id)

    # Never instant - an instant scan is not a decision, and the queue only reads as a
    # resource if the head takes long enough to see. Never hung, for the same reason a
    # distant contact is slow rather than unscannable.
    return max(fastest, min(slowest, seconds))
