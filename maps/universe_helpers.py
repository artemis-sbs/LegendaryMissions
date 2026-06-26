"""Helpers for the Open Universe map (maps/universe.mast).

A sector's contents are a pure function of (universe_seed, i, j): only the
current sector is instantiated, always around the origin, and a jump clears it
and regenerates the neighbour. So the whole universe is "stored" in its seed
plus the current coordinates (persistence of player-made changes comes later).
"""
import math

from sbs_utils import scatter
from sbs_utils.vec import Vec3
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
