
from sbs_utils.procedural.execution import get_shared_variable
from sbs_utils.procedural.query import to_id, to_object, to_blob #, object_exists, to_object_list, get_side
from sbs_utils.procedural.sides import side_set_hostile_to_players
from sbs_utils.procedural.roles import add_role
from sbs_utils.procedural.routes import follow_route_select_science
from sbs_utils.procedural.spawn import npc_spawn, terrain_spawn
from sbs_utils.procedural.links import link, unlink
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils import faces as faces
from sbs_utils.faces import set_face, random_face
from sbs_utils.names import name_random_hostile
from sbs_utils.vec import Vec3
import random
from fleet import fleet_spawn
from sbs_utils.procedural.fleet_tables import (
    fleet_table_get, fleet_table_races, fleet_table_pick_race)
from elite_abilitites import elite_get_all_abilities, elite_is_engine_ability, random_bits



def player_ship_update_friendly(player_id, friends, initial_scan = False):
    blob = to_blob(player_id)
    num_ids = 0 # blob.get("num_extra_scan_sources",0)
    print("NOTE: player_ship_update_friendly is depreicated")
    print("use link(player_ship. 'extra_scan_source', the_scan_sources)  ")
    print("system will update")


    for friend in friends:
        blob.set("extra_scan_source", to_id(friend), num_ids)
        num_ids += 1
        if initial_scan:
            follow_route_select_science(to_id(player_id), to_id(friend))

    blob.set("num_extra_scan_sources",num_ids,0)





def fleet_remove_ship(id_or_obj):
    ship_id = to_id(id_or_obj)
    if ship_id is None:
        return
    fleet_id = get_inventory_value(ship_id, "my_fleet_id")
    unlink(fleet_id,"ship_list", ship_id)



#--------------------------------------------------------------------------------------
def fleet_create(race, fleet_diff, posx, posy, posz, fleet_roles = "RaiderFleet", ship_roles=None, faction_side=False):
    """Create a new fleet and add the appropriate amount of ships

    Args:
        race (str): 
        fleet_diff (int): DIFFICULTY -1 to use as index for fleet lists
        posx (float): location
        posy (float): location
        posz (float): location
        fleet_roles (str, optional): Role for the fleet. Defaults to "RaiderFleet".
        ship_roles (str, optional): Roles for the ships. Defaults to None.

    Returns:
        fleet (Fleet): The created fleet
    """
    # At this point it is an index 0-10
    diff = get_shared_variable("DIFFICULTY", 4)
    # If it is -1 use the default
    if  fleet_diff == -1:
        fleet_diff = diff
    # if it < -99, adjust diffulty minus the hundreds place
    # it is an add either way negative is same as subtract
    if  fleet_diff < -99 or fleet_diff>99:
            fleet_diff = diff+(fleet_diff//100)

    fleet_diff = max(0, min(10,fleet_diff))
    #print(f"FLEET {fleet_diff}")

    # The ladders used to be six literals in this file behind an if/elif chain, with the
    # roster of raiding factions written as a random.choice([...]) beside it - so adding a
    # race meant editing a mission library and no mod could add one at all. They now live
    # in each race_* addon as fleets.yaml and register themselves, gated on NPC_RACES.
    race = (race or "").strip().lower()
    if race in ("", "random"):
        race = fleet_table_pick_race() or "kralien"
    siege_fleet = fleet_table_get(race, fleet_diff)
    if not siege_fleet:
        # A race with no registered ladder - not in NPC_RACES, or a typo. Say so: the
        # silent alternative is a fleet that spawns nothing and a mission that quietly
        # has no enemies.
        known = ", ".join(fleet_table_races()) or "none"
        print(f"fleet_create: no fleet table for race '{race}' "
              f"(is it in the NPC_RACES setting? registered: {known})")
        return None


    
    num_ships = len(siege_fleet)
#    max_carriers = int(max_carriers)
    fleet_obj = fleet_spawn(Vec3(posx, posy, posz), fleet_roles)

#    ship_key_list = filter_ship_data_by_side(None, race, "ship", True)

    # Allow the script to extend abilities
    script_abilities = get_shared_variable("elite_script_abilities", [])
    #all_abilities = []
    #all_abilities.extend(abilities)
    #all_abilities.extend(engine_abilities)
    #all_abilities.extend(script_abilities)
    all_abilities_copy = elite_get_all_abilities().copy()
    hard = ["elite_cloak", "elite_low_vis", "elite_jump_back"]
    # remove more difficult abilities
    if fleet_diff <5:
        for h in hard:
            all_abilities_copy.pop(h, None)

    # Per-faction (opt-in): put the ships on the RACE's OWN side, hostile to the
    # players, instead of the shared "raider" side. Register the side + relations
    # once here; each ship keeps the "raider" role (compat + combat scope) but its
    # SIDE is the faction, so a ceasefire / multi-faction setup works via diplomacy.
    # Default (faction_side False) keeps the historical shared "raider" side.
    if faction_side:
        side_set_hostile_to_players(race)

#    carrier_count = 0
    for b in range(num_ships):
        art_id = siege_fleet[b]
        if faction_side:
            roles = f"{race},{ship_roles}" if ship_roles is not None else f"{race},raider"
        else:
            roles = f"{ship_roles},{race}" if ship_roles is not None else f"raider,{race}"
        
        r_name = name_random_hostile(race)                           #  f"{random.choice(enemy_prefix)} {str(call_signs[enemy_name_number]).zfill(2)}"

        spawn_data = npc_spawn(posx, posy, posz, r_name, roles, art_id, "behav_npcship")
        raider = spawn_data.py_object
        set_inventory_value(raider.id, "my_fleet_id", fleet_obj.id)
        link(fleet_obj.id,"ship_list", raider.id)

        if ship_roles is None:
            ship_roles = ""
        skar_chance = 1 # max(int((10 - fleet_diff)*0.5), 1)
        if "elite" in ship_roles or (race == "skaraan" and random.randint(1,skar_chance) == 1):
            
            add_role(raider.id, "elite")
            max_abi = len(all_abilities_copy)
            abits = random_bits(max_abi, max(1, (fleet_diff+2)//2))  #random.randint(0,pow(2,max_abi))
            # set_inventory_value(raider.id, "elite_abilities", abits)
            # bit field
            # & 0x1 == Cloak  
            # & 0x2 == Jump Back
            # & 0x4 == Jump forward
            # & 0x8 == Jump Back
            for count, ab in enumerate(all_abilities_copy):
                bit = 2**count
                if (abits & bit)  == bit:
                    #
                    # Set the flag in engine for always on 
                    #
                    if elite_is_engine_ability(ab):
                        raider.data_set.set(ab, 1,0)
                    add_role(raider.id, ab)
            


        # Should add a common function to call to get the face based on race
        set_face(raider.id, random_face(race))
    return fleet_obj

