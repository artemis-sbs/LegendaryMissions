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
from sbs_utils.procedural.gui import gui_row, gui_text, gui_icon, gui_list_box_header, gui_list_box_is_header, gui_text_escape
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
def _results_attacker_id(parent_id, source_id):
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


def _results_is_creditable(attacker_id):
    """Only player BRIDGE ships earn credit here. Fighter/shuttle (cockpit) kills are
    credited by the hangar addon instead, so the two never double-count and the
    hangar's Air Wing works in missions that don't load this (consoles) addon."""
    if attacker_id is None or attacker_id == 0:
        return False
    return has_role(attacker_id, "__player__")


def _results_victim_tonnage(victim):
    """Flavor 'tonnage' for a destroyed object, from its shipData hullpoints."""
    so = to_object(victim)
    if so is None:
        return 0
    sd = get_ship_data_for(so.art_id)
    hp = (sd.get("hullpoints", 0) or 0) if sd is not None else 0
    return int(hp) * TONNAGE_PER_HULLPOINT


def _results_bump(agent_id, key, amount):
    set_inventory_value(agent_id, key, get_inventory_value(agent_id, key, 0) + amount)


def results_credit_kill(parent_id, source_id, victim_id):
    """Credit one kill + the victim's tonnage to the player bridge ship that landed
    the final blow. (Fighter/shuttle kills are credited by the hangar addon.)"""
    attacker = _results_attacker_id(parent_id, source_id)
    if not _results_is_creditable(attacker):
        return
    tons = _results_victim_tonnage(victim_id)
    _results_bump(attacker, _STAT_KILLS, 1)
    _results_bump(attacker, _STAT_TONNAGE, tons)


def results_credit_damage(parent_id, source_id, amount):
    """Accumulate raw damage dealt by a player bridge ship (the option-B 'impact'
    stat). (Cockpit damage is credited by the hangar addon.)"""
    attacker = _results_attacker_id(parent_id, source_id)
    if not _results_is_creditable(attacker):
        return
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        return
    if amount <= 0:
        return
    _results_bump(attacker, _STAT_DAMAGE, amount)


# --- End-screen / save read-outs ---------------------------------------------
def _results_hull_pct(ship_id):
    """Remaining hull % (0-100) from summed SHPSYS damage vs max; 100 if unknown.

    The formula moved to sbs_utils (`viewscreen_hull_percent`) when the viewscreen's
    data column needed the same number: two copies of "what does damaged mean" is one
    too many. This stays as the end-screen's name for it, and keeps the end screen's
    own convention that a ship we cannot read at all counts as 0 rather than unknown.
    """
    from sbs_utils.procedural.gui.viewscreen_pages import viewscreen_hull_percent
    if to_space_object(ship_id) is None:
        return 0
    pct = viewscreen_hull_percent(ship_id)
    return 100 if pct is None else pct


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
            "hull_pct": _results_hull_pct(sid),
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
    gui_text(f"$text:{gui_text_escape(item.get('name'))};justify: left;")
    gui_row("row-height: 1.0em;padding:6px;")
    gui_text(f"$text:Kills {item.get('kills')}   Tonnage Destroyed {item.get('tonnage')}   Damage Dealt {item.get('damage')}   Hull {item.get('hull_pct')}%;justify: left;font:gui-1")


def results_ship_title_template():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text("$text:Fleet;justify: left;")


def results_pilot_template(item):
    gui_row("row-height: 1.2em;padding:6px;")
    gui_text(f"$text:{gui_text_escape(item.get('call_sign'))};justify: left;")
    gui_row("row-height: 1.0em;padding:6px;")
    gui_text(f"$text:Sorties {item.get('sorties')}   Kills {item.get('kills')}   Tonnage Destroyed {item.get('tonnage')}   Damage Dealt {item.get('damage')}   Objectives {item.get('objectives')};justify: left;font:gui-1")


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


# ---------------------------------------------------------------------------
# Markdown for the results screen
#
# The summary and enemy breakdowns used to be built as one gui_row per stat, each row
# taking an equal share of the section - so six stats spread themselves over three
# quarters of the screen with a hand's width of black between each line, and a longer
# list simply ran off the bottom with no way to reach it.
#
# A text area renders markdown TABLES and scrolls when it has to, so the same numbers
# become one widget, tightly set, with the overflow problem solved rather than avoided.
# ---------------------------------------------------------------------------

_MD_NL = chr(10)


def _md_clean(text):
    """Cell text with braces removed.

    A `{` reaching MAST is re-run as an f-string, and these strings pass through MAST on
    their way to the widget. Ship and pilot names are author-set and could carry one.
    """
    return str(text).replace("{", "(").replace("}", ")")


def _md_table(pairs, head=("", "")):
    """[(label, value), ...] -> a two-column markdown table. Empty when there are no rows."""
    if not pairs:
        return ""
    out = ["| " + _md_clean(head[0]) + " | " + _md_clean(head[1]) + " |", "|---|---:|"]
    for label, value in pairs:
        out.append("| " + _md_clean(label) + " | " + _md_clean(value) + " |")
    return _MD_NL.join(out)


def results_summary_md(difficulty, surrendered, minutes, credits=None,
                       top_name="", top_earned=0):
    """The Summary tab as markdown.

    `credits` None hides its row (a mission that never captured CREDITS_START), and an
    empty `top_name` hides the multiplayer standing - same opt-in rules the row-based
    version had, kept here so the MAST side stays a single call.
    """
    t = results_summary()
    pairs = [
        ("Difficulty", difficulty),
        ("Enemies destroyed", t["kills"]),
        ("Tonnage destroyed", t["tonnage"]),
        ("Damage dealt", t["damage"]),
        ("Enemies surrendered", surrendered),
        ("Game time", str(minutes) + " minutes"),
    ]
    if credits is not None:
        pairs.append(("Credits earned", credits))
    if top_name:
        pairs.append(("Top earner", str(top_name) + " - " + str(top_earned)))
    return _md_table(pairs, ("", ""))


# shipData race key -> the name a player would recognize.
_MD_RACES = (
    ("tsn_destroyed", "Terran"),
    ("arvonian_ships_destroyed", "Arvonian"),
    ("kralien_ships_destroyed", "Kralien"),
    ("skaraan_ships_destroyed", "Skaraan"),
    ("ximni_ships_destroyed", "Ximni"),
    ("torgoth_ships_destroyed", "Torgoth"),
)


def results_enemies_md(stats):
    """The Enemies tab as markdown.

    Races with no kills are LEFT OUT rather than listed as zero: six stock races padded
    with zeroes tells a total-conversion mission's crew nothing, and a mission that fields
    other races had them counted under keys this list never knew about. Anything counted
    under an unrecognized `*_destroyed` key is picked up and titled, so a mod's races
    appear without this list being edited.
    """
    stats = stats or {}
    pairs = []
    known = set()
    for key, label in _MD_RACES:
        known.add(key)
        n = int(stats.get(key, 0) or 0)
        if n:
            pairs.append((label, n))
    for key in sorted(stats):
        if key in known or not str(key).endswith("_destroyed"):
            continue
        n = int(stats.get(key, 0) or 0)
        if not n:
            continue
        # Two shapes reach this dict: `<side>_destroyed` (from obj.side) and
        # `<race>_ships_destroyed` (from the art id). Strip the longer suffix first or a
        # race reads as "Tng Jem Ships" instead of "Tng Jem".
        label = str(key)
        for suffix in ("_ships_destroyed", "_destroyed"):
            if label.endswith(suffix):
                label = label[:-len(suffix)]
                break
        pairs.append((label.replace("_", " ").title(), n))
    surrendered = int(stats.get("ships_surrender", 0) or 0)
    if surrendered:
        pairs.append(("Surrendered", surrendered))
    if not pairs:
        return "Nothing was destroyed."
    return _md_table(pairs, ("Destroyed", ""))
