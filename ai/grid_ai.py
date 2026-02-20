from sbs_utils.procedural.grid import grid_detailed_status, grid_short_status
from sbs_utils.procedural.links import linked_to
from sbs_utils.procedural.query import to_id, to_object, to_blob, to_grid_object
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.roles import has_role, role
from sbs_utils.procedural.timers import is_timer_set, set_timer, is_timer_finished, clear_timer, format_time_remaining, get_time_remaining
from sbs_utils.procedural.comms import comms_broadcast
from sbs_utils.procedural.internal_damage import grid_get_max_hp
import random
import sbs

def grid_calc_speed(id_or_obj):
    _go_id = to_id(id_or_obj)
    _go = to_object(_go_id)
    if _go is None:
        return 0.01
    
    hp = get_inventory_value(_go_id, "HP", grid_get_max_hp())
    red_alert = get_inventory_value(_go.host_id, "red_alert", False)
    red_alert_coeff = 1.0 if not red_alert else 0.75

    speed = hp*0.002
    ripped_speed_coeff = get_inventory_value(_go_id, "ripped_speed_coeff", 1.0)
    rested_speed_coeff = get_inventory_value(_go_id, "rested_speed_coeff", 1.0)
    fed_speed_coeff = get_inventory_value(_go_id, "fed_speed_coeff", 1.0)
    work_speed_coeff = get_inventory_value(_go_id, "work_speed_coeff", 1.0)



    return speed * ripped_speed_coeff * rested_speed_coeff * fed_speed_coeff * work_speed_coeff * red_alert_coeff



def grid_damcons_detailed_status(id_or_obj, short_status=None, short_color=None, seconds=None):
    _go_id = to_id(id_or_obj)

    if short_color == None: short_color = get_inventory_value(_go_id, "last_status_color", "idle")
    if short_status is not None and seconds is not None: 
        grid_short_status(_go_id, short_status, short_color, seconds)
        set_inventory_value(_go_id, "last_status", short_status)
        set_inventory_value(_go_id, "last_status_color", short_color)

    short_status = get_inventory_value(_go_id, "last_status", "idle")

    work = linked_to(_go_id, "work-order")
    color = get_inventory_value(_go_id, "color", "white")
    work_count = len(work)
    hp = get_inventory_value(_go_id, "HP", 1)

    rested = "tired"
    if not is_timer_finished(_go_id, "rested_speed_coeff"):
        left = format_time_remaining(_go_id, "rested_speed_coeff")
        rested = f"rested for {left}"
    
    food = "hungry"
    if not is_timer_finished(_go_id, "fed_speed_coeff"):
        left = format_time_remaining(_go_id, "fed_speed_coeff")
        food = f"fed for {left}"

    fit = "weak"
    if not is_timer_finished(_go_id, "ripped_speed_coeff"):
        left = format_time_remaining(_go_id, "ripped_speed_coeff")
        fit = f"fit for {left}"

    if hp < 6:
        hp = f"{hp} HP visit sickbay"
    else:
        hp = f"{hp} HP"
        
    health_status = f"{hp}^{rested}^{food}^{fit}"
    work_item_status = f"{work_count} assign work"

    boost_time = get_time_remaining(_go_id, "idle_boost_timer")
    boost = "for boost idle in gym,mess, or quarters"
    if boost_time > 0:
        boost_time = format_time_remaining(_go_id, "idle_boost_timer")
        boost = f"boost in {boost_time}"

        
    # a = get_inventory_value(_go_id, "idle", 1.0)
    # b = get_inventory_value(_go_id, "idle_state", 1.0)
    # c = get_inventory_value(_go_id, "target_room", 1.0)
    # debug = f"{a}^{b}^{c}"

    detailed_status = f"{short_status}^{work_item_status}^{health_status}^{boost}"
    grid_detailed_status(_go_id, detailed_status, color)


def grid_damcons_handle_idling_boost(id_or_obj, room_id):
    _go_id = to_id(id_or_obj)
    obj = to_object(id_or_obj)
    if _go_id == room_id:
        return
    
    #
    # See if this needs to run
    #
    if has_role(room_id, "sickbay"):
        hp = get_inventory_value(_go_id, "HP", 0)
        if hp >= grid_get_max_hp(): return
    elif has_role(room_id, "gym"):
        ripped_speed_coeff = get_inventory_value(_go_id, "ripped_speed_coeff", 1.0)
        if ripped_speed_coeff != 1.0: return
    elif has_role(room_id, "quarters"):
        rested_speed_coeff = get_inventory_value(_go_id, "rested_speed_coeff", 1.0)
        if rested_speed_coeff != 1.0: return
    elif has_role(room_id, "mess"):
        fed_speed_coeff = get_inventory_value(_go_id, "fed_speed_coeff", 1.0)
        if fed_speed_coeff != 1.0: return
    else:
        return


    if not is_timer_set(_go_id, "idle_boost_timer"):
        set_timer(_go_id, "idle_boost_timer", minutes=1)
    

    if not is_timer_finished(_go_id, "idle_boost_timer"): return
    #
    # OK - waited long enough
    #
    clear_timer(_go_id, "idle_boost_timer")
    if has_role(room_id, "sickbay"):
        hp += 1
        ship = obj.host_id # obj defined in previous labels
        hp %= (grid_get_max_hp()+1)
        set_inventory_value(_go_id, "HP", hp)
        if hp < grid_get_max_hp():
            comms_broadcast(ship, f"{obj.name} recovering {hp}", "blue")
            set_timer(_go_id, "idle_boost_timer", minutes=2)
        else:
            color = get_inventory_value(_go_id, "color", "purple")
            go_blob = to_blob(_go_id)
            if go_blob is not None:
                go_blob.set("icon_color", color)
            comms_broadcast(ship, f"{obj.name} fully recovered", "green")
    elif has_role(room_id, "gym"):
        set_inventory_value(_go_id, "ripped_speed_coeff", 1.25)
        grid_short_status(_go_id, "Whoo good workout.", "blue", seconds=3)
        set_timer(_go_id, "ripped_speed_coeff", minutes=random.randint(10,16))
    elif has_role(room_id, "quarters"):
        grid_short_status(_go_id, "I feel rested.", "blue", seconds=3)
        set_inventory_value(_go_id, "rested_speed_coeff", 1.25)
        set_timer(_go_id, "rested_speed_coeff", minutes=random.randint(10,16))
    elif has_role(room_id, "mess"):
        grid_short_status(_go_id, "I ate good.", "blue", seconds=3)
        set_inventory_value(_go_id, "fed_speed_coeff", 1.25)
        set_timer(_go_id, "fed_speed_coeff", minutes=random.randint(10,16))



def grid_damcons_handle_idling_boost_finish(id_or_obj):
    BRAIN_AGENT = to_grid_object(id_or_obj)

    hm = sbs.get_hull_map(BRAIN_AGENT.host_id)
    if hm is None:
        return
    # 
    x = BRAIN_AGENT.data_set.get("curx",0)
    y = BRAIN_AGENT.data_set.get("cury",0)
    current_room_ids = set(hm.get_objects_at_point(x,y))
    _go_id = BRAIN_AGENT.id
    
    hp = get_inventory_value(_go_id, "HP", 0)
    if len(current_room_ids & role("sickbay")) > 0:
        hp += 1
        ship = BRAIN_AGENT.host_id # obj defined in previous labels
        hp %= (grid_get_max_hp()+1)
        set_inventory_value(_go_id, "HP", hp)
        if hp < grid_get_max_hp():
            comms_broadcast(ship, f"{BRAIN_AGENT.name} recovering {hp}", "blue")
            set_timer(_go_id, "idle_boost_timer", minutes=2)
        else:
            color = get_inventory_value(_go_id, "color", "purple")
            go_blob = to_blob(_go_id)
            if go_blob is not None:
                go_blob.set("icon_color", color)
            comms_broadcast(ship, f"{BRAIN_AGENT.name} fully recovered", "green")
    elif len(current_room_ids & role("gym")) > 0:
        grid_short_status(_go_id, "Whoo good workout.", "blue", seconds=3)
        set_timer(_go_id, "ripped_speed_coeff", minutes=random.randint(10,16))
        set_inventory_value(_go_id, "ripped_speed_coeff", 1.25)
    elif len(current_room_ids & role("quarters")) > 0:
        grid_short_status(_go_id, "I feel rested.", "blue", seconds=3)
        set_inventory_value(_go_id, "rested_speed_coeff", 1.25)
        set_timer(_go_id, "rested_speed_coeff", minutes=random.randint(10,16))
    elif len(current_room_ids & role("mess")) > 0:
        grid_short_status(_go_id, "I ate good.", "blue", seconds=3)
        set_inventory_value(_go_id, "fed_speed_coeff", 1.25)
        set_timer(_go_id, "fed_speed_coeff", minutes=random.randint(10,16))
