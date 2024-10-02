from sbs_utils.procedural.gui import gui_row, gui_text, gui_ship, gui_sub_section
from sbs_utils import fs

def console_select_template(item):
    gui_row("row-height: 1.2em;padding:13px;")
    gui_text(f"$text:{item.display_name};justify: left;font:gui-3;")
    gui_row("row-height: 1.2em;padding:13px;")
    gui_text(f"$text:{item.description};justify: left;font:gui-2;color:#bbb;")
    # gui_text(f"$text:Hello;justify: left;font:gui-2;")
    

def console_select_title_template():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text(f"$text:Consoles;justify: left;")
    

def console_ship_select_template(item):
    gui_row("row-height:3em;padding:13px;")
    gui_ship(f"{item.art_id}", style="col-width:50px;")
    with gui_sub_section():
        gui_text(f"$text:{item.name};justify: left;font:gui-3;")
        gui_row()
        gui_text(f"$text:{item.name};justify: left;font:gui-2;color:#bbb;")
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
    cd = f"{d}/media/{console}"

    if not os.path.isdir(cd):
        return []
    
    files = glob.glob(f"{cd}/*.png")
    # remove the png
    for i in range(len(files)):
        files[i] = os.path.splitext(files[i])[0]
    return files
    