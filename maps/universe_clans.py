"""Clan loading for the Open Universe (see clans.amd).

Clans are authored in clans.amd and spawned as sides. A system's owning clan is a
pure function of (seed, i, j): named home systems win, otherwise a keyed pick
among foe clans - so the galaxy map and what spawns agree. See UNIVERSE_CHANGES.md
(Epics C/I).
"""
from sbs_utils import scatter
from sbs_utils.procedural.quest import document_get_amd_file
from sbs_utils.mast.mast_node import MastDataObject


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
