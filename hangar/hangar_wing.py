"""A station's AI WING - the fighters it launches when a bridge orders it to.

The hangar's own craft cannot do this: they are player ships (player_spawn,
behav_playership), there for a pilot to climb into, and the engine only steers an NPC
brain's `target_pos` on a behav_npcship. So a wing is a separate thing - a COUNT of AI
fighters a station or carrier holds, spawned as NPC ships when it launches and removed
again when they come home. The hangar's player craft are never touched.

    ready   craft in the bay (starts at the wing size)
    out     live fighters flying for this host
    lost    neither - a fighter destroyed out there simply never comes back

Wing size: a mission's `hangar_wing_size` inventory override, else the HANGAR_WING_SIZE
setting for a station, else a carrier's `baycount` (capped by the same setting), else 0.

Supplies the `launch` capability to sbs_utils procedural/orders.py, which is what puts
Launch / Recall on the comms order menu of anything that has a wing.

Every function is prefixed `hangar_wing_` - one flat MAST namespace.
"""
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_id, to_object, object_exists
from sbs_utils.procedural.roles import has_role, role
from sbs_utils.procedural.ship_data import get_ship_data_for
from sbs_utils.procedural.spawn import npc_spawn

#: Role every wing fighter carries.
HANGAR_WING_ROLE = "hangar_wing"

#: Wing size when neither the mission nor the setting says otherwise.
HANGAR_WING_DEFAULT_SIZE = 4

#: Hull when the host's side has no fighter of its own.
HANGAR_WING_FALLBACK_HULL = "tsn_fighter"

#: How close a returning fighter must be to land.
HANGAR_WING_DOCK_DISTANCE = 800

_READY = "hangar_wing_ready"
_SIZE = "hangar_wing_size"
_HOME = "hangar_wing_home"


def _hangar_wing_setting():
    try:
        from sbs_utils.procedural.settings import settings_get_defaults
        v = settings_get_defaults().get("HANGAR_WING_SIZE", HANGAR_WING_DEFAULT_SIZE)
        return max(0, int(v))
    except Exception:                                   # noqa: BLE001
        return HANGAR_WING_DEFAULT_SIZE


def hangar_wing_size(host):
    """How many AI fighters `host` holds when full."""
    hid = to_id(host)
    so = to_object(hid)
    if so is None:
        return 0
    override = get_inventory_value(hid, _SIZE, None)
    if override is not None:
        return max(0, int(override))
    cap = _hangar_wing_setting()
    if has_role(hid, "station"):
        return cap
    entry = get_ship_data_for(getattr(so, "_ship_data_key", None)) or {}
    bays = entry.get("baycount") or 0
    return min(int(bays), cap) if bays else 0


def hangar_wing_set_size(host, size):
    """Give a host a wing of `size` (0 removes it) and fill its bay."""
    hid = to_id(host)
    if hid is None:
        return 0
    set_inventory_value(hid, _SIZE, max(0, int(size)))
    set_inventory_value(hid, _READY, max(0, int(size)))
    return int(size)


def hangar_wing_ready(host):
    """Fighters in the bay, ready to launch. Starts full."""
    hid = to_id(host)
    if hid is None:
        return 0
    ready = get_inventory_value(hid, _READY, None)
    if ready is None:
        ready = hangar_wing_size(hid)
        set_inventory_value(hid, _READY, ready)
    return ready


def hangar_wing_out(host):
    """Ids of the live fighters flying for `host`."""
    hid = to_id(host)
    if hid is None:
        return []
    return sorted(f for f in role(HANGAR_WING_ROLE)
                  if object_exists(f) and get_inventory_value(f, _HOME, None) == hid)


def hangar_wing_home(fighter):
    """The host a wing fighter belongs to, or None."""
    fid = to_id(fighter)
    return get_inventory_value(fid, _HOME, None) if fid else None


def hangar_wing_hull(host):
    """The fighter hull for `host`'s side, or the fallback."""
    from sbs_utils.procedural.ship_data import filter_ship_data_by_side
    so = to_object(host)
    side = getattr(so, "side", None) if so is not None else None
    try:
        keys = filter_ship_data_by_side(None, side, "fighter", ret_key_only=True) or []
    except Exception:                                   # noqa: BLE001
        keys = []
    # Prefer a real fighter over a bomber; either way the first of the side's own.
    fighters = [k for k in keys if "bomber" not in k]
    return (fighters or keys or [HANGAR_WING_FALLBACK_HULL])[0]


def hangar_wing_launch(host, count=None):
    """Launch up to `count` ready fighters (all of them by default). Returns their ids -
    the caller gives them their orders. [] when the bay is empty."""
    hid = to_id(host)
    so = to_object(hid)
    if so is None:
        return []
    ready = hangar_wing_ready(hid)
    n = ready if count is None else min(int(count), ready)
    if n <= 0:
        return []
    side = getattr(so, "side", None) or "tsn"
    hull = hangar_wing_hull(hid)
    pos = so.pos
    ids = []
    for i in range(n):
        # Fanned out around the host so they do not spawn inside each other.
        off = (i - (n - 1) / 2.0) * 150
        name = f"{so.name} Wing {i + 1}"
        fid = to_id(npc_spawn(pos.x + off, pos.y, pos.z + 300, name,
                              f"{side},fighter,{HANGAR_WING_ROLE}", hull, "behav_npcship"))
        if fid is None:
            continue
        set_inventory_value(fid, _HOME, hid)
        ids.append(fid)
    set_inventory_value(hid, _READY, ready - len(ids))
    return ids


def hangar_wing_land(fighter):
    """Land a returning fighter if it is close enough to home: it leaves the map and goes
    back in the bay. Returns True when it landed. A fighter whose home is gone stays out."""
    from sbs_utils.procedural.space_objects import delete_object
    import sbs
    fid = to_id(fighter)
    hid = hangar_wing_home(fid)
    if not fid or not hid or not object_exists(fid) or not object_exists(hid):
        return False
    if sbs.distance_id(fid, hid) > HANGAR_WING_DOCK_DISTANCE:
        return False
    delete_object(fid)
    set_inventory_value(hid, _READY, min(hangar_wing_size(hid), hangar_wing_ready(hid) + 1))
    return True


def hangar_wing_caps(object_id):
    """The orders-capability provider: `launch` for anything with a wing in the bay or
    out flying (Recall needs the second)."""
    if hangar_wing_size(object_id) <= 0 and not hangar_wing_out(object_id):
        return []
    if hangar_wing_ready(object_id) > 0 or hangar_wing_out(object_id):
        return ["launch"]
    return []


try:
    from sbs_utils.procedural.orders import orders_caps_provider
    orders_caps_provider(hangar_wing_caps)
except ImportError:                                     # an sbslib without orders
    pass
