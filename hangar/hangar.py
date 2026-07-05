from sbs_utils.fs import load_json_data, get_mission_dir_filename
from random import randint
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.procedural.query import set_science_selection, to_space_object, to_id, object_exists, to_data_set, to_space_object_list
from sbs_utils.procedural.links import link, unlink, get_dedicated_link, set_dedicated_link, linked_to, has_link
from sbs_utils.procedural.roles import has_role, remove_role, any_role, role, all_roles
from sbs_utils.procedural.space_objects import broad_test_around, closest, get_pos, set_pos
from sbs_utils.procedural.routes import RouteDamageDestroy
from sbs_utils.procedural.sides import to_side_object
from sbs_utils.procedural.media import media_read_relative_file
from sbs_utils.procedural.ship_data import get_ship_data_for
from sbs_utils.procedural.items import item_get
from sbs_utils.procedural.upgrades import upgrade_add

from sbs_utils.procedural.timers import is_timer_set, set_timer, is_timer_finished
from sbs_utils.procedural.execution import set_shared_variable, get_shared_variable, get_variable
from sbs_utils.agent import Agent
from sbs_utils.procedural.query import get_science_selection
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.comms import comms_broadcast
import random

from sbs_utils.procedural.internal_damage import grid_rebuild_grid_objects
from sbs_utils.procedural.grid import grid_delete_objects
from sbs_utils.fs import load_yaml_string
import sbs

_craft_id = 1

def hangar_bump_version():
    hangar_version = get_shared_variable("hangar_version", 0)
    set_shared_variable("hangar_version", hangar_version+1)

@RouteDamageDestroy
def hangar_handle_destroy():
    so = to_space_object(get_variable("DESTROYED_ID"))
    if so is None:
        return
    #
    # This is an example use of a Python function as a route
    #
    if has_role(so, "cockpit"):
        return

           
    if not(has_role(so, "station") or has_role(so,"__player__")):
        return
    #
    # Ok a station or player got destroyed
    # also remove things that are docked at the station
    #
    docked_crafts = linked_to(so, "hangar_craft") & role("standby")

    for id in docked_crafts:
        # restore it so delete message goes out
        #
        # TODO: The engine is nor deleting the object properly
        # For know forcing the script to forget about it
        sbs.delete_object(id)
    hangar_bump_version()    

def hangar_get_stats(client_id, fighter):
    fighter = to_space_object(fighter)
    if fighter is None:
        return ["", ""]
    
    # shield_max_val already holds the scaled capacity (the cockpit_shields
    # loadout item multiplies it directly), so read it as-is.
    front_shield_max_val = fighter.data_set.get("shield_max_val", 0)
    rear_shield_max_val = fighter.data_set.get("shield_max_val", 1)
    bs = fighter.data_set.get("beamDamage", 0)
    f = fighter.name
    t = "No"
    if has_role(fighter, "shuttle"):
        t = "No"
    else:
        t = "Yes"

    
    s = get_inventory_value(client_id, "sortie", 0)
    c = get_inventory_value(client_id, "completed_objectives", 0)
    call_sign = get_inventory_value(client_id, "call_sign", "pilot")
    line1 = "bad ship data key or data_set values"
    if bs is not None and front_shield_max_val is not None:
        line1 = f"{f}: TORP {t} BEAM {bs:.2f} SHLDS {int(front_shield_max_val)}" # | {int(rear_shield_max_val)}"
    line2 = f"{call_sign}: sorties {s} objectives {c}"
    return [line1, line2]
    
    
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
    set_science_selection(craft_id, docked_id) # This is effectively a waypoint home for the craft
    hangar_bump_version()


_craft_database = None
def hangar_get_craft_data(origin):
    global _craft_database
    if _craft_database is None:
        # The use of media read relative may not work?
        _craft_database = load_yaml_string(media_read_relative_file("hangar_crafts.yaml"))
    if _craft_database is None:
        return None
    
    ret = _craft_database.get(origin)
    if ret is not None:
        return ret
    return None



def hangar_get_ship_data_keys(docked_id):
    over_ride = get_inventory_value(docked_id, "HANGAR_ORIGIN_OVERRIDE", None)
    if over_ride is not None:
        craft_data = hangar_get_craft_data(over_ride)
        if craft_data is not None:
            return craft_data


    so = to_space_object(docked_id)
    side_agent = to_side_object(docked_id)
    over_ride = get_inventory_value(side_agent, "HANGAR_ORIGIN_OVERRIDE", None)
    if over_ride is not None:
        craft_data = hangar_get_craft_data(over_ride)
        if craft_data is not None:
            return craft_data

    origin = so.origin if so is not None else None
    craft_data = hangar_get_craft_data(origin)
    if craft_data is not None:
        return craft_data

    craft_data = hangar_get_craft_data("terran")
    if craft_data is not None:
        return craft_data
    
    print("WARNING: There is no hangar craft data")
    return []


# def hangar_get_ship_data_key(docked_id, roles):
#     craft_type = 2 if "shuttle" in roles  else 1 if "bomber" in roles else 0
#     craft_type_strings = [ "Fighter", "Bomber","Shuttle"]
#     keys = hangar_get_ship_data_keys(docked_id, roles)
#     key = keys[craft_type]
#     sd = get_ship_data_for(key)
#     return (key, sd, craft_type_strings[craft_type])
    



def hangar_apply_loadout(craft_id, upgrades):
    """Install a craft's default upgrades at spawn.

    Each entry in ``upgrades`` is either an item key string (``"cockpit_shields"``)
    or a dict ``{"item": key, ...extra}`` whose extra fields are passed to the
    item effect (e.g. ``{"item": "torp_bay", "torp_type": "Nuke", "amount": 2}``).
    Items are resolved from the registry by key and applied with ``upgrade_add``,
    so their effects (modifier_add coefficients, additive ammo) layer on top of
    the hull's shipData values.
    """
    for up in upgrades:
        if isinstance(up, str):
            ukey = up
            data = {"key": ukey}
        elif isinstance(up, dict):
            ukey = up.get("item")
            data = dict(up)
            data["key"] = ukey
        else:
            continue
        if not ukey:
            continue
        item_label = item_get(ukey)
        if item_label is None:
            print(f"WARNING: hangar loadout item not found: {ukey}")
            continue
        upgrade_add(craft_id, item_label, data=data, activate=True)


def hangar_craft_spawn(docked_id, craft_data):
    """
    Spawns a new hangar craft in the hangar of the specified ship or station.
    You probably don't need to use this, because in hangar.mast, when a ship or station is spawned, this function is called to create all the necessary shuttles, fighters, and bombers needed.

    Args:
        docked_id (int): the id of the parent craft
        art (str): the art id of the craft to spawn, from shipData.json
        roles (str): a comma-separated list of roles
        prefix (str): the desired prefix to the name of craft
    Returns:
        SpawnData: The SpawnData object associated with the craft
    """
    global _craft_id
    
    docked_id = to_id(docked_id)
    so = to_space_object(docked_id)

    sd_key = craft_data.get("key", "tsn_fighter")
    sd = get_ship_data_for(sd_key)
    name = "Fighter"
    origin = so.origin
    if sd is not None:
        name = sd.get("name", name)
        origin = sd.get("origin", origin)

    # The loadout "type" (fighter|bomber|shuttle) is the craft's variant role
    # and its displayed class. name/roles derive from shipData; only the variant
    # and the upgrade list are mission loadout data now.
    craft_type = craft_data.get("type", "fighter")
    roles = f"{so.side},{craft_type},cockpit,standby,hangar"

    _pos = so.engine_object.pos
    name = f"{origin} {name} {_craft_id}"
    craft = player_spawn(_pos.x, _pos.y,_pos.z, name, roles, sd_key)
    _craft_id += 1
    hm = sbs.get_hull_map(craft.id,True)
    # Not counted for end game
    craft.py_object.remove_role("PlayerShip,__player__")

    set_inventory_value(craft.id, "CRAFT_TYPE", craft_type.capitalize())

    # Apply the craft's default upgrades (shields, torpedo bays, ...) through the
    # item/upgrade system. Effects use modifier_add on data_set coefficients and
    # additive ammo, so they layer on top of the hull's shipData values.
    hangar_apply_loadout(craft.id, craft_data.get("upgrades", []))

    #
    # Cross links
    #
    hangar_set_dock(craft.id, docked_id)
    sbs.push_to_standby_list(craft.engine_object)
    set_science_selection(craft.id, docked_id)
    return craft

def hangar_objective_started(CRAFT_ID, OBJECTIVE_ID, objective):
    client_id = get_inventory_value(CRAFT_ID, "client_id", 0)
    comms_broadcast(client_id, f"Objective", "#B90")
    comms_broadcast(client_id, f"{objective}", "#B90")

def hangar_objective_complete(CRAFT_ID, OBJECTIVE_ID, objective):
    # Get the current load
    origin_o = to_space_object(CRAFT_ID)
    pilot = "A craft "
    if origin_o is not None:
        pilot = origin_o.name

    client_id = get_inventory_value(CRAFT_ID, "client_id", 0)
    if client_id!=0:
        c = get_inventory_value(client_id, "completed_objectives", 0)
        c += 1
        set_inventory_value(client_id, "completed_objectives", c)

    comms_broadcast(client_id, "Objective complete", "#090")
    comms_broadcast(client_id, f"   \x02 {objective}", "#090")
    comms_broadcast(OBJECTIVE_ID, f"{pilot} {objective}",  "#090")


def hangar_random_craft_spawn(docked_id, craft_type=None):
    """
    Spawns a random shuttle, bomber, or fighter.
    Pass craft_type to narrow the possibile crafts down to only the available shuttles,
    available fighters, or available bombers. (Usually there is only one available shuttle,
    one available fighter, and one available bomber.)
    If craft_type is not specified, then there is a 20% chance of spawning a shuttle,
    60% chance of spawning a fighter, and a 20% chance of spawning a bomber.
    Args:
        docked_id (int): the id of the ship or station in which the craft will spawn
        craft_type (str | None): Which type of craft to spawn. Valid values are "shuttle",
            "fighter", "bomber", and None. See main function description for details.
    Returns:
        SpawnData: The SpawnData object associated with the craft that was spawned.
    """
    if craft_type is None:
        craft_type_d10_roll = randint(1, 10)
        # 20% chance of shuttle
        if craft_type_d10_roll <= 2:
            craft_type = "shuttle"
        # 60% chance of fighter
        elif craft_type_d10_roll <= 8:
            craft_type = "fighter"
        # 20% chance of bomber
        else:
            craft_type = "bomber"
    
    craft_data_list = hangar_get_ship_data_keys(docked_id)
    filtered = [craft_data for craft_data in craft_data_list if craft_type == craft_data.get("type")]
    craft_data_to_spawn = random.choice(filtered)

    return hangar_craft_spawn(docked_id, craft_data_to_spawn)

def hangar_launch_craft(craft_id, client_id):
    if craft_id is None: return False
    craft = to_space_object(craft_id)
    if craft is None: return False
    if not has_role(craft_id, "standby"): return False
    if not is_timer_finished(craft_id, "refit"): return False

    hangar_bump_version()
    #
    # Add the craft back into the game arena
    #
    sbs.retrieve_from_standby_list(craft.engine_object)
    #
    #
    #
    grid_delete_objects(craft.id)

    #
    # Create the Ships internals
    #
    hm = sbs.get_hull_map(craft.id, True)

    craft.set_inventory_value("craft_name", craft.name)
    call_sign = get_inventory_value(client_id, "call_sign", None)
    sortie = get_inventory_value(client_id, "sortie", 0)
    sortie += 1
    set_inventory_value(client_id, "sortie", sortie)
    if call_sign is not None and len(call_sign)>0:
        craft.name = f"{call_sign} / {craft.name}"

    if hm is None: return False
    grid_rebuild_grid_objects(craft.id)

    blob = to_data_set(craft.id)

    # Use the torp blob dat to refill
    avail = blob.get("torpedo_types_available", 0)
    if not isinstance(avail, str):
        avail = ""
    avail = avail.split(",")
    for t in avail:
        t = t.strip()
        h = blob.get( f"{t}_MAX", 0)
        blob.set(f"{t}_NUM", h, 0)

    # Reset shields
    c = blob.get("shield_count", 0)
    for x in range(c):
        m = blob.get("shield_max_val", x)
        blob.set("shield_val", m, x)

    remove_role(craft.id, "standby")

    home_id = get_dedicated_link(craft.id, "home_dock")
    set_science_selection(craft_id, home_id)
    home = to_space_object(home_id)
    if home is not None:
        # set the position on launch, because if home
        # is a ship it could have moved
        craft.pos = home.pos
        craft.engine_object.rot_quat = home.engine_object.rot_quat
        
    return True


def hangar_attempt_dock_craft(craft_id, dock_rng = 600):
    """
    Try to dock the craft to the nearest space object with a hangar. 
    If the craft is not a valid dockable object, returns None.  
    If the craft isn't close enough, returns false.  
    If the docking is successful, returns true.  
    Args:
        craft_id (int): the ID of the craft
        dock_rng (int): the farthest the craft can be from its hangar in order to dock.
    Returns: 
        boolean | None
    """
    if craft_id is None: return False
    if has_role(craft_id, "standby"): return False
    craft = to_space_object(craft_id)
    if craft is None: return False
    
    
    #
    # Simple case for now, just dock with stations
    #
    home_id = get_dedicated_link(craft.id, "home_dock") 

    # None mean dock anywhere
    if dock_rng is None:
        dock_target = closest(craft_id, role("tsn") & any_role("station, __player__"))
    elif home_id is not None and sbs.distance_id(craft.id, home_id) < dock_rng:
        dock_target = home_id
    else:
        dockable = broad_test_around(craft.id, dock_rng, dock_rng, 0xF0)
        dock_target = closest(craft_id, dockable & role("tsn") & any_role("station, __player__"))

    if dock_target is None: return False
    hangar_bump_version()

    # Update home dock
    new_dock = to_id(dock_target)
    # send message?
    if home_id != new_dock:
        home_id = new_dock
        hangar_set_dock(craft_id, new_dock)
        
    
    set_science_selection(craft.id, dock_target)
    sbs.send_grid_selection_info(craft.id, "", "", "")
    # Not counted for end game
    craft.add_role("standby")
    craft.data_set.set("fighter_thrust_flag", 0,0)
    craft.data_set.set("fighter_shoot_flag", 0,0)
    craft.data_set.set("fighter_boost_flag", 0,0)
    craft.data_set.set("throttle", 0.0,0)
    craft_name = craft.get_inventory_value("craft_name", craft.name)
    craft.name = craft_name

    

    #
    # Remove any grid objects
    #
    grid_delete_objects(craft.id)

    pos = get_pos(dock_target)
    if pos:
        set_pos(craft.id, pos)
    sbs.push_to_standby_list_id(craft.id)

    #
    # Over filling cost refit time
    #
    refit_cooef = 1.0
    if has_role(craft_id, "shuttle"):
        docked_crafts = linked_to(home_id, "hangar_craft") & role("standby") & role("shuttle")
        max_refit = get_inventory_value(home_id, "MAX_SHUTTLE", 1)
        refit_cooef = max(1,len(docked_crafts) - max_refit)
    else:
        """ Treat fighters and bomber same """
        docked_crafts = linked_to(home_id, "hangar_craft") & role("standby") & role("fighter") & role("bomber") 
        max_refit = get_inventory_value(home_id, "MAX_FIGHTER", 1)
        refit_cooef = max(1,len(docked_crafts) - max_refit)

    set_timer(craft.id, "refit", seconds=int(30*refit_cooef))
    return True

from sbs_utils.procedural.gui import gui_row, gui_icon, gui_text, gui_blank
from sbs_utils.procedural.gui.listbox import gui_list_box
from sbs_utils.mast.mast_node import MastDataObject


# --- Fighter/shuttle combat credit (works without the consoles addon) --------
# Pilot kills/tonnage/damage are credited HERE (cockpit attackers only) so the Air
# Wing roster is meaningful in missions like Mining Days that don't load the results
# (consoles) addon. The consoles addon credits player BRIDGE ships only, so the two
# never double-count. Stats land on the same inventory keys either way.
HANGAR_TONNAGE_PER_HULLPOINT = 1000


def _hangar_attacker_id(parent_id, source_id):
    """The crediting attacker: firing ship (parent) when set, else the source."""
    aid = to_id(parent_id)
    if aid is None or aid == 0:
        aid = to_id(source_id)
    if aid == 0:
        return None
    return aid


def _hangar_victim_tonnage(victim):
    so = to_space_object(victim)
    if so is None:
        return 0
    sd = get_ship_data_for(so.art_id)
    hp = (sd.get("hullpoints", 0) or 0) if sd is not None else 0
    return int(hp) * HANGAR_TONNAGE_PER_HULLPOINT


def _hangar_bump(agent_id, key, amount):
    set_inventory_value(agent_id, key, get_inventory_value(agent_id, key, 0) + amount)


def hangar_credit_kill(parent_id, source_id, victim_id):
    """Credit a fighter/shuttle kill + tonnage to the cockpit and its pilot."""
    attacker = _hangar_attacker_id(parent_id, source_id)
    if attacker is None or not has_role(attacker, "cockpit"):
        return
    tons = _hangar_victim_tonnage(victim_id)
    _hangar_bump(attacker, "kills", 1)
    _hangar_bump(attacker, "tonnage", tons)
    pilot = get_inventory_value(attacker, "client_id", 0)
    if pilot:
        _hangar_bump(pilot, "kills", 1)
        _hangar_bump(pilot, "tonnage", tons)


def hangar_credit_damage(parent_id, source_id, amount):
    """Accumulate raw damage dealt by a cockpit (the 'impact' stat) on it + its pilot."""
    attacker = _hangar_attacker_id(parent_id, source_id)
    if attacker is None or not has_role(attacker, "cockpit"):
        return
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        return
    if amount <= 0:
        return
    _hangar_bump(attacker, "damage_dealt", amount)
    pilot = get_inventory_value(attacker, "client_id", 0)
    if pilot:
        _hangar_bump(pilot, "damage_dealt", amount)


# --- Air Wing roster (live during play) --------------------------------------
# One row per pilot. sortie / call_sign / completed_objectives are the hangar's
# own inventory; kills / tonnage are credited by the results addon's damage routes
# when it is loaded and default to 0 otherwise, so this roster works standalone.
def hangar_pilot_items():
    items = []
    try:
        client_ids = list(sbs.get_client_ID_list())
    except Exception:
        client_ids = []
    for cid in client_ids:
        sorties = get_inventory_value(cid, "sortie", 0)
        if not sorties:
            continue
        items.append(MastDataObject({
            "call_sign": str(get_inventory_value(cid, "call_sign", "pilot")),
            "sorties": sorties,
            "kills": get_inventory_value(cid, "kills", 0),
            "tonnage": get_inventory_value(cid, "tonnage", 0),
            "damage": int(get_inventory_value(cid, "damage_dealt", 0)),
            "objectives": get_inventory_value(cid, "completed_objectives", 0),
        }))
    return items


def hangar_pilot_template(item):
    gui_row("row-height: 1.2em;padding:6px;")
    gui_text(f"$text:{item.get('call_sign')};justify: left;")
    gui_row("row-height: 1.0em;padding:6px;")
    gui_text(f"$text:Sorties {item.get('sorties')}   Kills {item.get('kills')}   Tonnage {item.get('tonnage')}   Damage {item.get('damage')}   Objectives {item.get('objectives')};justify: left;font:gui-1")


def hangar_pilot_title_template():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text("$text:Air Wing;justify: left;")


def hangar_airwing_panel(cid, left, top, width, height):
    """Cockpit info-panel page: the live Air Wing roster. The panel framework sets
    up the section; we just fill it."""
    gui_list_box(hangar_pilot_items(), "", item_template=hangar_pilot_template, title_template=hangar_pilot_title_template, select=False)
    # keep the list off the panel's right edge
    gui_blank(style="col-width:0.5em")


def get_dock_name(so):
    """
    Get the name of the home hangar of the specified craft.
    Args:
        so: the ID or object representing the craft
    Returns:
        str: The name of the craft's home ship or station.
    """
    dock = get_science_selection(so)
    if not dock:
        return ""
    dock = to_space_object(dock)
    if not dock:
        return ""
    return f"{dock.name}"

def hangar_get_call_signs():
    ret = ["Aardvark","Badger","Chainsaw","Duckbill","Foxbat","Gargoyle","Hammerhead","Jellyfish","Kodiak","Lockjaw","Mongoose","Needlenose","Ostrich","Pancake","Rascal","Scarecrow","Tigershark","Vixen","Whiplash","Zealot"]
    random.shuffle(ret)
    return ret
     
    """Bartenders:
    Bubbles
    Cliff
    Flynn
    Highball
    Guff
    Jolly
    Mugsy
    Snout
    Tapper
    Whiskers"""

    


def hangar_get_docks(side):
    """
    Get a list of all stations and ships that have a hangar.
    Args:
        side (str): The side of the craft (currently unused)
    Returns:
        list[int]: A list of the IDs of all ships and stations with a hangar.
    """
    docks = has_link("hangar_craft")
    # crafts = all_roles(f"cockpit,standby,{side}")
    # docks = set()
    # for c in crafts:
    #     dock = get_science_selection(c)
    #     if dock is not None:
    #         docks.add(dock)
    return to_space_object_list(docks)

def hangar_get_crafts_at(dock_id):
    """
    Get all craft that are inside the specified hangar.
    Args:
        dock_id (int): The ID of the ship or station
    Returns:
        list[space_object]: A list of craft space_objects inside the hangar.
    """
    dock_id = to_id(dock_id)
    if dock_id is None:
        return []
    crafts = []
    all_crafts = all_roles(f"cockpit,standby,hangar")
    for c in all_crafts:
        dock = get_science_selection(c)
        if dock == dock_id:
            crafts.append(to_space_object(c))
    return crafts


def hangar_console_ship_template(item):
    gui_row("row-height: 1.0em;padding:13px;")
    gui_text(f"$text:{item.name};justify: left;")
    t = item.get_inventory_value("CRAFT_TYPE", "Fighter")
    gui_row("row-height: 1.0em;padding:13px;")
    gui_text(f"$text:{t};justify: left;font:gui-1")

    

def hangar_console_title_template():
    gui_row("row-height: 1.0em;padding:13px;background:#1578;")
    gui_text(f"$text:Ship;justify: left;")


def hangar_console_dock_template(item):
    gui_row("row-height: 1.0em;padding:13px;")
    gui_text(f"$text:{item.name};justify: left;")
    

def hangar_console_dock_title_template():
    gui_row("row-height: 1.0em;padding:13px;background:#1578;")
    gui_text(f"$text:Hangar Location;justify: left;")


