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
from sbs_utils.procedural.inventory import set_inventory_value


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
    obj = terrain_spawn(x, y, z, name, f"#,item,{key}", art, "behav_pickup")
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
