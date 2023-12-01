from sbs_utils.procedural.query import to_id, to_blob, to_object, to_list, to_set
from sbs_utils.procedural.roles import role, add_role, remove_role, all_roles,has_role
from sbs_utils.procedural.links import link,unlink
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.grid import grid_objects, grid_objects_at, grid_closest
from sbs_utils.procedural.spawn import grid_spawn
from sbs_utils.procedural.comms import comms_broadcast
from sbs_utils.procedural.space_objects import get_pos
from sbs_utils.helpers import FrameContext
from sbs_utils.fs import load_json_data, get_mission_dir_filename
from sbs_utils.tickdispatcher import TickDispatcher
import random
import sbs


_MAX_HP = 6
def grid_set_max_hp(max_hp):
    global _MAX_HP
    _MAX_HP = max_hp

def grid_get_max_hp():
    global _MAX_HP
    return _MAX_HP


_grid_data = None 
def grid_get_grid_data():
    global _grid_data
    if _grid_data is None:
        _grid_data = load_json_data(get_mission_dir_filename("grid_data.json"))
    return _grid_data

_themes = [
    {"silhouette": "#0F1F1F", "lines": "#2F4F4F", "nodes": "#778899", "silver": "LightYellow", "lime":"springgreen", "dc": ["slateblue", "CadetBlue", "royalblue"], "dc_damage": ["LightCoral", "LightSalmon", "Salmon"], "damage": "Crimson"},
    {"silhouette": "Gainsboro", "lines": "DarkKhaki", "nodes": "Khaki", "silver": "#003", "lime":"#060", "dc": ["slateblue", "CadetBlue", "royalblue"], "dc_damage": ["LightCoral", "LightSalmon", "Salmon"], "damage": "Crimson" },
    {"silhouette": "#0000bb66", "lines": "gray", "nodes": "darkgray", "silver": "#00a0a0", "lime":"#0ee", "dc": ["PaleGreen", "Cornsilk", "Lavender"], "dc_damage": ["LightCoral", "LightSalmon", "Salmon"], "damage": "#FE00FE"}
]

_grid_current_theme = 0
def grid_get_theme(theme=_grid_current_theme):
    if theme >= len(_themes):
        theme = 0
    return _themes[theme]

def grid_set_theme(theme):
    global _grid_current_theme
    if theme >= len(_themes):
        theme = 0
    _grid_current_theme  = theme


def grid_rebuild_grid_objects(id_or_obj, grid_data=None):
    if grid_data is None:
        grid_data = grid_get_grid_data()

    ship_id = to_id(id_or_obj)
    so = to_object(ship_id)
    if so is None: return 
    blob = to_blob(ship_id)
    if blob is None: return

    ship_grid  = grid_data.get(so.art_id)
    if ship_grid is None: return
    internal_items = ship_grid.get("grid_objects")
    if internal_items is None: return
    theme = grid_get_theme()


    #
    # Setup theme
    #
    blob.set("internal_color_ship_sillouette", theme["silhouette"],0)
    blob.set("internal_color_ship_lines", theme["lines"],0)
    blob.set("internal_color_ship_nodes", theme["nodes"],0)


    # Delete all grid objects
    items =grid_objects(ship_id)
    for k in items:
        # delete by id
        sbs.delete_grid_object(ship_id, k)


    #
    # Got data build grid objects
    #
    i=0 # used to create unique tag
    sensors = 0 # used to calculate max damage
    engines = 0
    weapons = 0
    shields = 0
    for g in internal_items:
        loc_x = int(g["x"])
        loc_y = int(g["y"])
        coords = f"{loc_x},{loc_y}"
        name_tag = f"{g['name']}:{coords}"
        color = g["color"]
        color = theme[color]

        go =  grid_spawn(ship_id,  name_tag, name_tag, loc_x, loc_y, g["icon"], color, g["roles"])
        go.blob.set("icon_scale", g["scale"]/2, 0)
        # save color so it cn be restored
        set_inventory_value(go.id, "color", color)
        #
        # Add link so query can find this relationship
        #       e.g. query to find engine grid objects on a ship
        #       linked_to(player_id, "grid_objects") & role("engine")
        #
        link(so, "grid_objects",go)
        add_role(go, "__undamaged__")
        i+=1

        #
        # Update max damage counts
        #
        roles = g["roles"].lower()
        if "sensor" in roles:
            sensors += 1
        if "engine" in roles:
            engines += 1
        if "shield" in roles:
            shields += 1
        if "weapon" in roles:
            weapons += 1

    blob.set('system_max_damage', weapons, sbs.SHPSYS.WEAPONS)
    blob.set('system_max_damage', engines, sbs.SHPSYS.ENGINES)
    blob.set('system_max_damage', sensors, sbs.SHPSYS.SENSORS)
    blob.set('system_max_damage', shields, sbs.SHPSYS.SHIELDS)
    blob.set('system_damage', 0, sbs.SHPSYS.WEAPONS)
    blob.set('system_damage', 0, sbs.SHPSYS.ENGINES)
    blob.set('system_damage', 0, sbs.SHPSYS.SENSORS)
    blob.set('system_damage', 0, sbs.SHPSYS.SHIELDS)

    #
    # This is needed to reset the coefficients after an explosion
    # set_damage_coefficients is in internal_damage
    #
    set_damage_coefficients(ship_id)
    grid_restore_damcons(ship_id)

    #
    # Create marker
    #
    v = sbs.vec3(0.5,0,0.5)
    loc = sbs.find_valid_grid_point_for_vector3(ship_id, v, 5)
    loc_x = loc[0]
    loc_y = loc[1]
    ship = ship_id & 0xFFFFFFFF
    marker_tag = f"marker:{ship}"
    # marker is named hallway
    # 23 flag, 101-filled square, 111
    marker_go = grid_spawn(ship_id, "marker", marker_tag, int(loc_x),int(loc_y), 101, "#9994", "#,marker") 
    marker_go.blob.set("icon_scale",1.5,0)
    marker_go_id =  to_id(marker_go)
    set_inventory_value(ship_id, "marker_id", marker_go_id)


def grid_restore_damcons(id_or_obj):
    ship_id = to_id(id_or_obj)

    hm = sbs.get_hull_map(ship_id)
    if hm is None: return
    theme = grid_get_theme()
    #
    # Get Colors from theme
    # 
    colors  = theme["dc"]
    damage_colors  = theme["dc_damage"]
    #
    # Create damcons/lifeforms
    #
    for i in range(3):
        # See if damcon exists
        _name = f"DC{i+1}"
        _test_go = hm.get_grid_object_by_name(_name)
        if _test_go is not None:
            _id = _test_go.unique_ID # _test_go is an object from the engine
            _blob = to_blob(_test_go.unique_ID)
            _blob.set("icon_color", colors[i], 0)
            # Hit points == MAX_HP
            set_inventory_value(_id, "HP", grid_get_max_hp() )
        else:
            v = sbs.vec3(0.5,0,0.5)
            point = sbs.find_valid_unoccupied_grid_point_for_vector3(ship_id, v, 5)
            dc = grid_spawn(ship_id, _name, _name, point[0],point[1],80, colors[i], "damcons, lifeform")
            dc.blob.set("icon_scale", 0.75,0 )
            _id = to_id(dc)
            _go = to_object(dc)
            set_inventory_value(_id, "color", colors[i])
            set_inventory_value(_id, "damage_color", damage_colors[i])
            set_inventory_value(_id, "idle_pos", (point[0], point[1]) )
            # Hit points == MAX_HP
            set_inventory_value(_id, "HP", grid_get_max_hp() )
            #
            # Create idle/rally point
            #
            dc_color = get_inventory_value(_id, "color", "white")
            marker_tag = f"{_go.name} rally point"
            idle_marker = grid_spawn(ship_id, marker_tag, marker_tag, point[0],point[1], 23, dc_color, "#,rally_point") 
            _blob = to_blob(idle_marker)
            _blob.set("icon_scale", 1.2, 0)
            set_inventory_value(_id, "idle_marker", to_id(idle_marker))


def grid_apply_system_damage(id_or_obj):
    ship_id = to_id(id_or_obj)
    if has_role(ship_id, "exploded"):
        return
    blob = to_blob(ship_id)

    undamaged_grid_objects = grid_objects(ship_id) & role("__undamaged__")
    damaged_grid_objects = grid_objects(ship_id) & role("__damaged__")
    the_roles =  ["weapon", "engine", "sensor", "shield"]


    for x in range(sbs.SHPSYS.MAX):
        # system_damaged = damaged_grid_objects & role(the_roles[x])
        system_damage = damaged_grid_objects & role(the_roles[x])
        cur = len(system_damage)
        blob.set('system_damage',cur, x)

    #should explode if len(undamaged_grid_objects)==0

    undamaged = undamaged_grid_objects & (role("weapon") | role("sensor") | role("shield") | role("engine")) 
    should_explode = len(undamaged) == 0
    set_damage_coefficients(ship_id)

    if should_explode:
        explode_player_ship(ship_id)
        respawn_seconds = get_inventory_value(ship_id, "respawn_time", None)
        if respawn_seconds is not None:
            def _do_respawn(t):
                respawn_player_ship(t.ship_id)    
                grid_rebuild_grid_objects(t.ship_id)

            t = TickDispatcher.do_once(_do_respawn, respawn_seconds)
            t.ship_id = ship_id

    return should_explode

def explode_player_ship(id_or_obj):
    ship_id = to_id(id_or_obj)
    if has_role(ship_id, "exploded"):
        return
    blob = to_blob(ship_id)
    so = to_object(ship_id)
    
    pos = get_pos(ship_id)
    if pos:
        sbs.create_transient(1, 0, ship_id, 0, 0, pos.x, pos.y, pos.z, "")  

    add_role(ship_id, "exploded")
    
    art_id = so.art_id
    set_inventory_value(ship_id, "art_id", art_id)
    so.set_art_id("invisible")
    # Reset the systems to no damage
    for sys in range(4):
        blob.set('system_damage', 0, sys)

def respawn_player_ship(id_or_obj):
    ship_id = to_id(id_or_obj)
    art_id = get_inventory_value(ship_id, "art_id")
    so = to_object(ship_id)
    engine_obj = so.space_object()
    FrameContext.context.sim.reposition_space_object(engine_obj, so.spawn_pos.x, so.spawn_pos.y, so.spawn_pos.z)
    so.set_art_id(art_id)
    remove_role(ship_id, "exploded")


def grid_damage_hallway(id_or_obj, loc_x, loc_y, damage_color):
    ship_id = to_id(id_or_obj)
    icon = 45 #fire   # 113 - Door

    name_tag = "hallway:{loc_x},{loc_y}"
    dam_go = grid_spawn(ship_id, name_tag, name_tag, loc_x,loc_y, icon, damage_color, "hallway, __damaged__") 
    link(ship_id, "damage", to_id(dam_go))


def set_damage_coefficients(id_or_obj):
    ship_id = to_id(id_or_obj)
    blob = to_blob(ship_id)
    if blob is None:
        return

    ship_gos = grid_objects(ship_id)
    # This ship's undamaged
    undamaged = ship_gos & role("__undamaged__")
    # This ships damaged
    damaged = ship_gos & role("__damaged__")
    #
    # get all eight systems damaged and undamaged
    #
    # arrays, Beam, Tube, Shield
    systems = [
        ("beam", "all_beam_damage_coeff",0), 
        ("torpedo", "all_tube_damage_coeff",0), 
        ("impulse", "impulse_damage_coeff",0), 
        ("warp", "warp_damage_coeff",0), 
        ("maneuver", "turn_damage_coeff",0),
        ("sensors", "sensor_damage_coeff",0),
        ("shield,fwd", "shield_damage_coeff",0), 
        ("shield,aft", "shield_damage_coeff",1)
        ]


    for system in systems:
        sys_role = system[0]
        _blob_name = system[1]
        _idx = system[2]

        _undam = undamaged & all_roles(sys_role)
        _dam = damaged & all_roles(sys_role)
        _total = max(1, len(_dam)+len(_undam))
        _coef = len(_undam) / _total
        # do print(f"damage {_coef} {_blob_name}")
        blob.set(_blob_name, _coef, _idx)

def grid_damage_grid_object(ship_id, grid_id, damage_color):
    blob = to_blob(grid_id)
    blob.set("icon_color", damage_color, 0)
    link(ship_id, "damage", grid_id) 
    add_role(grid_id, "__damaged__")
    remove_role(grid_id, "__undamaged__")

# def grid_mark_repaired_grid_object(ship_id, grid_id, repair_color):
#     blob = to_blob(grid_id)
#     blob.set("icon_color", repair_color, 0)
#     unlink(ship_id, "damage", grid_id) 
#     remove_role(grid_id, "__damaged__")
#     add_role(grid_id, "__undamaged__")

    


def convert_system_to_string(the_system):
    if isinstance(the_system, str):
        return the_system
    elif isinstance(the_system, sbs.SHPSYS):
        the_system = the_system.value
    
    the_roles =  ["weapon", "engine", "sensor", "shield"]
    hit_system = int(the_system)
    return the_roles[hit_system]

    
    

def grid_damage_system(id_or_obj, the_system):
    """ grid_damage_system

    damage a system using the grid objects of the ship

    :param id_or_obj: the ship to damage
    :type id_oe_obj: int, obj, close_data, spawn_data
    :param the_system: The system to damage, None picks random
    :type: string, int, sbs.SHPSYS
    :rtype: bool if a system was found to be damaged
    """
    ship_id = to_id(id_or_obj)
    if has_role(ship_id, "exploded"):
        return False
    if the_system is None:
        the_system = convert_system_to_string(random.randrange(4))

    the_system = convert_system_to_string(the_system)
    hittable = to_list(grid_objects(ship_id) & role("__undamaged__") & role(the_system))
    if len(hittable) == 0:
        return False
    go_id = random.choice(hittable)
    damage_color = grid_get_theme()["damage"]
    grid_damage_grid_object(ship_id, go_id, damage_color)
    add_role(go_id, "__damaged__")
    grid_apply_system_damage(ship_id)
    return True


###################
def grid_damage_pos(id_or_obj, loc_x, loc_y):
    ship_id = to_id(id_or_obj)
    go_set_at_loc = grid_objects_at(ship_id, loc_x, loc_y)
    #
    # If empty hallway hit, Drop damage down 
    #
    if len(go_set_at_loc) == 0:
        grid_damage_hallway(ship_id, loc_x,loc_y)
        return




def grid_take_internal_damage_at(id_or_obj, source_point, system_hit, damage_amount):
    ship_id = to_id(id_or_obj)
    # Make sure you don't take further damage
    if has_role(ship_id, "exploded"): return
    # Host is no more 
    hm = sbs.get_hull_map(ship_id)
    if hm is None: return

    loc_x = 0
    loc_y = 0
    damage_radius = int(((hm.w+hm.h) / 2 / 2) + 2) # Average halved + 2

    loc = sbs.find_valid_grid_point_for_vector3(ship_id, source_point, damage_radius)
    # Nothing to do END
    if len(loc)== 0: return
    #
    # pick a random system 
    # this can get overridden by finding a grid object in the hit location
    #
    blob = to_blob(ship_id)

    loc_x = loc[0]
    loc_y = loc[1]
    # do print(f"{loc_x} {loc_y} {EVENT.source_point.x} {EVENT.source_point.y} {EVENT.source_point.z}")
    go_set_at_loc = grid_objects_at(ship_id, loc_x, loc_y)
    #
    # If empty hallway hit, Drop damage down 
    #
    damage_color = grid_get_theme()["damage"]
    if len(go_set_at_loc) == 0:

        grid_damage_hallway(ship_id, loc_x, loc_y, damage_color)
        return grid_apply_system_damage(ship_id)
#
    # there are things here
    #
    #
    # Try several times to apply damage
    # if damage is applied just do it once
    #
    num_retry = 3
    injured_dc = set()
    for retry in range(num_retry):
        already_damaged = False
        
        for go_id in go_set_at_loc:
            #
            # track hit lifeforms
            #
            if has_role(go_id, "marker"): continue
            if has_role(go_id, "rally_point"): continue
            if has_role(go_id, "lifeform"):
                injured_dc.add(go_id)
                # don't mark lifeforms as damaged
                continue

            if has_role(go_id, "__damaged__"):
                already_damaged = True
                continue

            go = to_object(go_id)
            blob = to_blob(go_id)
            blob.set("icon_color", damage_color, 0)
            link(ship_id, "damage", go_id) 
            add_role(go_id, "__damaged__")
            remove_role(go_id, "__undamaged__")
        #
        # I all damage was new, we are done
        #
        if not already_damaged: break
        
        #
        # otherwise
        # find closest undamaged thing, not hallways
        # Using it's x,y as the new place to try
        #
        a_go = next(iter(go_set_at_loc))
        undam = grid_closest(a_go, role("__undamaged__") & grid_objects(ship_id))
        #
        # Just need one item to get x,y
        #
        if undam is not None:
            go_blob = to_blob(undam)
            loc_x = int(go_blob.get("curx", 0))
            loc_y = int(go_blob.get("cury", 0))

            #do print(f"{loc_x} {loc_y}")
            go_set_at_loc = grid_objects_at(ship_id, loc_x, loc_y)


    for d in injured_dc:
        hp =  get_inventory_value(d, "HP", 0)
        hp -= 1
        set_inventory_value(d, "HP", hp)
        go = to_object(d)
        blob = to_blob(d)
        dc_damage_color = get_inventory_value(d, "damage_color")
        dc_damage_color = damage_color if damage_color else damage_color

        blob.set("icon_color", dc_damage_color, 0)
        if hp <= 0:
            sbs.delete_grid_object(go.host_id, d)
            comms_broadcast(ship_id, f"{go.name} has perished", dc_damage_color)
            if go is not None:
                go.destroyed()
        else:
            comms_broadcast(ship_id, f"{go.name} has been hurt hp={hp}","yellow")


    return grid_apply_system_damage(ship_id)


def grid_repair_system_damage(id_or_obj, the_system=None):
    ship_id = to_id(id_or_obj)
    
    if the_system is None:
        the_system = convert_system_to_string(random.randrange(4))

    the_system = convert_system_to_string(the_system)
    fixable = to_list(grid_objects(ship_id) & role("__damaged__") & role(the_system))
    if len(fixable) == 0:
        return False
    go_id = random.choice(fixable)
    grid_repair_grid_objects(ship_id, go_id)
    grid_apply_system_damage(ship_id)
    return True



def grid_repair_grid_objects(player_ship, id_or_set, who_repaired=None):
    at_point = to_set(id_or_set)
    damcon_repairer = to_id(who_repaired)
    player_ship_id = to_id(player_ship)

    something_healed = False
    for id in at_point:
        #
        # Remove work order, even if no longer damaged
        # 
        if damcon_repairer is not None:
            unlink(damcon_repairer, "work-order", id)

        # Only deal with Damage
        if not has_role(id, "__damaged__"): continue 
        if has_role(id, "damcons"): continue
        go = to_object(id)
        if go is None: continue


        # Have to unlink this so it is no longer seen
        unlink(go.host_id, "damage", id)
        remove_role(id, "__damaged__")
        add_role(id, "__undamaged__")


        # If hallway damage delete
        # else restore color and repair system
        system_heal = None
        if has_role(id, "hallway"):
            sbs.delete_grid_object(go.host_id, id)
            go.destroyed()
        #
        # This is a room, fix
        #
        else:
            blob = to_blob(id)
            color = get_inventory_value(id, "color")

            if color is None:
                color = "purple"
            blob.set("icon_color", color, 0)
            if has_role(id, "sensor"):
                system_heal = sbs.SHPSYS.SENSORS
            elif has_role(id, "weapon"):
                system_heal = sbs.SHPSYS.WEAPONS
            elif has_role(id, "engine"):
                system_heal = sbs.SHPSYS.ENGINES
            elif has_role(id, "shield"):
                system_heal = sbs.SHPSYS.SHIELDS
        #
        # 
        #
        if system_heal is not None:
            ship_blob = to_blob(player_ship_id)
            something_healed = True
        
            current = ship_blob.get('system_damage', system_heal)
            if current >0:
                ship_blob.set('system_damage', current-1 , system_heal)
            else:
                ship_blob.set('system_damage', 0 ,  system_heal)

    #
    # Update the damage coefficients if a system was healed
    # Label is in internal_damage, Expects DAMAGE_ORIGIN_ID
    #

    if something_healed:
        set_damage_coefficients(player_ship_id )
    
