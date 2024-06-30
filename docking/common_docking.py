import sbs
from sbs_utils.procedural.query import to_id, to_object, to_blob, object_exists, to_engine_object, to_list, set_weapons_selection
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.comms import comms_message
from sbs_utils.procedural.execution import get_shared_variable, task_cancel, task_schedule
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.timers import is_timer_finished, set_timer
from sbs_utils.procedural.space_objects import closest
from sbs_utils.procedural.grid import grid_objects
from sbs_utils.tickdispatcher import TickDispatcher
from damage.internal_damage import grid_restore_damcons, grid_repair_grid_objects
from sbs_utils.faces import get_face
from sbs_utils.procedural.signal import signal_emit




__build_times = {
    "command": {"build_times": {"Homing": 2, "Nuke": 5, "EMP": 3, "Mine": 2}},
    "civil": {"build_times": {"Homing": 6, "Nuke": 20, "EMP": 10, "Mine": 8 }},
    "industry": {"build_times": {"Homing": 1, "Nuke": 4, "EMP": 2, "Mine": 2 }},
    "science": {"build_times": {"Homing": 6, "Nuke": 20, "EMP": 10, "Mine": 8}},
    "default": {"build_times": {"Homing": 3, "Nuke": 10, "EMP": 5, "Mine": 4}}
}

sbs.set_shared_string("Homing","gui_text:Homing;  speed:10; lifetime:25; flare_color:white; trail_color:white;warhead:standard;damage:35; explosion_size:10;explosion_color:fire; behavior:homing; energy_conversion_value:100")
sbs.set_shared_string("Nuke"  ,"gui_text:Nuke  ;  speed:10; lifetime:25; flare_color:white; trail_color:#99f;warhead:blast; blast_radius:1000; damage:5; explosion_size:20;explosion_color:fire; behavior:homing; energy_conversion_value:200")
sbs.set_shared_string("EMP"   , "gui_text:EMP  ;  speed:10; lifetime:25; flare_color:yellow; trail_color:#99f;warhead:blast,reduce_shields; blast_radius:1000; damage:50; explosion_size:20;explosion_color:#11F; behavior:homing; energy_conversion_value:50")
sbs.set_shared_string("Mine"  , "gui_text:Mine ;  speed:10; lifetime:25; flare_color:white; trail_color:white; warhead:blast; blast_radius:1000; damage:5; explosion_size:20; explosion_color:fire; behavior:mine; energy_conversion_value:200")


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



def schedule_player_docking(player_id_or_obj, difficulty):
    #
    # Schedule a simple tick task 
    # Pass the player ID to the task
    #
    t = TickDispatcher.do_interval(player_docking_task, 5)
    t.set_inventory_value("player_id", to_id(player_id_or_obj))
    t.set_inventory_value("difficulty", difficulty)
    

RATE_SLOW = 5
RATE_FAST = 0

def player_docking_task(t):
    player_id = t.get_inventory_value("player_id")
    difficulty = t.get_inventory_value("difficulty")
    rate = player_docking(player_id, difficulty)
    if rate is None:
        t.stop()
    else:
        t.delay = rate



def player_docking(player_id_or_obj, difficulty, docking_range=600, docked_cb=None, docking_cb=None, dock_start_cb=None):
    if not object_exists(player_id_or_obj):
        # Ship is destroyed
        return None
    
    player_id = to_id(player_id_or_obj)
    player_blob = to_blob(player_id_or_obj)


    dock_state_string = player_blob.get("dock_state", 0)

    if "undocked" == dock_state_string:
        player_blob.set("dock_base_id", 0)
        _too_close = 300+(difficulty+1)*200
        raider = closest(player_id_or_obj, role("raider"), _too_close)
        if raider is None:
            station = closest(player_id_or_obj, role("Station"), docking_range)
            if station is not None:
                player_blob.set("dock_base_id", to_id(station))
    #
    # 
    #
    set_inventory_value(player_id, "dock_state", dock_state_string)

    dock_stationID = player_blob.get("dock_base_id", 0)

    if dock_stationID is None:
        return RATE_SLOW
    
    if "docking" == dock_state_string:
        rate = player_docking_docking(player_id, dock_stationID)
        if docked_cb is not None:
            docking_cb(player_id)
        return rate
    
    if "dock_start" == dock_state_string:
        rate = player_docking_dock_start(player_id, dock_stationID)
        set_weapons_selection(player_id, 0)
        if dock_start_cb is not None:
            dock_start_cb(player_id)
        return rate
    

    if "docked" == dock_state_string:
        rate = player_docking_docked(player_id, dock_stationID)
        if docked_cb is not None:
            docked_cb(player_id)
        return rate
    
    return RATE_SLOW

def player_docking_docking(player_id_or_obj, dock_station):
    player_blob = to_blob(player_id_or_obj)
    player_id = to_id(player_id_or_obj)
    player_so = to_engine_object(player_id_or_obj)
    dock_station_id = to_id(dock_station)
    dock_station_so = to_engine_object(dock_station_id)

    if player_so is None:
        return None # Player ship died stop running
    
    if dock_station_so is None:
        # Station died
        player_blob.set("dock_state", "undocked")
        return RATE_SLOW

    

    # check to see if the player ship is close enough to be docked
    distanceValue = sbs.distance_id(dock_station_id, player_id)

    closeEnough = dock_station_so.exclusion_radius + player_so.exclusion_radius
    closeEnough = closeEnough * 1.1
    if distanceValue <= closeEnough:
        player_blob.set("dock_state", "dock_start")
    return RATE_FAST

def player_docking_dock_start(player_id_or_obj, dock_station_id):
    player_blob = to_blob(player_id_or_obj)
    player_id = to_id(player_id_or_obj)
    if player_blob is None:
        return None # Player died

    player_blob.set("dock_state", "docked")
    #TODO: move this out and respond to signal
    grid_restore_damcons(player_id)
    # A hack to get attributes
    data = {}
    data["ORIGIN_ID"] = player_id
    data["SELECTED_ID"] = dock_station_id
    signal_emit("docked", data)
    
    return RATE_FAST


def player_docking_docked(player_id_or_obj, dock_station):
    player_blob = to_blob(player_id_or_obj)
    dock_station_blob = to_blob(dock_station)
    dock_station_id = to_id(dock_station)
    player_id = to_id(player_id_or_obj)

    if player_blob is None:
        return None # Player ship died stop running
    
    if dock_station_blob is None:
        # Station died
        player_blob.set("dock_state", "undocked")
        return RATE_SLOW


    refuel_amount = 20
    load_torp = is_timer_finished(player_id,"priority_docking_torp")
    if not is_timer_finished(player_id,"priority_docking"):
        refuel_amount+=20
        set_timer(player_id,"priority_docking", 2)
        if load_torp:
            set_timer(player_id,"priority_docking_torp", 2)
    else:
        if load_torp:
            set_timer(player_id,"priority_docking_torp", 6)
    
        
    throttle = player_blob.get("playerThrottle",0)
    if throttle >1.0:
        player_blob.set("playerThrottle",0.5, 0)
        comms_message("Attempting to warp while docked can hurt our systems.", dock_station_id, player_id,  "GEEZ! YOU'RE STILL DOCKED", None, "white", "red")
        return RATE_SLOW



    # refuel
    fuel_value = player_blob.get("energy",0)
    if fuel_value < 1000:
        fuel_value = fuel_value + refuel_amount
        player_blob.set("energy", int(fuel_value))


    # resupply torps
    if load_torp:
        _torp_types = player_blob.get("torpedo_types_available",0)
        _torp_types =  [x.strip() for x in _torp_types.split(',')]
        for torps in _torp_types:
            tLeft = dock_station_blob.get(f"{torps}_NUM", 0)
            if tLeft is not None and tLeft > 0:
                torp_max = player_blob.get(f"{torps}_MAX", 0)
                if torp_max is None:
                    torp_max = 10
                torp_now = player_blob.get(f"{torps}_NUM", 0)
                if torp_now < torp_max:
                    torp_now = torp_now + 1
                    player_blob.set(f"{torps}_NUM", torp_now,0)
                    dock_station_blob.set(f"{torps}_NUM", tLeft-1, 0)



    #repair shields (more than normal)
    shieldCoeff = player_blob.get("repair_rate_shields",0)
    

    sCount = player_blob.get("shield_count",0)
    for shield in range(sCount):
        sVal = player_blob.get("shield_val", shield)
        sValMax = player_blob.get("shield_max_val", shield)
        changed = (sVal < sValMax)
        sVal = max(0.0, min(sVal + shieldCoeff, sValMax)) # clamp the value
        if changed:
            player_blob.set("shield_val", sVal, shield)

    systemCoeff = player_blob.get("repair_rate_systems",0)
    #
    # Repair a system rooms first
    #
    system_grid_objects = to_list(grid_objects(player_id) & role("__damaged__") & role("system"))
    if len(system_grid_objects):
        grid_repair_grid_objects(player_id, system_grid_objects[0])
    else:
        #
        # Repair hallways and non system rooms
        #
        non_system_grid_objects = to_list((grid_objects(player_id) & role("__damaged__") ) - role("system") -  role("lifeform"))
        if len(non_system_grid_objects):
            grid_repair_grid_objects(player_id, non_system_grid_objects[0])



    return RATE_FAST