from sbs_utils.procedural.gui.button import Button
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui import *
from sbs_utils.procedural.execution import gui_get_variable, gui_set_variable, task_schedule, gui_sub_task_schedule
from sbs_utils.procedural.query import to_set, to_object
from sbs_utils.procedural.comms import comms_broadcast, comms_navigate, comms_navigate_override
from sbs_utils.procedural.ship_data import filter_ship_data_by_side
from sbs_utils.procedural.roles import role, has_role
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.signal import signal_emit
import sbs


def get_gm_label():
    ret = []
    page = FrameContext.page
    if page is None:
        return []
    #
    # Walk all labels looking for map Labels
    #
    init_label = None
    all_labels = page.story.labels
    for l in all_labels:
        if not l.startswith("gamemaster_menu"):
            continue
        m = all_labels[l]
        comms_broadcast(0, f"Label path: {m.path}")
        if m.path == "__overview__":
            init_label = m
        else:
            ret.append(m)
#                {"name": m.display_name, "description": text_sanitize(m.desc), "label": m},
#            )
    #
    # If there is just the one i.e. the init return that
    #
    if len(ret)==0 and init_label is not None:
        return [init_label]
    elif len(ret)==0:
        return  [
            {"name": "No maps found", "description": "No maps were found when searching all mast/python labels."},
        ]
    return ret

class GM_Gui_Tab(Button):
   def __init__(self, tag, name, icon):
      super().__init__(tag, f"$text:{name}")
      pass

# def buildButton(parent)
def get_ship_data_for_side(side):
    ships = filter_ship_data_by_side(None, sides=side)
    for ship in ships:
        gui_button(ship["key"], data={"ship":ship})
        gui_message(ship, "GM_Spawn")

def buildButtons(parent_category, items):
    # with gui_list_box():
    for item in items:
        b = gui_button(item, data={"parent_category":parent_category, "item": item})
        # lbl = f"gm_select_{parent_category}_{item}"
        # lbl = "GM_Button_Pressed"
        # comms_broadcast(0, lbl)
        gui_message(b,"GM_Button_Pressed")
        gui_row()

spawn_sides = list((
    "TSN",
    "USFP",
    "Kralien",
    "Arvonian",
    "Torgoth",
    "Skaraan",
    "Ximni",
    "Pirate"
))

spawn_terrain = list((
    "asteroids",
    "nebulae",
    "pickups"
))

spawn_monster = list((
    "charybdis",
    "piranha"
))

def get_sides():
    """
    Returns a list of the names of all sides (Agents with the role "__side__")
    """
    sides = role("__side__")
    sides_list = list()
    for s in sides:
        # side = to_object(s)
        sides_list.append(get_inventory_value(s, "side_name", ""))
    return sides_list

def gm_build_item(item):
    gui_row("row-height: 2em;")
    gui_button(item["title"])
    print("gm build item")
def gm_build_title(title):
    gui_row("row-height: 2em;")
    gui_text(title["title"])
    print("gm build title")

def build_spawn_menu():
    signal_emit("gm_settings_choice", {"width": "350px;"})
    sides = get_sides()
    # comms_broadcast(0, f"{','.join(sides)}")
    # gui_drop_down(f"$text:TSN;list:{','.join(sides)}", var="GM_SIDE_SELECT")
    # get_gm_label()
    # gui_property_list_box(name="Spawn")
    # props = """
    # Main:
    #     Player Ships: 'gui_int_slider("$text:int;low: 1.0;high:8.0;", var= "PLAYER_COUNT")'
    #     Difficulty: 'gui_int_slider("$text:int;low: 1.0;high:11.0;", var= "DIFFICULTY")'
    # Map:
    #     Terrain: 'gui_drop_down("$text: {TERRAIN_SELECT};list: none, few, some, lots, max",var="TERRAIN_SELECT")'
    #     Lethal Terrain: 'gui_drop_down("$text: {LETHAL_SELECT};list: none, few, some, lots, max", var="LETHAL_SELECT")'
    #     Friendly Ships: 'gui_drop_down("$text: {FRIENDLY_SELECT};list: none, few, some, lots, max", var="FRIENDLY_SELECT")'
    #     Monsters: 'gui_drop_down("$text: {MONSTER_SELECT};list: none, few, some, lots, max", var="MONSTER_SELECT")'
    #     Upgrades: 'gui_drop_down("$text: {UPGRADE_SELECT};list: none, few, some, lots, max", var= "UPGRADE_SELECT")'
    #     Time Limit: 'gui_input("desc: Minutes;", var="GAME_TIME_LIMIT")'
    # """
    # gui_properties_set(props)
    # gui_row()
    # gui_text("Name")
    # gui_button("Hi")
    # gui_row()
    items = ["Hello", "Goodbye"]
    messages_objs = [{"title": "Carapaction Coil", "message":"5 min 300% shield recharge boost", "title_color": "yellow"}]
    messages_objs.append({"title": "Infusion P-Coils", "message":"5 min Impulse and Maneuver Speed boost", "title_color": "yellow"})
    messages_objs.append({"title": "Lateral Array", "message":"5 min Target Scan Triple Speed", "title_color": "green" })
    messages_objs.append({"title": "Lateral Array", "message":"5 min Target Scan Triple Speed", "title_color": "green" })
    messages_objs.append({"title": "Lateral Array", "message":"5 min Target Scan Triple Speed", "title_color": "green" })
    messages_objs.append({"title": "Lateral Array", "message":"5 min Target Scan Triple Speed", "title_color": "green" })
    messages_objs.append({"title": "Lateral Array", "message":"5 min Target Scan Triple Speed", "title_color": "green" })
    messages_objs.append({"title": "Lateral Array", "message":"5 min Target Scan Triple Speed", "title_color": "green" })
    messages_objs.append({"title": "Infusion P-Coils", "message":"5 min Impulse and Maneuver Speed boost", "title_color": "yellow"})
    messages_objs.append({"title": "Lateral Array", "message":"5 min Target Scan Triple Speed", "title_color": "green" })
    with gui_sub_section():
        gui_row()
        list_box = gui_list_box(messages_objs, "$text: Spawn Stuff;", collapsible=True, item_template=gm_build_item, title_section_style=gm_build_title)
    # gui_row()
    return list_box
    

def gm_gui_panel_widget_show(cid, left, top, width, height, menu):
    # signal_emit("gm_settings_choice", {"width": "150px"})
    # build_spawn_menu()
    diff = 1
    gui_text(f"$text:{menu}")
    gui_row("row-height: 0.2em;")
    top = top + diff
    height = height - diff
    # gui_panel_widget_show(cid, left, top, width, height, "comms_control")
    # path = "//comms/gamemaster/"+menu
    # # comms_broadcast(0, path)
    # # comms_navigate(path)
    # ship = sbs.get_ship_of_client()
    # if ship is None:
    #    comms_broadcast(0, "ship is None")
    # sel = gui_get_variable("gm_selection")
    # if sel is None:
    #    comms_broadcast(0, "sel is None")
    # comms_navigate_override(ship, sel, path)
    set_inventory_value(cid, "gm_menu", menu)
    spawn_sides = get_sides()
    if menu == "spawn":
        build_spawn_menu()

    elif menu == "spawn/ship":
        build_menu(spawn_sides)
        # gui_sub_task_schedule("gm_spawn_ship", data={"buttons":spawn_sides})
        # buildButtons("ship",spawn_sides)
    elif menu == "spawn/fleet":
        buildButtons("fleet",spawn_sides)
    elif menu == "spawn/starbase":
        buildButtons("starbase",spawn_sides)
    elif menu == "spawn/terrain":
        buildButtons("terrain",spawn_terrain)
    elif menu == "spawn/monster":
        buildButtons("monster",spawn_monster)
    elif menu == "config/world":
        gui_row("row-height: 4em;")
        gui_button("Manage Sides", on_press="gamemaster_side_relations")
        gui_row()
    # elif menu == "test_comms":
    #     gui_panel_widget_show(cid, left, top, width, height, "comms_control")
    #     path = "//comms/gamemaster/"+menu
    #     # comms_broadcast(0, path)
    #     # comms_navigate(path)
    #     ship = sbs.get_ship_of_client(cid)
    #     comms_broadcast(0, f"Ship: {ship}")
    #     if ship is None:
    #        comms_broadcast(0, "ship is None")
    #     sel = gui_get_variable("gm_selection")
    #     comms_broadcast(0, f"Selected: {sel}")
    #     if sel is None:
    #        comms_broadcast(0, "sel is None")
    #     comms_navigate_override(ship, sel, path)
    # elif menu == "spawn":
    #     build_spawn_menu()
    else:
        pass

def open_side_management_screen():
    signal_emit("side_management")
    
def gm_comms_path(COMMS_ORIGIN_ID, path) -> bool:
    if not has_role(COMMS_ORIGIN_ID, "gamemaster"):
        return False
    return get_inventory_value(COMMS_ORIGIN_ID, "gm_menu", "") == path

def buildShipPropsPanel(title, props_list):
    gui_property_list_box(title)
    gui_properties_set(props_list)
    
def build_menu(button_names, button_labels=None, button_height=10, width=100):
    # with gui_sub_section(style=f"col-width: {width}px; row-height: {button_height*len(button_names)}px;"):
    # with menu:
        for button in range(len(button_names)):
            op = None
            if button_labels is not None:
                op = button_labels[button]
            gui_button(button_names[button], style=f"row-height: {button_height}px;", on_press="gm_build_sub_menu")
            gui_row()

def nothing(cid, left, top, width, height, widget=""):
    """Literally does nothing"""
    pass

def gui_spacer_row():
    """Make a small spacer row between gui elements"""
    gui_row("row-height: 0.2em;")
    gui_text(" ")
    gui_row()


def spawn_sub_menu(button):
    bounds = button.bounds
    if bounds is None:
        from sbs_utils.pages.layout.bounds import Bounds
        bounds = Bounds(0,0,150,100)#shouldn't be a thing
    gui_section(f"area: {bounds.right}, {bounds.top}, {bounds.right + 150}, 100")
    with gui_sub_section():
        gui_button("Testing")

# def type(obj):
#     return (obj)
