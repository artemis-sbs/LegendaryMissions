
# TODO: Move to sbs_utils?

from sbs_utils.pages.layout.column import Column
from sbs_utils.pages.layout.bounds import Bounds
from sbs_utils.pages.layout.clickable import Clickable
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.style import apply_control_styles
from re import sub
from sbs_utils.procedural.execution import task_schedule

class Spinner(Column):
    """
    A gui element that creates two buttons, one on top of the other.
    """
    default_top_icon = 148
    default_bottom_icon = 150

    show_top_icon = True
    show_bottom_icon = True

    # Callable or label
    on_top_pressed = None
    on_bottom_pressed = None

    def __init__(self, tag, props) -> None:
        super().__init__()
        self.tag = tag
        self.props = props
        self.square = True

    def _present(self,  event):
        ctx = FrameContext.context
        top,bottom = self.splitBoundsHorizontally(self.bounds)
        if self.show_top_icon:
            top_tag = self.tag + "_top"
            top_icon_props = self.override_prop_icons(self.default_top_icon)
            ctx.sbs.send_gui_iconbutton(event.client_id, self.region_tag,
                top_tag, top_icon_props, 
                top.left,top.top, top.right, top.bottom)
        if self.show_bottom_icon:
            bottom_tag = self.tag + "_bottom"
            bottom_icon_props = self.override_prop_icons(self.default_bottom_icon)
            ctx.sbs.send_gui_iconbutton(event.client_id, self.region_tag,
                bottom_tag, bottom_icon_props,
                bottom.left, bottom.top, bottom.right, bottom.bottom)
        self.data["tag"] = self.tag
        
    def set_on_top_pressed(self, label):
        self.on_top_pressed = label
    def set_on_bottom_pressed(self, label):
        self.on_bottom_pressed = label

    @property
    def value(self):
         return self.props
       
    @value.setter
    def value(self, v):
        self.props = v
    def update(self, props):
        self.props = props

    def on_message(self, event):
        Clickable.clicked[event.client_id] = self #Not sure what this does tbh
        handler = None
        if event.sub_tag.find(self.data["tag"]) == -1:
            return
        if event.sub_tag.find("top") != -1:
            # event.sub_tag = event.sub_tag.replace("_top","")
            handler = self.on_top_pressed
        elif event.sub_tag.find("bottom") != -1:
            # event.sub_tag = event.sub_tag.replace("_bottom","")
            handler = self.on_bottom_pressed
        if handler is not None:
            if callable(handler):
                handler(event, self.data)
            else:
                data = self.data
                data["EVENT": event]
                task_schedule(handler, data)

    def splitBoundsHorizontally(self, bounds):
        """
        Converts the provided bounds into two separate bounds that together equal the provided bound.
        """
        middle_bound = (bounds.bottom-bounds.top)/2 + bounds.top
        top = Bounds(bounds.left,bounds.top,bounds.right,middle_bound)
        bottom = Bounds(bounds.left, middle_bound, bounds.right, bounds.bottom)
        return top,bottom
    
    def override_prop_icons(self, value):
        """
        Helper function to get the correct props string for the gui element
        """
        props = self.props
        ret = sub(r"icon_index:[ \t]?\d*",f"icon_index: {value}", props) # replace existing icon idex (for if someone tries to give it an icon_index)
        if ret.find("icon_index") == -1:
            ret = f"icon_index:{value};" + ret # If the icon_index isn't set, add it.
        return ret
    
def gui_spinner(props, style=None, data=None, on_press_top=None, on_press_bottom=None, default_top_icon=148, default_bottom_icon=150):
    """
    Build an Spinner gui element with two buttons stacked on top of each other. 
    """
    page = FrameContext.page
    task = FrameContext.task
    if page is None:
        return None
    tag = page.get_tag()
    props = task.compile_and_format_string(props)
    layout_item = Spinner(tag, props)
    # layout_item.is_sub_task = is_sub_task
    layout_item.default_top_icon = default_top_icon
    layout_item.default_bottom_icon = default_bottom_icon
    layout_item.data = data
    layout_item.set_on_bottom_pressed(on_press_bottom)
    layout_item.set_on_top_pressed(on_press_top)
    apply_control_styles(".spinner", style, layout_item, task)
    # Last in case tag changed in style
    runtime_item = None
    # runtime_item = MessageHandler(layout_item, task, on_press, is_sub_task)

    page.add_content(layout_item, runtime_item)
    # page.add_content(layout_item)
    return layout_item