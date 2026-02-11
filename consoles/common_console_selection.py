from sbs_utils.procedural.gui import gui_row, gui_text, gui_ship, gui_sub_section, gui_checkbox, gui_task_for_client, gui_icon, gui_blank
from sbs_utils import fs
from sbs_utils.procedural import ship_data
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui import gui_tab_get_list

def console_select_template(item, **kwargs):
    gui_row("row-height: 2.5em;")
    sec = kwargs.get("section")
    # Too coupled for now just  test
    click_color = "#fff1"
    if sec:
        sec.click_text = None
        sec.click_tag = None
        click_color = sec.click_background

    con = gui_sub_section()
    with con:
        gui_row("row-height: 1.2em;padding:13px;")
        gui_text(f"$text:{item.display_name};justify: left;font:gui-3;")
        gui_row("row-height: 1.2em;padding:13px;")
        gui_text(f"$text:{item.description};justify: left;font:gui-2;color:#bbb;")

    con.sub_section.click_tag = kwargs.get("click_tag")
    con.sub_section.click_text = ""
    con.sub_section.click_background = click_color

    if not FrameContext.client_task.get_variable("TAB_CONSOLES_ENABLE", False):
        return

    console = item.path.upper()
    if item.path in gui_tab_get_list():
        selected = kwargs.get("selected")
        if selected:
            cb = gui_icon(f"icon_index: 101;color:white;")
        else:
            cb = gui_checkbox(f"icon_index: 101;color:white;", var=f"{console}_TAB_ENABLED")
            
    

def console_select_title_template():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text(f"$text:Consoles;justify: left;")
    

def console_ship_select_template(item):
    gui_row("row-height:2.5em;padding:13px;")
    gui_ship(f"{item.art_id}", style="col-width:50px;padding:0,0,5px,0;")
    dat = ship_data.get_ship_data_for(item.art_id)
    desc = "A fine ship"
    if dat is not None:
        desc = dat.get("name")
        origin = dat.get("origin")
        if origin is not None:
            desc = f"{origin} - {desc}"
        else:
            desc = f"{desc}"

    with gui_sub_section():
        gui_row("row-height:1.2em;")
        gui_text(f"$text:{item.name} - {item.side};justify: left;font:gui-3;")
        gui_row("row-height:1em;")
        gui_text(f"$text:{desc};justify: left;font:gui-2;color:#bbb;")
    # gui_text(f"$text:Hello;justify: left;font:gui-2;")
    

def console_ship_select_title_template():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text(f"$text:Ships;justify: left;")
    
import os
def console_get_console_type():
    ## This is illogical, because this is only on the server
    return os.environ.get("cosmos_start_mode")

import glob
def console_get_images(console):
    # "media/helm/consoles0001"
    d = fs.get_mission_dir()
    cd = f"{d}/media/LegendaryMissions/{console}"

    if not os.path.isdir(cd):
        return []
    
    files = glob.glob(f"{cd}/*.png")
    # remove the png
    for i in range(len(files)):
        files[i] = os.path.splitext(files[i])[0]
    return files
    
from sbs_utils.procedural.gui import gui_task_for_client, gui_panel_widget_hide, gui_panel_widget_show
def console_comms_swap_panels_from_water(cid,left,top,width,height):
    console_comms_swap_panels(cid,left,top,width,height, True)
def console_comms_swap_panels_from_2d(cid,left,top,width,height):
    console_comms_swap_panels(cid,left,top,width,height, False)

def console_comms_swap_panels(cid,left,top,width,height, water):
    task = gui_task_for_client(cid)
    if task is None:
        return
    
    view2d = task.get_variable("view2d_widget_control")
    if view2d is None:
        return
    
    vb = view2d.bounds 

    if not water:
        gui_panel_widget_show(cid, vb.left,vb.top,vb.width, vb.height, "comms_waterfall")
        gui_panel_widget_show(cid, left,top,width, height, "comms_2d_view")
    else:
        gui_panel_widget_show(cid, vb.left,vb.top,vb.width, vb.height, "comms_2d_view")
        gui_panel_widget_show(cid, left,top,width, height, "comms_waterfall")
    


def console_tab_toggle():
    pass


############################################
## These are for the comms prototype
def comms_recent_sort(items):
    return sorted(items, key=lambda cm: cm.get("time"))

from sbs_utils.procedural.gui import gui_face
def comms_recent_item(item):

    gui_row("row-height:2em")

    gui_face(f"{item.face}")
    

    # Is storing the face expensive to memory
    with gui_sub_section():
        gui_row("row-height:1em")
        title = item.title
        title_color = item.title_color
        msg = item.message
        msg_color = item.message_color

        if item.other_id == 0:
            msg = title
            msg_color = title_color
            title = "Ultra Band"
            title_color = "white"
        elif item.player_id == item.other_id:
            msg = title
            msg_color = title_color
            title = "Internal Comms"
            title_color = "white"
            
        title = title[:20] + " .."
        
        
        msg = msg[:20] + " .."
        
        title = f"$text:{title};font:gui-2;color:{title_color};"
        msg = f"$text:{msg};font:gui-1;color:{msg_color};"
        
        gui_text(title)
        gui_row()
        gui_text(msg)

        

        

def comms_message_item(item):
    gui_row("row-height:2em")

    if item.receive:
        gui_face(f"{item.face}")
    else:
        gui_blank(1,"col-width:2em")
    # Is storing the face expensive to memory
    with gui_sub_section():
        gui_row("row-height:1em")
        title = item.title
        title_color = item.title_color
        msg = item.message

        title = title[:16] + " .."
        msg = msg[:16] + " .."

        msg_color = item.message_color
        title = f"$text:{title};font:gui-2;color:{title_color};"
        msg = f"$text:{msg};font:gui-1;;color:{msg_color};"

        if not item.receive:
            title += "justify:right;"
            msg += "justify:right;"
        
        gui_text(title)
        gui_row()
        gui_text(msg)

    if not item.receive:
        gui_face(f"{item.face}")
    else:
        gui_blank(1,"col-width:2em")
    
