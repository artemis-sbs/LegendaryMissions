from sbs_utils.procedural.gui.property_listbox import _gui_properties_items
from sbs_utils.procedural.roles import has_role, has_roles
from sbs_utils.mast.mast_globals import debug_print, MastGlobals
from sbs_utils.procedural.style import apply_control_styles
from sbs_utils.procedural.torpedoes import torpedo_get_available_types_for_ship, torpedo_get_count_for_ship, torp_get_attribute_value
from sbs_utils.procedural.gui.message import gui_message
from sbs_utils.procedural.gui.section import gui_sub_section
from sbs_utils.procedural.ship_data import get_ship_data, get_ship_data_for
from sbs_utils.procedural.gui.button import gui_button
from sbs_utils.procedural.gui.icon import gui_icon
from sbs_utils.procedural.inventory import  get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import get_science_selection, get_weapons_selection, to_object, get_comms_selection, get_data_set_value, to_blob
from sbs_utils.procedural.links import linked_to
from sbs_utils.helpers import FrameContext, gui_text_escape
from sbs_utils.vec import Vec3
from sbs_utils.procedural.execution import labels_get_type, gui_get_variable, AWAIT, gui_set_variable


def gamemaster_show_nav_area(ORIGIN_ID, pos, size_delta, text, selection_type, color):
    x = pos.x
    y = pos.z

    sim = FrameContext.context.sim

    size = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SIZE", 5000)
    size += size_delta
    size = max(min(50000, size), 2000)
    if size_delta == 0:
        size = 5000

    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SIZE", size)
    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_x", x)
    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_y", y)
    
    nav_id = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SELECT_ID", None)
    if nav_id:
        sim.delete_navpoint_by_id(nav_id)

    nav_id = sim.add_navarea(x-size, y-size,x+size, y-size,x-size, y+size,x+size, y+size, text, color)
    nav = sim.get_navpoint_by_id(nav_id)

    nav.visibleToShip = ORIGIN_ID
    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SELECT_ID", nav_id)

def gamemaster_move_nav_area(ORIGIN_ID, pos, size_delta=0, selection_type="lmb"):
    """
    Move a nav area without changing text or color, and only changing the size if desired.
    """
    x = pos.x
    y = pos.z
    text = "Game Master"
    color = "#040" #green

    # navarea.

    sim = FrameContext.context.sim

    size = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SIZE", 5000)
    size += size_delta

    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SIZE", size)
    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_x", x)
    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_y", y)
    
    nav_id = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SELECT_ID", None)

    if nav_id:
        text = nav_id.text
        color = nav_id.color
        sim.delete_navpoint_by_id(nav_id)


    nav_id = sim.add_navarea(x-size, y-size,x+size, y-size,x-size, y+size,x+size, y+size, text, color)
    nav = sim.get_navpoint_by_id(nav_id)

    nav.visibleToShip = ORIGIN_ID
    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SELECT_ID", nav_id)

def gamemaster_get_size(ORIGIN_ID, selection_type="lmb"):
    """
    Get the gamemaster's nav area size.
    """
    #TODO: Change this to use 3D.
    size = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SIZE", 5000)
    return size

def gamemaster_get_pos(ORIGIN_ID, selection_type="lmb"):
    """
    Get the position of the gamemaster's selection.
    Args:
        ORIGIN_ID (int): the gamemaster "ship"
        selection_type (str): The button click used (left or right). "lmb" or "rmb" standing for "left/right mouse button". Default is "lmb".
    """
    x = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_x", 0)
    # The more user-intuitive "y" is used for the inventory key, but it's actually "z"
    z = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_y", 0)

    y = 1

    _other = 0
    if selection_type == "rmb":
        _other = get_weapons_selection(ORIGIN_ID)
    elif selection_type == "lmb":
        _other = get_science_selection(ORIGIN_ID)

    if _other==0:
        return Vec3(x,y,z)
    _obj = to_object(_other)
    if _obj is None:
        return Vec3(x,y,z)

    # While the object's vertical axis value might be one value, we increase it by 1 to avoid issues with black holes. Minimal effect on anything else.
    v = Vec3(_obj.pos)
    v.y = v.y + 1
    return v
    

    

from sbs_utils.procedural.gui import gui_row, gui_text, gui_text_area

from sbs_utils.procedural.gui import gui_panel_widget_show, gui_panel_widget_hide, gui_slider, gui_blank, gui_message_label

def gamemaster_panel_camera_show(cid, left,top,width, height):
    gui_panel_widget_show(cid, left,top,width, height, "3dview")
    # For 3D view
    gui_blank()

    dl = gui_slider("low: 0; high:300.0;", style="col-width:20px;", var="dolly")
    gui_row("row-height: 20px;")
    ob = gui_slider("low: 0.0; high:360.0;", var="orbit")
    gui_message_label(dl, "gamemaster_move_camera")
    gui_message_label(ob, "gamemaster_move_camera")


def gamemaster_panel_camera_hide(cid, left,top,width, height):
    gui_panel_widget_hide(cid, left,top,width, height, "3dview")


def gamemaster_panel_instructions(cid, left,top,width, height):
    task = FrameContext.task
    if task is None:
        return
    gm_text = task.get_variable("GAMEMASTER_INSTRUCTIONS", "Game Master instructions^set the variable GAMEMASTER_INSTRUCTIONS to see it here.")

    gui_text_area(gm_text)

def gm_get_menu_items_tree(parent_menu=None):
    """
    Get the menu items for the gamemaster
    Args:
        parent_menu: The path of the parent_menu, e.g. `"gm_menu/terrain"`
    """
    if parent_menu is None:
        labels = labels_get_type("gm_menu")
    else:
        labels = labels_get_type(parent_menu)
    items = {}
    for label in labels:
        path = label.get_inventory_value("type")
        if path is None:
            continue
        if parent_menu is not None:
            items[path] = label
            continue
        tree = path.split("/")
        if len(tree) == 2:
            items[path] = label
    return items

def gm_get_mast_global_function(func_name):
    """
    Get the function of the given name, if it exists.
    Args:
        func_name (str): The function name
    Returns:
        Callable | None: The function or None
    """
    return MastGlobals.globals.get(func_name)

def gm_show_menu_contents(cid, left, top, width, height, widget):
    """
    Build the menu for the gamemaster
    """
    newItems = []
    items = gm_get_menu_items_tree()
    for k, v in items.items():
        data = {"name": k, "on_press": "GM_Menu_Select", "args": {"label": v.name}}
        newItems.append(data)
    return newItems

def gm_build_menu_icons(item):
    """Builds the icons to press to go to each menu"""
    icon = item.get_inventory_value("icon_index")
    icon_color = item.get_inventory_value("icon_color")
    if icon_color is None:
        icon_color = "#14749aa8"
    if icon is not None:
        GAMEMASTER_CONSOLE_ICON_SIZE = gui_get_variable("GAMEMASTER_CONSOLE_ICON_SIZE")
        gui_row(f"row-height: {GAMEMASTER_CONSOLE_ICON_SIZE}px;")
        if isinstance(icon, int) or icon.isdigit():
            gui_icon(f"icon_index: {icon};color: {icon_color};")
        else:
            gui_text(f"$text: {icon}; color: {icon_color}")
    else:
        gui_text(item.get_inventory_value("type"))
        print("Icon is None")

def sort_menu_labels(a,b):
    print("Sorting")
    if a is None and b is not None:
        return False
    if b is None and a is not None:
        return True
    if a is None and b is None:
        return True
    a1 = a.get_inventory_value("priority")
    b1 = b.get_inventory_value("priority")
    return a1 > b1

def gm_spawn_type_button(props="", style=""):
    button = gui_sub_section(f"click_background: #5555;click_text:;{style};")
    with button:
        gui_row("row-height: 1em;")
        gui_text(f"{props}")
    return button

origins_sides_roles = None
def gm_get_origins_sides_roles() -> dict:
    """
    Gets sets of origins, sides, and roles defined in shipData as a dict.
    Caches the data after first use, since the data won't change.
    NOTE: Sides that are specified in shipData may not be initialized in-game!
    
    Returns:
        dict: A dictionary containing origins, roles, and sides used in shipData.
    """
    global origins_sides_roles
    if origins_sides_roles is not None:
        return origins_sides_roles
    data = get_ship_data()["#ship-list"] # A list of ship dict entries
    origin_set = set()
    side_set = set()
    role_set = set()

    for ship in data:
        # key = ship.get("key")
        # print(key)
        o = ship.get("origin")
        if o == "monster" or o == "Roklithoid":
            continue
        if o is not None:
            origin_set.add(o + " ")
        s = ship.get("side")
        if s is not None:
            side_set.add(s + " ")
        r = ship.get("roles")
        if r is not None:
            r_list = r.split(",")
            for _r in r_list:
                role_set.add(_r.strip() + " ")
        else:
            key = ship.get("key")
            # print(f"{key} doesn't have a role specified in shipData...")

    origins_sides_roles = {
        "origins": origin_set,
        "sides": side_set,
        "roles": role_set
    }
    return origins_sides_roles



def filter_ship_data_generically(text, required_roles=None, required_origin=None, required_side=None):
    """
    Filters ship data by search text and optional ship-data requirements.

    Each whitespace-separated search term must match somewhere in the key,
    name, origin, side, roles, or description.
    Every required role must be present. Origin and side requirements are
    matched case-insensitively after surrounding whitespace is removed.

    Args:
        text (str): The text for which to search.
        required_roles (str | iterable[str] | None): Roles every result must have.
        required_origin (str | None): Origin every result must have.
        required_side (str | None): Side every result must have.

    Returns:
        list: The matching ship data dictionaries.

    """
    data = get_ship_data()
    if data is None:
        return []

    def normalize_requirement(value):
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        return [str(item).strip().lower() for item in value if str(item).strip()]

    needle = "" if text is None else str(text).strip().lower()
    search_terms = needle.split()
    required_roles = normalize_requirement(required_roles)
    required_origin = normalize_requirement(required_origin)
    required_side = normalize_requirement(required_side)

    results = []
    for ship in data.get("#ship-list", []):
        if not ship.get("key"):
            continue

        key = str(ship.get("key", ""))
        name = str(ship.get("name", ""))
        origin = str(ship.get("origin", ""))
        side = str(ship.get("side", ""))
        roles = str(ship.get("roles", ""))
        long_desc = str(ship.get("long_desc", ""))

        ship_origin = origin.strip().lower()
        ship_side = side.strip().lower()
        ship_roles = {role.strip().lower() for role in roles.split(",") if role.strip()}

        if required_origin and ship_origin not in required_origin:
            continue
        if required_side and ship_side not in required_side:
            continue
        if not all(role_name in ship_roles for role_name in required_roles):
            continue

        # Join all the text into one string
        haystack = "|".join([
            key,
            name,
            origin,
            side,
            roles,
            long_desc
        ]).lower()

        if all(term in haystack for term in search_terms):
            results.append(ship)

    return results

def layout_item_update_style(item, style):
    """
    Update the style of a layout item.
    """
    apply_control_styles(".text", style, item, FrameContext.task)
    item.mark_layout_dirty()

def gm_ship_spawn_select_template(item):
    # gui_row("padding:13px;")
    # print(f"{item}")
    # ss = gui_get_variable("set_string")
    # if not ss:
    #     if item is None:
    #         print("Item is None!")
    #     else:
    #         print(item)
    #     gui_set_variable("set_string",True)
    art = item.get("artfileroot", "")
    key = item.get("key","")
    # gui_ship(f"{art}", style="col-width:50px;padding:0,0,5px,0;")
    dat = get_ship_data_for(key)
    name = "Unknown ship"
    origin = "Unknown origin"
    roles = "No roles found"
    long_desc = "Description"
    if dat is not None:
        name = dat.get("name") or name
        origin = dat.get("origin") or origin
        roles = dat.get("roles") or roles
        roles = ", ".join(roles.split(","))
        long_desc = dat.get("long_desc") or long_desc
    else:
        print(f"data is None for {art}")
    name = gui_text_escape(str(name)).strip()
    origin = gui_text_escape(str(origin)).strip()
    roles = gui_text_escape(str(roles)).strip()
    long_desc = gui_text_escape(str(long_desc)).strip()
    # gui_row("row-height: min-content;")
    # gui_row()
    # with gui_sub_section("row-height: min-content;"):
        # gui_row("row-height:1em;")
        # # Escape the user-entered ship name so a ':' or ';' in it can't inject
        # # style properties or break the justify/font that follow (issue #569).
        # ship_label = gui_text_escape(f"{item.name} - {item.side}")
        # gui_text(f"$text:{ship_label};justify: left;font:gui-3;")
    gui_row("row-height: 3em;")
    # Explicit col-width on both sides: unset columns default to a 1fr/1fr
    # split, not to their natural size, so the ship render and the text
    # column need their share stated here.
    # with gui_sub_section(style="col-width: 30px;"):
    #     gui_ship(f"$type:{art};angle:45;")
    with gui_sub_section("padding: 2px;"):
        gui_row("row-height:1em; border: 1px,1px,1px,1px; border-color: #3139af; background-color: #000444;")
        gui_text(f"$text:{name};justify: left;font:gui-2;color:#bbb;", "col-width: content;")
        # gui_row("row-height: 1em;")
        gui_blank()
        gui_text(f"$text:{origin};","col-width: content;")
        gui_row("row-height: 2em;")
        gui_text(f"$text:Roles: {roles};")
        # row-height: min-content falls back to flex inside a listbox item
        # template (content-sizing keywords don't hug content there), so an
        # unstyled row does the same thing without implying it measures.
        # gui_row()
        # gui_text(f"$text:{long_desc}","overflow: shrink;")



_SYSTEM_INDEX_NAMES = {
    0: "Weapons",
    1: "Engines",
    2: "Sensors",
    3: "Shields",
}

_ELITE_ABILITY_LABELS = {
    "elite_low_vis": "LowVis",
    "elite_main_scn_invis": "MainScanInvis",
    "elite_drone_launcher": "DroneLauncher",
    "elite_anti_mine": "AntiMine",
    "elite_anti_torpedo": "AntiTorpedo",
}


def _gm_get_ship_data_fields(obj):
    ship_key = getattr(obj, "ship_data_key", None) or getattr(obj, "art_id", "")
    sd = get_ship_data_for(ship_key) if ship_key else None
    if not isinstance(sd, dict):
        sd = {}

    ship_type = sd.get("name") or ship_key or obj.name
    origin = sd.get("origin") or getattr(obj, "origin", "") or "unknown"
    side = sd.get("side") or getattr(obj, "side", "") or "unknown"
    return ship_type, origin, side, sd


def _gm_format_shields(obj_id):
    count = int(get_data_set_value(obj_id, "shield_count", 0) or 0)
    if count <= 0:
        return "none"

    parts = []
    for i in range(count):
        cur = get_data_set_value(obj_id, "shield_val", i)
        mx = get_data_set_value(obj_id, "shield_max_val", i)
        if cur is None:
            cur = 0
        if mx is None:
            mx = 0
        parts.append(f"{i + 1}:{round(float(cur), 1)}/{round(float(mx), 1)}")
    return ", ".join(parts)


def _gm_format_roles(obj):
    try:
        roles = sorted(obj.get_roles())
    except Exception:
        roles = []
    return ", ".join(roles) if roles else "none"


def _gm_format_system_damage(obj_id):
    rows = []
    seen_indices = set()

    for i in range(30):
        label = get_data_set_value(obj_id, "eng_control_label", i)
        if not label:
            continue
        sys_index = int(get_data_set_value(obj_id, "eng_control_type_index", i) or i)
        if sys_index in seen_indices:
            continue
        seen_indices.add(sys_index)

        cur = float(get_data_set_value(obj_id, "system_damage", sys_index) or 0)
        mx = float(get_data_set_value(obj_id, "system_max_damage", sys_index) or 0)
        rows.append(f"{label}: {round(cur, 1)}/{round(mx, 1)}")

    if not rows:
        for idx, name in _SYSTEM_INDEX_NAMES.items():
            mx = float(get_data_set_value(obj_id, "system_max_damage", idx) or 0)
            if mx <= 0:
                continue
            cur = float(get_data_set_value(obj_id, "system_damage", idx) or 0)
            rows.append(f"{name}: {round(cur, 1)}/{round(mx, 1)}")

    return "^".join(rows) if rows else "none"


def _gm_format_npc_hull(obj_id, ship_data):
    base_hull = ship_data.get("hullpoints", None)
    if base_hull is not None:
        base_hull = float(base_hull)

    total_max = 0.0
    total_dmg = 0.0
    for idx in range(4):
        mx = float(get_data_set_value(obj_id, "system_max_damage", idx) or 0)
        cur = float(get_data_set_value(obj_id, "system_damage", idx) or 0)
        total_max += mx
        total_dmg += cur

    if total_max > 0 and base_hull is not None:
        ratio = max(0.0, min(1.0, 1.0 - (total_dmg / total_max)))
        current_hull = round(base_hull * ratio, 2)
        return f"{current_hull}/{base_hull}"

    if base_hull is not None:
        return str(base_hull)

    if total_max > 0:
        return f"{round(max(0.0, total_max - total_dmg), 1)}/{round(total_max, 1)}"

    return "unknown"


def _gm_format_npc_abilities(obj_id, obj):
    abilities = []

    for r in obj.get_roles():
        if r.startswith("elite_"):
            abilities.append(_ELITE_ABILITY_LABELS.get(r, r))

    for key, label in _ELITE_ABILITY_LABELS.items():
        if get_data_set_value(obj_id, key, 0):
            abilities.append(label)

    # Preserve order while removing duplicates.
    seen = set()
    deduped = []
    for a in abilities:
        if a in seen:
            continue
        seen.add(a)
        deduped.append(a)

    return ", ".join(deduped) if deduped else "none"


def _gm_format_player_upgrades(obj_id):
    names = []
    for up_id in linked_to(obj_id, "__UPGRADE__"):
        up = to_object(up_id)
        if up is None:
            continue

        label = getattr(up, "label", None)
        display = None
        if label is not None and hasattr(label, "get_inventory_value"):
            display = label.get_inventory_value("display_name", None)
        if not display and label is not None and hasattr(label, "name"):
            display = label.name
        if not display and label is not None:
            display = str(label)
        if display:
            names.append(display)

    return ", ".join(sorted(names)) if names else "none"


def _gm_format_fleet_info(obj_id):
    fleet_id = get_inventory_value(obj_id, "my_fleet_id", None)
    if not fleet_id:
        return "none", "none"

    fleet_obj = to_object(fleet_id)
    fleet_name = getattr(fleet_obj, "name", None) if fleet_obj is not None else None
    if not fleet_name:
        fleet_name = f"Fleet {fleet_id}"

    members = sorted([sid for sid in linked_to(fleet_id, "ship_list") if sid is not None])
    if not members:
        return fleet_name, "unknown"

    flagship_id = members[0]
    if flagship_id == obj_id:
        flagship_ref = "This ship is the flagship"
    else:
        flagship_obj = to_object(flagship_id)
        flagship_name = getattr(flagship_obj, "name", None) if flagship_obj is not None else None
        if not flagship_name:
            flagship_name = str(flagship_id)
        flagship_ref = f"{flagship_name} ({flagship_id})"

    return fleet_name, flagship_ref


def gm_selected_fleet_data(obj_id):
    """Return the selected ship's fleet name and its current ship members."""
    fleet_id = get_inventory_value(obj_id, "my_fleet_id", None)
    if not fleet_id:
        return None, []

    fleet_obj = to_object(fleet_id)
    fleet_name = getattr(fleet_obj, "name", None) if fleet_obj is not None else None
    if not fleet_name:
        fleet_name = f"Fleet {fleet_id}"

    ships = []
    for ship_id in linked_to(fleet_id, "ship_list"):
        ship = to_object(ship_id)
        if ship is None:
            continue
        ship_type, origin, _side, ship_data = _gm_get_ship_data_fields(ship)
        roles = ship_data.get("roles") or _gm_format_roles(ship) or "none"
        ships.append({
            "ship": ship,
            "ship_id": ship_id,
            "name": getattr(ship, "name", None) or str(ship_id),
            "type": ship_type,
            "origin": origin,
            "roles": roles,
            "side":_side
        })

    ships.sort(key=lambda item: str(item.get("name", "")).lower())
    return fleet_name, ships


def gm_selected_fleet_ship_template(item):
    """Render one removable ship entry in the selected-fleet listbox."""
    name = gui_text_escape(str(item.get("name", "Unknown ship")))
    ship_type = gui_text_escape(str(item.get("type", "unknown")))
    origin = gui_text_escape(str(item.get("origin", "unknown")))
    roles = gui_text_escape(str(item.get("roles", "none")))
    side = gui_text_escape(str(item.get("side","unknown")))

    gui_row("row-height: 3.5em;")
    with gui_sub_section():
        gui_row("row-height: 1.2em;")
        gui_text(f"$text:{name};font:gui-2;color:#bbb;","col-width:content;")
        gui_blank()
        gui_text(f"$text:{side};","col-width: content;")
        gui_blank()
        remove_button = gui_text(f"$text:X;","click_background: red; click_text:;col-width: content;")
        gui_row("row-height: 1.1em;")
        gui_text(f"$text:Type: {ship_type}  Origin: {origin};")
        gui_row("row-height: 1.1em;")
        gui_text(f"$text:Roles: {roles};")
        # remove_button = gui_button("Remove", data=item)
        remove_button.data = item
        gui_message(remove_button, "gm_remove_selected_fleet_ship")


def gm_selected_object_details(gm_id):
    """Build a multi-line details block for the GM-selected object."""
    sel = get_inventory_value(gm_id, "gamemaster_prev_selection", None)
    if not sel:
        return "Selected Object^none"

    obj = to_object(sel)
    if obj is None:
        return f"Selected Object^Missing object id: {sel}"

    ship_type, origin, side, ship_data = _gm_get_ship_data_fields(obj)
    obj_id = obj.id
    lines = [
        f"Selected Object: {obj.name}",
        f"Object ID: {obj_id}",
    ]

    if obj.is_terrain:
        lines.append("Type: Terrain")
        lines.append(f"Terrain type: {ship_type}")
        return "^".join(lines)

    if hasattr(obj, "has_role") and obj.has_role("station"):
        lines.append("Type: Station")
        lines.append(f"Station type: {ship_type}")
        lines.append(f"Station origin: {origin}")
        lines.append(f"Side: {side}")
        lines.append(f"Current shield strength values: {_gm_format_shields(obj_id)}")
        armor = get_data_set_value(obj_id, "armor", 0)
        armor_max = get_data_set_value(obj_id, "armorMax", 0)
        lines.append(f"Current armor: {round(float(armor or 0), 1)}/{round(float(armor_max or 0), 1)}")
        lines.append(f"Current roles: {_gm_format_roles(obj)}")
        return "^".join(lines)

    if obj.is_player or (hasattr(obj, "has_role") and obj.has_role("__player__")):
        lines.append("Type: Player Ship")
        lines.append(f"Ship type: {ship_type}")
        lines.append(f"Ship origin: {origin}")
        lines.append(f"Side: {side}")
        lines.append(f"Current shield strength values: {_gm_format_shields(obj_id)}")
        lines.append("Current damage to each system:")
        lines.append(_gm_format_system_damage(obj_id))
        lines.append(f"Current roles: {_gm_format_roles(obj)}")
        lines.append(f"Available upgrades: {_gm_format_player_upgrades(obj_id)}")
        return "^".join(lines)

    lines.append("Type: NPC Ship")
    lines.append(f"Ship type: {ship_type}")
    lines.append(f"Ship origin: {origin}")
    lines.append(f"Side: {side}")
    fleet_name, flagship_ref = _gm_format_fleet_info(obj_id)
    lines.append(f"Fleet name: {fleet_name}")
    lines.append(f"Flagship reference: {flagship_ref}")
    lines.append(f"Current shield strength values: {_gm_format_shields(obj_id)}")
    lines.append(f"Current hull points: {_gm_format_npc_hull(obj_id, ship_data)}")
    lines.append(f"Current special abilities: {_gm_format_npc_abilities(obj_id, obj)}")
    lines.append(f"Current roles: {_gm_format_roles(obj)}")
    return "^".join(lines)

class GmDetailSection:
    """A header row plus a collapsible body row; `visible` (by object type) and `collapsed` (by user) are independent."""

    def __init__(self, header_row, body_row):
        self.header_row = header_row
        self.body_row = body_row
        self.visible = True
        self.collapsed = False
        self._apply()

    def _apply(self):
        self.header_row.show(self.visible)
        self.body_row.show(self.visible and not self.collapsed)

    def show(self, visible):
        self.visible = bool(visible)
        self._apply()

    def toggle(self):
        self.collapsed = not self.collapsed
        self._apply()


class GmSelectionDetails:
    """Fills the selected-object details panel; widgets are registered by the MAST layout code."""

    def __init__(self, gm_id):
        self.gm_id = gm_id
        self.sections = {}
        self.texts = {}
        self.shields = []
        self.systems = []
        self.hull = None

    # --- registration (called while the layout is built) ---
    def add_section(self, key, header_row, body_row):
        section = GmDetailSection(header_row, body_row)
        self.sections[key] = section
        return section

    def add_text(self, key, widget):
        self.texts[key] = widget

    def add_gauge(self, key, gauge):
        """key: shield and system pool in order; armor and hull are single gauges."""
        if key == "shield":
            self.shields.append(gauge)
        elif key == "system":
            self.systems.append(gauge)
        else:
            setattr(self, key, gauge)

    # --- data gathering ---
    @staticmethod
    def _num(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _shield_values(self, obj_id):
        """[(label, cur, max)] for each shield arc."""
        count = int(self._num(get_data_set_value(obj_id, "shield_count", 0)))
        return [
            (f"Shield {i + 1}",
             self._num(get_data_set_value(obj_id, "shield_val", i)),
             self._num(get_data_set_value(obj_id, "shield_max_val", i)))
            for i in range(min(count, len(self.shields)))
        ]

    def _system_values(self, obj_id):
        """[(label, damage, max_damage)] for each damageable system (damage grows)."""
        rows = []
        seen = set()
        for i in range(30):
            label = get_data_set_value(obj_id, "eng_control_label", i)
            if not label:
                continue
            idx = int(get_data_set_value(obj_id, "eng_control_type_index", i) or i)
            if idx in seen:
                continue
            seen.add(idx)
            rows.append((str(label), self._num(get_data_set_value(obj_id, "system_damage", idx)),
                         self._num(get_data_set_value(obj_id, "system_max_damage", idx))))
        if not rows:
            for idx, name in _SYSTEM_INDEX_NAMES.items():
                mx = self._num(get_data_set_value(obj_id, "system_max_damage", idx))
                if mx > 0:
                    rows.append((name, self._num(get_data_set_value(obj_id, "system_damage", idx)), mx))
        return rows[:len(self.systems)]

    def _npc_hull_values(self, obj_id, ship_data):
        """(current, max) hull points, or None when the hull is unknown."""
        base = ship_data.get("hullpoints", None)
        if base is None:
            return None
        total_max = 0.0
        total_dmg = 0.0
        for idx in range(4):
            mx = get_data_set_value(obj_id, "system_max_damage", idx, 0)
            cur = get_data_set_value(obj_id, "system_damage", idx, 0)
            total_max += mx
            total_dmg += cur
        max_hullpoints = total_max + base
        current_hullpoints = max_hullpoints - total_dmg
        return current_hullpoints, max_hullpoints

    # --- widget updates ---
    def _set_text(self, key, label, value):
        self.texts[key].update("text:" + gui_text_escape(f"{label}: {value}") + ";")

    @staticmethod
    def _set_gauges(gauges, rows):
        """Fill a pool of gauges from (label, value, max) rows; hide the spare ones."""
        for i, g in enumerate(gauges):
            if i < len(rows):
                label, value, mx = rows[i]
                g.update(value=value, max=mx, label=label)
                g.show(True)
            else:
                g.show(False)

    def refresh_data(self):
        """Push the GM-selected object's data into the widgets; hide sections that do not apply."""
        sel = get_inventory_value(self.gm_id, "gamemaster_prev_selection", None)
        obj = to_object(sel) if sel else None
        sections = self.sections

        if obj is None:
            for s in sections.values():
                s.show(False)
            sections["general"].show(True)
            self.texts["name"].update("text:No object selected.;")
            for k in ("id", "type", "origin", "side"):
                self._set_text(k, k.capitalize(), "-")
            return

        obj_id = obj.id
        ship_type, origin, side, ship_data = _gm_get_ship_data_fields(obj)
        is_station = has_role(obj_id, "station")
        is_player = has_role(obj_id,"__player__")
        is_terrain = obj.is_terrain
        is_npc = has_roles(obj_id,"__npc__,ship")
        is_monster = has_role(obj_id, "monster")
        kind = "Terrain" if is_terrain else "Monster" if is_monster else "Station" if is_station else "Player Ship" if is_player else "NPC Ship"

        self.texts["name"].update("text:" + gui_text_escape(str(obj.name)) + ";font:gui-2;")
        self._set_text("id", "ID", obj_id)
        self._set_text("type", f"Type ({kind})", ship_type)
        self._set_text("origin", "Origin", origin)
        self._set_text("side", "Side", side)
        # self._set_text("roles", "Roles", _gm_format_roles(obj))

        shield_rows = [] if is_terrain else self._shield_values(obj_id)
        self._set_gauges(self.shields, shield_rows)
        sections["defense"].show(shield_rows)

        show_hull = False
        if is_station:
            show_hull = True
            armor_max = self._num(get_data_set_value(obj_id, "armorMax", 0))
            self.hull.update(value=self._num(get_data_set_value(obj_id, "armor", 0)), max=armor_max, label="Armor")
        elif is_npc:
            hull = self._npc_hull_values(obj_id, ship_data)
            show_hull = hull is not None
            if show_hull:
                self.hull.update(value=hull[0], max=hull[1], label="Hull")


        systems = self._system_values(obj_id) if is_player or is_npc else []
        # Damage grows, so the bar shows what is left of each system.
        self._set_gauges(self.systems, [(n, max(0.0, mx - d), mx) for n, d, mx in systems])
        sections["systems"].show(bool(systems) or show_hull)

        sections["fleet"].show(is_npc)
        if is_npc:
            fleet_name, flagship = _gm_format_fleet_info(obj_id)
            self._set_text("fleet", "Fleet", fleet_name)
            self._set_text("flagship", "Flagship", flagship)

        sections["extras"].show(is_npc or is_player)
        self._set_text("abilities", "Abilities", _gm_format_npc_abilities(obj_id, obj) if is_npc else "n/a")
        self._set_text("upgrades", "Upgrades", _gm_format_player_upgrades(obj_id) if is_player else "n/a")
        sections["general"].show(True)


def gm_selection_details_build(gm_id):
    """Builder exposed to MAST (which only sees functions); the handler is kept with gui_set_variable."""
    return GmSelectionDetails(gm_id)


def get_beam_blob_keys():
    return [
        "beamArcWidth",
        "beamBarrelAngle",
        "beamCycleTime",
        "beamDamage",
        "beamRange",
        "beamTimer",
        "beam_damage_coeff",
        "beam_upgrade_coeff"
    ]

def gm_get_beam_data_for(id_or_obj):
    blob = to_blob(id_or_obj)
    beams = list()
    if blob is None:
        return beams
    num_beams = blob.get("beamCount",0)
    if num_beams is None:
        return beams

    for i in range(num_beams):
        arc_width = blob.get("beamArcWidth", i)
        barrel_angle = blob.get("beamBarrelAngle", i)
        cycle_time = blob.get("beamCycleTime", i)
        damage = blob.get("beamDamage", i)
        beam_range = blob.get("beamRange", i)
        timer = blob.get("beamTimer", i)
        damage_coeff = blob.get("beam_damage_coeff", i)
        upgrade_coeff = blob.get("beam_upgrade_coeff", i)

        data = {
            "ship":id_or_obj,
            "index":i,
            "arc_width":arc_width,
            "barrel_angle":barrel_angle,
            "cycle_time":cycle_time,
            "damage":damage,
            "beam_range":beam_range,
            "timer":timer,
            "damage_coeff":damage_coeff,
            "upgrade_coeff": upgrade_coeff
        }
        beams.append(data)
    return beams

def gm_list_box_beam_info(item):
    gui_row("row-height: 1em;")
    gui_text(f"Beam {item.get('index',0)}", "col-width: content;")
    gui_blank()
    # ib = gui_icon_button("icon_index: 155; color:red;")
    ib = gui_button("X ","col-width: content;",data={"item":item})
    gui_message(ib, "gm_delete_beam_from_ship")

def update_property_set(lb, props):
    if lb is None or props is None:
        return
    # this function isn't a mast global, so instead we call it inside this helper function.
    lb.items = _gui_properties_items(props)
    lb.mark_layout_dirty()

def gm_torp_get_data_for(id_or_obj):
    """
    Get basic data for each torp type available to the selected ship.
    """
    if id_or_obj is None:
        return []
    torps = torpedo_get_available_types_for_ship(id_or_obj)
    ret = list()
    for t in torps:
        cur,_max = torpedo_get_count_for_ship(id_or_obj, t)
        name = torp_get_attribute_value(t,"gui_text")
        data = dict()
        data["ship"] = id_or_obj
        data["key"] = t
        data["cur"] = cur
        data["max"] = _max
        data["name"] = name
        ret.append(data)
    return ret


def gm_list_box_loadout_info(item):
    # Name row
    gui_row("row-height: 1.5em;")
    name = item.get("name", "Name???")
    gui_text(f"{name}")

    # Current count row
    cur = item.get("cur", 0)
    gui_row("row-height: 2em;")
    sub = gui_button("$text: - ;", "col-width: content;", data={"torp_item":item, "add":False})
    gui_message(sub, "gm_add_or_remove_torp")
    gui_text(f"$text: Current: {cur};")
    add = gui_button("$text: + ;", "col-width: content;", data={"torp_item":item, "add":True})
    gui_message(add, "gm_add_or_remove_torp")

    # Max count row
    _max = item.get("max",0)
    gui_row("row-height: 2em;")
    sub = gui_button("$text: - ;", "col-width: content;", data={"torp_item":item, "add":False})
    gui_message(sub, "gm_change_torp_capacity")
    gui_text(f"$text: Maximum: {_max};")
    add = gui_button("$text: + ;", "col-width: content;", data={"torp_item":item, "add":True})
    gui_message(add, "gm_change_torp_capacity")
    
