"""How long a scan takes - the engine's own rule, measured.

Split out of `science_queue` because it is the part worth reading on its own.

MEASURED ON ENGINE 1.3.15 (2026-10-13, `data/missions/_e1315_probe case=scantime`: a real
client pressing Start Scan on stationary targets at thirteen ranges from 400 to 140,000,
the scanning ship's `cur_scan_percent` sampled every tick):

    seconds = closest_scan_delay
              + (farthest_scan_delay - closest_scan_delay) * min(distance, reach) / reach
    reach   = min(ship_science_scan_range, 100000)

So a scan never takes longer than `farthest_scan_delay`: 100,000 and 140,000 both took
19.8s. Before that was measured this file let the line run on past `reach`, and a far-off
enemy took up to three times as long here as on the stock console.

* The engine WRITES the two delays on a player ship, 0.3 and 20.0; changing them changed
  the times exactly as the line says.
* `ship_science_scan_range` is 150000 x (1 + Engineering's SENSORS slider) / 2 x
  `sensor_upgrade_coeff` x `sensor_damage_coeff`, each factor measured alone: slider 0.5
  gave 112500 and 3.0 gave 300000; upgrade 0.5 and damage 0.5 each gave 75000.
  **The engine only publishes it while ITS OWN scan runs** - this console runs the queue
  itself, so it usually has to build the number from those same four parts.
* `ship_base_scan_range` is NOT in it: 5000 and 20000 gave identical times. The first
  version of this file divided by it, which is why a scan here took several times as
  long as the stock console's - 20s at 5,000 against the engine's 1.3s.
* `scan_strength_coeff` is NOT in it either: a hull at 2.0 timed the same as one at 1.0.
* Sensors matter only through `reach`, and only once it drops below the 100000 cap: a
  slider under about a third, an upgrade or damage factor under two thirds. More power
  than that scans no faster - slider 0.5 and 3.0 both timed exactly as 1.0.
* The engine advances a scan in half-second steps, so nothing lands in under 0.5s.

LM_SCI_SCAN_SLOWEST is OUR guard against a mission writing absurd delays, not a limit
the engine has.

Prefixed `lm_sci_` because every top-level function here becomes a MAST global in one
flat, mission-wide namespace. A leading underscore is private to this file.
"""
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.query import to_object, to_id

#: Engineering's live sensor efficiency. Only read when the engine has not published
#: `ship_science_scan_range`, which already has it folded in.
LM_SCI_SENSOR_COEFF_KEY = "sensor_damage_coeff"

#: Wrecked sensors should HURT, not stop the console dead: a scan that can never finish
#: reads as a bug rather than as damage.
LM_SCI_SENSOR_COEFF_MIN = 0.25

#: The engine's own scan fields on the scanning ship.
LM_SCI_CLOSEST_DELAY_KEY = "closest_scan_delay"
LM_SCI_FARTHEST_DELAY_KEY = "farthest_scan_delay"
LM_SCI_SCIENCE_RANGE_KEY = "ship_science_scan_range"

#: `ship_science_scan_range` on a ship with undamaged sensors, as the engine wrote it.
LM_SCI_SCIENCE_RANGE = 150000.0

#: The engine's SENSORS power slider, as Engineering's own table names it.
LM_SCI_SENSOR_SLIDER_LABEL = "sens"

#: The engine's cap on the range a scan is measured against.
LM_SCI_REACH_CAP = 100000.0


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


def lm_sci_sensor_slider(ship_id):
    """Engineering's SENSORS power slider (1.0 = normal), or 1.0 when there is none.

    Found by LABEL, the way Engineering's own table is read: the row order is the
    engine's, and a hull with a different set of controls must not have the wrong
    slider read as sensors.
    """
    ship = to_object(ship_id)
    if ship is None:
        return 1.0
    ds = ship.data_set
    for i in range(16):
        label = ds.get("eng_control_label", i)
        if not label:
            break
        if LM_SCI_SENSOR_SLIDER_LABEL in str(label).lower():
            value = ds.get("eng_control_value", i)
            return 1.0 if value is None else max(0.0, float(value))
    return 1.0


def lm_sci_scan_reach(ship_id):
    """The range a scan is measured against: the engine's science range, capped.

    The engine publishes `ship_science_scan_range` only while its own scan runs, and this
    console runs the queue itself - so usually it is rebuilt here, the way the engine was
    measured to build it: 150000 x (1 + sensor slider) / 2 x upgrade x damage.
    """
    ship = to_object(ship_id)
    if _written(ship, LM_SCI_SCIENCE_RANGE_KEY):
        reach = float(ship.data_set.get(LM_SCI_SCIENCE_RANGE_KEY, 0))
    else:
        reach = (LM_SCI_SCIENCE_RANGE
                 * (1.0 + lm_sci_sensor_slider(ship_id)) / 2.0
                 * _coeff(ship, "sensor_upgrade_coeff")
                 * lm_sci_sensor_coeff(ship_id))
    # A slider at zero with wrecked sensors is still slow, never a division by zero.
    return max(1.0, min(reach, LM_SCI_REACH_CAP))


def lm_sci_scan_time_compute(origin_id, target_id, closest_default, farthest_default,
                        fastest, slowest):
    """Seconds for `origin` to scan `target`. None when it cannot be worked out.

    NOT named `lm_sci_scan_seconds`: every top-level function in an addon `.py` becomes a
    MAST global in ONE flat, mission-wide namespace, assigned unconditionally with no
    warning - so two files defining that name collide, last loaded wins, and the caller
    gets whichever signature it did not expect. `science_queue` owns the short name; this
    is the computation behind it.

    The stand-in numbers come from `science_queue`, which owns them; this module owns the
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

    closest = (float(origin.data_set.get(LM_SCI_CLOSEST_DELAY_KEY, 0))
               if _written(origin, LM_SCI_CLOSEST_DELAY_KEY) else closest_default)
    farthest = (float(origin.data_set.get(LM_SCI_FARTHEST_DELAY_KEY, 0))
                if _written(origin, LM_SCI_FARTHEST_DELAY_KEY) else farthest_default)

    # Linear in distance up to the reach, and flat beyond it - measured out to 140,000.
    reach = lm_sci_scan_reach(origin_id)
    seconds = closest + (farthest - closest) * (min(dist, reach) / reach)

    # The floor is the engine's own step. The ceiling is ours: a very distant contact is
    # slow rather than unscannable, because a scan that cannot finish reads as a bug.
    return max(fastest, min(slowest, seconds))
