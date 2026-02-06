
from sbs_utils.procedural.execution import get_shared_variable
from sbs_utils.procedural.query import to_id, to_object, to_blob #, object_exists, to_object_list, get_side
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





siege_kralien_fleet = [
    # DIFFICULTY 1
    [["kralien_cruiser"], 
     ["kralien_cruiser", "kralien_cruiser"], 
     ["kralien_battleship"], 
     ["kralien_battleship", "kralien_cruiser"], 
     ["kralien_dreadnought"]],
    # DIFFICULTY 2
    [["kralien_cruiser", "kralien_cruiser", "kralien_cruiser"], 
     ["kralien_cruiser", "kralien_cruiser", "kralien_cruiser"], 
     ["kralien_battleship", "kralien_battleship"], 
     ["kralien_battleship", "kralien_battleship"], 
     ["kralien_dreadnought", "kralien_cruiser"]],
    # DIFFICULTY 3
    [["kralien_battleship", "kralien_cruiser", "kralien_cruiser"], 
     ["kralien_battleship", "kralien_cruiser", "kralien_cruiser"], 
     ["kralien_battleship", "kralien_cruiser", "kralien_cruiser"], 
     ["kralien_dreadnought", "kralien_cruiser"], 
     ["kralien_dreadnought", "kralien_cruiser"]],
    # DIFFICULTY 4
    [["kralien_battleship", "kralien_battleship", "kralien_cruiser"],
     ["kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought"]],
    # DIFFICULTY 5
    [["kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_battleship", "kralien_battleship", "kralien_battleship"],
     ["kralien_battleship", "kralien_battleship", "kralien_battleship"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_cruiser"]],
    # DIFFICULTY 6
    [["kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship"]],
    # DIFFICULTY 7
    [["kralien_battleship", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_battleship"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_battleship", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"]],
    # DIFFICULTY 8
    [["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_battleship", "kralien_battleship"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"]],
    # DIFFICULTY 9
    [["kralien_dreadnought", "kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_battleship", "kralien_battleship"]],
    # DIFFICULTY 10
    [["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_battleship", "kralien_battleship"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_battleship", "kralien_battleship", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_cruiser", "kralien_cruiser", "kralien_cruiser"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_battleship"]],
    # DIFFICULTY 11
    [["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought"],
     ["kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought", "kralien_dreadnought"]]
]

siege_torgoth_fleet = [
    # DIFFICULTY 1
    [["torgoth_destroyer"],
     ["torgoth_destroyer"],
     ["torgoth_destroyer"],
     ["torgoth_destroyer"],
     ["torgoth_destroyer"]],
     # DIFFICULTY 2
     [["torgoth_destroyer"],
      ["torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath"],
      ["torgoth_goliath"]],
     # DIFFICULTY 3
     [["torgoth_destroyer"],
      ["torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath"],
      ["torgoth_goliath", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer"]],
     # DIFFICULTY 4
     [["torgoth_destroyer"],
      ["torgoth_goliath"],
      ["torgoth_goliath", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"]],
     # DIFFICULTY 5
     [["torgoth_goliath", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"]],
     # DIFFICULTY 6
     [["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"]],
     # DIFFICULTY 7
     [["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer"]],
     # DIFFICULTY 8
     [["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"]],
     # DIFFICULTY 9
     [["torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"]],
     # DIFFICULTY 10
     [["torgoth_goliath", "torgoth_goliath", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_leviathan", "torgoth_leviathan", "torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_destroyer", "torgoth_destroyer", "torgoth_destroyer"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_leviathan", "torgoth_destroyer", "torgoth_destroyer"]],
     # DIFFICULTY 11
     [["torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth"],
      ["torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth", "torgoth_behemoth"]]
]

siege_arvonian_fleet = [
    # DIFFICULTY 1
    [["arvonian_destroyer"],
     ["arvonian_destroyer"],
     ["arvonian_destroyer"],
     ["arvonian_destroyer"],
     ["arvonian_destroyer"]],
     # DIFFICULTY 2
     [["arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # DIFFICULTY 3
     [["arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # DIFFICULTY 4
     [["arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier"]],
     # DIFFICULTY 5
     [["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier"],
      ["arvonian_light_carrier", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"]],
     # DIFFICULTY 6
     [["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # DIFFICULTY 7
     [["arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer"]],
     # DIFFICULTY 8
     [["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # DIFFICULTY 9
     [["arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_light_carrier", "arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # DIFFICULTY 10
     [["arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_light_carrier", "arvonian_light_carrier", "arvonian_destroyer", "arvonian_destroyer"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_destroyer", "arvonian_destroyer", "arvonian_destroyer"]],
     # DIFFICULTY 11
     [["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier"],
      ["arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier", "arvonian_carrier"]]
]

siege_skaraan_fleet = [
    # DIFFICULTY 1
    [["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_defiler"]],
     # DIFFICULTY 2
     [["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"]],
     # DIFFICULTY 3
     [["skaraan_defiler"],
     ["skaraan_defiler"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"]],
     # DIFFICULTY 4
     [["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"]],
     # DIFFICULTY 5
     [["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_executor"]],
     # DIFFICULTY 6
     [["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_executor"],
     ["skaraan_executor"]],
     # DIFFICULTY 7
     [["skaraan_enforcer"],
     ["skaraan_enforcer"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"]],
     # DIFFICULTY 8
     [["skaraan_enforcer"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"]],
     # DIFFICULTY 9
     [["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"],
     ["skaraan_executor"]],
     # DIFFICULTY 10
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
     # DIFFICULTY 11
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
    # DIFFICULTY 1
    [["xim_scout"],
     ["xim_scout"],
     ["xim_scout"],
     ["xim_scout"],
     ["xim_corsair"]],
     # DIFFICULTY 2
     [["xim_scout"],
     ["xim_scout"],
     ["xim_scout"],
     ["xim_corsair"],
     ["xim_light_cruiser"]],
     # DIFFICULTY 3
     [["xim_scout"],
     ["xim_scout"],
     ["xim_corsair"],
     ["xim_corsair"],
     ["xim_light_cruiser"]],
     # DIFFICULTY 4
     [["xim_scout"],
     ["xim_corsair"],
     ["xim_corsair"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"]],
     # DIFFICULTY 5
     [["xim_scout"],
     ["xim_corsair"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"]],
     # DIFFICULTY 6
     [["xim_corsair"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"]],
     # DIFFICULTY 7
     [["xim_light_cruiser"],
     ["xim_light_cruiser"],
     ["xim_light_cruiser"],
     ["xim_dreadnought"],
     ["xim_dreadnought"]],
     #DIFFICULTY 8
     [["xim_dreadnought"],
     ["xim_dreadnought"],
     ["xim_dreadnought"],
     ["xim_dreadnought"],
     ["xim_battleship"]],
     # DIFFICULTY 9
     [["xim_dreadnought"],
     ["xim_dreadnought"],
     ["xim_battleship"],
     ["xim_battleship"],
     ["xim_battleship"]],
     # DIFFICULTY 10
     [["xim_dreadnought"],
     ["xim_battleship"],
     ["xim_battleship"],
     ["xim_dreadnought", "xim_dreadnought"],
     ["xim_battleship", "xim_battleship"]],
     # DIFFICULTY 11
     [["xim_dreadnought", "xim_dreadnought", "xim_dreadnought", "xim_battleship", "xim_battleship", "xim_battleship"],
     ["xim_dreadnought", "xim_dreadnought", "xim_dreadnought", "xim_battleship", "xim_battleship", "xim_battleship"],
     ["xim_dreadnought", "xim_dreadnought", "xim_dreadnought", "xim_battleship", "xim_battleship", "xim_battleship"],
     ["xim_dreadnought", "xim_dreadnought", "xim_dreadnought", "xim_battleship", "xim_battleship", "xim_battleship"],
     ["xim_dreadnought", "xim_dreadnought", "xim_dreadnought", "xim_battleship", "xim_battleship", "xim_battleship"]]
]

siege_pirate_fleet = [
    # DIFFICULTY 1
    [["pirate_longbow"],
     ["pirate_longbow"],
     ["pirate_longbow"],
     ["pirate_longbow"],
     ["pirate_longbow"]],
     # DIFFICULTY 2
     [["pirate_longbow"],
      ["pirate_longbow"],
      ["pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"]],
     # DIFFICULTY 3
     [["pirate_longbow"],
      ["pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow"]],
     # DIFFICULTY 4
     [["pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow"],
      ["pirate_strongbow"]],
     # DIFFICULTY 5
     [["pirate_longbow"],
      ["pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow"],
      ["pirate_strongbow"],
      ["pirate_strongbow"]],
     # DIFFICULTY 6
     [["pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow"],
      ["pirate_strongbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"]],
     # DIFFICULTY 7
     [["pirate_longbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine"]],
     # DIFFICULTY 8
     [["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow", "pirate_longbow"]],
     # DIFFICULTY 9
     [["pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_longbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow", "pirate_longbow", "pirate_longbow"]],
     # DIFFICULTY 10
     [["pirate_strongbow", "pirate_strongbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_longbow", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_brigantine", "pirate_longbow", "pirate_longbow"],
      ["pirate_brigantine", "pirate_brigantine", "pirate_longbow", "pirate_longbow"],
      ["pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_longbow", "pirate_longbow"]],
     # DIFFICULTY 11
     [["pirate_strongbow", "pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_brigantine", "pirate_brigantine"],
      ["pirate_strongbow", "pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_brigantine", "pirate_brigantine"],
      ["pirate_strongbow", "pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_brigantine", "pirate_brigantine"],
      ["pirate_strongbow", "pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_brigantine", "pirate_brigantine"],
      ["pirate_strongbow", "pirate_strongbow", "pirate_strongbow", "pirate_brigantine", "pirate_brigantine", "pirate_brigantine"]]
]





def fleet_remove_ship(id_or_obj):
    ship_id = to_id(id_or_obj)
    if ship_id is None:
        return
    fleet_id = get_inventory_value(ship_id, "my_fleet_id")
    unlink(fleet_id,"ship_list", ship_id)



#--------------------------------------------------------------------------------------
def fleet_create(race, fleet_diff, posx, posy, posz, fleet_roles = "RaiderFleet", ship_roles=None):
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

    race = race.strip().lower()
    fleet_rand = random.randint(0, 4)
    siege_fleet = []
    if race == "random":
        race = random.choice(["kralien", "torgoth","arvonian", "skaraan", "ximni", "pirate"])
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

#    carrier_count = 0
    for b in range(num_ships):
        art_id = siege_fleet[b]
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

