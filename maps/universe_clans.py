"""Clan loading for the Open Universe (see clans.amd).

Clans are authored in clans.amd and spawned as sides. A system's owning clan is a
pure function of (seed, i, j): named home systems win, otherwise a keyed pick
among foe clans - so the galaxy map and what spawns agree. See UNIVERSE_CHANGES.md
(Epics C/I).
"""
from sbs_utils import scatter
from sbs_utils.procedural.quest import document_get_amd_file
from sbs_utils.procedural.execution import labels_get_type
from sbs_utils.mast.mast_node import MastDataObject


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
            "enemies": "tsn" if diplomacy == "foe" else "",
        }))
    return clans


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


def universe_system_clan(clans, seed, i, j, base_kind):
    """Owning clan key + effective kind for a system, given its base kind.

    A clan home -> that clan + 'station' (a clan presence); a keyed 'enemy'
    system -> a foe clan (still 'enemy'); otherwise no clan. Both the map and the
    generator call this so naming/ownership match what spawns. base_kind comes
    from universe_sector_kind (clan-agnostic) - passed in to avoid a cross-import.
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
