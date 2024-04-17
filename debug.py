from sbs_utils.procedural.gui import gui_row, gui_icon, gui_text

def debug_menu_template(item):
    gui_row("row-height: 48px;padding:3px")
    gui_icon(f"icon_index: {item['icon']};color:white;")
    gui_row("row-height: 1.2em")
    gui_text(f"text:{item['text']};justify:left;")
    

