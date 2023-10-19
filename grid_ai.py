from sbs_utils.procedural.grid import grid_detailed_status, grid_short_status
from sbs_utils.procedural.links import linked_to
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.inventory import get_inventory_value


def grid_damcons_detailed_status(id_or_obj, short_status, short_color, seconds):
    _go_id = to_id(id_or_obj)

    grid_short_status(_go_id, short_status, short_color, seconds)

    work = linked_to(_go_id, "work-order")
    color = get_inventory_value(_go_id, "color", "white")
    work_count = len(work)
    work_item_status = f"{work_count} assign work"

    detailed_status = f"{short_status}^{work_item_status}"
    grid_detailed_status(_go_id, detailed_status, color)
