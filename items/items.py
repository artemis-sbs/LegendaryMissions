"""Item/upgrade registry for the discoverable item system.

Items are ordinary prefab labels tagged with `metadata: type: item/...` (no new
syntax - same pattern as the other prefabs). They are discovered with
`labels_get_type("item/")`, exactly like maps/media. This module is the single
source of truth the spawner, collector, GUI, and market all read from.
"""
import random
from sbs_utils import scatter
from sbs_utils.vec import Vec3
from sbs_utils.procedural.execution import labels_get_type
from sbs_utils.procedural.spawn import terrain_spawn
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.sides import to_side_id
from sbs_utils.procedural.signal import signal_emit


def items_get_list():
    """Return all registered item labels (metadata ``type: item/...``)."""
    return labels_get_type("item/")


def item_get(key):
    """Return the item label whose metadata ``key`` matches, or ``None``."""
    for lbl in labels_get_type("item/"):
        if lbl.get_inventory_value("key") == key:
            return lbl
    return None


def item_meta(item, field, default=None):
    """Read a metadata field from an item (a label object or a key string)."""
    lbl = item if not isinstance(item, str) else item_get(item)
    if lbl is None:
        return default
    return lbl.get_inventory_value(field, default)


def item_keys():
    """Return the list of all registered item keys."""
    return [lbl.get_inventory_value("key") for lbl in labels_get_type("item/")]


def items_of_category(category):
    """Return item labels whose ``type`` contains the given category segment.

    e.g. ``items_of_category("upgrade")`` or ``items_of_category("resource")``.
    """
    ret = []
    for lbl in labels_get_type("item/"):
        t = lbl.get_inventory_value("type", "")
        if category in t.split("/"):
            ret.append(lbl)
    return ret


# --- Spawning (registry-driven; replaces the legacy hardcoded chain) ---------
def item_spawn(key, x, y, z, name=None, blink=None, yaw=None):
    """Spawn a collectible pickup for an item ``key`` at ``(x, y, z)``.

    Art comes from the registry; the key is stored on the pickup as the
    ``item_key`` inventory value so the generic collision route can credit it
    without any per-item code.
    """
    art = item_meta(key, "art", "unknown")
    if name is None:
        name = item_meta(key, "display_text", key)
    if blink is None:
        blink = random.randint(1, 2)
    if yaw is None:
        yaw = random.uniform(0.03, 0.08)
    # Roles: "item" (new generic collection) + "upgrade" and the key (legacy
    # role checks, e.g. science scans, still match).
    obj = terrain_spawn(x, y, z, name, f"#,item,upgrade,{key}", art, "behav_pickup")
    obj.engine_object.steer_yaw = yaw
    obj.engine_object.blink_state = int(blink)
    set_inventory_value(obj.id, "item_key", key)
    return obj


def _item_spawn_pool(categories):
    """(keys, weights) eligible to spawn in space, weighted by 1/tier."""
    keys = []
    weights = []
    for lbl in labels_get_type("item/"):
        cats = lbl.get_inventory_value("type", "").split("/")
        if categories and not any(c in cats for c in categories):
            continue
        k = lbl.get_inventory_value("key")
        if not k:
            continue
        tier = lbl.get_inventory_value("tier", 1) or 1
        keys.append(k)
        weights.append(1.0 / max(1, int(tier)))
    return keys, weights


def terrain_spawn_items(density, center=None, points=None, categories=None):
    """Scatter tier-weighted item pickups (default categories: upgrade+resource).

    ``density`` 1-4 controls how many spawn. If ``points`` is given they are
    sampled; otherwise a box scatter around ``center`` is used.
    """
    if center is None:
        center = Vec3(0, 0, 0)
    if categories is None:
        categories = ["upgrade", "resource"]
    keys, weights = _item_spawn_pool(categories)
    if not keys:
        return
    ranges = {1: (1, 3), 2: (3, 5), 3: (5, 10), 4: (10, 15)}
    lo, hi = ranges.get(int(density), (0, 0))
    num = random.randint(lo, hi) if hi else 0
    if num <= 0:
        return
    if points is not None:
        pts = list(points)
        spawn_points = random.sample(pts, num) if len(pts) >= num else pts
    else:
        spawn_points = scatter.box(num, center.x, center.y, center.z, 75000, 1000, 75000, centered=True)
    for v in spawn_points:
        key = random.choices(keys, weights=weights)[0]
        item_spawn(key, v.x, v.y, v.z)


# --- Backward-compat shims (old upgrades API -> registry) --------------------
def pickup_spawn(x, y, z, roles, blink=None, yaw=None, name=None, art_id=None):
    """Legacy shim: the old ``roles`` arg carried the upgrade key."""
    key = roles.split(",")[0].strip() if roles else ""
    return item_spawn(key, x, y, z, name=name, blink=blink, yaw=yaw)


def terrain_spawn_pickups(upgrade_value, center=None, points=None):
    """Legacy shim onto the registry-driven spawner."""
    terrain_spawn_items(upgrade_value, center=center, points=points,
                        categories=["upgrade", "resource"])


# --- Market / economy --------------------------------------------------------
# Credits are a shared per-side pool. Station stock lives on the station agent
# (stock_<key>); a station is "seeded" finite, or treated as unlimited if not.
MARKET_SELL_FACTOR = 0.5


def market_purchasable():
    """Item labels with a positive price (buyable/sellable)."""
    ret = []
    for lbl in labels_get_type("item/"):
        if (lbl.get_inventory_value("price", 0) or 0) > 0:
            ret.append(lbl)
    return ret


def market_is_seeded(station_id):
    return get_inventory_value(station_id, "market_seeded", 0) == 1


def market_stock(station_id, key):
    """Units of `key` a station has; a large number when not finite-seeded."""
    if not market_is_seeded(station_id):
        return 9999
    return get_inventory_value(station_id, "stock_" + key, 0)


def _disposition_for(seed_key, idx):
    """Per-(sector, item) price multiplier in [0.5, 1.5): low = producer
    (cheap, well-stocked), high = consumer (dear, wants it). Deterministic."""
    return 0.5 + random.Random(scatter._mix(int(seed_key), idx + 1000)).random()


def _purchasable_index(key):
    for i, lbl in enumerate(market_purchasable()):
        if lbl.get_inventory_value("key") == key:
            return i
    return None


def market_disposition(station_id, key):
    """Station's price disposition for an item (1.0 if not finite-seeded)."""
    seed_key = get_inventory_value(station_id, "market_seed_key", None)
    if seed_key is None:
        return 1.0
    idx = _purchasable_index(key)
    return 1.0 if idx is None else _disposition_for(int(seed_key), idx)


def market_price(station_id, key):
    """Current buy price = base price x the station's disposition."""
    lbl = item_get(key)
    base = (lbl.get_inventory_value("price", 0) or 0) if lbl is not None else 0
    return int(round(base * market_disposition(station_id, key)))


def market_sell_price(station_id, key):
    """What a station pays to buy an item from the player."""
    return int(market_price(station_id, key) * MARKET_SELL_FACTOR)


def market_seed(station_id, seed_key):
    """Deterministically stock a station's market (finite), keyed by seed_key.

    Same seed_key (e.g. a sector key) reproduces the same stock and prices.
    Producers (low disposition) are well-stocked; consumers (high) near-empty.
    """
    set_inventory_value(station_id, "market_seed_key", int(seed_key))
    for i, lbl in enumerate(market_purchasable()):
        k = lbl.get_inventory_value("key")
        disp = _disposition_for(int(seed_key), i)
        qty = max(0, round((1.6 - disp) * 4))
        set_inventory_value(station_id, "stock_" + k, qty)
    set_inventory_value(station_id, "market_seeded", 1)


def market_snapshot(station_id):
    """Current stock as {key: qty} (for persistence)."""
    snap = {}
    for lbl in market_purchasable():
        k = lbl.get_inventory_value("key")
        snap[k] = get_inventory_value(station_id, "stock_" + k, 0)
    return snap


def market_restore(station_id, snapshot):
    """Apply a saved stock snapshot to a station (marks it finite-seeded)."""
    if not isinstance(snapshot, dict):
        return
    for k, qty in snapshot.items():
        set_inventory_value(station_id, "stock_" + k, qty)
    set_inventory_value(station_id, "market_seeded", 1)


def _ship_side_id(ship_id):
    ship = to_object(ship_id)
    return to_side_id(ship.side) if ship is not None and ship.side else None


def market_buy(ship_id, station_id, key):
    """Buy one `key` for the ship from the station, paying side credits."""
    if item_get(key) is None:
        return False
    price = market_price(station_id, key)
    sid = _ship_side_id(ship_id)
    if sid is None or price <= 0:
        return False
    credits = get_inventory_value(sid, "credits", 0)
    if credits < price or market_stock(station_id, key) <= 0:
        return False
    set_inventory_value(sid, "credits", credits - price)
    set_inventory_value(ship_id, key, get_inventory_value(ship_id, key, 0) + 1)
    if market_is_seeded(station_id):
        set_inventory_value(station_id, "stock_" + key,
                            get_inventory_value(station_id, "stock_" + key, 0) - 1)
    signal_emit("item_bought", {"holder_id": ship_id, "station_id": station_id, "key": key})
    signal_emit("item_changed", {"holder_id": ship_id})
    return True


def market_sell(ship_id, station_id, key):
    """Sell one `key` from the ship to the station for side credits."""
    lbl = item_get(key)
    if lbl is None:
        return False
    owned = get_inventory_value(ship_id, key, 0)
    if owned <= 0:
        return False
    sid = _ship_side_id(ship_id)
    if sid is None:
        return False
    payout = market_sell_price(station_id, key)
    set_inventory_value(sid, "credits", get_inventory_value(sid, "credits", 0) + payout)
    set_inventory_value(ship_id, key, owned - 1)
    if market_is_seeded(station_id):
        set_inventory_value(station_id, "stock_" + key,
                            get_inventory_value(station_id, "stock_" + key, 0) + 1)
    signal_emit("item_sold", {"holder_id": ship_id, "station_id": station_id, "key": key})
    signal_emit("item_changed", {"holder_id": ship_id})
    return True
