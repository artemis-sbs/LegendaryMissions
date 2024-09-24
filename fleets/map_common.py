
from sbs_utils.procedural.execution import get_shared_variable
from sbs_utils.procedural.query import to_id, to_object #, object_exists, to_object_list, get_side
from sbs_utils.procedural.roles import add_role
from sbs_utils.procedural.spawn import npc_spawn, terrain_spawn
from sbs_utils.procedural.links import link, unlink
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.ship_data import get_ship_data_for, filter_ship_data_by_side
from sbs_utils import faces as faces
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

def terrain_spawn_black_hole(x,y,z, gravity_radius= 1500, gravity_strength=1.0, turbulence_strength= 1.0, collision_damage=200):
    global enemy_name_number

    _prefix = "XEA"
    r_name = f"{random.choice(_prefix)} {str(call_signs[enemy_name_number]).zfill(2)}"
    enemy_name_number = (enemy_name_number+1)%99

    bh = to_object(terrain_spawn(x,y,z, r_name, "#,black_hole", "maelstrom", "behav_maelstrom"))
    bh.engine_object.exclusion_radius = 100 # event horizon
    blob = bh.data_set
    blob.set("gravity_radius", gravity_radius, 0)
    blob.set("gravity_strength", gravity_strength, 0)
    blob.set("turbulence_strength", turbulence_strength, 0)
    blob.set("collision_damage", collision_damage, 0)
    # Note this returns the object, not spawn data. SpawnData is deprecated 
    return bh


engine_abilities = {
        # Blob flags (Always On)
        "elite_low_vis": "LowVis",
        "elite_main_scn_invis": "Invs",
        "elite_drone_launcher": "Drones",
        "elite_anti_mine": "AntiMine",
        "elite_anti_torpedo": "AntiTorp"
}
abilities = {

    "elite_cloak": "Cloak",
    "elite_jump_back": "Back",
    "elite_jump_forward": "Forward",
    "elite_warp": "Warp",
    "elite_het_turn": "HET",
    # Blob Flags Randomize
    "elite_tractor": "Tractor",  # also needs to set tractor_target_uid
    "elite_shield_drain": "ShldDrain",
    "elite_shield_vamp": "ShldVamp", # Drain is also assumed
    "elite_shield_scramble": "Scram",
}
all_abilities = abilities | engine_abilities

siege_kralien_fleet = [
    # Difficulty 1
    [["kralien_cruiser"], 
     ["kralien_cruiser", "kralien_cruiser"], 
     ["kralien_battleship"], 
     ["kralien_battleship", "kralien_cruiser"], 
     ["kralien_dreadnought"]],
    # Difficulty 2
    [["kralien_cruiser", "kralien_cruiser", "kralien_cruiser"], 
     ["kralien_cruiser", "kralien_cruiser", "kralien_cruiser"], 
     ["kralien_battleship", "kralien_battleship"], 
     ["kralien_battleship", "kralien_battleship"], 
     ["kralien_dreadnought", "kralien_cruiser"]],
    # Difficulty 3
    [["kralien_battleship", "kralien_cruiser", "kralien_cruiser"], 
     ["kralien_battleship", "kralien_cruiser", "kralien_cruiser"], 
     ["kralien_battleship", "kralien_cruiser", "kralien_cruiser"], 
     ["kralien_dreadnought", "kralien_cruiser"], 
     ["kralien_dreadnought", "kralien_cruiser"]],
    # Difficulty 4
    [["kralien_battleship", "kralien_battleship", "kralien_cruiser"],
     ["kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought"]],
    # Difficulty 5
    [["kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_battleship", "kralien_battleship", "kralien_battleship"],
     ["kralien_battleship", "kralien_battleship", "kralien_battleship"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_cruiser"]],
    # Difficulty 6
    [["kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship"]],
    # Difficulty 7
    [["kralien_battleship", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_battleship"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_battleship", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"]],
    # Difficulty 8
    [["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_battleship", "kralien_battleship"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"]],
    # Difficulty 9
    [["kralien_dreadnought", "kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_battleship", "kralien_battleship"]],
    # Difficulty 10
    [["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_battleship", "kralien_battleship"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_battleship"]],
    # Difficulty 11
    [["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought"]]
]

siege_torgoth_fleet = [
    # Difficulty 1
    [["torgoth_destroyer"],
     ["torgoth_destroyer"],
     ["torgoth_destroyer"],
     ["torgoth_destroyer"],
     ["torgoth_destroyer"]],
     # Difficulty 2
     [["torgoth_destroyer"],
      ["torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath"],
      ["torgoth_goliath"]],
     # Difficulty 3
     [["torgoth_destroyer"],
      ["torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath"],
      ["torgoth_goliath", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer"]],
     # Difficulty 4
     [["torgoth_destroyer"],
      ["torgoth_goliath"],
      ["torgoth_goliath", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"]],
     # Difficulty 5
     [["torgoth_goliath", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"]],
     # Difficulty 6
     [["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"]],
     # Difficulty 7
     [["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer"]],
     # Difficulty 8
     [["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"]],
     # Difficulty 9
     [["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"]],
     # Difficulty 10
     [["torgoth_goliath", "torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_leviathan", "torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"]],
     # Difficulty 11
     [["torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth"]]
]

siege_arvonian_fleet = [
    # Difficulty 1
    [["arvonian_destroyer"],
     ["arvonian_destroyer"],
     ["arvonian_destroyer"],
     ["arvonian_destroyer"],
     ["arvonian_destroyer"]],
     # Difficulty 2
     [["arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # Difficulty 3
     [["arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # Difficulty 4
     [["arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier"]],
     # Difficulty 5
     [["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier"],
      ["arvonian_light_carrier", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"]],
     # Difficulty 6
     [["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # Difficulty 7
     [["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer"]],
     # Difficulty 8
     [["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # Difficulty 9
     [["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # Difficulty 10
     [["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_light_carrier", "arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # Difficulty 11
     [["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier"]]
]

siege_skaraan_fleet = [
    # Difficulty 1
    [["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_defiler"]],
     # Difficulty 2
     [["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"]],
     # Difficulty 3
     [["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"]],
     # Difficulty 4
     [["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"]],
     # Difficulty 5
     [["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_executor"]],
     # Difficulty 6
     [["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_executor"],
     ["skaraan_executor"]],
     # Difficulty 7
     [["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"]],
     # Difficulty 8
     [["skaraan_enforcer"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"]],
     # Difficulty 9
     [["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"]],
     # Difficulty 10
     [["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"]],
    #  [["skaraan_executor"],
    #  ["skaraan_executor"],
    #  ["skaraan_executor"],
    #  ["skaraan_executor"],
    #  ["skaraan_executor", "skaraan_executor"]],
     # Difficulty 11
     [["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"]],

    #  [["skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor"],
    #  ["skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor"],
    #  ["skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor"],
    #  ["skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor"],
    #  ["skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor", "skaraan_executor"]]
]

siege_ximni_fleet = [
    # Difficulty 1
    [["xim_scout"],
     ["xim_scout"],
     ["xim_scout"],
     ["xim_scout"],
     ["xim_corsair"]],
     # Difficulty 2
     [["xim_scout"],
     ["xim_scout"],
     ["xim_scout"],
     ["xim_corsair"],
     ["xim_light_cruiser"]],
     # Difficulty 3
     [["xim_scout"],
     ["xim_scout"],
     ["xim_corsair"],
     ["xim_corsair"],
     ["xim_light_cruiser"]],
     # Difficulty 4
     [["xim_scout"],
     ["xim_corsair"],
     ["xim_corsair"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"]],
     # Difficulty 5
     [["xim_scout"],
     ["xim_corsair"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"]],
     # Difficulty 6
     [["xim_corsair"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"]],
     # Difficulty 7
     [["xim_light_cruiser"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"],
     ["xim_dreadnought"],
     ["xim_dreadnought"]],
     #Difficulty 8
     [["xim_dreadnought"],
     ["xim_dreadnought"],
     ["xim_dreadnought"],
     ["xim_dreadnought"],
     ["xim_battleship"]],
     # Difficulty 9
     [["xim_dreadnought"],
     ["xim_dreadnought"],
     ["xim_battleship"],
     ["xim_battleship"],
     ["xim_battleship"]],
     # Difficulty 10
     [["xim_dreadnought"],
     ["xim_battleship"],
     ["xim_battleship"],
     ["xim_dreadnought", "xim_dreadnought"],
     ["xim_battleship", "xim_battleship"]],
     # Difficulty 11
     [["xim_dreadnought", "xim_dreadnought", "xim_dreadnought", "xim_battleship", "xim_battleship", "xim_battleship"],
     ["xim_dreadnought", "xim_dreadnought", "xim_dreadnought", "xim_battleship", "xim_battleship", "xim_battleship"],
     ["xim_dreadnought", "xim_dreadnought", "xim_dreadnought", "xim_battleship", "xim_battleship", "xim_battleship"],
     ["xim_dreadnought", "xim_dreadnought", "xim_dreadnought", "xim_battleship", "xim_battleship", "xim_battleship"],
     ["xim_dreadnought", "xim_dreadnought", "xim_dreadnought", "xim_battleship", "xim_battleship", "xim_battleship"]]
]

siege_pirate_fleet = [
    # Difficulty 1
    [["pirate_longbow"],
     ["pirate_longbow"],
     ["pirate_longbow"],
     ["pirate_longbow"],
     ["pirate_longbow"]],
     # Difficulty 2
     [["pirate_longbow"],
      ["pirate_longbow"],
      ["pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"]],
     # Difficulty 3
     [["pirate_longbow"],
      ["pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow"]],
     # Difficulty 4
     [["pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow"],
      ["pirate_strongbow"]],
     # Difficulty 5
     [["pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow"],
      ["pirate_strongbow"],
      ["pirate_strongbow"]],
     # Difficulty 6
     [["pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow"],
      ["pirate_strongbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"]],
     # Difficulty 7
     [["pirate_longbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine"]],
     # Difficulty 8
     [["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow", "pirate_longbow"]],
     # Difficulty 9
     [["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow", "pirate_longbow", "pirate_longbow"]],
     # Difficulty 10
     [["pirate_strongbow", "pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_brigantine", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_brigantine", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_longbow", "pirate_longbow"]],
     # Difficulty 11
     [["pirate_strongbow", "pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_brigantine", "pirate_brigantine"],
      ["pirate_strongbow", "pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_brigantine", "pirate_brigantine"],
      ["pirate_strongbow", "pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_brigantine", "pirate_brigantine"],
      ["pirate_strongbow", "pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_brigantine", "pirate_brigantine"],
      ["pirate_strongbow", "pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_brigantine", "pirate_brigantine"]]
]



def elite_is_engine_ability(ab):
    return ab in engine_abilities.keys()

def elite_get_non_engine():
    script_abilities = get_shared_variable("elite_script_abilities", {})
    return abilities | script_abilities

def elite_get_all_abilities():
    script_abilities = get_shared_variable("elite_script_abilities", {})
    return all_abilities | script_abilities

def elite_get_abilities_scan(id_or_obj):
    ship_obj = to_object(id_or_obj)
    if ship_obj is None:
        return ""
    abi = ""
    roles = ship_obj.get_roles()
    for role in roles:
        #print(role)
        ab = all_abilities.get(role, None)
        if ab is not None:
            abi += "," + ab
    return abi

def fleet_remove_ship(id_or_obj):
    ship_id = to_id(id_or_obj)
    if ship_id is None:
        return
    fleet_id = get_inventory_value(ship_id, "my_fleet_id")
    unlink(fleet_id,"ship_list", ship_id)

#all_bits = [2**x for x in range(len(all_abilities))]
# Adding extra for script created elite
all_bits = [2**x for x in range(32)]
def random_bits(bits, count):
    bits = min(bits, len(all_bits))
    pick = list(all_bits[:bits])
    ret = 0
    random.shuffle(pick)
    #print(pick)
    p = pick[:count]
    #print(p)
    for b in p:
        ret |= b
        
    return ret


# Noone using this and too much overlap with seige_fleet delete later
#--------------------------------------------------------------------------------------
# def create_npc_fleet_and_ships(race, num_ships, max_carriers, posx, posy, posz, fleet_roles = "RaiderFleet", ship_roles=None):
#     """Create a new fleet and add the appropriate amount of ships

#     Args:
#         race (str): 
#         num_ships (int): The Number of ships in the fleet
#         max_carriers (int): Maximum number of ships
#         posx (float): location
#         posy (float): location
#         posz (float): location
#         fleet_roles (str, optional): Role for the fleet. Defaults to "RaiderFleet".
#         ship_roles (str, optional): Roles for the ships. Defaults to None.

#     Returns:
#         fleet (Fleet): The created fleet
#     """
#     race = race.strip().lower()
#     num_ships = int(num_ships)
#     max_carriers = int(max_carriers)
#     fleet_obj = fleet_spawn(Vec3(posx, posy, posz), fleet_roles)

#     ship_key_list = filter_ship_data_by_side(None, race, "ship", True)

#     # Allow the script to extend abilities
#     script_abilities = get_shared_variable("elite_script_abilities", [])
#     all_abilities = []
#     all_abilities.extend(abilities)
#     all_abilities.extend(engine_abilities)
#     all_abilities.extend(script_abilities)

    
#     carrier_count = 0
#     for b in range(num_ships):
#         done_ae = False
#         while not done_ae:
#             art_id = random.choice(ship_key_list)
#             ship_data_ae = get_ship_data_for(art_id)

#             # is this shis gonna be a carrier?
#             d_roles = ship_data_ae.get("roles", "")
#             if "carrier" in d_roles and carrier_count >= max_carriers:
#                 continue
#             if "carrier" in d_roles:
#                 carrier_count += 1
#             done_ae = True

#         roles = f"{race}, raider,{ship_roles}" if ship_roles is not None else f"{race}, raider"
        
#         r_name = get_random_npc_call_sign(race)                           #  f"{random.choice(enemy_prefix)} {str(call_signs[enemy_name_number]).zfill(2)}"

#         spawn_data = npc_spawn(posx, posy, posz, r_name, roles, art_id, "behav_npcship")
#         raider = spawn_data.py_object
#         set_inventory_value(raider.id, "my_fleet_id", fleet_obj.id)
#         link(fleet_obj.id,"ship_list", raider.id)

#         if ship_roles is None:
#             ship_roles = ""
#         if "elite" in ship_roles or (race == "skaraan" and random.randint(1,10) == 4):
#             add_role(raider.id, "elite")
#             max_abi = len(all_abilities)
#             abits = random_bits(max_abi, 3)  # random.randint(0,pow(2,max_abi))
#             # set_inventory_value(raider.id, "elite_abilities", abits)
#             # bit field
#             # & 0x1 == Cloak  
#             # & 0x2 == Jump Back
#             # & 0x4 == Jump forward
#             # & 0x8 == Jump Back
#             for count, ab in enumerate(all_abilities):
#                 bit = count * 2
#                 if (abits & bit)  == bit:
#                     #
#                     # Set the flag in engine for always on 
#                     #
#                     if elite_is_engine_ability(ab):
#                         raider.data_set.set(ab, 1,0)
#                     add_role(raider.id, ab)


#         # Should add a common function to call to get the face based on race
#         set_face(raider.id, random_face(race))
#     return fleet_obj

#--------------------------------------------------------------------------------------
def create_siege_fleet(race, fleet_diff, posx, posy, posz, fleet_roles = "RaiderFleet", ship_roles=None):
    """Create a new fleet and add the appropriate amount of ships

    Args:
        race (str): 
        fleet_diff (int): difficulty -1 to use as index for fleet lists
        posx (float): location
        posy (float): location
        posz (float): location
        fleet_roles (str, optional): Role for the fleet. Defaults to "RaiderFleet".
        ship_roles (str, optional): Roles for the ships. Defaults to None.

    Returns:
        fleet (Fleet): The created fleet
    """
    race = race.strip().lower()
    fleet_rand = random.randint(0, 4)
    siege_fleet = []
    if race == "kralien":
        siege_fleet = siege_kralien_fleet[fleet_diff][fleet_rand]
    if race == "torgoth":
        siege_fleet = siege_torgoth_fleet[fleet_diff][fleet_rand]
    if race == "arvonian":
        siege_fleet = siege_arvonian_fleet[fleet_diff][fleet_rand]
    if race == "skaraan":
        siege_fleet = siege_skaraan_fleet[fleet_diff][fleet_rand]
    if race == "ximni":
        siege_fleet = siege_ximni_fleet[fleet_diff][fleet_rand]
    if race == "pirate":
        siege_fleet = siege_pirate_fleet[fleet_diff][fleet_rand]
    if race == None:
        race = "kralien"
        siege_fleet = siege_kralien_fleet[fleet_diff][fleet_rand]

    #print(f"Create Fleet, Race: {race}, Ships: {siege_fleet}, Pos: {int(posx)}, {int(posy)}, {int(posz)}")

    
    num_ships = len(siege_fleet)
#    max_carriers = int(max_carriers)
    fleet_obj = fleet_spawn(Vec3(posx, posy, posz), fleet_roles)

#    ship_key_list = filter_ship_data_by_side(None, race, "ship", True)

    # Allow the script to extend abilities
    script_abilities = get_shared_variable("elite_script_abilities", [])
    all_abilities = []
    all_abilities.extend(abilities)
    all_abilities.extend(engine_abilities)
    all_abilities.extend(script_abilities)

    
#    carrier_count = 0
    for b in range(num_ships):
#        done_ae = False
#        while not done_ae:
#            art_id = siege_fleet[b]
#            ship_data_ae = get_ship_data_for(art_id)

            # is this shis gonna be a carrier?
#            d_roles = ship_data_ae.get("roles", "")
#            if "carrier" in d_roles and carrier_count >= max_carriers:
#                continue
#            if "carrier" in d_roles:
#                carrier_count += 1
#            done_ae = True
        art_id = siege_fleet[b]
        roles = f"{race}, raider,{ship_roles}" if ship_roles is not None else f"{race}, raider"
        
        r_name = get_random_npc_call_sign(race)                           #  f"{random.choice(enemy_prefix)} {str(call_signs[enemy_name_number]).zfill(2)}"

        spawn_data = npc_spawn(posx, posy, posz, r_name, roles, art_id, "behav_npcship")
        raider = spawn_data.py_object
        set_inventory_value(raider.id, "my_fleet_id", fleet_obj.id)
        link(fleet_obj.id,"ship_list", raider.id)

        if ship_roles is None:
            ship_roles = ""
        skar_chance = 1 # max(int((10 - fleet_diff)*0.5), 1)
        if "elite" in ship_roles or (race == "skaraan" and random.randint(1,skar_chance) == 1):
            
            add_role(raider.id, "elite")
            max_abi = len(all_abilities)
            abits = random_bits(max_abi, max(1, (fleet_diff+2)//2))  #random.randint(0,pow(2,max_abi))
            # set_inventory_value(raider.id, "elite_abilities", abits)
            # bit field
            # & 0x1 == Cloak  
            # & 0x2 == Jump Back
            # & 0x4 == Jump forward
            # & 0x8 == Jump Back
            for count, ab in enumerate(all_abilities):
                bit = 2**count
                if (abits & bit)  == bit:
                    #
                    # Set the flag in engine for always on 
                    #
                    if elite_is_engine_ability(ab):
                        raider.data_set.set(ab, 1,0)
                    add_role(raider.id, ab)
            #print("Elite "+ elite_get_abilities_scan(raider.id))


        # Should add a common function to call to get the face based on race
        set_face(raider.id, random_face(race))
    return fleet_obj

def get_face_from_data(face_style):
    match face_style:
        case "terran":
            return faces.random_terran()
        case "terran_male":
            return faces.random_terran_male()
        case "terran_female":
            return faces.random_terran_female()
        case "terran_fluid":
            return faces.random_terran_fluid()
        case "terran_civilian":
            return faces.random_terran_fluid()
        case "torgoth":
            return faces.random_torgoth()
        case "skaraan":
            return faces.random_skaraan()
        case "ximni":
            return faces.random_ximni()
        case "arvonian":
            return faces.random_arvonian()
        case "kralien":
            return faces.random_kralien()
        case "random":
            return faces.random_face()
    return face_style

