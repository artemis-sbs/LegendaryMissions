"""Helpers for the Open Universe map (maps/universe.mast).

A sector's contents are a pure function of (universe_seed, i, j): only the
current sector is instantiated, always around the origin, and a jump clears it
and regenerates the neighbour. So the whole universe is "stored" in its seed
plus the current coordinates (persistence of player-made changes comes later).
"""
import math
import os
import shutil

from sbs_utils import scatter
from sbs_utils.vec import Vec3
from sbs_utils.fs import get_mission_dir, save_yaml_data, load_yaml_data
from sbs_utils.procedural.terrain import terrain_spawn_field_keyed
from sbs_utils.procedural.space_objects import delete_objects_box
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.query import to_object_list
from sbs_utils.procedural.execution import labels_get_type
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.sides import to_side_id
from sbs_utils.procedural.upgrades import upgrade_add
from sbs_utils.procedural.quest import quest_agent_quests, quest_add, quest_set_key
from sbs_utils.agent import Agent

# Half-extent of a sector's playable area (world units).
UNIVERSE_SECTOR_R = 50_000

# --- Save format version + migration ----------------------------------------
# The universe is mostly procedural (regenerated from the seed); the save stores
# only deltas, so most changes need NO migration. Bump this only for a breaking
# restructure of a stored field, and add a matching _MIGRATIONS step. Additive
# fields are read with .get(default) and don't need a bump. See QUESTS_PLAN 8a.
UNIVERSE_SAVE_VERSION = 1

# Ordered single-step migrations: _MIGRATIONS[v] upgrades a v save to v+1.
# e.g. _MIGRATIONS = {1: _migrate_1_to_2}
_MIGRATIONS = {}


def universe_sector_key(universe_seed, i, j):
    """Stable per-sector seed derived from the universe seed and logical coords.

    Uses the same position-keyed mix as the scatter lattice, so a sector's
    terrain is reproducible and independent of any other sector.
    """
    return scatter._mix(int(universe_seed), int(i), int(j))


def universe_generate_sector(universe_seed, i, j, terrain_value=2):
    """Spawn a sector's keyed asteroid/nebula field at the origin.

    Pure function of (universe_seed, i, j): the same sector always regenerates
    the same field. Features (stations, enemies, anomalies) come in a later step.
    """
    key = universe_sector_key(universe_seed, i, j)
    r = UNIVERSE_SECTOR_R
    nebula_chance = terrain_value * 0.0012
    asteroid_chance = terrain_value * 0.0010
    terrain_spawn_field_keyed(key, 1000, -r, -r, r, r, terrain_value,
                              nebula_chance, asteroid_chance)


def universe_clear_sector():
    """Remove the current sector's terrain and NPCs, keeping player ships.

    broad_type 0x1F = terrain (0x0f) + NPC (0x10); PLAYER (0x20) is excluded, so
    the player ships survive the jump while everything else is despawned.
    """
    delete_objects_box(0, 0, 0, 1_000_000, 1_000_000, 1_000_000, broad_type=0x1F)


def universe_reposition_players():
    """Place player ships back near the origin after arriving in a new sector."""
    players = to_object_list(role("__player__"))
    n = max(1, len(players))
    for idx, p in enumerate(players):
        ang = (idx / n) * 2.0 * math.pi
        p.pos = Vec3(2000.0 * math.cos(ang), 0.0, 2000.0 * math.sin(ang))


# --- Persistence (procedural + delta) ---------------------------------------
# The base universe regenerates from the seed; only player-made changes are
# stored. One shared save file under data/missions/common_data.
def universe_save_path():
    """Path to the single universe save file, creating common_data if needed."""
    common = os.path.join(os.path.dirname(get_mission_dir()), "common_data")
    os.makedirs(common, exist_ok=True)
    return os.path.join(common, "universe_save.yaml")


def universe_save_state(data):
    """Write the full save dict (low-level), stamped with the current version."""
    data["save_version"] = UNIVERSE_SAVE_VERSION
    save_yaml_data(universe_save_path(), data)


def universe_migrate(data):
    """Bring a loaded save up to UNIVERSE_SAVE_VERSION via the migration ladder.

    Only stored deltas are ever migrated (procedural content regenerates from the
    seed). Returns the upgraded dict, the dict unchanged if it is NEWER than this
    build understands (load best-effort, don't rewrite), or None if it cannot be
    migrated - which the callers treat as "no save" (New Game). See QUESTS_PLAN 8a.
    """
    if not isinstance(data, dict):
        return None
    v = data.get("save_version", 1)
    if v > UNIVERSE_SAVE_VERSION:
        return data
    try:
        while v < UNIVERSE_SAVE_VERSION and v in _MIGRATIONS:
            data = _MIGRATIONS[v](data)
            v += 1
        data["save_version"] = v
        return data
    except Exception as e:
        print(f"universe_migrate failed: {e}")
        return None


def universe_save(seed, i, j, sectors):
    """Persist the universe seed, current sector, and delta map.

    Merges into the existing save so the players/side_credits sections (written
    by universe_save_players) are preserved.
    """
    data = universe_load() or {}
    data["universe_seed"] = seed
    data["current_sector"] = [i, j]
    data["sectors"] = sectors
    universe_save_state(data)


# --- Player / economy persistence -------------------------------------------
# Items are per-ship (counts); credits are a shared per-side pool (the future
# admiral / RTS console will own more of this economy). Keyed by ship name /
# side key, which are stable across reloads (runtime ids are not).
UNIVERSE_START_CREDITS = 500


def _item_keys():
    return [l.get_inventory_value("key") for l in labels_get_type("item/")]


def _item_label(key):
    for l in labels_get_type("item/"):
        if l.get_inventory_value("key") == key:
            return l
    return None


# Quests persist alongside items: per-ship quests by ship name, plus the
# shared/game quest tree. Flat quests only (matches current usage); serialized
# fields are YAML-safe (state/progress are ints, data is the AMD yaml dict).
def _serialize_quests(agent_id):
    tree = quest_agent_quests(agent_id)
    out = {}
    if tree is None:
        return out
    children = tree.get("children") or {}
    for qid, q in children.items():
        out[qid] = {
            "display_text": q.get("display_text", ""),
            "description": q.get("description", ""),
            "state": int(q.get("state", 0) or 0),
            "data": q.get("data"),
            "progress": q.get("progress", 0),
        }
    return out


def _restore_quests(agent_id, quests):
    if not isinstance(quests, dict):
        return
    for qid, rec in quests.items():
        quest_add(agent_id, qid, rec.get("display_text", ""),
                  rec.get("description", ""), state=rec.get("state", 0),
                  data=rec.get("data"))
        prog = rec.get("progress", 0)
        if prog:
            quest_set_key(agent_id, qid, "progress", prog)


def universe_save_players():
    """Persist per-ship items/installs/quests, shared credits, and game quests."""
    data = universe_load() or {}
    players = {}
    side_credits = {}
    for ship in to_object_list(role("__player__")):
        items = {}
        for k in _item_keys():
            c = get_inventory_value(ship.id, k, 0)
            if c:
                items[k] = c
        installs = get_inventory_value(ship.id, "installs", [])
        players[ship.name] = {"items": items, "installs": list(installs),
                              "quests": _serialize_quests(ship.id)}
        side = ship.side
        if side:
            side_credits[side] = get_inventory_value(to_side_id(side), "credits", 0)
    data["players"] = players
    data["side_credits"] = side_credits
    data["shared_quests"] = _serialize_quests(Agent.SHARED_ID)
    universe_save_state(data)


def universe_load_players():
    """Restore per-ship items/installs + per-side credits; re-apply installs.

    New universes (no save) start each player side at UNIVERSE_START_CREDITS.
    """
    data = universe_load() or {}
    players = data.get("players", {})
    side_credits = data.get("side_credits", {})
    seen_sides = set()
    _restore_quests(Agent.SHARED_ID, data.get("shared_quests"))
    for ship in to_object_list(role("__player__")):
        side = ship.side
        if side and side not in seen_sides:
            set_inventory_value(to_side_id(side), "credits",
                                side_credits.get(side, UNIVERSE_START_CREDITS))
            seen_sides.add(side)
        pdata = players.get(ship.name)
        if not pdata:
            continue
        for k, c in pdata.get("items", {}).items():
            set_inventory_value(ship.id, k, c)
        installs = pdata.get("installs", [])
        set_inventory_value(ship.id, "installs", installs)
        for k in installs:
            lbl = _item_label(k)
            if lbl is not None:
                upgrade_add(ship.id, lbl, data={"key": k}, activate=True)
        _restore_quests(ship.id, pdata.get("quests"))


def universe_load():
    """Load the saved universe (migrated to the current version), or None.

    Backs up the file once before an upgrading migration so a bad migration is
    recoverable (universe_save.yaml.bak).
    """
    raw = load_yaml_data(universe_save_path())
    if not isinstance(raw, dict):
        return None
    before = raw.get("save_version", 1)
    data = universe_migrate(raw)
    if data is not None and data.get("save_version", 1) > before:
        path = universe_save_path()
        if not os.path.exists(path + ".bak"):
            try:
                shutil.copyfile(path, path + ".bak")
            except Exception:
                pass
    return data


def universe_sector_flag(sectors, i, j, flag):
    """True if a per-sector delta flag (e.g. station_destroyed) is set."""
    if not isinstance(sectors, dict):
        return False
    s = sectors.get(f"{i},{j}")
    return bool(s.get(flag)) if isinstance(s, dict) else False


def universe_set_sector_flag(sectors, i, j, flag, value=True):
    """Set a per-sector delta flag; returns the (possibly new) sectors dict."""
    return universe_set_sector_value(sectors, i, j, flag, value)


def universe_sector_value(sectors, i, j, field, default=None):
    """Read an arbitrary per-sector delta field (e.g. market stock)."""
    if not isinstance(sectors, dict):
        return default
    s = sectors.get(f"{i},{j}")
    return s.get(field, default) if isinstance(s, dict) else default


def universe_set_sector_value(sectors, i, j, field, value):
    """Set an arbitrary per-sector delta field; returns the sectors dict."""
    if not isinstance(sectors, dict):
        sectors = {}
    k = f"{i},{j}"
    s = sectors.get(k)
    if not isinstance(s, dict):
        s = {}
    s[field] = value
    sectors[k] = s
    return sectors


# --- Sector kind + galaxy map ------------------------------------------------
# Named landmarks at fixed coords; these override the procedural kind and are
# shown on the galaxy map even before you visit them. Add more here freely.
UNIVERSE_POIS = {
    (0, 0): ("Home Base", "home"),
    (5, 3): ("Trade Nexus", "station"),
    (-4, 6): ("The Maelstrom", "anomaly"),
    (8, -5): ("Raider Den", "enemy"),
    (-7, -7): ("Derelict Drift", "nebula"),
}

_KIND_ABBR = {"home": "Home", "station": "Base", "enemy": "Foe",
              "nebula": "Neb", "anomaly": "!!", "empty": "."}


def universe_sector_name(i, j):
    """The named-POI label for a sector, or '' if it's procedural."""
    poi = UNIVERSE_POIS.get((int(i), int(j)))
    return poi[0] if poi else ""


def universe_sector_kind(seed, i, j, danger="Quiet"):
    """The deterministic kind of any sector (pure - does not spawn anything).

    Named POIs win; (0,0) is always home; otherwise a keyed roll against the
    Danger thresholds. Both the generator and the galaxy map call this, so what
    you see on the map is exactly what spawns when you arrive.
    """
    i = int(i)
    j = int(j)
    poi = UNIVERSE_POIS.get((i, j))
    if poi:
        return poi[1]
    if i == 0 and j == 0:
        return "home"
    roll = scatter.cell_roll(seed, 1, i, j, 7)
    t_station, t_enemy, t_nebula, t_anomaly = 0.15, 0.15, 0.12, 0.08
    if danger == "Balanced":
        t_station, t_enemy, t_nebula, t_anomaly = 0.20, 0.25, 0.15, 0.10
    elif danger == "Dangerous":
        t_station, t_enemy, t_nebula, t_anomaly = 0.15, 0.40, 0.15, 0.10
    if roll < t_station:
        return "station"
    if roll < t_station + t_enemy:
        return "enemy"
    if roll < t_station + t_enemy + t_nebula:
        return "nebula"
    if roll < t_station + t_enemy + t_nebula + t_anomaly:
        return "anomaly"
    return "empty"


def universe_map_cell_text(seed, i, j, danger, sectors, reveal):
    """Short label for a galaxy-map cell.

    Named POIs always show; otherwise unvisited sectors read '?' under fog of
    war ("Full Chart" reveals everything, since it's all deterministic).
    """
    name = universe_sector_name(i, j)
    if name:
        return name
    if reveal != "Full Chart" and not universe_sector_flag(sectors, i, j, "visited"):
        return "?"
    return _KIND_ABBR.get(universe_sector_kind(seed, i, j, danger), ".")
