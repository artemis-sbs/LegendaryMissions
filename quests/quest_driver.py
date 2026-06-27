"""Quest driver: advance active quests from existing game signals and apply
rewards. Declarative triggers live in each quest's AMD `--- yaml ---` data
section (on_kill / on_collect / ...); complex quests can instead carry a MAST
`label` for bespoke logic. Runs server-side (called from signal routes).

Note: the quest API's quest_set_state/activate/complete only *emit* signals -
they don't write state. This driver writes state directly (idempotently) so
progress is immediate and never double-counts, and also handles the API's
quest_activated/quest_completed signals so manual activation still updates state.
"""
from sbs_utils.procedural.quest import (
    quest_agent_quests, quest_get_state, quest_get_data,
    quest_get_key, quest_set_key, quest_get_display_name, quest_add, QuestState)
from sbs_utils.procedural.roles import has_role, role
from sbs_utils.procedural.query import to_object, to_object_list, to_id
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.sides import to_side_id
from sbs_utils.procedural.comms import comms_broadcast
from sbs_utils.procedural.gui import gui_row, gui_text
from sbs_utils.mast.mast_node import MastDataObject


def quest_grant_reward(agent_id, reward):
    """Grant a quest reward: credits to the agent's side, items to the agent."""
    if not isinstance(reward, dict):
        return
    credits = reward.get("credits", 0)
    if credits:
        ship = to_object(agent_id)
        side = ship.side if ship is not None else None
        if side:
            sid = to_side_id(side)
            set_inventory_value(sid, "credits", get_inventory_value(sid, "credits", 0) + credits)
    for k, n in (reward.get("items") or {}).items():
        set_inventory_value(agent_id, k, get_inventory_value(agent_id, k, 0) + n)


def quest_mark_active(agent_id, quest_id):
    """Set a quest ACTIVE (idempotent)."""
    if quest_get_state(agent_id, quest_id) == QuestState.ACTIVE:
        return
    quest_set_key(agent_id, quest_id, "state", QuestState.ACTIVE)


def quest_mark_complete(agent_id, quest_id):
    """Complete a quest (idempotent): set state, grant reward, announce."""
    if quest_get_state(agent_id, quest_id) == QuestState.COMPLETE:
        return
    quest_set_key(agent_id, quest_id, "state", QuestState.COMPLETE)
    data = quest_get_data(agent_id, quest_id) or {}
    quest_grant_reward(agent_id, data.get("reward"))
    name = quest_get_display_name(agent_id, quest_id) or quest_id
    comms_broadcast(agent_id, "Mission complete: " + str(name), "#0f0")


def _active_quests(agent_id):
    """(quest_id, data) for each ACTIVE quest on the agent."""
    tree = quest_agent_quests(agent_id)
    if tree is None:
        return []
    out = []
    for qid in tree.get("children", {}):
        if quest_get_state(agent_id, qid) == QuestState.ACTIVE:
            out.append((qid, quest_get_data(agent_id, qid) or {}))
    return out


def _advance_count(agent_id, qid, data, need):
    prog = (quest_get_key(agent_id, qid, "progress", 0) or 0) + 1
    quest_set_key(agent_id, qid, "progress", prog)
    if prog >= need:
        quest_mark_complete(agent_id, qid)


def quest_on_kill(killer_id, destroyed_id):
    """Advance the killer's on_kill quests when an object is destroyed."""
    if killer_id is None:
        return
    for qid, data in _active_quests(killer_id):
        trig = data.get("on_kill")
        if not isinstance(trig, dict):
            continue
        role = trig.get("role")
        if role and not has_role(destroyed_id, role):
            continue
        _advance_count(killer_id, qid, data, trig.get("count", 1))


def quest_on_arrive(i, j):
    """Complete on_reach(sector) quests for every player arriving at (i,j).

    Reaching a place is a single event (not a count), so it completes the
    objective. Used by the Open Universe (signal universe_arrived).
    """
    target = [int(i), int(j)]
    for ship in to_object_list(role("__player__")):
        for qid, data in _active_quests(ship.id):
            trig = data.get("on_reach")
            if isinstance(trig, dict) and list(trig.get("sector") or []) == target:
                quest_mark_complete(ship.id, qid)


def quest_on_collect(holder_id, key):
    """Advance the holder's on_collect quests when an item is collected."""
    if holder_id is None:
        return
    for qid, data in _active_quests(holder_id):
        trig = data.get("on_collect")
        if not isinstance(trig, dict):
            continue
        if trig.get("key") and trig.get("key") != key:
            continue
        _advance_count(holder_id, qid, data, trig.get("count", 1))


# --- Hangar quest board ------------------------------------------------------
def hangar_quests_for(doc, cockpit_type):
    """Quest nodes from the parsed AMD doc whose cockpit matches (or 'any').

    AMD nodes are plain dicts with list "children" and a "key" id; the
    "--- yaml ---" section is parsed into "data".
    """
    if doc is None:
        return []
    out = []
    for n in doc.get("children", []):
        ck = (n.get("data") or {}).get("cockpit", "any")
        if ck == cockpit_type or ck == "any":
            out.append(n)
    return out


def hangar_assign_quest(cockpit_id, doc, cockpit_type, quest_id):
    """Add+activate the chosen sortie quest on the cockpit. Returns the node."""
    for n in hangar_quests_for(doc, cockpit_type):
        if n.get("key") == quest_id:
            quest_add(cockpit_id, n.get("key"), n.get("display_text"),
                      n.get("description", ""), data=n.get("data"))
            quest_mark_active(cockpit_id, n.get("key"))
            return n
    return None


def hangar_cockpit_type(ride):
    """Cockpit class for board filtering: 'shuttle' if the craft has that role,
    else 'fighter'. None ride -> 'fighter'."""
    rid = to_id(ride)
    if rid is not None and has_role(rid, "shuttle"):
        return "shuttle"
    return "fighter"


def hangar_quest_items(doc, cockpit_type):
    """Selectable list-box items (MastDataObject) for the cockpit's sorties."""
    items = []
    for n in hangar_quests_for(doc, cockpit_type):
        items.append(MastDataObject({
            "key": n.get("key"),
            "title": n.get("display_text"),
            "objective": (n.get("data") or {}).get("objective", ""),
            "desc": (n.get("description") or "").strip(),
        }))
    return items


def hangar_quest_template(item):
    """List-box row renderer for a sortie quest."""
    gui_row("row-height: 1.2em;padding:13px;")
    gui_text(f"$text:{item.title};justify: left;")
    obj = item.get("objective", "")
    if obj:
        gui_row("row-height: 1.1em;padding:13px;")
        gui_text(f"$text:{obj};justify: left;font:gui-1")


def hangar_quest_title_template():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text("$text:Sortie Orders;justify: left;")
