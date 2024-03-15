from sbs_utils.fs import load_json_data, get_mission_dir_filename
from random import randint
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.procedural.query import set_science_selection, to_object, to_id, object_exists, set_data_set_value
from sbs_utils.procedural.links import link, unlink, get_dedicated_link, set_dedicated_link, linked_to
from sbs_utils.procedural.roles import has_role, remove_role, any_role, role
from sbs_utils.procedural.space_objects import broad_test_around, closest, get_pos, set_pos
from sbs_utils.procedural.routes import RouteDestroy
from sbs_utils.procedural.timers import is_timer_set, set_timer, is_timer_finished
from sbs_utils.procedural.execution import set_shared_variable, get_shared_variable, get_variable
from sbs_utils.agent import Agent

from internal_damage import grid_rebuild_grid_objects
import sbs

_craft_id = 1

def hangar_bump_version():
    hangar_version = get_shared_variable("hangar_version", 0)
    set_shared_variable("hangar_version", hangar_version+1)

@RouteDestroy
def hagar_handle_destroy():
    so = to_object(get_variable("DESTROYED_ID"))
    if so is None:
        return
    #
    # This is an example use of a Python function as a route
    #
    if has_role(so, "cockpit"):
        print(f"A craft was deleted {so.id&0xffff}")
        return

           
    if not(has_role(so, "station") or has_role(so,"__player__")):
        return
    #
    # Ok a station or player got destroyed
    # also remove things that are docked at the station
    #
    docked_crafts = linked_to(so, "hangar_craft") & role("standby")

    for id in docked_crafts:
        print(f"deleting docked craft {id&0xffff}")
        # restore it so delete message goes out
        #
        # TODO: The engine is nor deleting the object properly
        # For know forcing the script to forget about it
        sbs.delete_object(id)
    hangar_bump_version()    
        
    
def hangar_set_dock(craft_id, docked_id):
    craft_id = to_id(craft_id)
    docked_id = to_id(docked_id)
    if not object_exists(craft_id):
        return
    if not object_exists(docked_id):
        return

    current = get_dedicated_link(craft_id, "home_dock")
    if current is not None: 
        unlink(docked_id, "hangar_craft", craft_id)

    set_dedicated_link(craft_id, "home_dock", docked_id) # dedicated = can only have one
    link(docked_id, "hangar_craft", craft_id)
    set_science_selection(craft_id, docked_id)
    hangar_bump_version()

def hangar_craft_spawn(docked_id, art, roles, prefix):
    global _craft_id
    if roles is None:
        roles = "cockpit,standby"
    else:
        roles += ",cockpit,standby"

    docked_id = to_id(docked_id) 
        

    so = to_object(docked_id)
    _pos = so.engine_object.pos
    craft = player_spawn(_pos.x, _pos.y,_pos.z, f"{prefix} {_craft_id}", roles, art)
    _craft_id += 1
    hm = sbs.get_hull_map(craft.id,True)
    # Not counted for end game
    craft.py_object.remove_role("PlayerShip,__player__")
    #
    # Cross links
    #
    hangar_set_dock(craft.id, docked_id)
    sbs.push_to_standby_list(craft.engine_object)
    set_science_selection(craft.id, docked_id)
    return craft
    

def hangar_random_craft_spawn(docked_id, roles):
    if randint(0,3) == 1:
        return hangar_shuttle_spawn(docked_id, roles)
    
    return hangar_fighter_spawn(docked_id, roles)

def hangar_fighter_spawn(docked_id, roles):
    if roles is None:
        roles = "fighter"
    else:
        roles += ",fighter" 
    return hangar_craft_spawn(docked_id, "tsn_fighter", roles, "FX")

def hangar_shuttle_spawn(docked_id, roles):
    if roles is None:
        roles = "shuttle"
    else:
        roles += ",shuttle" 
    return hangar_craft_spawn(docked_id, "tsn_shuttle", roles, "SX")

def hangar_launch_craft(craft_id):
    if craft_id is None: return
    craft = to_object(craft_id)
    if craft is None: return
    if not has_role(craft_id, "standby"): return
    if not is_timer_finished(craft_id, "refit"): return

    hangar_bump_version()
    #
    # Add the craft back into the game arena
    #
    sbs.retrieve_from_standby_list(craft.engine_object)
    #
    # Create the Ships internals
    #
    hm = sbs.get_hull_map(craft.id, True)
    if hm is None: return False
    grid_rebuild_grid_objects(craft.id)
    if has_role(craft.id, "fighter"):
        set_data_set_value(craft.id, "torpedo_count", 5, sbs.TORPEDO.HOMING)
    remove_role(craft.id, "standby")

    home_id = get_dedicated_link(craft.id, "home_dock")
    set_science_selection(craft_id, home_id)
    return True


def hangar_attempt_dock_craft(craft_id, dock_rng = 600):
    if craft_id is None: return
    if has_role(craft_id, "standby"): return
    craft = to_object(craft_id)
    if craft is None: return
    
    
    #
    # Simple case for now, just dock with stations
    #
    home_id = get_dedicated_link(craft.id, "home_dock") 

    if home_id is not None and sbs.distance_id(craft.id, home_id) < dock_rng:
        dock_target = home_id
    else:
        dockable = broad_test_around(craft.id, dock_rng, dock_rng, 0x10)
        # print(len(role("tsn") & any_role("station,__player__")))
        dock_target = closest(craft_id, dockable & role("tsn") & any_role("station, __player__"))

    if dock_target is None: return False
    hangar_bump_version()

    set_science_selection(craft.id, dock_target)
    # Not counted for end game
    craft.add_role("standby")
    craft.data_set.set("fighter_thrust_flag", 0,0)
    craft.data_set.set("fighter_shoot_flag", 0,0)
    craft.data_set.set("fighter_boost_flag", 0,0)
    craft.data_set.set("throttle", 0.0,0)
    pos = get_pos(dock_target)
    if pos:
        set_pos(craft.id, pos)
    sbs.push_to_standby_list_id(craft.id)
    set_timer(craft.id, "refit", seconds=30)
    return True

