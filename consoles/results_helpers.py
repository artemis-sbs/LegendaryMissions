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
from sbs_utils.gui import get_client_aspect_ratio
from sbs_utils.helpers import FrameContext
from sbs_utils.pages.layout.measure import measure_line_width


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
# The stat tabs
#
# The summary and enemy breakdowns used to be built as one gui_row per stat, each row
# taking an equal share of the section - so six stats spread themselves over three
# quarters of the screen with a hand's width of black between each line, and a longer
# list simply ran off the bottom with no way to reach it. They became a markdown table
# in a text area next, which fixed the spread and the overflow but is fixed at the
# text area's own fonts and only ever uses as much width as the words need. They are
# now gui_tables: one widget, scrolls when it has to, sized and fonted by the screen.
# ---------------------------------------------------------------------------

def _md_clean(text):
    """Cell text with braces removed.

    A `{` reaching MAST is re-run as an f-string, and these strings pass through MAST on
    their way to the widget. Ship and pilot names are author-set and could carry one.
    """
    return str(text).replace("{", "(").replace("}", ")")


# ---------------------------------------------------------------------------
# The stat tabs are gui_table ROWS + COLUMNS, not a markdown table.
#
# A text-area table cannot do either thing this screen needs. Its fonts are class
# constants (TableLine.HDR_FONT gui-3 / BODY_FONT gui-2), so a stat block cannot be
# made bigger; and its columns are sized to their NATURAL content and only ever
# shrunk to fit - never grown. Measured at 2880x1394 the Summary was handed a 2025px
# panel and drew a 232px table in the corner of it, with "Enemies surrendered"
# wrapping inside a column sized to the exact width of that same text.
#
# gui_table sizes `auto` columns to the widest cell across ALL rows and shares the
# FULL width between them, and it takes a `font`. Same pairs, same opt-in rules.
# ---------------------------------------------------------------------------

def _pair_rows(pairs):
    """[(label, value), ...] -> the row dicts gui_table reads (see _RESULT_COLUMNS)."""
    return [{"stat": _md_clean(label), "value": _md_clean(value)}
            for label, value in pairs]


# The font both stat tabs are drawn in. Here rather than in the .mast because the
# column widths below are MEASURED in it - the two cannot be allowed to drift apart.
STAT_FONT = "gui-4"


def _fit_pct(texts, font, span, floor_frac, ceil_frac):
    """Screen-percent width that fits the widest of `texts`, with a little slack.

    Falls back to `span * ceil_frac` when the engine cannot measure (no client aspect
    ratio yet, headless), so a screen still lays out - just not as tightly.
    """
    ar = get_client_aspect_ratio(FrameContext.client_id)
    widest = 0
    for t in texts:
        w = measure_line_width(font, str(t))
        if w is None:
            return round(span * ceil_frac, 2)
        if w > widest:
            widest = w
    if not ar or not ar.x:
        return round(span * ceil_frac, 2)
    # 1.12: a column sized to the exact width of its own longest string wraps on any
    # rounding disagreement between measuring the text and drawing it, and a wrap in a
    # fixed-height table row spills into the row below.
    pct = (widest * 1.12 / ar.x) * 100.0
    return round(min(max(pct, span * floor_frac), span * ceil_frac), 2)


def results_stat_columns(items=None, span=70.0, font=None):
    """Column spec shared by every stat tab, so they line up with each other.

    `span` is how many points of SCREEN WIDTH the panel holding the table covers - the
    tab content sits at `area: 28, 6, 99, 94`, so ~70. It is a parameter and not a
    constant because a `col-width` is resolved against the SCREEN, not against the
    table: gui_table's `auto` columns are shared out of 100, which put the second column
    of this table at 97..129% - off the screen entirely, drawn and invisible.

    So the widths are MEASURED here instead, in the font the cells are drawn in, and
    converted to screen percent for the screen actually in front of the player. A fixed
    percentage cannot do this job: a font is an absolute pixel size, so a value column
    of 10 points is 288px on an ultrawide and 102px on 1024x768 - wide enough for
    "6 minutes" on one and not the other.

    The NUMBER LEADS and the label follows it, left-justified:

          12  Enemies destroyed
        4750  Damage dealt

    THREE columns, not two, and the middle one is empty. A right-justified column puts
    its text hard against the column that follows, and widening it moves both - so the
    gap cannot come from either of the two columns that carry text ("5Difficulty" is
    what happens without this). A spacer column one "MM" wide is the gap.

    Only the value column is measured: right-justified so the figures line up on their
    units, and no wider than the widest of them. Values are kept NUMERIC (the unit lives
    in the label - "Game time (minutes)") so that column stays narrow and the numbers
    stay a column of numbers. The label column is everything left in the panel; being
    left-justified, its width decides nothing but how long a label may get before it
    wraps, so a label can never wrap.
    """
    font = font or STAT_FONT
    items = items or []
    value_w = _fit_pct([i["value"] for i in items], font, span, 0.06, 0.25)
    gap_w = _fit_pct(["MM"], font, span, 0.01, 0.08)
    return [
        {"key": "value", "label": "", "align": "r", "width": value_w},
        {"key": None, "label": "", "align": "l", "width": gap_w},
        {"key": "stat", "label": "", "align": "l", "width": round(span - value_w - gap_w, 2)},
    ]


def results_summary_items(difficulty, surrendered, minutes, credits=None,
                          top_name="", top_earned=0):
    """The Summary tab's rows.

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
        # The unit rides in the LABEL, and so does the earner's name: the value column is
        # measured on its widest entry, so one "6 minutes" or "Artemis - 120" in it makes
        # every number in the table sit that far from its label.
        ("Game time (minutes)", minutes),
    ]
    if credits is not None:
        pairs.append(("Credits earned", credits))
    if top_name:
        pairs.append(("Top earner - " + str(top_name), top_earned))
    return _pair_rows(pairs)


# shipData race key -> the name a player would recognize.
_MD_RACES = (
    ("tsn_destroyed", "Terran"),
    ("arvonian_ships_destroyed", "Arvonian"),
    ("kralien_ships_destroyed", "Kralien"),
    ("skaraan_ships_destroyed", "Skaraan"),
    ("ximni_ships_destroyed", "Ximni"),
    ("torgoth_ships_destroyed", "Torgoth"),
)


def results_enemies_items(stats):
    """The Enemies tab's rows (empty when nothing was destroyed).

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
    return _pair_rows(pairs)
