from sbs_utils.procedural.roles import role
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.execution import task_cancel, task_schedule
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.torpedoes import torpedo_get_available_types_for_ship



# I'll leave this here for now, but this information now goes in the torpedo prefabs.
__build_times = {
    "command": {"build_times": {"Homing": 2, "Nuke": 5, "EMP": 3, "Mine": 2, "PShock": 5, "Tag": 1}},
    "civil": {"build_times": {"Homing": 6, "Nuke": 20, "EMP": 10, "Mine": 8, "PShock": 20, "Tag": 2}},
    "industry": {"build_times": {"Homing": 1, "Nuke": 4, "EMP": 2, "Mine": 2, "PShock": 4, "Tag": 1}},
    "science": {"build_times": {"Homing": 6, "Nuke": 20, "EMP": 10, "Mine": 8, "PShock": 20, "Tag": 2}},
    "default": {"build_times": {"Homing": 3, "Nuke": 10, "EMP": 5, "Mine": 4, "PShock": 10, "Tag": 1}}
}

#TODO Should these functions be moved to sbs_utils?
def docking_get_torp_build_times(key):
    """
    Get the time it takes to build the torpedo with the given key at stations.
    Args:
        key (str): The key of the torpedo type
    Returns:
        dict: A dictionary with station types as the keys (e.g. command) and the time to build as the value.
    """
    torps = role(key) & role("torpedo_definition")
    torp = torps.pop() # Should only be one
    return get_inventory_value(torp, "build_times")

def docking_get_build_time_for(id_or_obj, torp_type):
    # times = docking_get_torp_build_times(torp_type)
    so = to_object(id_or_obj)
    if so is not None:
        time = get_inventory_value(so, f"{torp_type}_BUILD_SPEED", 1000)
        return time
    return 1000


def docking_build_munition_queue_task(id_or_obj, torp_type):
    build_task = get_inventory_value(id_or_obj, "build_task")
    build_type = get_inventory_value(id_or_obj, "build_type")

    if build_type == torp_type:
        return False

    set_inventory_value(id_or_obj, "build_type", torp_type)
    # if it is running stop it
    if build_task is not None:
        task_cancel(build_task)
    # Start the new work    
    build_time = docking_get_build_time_for(id_or_obj, torp_type)*60
    set_inventory_value(id_or_obj, "build_task", task_schedule("task_station_building", 
        data={"station_id": to_id(id_or_obj), "build_time": build_time, "torpedo_build_type": torp_type}))
    return True


def docking_order_torpedo_keys(reference_id_or_obj, keys):
    """Order torpedo keys the way the engine orders them for a given ship.

    The authority is the ship's own ``torpedo_types_available`` data_set value, which
    the engine fills from its shipData ``torpedostart`` list - the same source and the
    same order the ship-data widget renders. Ordering a menu by it is what makes the
    menu agree with the widget (LegendaryMissions#693).

    Anything the reference ship does not carry - Beacon, or every type but Homing when
    the reference is a fighter - has no engine opinion to follow, so it falls to the
    tail ordered by the definition's ``sort_order``, then by key. That keeps the tail
    stable instead of handing it back in set order.

    Do NOT pass a station as the reference. Stations have no ``torpedostart`` in
    shipData, so the engine answers None for them - while the mock answers with its
    own default ("Homing,Nuke,EMP,Mine"), which would look correct in a headless run
    and silently reorder on a real bridge.

    Args:
        reference_id_or_obj (Agent | int): The PLAYER ship whose order to follow,
            normally the console asking for the menu.
        keys (list[str]): Torpedo type keys to order.

    Returns:
        list[str]: The keys, ordered.
    """
    if not keys:
        return list(keys or [])
    engine_order = torpedo_get_available_types_for_ship(reference_id_or_obj) or []
    rank = {key: i for i, key in enumerate(engine_order)}
    tail = len(rank)
    return sorted(keys, key=lambda k: (rank.get(k, tail), _docking_torp_sort_order(k), k))


def _docking_torp_sort_order(key):
    """The sort_order the torpedo prefab declared, or 100 if it declared none."""
    torps = role(key) & role("torpedo_definition")
    if not torps:
        return 100
    order = get_inventory_value(next(iter(torps)), "sort_order", 100)
    return 100 if order is None else order
