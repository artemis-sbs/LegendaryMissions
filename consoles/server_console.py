from sbs_utils.procedural.gui.text import gui_text_area

from sbs_utils.procedural.gui import gui_row, gui_text
from sbs_utils.helpers import gui_text_escape

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
    gui_text(f"$text:{gui_text_escape(item.display_name)};justify: left;font:gui-3;")
    # The description fills WHAT IS LEFT of the item (1fr, the default). It was
    # a fixed `15em`, which is 360px at every resolution: correct in a 768-tall
    # window, but at 1024x600 it put the text's box at 108% -- off the bottom of
    # the screen. A carousel item now gets the picker's real height (see
    # LayoutListbox._present), so a flex row here tracks the window.
    #
    # A description too long for that space scrolls inside the text area rather
    # than spilling, which is what the text area was reached for in the first
    # place -- it only started doing it once TextArea stopped treating a long
    # one-line message as a simple label.
    #
    # gui_text_escape: a description containing ':' or ';' would otherwise be
    # read as further style props and lose its tail.
    gui_row("padding:10px,0,10px,3px;font:gui-2;")
    gui_text_area(f"$text:{gui_text_escape(item.desc)};justify: left;color:#999;font:gui-2;")
    
    

# def main_mission_select_title_template():
#     gui_row("row-height: 1.2em;padding:13px;background:#1578;")
#     gui_text(f"$text:{MISSIONS_TITLE};justify: left;")
    
