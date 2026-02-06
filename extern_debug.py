#
# Use this file to debug the runnign of MAST outside of Cosmos
# See extern_debug.mast for starting a map
#

import sys
# Make the main i.e. command line module the script module
sys.path.append("../__lib__/artemis-sbs.sbs_utils.v1.3.0.sbslib")

def mock_sbs_runtime(file):
    sys.modules['script'] = sys.modules.get('__main__')
    # import sbslibs
    #sys.path.append("../../../PyAddons")
    #import sbslibs
    sys.path.append("../sbs_utils/mock")

    # this loads all the sbs libs in story.json
    import sbs_utils.mock.sbs as sbs



    # sbs_utils should now be loaded
    from sbs_utils.mast.mast_node import MastNode, mast_node, IF_EXP_REGEX
    from sbs_utils.mast.mast import Mast
    from sbs_utils.mast import core_nodes
    from sbs_utils.mast_sbs import story_nodes
    from sbs_utils import fs

    #
    # Get Mast up in running within
    #
    import os
    fs.exe_dir = os.path.abspath("../../..")
    script_dir = os.path.dirname(os.path.abspath(__file__))


    from sbs_utils.mast_sbs import mast_sbs_procedural
    from sbs_utils.mast.mast_globals import MastGlobals
    from sbs_utils.mast_sbs.maststorypage import StoryPage
    from sbs_utils.helpers import FrameContext, Context, FakeEvent
    from sbs_utils.agent import Agent
    from sbs_utils.handlerhooks import cosmos_event_handler

    sim = sbs.create_new_sim()

    Agent.SHARED.set_inventory_value("sim", sim)
    ctx = Context(sim, sbs, FakeEvent())
    #page = StoryPage()
    #FrameContext.page = page
    FrameContext.context = ctx


    from sbs_utils.gui import Gui
    class MyStoryPage(StoryPage):
            story_file = file
        
    Gui.server_start_page_class(MyStoryPage)
    Gui.client_start_page_class(MyStoryPage)

    
    
    event = FakeEvent(0, "mission_tick")

    import time
    while True:
        cosmos_event_handler(sim,event)
        sim._time_tick_counter += 1
        time.sleep(0.001)

mock_sbs_runtime("extern_debug.mast")