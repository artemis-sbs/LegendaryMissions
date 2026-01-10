from sbs_utils.procedural.gui import gui_row, gui_text, gui_hole
from sbs_utils.procedural.quest import quest_agent_quests, QuestState, quest_add_yaml
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui.listbox import gui_list_box_header, gui_list_box_is_header
from sbs_utils.agent import Agent




def quest_item(item):
    
    if not gui_list_box_is_header(item):
        gui_row("row-height: 1em;padding:5px,0,5px,0;")
        id = item.get("id")
        indent = id.count("/") * 15
        

        display_text = "  "*indent + item.get("display_text")
        gui_text(f"$text:{display_text};justify: left;",f"padding:{indent}px,0,0.1em,0;")
    else:
        gui_row("row-height: 1em;padding:5px,0,5px,0;")
        if not item.collapse:
            label = f"- {item.label}"
            gui_text(f"$text:{label};justify: left;color:#02FF;", "background: #FFFC")
        else:
            label = f"+ {item.label}"
            gui_text(f"$text:{label};justify: left;color:#FFF;", "background: #0173")
        return
    
def quest_title():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text(f"$text:QUESTS;justify: left;")


def quest_flatten_list():
    game_quests = quest_agent_quests(Agent.SHARED_ID)
    client_id = FrameContext.client_id
    client_quests = None
    ship_quests = None

    if client_id != 0:
        client_quests = quest_agent_quests(client_id)
        ship_id = FrameContext.context.sbs.get_ship_of_client(client_id)
        if ship_id != 0:
            ship_quests = quest_agent_quests(ship_id)

    ret = []

    def append_quests(quests, header=None):
        active = []
        idle = []
        completed = []
        
        if len(quests)>0:
            if header is not None:
                active.append(gui_list_box_header(header))

            for q in quests.values():
                state = q.get("state", QuestState.IDLE)
                if  state == QuestState.ACTIVE:
                    active.append(q)
                    active.extend(append_quests(q.children))
                if  state == QuestState.IDLE:
                    idle.append(q)
                    idle.extend(append_quests(q.children))
                if state == QuestState.COMPLETE:
                    completed.append(q)
                    completed.extend(append_quests(q.children))
            active.extend(idle)
            active.extend(completed)
            
        return active


    ret.extend(append_quests(game_quests, "Game"))
    ret.extend(append_quests(client_quests, "Client"))
    ret.extend(append_quests(ship_quests, "Ship"))

    return ret




def quest_create_test_data():
    yaml_text = """
quest1:
    display_text: quest1
    description: Track the number of quest1
quest2:
    display_text: quest2
    description: |+

        Track the number of quest2

        $h2 This is headind 2

        $t Title

        $h3 This is H3

        $ol 
        One
        Two
        Three

        $h3 This is H3

        $ul
        Blue
        Red 
        Green

        $h3 This is H3
        
kills:
    display_text: kills
    description: Track the number of kills
    children:
        kills25:
            display_text: kill 25
        kills50:
            display_text: kill 50
        kills100:
            display_text: kill 100
"""
    # signal_register("quest_activated", quest_activated)
    quest_add_yaml(Agent.SHARED_ID, yaml_text)
    client_id = FrameContext.client_id
    if client_id == 0:
        return

    ship_id = FrameContext.context.sbs.get_ship_of_client(client_id)
    if ship_id == 0:
        return
    
    quest_add_yaml(client_id, yaml_text)
    quest_add_yaml(ship_id, yaml_text)
  