from sbs_utils.procedural.inventory import  get_inventory_value, set_inventory_value
from sbs_utils.helpers import FrameContext


def admiral_show_nav_area(ORIGIN_ID, pos, size_delta):
    x = pos.x
    y = pos.z

    sim = FrameContext.context.sim

    size = get_inventory_value(ORIGIN_ID, "ADMIRAL_SIZE", 5000)
    size += size_delta
    size = max(min(50000, size), 2000)

    set_inventory_value(ORIGIN_ID, "ADMIRAL_SIZE", size)
    
    nav_name = "admiral"
    nav_id = get_inventory_value(ORIGIN_ID, "ADMIRAL_SELECT_ID", None)
    if nav_id:
        sim.delete_navpoint_by_id(nav_id)

    nav_id = sim.add_navarea(x-size, y-size,x+size, y-size,x-size, y+size,x+size, y+size, nav_name, "#444")
    nav = sim.get_navpoint_by_id(nav_id)

    nav.visibleToShip = ORIGIN_ID
    set_inventory_value(ORIGIN_ID, "ADMIRAL_SELECT_ID", nav_id)


