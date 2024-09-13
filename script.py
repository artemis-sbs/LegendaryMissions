try:
    import sbslibs
    from sbs_utils.handlerhooks import *
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
except Exception as e:
    message = e
    def cosmos_event_handler(sim, event):
        import sbs
        sbs.send_gui_clear(event.client_id, "")
        sbs.send_gui_text(
            event.client_id,"", "text", f"$text:sbs_utils runtime error^{message};", 0, 0, 80, 95)
        sbs.send_gui_complete(event.client_id, "")
