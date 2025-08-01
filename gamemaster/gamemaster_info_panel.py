from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui import *
from sbs_utils.procedural.execution import gui_get_variable, gui_set_variable
from sbs_utils.procedural.query import to_set, to_object
from sbs_utils.procedural.comms import comms_broadcast, comms_navigate, comms_navigate_override
import sbs


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
    gui_row()

    side_change = gui_drop_down(f"$text:{obj.side};list:{obj.side},Kralien,Arvonian,Torgoth,Skaraan,Ximni",style="row-height: 2em;",var="gm_ship_side")
    gui_message(side_change, "update_ship_side")
    gui_row()

    # roles = obj.get_roles()
    # role_str = ",".join(roles)
    # ship_roles_gui = gui_input(f"desc:{role_str}", var="ship_roles")
    # # gui_message(ship_roles_gui, update_ship_roles)
    # gui_row()



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




