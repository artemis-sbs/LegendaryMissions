from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.comms import comms_navigate
import sbs


#
# NOTE: These all could be moved to the sbs_utils library
#

def comms_set_2dview_focus(client_id, focus_id=0):
    if focus_id is None:
        return
    follow = get_inventory_value(client_id, "2d_follow")
    set_inventory_value(client_id, "2dview_alt_ship", focus_id)
    if not follow:
        focus_id = 0
    sbs.assign_client_to_alt_ship(client_id, focus_id)

    #comms_navigate("comms")
