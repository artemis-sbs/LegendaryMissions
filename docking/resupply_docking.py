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

RATE_SLOW = 5
RATE_FAST = 0

# The Resupply Tanker is used in the Deep Strike mission. It provides energy and one nuclear torpedo every 5 minutes. 
# In Artemis 2.x, the Resupply Tanker would give a +500 burst of energy and add a nuke to the player ship every 5 minutes.
# In Cosmos, we can code the Resupply Tanker so it functions like a station. To match the functionality of the previous version,
# some of the station operations have been removed, like resupplying all torpedo types, and faster shield/system repair.
# To provide something similar to the +500 energy boost, we've added a button to Comms to request a HiDens Power Cell every 5 mins.   

def player_docking_resupply_docked(player_id_or_obj, dock_station):
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
    #shieldCoeff = player_blob.get("repair_rate_shields",0)
    

    #sCount = player_blob.get("shield_count",0)
    #for shield in range(sCount):
    #    sVal = player_blob.get("shield_val", shield)
    #    sValMax = player_blob.get("shield_max_val", shield)
    #    changed = (sVal < sValMax)
    #    sVal = max(0.0, min(sVal + shieldCoeff, sValMax)) # clamp the value
    #    if changed:
    #        player_blob.set("shield_val", sVal, shield)

    #systemCoeff = player_blob.get("repair_rate_systems",0)
    #
    # Repair a system rooms first
    #
    #system_grid_objects = to_list(grid_objects(player_id) & role("__damaged__") & role("system"))
    #if len(system_grid_objects):
    #    grid_repair_grid_objects(player_id, system_grid_objects[0])
    #else:
        #
        # Repair hallways and non system rooms
        #
    #    non_system_grid_objects = to_list((grid_objects(player_id) & role("__damaged__") ) - role("system") -  role("lifeform"))
    #    if len(non_system_grid_objects):
    #        grid_repair_grid_objects(player_id, non_system_grid_objects[0])

    return RATE_FAST