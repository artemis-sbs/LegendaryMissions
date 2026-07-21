from sbs_utils.procedural.gui import gui_row, gui_text, gui_ship, gui_sub_section, gui_button, gui_task_for_client, gui_icon, gui_blank, gui_message_callback, gui_text_escape
from sbs_utils.procedural.gui import gui_tab_is_top, gui_tab_add_top, gui_tab_remove_top
from sbs_utils import fs
from sbs_utils.procedural import ship_data
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui import gui_tab_get_list
from sbs_utils.pages.layout.measure import measure_block_height
from sbs_utils.gui import get_client_aspect_ratio


def console_select_tab(event, sender):
    console = sender.__console
    en = FrameContext.client_task.get_variable(f"{console}_TAB_ENABLED", False)
    if en:
        sender.value = "TAB^OFF"
    else:
        sender.value = "$text:TAB^ON;color:lime;"
    FrameContext.client_task.set_variable(f"{console}_TAB_ENABLED", not en)

# One console row is a title (one line, gui-3) over a description (free text,
# gui-2). Most descriptions are one line; "Director" is three. A fixed
# `row-height: 1em` on the description meant the extra lines drew over the row
# below, because the engine does not clip.
_DESC_FONT = "gui-2"
# The title row is `row-height: 1em` and the row declares no font, so it is one
# line of the DEFAULT font (24px), not of the gui-3 it draws. That 4px under-ask
# is deliberate and unchanged -- it reads better in engine, and it is what keeps
# an ordinary one-line row at exactly its old 2em.
_TITLE_PX = 24
# `padding:13px` does NOT come out of the row height here -- the audit reports a
# box exactly as tall as the row. So padding is subtracted from the measuring
# WIDTH and never added to the height. Adding it to the height was the first
# attempt and it doubled every row.
_ROW_PAD_PX = 13
# The listbox adds an indent and a selection tick the template cannot see from
# here. Measure against a narrower width than the row really has: erring narrow
# makes a row slightly too tall (a harmless gap), erring wide brings the overlap
# back.
_UNSEEN_CHROME_PX = 40


def _console_item_px(item, listbox):
    """(description px, whole item px), measured rather than assumed.

    Returns (None, None) when there is nothing to measure against, so the caller
    falls back to the old fixed heights instead of guessing.
    """
    if listbox is None:
        return None, None
    ar = get_client_aspect_ratio(FrameContext.client_id)
    if ar is None or not ar.x:
        return None, None
    width_px = listbox.bounds.width / 100 * ar.x - _UNSEEN_CHROME_PX - _ROW_PAD_PX
    if width_px <= 0:
        return None, None
    desc_px = measure_block_height(_DESC_FONT, item.description or "", int(width_px))
    if desc_px is None:
        return None, None
    # A one-line description gives 24 + 24 = 48px, which is exactly the 2em this
    # row has always been. Only a description that genuinely wraps grows.
    return desc_px, _TITLE_PX + desc_px


def console_select_template(item, **kwargs):
    #
    # Size the ROWS and let the listbox measure them. Do NOT return a height:
    # LayoutListbox only calls sec.resize_to_content() when the template returns
    # None, and each item's section starts with ZERO height -- so returning a
    # size leaves the section degenerate and the row becomes unclickable
    # (no selection highlight, no click region). The rows below already carry
    # the real heights, which resize_to_content sums correctly.
    #
    desc_px, item_px = _console_item_px(item, kwargs.get("listbox"))
    if item_px is not None:
        gui_row(f"row-height: {item_px}px;")
    else:
        gui_row("row-height: 2em;")

    sec = kwargs.get("section")
    # Too coupled for now just  test
    click_color = "#fff1"
    if sec:
        sec.click_text = None
        sec.click_tag = None
        click_color = sec.click_background

    con = gui_sub_section()
    with con:
        gui_row("row-height: 1em;padding:13px;")
        gui_text(f"$text:{item.display_name};justify: left;font:gui-3;")
        gui_row(f"row-height: {desc_px}px;padding:13px;"
                if desc_px is not None else "row-height: 1em;padding:13px;")
        gui_text(f"$text:{item.description};justify: left;font:gui-2;color:#bbb;")

    con.sub_section.click_tag = kwargs.get("click_tag")
    con.sub_section.click_text = ""
    con.sub_section.click_background = click_color

    if not FrameContext.client_task.get_variable("ALLOW_CONSOLE_TABS", False):
        return

    console = item.path.upper()
    if item.path in gui_tab_get_list():
        selected = kwargs.get("selected")
        if selected:
            return
            # cb = gui_icon(f"icon_index: 101;color:white;")
        #else:
        #    cb = gui_checkbox(f"icon_index: 101;color:white;", var=f"{console}_TAB_ENABLED")

        en = FrameContext.client_task.get_variable(f"{console}_TAB_ENABLED", False)
        t = "$text:TAB^ON;color:lime;" if en else  "TAB^OFF"
        b = gui_button(t, "col-width:2.5em")
        b.__console = console

        gui_message_callback(b, console_select_tab)


        
    

def console_select_title_template():
    gui_row("row-height: 1em;padding:13px;background:#1578;")
    gui_text(f"$text:Consoles;justify: left;")
    

def console_ship_select_template(item):
    gui_row("row-height:2em;padding:13px;")
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
        gui_row("row-height:1em;")
        # Escape the user-entered ship name so a ':' or ';' in it can't inject
        # style properties or break the justify/font that follow (issue #569).
        ship_label = gui_text_escape(f"{item.name} - {item.side}")
        gui_text(f"$text:{ship_label};justify: left;font:gui-3;")
        gui_row("row-height:1em;")
        gui_text(f"$text:{desc};justify: left;font:gui-2;color:#bbb;")
    # gui_text(f"$text:Hello;justify: left;font:gui-2;")
    

def console_ship_select_title_template():
    gui_row("row-height: 1em;padding:13px;background:#1578;")
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
        
        title = f"$text:{gui_text_escape(title)};font:gui-2;color:{title_color};"
        msg = f"$text:{gui_text_escape(msg)};font:gui-1;color:{msg_color};"
        
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
        title = f"$text:{gui_text_escape(title)};font:gui-2;color:{title_color};"
        msg = f"$text:{gui_text_escape(msg)};font:gui-1;;color:{msg_color};"

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
    
