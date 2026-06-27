"""Item/upgrade registry for the discoverable item system.

Items are ordinary prefab labels tagged with `metadata: type: item/...` (no new
syntax - same pattern as the other prefabs). They are discovered with
`labels_get_type("item/")`, exactly like maps/media. This module is the single
source of truth the spawner, collector, GUI, and market all read from.
"""
from sbs_utils.procedural.execution import labels_get_type


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
