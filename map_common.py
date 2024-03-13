from sbs_utils.objects import Npc
from sbs_utils.agent import Agent, get_story_id
from sbs_utils.mast.label import label
from sbs_utils.tickdispatcher import TickDispatcher
from sbs_utils.procedural.execution import task_schedule, jump, AWAIT, get_variable
from sbs_utils.procedural.timers import delay_sim, is_timer_set_and_finished, is_timer_finished, set_timer, is_timer_set, clear_timer
from sbs_utils.procedural.query import to_object, to_id, object_exists, to_object_list, get_side
from sbs_utils.procedural.space_objects import target, closest, clear_target, closest_list
from sbs_utils.procedural.roles import role, all_roles, get_race
from sbs_utils.procedural.science import science_set_scan_data
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.procedural.links import get_dedicated_link, set_dedicated_link, unlink, link
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.ship_data import get_ship_data_for, filter_ship_data_by_side
from sbs_utils.faces import set_face, random_face
from sbs_utils.vec import Vec3
import random
from fleet import fleet_spawn




call_signs = []
enemy_name_number = 0
call_signs.extend(range(1,100))
#print(f"call_signs size = {len(call_signs)}")
random.shuffle(call_signs)

#--------------------------------------------------------------------------------------
def get_random_npc_call_sign(race):
    global enemy_name_number

    enemy_prefix = "KLMNQ"
    if race == "skaraan":
        enemy_prefix = "TR"
    r_name = f"{random.choice(enemy_prefix)} {str(call_signs[enemy_name_number]).zfill(2)}"
    enemy_name_number = (enemy_name_number+1)%99
    return r_name


#--------------------------------------------------------------------------------------
def create_npc_fleet_and_ships(race, num_ships, max_carriers, posx, posy, posz, roles = "RaiderFleet"):

    num_ships = int(num_ships)
    max_carriers = int(max_carriers)
    fleet_obj = fleet_spawn(Vec3(posx, posy, posz), roles)

    ship_key_list = filter_ship_data_by_side(None, race, "ship", True)
    
    carrier_count = 0
    for b in range(num_ships):

        done_ae = False
        while not done_ae:
            art_id = random.choice(ship_key_list)
            ship_data_ae = get_ship_data_for(art_id)

            # is this shis gonna be a carrier?
            d_roles = ship_data_ae.get("roles", "")
            if "carrier" in d_roles and carrier_count >= max_carriers:
                continue
            if "carrier" in d_roles:
                carrier_count += 1
            done_ae = True

        roles = f"{race}, raider"
        r_name = get_random_npc_call_sign(race)                           #  f"{random.choice(enemy_prefix)} {str(call_signs[enemy_name_number]).zfill(2)}"

        spawn_data = npc_spawn(posx, posy, posz, r_name, roles, art_id, "behav_npcship")
        raider = spawn_data.py_object
        set_inventory_value(raider.id, "my_fleet_id", fleet_obj.id)
        link(fleet_obj.id,"ship_list", raider.id)


        # Should add a common function to call to get the face based on race
        set_face(raider.id, random_face(race))

