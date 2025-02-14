
from sbs_utils.procedural.gui import gui_row, gui_text

def main_mission_select_template(item):
    gui_row("row-height:2px;background:#ddd;padding:10px,0,10px,3px;")
    gui_row("row-height: 2em;padding:10px,10px,10px,3px;")
    gui_text(f"$text:{item.display_name};justify: left;font:gui-3;")
    gui_row("row-height:15em;padding:10px,0,10px,3px;")
    gui_text(f"$text:{item.desc};justify: left;color:#999;font:gui-2;")
    
    

def main_mission_select_title_template():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text(f"$text:Mission types;justify: left;")
    
