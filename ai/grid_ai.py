from sbs_utils.procedural.grid import grid_detailed_status, grid_short_status
from sbs_utils.procedural.links import linked_to
from sbs_utils.procedural.query import to_id, to_object, to_blob, to_grid_object
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.roles import has_role, role
from sbs_utils.procedural.timers import is_timer_set, set_timer, is_timer_finished, clear_timer, format_time_remaining, get_time_remaining
from sbs_utils.procedural.comms import comms_broadcast
from sbs_utils.procedural.internal_damage import grid_get_max_hp, grid_node_state
from sbs_utils.procedural.grid import grid_objects
from sbs_utils.procedural.work_orders import (work_orders_for, work_order_kind,
                                             work_order_priority, work_order_workers,
                                             KIND_REPAIR, PRIORITY_LOW, PRIORITY_NORMAL,
                                             PRIORITY_HIGH, PRIORITY_CRITICAL)
from sbs_utils.procedural.query import to_object_list
from sbs_utils.agent import Agent
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




def grid_damcons_detailed_status_update(id_or_obj, short_status=None, short_color=None, seconds=None):
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
    if hp < 6:
        hp = f"{hp} HP visit sickbay"
    else:
        hp = f"{hp} HP"
        
    health_status = f"{hp}"

    # This should be less Hard coded
    speed_modifiers = get_inventory_value(_go_id, f"speed_modifiers", {})
    new_speed_modifiers = {}
    for k,speed_up in speed_modifiers.items():
        #print(f"{k}")
        if speed_up is not None and not speed_up.expired():
            left = speed_up.format_time_remaining()
            status = f"{k} for {left}"
            health_status += "^" + status
            new_speed_modifiers[k]=speed_up
    set_inventory_value(_go_id, f"speed_modifiers", new_speed_modifiers)
    
    work_item_status = f"{work_count} work items"

    boost_time = get_time_remaining(_go_id, "idle_boost_timer")
    boost = "for boost idle in gym,mess, or quarters"
    if boost_time > 0:
        boost_time = format_time_remaining(_go_id, "idle_boost_timer")
        boost = f"boost in {boost_time}"

        
    detailed_status = f"{short_status}^{work_item_status}^{health_status}^{boost}"
    grid_detailed_status(_go_id, detailed_status, color)


# --- the Selected tab's body -------------------------------------------------
# Engineering's grid_face used to be an engine widget fed one `^`-separated string
# on the node's `info_text` blob key (grid_damcons_detailed_status_update, above).
# The console owns that rectangle now, so the long form is authored markdown in a
# text area that wraps and scrolls, and `info_text` goes on serving the grid item
# list's tooltip unchanged.

# Characters gui_text_area's mini-markdown consumes. A node NAME is engine-supplied
# (it is "roomname:x,y") and a damcon name is mission-supplied, so neither can be
# trusted to be free of them: '[' makes the line a link reference and REPLACES it,
# '^' is the newline escape, a backtick ends the $text: quoting on the send path,
# and a leading '-' or '#' turns the line into a bullet or a heading.
_MD_STRIP = "[]^`"


def _md_safe(text):
    """Make an engine- or mission-supplied string safe to drop into markdown.

    Args:
        text: anything; None becomes "".

    Returns:
        str: ASCII-safe, with the markdown-significant characters removed and any
        leading list/heading marker defused.
    """
    if text is None:
        return ""
    out = "".join(c for c in str(text) if c not in _MD_STRIP)
    out = out.replace("{", "(").replace("}", ")")
    return out.lstrip("-#> \t")


_PRIORITY_WORDS = ((PRIORITY_CRITICAL, "critical"), (PRIORITY_HIGH, "high"),
                   (PRIORITY_NORMAL, "normal"), (PRIORITY_LOW, "low"))


def _order_words(node_id):
    """An order as "repair - high".

    The nearest rung's NAME, not the number: a number would make the engineer do
    arithmetic to compare two jobs, and going by nearest means a mission's own
    custom priority still reads as something.
    """
    kind = work_order_kind(node_id) or KIND_REPAIR
    verb = "repair" if kind == KIND_REPAIR else "tune"
    word = min(_PRIORITY_WORDS,
               key=lambda p: abs(p[0] - work_order_priority(node_id)))[1]
    return f"{verb} - {word}"


def _grid_node_condition_line(node_id):
    """One bullet describing the node's condition, or None for a plain nominal one."""
    state = grid_node_state(node_id)
    if state == "damaged":
        return "DAMAGED"
    if state == "worn":
        return "Worn - needs maintenance"
    if state == "tuned":
        return "Tuned"
    return None


def _grid_node_roles(node_id):
    """The node's own roles, minus the bookkeeping ones, as display text."""
    agent = Agent.get(node_id)
    if agent is None:
        return ""
    # get_roles(), not `.roles` - that is the class-level Stuff registry keyed by
    # role name, not this agent's own list, and iterating it is a TypeError. It
    # would have surfaced as a silently BLANK panel tab, never as an error.
    # Not just the `__` bookkeeping roles. `#` (the "no default roles" marker) leaves
    # an EMPTY entry, which rendered as a leading comma, and `gridobject` is on every
    # node so it says nothing about this one. Both were noise in a line that exists
    # to answer "what is this room FOR".
    hidden = ("", "#", "gridobject", "room")
    names = sorted(r for r in agent.get_roles()
                   if r and r not in hidden and not r.startswith("__"))
    return ", ".join(names)


# The four tier colors, plus the two neutrals the panel uses for text that is not
# reporting a condition. Same values the glyph row and the grid draw with, so a line
# and the node it describes can never disagree.
_MD_OK = "springgreen"
_MD_TUNED = "#40E0E0"
_MD_WORN = "Gold"
_MD_BAD = "Crimson"
_MD_TEXT = "#E6E6F0"
_MD_DIM = "#8B85A8"


def _md_line(text, color=_MD_TEXT):
    """One colored bullet.

    `$$<style>; <text>` sets a one-off style and BYPASSES the markdown pass, which is
    why the dash is literal here - a real `-` bullet is restyled by the built-in `ul`
    style and comes back the same color as every other line, which is the whole thing
    this is fixing.
    """
    return f"$$color:{color};font:gui-2;  - {text}"


def _md_state_color(node_id):
    """The tier color for a node, for a line that is reporting its condition."""
    state = grid_node_state(node_id)
    if state == "damaged":
        return _MD_BAD
    if state == "worn":
        return _MD_WORN
    if state == "tuned":
        return _MD_TUNED
    return _MD_OK


# What a team standing still is actually waiting to DO. ai_idle_at_room parks a
# damcon on a room and fires the room's upgrade once its timer elapses, so "idle" and
# "part way through a job" look identical from outside - which is exactly how a tune
# in progress reads as a team ignoring its orders.
_WORK_WORDS = {"ai_tune_node": "tuning", "ai_fix_damage": "repairing"}


def _pending_work_word(node_id):
    """The verb for whatever this team is parked to do, or None if just resting."""
    room_data = get_inventory_value(node_id, "idle_room_data", None) or {}
    upgrade = room_data.get("upgrade")
    # An upgrade entry is a bare label name or a dict carrying one.
    if isinstance(upgrade, dict):
        upgrade = upgrade.get("label")
    return _WORK_WORDS.get(str(upgrade))


def grid_selected_markdown(ship_id, node_id):
    """The Engineering panel's Selected tab, as gui_text_area markdown.

    Authored markdown, not prose that got lucky - every dynamic value goes through
    `_md_safe` first. ASCII only: this reaches an engine-rendered surface.

    Args:
        ship_id: the ship the node belongs to.
        node_id: the selected grid node, or None/0 when nothing is selected.

    Returns:
        str: markdown for gui_text_area, or an empty-state line.
    """
    node = to_object(node_id) if node_id else None
    if node is None:
        return "$text:(nothing selected);color:#888;"

    lines = [f"## {_md_safe(node.name)}"]

    if has_role(node_id, "damcons"):
        lines.append(_md_line(_md_safe(get_inventory_value(node_id, 'last_status', 'idle'))))

        max_hp = grid_get_max_hp()
        hp = get_inventory_value(node_id, "HP", max_hp)
        # Green at full, gold once it slips, crimson when the team is nearly out -
        # the same reading as a system pool, so one glance covers crew and hull.
        if hp >= max_hp:
            hp_color = _MD_OK
        elif hp * 2 > max_hp:
            hp_color = _MD_WORN
        else:
            hp_color = _MD_BAD
        hp_text = f"HP {hp} of {max_hp}"
        if hp < max_hp:
            hp_text += " - visit sickbay"
        lines.append(_md_line(hp_text, hp_color))

        # Live speed boosts, same source the tooltip reads. Expired ones are dropped
        # by grid_damcons_detailed_status_update, which runs every tick on the brain;
        # this only READS, so a stale entry is skipped rather than pruned here.
        for name, mod in (get_inventory_value(node_id, "speed_modifiers", {}) or {}).items():
            if mod is not None and not mod.expired():
                lines.append(_md_line(f"{_md_safe(name)} for {mod.format_time_remaining()}",
                                      _MD_TUNED))

        # A team parked on a job counts down the SAME timer as one parked in the gym,
        # so saying "boost" for both is what made a tune in progress read as a team
        # sitting on its hands. Name the job when there is one.
        boost_time = get_time_remaining(node_id, "idle_boost_timer")
        work_word = _pending_work_word(node_id)
        if boost_time > 0 and work_word:
            lines.append(_md_line(f"{work_word} - {format_time_remaining(node_id, 'idle_boost_timer')} to go",
                                  _MD_WORN))
        elif boost_time > 0:
            lines.append(_md_line(f"boost in {format_time_remaining(node_id, 'idle_boost_timer')}",
                                  _MD_TUNED))
        elif work_word:
            lines.append(_md_line(f"{work_word} here", _MD_WORN))
        else:
            lines.append(_md_line("idle in gym, mess or quarters to boost", _MD_DIM))

        # work_orders_for, not linked_to: it drops orders whose node was deleted,
        # repaired by somebody else, or replaced by a grid rebuild. The count on this
        # panel used to include every one of those, forever.
        orders = to_object_list(work_orders_for(node_id))
        lines.append("")
        lines.append(f"## Orders {len(orders)}")
        if not orders:
            lines.append(_md_line("none assigned", _MD_DIM))
        for target in sorted(orders, key=lambda t: -work_order_priority(t.id)):
            lines.append(_md_line(f"{_md_safe(target.name)} - {_order_words(target.id)}",
                                  _md_state_color(target.id)))
        return "\n".join(lines)

    # A room, a system node, or anything else selectable on the interior view.
    condition = _grid_node_condition_line(node_id)
    lines.append(_md_line(condition or "Nominal", _md_state_color(node_id)))

    roles = _grid_node_roles(node_id)
    if roles:
        lines.append(_md_line(_md_safe(roles), _MD_DIM))

    workers = to_object_list(work_order_workers(node_id))
    if workers:
        names = ", ".join(_md_safe(w.name) for w in sorted(workers, key=lambda d: d.name))
        lines.append(_md_line(_order_words(node_id), _md_state_color(node_id)))
        lines.append(_md_line(f"assigned {names}"))
    elif condition:
        lines.append(_md_line("no team assigned", _MD_DIM))
    return "\n".join(lines)
