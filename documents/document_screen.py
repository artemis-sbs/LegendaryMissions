from sbs_utils.procedural.gui import gui_row, gui_text, gui_icon
# MAST sees every module-level name an addon's `.py` imports - this is how
# quest_tab.mast reaches the shared-media resolver.
from sbs_utils.procedural.media_paths import media_shared
from sbs_utils.procedural.quest import QuestState, document_get_amd_file 

from sbs_utils.procedural.gui.listbox import gui_list_box_is_header
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.inventory import set_inventory_value
from sbs_utils import fs
from sbs_utils.agent import Agent


def document_link_to(obj_list, document):
    """The `on_link` for a document's text area: a `[Text](ref://key)` link SELECTS
    that topic in the list beside it.

    So a link and a click on the list are the same thing - the list's own `on change`
    swaps the page, the highlight follows, and Back-and-forth through the list still
    works. The key is a record's key as written in its heading (`engineering`); a
    nested record whose key carries a path matches on its last part too.

    A key nothing matches does nothing, rather than guessing a topic.
    """
    def _go(key, _widget):
        want = str(key or "").strip().lower()
        for item in document:
            data = item.data if gui_list_box_is_header(item) else item
            if data is None:
                continue
            k = str(data.get("key") or "").strip().lower()
            if k and (k == want or k.rsplit("/", 1)[-1] == want):
                obj_list.value = data
                return
    return _go


def document_item(item):
    
    if not gui_list_box_is_header(item):
        gui_row("row-height: 1.5em;padding:8px,0,0,0;")
        icon_index = item.get("icon_index")
        icon_color = item.get("icon_color","white")
        if item.get("state"):
            if item.state == QuestState.COMPLETE:
                icon_index = 101
                icon_color = "#151"
            elif item.state == QuestState.FAILED:
                icon_index = 101
                icon_color = "#a22"
            else:
                icon_index = 121
                icon_color = "#eee"
        if icon_index is not None:
            gui_icon(f"icon_index:{icon_index};color:{icon_color};", "padding:5px,0,5px,0;")
        display_text = item.get("display_text")
        gui_text(f"$text:{display_text};justify: left;draw_layer:1000;","padding:5px,6px,0,0;")
    else:
        gui_row("row-height: 1.5em;padding:8px,0,0,0;")

        data = item.data
        if data is not None:
            if not gui_list_box_is_header(item) and item.get("state"):
                if data.state == QuestState.COMPLETE:
                    gui_icon("icon_index:101;color:#151;", "padding:0,0,5px,0;")
                else:
                    gui_icon("icon_index:121;color:#eee;", "padding:0,0,5px,0;")
                
        icon_index = 155 if not item.collapse else 154

        
        text = gui_text(f"$text:{item.label};justify: left;color:#fff;", "padding:5px,6px,0,0;background: #1578")
        # if item.data is not None and not data.get("root"):
        #     icon = gui_icon(f"icon_index:{icon_index};color:#fff;", "padding:0,0,5px,0;background: #1578;")
        if item.data is not None and not data.get("root"):
            icon = gui_icon(f"icon_index:{icon_index};color:#fff;", "padding:0,0,5px,0;background: #1578;")
            if item.selectable:
                icon.click_text = ""
                icon.click_tag = item.collapse_tag
                icon.click_background = "#aaaa"
                icon.click_color = "black"
                icon.background_color = "#1576"
                text.background_color = "#1576"
    return


