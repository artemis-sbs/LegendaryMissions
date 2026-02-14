from sbs_utils.procedural.gui import gui_row, gui_text, gui_icon
from sbs_utils.procedural.quest import QuestState, document_get_amd_file 

from sbs_utils.procedural.gui.listbox import gui_list_box_is_header
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.inventory import set_inventory_value
from sbs_utils import fs
from sbs_utils.agent import Agent


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
    


def quest_create_test_data():
    # signal_register("quest_activated", quest_activated)
    doc = document_get_amd_file(fs.get_mission_dir_filename("consoles/quest.amd"))

    client_id = FrameContext.client_id
    if client_id == 0:
        return

    ship_id = FrameContext.context.sbs.get_ship_of_client(client_id)
    if ship_id == 0:
        return
    
    set_inventory_value(Agent.SHARED_ID,"__quests__", doc)
    set_inventory_value(client_id,"__quests__", doc)
    set_inventory_value(ship_id, "__quests__",doc)
    return doc


