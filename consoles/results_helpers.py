import datetime

import sbs
from sbs_utils.procedural.query import to_object, to_space_object, to_space_object_list, to_id
from sbs_utils.procedural.roles import has_role, role
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.ship_data import get_ship_data_for
from sbs_utils.procedural.quest import (
    quest_agent_quests, quest_get_state, quest_get_key, quest_get_display_name, QuestState,
    quest_log_build_items)
from sbs_utils.mast.mast_node import MastDataObject
from sbs_utils.procedural.gui import gui_row, gui_text, gui_icon, gui_list_box_header, gui_list_box_is_header
from sbs_utils.agent import Agent


# "Tonnage" is flavor: a destroyed hull's shipData `hullpoints` (a small 1-8 tier)
# scaled so the end-screen number reads like naval tonnage sunk.
TONNAGE_PER_HULLPOINT = 1000

# Per-agent inventory keys this module writes (kills/tonnage/damage_dealt). sortie /
# completed_objectives / call_sign are written by the hangar; we only read those.
_STAT_KILLS = "kills"
_STAT_TONNAGE = "tonnage"
_STAT_DAMAGE = "damage_dealt"


# --- Kill / damage attribution (called from the damage routes) ---------------
def _attacker_id(parent_id, source_id):
    """The agent that gets the credit: the firing ship (parent) when set, else the
    source. Beams report the ship as the source; projectiles report the ship as the
    parent and the projectile as the source - so prefer parent, fall back to source.
    """
    aid = to_id(parent_id)
    if aid is None or aid == 0:
        aid = to_id(source_id)
    if aid == 0:
        return None
    return aid


def _is_creditable(attacker_id):
    """Only player BRIDGE ships earn credit here. Fighter/shuttle (cockpit) kills are
    credited by the hangar addon instead, so the two never double-count and the
    hangar's Air Wing works in missions that don't load this (consoles) addon."""
    if attacker_id is None or attacker_id == 0:
        return False
    return has_role(attacker_id, "__player__")


def _victim_tonnage(victim):
    """Flavor 'tonnage' for a destroyed object, from its shipData hullpoints."""
    so = to_object(victim)
    if so is None:
        return 0
    sd = get_ship_data_for(so.art_id)
    hp = (sd.get("hullpoints", 0) or 0) if sd is not None else 0
    return int(hp) * TONNAGE_PER_HULLPOINT


def _bump(agent_id, key, amount):
    set_inventory_value(agent_id, key, get_inventory_value(agent_id, key, 0) + amount)


def results_credit_kill(parent_id, source_id, victim_id):
    """Credit one kill + the victim's tonnage to the player bridge ship that landed
    the final blow. (Fighter/shuttle kills are credited by the hangar addon.)"""
    attacker = _attacker_id(parent_id, source_id)
    if not _is_creditable(attacker):
        return
    tons = _victim_tonnage(victim_id)
    _bump(attacker, _STAT_KILLS, 1)
    _bump(attacker, _STAT_TONNAGE, tons)


def results_credit_damage(parent_id, source_id, amount):
    """Accumulate raw damage dealt by a player bridge ship (the option-B 'impact'
    stat). (Cockpit damage is credited by the hangar addon.)"""
    attacker = _attacker_id(parent_id, source_id)
    if not _is_creditable(attacker):
        return
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        return
    if amount <= 0:
        return
    _bump(attacker, _STAT_DAMAGE, amount)


# --- End-screen / save read-outs ---------------------------------------------
def _hull_pct(ship_id):
    """Remaining hull % (0-100) from summed SHPSYS damage vs max; 100 if unknown."""
    so = to_space_object(ship_id)
    if so is None:
        return 0
    blob = so.data_set
    if blob is None:
        return 100
    cur = 0
    mx = 0
    for i in range(4):  # four ship systems; death = all four maxed
        mx += blob.get("system_max_damage", i) or 0
        cur += blob.get("system_damage", i) or 0
    if mx <= 0:
        return 100
    pct = int(round(100 * (1.0 - (float(cur) / float(mx)))))
    return max(0, min(100, pct))


def results_player_ships():
    """Per surviving player bridge ship: name, kills, tonnage, damage, hull %.
    (Destroyed player ships are gone from the role, so they aren't listed.)"""
    ships = []
    for so in to_space_object_list(role("__player__")):
        sid = so.id
        ships.append({
            "name": str(so.name),
            "kills": get_inventory_value(sid, _STAT_KILLS, 0),
            "tonnage": get_inventory_value(sid, _STAT_TONNAGE, 0),
            "damage": int(get_inventory_value(sid, _STAT_DAMAGE, 0)),
            "hull_pct": _hull_pct(sid),
        })
    return ships


def _client_ids():
    try:
        return list(sbs.get_client_ID_list())
    except Exception:
        return []


def results_pilots():
    """Per pilot (client that flew at least one sortie): call sign, sorties, kills,
    tonnage, objectives, damage."""
    pilots = []
    for cid in _client_ids():
        sorties = get_inventory_value(cid, "sortie", 0)
        if not sorties:
            continue
        pilots.append({
            "call_sign": str(get_inventory_value(cid, "call_sign", "pilot")),
            "sorties": sorties,
            "kills": get_inventory_value(cid, _STAT_KILLS, 0),
            "tonnage": get_inventory_value(cid, _STAT_TONNAGE, 0),
            "objectives": get_inventory_value(cid, "completed_objectives", 0),
            "damage": int(get_inventory_value(cid, _STAT_DAMAGE, 0)),
        })
    return pilots


_QUEST_STATE_LABEL = {
    int(QuestState.ACTIVE): "Active", int(QuestState.IDLE): "Available",
    int(QuestState.COMPLETE): "Done", int(QuestState.FAILED): "Failed",
    int(QuestState.POSTING): "Posted",
}


def results_quests():
    """Game (SHARED) + per-ship quests with a display state, for the read-only
    Quests tab and the save. SECRET (undiscovered) quests are hidden."""
    out = []
    sources = [("Game", Agent.SHARED_ID)]
    for so in to_space_object_list(role("__player__")):
        sources.append((str(so.name), so.id))
    for group, aid in sources:
        tree = quest_agent_quests(aid)
        children = tree.get("children") if tree is not None else None
        for qid, q in (children or {}).items():
            st = int(q.get("state", QuestState.IDLE) or 0)
            if st == int(QuestState.SECRET):
                continue
            out.append({
                "group": group,
                "title": str(q.get("display_text", qid)),
                "state": st,
                "state_label": _QUEST_STATE_LABEL.get(st, ""),
                "desc": (q.get("description") or "").strip(),
            })
    return out


def results_summary():
    """Game-wide player totals (no double counting): bridge ships + pilots."""
    kills = 0
    tonnage = 0
    damage = 0
    for s in results_player_ships():
        kills += s["kills"]
        tonnage += s["tonnage"]
        damage += s["damage"]
    for p in results_pilots():
        kills += p["kills"]
        tonnage += p["tonnage"]
        damage += p["damage"]
    return {"kills": kills, "tonnage": tonnage, "damage": damage}


def results_record_extra():
    """The dense per-ship / per-pilot / quest breakdown for the saved YAML record
    (more than the GUI shows, by design)."""
    return {
        "summary": results_summary(),
        "ships": results_player_ships(),
        "pilots": results_pilots(),
        "quests": results_quests(),
    }


# --- GUI list-box adapters (wrap dicts so templates can use .get) -------------
def _wrap(rows):
    return [MastDataObject(r) for r in rows]


def results_ship_items():
    return _wrap(results_player_ships())


def results_pilot_items():
    return _wrap(results_pilots())


def results_quest_items():
    """Collapsible quest-log items for the results tab: the game (SHARED) plus every
    player ship. Uses the SAME shared renderer as the in-game log (quest_log_*);
    only the `sources` list differs, so both logs stay identical by construction."""
    sources = [("Game", Agent.SHARED_ID)]
    for so in to_space_object_list(role("__player__")):
        sources.append((str(so.name), so.id))
    return quest_log_build_items(sources)


def results_ship_template(item):
    gui_row("row-height: 1.2em;padding:6px;")
    gui_text(f"$text:{item.get('name')};justify: left;")
    gui_row("row-height: 1.0em;padding:6px;")
    gui_text(f"$text:Kills {item.get('kills')}   Tonnage {item.get('tonnage')}   Damage {item.get('damage')}   Hull {item.get('hull_pct')}%;justify: left;font:gui-1")


def results_ship_title_template():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text("$text:Fleet;justify: left;")


def results_pilot_template(item):
    gui_row("row-height: 1.2em;padding:6px;")
    gui_text(f"$text:{item.get('call_sign')};justify: left;")
    gui_row("row-height: 1.0em;padding:6px;")
    gui_text(f"$text:Sorties {item.get('sorties')}   Kills {item.get('kills')}   Tonnage {item.get('tonnage')}   Damage {item.get('damage')}   Objectives {item.get('objectives')};justify: left;font:gui-1")


def results_pilot_title_template():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text("$text:Air Wing;justify: left;")


# Quest rows/headers + the tab title are rendered by the SHARED sbs_utils
# quest_log_template / quest_log_title (used by the in-game log too) - see
# game_results.mast. There is intentionally no results-specific quest template.


def game_results_timestamp():
    """Wall-clock timestamp ("YYYY-MM-DD HH:MM:SS") for a game-results record.

    Computed in Python on purpose: MAST inline (~~ ~~) runs with a restricted
    __builtins__ (the mast_globals allow-list, no __import__), and datetime's
    now()/strftime() trigger an internal import that fails there. A normal module
    function runs with real builtins, so calling it from MAST is safe.
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def game_results_map(world_select):
    """Best-effort readable scenario/map name for a game-results record.

    LM's WORLD_SELECT may be a map object (with .display_name / .path), a plain
    string, or None. (getattr isn't in MAST's eval globals, so do this in Python.)
    """
    if world_select is None:
        return ""
    name = getattr(world_select, "display_name", None) or getattr(world_select, "path", None)
    return str(name) if name else str(world_select)
