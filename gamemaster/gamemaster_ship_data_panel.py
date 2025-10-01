# LISTBOX STUFF -----------------------------
from sbs_utils.pages.widgets.layout_listbox import LayoutListBoxHeader, LayoutListbox
from sbs_utils.procedural.gui import gui_list_box, gui_message_callback, gui_row, gui_text, gui_icon_button, gui_blank, gui_sub_section, gui_represent, gui_hide, gui_show
from sbs_utils.procedural.execution import gui_get_variable, gui_set_variable
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_set, to_object, to_blob, to_id
def buildListboxHeader(label, collabsible=True):
    return LayoutListBoxHeader(label, collabsible)

# def ship_inventory_category(item):
#     LayoutListBoxHeader(item.label, True)

class ShipInventoryItem:
        """
        Class that defines all required information for an item for the ShipInventory listbox builder
        """
        
        name = ""
        """Display name of the item"""
        agent = 0
        """The agent or agent ID of the selected ship"""
        blob = True
        """Is the key relevant for the ship's blob (data_set) (True), or the Agent's inventory(False)?"""
        key = ""
        """The key representing the desired data"""
        increment = 1
        """How much should the value change by?"""
        category = "Default"
        """The category, or header, under which the value should be placed"""
        key_index = 0
        """For keys that return a list, the index of the needed information"""
        inventory = None
        """The parent listbox layout item. Don't mess with this."""
        value = None
        """The current value to be displayed by the item"""
        def __init__(self, name, key, agent=None, blob=True, increment=1, category="Default", key_index=0) -> None:
            """
            Build a ShipInventoryItem, use to generate an item to add to a ShipInventory object

            args:
                name(str): The display name of the item
                key(str): The inventory or blob key that is being modified.
                agent(Agent|int): The agent or ID of the space object being modified.
                blob(boolean): If True, the key is for blob data. If false, it is an inventory key.
                increment(int): The value by which the value will be modified. (Must be positive. If not, is made positive.)
                category(str): The category or header under which the item will be placed.
                key_index(int): If the key is a list, then the key_index will be used. E.g. the blob key "shield_val" requires an index.
            """
            increment = abs(increment)
            agent = to_id(agent)
            self.name = name
            self.key = key
            self.agent = agent
            self.blob = blob
            self.increment = increment
            self.category = category
            self.key_index = key_index

        def __str__(self) -> str:
            return str({"name":self.name,"agent": self.agent, "key": self.key, "blob": self.blob, "increment": self.increment, "category":self.category, "key_index": self.key_index})

def build_ship_inventory_item(name, key, blob=True, increment=1, category="Default", key_index=0):
    """
    Build a ShipInventoryItem, use to generate an item to add to a ShipInventory object

    args:
        name(str): The display name of the item
        key(str): The inventory or blob key that is being modified.
        agent(Agent|int): The agent or ID of the space object being modified.
        blob(boolean): If True, the key is for blob data. If false, it is an inventory key.
        increment(int): The value by which the value will be modified. (Must be positive. If not, is made positive.)
        category(str): The category or header under which the item will be placed.
        key_index(int): If the key is a list, then the key_index will be used. E.g. the blob key "shield_val" requires an index.
    """
    return ShipInventoryItem(name,key,blob,increment,category,key_index)

def add_ship_inventory_item(name, key, blob=True, increment=1, category="Default", key_index=0, inventory_key=None):
    """
    Add an item to the Ship Inventory (specified by `inventory_key`.)

    Args:
        name(str): The display name of the item
        key(str): The inventory or blob key that is being modified.
        agent(Agent|int): The agent or ID of the space object being modified.
        blob(boolean): If True, the key is for blob data. If false, it is an inventory key.
        increment(int): The value by which the value will be modified. (Must be positive. If not, is made positive.)
        category(str): The category or header under which the item will be placed.
        key_index(int): If the key is a list, then the key_index will be used. E.g. the blob key "shield_val" requires an index.
        inventory_key(str): The key specifying which ShipInventory object to which the item will be added.
    """
    if inventory_key is None:
        inventory_key = "SHIP_INVENTORY"
    inv = gui_get_ship_inventory(inventory_key)
    if inv is None:
        # NOTE: Could have this initialize the element, but there's no guarantee it would happen in a place where it would show up properly. It should be initialized in the console gui setup
        print("ERROR: ShipInventory not initialized. Call gui_ship_inventory() to initialize the ShipInventory and associated listbox first.")
        return
    inv.add_item(name, key, blob, increment, category, key_index)

class ShipInventory:
    tag = "SHIP_INVENTORY"
    items = list()
    categories = set() # Don't want duplicate categories
    agent = None
    layout_item = None
    def __init__(self, agent, tag=None) -> None:
        self.agent = agent
        if tag is not None:
            self.tag = tag
        if tag is None:
            tag = self.tag
        gui_set_variable(f"SHIP_INVENTORY_{tag}", self)

    def add_item(self, name, key, blob=True, increment=1, category="Default", key_index=0):
        """
        Build a ShipInventoryItem, and add it to the ShipInventory. Use to generate an item to add to a ShipInventory object

        args:
            name(str): The display name of the item
            key(str): The inventory or blob key that is being modified.
            agent(Agent|int): The agent or ID of the space object being modified.
            blob(boolean): If True, the key is for blob data. If false, it is an inventory key.
            increment(int): The value by which the value will be modified. (Must be positive. If not, is made positive.)
            category(str): The category or header under which the item will be placed.
            key_index(int): If the key is a list, then the key_index will be used. E.g. the blob key "shield_val" requires an index.
        """
        i = ShipInventoryItem(name,key,self.agent,blob,increment,category,key_index)
        self.add_ship_inventory_item(i)

    def change_agent(self, agent):
        """
        Update the agent for which the data is being displayed.
        """

        self.agent = agent
        if agent is None:
            self.hide()
            return
        
        for i in self.items:
            i.agent = agent

        # if self.layout_item is not None:
        #     self.layout_item.represent(FakeEvent(""))

    def add_ship_inventory_item(self, item):
        """
        Add a ShipInventoryItem to this ShipInventory
        args:
            item(ShipInventoryItem): The ShipInventoryItem to add.
        """
        if isinstance(item,ShipInventoryItem):
            item.agent = self.agent
            self.items.append(item)
            self.categories.add(item.category)
        else:
            print("NOT a ShipInventoryItem")

    def build_list_box(self):
        lb = gui_list_box([],"",item_template=ship_inventory_item,collapsible=True)
        self.layout_item = lb
        # self.rebuild()
        return lb
    
    def rebuild(self):
        if self.agent is None:
            self.layout_item.items = []
            return
        ret = []
        cats = sorted(list(self.categories))
        for cat in cats:
            # Remember the state of the list box header, so if it's collapsed, it will stay so, and vice versa
            collapse = True
            for item in self.layout_item.items:
                if isinstance(item, LayoutListBoxHeader):
                    if item.label == cat:
                        collapse = item.collapse
                        break
            cat_items = []
            
            # Now we find all the items that have this category and add them.
            for item in self.items:
                if item.category == cat:
                    item.inventory = self.layout_item
                    val = 0
                    if item.blob:
                        blob = to_blob(item.agent)
                        if blob is not None:
                            val = blob.get(item.key, item.key_index)
                    else:
                        val = get_inventory_value(item.agent, item.key)
                    if not isinstance(val, int) and not isinstance(val, float): # Or if it's None
                        print(f"{item.key} is not a number! Skipping!")
                        continue
                    item.value = val
                    cat_items.append(item)
                    # ret.append(item)
            if len(cat_items) > 0:
                ret.append(LayoutListBoxHeader(cat, collapse))
                ret.extend(cat_items)

        # Set the items in the list box.
        self.layout_item.items = ret
    
    def represent(self):
        gui_represent(self.layout_item)

    def hide(self):
        gui_hide(self.layout_item)

    def show(self):
        gui_show(self.layout_item)
        


def gui_ship_inventory(agent, tag=None) -> ShipInventory:
    """
    Create a new ShipInventory object.
    Args:
        agent(id|Agent): The id or agent for which information will be displayed
        tag(str): The tag to use for this gui element
    """
    return ShipInventory(agent, tag)

def gm_show_ship_info(a,b,c,d,e):
    inv = gui_get_ship_inventory()
    if inv is not None:
        inv.show()
def gm_hide_ship_info(a,b,c,d,e):
    inv = gui_get_ship_inventory()
    if inv is not None:
        inv.hide()

def gui_get_ship_inventory(tag=None):
    """
    Get the ShipInventory object with the given tag. Returns None if it doesn't exist.
    """
    if tag is None:
        tag = "SHIP_INVENTORY"
    return gui_get_variable(f"SHIP_INVENTORY_{tag}")

def change_inventory_value(event, data, mult, tag):
    """
    Called when a +/- button is pressed on a ShipInventory LayoutListBox
    """
    if event.sub_tag != tag:
        return
    new = 0
    if data.blob:
        blob = to_blob(data.agent)
        old = blob.get(data.key, data.key_index)
        if old is None:
            old = 0
        if isinstance(old, int) or isinstance(old, float):
            new = old + abs(data.increment)*mult
            if new < 0:
                new = 0
            blob.set(data.key, new, data.key_index)
        else:
            Exception(f"{data.key} is not a valid ShipInventory value - must be a number!")
    else:
        old = get_inventory_value(data.agent, data.key, None)
        if old is None:
            old = 0
        new = old + abs(data.increment)*mult
        if new < 0:
            new = 0
        set_inventory_value(data.agent, data.key, new)
        new = int(new)
    data.value = new
    # We don't need to update the text here because represent will do this for us.
    # Also, just using represent on the gui_text is bugged.
    data.inventory.represent(event)

def ship_inventory_item(item):
    """
    args: 
        item (dict): A dict containing the following keys:
            name: The display name of the item
            agent: The ID of the selected space object or agent
            blob: True if the key belongs to the blob, False if it's an inventory key
            key: The key for which the value will be changed
            increment: The quantity to increase or decrease the value by
            category: The name of the category this item should belong to
    """
    
    collapsable =  isinstance(item, LayoutListBoxHeader)
    if collapsable:
        gui_row("row-height: 1.2em;")
        if not item.collapse:
            gui_text(f"$text:{item.label};justify: center;color:#02FF;", "background: #FFFC")
        else:
            gui_text(f"$text:{item.label};justify: center;color:#FFF;", "background: #0173")
    else:
        val = item.value

        # We need to do the calculations here because of the refresh logic
        val = 0
        if item.blob:
            blob = to_blob(item.agent)
            if blob is not None:
                val = blob.get(item.key, item.key_index)
        else:
            val = get_inventory_value(item.agent, item.key)
        if not isinstance(val, int) and not isinstance(val, float): # Or if it's None
            print(f"{item.key} is not a number! Skipping!")
            return


        gui_row("row-height: 5px;") # Gap between items
        gui_row("row-height: 2em;")

        # Text Display of item
        gui_text(f"$text:{item.name};justify: center;")

        # First Icon button
        sub = gui_icon_button("icon_index:155;color:white;")

        # The number
        val = int(val) #Just use integers
        value = gui_text(f"$text:{val};justify:center")

        # Second Icon button
        add = gui_icon_button("icon_index:154;color:white;")

        gui_message_callback(sub, lambda e: change_inventory_value(e, item, -1, sub.tag))
        gui_message_callback(add, lambda e: change_inventory_value(e, item, 1, add.tag))
