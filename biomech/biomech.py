"""BioMech behavior for LegendaryMissions - reusable by any mission that loads this
addon (not siege-specific).

Cosmos has no built-in BioMech AI, so the lifecycle is scripted here.

GROWTH LADDER. The four shipData keys biomech_a..d (art Drone1..4) are FULL ship
templates with escalating shields / hull / speed / roles. A BioMech's stats come from
the engine reading its shipData key at *spawn* time (create_space_object bakes them
into the hull). So "evolving" is NOT swapping art_id on a live hull - that changes only
the 3D model and leaves the earlier stage's baked-in stats (a Stage-4-looking hull with
Stage-1 shields). Instead we EVOLVE BY RESPAWN: spawn a fresh hull from the next stage's
key at the old hull's position, then delete the old hull. Every BioMech - initial or
evolved - therefore carries the complete, correct state of its stage.

One spawn path (biomech_spawn) is shared by prefab_biomech and biomech_evolve, so the
stage art, roles, and brain are defined once. Pair with the biomech_infestation driver
in biomech.mast.
"""
import random
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.procedural.query import to_id, to_object_list
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.brain import brain_add
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.space_objects import delete_object

# The growth ladder: each key is a distinct shipData template (escalating stats).
BIOMECH_STAGE_ARTS = ["biomech_a", "biomech_b", "biomech_c", "biomech_d"]

# One definition of the BioMech brain, shared by every spawn (initial and evolved):
# a fast, aggressive chase (BioMechs out-run and out-turn ships), stations as fallback.
BIOMECH_BRAIN = [
    {"label": "ai_chase_player",  "data": {"force_shoot": True, "throttle": 2.8}},
    {"label": "ai_chase_station", "data": {"force_shoot": True, "throttle": 2.2}},
]


def biomech_spawn(x, y, z, art="biomech_a", roles="biomech, raider", name="BioMech"):
    """THE single BioMech spawn path. Spawn one hull of the given stage `art` with the
    shared chase brain, so every BioMech gets the full shipData stats for its stage.
    Remembers its `roles` so an evolve can respawn with the same roles. Returns the id."""
    obj = npc_spawn(x, y, z, name, roles, art, "behav_npcship")
    bid = to_id(obj)
    set_inventory_value(bid, "biomech:roles", roles)
    brain_add(bid, BIOMECH_BRAIN)
    return bid


def biomech_count():
    """Number of live BioMechs (role 'biomech')."""
    return len(role("biomech"))


def biomech_stage(obj):
    """Stage index 0..3 for a BioMech (by its shipData key); 0 if unrecognized."""
    try:
        return BIOMECH_STAGE_ARTS.index(obj.art_id)
    except ValueError:
        return 0


def biomech_evolve():
    """Evolve one random pre-Stage-4 BioMech by RESPAWNING it at the next stage: spawn a
    fresh hull from the next shipData key (full stage stats - shields/hull/speed/roles)
    at the old hull's position, then delete the old hull. Returns the new BioMech id, or
    0 if every BioMech is already Stage 4.

    Respawn (not an art_id swap) is what actually promotes the stats: the engine only
    derives a hull's stats from its shipData key when the hull is created."""
    growable = []
    for o in to_object_list(role("biomech")):
        idx = biomech_stage(o)
        if idx < len(BIOMECH_STAGE_ARTS) - 1:
            growable.append((o, idx))
    if not growable:
        return 0
    old, idx = random.choice(growable)
    pos = old.pos
    roles = get_inventory_value(old.id, "biomech:roles", "biomech, raider")
    new_id = biomech_spawn(pos.x, pos.y, pos.z, BIOMECH_STAGE_ARTS[idx + 1], roles)
    delete_object(old.id)
    return new_id


def biomech_has_stage4():
    """True once at least one BioMech has matured to Stage 4 (biomech_d) - the stage
    that reproduces in the lore."""
    for o in to_object_list(role("biomech")):
        if o.art_id == BIOMECH_STAGE_ARTS[-1]:
            return True
    return False
