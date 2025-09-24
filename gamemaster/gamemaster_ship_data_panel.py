# LISTBOX STUFF -----------------------------
from sbs_utils.pages.widgets.layout_listbox import LayoutListBoxHeader, LayoutListbox
from sbs_utils.procedural.gui import gui_list_box, gui_message_callback, gui_row, gui_text, gui_icon_button, gui_blank, gui_sub_section
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
        def __init__(self, name, key, agent, blob=True, increment=1, category="Default", key_index=0) -> None:
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

def build_ship_inventory_item(self, name, key, agent, blob=True, increment=1, category="Default", key_index=0):
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
    return ShipInventoryItem(name,key,agent,blob,increment,category,key_index)

class ShipInventory:
    tag = "SHIP_INVENTORY"
    items = list()
    categories = set() # Don't want duplicate categories
    def __init__(self, tag=None) -> None:
        if tag is not None:
            self.tag = tag
        gui_set_variable(f"SHIP_INVENTORY_{tag}", self)
    def add_item(self, name, key, agent, blob=True, increment=1, category="Default", key_index=0):
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
        i = ShipInventoryItem(name,key,agent,blob,increment,category,key_index)
        self.add_ship_inventory_item(i)

    def add_ship_inventory_item(self, item):
        """
        Add a ShipInventoryItem to this ShipInventory
        args:
            item(ShipInventoryItem): The ShipInventoryItem to add.
        """
        if isinstance(item,ShipInventoryItem):
            self.items.append(item)
            self.categories.add(item.category)
        else:
            print("NOT a ShipInventoryItem")

    def build_list_box(self):
        ret = []
        lb = gui_list_box([],"",item_template=ship_inventory_item,collapsible=True)
        cats = sorted(list(self.categories))
        for cat in cats:
            ret.append(LayoutListBoxHeader(cat, True))
            for item in self.items:
                if item.category == cat:
                    item.inventory = lb
                    ret.append(item)
        lb.items = ret
        return lb


def gui_ship_inventory(tag=None) -> ShipInventory:
    """
    Create a new ShipInventory object.
    """
    return ShipInventory(tag)

def gui_get_ship_inventory(tag=None):
    """
    Get the ShipInventory object with the given tag.
    """
    if tag is None:
        tag = "SHIP_INVENTORY"
    return gui_get_variable(f"SHIP_INVENTORY_{tag}")

def change_inventory_value(event, data, mult, tag, text):
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
    text.update(f"$text:{new}")
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
        val = 0
        if item.blob:
            val = to_blob(item.agent).get(item.key, item.key_index)
        else:
            val = get_inventory_value(item.agent, item.key)
        if not isinstance(val, int) and not isinstance(val, float): # Or if it's None
            print(f"{item.key} is not a number! Skipping!")
            return
        gui_row("row-height: 2em;")
        # First Icon button
        sub = gui_icon_button("icon_index:155;color:white;")

        # Text Display of item
        gui_text(f"$text:{item.name};justify: center;")

        # Second Icon button
        add = gui_icon_button("icon_index:154;color:white;")

        val = int(val) #Just use integers
        value = gui_text(f"$text:{val};justify:center")

        gui_message_callback(sub, lambda e: change_inventory_value(e, item, -1, sub.tag, value))
        gui_message_callback(add, lambda e: change_inventory_value(e, item, 1, add.tag, value))
