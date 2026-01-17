from sbs_utils.procedural.gui import gui_row, gui_text, gui_icon, gui_blank
from sbs_utils.procedural.quest import quest_agent_quests, QuestState, quest_add_yaml
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui.listbox import gui_list_box_header, gui_list_box_is_header
from sbs_utils.agent import Agent




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
        
        if len(quests)>0:
            if header is not None:
                active.append(gui_list_box_header(header,False,indent, data is not None,data))

            for q in quests.values():
                q.indent = indent
                state = q.get("state", QuestState.IDLE)
                if  state == QuestState.ACTIVE:
                    active.append(q)
                    active.extend(append_quests(q.children))
                if  state == QuestState.IDLE:
                    c = append_quests(q.children, q.display_text, indent+1, q)
                    if len(c)>0:
                        idle.extend(c)
                    else:
                        idle.append(q)
                    
                    
                if state == QuestState.COMPLETE:
                    completed.append(q)
                    completed.extend(append_quests(q.children))
                if state == QuestState.FAILED:
                    failed.append(q)
                    failed.extend(append_quests(q.children))

            active.extend(idle)
            active.extend(completed)
            active.extend(failed)
            
        return active


    ret.extend(append_quests(game_quests, "Game"))
    ret.extend(append_quests(client_quests, "Client"))
    ret.extend(append_quests(ship_quests, "Ship"))

    return ret




def quest_create_test_data():
    yaml_text = """
quest1:
    display_text: quest1
    description: |+ 
        Track the number of quest1

        $$font:gui-2;color:blue;background:white This is white on blue

        $$font:gui-2;color:green;background:white 
        This is green on white
        still is
        and now

        but not now
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

        ## Example sub image

        ![](image://test2?scale=0.5&fill=center)

    

        ## Ship
        
        ![](ship://tsn_light_cruiser?height=100&align=center)

        ## Face

        ![](face://ter #964b00 8 1;ter #968b00 3 0;ter #968b00 4 0;ter #968b00 5 2;ter #fff 3 5;ter #964b00 8 4;?align=left)
        

        $h3 This is H3

        $ul
        Blue
        Red 
        Green
        Test

        ![](image://test?scale=0.25&fill=center)

        ![](image://ball?scale=0.25&fill=center&color=blue)

        


        $h3 This is H3

        # Heading one

        ### Heading 3
        
        1. This
        1. Is
        1. ordered

        - This
        - is 
        - unordered

        # End
        

kills:
    display_text: kills
    description: Track the number of kills
    children:
        kills25:
            display_text: kill 25
            state: COMPLETE
        kills50:
            display_text: kill 50
        kills100:
            display_text: kill 100
            state: FAILED
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
  