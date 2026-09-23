from sbs_utils.procedural.gui import gui_row, gui_text, gui_ship, gui_sub_section, gui_button, gui_task_for_client, gui_icon, gui_blank, gui_message_callback, gui_text_escape
from sbs_utils.procedural.gui import gui_tab_is_top, gui_tab_add_top, gui_tab_remove_top
from sbs_utils import fs
from sbs_utils.procedural import ship_data
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui import gui_tab_get_list
from sbs_utils.pages.layout.measure import measure_block_height
from sbs_utils.gui import get_client_aspect_ratio
from sbs_utils.mast.mast_node import MastDataObject
from sbs_utils.procedural.crew import crew_preview_post, crew_preview_markdown


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
    """One ship row. `item` is a SLOT NUMBER, not a ship.

    Nothing here resolves an engine object. The row is drawn from the roster RECORD, and
    `gui_ship` already took a hull KEY rather than a ship - it was only ever the SOURCE of
    that key that needed an object.

    That matters beyond tidiness: this template runs for every visible row, on every
    console, every rebuild. Reading `.name` and `.art_id` off live Agents here is a
    per-frame engine read per client, on ships the roster may be reshaping underneath.
    """
    from sbs_utils.procedural.player_roster import player_roster_display
    row = player_roster_display(item)
    hull = row["hull"]

    gui_row("row-height:2em;padding:13px;")
    gui_ship(f"{hull}", style="col-width:50px;padding:0,0,5px,0;")
    dat = ship_data.get_ship_data_for(hull)
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
        ship_label = gui_text_escape(f"{row['name']} - {row['side']}")
        gui_text(f"$text:{ship_label};justify: left;font:gui-3;")
        gui_row("row-height:1em;")
        gui_text(f"$text:{desc};justify: left;font:gui-2;color:#bbb;")
    

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
    from sbs_utils.procedural.media_paths import media_shared
    d = fs.get_mission_dir()
    cd = os.path.join(d, *media_shared(console).split("/"))

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

from sbs_utils.procedural.gui import gui_face
_IDENTITY_FACE_PX = 44


def console_crew_identity(client_id, slot, hull, console,
                          own_name="", own_face="", own_portrait="", own_pick=""):
    """Who this console is about to be: one record the picker's identity row binds to.

    A PREVIEW - it takes no seat and writes nothing, and because a seat's automatic name is
    allocated once and kept, what this shows is what `crew_assign` publishes when the player
    presses Ready. Clicking through the station list is therefore free to re-ask.

    Keyed on the SLOT and the HULL rather than on a ship: the picker binds to slots and the
    ship it is choosing a hull for may not exist yet, which is exactly when a mod's
    `Hull:`-bound cast has to be able to answer.
    """
    post = crew_preview_post(client_id, None, console,
                             own_name=own_name, own_face=own_face,
                             own_portrait=own_portrait, own_pick=own_pick,
                             hull=hull, slot=slot)
    name = post.name or ""
    rank = post.rank or ""
    return MastDataObject({
        # Reads as a prompt when there is nobody, which is what it is: press Edit and say.
        "label": (f"{rank} {name}".strip() if name else "No crew name"),
        "name": name,
        "rank": rank,
        "face": post.face or "",
        "portrait": post.portrait or "",
        "markdown": crew_preview_markdown(post.face, post.portrait,
                                          height=_IDENTITY_FACE_PX, align="left"),
    })
