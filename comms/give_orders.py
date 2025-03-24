from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.query import to_object, get_comms_selection
from sbs_utils.procedural.roles import has_roles

from sbs_utils.vec import Vec3
import sbs


#
# NOTE: These all could be moved to the sbs_utils library
#

def comms_set_2dview_focus(client_id, focus_id=0, EVENT=None):
    if focus_id is None:
        return
    
    follow = get_inventory_value(client_id, "2d_follow")
    on_ship =  sbs.get_ship_of_client(client_id)
    set_inventory_value(client_id, "2dview_alt_ship", focus_id)
    set_inventory_value(on_ship, "2dview_alt_ship", focus_id)
    
    set_id = focus_id
    if not follow:
        set_id = 0

    previous = get_inventory_value(client_id, "2dview_alt_ship_prev", 0)
    if previous != set_id:
        sbs.assign_client_to_alt_ship(client_id, set_id)
        set_inventory_value(client_id, "2dview_alt_ship_prev", set_id)
    

    ###### UPDATE NAVAREAS
    on_ship =  sbs.get_ship_of_client(client_id)
    alt_ship = focus_id
    sim = FrameContext.context.sim
    if alt_ship == 0:
        del_ships = [on_ship]
    else:
        del_ships = [alt_ship, on_ship]

    ## Remember selection defaults
    selected_id = get_comms_selection(on_ship)
    selected_id = get_inventory_value(alt_ship, "ORDERS_SELECTED_OBJECT", None )
    source_point = get_inventory_value(alt_ship, "ORDERS_SELECTED_POINT", None)
    if EVENT is not None:
        selected_id = EVENT.selected_id
        source_point = Vec3(EVENT.source_point)
    
    #
    # Delete the Nav areas here
    #  Then create then if needed
    for this_ship in del_ships:
        set_inventory_value(this_ship, "ORDERS_SELECTED_POINT", None)
        set_inventory_value(this_ship, "ORDERS_SELECTED_OBJECT", None)
        nav_id = get_inventory_value(this_ship, "ORDERS_SELECTED_NAV", None)
        if nav_id is not None:
            sim.delete_navpoint_by_id(nav_id)

    
    if alt_ship == 0:
        return
    alt_ship_obj = to_object(alt_ship)
    if alt_ship_obj is None:
        return
    if not has_roles(alt_ship, "tsn, defender"):
        return
    
    
    # Now the event is important 
    nav_color = "#444"
    if selected_id != 0 and selected_id is not None:
        _sel_ship = to_object(selected_id)
        if _sel_ship is None:
            return
        
        pos = source_point
        set_inventory_value(alt_ship, "ORDERS_SELECTED_POINT", None)
        #set_inventory_value(alt_ship, "ORDERS_SELECTED_ID", EVENT.selected_id)
        pos = Vec3(_sel_ship.pos)
        set_inventory_value(alt_ship, "ORDERS_SELECTED_POINT", pos)
        set_inventory_value(alt_ship, "ORDERS_SELECTED_OBJECT", selected_id)
        # Need to update
        set_inventory_value(on_ship, "ORDERS_SELECTED_OBJECT", selected_id)
    

        size = 1000
        nav_color = "#044"
        nav_name = f"^^^^^^Order Object^for {alt_ship_obj.name}"
    
        x = pos.x
        y = pos.y
        z = pos.z

    elif source_point is not None:
        set_inventory_value(alt_ship, "ORDERS_SELECTED_POINT", Vec3(source_point))
        set_inventory_value(alt_ship, "ORDERS_SELECTED_OBJECT", None)
        x = source_point.x
        # Same plan as ship
        y = alt_ship_obj.pos.y # EVENT.source_point.y
        z = source_point.z
        size = 400
        nav_color = "#00a"
        nav_name = f"^^^Order Waypoint^for {alt_ship_obj.name}"
    else:
        return
    
    # Create/update nav point
    # On both the alt_ship and on_ship
    for this_ship in [alt_ship, on_ship]:
        y = z
        nav_id = sim.add_navarea(x-size, y-size,x+size, y-size,x-size, y+size,x+size, y+size, nav_name, nav_color)
        #nav_id = sim.add_navpoint(x, y, z, nav_name, "#eee")
        nav = sim.get_navpoint_by_id(nav_id)
        nav.visibleToShip = this_ship
        set_inventory_value(this_ship, "ORDERS_SELECTED_NAV", nav_id)



def science_set_2dview_focus(client_id, focus_id=0):
    if focus_id is None:
        return
    
    follow = get_inventory_value(client_id, "2d_follow")
    on_ship =  sbs.get_ship_of_client(client_id)
    set_inventory_value(client_id, "science_2dview_alt_ship", focus_id)
    set_inventory_value(on_ship, "science_2dview_alt_ship", focus_id)
    set_id = focus_id
    if not follow:
        set_id = 0

    previous = get_inventory_value(client_id, "science_2dview_alt_ship_prev", 0)
    if previous != set_id:
        sbs.assign_client_to_alt_ship(client_id, set_id)
        set_inventory_value(client_id, "science_2dview_alt_ship_prev", set_id)

    