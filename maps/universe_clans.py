"""Clan loading for the Open Universe (see clans.amd).

Clans are authored in clans.amd and spawned as sides. A system's owning clan is a
pure function of (seed, i, j): named home systems win, otherwise a keyed pick
among foe clans - so the galaxy map and what spawns agree. See UNIVERSE_CHANGES.md
(Epics C/I).
"""
import random
from sbs_utils import scatter
from sbs_utils.procedural.quest import document_get_amd_file
from sbs_utils.procedural.execution import labels_get_type
from sbs_utils.procedural.sides import side_set_relations
from sbs_utils.procedural.roles import all_roles
from sbs_utils.procedural.gui import gui_row, gui_text, gui_info_panel_send_message
from sbs_utils.mast.mast_node import MastDataObject

# Fallback race pool when a clan declares no makeup.
_DEFAULT_RACES = ["Kralien", "Torgoth", "Arvonian", "Ximni"]


# --- Nav "known locations" list ----------------------------------------------
def universe_known_locations(clans, quest_targets):
    """Notable systems for the nav list: home base, clan homes, and active quest
    targets - each a MastDataObject with name + i/j."""
    locs = [MastDataObject({"name": "Home Base", "i": 0, "j": 0})]
    for c in clans:
        for h in (c.get("homes") or []):
            if len(h) == 2:
                locs.append(MastDataObject({"name": c.name, "i": int(h[0]), "j": int(h[1])}))
    for t in quest_targets:
        locs.append(MastDataObject({"name": "Quest Target", "i": int(t[0]), "j": int(t[1])}))
    return locs


def universe_location_template(item):
    gui_row("row-height: 1.2em;")
    gui_text(f"$text:{item.name}  ({item.i}, {item.j});justify:left;font:gui-1")


def universe_location_title():
    gui_row("row-height: 1.2em;padding:6px;background:#1578;")
    gui_text("$text:Known Locations;justify:left;")


# --- Diplomacy deltas (persisted per side/clan pair) -------------------------
# Authored defaults come from clans.amd (foe/neutral); these deltas override them
# (e.g. a negotiated ceasefire) and persist in the save. Keyed by a sorted pair.
def universe_dip_key(a, b):
    return "|".join(sorted([str(a), str(b)]))


def universe_set_dip(dip, a, b, relation):
    """Record a per-pair relation override; returns the (possibly new) dict."""
    if not isinstance(dip, dict):
        dip = {}
    dip[universe_dip_key(a, b)] = int(relation)
    return dip


def universe_apply_dip(dip):
    """Re-apply saved per-pair relation overrides (call after sides exist)."""
    if not isinstance(dip, dict):
        return
    for k, relation in dip.items():
        parts = k.split("|")
        if len(parts) == 2:
            side_set_relations(parts[0], parts[1], relation)


# --- Universe registry (start-screen dropdown) -------------------------------
# Each universe is a label (type: universe/<key>) in universes.mast naming its
# clans/narrative AMD files. The dropdown lists them; selecting one picks which
# clans.amd (+ narrative.amd) to load.
def universe_registry():
    return labels_get_type("universe/")


def universe_options_csv():
    """Comma list of universe display names for the dropdown's list: field."""
    names = []
    for l in universe_registry():
        names.append(l.get_inventory_value("display", l.get_inventory_value("key", "Default")))
    return ", ".join(names) if names else "Default"


def _universe_field(display, field, default):
    for l in universe_registry():
        if l.get_inventory_value("display") == display or l.get_inventory_value("key") == display:
            return l.get_inventory_value(field, default)
    return default


def universe_clans_file(display):
    """The clans.amd filename for the selected universe (fallback clans.amd)."""
    return _universe_field(display, "clans", "clans.amd")


def universe_narrative_file(display):
    """The narrative.amd filename for the selected universe (fallback)."""
    return _universe_field(display, "narrative", "narrative.amd")


def universe_parse_clans(content):
    """Parse clans.amd content into a list of clan records (MastDataObject).

    Each record: key, name, desc, color, archetype, diplomacy (foe/neutral),
    homes [[i,j],...], leans {axis:val}, quest_pool [..], and enemies (csv for
    prefab_side_generic - "tsn" for foe clans, "" for neutral).
    """
    doc = document_get_amd_file(None, "Clans", content=content)
    clans = []
    for n in doc.get("children", []):
        data = n.get("data") or {}
        diplomacy = data.get("diplomacy", "neutral")
        clans.append(MastDataObject({
            "key": n.get("key"),
            "name": n.get("display_text"),
            "desc": (n.get("description") or "").strip(),
            "color": data.get("color", "#888888"),
            "archetype": data.get("archetype", "neutral"),
            "diplomacy": diplomacy,
            "homes": data.get("homes") or [],
            "leans": data.get("leans") or {},
            "quest_pool": data.get("quest_pool") or [],
            "chatter": data.get("chatter") or [],
            # makeup: race composition of this clan's ships - a single race, an
            # even list, or a {race: weight} dict (see clan_pick_race).
            "makeup": data.get("makeup"),
            # Optional comms-card identity (info panel): a face string + an icon.
            "face": data.get("face"),
            "icon": data.get("icon"),
            "enemies": "tsn" if diplomacy == "foe" else "",
        }))
    return clans


# Ambient comms chatter by archetype (clans.amd may override with a `chatter:`
# list). {name} is substituted with the clan name. Flavor only - never reveals
# the map (round-5 decision).
_ARCHETYPE_CHATTER = {
    "military":  ["This is {name} space - mind your conduct, captain.",
                  "{name} patrols have you on scope."],
    "trader":    ["{name} welcomes honest custom - credits talk.",
                  "Safe lanes, captain. {name} has cargo if you have coin."],
    "settler":   ["{name} holds the drift out here. Keep it civil.",
                  "Not much law this far out - {name} looks after its own."],
    "mercenary": ["{name} works for the highest bidder. Got a contract?",
                  "Coin first, questions later - the {name} way."],
    "pirate":    ["{name} smells weakness, captain...",
                  "Best run along - this is {name} territory."],
    "cult":      ["The {name} sees more than you know.",
                  "{name} whispers in the dark between stars."],
}


def universe_chatter_line(clan):
    """A random ambient line for a clan (its authored chatter, else archetype
    defaults), with {name} substituted. '' if none."""
    if clan is None:
        return ""
    lines = clan.get("chatter") or _ARCHETYPE_CHATTER.get(clan.get("archetype"), [])
    if not lines:
        return ""
    return random.choice(lines).replace("{name}", clan.get("name", "the locals"))


# --- Chatter / narrative comms delivery (info panel, NOT the text waterfall) ---
# Chatter reads as a hail from a clan, not a log blip: an info-panel card carrying
# the clan's name + color (+ optional face/icon), kept in history, auto-dismissed.
# This mirrors the HereThereBeMonsters here_*_info_message helpers - good
# candidates to promote into sbs_utils (procedural.comms) as a reusable
# "incoming comms card" so missions don't each reinvent it. See UNIVERSE_CHANGES.
def _chatter_consoles():
    """The comms consoles that should receive universe chatter/comms cards."""
    return all_roles("console, comms")


def universe_chatter_card(clan, line, time=10):
    """Deliver a clan's ambient line as an info-panel card (face/name/color)."""
    if not line:
        return
    color = clan.get("color", "#0cf") if clan is not None else "#0cf"
    name = clan.get("name") if clan is not None else None
    gui_info_panel_send_message(
        _chatter_consoles(), line, message_color=color, title=name,
        title_color=color, face=(clan.get("face") if clan is not None else None),
        icon_index=(clan.get("icon") if clan is not None else None),
        time=time, history=True)


def universe_info_card(line, title=None, color="#0cf", time=10):
    """Deliver a non-clan ambient/narrative line (sensors, comms chatter, news) as
    an info-panel card - same surface as clan chatter, no portrait."""
    if not line:
        return
    gui_info_panel_send_message(
        _chatter_consoles(), line, message_color=color, title=title,
        title_color=color, time=time, history=True)


def clan_pick_race(clan):
    """Pick a race for one of a clan's ships from its authored makeup.

    makeup may be a single race string, an even list ([Torgoth, Kralien]), or a
    weighted dict ({Torgoth: 70, Kralien: 30}). No makeup (or no clan) -> a random
    pick from the default pool, preserving the old mixed behavior.
    """
    makeup = clan.get("makeup") if clan is not None else None
    if not makeup:
        return random.choice(_DEFAULT_RACES)
    if isinstance(makeup, dict):
        races = list(makeup.keys())
        weights = list(makeup.values())
        return random.choices(races, weights=weights)[0]
    if isinstance(makeup, list):
        return random.choice(makeup) if makeup else random.choice(_DEFAULT_RACES)
    return str(makeup)


def clan_get(clans, key):
    """The clan record with this key, or None."""
    for c in clans:
        if c.key == key:
            return c
    return None


def clan_home_owner(clans, i, j):
    """The clan key whose home is system (i,j), or None (named homes win)."""
    for c in clans:
        for h in c.get("homes", []):
            if len(h) == 2 and int(h[0]) == int(i) and int(h[1]) == int(j):
                return c.key
    return None


def clan_name(clans, key):
    """Display name for a clan key (or the key if unknown)."""
    c = clan_get(clans, key)
    return c.name if c is not None else key


def clan_color(clans, key):
    """Map/side color for a clan key (or a default)."""
    c = clan_get(clans, key)
    return c.color if c is not None else "#888888"


def clan_archetype(clans, key):
    """Archetype for a clan key (military/trader/...), or None. Used to flavor the
    system POI deck (universe_systems.py)."""
    c = clan_get(clans, key)
    return c.archetype if c is not None else None


def universe_system_clan(clans, seed, i, j, base_kind):
    """Owning clan key + effective kind for a system, given its base kind.

    A clan home -> that clan + 'station' (a clan presence); a keyed 'enemy'
    system -> a foe clan (still 'enemy'); otherwise no clan. Both the map and the
    generator call this so naming/ownership match what spawns. base_kind comes
    from universe_system_kind (clan-agnostic) - passed in to avoid a cross-import.
    """
    home = clan_home_owner(clans, i, j)
    if home is not None:
        return home, "station"
    if base_kind == "enemy":
        return clan_for_system(clans, seed, i, j), "enemy"
    return None, base_kind


def clan_for_system(clans, seed, i, j):
    """Owning clan key for a clan/foe system: home wins, else a keyed pick among
    foe clans (deterministic). Returns None if there are no foe clans.

    The caller decides whether a given system IS a clan system (by kind); this
    just names the owner reproducibly so the map and spawn agree.
    """
    owner = clan_home_owner(clans, i, j)
    if owner is not None:
        return owner
    foes = [c.key for c in clans if c.diplomacy == "foe"]
    if not foes:
        return None
    roll = scatter.cell_roll(seed, 13, int(i), int(j), 7)
    return foes[int(roll * len(foes)) % len(foes)]
