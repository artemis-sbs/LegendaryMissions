import sbs
from sbs_utils.procedural.query import to_id, to_blob, object_exists, to_engine_object, to_list, inc_disable_weapons_selection, dec_disable_weapons_selection
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.space_objects import closest
from sbs_utils.procedural.grid import grid_objects
from sbs_utils.tickdispatcher import TickDispatcher
from internal_damage import grid_restore_damcons, grid_repair_grid_objects




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
    prev_dock_state_string = get_inventory_value(player_id, "dock_state")
    
    
    if "undocked" == dock_state_string:
        if prev_dock_state_string =="docked":
            dec_disable_weapons_selection(player_id)
        
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
        inc_disable_weapons_selection(player_id)
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

    # check to see if the player ship is close enough to be docked
    distanceValue = sbs.distance_id(dock_station_id, player_id)

    closeEnough = dock_station_so.exclusion_radius + player_so.exclusion_radius
    closeEnough = closeEnough * 1.1
    if distanceValue <= closeEnough:
        player_blob.set("dock_state", "dock_start")
    return RATE_FAST

def player_docking_dock_start(player_id_or_obj, dock_station):
    player_blob = to_blob(player_id_or_obj)
    player_id = to_id(player_id_or_obj)

    player_blob.set("dock_state", "docked")
    grid_restore_damcons(player_id)
    return RATE_FAST


def player_docking_docked(player_id_or_obj, dock_station):
    player_blob = to_blob(player_id_or_obj)
    dock_station_blob = to_blob(dock_station)
    player_id = to_id(player_id_or_obj)

    # refuel
    fuel_value = player_blob.get("energy",0)
    if fuel_value < 1000:
        fuel_value = fuel_value + 20
        player_blob.set("energy", int(fuel_value))


    # resupply torps
    for torps in range(sbs.TORPEDO.TORPTYPECOUNT):
        tLeft = dock_station_blob.get("torpedo_count", torps)
        if tLeft > 0:
            torp_max = player_blob.get("torpedo_max", torps)
            torp_now = player_blob.get("torpedo_count", torps)
            if torp_now < torp_max:
                torp_now = torp_now + 1
                player_blob.set("torpedo_count", torp_now,torps)
                dock_station_blob.set("torpedo_count", tLeft-1, torps)


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