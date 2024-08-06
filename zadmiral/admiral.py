from sbs_utils.procedural.inventory import  get_inventory_value, set_inventory_value
from sbs_utils.helpers import FrameContext


def admiral_show_nav_area(ORIGIN_ID, pos, size_delta, text, selection_type, color):
    x = pos.x
    y = pos.z

    sim = FrameContext.context.sim

    size = get_inventory_value(ORIGIN_ID, f"ADMIRAL_{selection_type}_SIZE", 5000)
    size += size_delta
    size = max(min(50000, size), 2000)
    if size_delta < 0:
        size = 5000

    set_inventory_value(ORIGIN_ID, f"ADMIRAL_{selection_type}_SIZE", size)
    
    nav_id = get_inventory_value(ORIGIN_ID, f"ADMIRAL_{selection_type}_SELECT_ID", None)
    if nav_id:
        sim.delete_navpoint_by_id(nav_id)

    nav_id = sim.add_navarea(x-size, y-size,x+size, y-size,x-size, y+size,x+size, y+size, text, color)
    nav = sim.get_navpoint_by_id(nav_id)

    nav.visibleToShip = ORIGIN_ID
    set_inventory_value(ORIGIN_ID, f"ADMIRAL_{selection_type}_SELECT_ID", nav_id)

