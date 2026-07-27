
from sbs_utils.procedural.gui import gui_row, gui_text

def main_mission_select_template(item):
    gui_row("row-height:2px;background:#ddd;padding:10px,0,10px,3px;")
    # Two things had to be said out loud to make this row hold its own title:
    #
    #   font:gui-3   `em` resolves against the ROW's font, and an undeclared row
    #                is 24px (gui-2, the engine default) -- short of the gui-3
    #                title, which then overdraws, since the engine does not clip.
    #   +10px        the row's own top padding comes OUT of the row height, so a
    #                bare 1em left the text 10px short (audit: box 18px, text 28).
    #
    # NB not `row-height: content`: this is a listbox item template, and content
    # sizing inside a listbox still falls back to flex.
    gui_row("row-height: 1em+10px;padding:10px,10px,10px,0;font:gui-3;")
    gui_text(f"$text:`{item.display_name}`;justify: left;font:gui-3;")
    gui_row("row-height:15em;padding:10px,0,10px,3px;")
    gui_text(f"$text:`{item.desc}`;justify: left;color:#999;font:gui-2;")
    
    

# def main_mission_select_title_template():
#     gui_row("row-height: 1.2em;padding:13px;background:#1578;")
#     gui_text(f"$text:{MISSIONS_TITLE};justify: left;")
    
