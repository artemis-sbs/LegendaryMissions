from sbs_utils.procedural.gui.button import Button
from sbs_utils.helpers import FrameContext, FakeEvent
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
        # comms_broadcast(0, f"Label path: {m.path}")
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

#
# TODO: This is now in the library as gui_listbox_items_convert_headers
#
def gm_convert_listbox_items(items):
    """Converts a list of strings into a list of objects that allow a listbox to collapse if a header is clicked
    To make a header, prefix the name with `>>`. 
    Example usage:
        ```python
        item = [">>Header","Item1","Item2",">>Another Header","Another Item 1","Another Item 2"]
        ret = gm_convert_listbox_items(item)
        gui_list_box(items=ret, style="", select=True, collapsible=True)
        ```
    Args:
        items (list(str)): A list of strings
    Returns:
        (list(str|LayoutListBoxHeader)): A list of LayoutListBoxHeader (for the headers) and strings (for the items)
    """
    # TODO: This maybe should be integrated into sbs_utils somehow?
    ret = []
    for k in items:
        if isinstance(k,str):
            collapse = False
            if k.startswith(">>"):
                k = k[2:]
                ret.append(LayoutListBoxHeader(k, collapse))
            else:
                ret.append(k)
    return ret

# def buildButton(parent)
def get_ship_data_for_side(side):
    ships = filter_ship_data_by_side(None, sides=side)
    for ship in ships:
        gui_button(ship["key"], data={"ship":ship})
        gui_message(ship, "GM_Spawn")

def buildButtons(parent_category, items):
    # with gui_list_box():
    for item in items:
        gui_row("row-height: 2em;")
        b = gui_button(item, data={"parent_category":parent_category, "item": item})
        # lbl = f"gm_select_{parent_category}_{item}"
        # lbl = "GM_Button_Pressed"
        # comms_broadcast(0, lbl)
        gui_message(b,"GM_Button_Pressed")
        # gui_row()
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

def gm_set_menu_contents(client_id, menu, contents):
    """
    Set the contents of a menu. Empties all derived menus.
    Args:
        menu (int): The menu number (1-5)
        contents (dict): A dict with 'name' and 'on_press' values
    """
    listbox = get_inventory_value(client_id, f"gm_list_box_{menu}")
    listbox.items = contents
    listbox.represent(FakeEvent(client_id))
    for x in range(menu+1,6):
        lb = get_inventory_value(client_id, f"gm_list_box_{x}")
        lb.items = []
        lb.represent(FakeEvent(client_id))

#
# TODO: This is now in the library as gui_list_box_header
#
from sbs_utils.pages.widgets.layout_listbox import LayoutListBoxHeader
def buildListboxHeader(label, collabsible=True):
    return LayoutListBoxHeader(label, collabsible)

def spawn_with_side_common(client_id,required_roles = [], exclude_roles=[]):
    sides = get_sides()
    # side_dropdown = gui_drop_down(f"items:{','.join(sides)}")
    race = get_inventory_value(client_id, "gm_spawn_menu_race")
    # side_dropdown.value = race
    prev_menu = get_inventory_value(client_id, "gm_menu")
    if prev_menu is None:
        prev_menu = ""
    if prev_menu.find("spawn") != -1:
        # `race` is not the best word for this use case, origin might be better?
        race = get_inventory_value(client_id, "gm_spawn_menu_race")
        if race is None:
            race = "TSN"

        ships = filter_ship_data_by_side(None, race)
        roles = list()
        for ship in ships:
            ship_roles = ship["roles"].split(",")
            has_required = True
            for rr in required_roles:
                if ship_roles.count(rr) == 0:
                    has_required = False
                    break
            if has_required:
                roles.extend(ship_roles)
        # remove duplicates
        roles = set(roles)
        for ex in exclude_roles:
            roles.discard(ex)
        # roles.discard("ship")
        # roles.discard("cockpit")
        roles.discard(race.lower())
        # sort alphabetically
        roles = sorted(list(roles))
        # menu.items = []
        newItems = []
        for r in roles:
            data = {"name": r, "on_press": "GM_Side_Selection"}
            newItems.append(data)
            # print(f"Adding {r}")
        gm_set_menu_contents(client_id, 1, newItems)


def gm_get_ships_for_side(race, required_roles = [], exclude_roles=[]):
    """
    Get ships from shipData.yaml that match the race, required roles, and excluded roles
    """
    print(f"Race: {race}")
    ships = filter_ship_data_by_side(None, race)
    print(f"Lenght: {len(ships)}")
    roles = list()
    for ship in ships:
        ship_roles = ship["roles"].split(",")
        has_required = True
        for rr in required_roles:
            if ship_roles.count(rr) == 0:
                has_required = False
                break
        if has_required:
            roles.extend(ship_roles)
    # remove duplicates
    roles = set(roles)
    for ex in exclude_roles:
        roles.discard(ex)
    roles.discard(race.lower())
    # sort alphabetically
    roles = sorted(list(roles))
    print(f"{roles}")
    return roles
    # newItems = []
    # for r in roles:
    #     data = {"name": r, "on_press": "GM_Side_Selection"}
    #     newItems.append(data)


def gm_gui_panel_widget_show(cid, left, top, width, height, menu):
    gui_row("row-height: 1.5em;")
    gui_text(f"$text:{menu}")

    
    spawn_sides = get_sides()
    # if menu == "spawn":
    #     build_spawn_menu()


    # All of these use a very similar format, so we'll use spawn_with_side_common() to handle it
    if menu == "spawn/ship":
        pass
        # buildButtons("ship",spawn_sides)
        # spawn_with_side_common(cid, [], ["ship","cockpit","station"])
    elif menu == "spawn/fleet":
        pass
        # buildButtons("fleet",spawn_sides)
        # spawn_with_side_common(cid)
    elif menu == "spawn/starbase":
        pass
        # buildButtons("starbase",spawn_sides)
        # spawn_with_side_common(cid, ["station"], ["ship","cockpit"])


    # These are more specific to each option
    elif menu == "terrain":
        buildButtons("terrain",spawn_terrain)
    elif menu == "monster":
        buildButtons("monster",spawn_monster)
    elif menu == "config/world":
        gui_row("row-height: 2em;")
        gui_button("Manage Sides", on_press="gamemaster_side_relations")
        # Uncomment these when the time limit system is working right? Works in comms buttons of course
        # gui_row("row-height: 2em;")
        # gui_button("Time Limit", "", on_press="gm_time_setup")
        gui_row()
    else:
        gm_set_menu_contents(cid, 1, [])
        pass
    set_inventory_value(cid, "gm_menu", menu)

# def open_side_management_screen():
#     signal_emit("side_management")

# TODO: KEEP FOR NOW
# def gm_comms_path(COMMS_ORIGIN_ID, path) -> bool:
#     if not has_role(COMMS_ORIGIN_ID, "gamemaster"):
#         return False
#     return get_inventory_value(COMMS_ORIGIN_ID, "gm_menu", "") == path

# def buildShipPropsPanel(title, props_list):
#     gui_property_list_box(title)
#     gui_properties_set(props_list)
    
# def build_menu(button_names, button_labels=None, button_height=10, width=100):
#     # with gui_sub_section(style=f"col-width: {width}px; row-height: {button_height*len(button_names)}px;"):
#     # with menu:
#         for button in range(len(button_names)):
#             op = None
#             if button_labels is not None:
#                 op = button_labels[button]
#             gui_row()
#             gui_button(button_names[button], style=f"row-height: {button_height}px;", on_press="GM_Button_Pressed")
#             # gui_row()

def nothing(cid, left, top, width, height, widget=""):
    """Literally does nothing"""
    pass

def gui_spacer_row(row_height="0.2em"):
    """Make a small spacer row between gui elements"""
    gui_row(f"row-height: {row_height};")
    gui_text(" ")
    # gui_row()


# def spawn_sub_menu(button):
#     bounds = button.bounds
#     if bounds is None:
#         from sbs_utils.pages.layout.bounds import Bounds
#         bounds = Bounds(0,0,150,100)#shouldn't be a thing
#     gui_section(f"area: {bounds.right}, {bounds.top}, {bounds.right + 150}, 100")
#     with gui_sub_section():
#         gui_button("Testing")

# def type(obj):
#     return (obj)
