import sbslibs
from  sbs_utils.handlerhooks import *
from sbs_utils.gui import Gui
from sbs_utils.mast.maststorypage import StoryPage
from sbs_utils.mast.mast import Mast

class MyStoryPage(StoryPage):
    story_file = "story.mast"
#
# Uncomment this out to have Mast show the mast code in 
# runtime errors.
# Comment it out will reduce memory used.
#
Mast.include_code = True

Gui.server_start_page_class(MyStoryPage)
Gui.client_start_page_class(MyStoryPage)
