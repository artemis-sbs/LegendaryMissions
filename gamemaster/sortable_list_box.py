
# TODO: Move to sbs_utils?

from sbs_utils.pages.widgets.layout_listbox import LayoutListbox, LayoutListBoxHeader
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.style import apply_control_styles
from spinner import gui_spinner

class ListBoxSortable(LayoutListbox):
    
    def move_item_up(self, event, data):
        cur_index = data["index"]
        if cur_index == 0:
            return # Can't go lower
        item = self.items[cur_index]
        self.items.remove(item)
        self.items.insert(cur_index - 1, item)
        self.represent(event)

    def move_item_down(self, event, data):
        cur_index = data["index"]
        if cur_index == len(self.items)-1:
            return # Can't go higher
        item = self.items[cur_index]
        self.items.remove(item)
        self.items.insert(cur_index + 1, item)
        self.represent(event)

    def default_item_template(self, item):
        from sbs_utils.procedural.gui import gui_row, gui_text
        # gui_row("row-height: 1.2em;")
        task = FrameContext.task
        # task.set_variable("LB_ITEM", item)
        if self.item_template is not None:
            msg = task.compile_and_format_string(self.item_template)
        else:
            msg = item
        collapsable =  isinstance(item, LayoutListBoxHeader)
        if collapsable:
            gui_row("row-height: 1.2em;")
            if not item.collapse:
                gui_text(f"$text:{item.label};justify: center;color:#02FF;", "background: #FFFC")
            else:
                gui_text(f"$text:{item.label};justify: center;color:#FFF;", "background: #0173")
        else:
            index = self.items.index(item)
            gui_row("row-height:2px;")
            gui_text("","background:#7a7a7a;")
            gui_row("row-height: 2.4em;")
            gui_text(f"$text:{msg};justify: left;","background:#0173;")
            arrow = gui_spinner("color:white;","",{"index":index},self.move_item_up,self.move_item_down)
            if index == 0:
                arrow.show_top_icon = False
            elif index == len(self.items)-1:
                arrow.show_bottom_icon = False
            gui_row("row-height:2px;")
            gui_text("","background:#7a7a7a;")

def gui_list_box_sortable(items, style, 
                 item_template=None, title_template=None, 
                 section_style=None, title_section_style=None,
                 select=False, multi=False, carousel=False,  collapsible=False,read_only=False):
    """
    Build a ListBoxSortable gui element

    Args:
        items: A list of the items that should be included
        style (str): Custom style attributes
        item_template (list(str|LayoutListBoxHeader)): A list of strings, or, if a header is desired, then that item should be a LayoutListBoxHeader object
        title_template (str|callable): if a callable, will call the function to build the title. If a string, then title_template will be used as the title of the listbox
        section_style (str): Style attributes for each section
        title_section_style (str): Style attributes for the title
        select (boolean): If true, item(s) within the listbox can be selected.
        multi (boolean): If true, multiple items can be selected. Ignored if `select` is None
        carousel (boolean): If true, will use the carousel styling, e.g. the ship type selection menu
        collapsible (boolean): If true, clicking on a header will collapse everything until the next header
        read_only (boolean): Can the items be modified
    Returns:
        The LayoutListBox layout object
    """
    page = FrameContext.page
    task = FrameContext.task
    if page is None:
        return None
    tag = page.get_tag()
    # The gui_content sets the values
    layout_item = ListBoxSortable(0, 0, tag, items,
                 item_template, title_template, 
                 section_style, title_section_style,
                 select,multi, carousel,  collapsible, read_only)

    apply_control_styles(".listbox", style, layout_item, task)
    # Last in case tag changed in style
    page.add_content(layout_item, None)
    return layout_item