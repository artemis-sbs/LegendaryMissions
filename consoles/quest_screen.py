from sbs_utils.procedural.gui import gui_row, gui_text, gui_icon, gui_blank
from sbs_utils.procedural.quest import quest_agent_quests, QuestState, quest_add_yaml
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui.listbox import gui_list_box_header, gui_list_box_is_header
from sbs_utils.agent import Agent
from sbs_utils.mast.mast_node import MastDataObject
from sbs_utils.procedural.inventory import set_inventory_value
from sbs_utils import fs


def quest_item(item):
    
    if not gui_list_box_is_header(item):
        gui_row("row-height: 1.5em;padding:8px,0,0,0;")
        if item.state == QuestState.COMPLETE:
            gui_icon("icon_index:101;color:#151;", "padding:0,0,5px,0;")
        elif item.state == QuestState.FAILED:
            gui_icon("icon_index:101;color:#a22;", "padding:0,0,5px,0;")
        else:
            gui_icon("icon_index:121;color:#eee;", "padding:0,0,5px,0;")
        display_text = item.get("display_text")
        gui_text(f"$text:{display_text};justify: left;draw_layer:1000;","padding:5px,6px,0,0;")
    else:
        gui_row("row-height: 1.5em;padding:8px,0,0,0;")

        data = item.data
        if data is not None:
            if data.state == QuestState.COMPLETE:
                gui_icon("icon_index:101;color:#151;", "padding:0,0,5px,0;")
            else:
                gui_icon("icon_index:121;color:#eee;", "padding:0,0,5px,0;")
            
        icon_index = 155 if not item.collapse else 154

        
        text = gui_text(f"$text:{item.label};justify: left;color:#fff;", "padding:5px,6px,0,0;background: #1578")
        icon = gui_icon(f"icon_index:{icon_index};color:#fff;", "padding:0,0,5px,0;background: #1578;")
        if item.selectable:
            icon.click_text = ""
            icon.click_tag = item.collapse_tag
            icon.click_background = "#aaaa"
            icon.click_color = "black"
            icon.background_color = "#1576"
            text.background_color = "#1576"
    return
    
def quest_title():
    gui_row("row-height: 1.5em;padding:3px;background:#157e;")
    gui_text(f"$text:QUESTS;justify: center;")


def quest_flatten_list():
    game_quests = quest_agent_quests(Agent.SHARED_ID)
    # game_quests = document_get_amd_file("consoles/quest.amd")
    client_id = FrameContext.client_id
    client_quests = None
    ship_quests = None

    if client_id != 0:
        client_quests = quest_agent_quests(client_id)
        ship_id = FrameContext.context.sbs.get_ship_of_client(client_id)
        if ship_id != 0:
            ship_quests = quest_agent_quests(ship_id)

    ret = []

    def append_quests(quests, header=None, indent=0, data=None):
        active = []
        idle = []
        completed = []
        failed = []

        if quests is None:
            return []

        if header is not None:
            header_indent = max(indent-1,0)
        # root headers have no data
        # when data is not None this is adding the 
        # Parent so the indent is one less
        
        children = quests.get("children")
        if data is None:
            active.append(gui_list_box_header(header,False,header_indent, data is not None,data))
        elif len(children)>0:
            active.append(gui_list_box_header(header,False,header_indent, data is not None,data))
        
        if len(children)==0 and data is not None:
            return [data]

        for q in children:
            q = MastDataObject(q)
            q.indent = indent

            state = q.get("state", QuestState.IDLE)
            if isinstance(state, str):
                try:
                    state = QuestState[state]
                    q.state = state
                except Exception:
                    state = QuestState.IDLE
            if  state == QuestState.ACTIVE:
                active.extend(append_quests(q, q.display_text, indent+1, q))
            if  state == QuestState.IDLE:
                idle.extend( append_quests(q, q.display_text, indent+1, q))
            if state == QuestState.COMPLETE:
                completed.extend(append_quests(q, q.display_text, indent+1, q))
            if state == QuestState.FAILED:
                failed.extend(append_quests(q, q.display_text, indent+1, q))

        active.extend(idle)
        active.extend(completed)
        active.extend(failed)
        
        return active


    ret.extend(append_quests(game_quests, "Game"))
    ret.extend(append_quests(client_quests, "Client"))
    ret.extend(append_quests(ship_quests, "Ship"))

    return ret




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
  

import re
def document_get_amd_file(file_path, strip_comments=True):
    toc = {"children": [], "description":""}
    toc_stack = [toc]
    rule_section = re.compile(r"#+[ \t]+\[(?P<display_text>.*)\]\((?P<urn>.*)\)[ \t]*")

    lines = []
    try:
        with open(file_path, "r") as file:
            lines = file.readlines()
    except Exception as e:
        print("no file")

    for i, line in enumerate(lines):
        m = rule_section.match(line)

        #
        # Check for
        #
        if m is not None:
            level = line.split(None, 1)
            level = len(level[0])

            data = m.groupdict()
            display_text = data.get("display_text")
            
            urn = data.get("urn")
            urn = urn.split("?", 1)
            key = urn[0]
            
            section = {"key": key, "display_text": display_text, "children": [], "description":"", "state": 0}

            if len(urn) == 2:
                query_string = urn[1].split("&")
                for kvalue in query_string:
                    kvalue = kvalue.split("=")
                    if len(kvalue) != 2:
                        raise Exception(f"ERROR: URN invalid line Line {i}\n{line}")
                    this_key = kvalue[0]
                    value = kvalue[1]
                    section[this_key] = value
            elif len(urn) != 1:
                raise Exception(f"ERROR: URN invalid line Line {i}\n{line}")

            # The root is level 0
            if level == len(toc_stack):
                toc_stack.append(section)
            elif level == len(toc_stack) + 1:
                toc_stack[level] = section
            elif level < len(toc_stack):
                toc_stack = toc_stack[: level + 1]
                toc_stack[level] = section
            else:
                raise Exception(f"ERROR: Document structure error Line {i}\n{line}")
            root = toc_stack[level - 1]
            children = root.get("children")
            children.append(section)
        elif strip_comments and line.startswith("//"):
            continue
        else:
            section = toc_stack[-1]
            desc = section.get("description", "")
            if len(desc)>0:
                desc += "\n"
            desc += line
            section["description"] = desc
    # fs.save_json_data(file_path+".json", toc)
    return toc
