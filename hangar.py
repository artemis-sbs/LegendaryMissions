from sbs_utils.fs import load_json_data, get_mission_dir_filename
from random import randint
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.procedural.query import set_science_selection, to_object
import sbs

_craft_id = 1

_hangar_mission_data = None 
def hangar_get_mission_data():
    global _hangar_mission_data
    if _hangar_mission_data is None:
        _hangar_mission_data = load_json_data(get_mission_dir_filename("hangar_mission_data.json"))
    return _hangar_mission_data


def hangar_random_craft_spawn(docked_id):
    if randint(0,3) == 1:
        return hangar_shuttle_spawn(docked_id)
    
    return hangar_fighter_spawn(docked_id)

def hangar_fighter_spawn(docked_id):
    return hangar_craft_spawn(docked_id, "tsn_fighter", "fighter", "FX")

def hangar_shuttle_spawn(docked_id):
    return hangar_craft_spawn(docked_id, "tsn_shuttle", "shuttle", "SX")


def hangar_craft_spawn(docked_id, art, craft_type, prefix):
    global _craft_id
    so = to_object(docked_id)
    _pos = so.engine_object.pos
    craft = player_spawn(_pos.x, _pos.y,_pos.z, f"{prefix} {_craft_id}", f"tsn, {craft_type}, cockpit,standby", art)
    _craft_id += 1
    hm = sbs.get_hull_map(craft.id,True)
    # Not counted for end game
    craft.py_object.remove_role("PlayerShip,__player__")
    sbs.push_to_standby_list(craft.engine_object)
    set_science_selection(craft.id, docked_id)
    return craft
    