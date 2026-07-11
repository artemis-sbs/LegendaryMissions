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
    quest_agent_quests, quest_get, quest_get_state, quest_get_data,
    quest_get_key, quest_set_key, quest_get_display_name, quest_add, QuestState,
    quest_log_build_items)
from sbs_utils.procedural.roles import has_role, role
from sbs_utils.procedural.query import to_object, to_object_list, to_id, is_space_object_id
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.sides import to_side_id
from sbs_utils.procedural.timers import set_timer, is_timer_set, is_timer_finished
from sbs_utils.procedural.comms import comms_broadcast
from sbs_utils.procedural.signal import signal_emit
from sbs_utils.procedural.gui import gui_row, gui_text, gui_icon, gui_list_box_header, gui_list_box_is_header
from sbs_utils.mast.mast_node import MastDataObject
from sbs_utils.agent import Agent


def _quest_audience(agent_id):
    """Who should see a quest's complete/fail line. A per-ship quest is owned by a
    real space object -> tell that ship. A shared-scope quest is owned by the
    non-space SHARED story agent (Agent.SHARED_ID), which is NOT a player ship, so
    tell every player instead - passing SHARED to send_message_to_player_ship
    raises "invalid space object"."""
    if is_space_object_id(agent_id):
        return agent_id
    return role("__player__")


def quest_grant_reward(agent_id, reward):
    """Grant a quest reward: credits to the agent's side, items to the agent."""
    if not isinstance(reward, dict):
        return
    credits = reward.get("credits", 0)
    if credits:
        ship = to_object(agent_id)
        side = getattr(ship, "side", None)   # SHARED / console agents have no .side
        if side:
            sid = to_side_id(side)
            set_inventory_value(sid, "credits", get_inventory_value(sid, "credits", 0) + credits)
    for k, n in (reward.get("items") or {}).items():
        set_inventory_value(agent_id, k, get_inventory_value(agent_id, k, 0) + n)


def quest_grant_penalty(agent_id, penalty):
    """Apply a quest penalty (mirror of quest_grant_reward): deduct credits from
    the agent's side, remove items from the agent. Never goes below zero."""
    if not isinstance(penalty, dict):
        return
    credits = penalty.get("credits", 0)
    if credits:
        ship = to_object(agent_id)
        side = getattr(ship, "side", None)   # SHARED / console agents have no .side
        if side:
            sid = to_side_id(side)
            set_inventory_value(sid, "credits", max(0, get_inventory_value(sid, "credits", 0) - credits))
    for k, n in (penalty.get("items") or {}).items():
        set_inventory_value(agent_id, k, max(0, get_inventory_value(agent_id, k, 0) - n))


def _quest_maybe_end_game(agent_id, quest_id, data, win):
    """Fire game_over once if this quest is a game-ending mission quest.

    A quest with end_win (on COMPLETE) or end_lose (on FAILED) ends the game;
    win_text/lose_text (falling back to the display name) is the end-screen reason.
    Guarding the actual teardown lives in the //signal/game_over route.
    """
    if not data.get("end_win" if win else "end_lose"):
        return
    text = data.get("win_text" if win else "lose_text") or quest_get_display_name(agent_id, quest_id) or quest_id
    signal_emit("game_over", {"WIN": bool(win), "TEXT": str(text),
                              "AGENT_ID": to_id(agent_id), "QUEST_ID": quest_id})


def quest_reeval_mission(agent_id, parent_qid):
    """Re-evaluate a mission (parent) quest from its children's states.

    Any `critical` child FAILED -> the mission FAILS; else once every `required`
    child is COMPLETE the mission COMPLETES. No-op unless the parent is ACTIVE, so
    it settles exactly once. Children link up via their data `parent: <parent_qid>`.
    """
    if not parent_qid or quest_get_state(agent_id, parent_qid) != QuestState.ACTIVE:
        return
    tree = quest_agent_quests(agent_id)
    if tree is None:
        return
    required_done = []
    for qid in tree.get("children", {}):
        d = quest_get_data(agent_id, qid) or {}
        if d.get("parent") != parent_qid:
            continue
        st = quest_get_state(agent_id, qid)
        if d.get("critical") and st == QuestState.FAILED:
            quest_mark_failed(agent_id, parent_qid)
            return
        if d.get("required"):
            required_done.append(st == QuestState.COMPLETE)
    if required_done and all(required_done):
        quest_mark_complete(agent_id, parent_qid)


def _quest_tree_parent(quest_id):
    """The parent path of a nested quest key (`arc/step` -> `arc`); None for a top-level key."""
    return quest_id.rsplit("/", 1)[0] if "/" in quest_id else None


def quest_reeval_tree_parent(agent_id, quest_id):
    """A quest with CHILDREN completes when ALL its children are COMPLETE - the natural
    'the arc is done when its steps are done'. Called when a nested `arc/step` settles: it
    completes the tree parent, which recurses UP via quest_mark_complete. SECRET children
    are unrevealed future steps, so they block completion (the arc isn't finished). Only an
    ACTIVE parent is settled; idempotent (quest_mark_complete no-ops if already complete).

    Author a parent as a pure CONTAINER (no own When trigger) with leaf children as the
    objectives, so its completion is driven only by the children (unambiguous)."""
    parent = _quest_tree_parent(quest_id)
    if parent is None:
        return
    if quest_get_state(agent_id, parent) != QuestState.ACTIVE:
        return
    pnode = quest_get(agent_id, parent)
    kids = (pnode.get("children") if pnode is not None else None) or {}
    if not kids:
        return
    for c in kids.values():
        if int(c.get("state", 0) or 0) != int(QuestState.COMPLETE):
            return  # a child still to do -> parent stays active
    quest_mark_complete(agent_id, parent)


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
    quest_reveal(agent_id, data.get("reveal"))
    # On-complete actions: emit an optional custom signal (e.g. to flip
    # diplomacy), and a generic quest_finished carrying the data so addons can
    # react (the universe applies the declarative rep: block from it).
    sig = data.get("signal")
    if sig:
        signal_emit(sig, {"AGENT_ID": agent_id, "QUEST_ID": quest_id})
    signal_emit("quest_finished", {"AGENT_ID": agent_id, "QUEST_ID": quest_id, "DATA": data})
    name = quest_get_display_name(agent_id, quest_id) or quest_id
    comms_broadcast(_quest_audience(agent_id), "Mission complete: " + str(name), "#0f0")
    # A game-ending mission quest wins the game; then bubble up to a parent mission.
    _quest_maybe_end_game(agent_id, quest_id, data, win=True)
    if data.get("parent"):
        quest_reeval_mission(agent_id, data.get("parent"))
    # A quest with children (a nested-key arc) completes when all its children complete:
    # settle this quest's TREE parent, recursing up.
    quest_reeval_tree_parent(agent_id, quest_id)


_STATE_NAMES = {
    "idle": QuestState.IDLE, "active": QuestState.ACTIVE, "secret": QuestState.SECRET,
    "complete": QuestState.COMPLETE, "failed": QuestState.FAILED,
}


def quest_grant_amd(agent_id, doc, _prefix=""):
    """Grant all quests from a parsed AMD story doc to an agent at once.

    Each heading becomes a quest; its data `state` (active/secret/idle/...) sets
    the starting state, so a multi-step story is granted as parent ACTIVE + later
    steps SECRET, chained by each step's `reveal`. Idempotent per quest id.

    NESTED headings become NESTED quests: a deeper heading (`#### step` under a
    `### arc`) is granted with the '/'-path key `arc/step` (via quest_folder), so
    the arc renders as a collapsible tree in the Quests tab and its steps trigger /
    reveal by their full path. The parent is granted before its children so
    quest_folder can attach them.
    """
    if doc is None:
        return
    for n in doc.get("children", []):
        key = n.get("key")
        if not key:
            continue
        qid = _prefix + key
        data = n.get("data") or {}
        # scope: shared -> grant to the game (SHARED) agent, so the whole crew
        # shares the arc; otherwise to the given agent (ship).
        target = Agent.SHARED_ID if data.get("scope") == "shared" else agent_id
        if quest_get_state(target, qid) == QuestState.IDLE:  # skip already-granted
            st = _STATE_NAMES.get(str(data.get("state", "idle")).lower(), QuestState.IDLE)
            quest_add(target, qid, n.get("display_text"),
                      (n.get("description") or "").strip(), state=st, data=data)
        # Recurse into nested headings, building the child path key `<qid>/<childkey>`.
        if n.get("children"):
            quest_grant_amd(agent_id, n, _prefix=qid + "/")


def quest_reveal(agent_id, reveal):
    """Activate sub-quests revealed on completion (reveal: id, or [ids]).

    The revealed quests must already exist on the agent (added SECRET/IDLE when
    the parent story was granted); this flips them ACTIVE so their triggers go
    live - the next step(s) of a multi-step bridge story.
    """
    if not reveal:
        return
    ids = reveal if isinstance(reveal, list) else [reveal]
    for qid in ids:
        quest_mark_active(agent_id, qid)


def quest_shared_state(quest_id):
    """State of a game-level (SHARED) quest - convenience for narrative arcs."""
    return int(quest_get_state(Agent.SHARED_ID, quest_id) or 0)


def quest_mark_failed(agent_id, quest_id):
    """Fail an active quest (idempotent): set state, apply penalty, announce, then
    fire the lose (if end_lose) and bubble up to the parent mission."""
    if quest_get_state(agent_id, quest_id) != QuestState.ACTIVE:
        return
    quest_set_key(agent_id, quest_id, "state", QuestState.FAILED)
    data = quest_get_data(agent_id, quest_id) or {}
    quest_grant_penalty(agent_id, data.get("penalty"))
    name = quest_get_display_name(agent_id, quest_id) or quest_id
    comms_broadcast(_quest_audience(agent_id), "Mission failed: " + str(name), "#f33")
    _quest_maybe_end_game(agent_id, quest_id, data, win=False)
    if data.get("parent"):
        quest_reeval_mission(agent_id, data.get("parent"))


def _collect_active_quests(children, prefix, out):
    """Recurse the quest tree, appending (full_path, data) for every ACTIVE quest - so
    NESTED arc steps (`arc/step`, authored as nested quest keys) fire their triggers too.
    The path is '/'-separated so quest_get_key / quest_set_key / quest_mark_complete
    navigate it via quest_folder. Flat quests (no children) are unchanged (path == key)."""
    for cid, q in (children or {}).items():
        path = prefix + cid
        if int(q.get("state", 0) or 0) == int(QuestState.ACTIVE):
            out.append((path, q.get("data") or {}))
        sub = q.get("children")
        if sub:
            _collect_active_quests(sub, path + "/", out)


def _active_quests(agent_id):
    """(quest_id, data) for each ACTIVE quest on the agent, INCLUDING nested arc steps
    (quest_id is the full '/'-path). Every on_* trigger handler iterates this."""
    tree = quest_agent_quests(agent_id)
    if tree is None:
        return []
    out = []
    _collect_active_quests(tree.get("children", {}), "", out)
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


def quest_on_kill_shared(destroyed_id):
    """Advance game-level (SHARED) on_kill quests for any kill. Called once per
    kill (separate from per-killer credit) so SHARED counts aren't doubled by the
    source+parent calls."""
    quest_on_kill(Agent.SHARED_ID, destroyed_id)


def quest_on_scan(scanner_id, scanned_id):
    """Advance the scanner's (and game/SHARED) on_scan quests when science scans
    a target. on_scan {role: <role>} (optional) filters by the scanned role."""
    if scanner_id is None:
        return
    for aid in (scanner_id, Agent.SHARED_ID):
        for qid, data in _active_quests(aid):
            trig = data.get("on_scan")
            if not isinstance(trig, dict):
                continue
            want = trig.get("role")
            if want and not has_role(scanned_id, want):
                continue
            _advance_count(aid, qid, data, trig.get("count", 1))


def quest_on_dock(ship_id, station_id):
    """Advance the ship's (and game/SHARED) on_dock quests when it docks a
    station. on_dock {role: <role>} (optional) filters by the station's role."""
    if ship_id is None:
        return
    for aid in (ship_id, Agent.SHARED_ID):
        for qid, data in _active_quests(aid):
            trig = data.get("on_dock")
            if not isinstance(trig, dict):
                continue
            want = trig.get("role")
            if want and not has_role(station_id, want):
                continue
            _advance_count(aid, qid, data, trig.get("count", 1))


def quest_on_signal(name):
    """Generic named trigger for on_signal / on_comms quests (escape hatch).

    A mission/comms route fires signal_emit("quest_signal", {"SIGNAL_NAME": ...});
    this advances any ACTIVE quest (players + SHARED) whose on_signal {name} or
    on_comms {option} matches. Lets authors add beats with no new driver code.
    """
    agents = [Agent.SHARED_ID]
    for s in to_object_list(role("__player__")):
        agents.append(s.id)
    for aid in agents:
        for qid, data in _active_quests(aid):
            trig = data.get("on_signal") or data.get("on_comms")
            if isinstance(trig, dict):
                want = trig.get("name") or trig.get("option")
                if not want or want == name:
                    _advance_count(aid, qid, data, trig.get("count", 1))
            # Fail trigger: a matching signal fails the quest (mirror of on_signal).
            ftrig = data.get("fail_on_signal")
            if isinstance(ftrig, dict):
                fwant = ftrig.get("name") or ftrig.get("option")
                if not fwant or fwant == name:
                    quest_mark_failed(aid, qid)


def quest_fail_on_all_dead(destroyed_id=None):
    """Fail ACTIVE quests whose fail_on_all_dead {role} guard just emptied - the
    last holder of that role has died. Called from the killed route; the victim is
    still registered there, so it is excluded from the remaining count."""
    for aid in [Agent.SHARED_ID] + [s.id for s in to_object_list(role("__player__"))]:
        for qid, data in _active_quests(aid):
            trig = data.get("fail_on_all_dead")
            if not isinstance(trig, dict):
                continue
            want = trig.get("role")
            if not want:
                continue
            count = len(role(want))
            if destroyed_id is not None and has_role(destroyed_id, want):
                count -= 1  # the ship dying right now still holds the role
            if count <= 0:
                quest_mark_failed(aid, qid)


def quest_tick_fail_after():
    """Watcher tick: fail ACTIVE quests whose fail_after deadline elapsed. The
    deadline is anchored lazily (a per-quest timer set on first sight), so
    activation needs no hook - general to any mission, not just siege."""
    for aid in [Agent.SHARED_ID] + [s.id for s in to_object_list(role("__player__"))]:
        for qid, data in _active_quests(aid):
            trig = data.get("fail_after")
            if not isinstance(trig, dict):
                continue
            secs = int(trig.get("seconds", 0) or 0) + int(trig.get("minutes", 0) or 0) * 60
            if secs <= 0:
                continue
            tname = "qfail:" + str(qid)
            if not is_timer_set(aid, tname):
                set_timer(aid, tname, seconds=secs)
            elif is_timer_finished(aid, tname):
                quest_mark_failed(aid, qid)


def quest_on_arrive(i, j):
    """Complete on_reach(sector) quests for every player arriving at (i,j).

    Reaching a place is a single event (not a count), so it completes the
    objective. Used by the Open Universe (signal universe_arrived).
    """
    target = [int(i), int(j)]
    agents = [s.id for s in to_object_list(role("__player__"))]
    agents.append(Agent.SHARED_ID)
    for aid in agents:
        for qid, data in _active_quests(aid):
            trig = data.get("on_reach")
            if isinstance(trig, dict) and list(trig.get("sector") or []) == target:
                quest_mark_complete(aid, qid)


def quest_on_collect(holder_id, key):
    """Advance the holder's (and game/SHARED) on_collect quests on collection."""
    if holder_id is None:
        return
    for aid in (holder_id, Agent.SHARED_ID):
        for qid, data in _active_quests(aid):
            trig = data.get("on_collect")
            if not isinstance(trig, dict):
                continue
            if trig.get("key") and trig.get("key") != key:
                continue
            _advance_count(aid, qid, data, trig.get("count", 1))


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


# --- Quest log tab (accept/abandon) ------------------------------------------
# Rendering is shared with the end-game results Quests tab via sbs_utils
# quest_log_build_items / quest_log_template / quest_log_title, so the look lives
# in ONE place. Only `sources` (whose quests to show) differs between the two logs.
def quest_tab_items(client_id, ship_id):
    """Collapsible quest-log items for THIS console: the game (SHARED), the client,
    and its ship. Rows carry their owning agent (for accept/abandon)."""
    sources = [("Game", Agent.SHARED_ID)]
    if client_id and client_id != 0:
        sources.append(("You", client_id))
    if ship_id and ship_id != 0:
        sources.append(("Ship", ship_id))
    return quest_log_build_items(sources)


def quest_tab_accept(item):
    """Accept an available (IDLE) quest. No-op on a section header."""
    if item is None or gui_list_box_is_header(item):
        return
    if item.get("state") == int(QuestState.IDLE):
        quest_mark_active(item.get("agent_id"), item.get("key"))


def quest_tab_abandon(item):
    """Abandon an active quest (-> FAILED). No-op on a section header."""
    if item is None or gui_list_box_is_header(item):
        return
    if item.get("state") == int(QuestState.ACTIVE):
        quest_set_key(item.get("agent_id"), item.get("key"), "state", QuestState.FAILED)
