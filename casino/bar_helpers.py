"""Listbox templates for the bar (patron list + message board). gui_list_box
takes template functions (like the hangar roster), not the non-existent
`list_box_control` the old prototype used. Items are plain dicts with
`face`/`msg`/`call_sign` keys."""
from sbs_utils.procedural.gui import gui_row, gui_text, gui_face, gui_text_escape


def bar_message_template(item):
    gui_row("row-height: 4em; padding:4px;")
    face = item.get("face", "")
    if face:
        gui_face(face)
    gui_text(f"$text:{gui_text_escape(item.get('msg', ''))};justify:left;")

def bar_message_title():
    gui_row("row-height: 1.5em; padding:6px; background:#1578;")
    gui_text("$text:Conversation;justify:center;")

def bar_patron_template(item):
    gui_row("row-height: 4em; padding:4px;")
    face = item.get("face", "")
    if face:
        gui_face(face)
    gui_text(f"$text:{gui_text_escape(item.get('call_sign', 'pilot'))};justify:center;")

def bar_patron_title():
    gui_row("row-height: 1.5em; padding:6px; background:#1578;")
    gui_text("$text:Patrons;justify:center;")
