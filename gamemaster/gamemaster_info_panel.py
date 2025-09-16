from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui import *
from sbs_utils.procedural.execution import gui_get_variable, gui_set_variable
from sbs_utils.procedural.query import to_set, to_object
from sbs_utils.procedural.comms import comms_broadcast, comms_navigate, comms_navigate_override
from sbs_utils.procedural.signal import signal_emit
from sbs_utils.procedural.sides import side_keys_set
import sbs

world_options = [
    {"path":"world_options","title": "Manage Sides", "label": "gamemaster_side_relations"}
]


def gm_panel_list(cid, left, top, width, height):
    task = gui_task_for_client(cid)
    if task is None:
        return
    show_gm_panel_gui(cid)

def gm_panel_list_tick(cid):
    sel = gui_get_variable("gm_selection")
    comms_broadcast(0, f"SEL: {sel}")
    task = gui_task_for_client(cid)
    if task is None:
        return 1
    show_gm_panel_gui(cid)

def show_gm_panel_gui(cid):
    # Let user know how to fix the issue
    comms_broadcast(cid, "NOTE: Comms Message textbox has broken and will not work until you refresh the console. You can still use Paste from Clipboard and Send functionality without issue.")
    task = gui_task_for_client(cid)
    if task is None:
        return
    
    sel = gui_get_variable("gm_selection")
    gui_set_variable("gm_display_id",sel)
    obj = to_object(sel)
    if obj is None:
        gui_text(f"$text: No valid object selected.")
        return
    gui_row(style="row-height:2.1em;")
    # with gui_sub_section():
    # gui_button(f"$text: {obj.name}; tag: ship_name")
    # gui_button(f"$text: Hello")
    ship_name_change = gui_input(f"$text:{obj.name};desc:Ship Name", var="gm_ship_name")
    gui_message(ship_name_change, "update_ship_name")
    gui_row("row-height: 2em;")
    sides = role("__side__")
    sides_list = list()
    for s in sides:
        sides_list.append(get_inventory_value(s, "side_name", ""))
    sides = ",".join(sides_list)
    side_change = gui_drop_down(f"$text:{obj.side};list:{sides}",style="row-height: 2em;",var="gm_ship_side")
    gui_message(side_change, "update_ship_side")
    gui_row()

    # roles = obj.get_roles()
    # role_str = ",".join(roles)
    # ship_roles_gui = gui_input(f"desc:{role_str}", var="ship_roles")
    # # gui_message(ship_roles_gui, update_ship_roles)
    # gui_row()
from sbs_utils.procedural.style import apply_control_styles
def listbox_button(item, menu=1):
    """
    Build a listbox item.
    Args:
        item: A python dict. Should contain the following values:
            name: str
            on_press: label
    """
    gui_row("row-height: 1.5em;")
    # task = FrameContext.task
    name = ""
    if isinstance(item, str):
        name = item
    else:
        name = item['name']
    layout_item = gui_button(f"{name}", data=item)
    gui_message(layout_item, "GM_Button_Pressed")
    # apply_control_styles(".button", "", layout_item, task)
    # gui_button()

def simple_listbox_button(item):
    gui_row("row-height: 1.5em;")
    task = FrameContext.task
    
    layout_item = gui_text(f"{item}")
    apply_control_styles(".button", "", layout_item, task)

def simple_listbox_title():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text(f"$text:Ship;justify: left;")

def listbox_item_pressed(button):
    print("listbox item pressed")
    signal_emit("gm_button_selected", {"button": button})

def buildIcon(item):
    """Probably won't use, but it's a possible depiction of an alternative to the Info Panel implementation"""
    print(f"building icon: {item}")
    gui_row("row-height:45px;")
    gui_icon(f"icon_index:{item};color:white;")
    gui_text(f"$text:{item}")

def gm_panel_list_item(message_obj):
    task = FrameContext.client_task
    if message_obj is None:
        return

    icon = message_obj.get("icon_index")
    color = message_obj.get("icon_color", "white")
    face = message_obj.get("face")
    title = message_obj.get("title")
    title = task.compile_and_format_string(title)
    message = message_obj.get("message")
    message = task.compile_and_format_string(message)

    title_color = message_obj.get("title_color", "white")
    title_color = task.compile_and_format_string(title_color)
    message_color = message_obj.get("message_color", "white")
    message_color = task.compile_and_format_string(message_color)


    # Need this for the flacky sub_section
    # if icon is not None or face is not None:

    #
    # Title
    #
    gui_row(style="row-height:2.1em;")
    with gui_sub_section():
        gui_row(style="row-height:2em;")
        if icon is not None or face is not None:
            with gui_sub_section(style="row-height:2em;col-width:2em;"):
                gui_row(style="row-height:1.8em;col-width:1.8em;")
                with gui_sub_section():
                    if icon is not None:
                        gui_row()
                        gui_icon(f"icon_index:{icon};color:{color};")
                    if face is not None:
                        gui_row()
                        gui_face(face)

        if title:
            gui_text(f"$text: {title};font:gui-2;color:{title_color};")
        elif message:
            gui_text(f"$text: {message};font:gui-2;color:{message_color};")

from sbs_utils.procedural.timers import is_timer_set, format_time_remaining
from sbs_utils.procedural.inventory import set_inventory_value, get_inventory_value
from sbs_utils.procedural.sides import to_side_id, side_enemy_members_set, sides_set, side_display_name, side_members_set
from sbs_utils.mast.mast_node import Scope # Enum, 1
from sbs_utils.procedural.roles import role,any_role
def show_gm_stats(client_id, top, left, width, height):
    print(f"show gm stats CID: {client_id}")
    if is_timer_set(Scope.SHARED, "time_limit"):
        gui_row("row-height: 45px")
        gui_text("$text: time left;justify: right;font:gui-3;")
        gui_row()
        t = format_time_remaining(Scope.SHARED, "time_limit")
        gui_text(f"$text: {t};justify:left;font:gui-3;", style="tag: sh_game_time;padding:20px;")    
        
        # TODO: Add timer changes
        # gui_row("row-height: 0.5em;")
        # gui_text(" ")
        # gui_row()
        # gui_text("Adjust Time")
        # time = gui_drop_down("1 Minute, 5 Minutes, 10 Minutes")
        # gui_button("Add Time")
        # gui_button("Remove Time")

    gui_row("row-height: 45px")
    # Show remaining enemy count
    gm_side = get_inventory_value(client_id, "gamemaster_cur_side",None)
    if gm_side is None:
        player = role("__player__").pop()
        side = to_side_id(player)
        gm_side = get_inventory_value(side, "side_key", "tsn")
        set_inventory_value(client_id, "gamemaster_cur_side", gm_side)
    print(f"{gm_side}")

    sides = sides_set()
    side_counts = list()
    for side in sides:
        r = side_members_set(side)-any_role("shuttle,fighter,gamemaster")
        for m in r:
            o = to_object(m)
            comms_broadcast(0, o.name)
        # r = role("raider") 
        count=len(r)
        if count > 0:
            gui_text(f"$text: {side_display_name(side)};justify:right;font:gui-2;")
            raider_count = gui_text(f"$text: {count};justify:left;font:gui-2;", style="tag: sh_raider_count;padding:10px;")
            side_counts.append(raider_count)
            gui_row()
    set_inventory_value(client_id, "gm_counts_list", side_counts)
    set_inventory_value(client_id, "gm_show_stats", True)
    
def hide_gm_stats(client_id, top, left, width, height):
    set_inventory_value(client_id, "gm_show_stats", False)

def tick_gm_stats():
    pass



def gm_add_world_option(path, title, label):
    world_options.append({"path": path, "title": title, "label": label})
