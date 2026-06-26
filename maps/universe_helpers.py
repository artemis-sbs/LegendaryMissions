"""Helpers for the Open Universe map (maps/universe.mast).

A sector's contents are a pure function of (universe_seed, i, j): only the
current sector is instantiated, always around the origin, and a jump clears it
and regenerates the neighbour. So the whole universe is "stored" in its seed
plus the current coordinates (persistence of player-made changes comes later).
"""
import math
import os

from sbs_utils import scatter
from sbs_utils.vec import Vec3
from sbs_utils.fs import get_mission_dir, save_yaml_data, load_yaml_data
from sbs_utils.procedural.terrain import terrain_spawn_field_keyed
from sbs_utils.procedural.space_objects import delete_objects_box
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.query import to_object_list

# Half-extent of a sector's playable area (world units).
UNIVERSE_SECTOR_R = 50_000


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


def universe_save(seed, i, j, sectors):
    """Persist the universe seed, current sector, and the sparse delta map."""
    save_yaml_data(universe_save_path(),
                   {"universe_seed": seed, "current_sector": [i, j], "sectors": sectors})


def universe_load():
    """Load the saved universe, or None if there is no valid save."""
    data = load_yaml_data(universe_save_path())
    return data if isinstance(data, dict) else None


def universe_sector_flag(sectors, i, j, flag):
    """True if a per-sector delta flag (e.g. station_destroyed) is set."""
    if not isinstance(sectors, dict):
        return False
    s = sectors.get(f"{i},{j}")
    return bool(s.get(flag)) if isinstance(s, dict) else False


def universe_set_sector_flag(sectors, i, j, flag, value=True):
    """Set a per-sector delta flag; returns the (possibly new) sectors dict."""
    if not isinstance(sectors, dict):
        sectors = {}
    k = f"{i},{j}"
    s = sectors.get(k)
    if not isinstance(s, dict):
        s = {}
    s[flag] = value
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
