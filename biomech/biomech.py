"""BioMech behavior for LegendaryMissions - reusable by any mission that loads this
addon (not siege-specific).

Cosmos has no built-in BioMech AI, so the lifecycle is scripted here. The four
shipData stages biomech_a..d (art Drone1..4, escalating shields) ARE the growth
ladder, so "evolving" is just swapping art_id and the stats/appearance follow
shipData - no extra per-ship state to track. Pair with prefab_biomech (spawn) and
the biomech_infestation driver in biomech.mast.
"""
import random
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.query import to_object_list

BIOMECH_STAGE_ARTS = ["biomech_a", "biomech_b", "biomech_c", "biomech_d"]


def biomech_count():
    """Number of live BioMechs (role 'biomech')."""
    return len(role("biomech"))


def biomech_evolve():
    """Evolve one random pre-Stage-4 BioMech to the next stage: swap its art_id so its
    shields/appearance follow shipData (the Cosmos stand-in for the 2.x asteroid-eating
    growth). The art IS the stage. Returns the evolved id, or 0 if all are Stage 4."""
    growable = []
    for o in to_object_list(role("biomech")):
        try:
            idx = BIOMECH_STAGE_ARTS.index(o.art_id)
        except ValueError:
            idx = 0
        if idx < len(BIOMECH_STAGE_ARTS) - 1:
            growable.append((o, idx))
    if not growable:
        return 0
    o, idx = random.choice(growable)
    o.art_id = BIOMECH_STAGE_ARTS[idx + 1]
    return o.id


def biomech_has_stage4():
    """True once at least one BioMech has matured to Stage 4 (biomech_d) - the stage
    that reproduces in the lore."""
    for o in to_object_list(role("biomech")):
        if o.art_id == BIOMECH_STAGE_ARTS[-1]:
            return True
    return False
