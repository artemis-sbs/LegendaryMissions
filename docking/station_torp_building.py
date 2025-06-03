import sbs
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.execution import get_shared_variable, task_cancel, task_schedule
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value




__build_times = {
    "command": {"build_times": {"Homing": 2, "Nuke": 5, "EMP": 3, "Mine": 2}},
    "civil": {"build_times": {"Homing": 6, "Nuke": 20, "EMP": 10, "Mine": 8 }},
    "industry": {"build_times": {"Homing": 1, "Nuke": 4, "EMP": 2, "Mine": 2 }},
    "science": {"build_times": {"Homing": 6, "Nuke": 20, "EMP": 10, "Mine": 8}},
    "default": {"build_times": {"Homing": 3, "Nuke": 10, "EMP": 5, "Mine": 4}}
}


def get_build_times(id_or_obj):
    build_times = get_shared_variable("build_times", __build_times)
    if build_times is None:
        build_times = __build_times
    
    #   HOMING : 0, NUKE : 1, EMP : 2, MINE : 3
    so = to_object(id_or_obj)
    if so is not None:
        artid = so.art_id
        for k in build_times:
            if k in artid:
                return  build_times[k]["build_times"]

    return build_times["default"]["build_times"]

def get_build_time_for(id_or_obj, torp_type):
    bt = get_build_times(id_or_obj)
    return bt.get(torp_type, 1000) * 60


def build_munition_queue_task(id_or_obj, torp_type):
    build_task = get_inventory_value(id_or_obj, "build_task")
    build_type = get_inventory_value(id_or_obj, "build_type")

    if build_type == torp_type:
        return False

    set_inventory_value(id_or_obj, "build_type", torp_type)
    # if it is running stop it
    if build_task is not None:
        task_cancel(build_task)
    # Start the new work    
    build_time = get_build_time_for(id_or_obj, torp_type)
    set_inventory_value(id_or_obj, "build_task", task_schedule("task_station_building", 
        data={"station_id": to_id(id_or_obj), "build_time": build_time, "torpedo_build_type": torp_type}))
    return True

