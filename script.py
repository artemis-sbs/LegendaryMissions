import sbslibs
from  sbs_utils.handlerhooks import *
from sbs_utils.gui import Gui
from sbs_utils.mast.maststoryscheduler import StoryPage


class MyStoryPage(StoryPage):
    story_file = "siege.mast"

Gui.server_start_page_class(MyStoryPage)
Gui.client_start_page_class(MyStoryPage)
