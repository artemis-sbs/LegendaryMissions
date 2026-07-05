"""BioMech behavior for LegendaryMissions - reusable by any mission that loads this
addon (not siege-specific).

Cosmos has no built-in BioMech AI, so the lifecycle AND the disposition are scripted
here, modelling the Artemis 2.x BioMech:

  * Stages 1-3 are PASSIVE and NEUTRAL. They live on a neutral side no one is hostile
    to, so players will not auto-engage them; they avoid combat and drift toward
    asteroids to feed (ai_biomech_feed) and do not shoot.
  * COLLECTIVE MIND. Attacking any BioMech wakes the hive - but BOUNDED to an aggro
    radius (an area effect), not the whole sector. biomech_enrage() flips the nearby
    hulls to enraged, points them at the attacker, and switches each PER-OBJECT to a
    hostile side (so only the woken hulls turn hostile); ai_biomech_hunt then chases and
    fires. biomech_calm() reverses it. (The engine broad_test is capped at ~5000u, so
    the bound is a plain distance check, which also lets it exceed that cap and be
    unit-tested.)
  * Stage 4 is sentient - a comms route (biomech_brains.mast) lets a ship hail a Stage-4
    hull to calm (biomech_calm) or taunt (biomech_enrage) the hive.

GROWTH LADDER (evolve by RESPAWN). The four shipData keys biomech_a..d (art Drone1..4)
are FULL ship templates with escalating shields / hull / speed / roles. A hull's stats
come from the engine reading its shipData key at *spawn* time, so "evolving" is NOT an
art_id swap (that changes only the 3D model, keeping the earlier stage's baked-in
stats). biomech_evolve() respawns a fresh next-stage hull at the old hull's position and
deletes the old one, so every BioMech carries the complete state of its stage.

One spawn path (biomech_spawn) is shared by prefab_biomech and biomech_evolve. Pair with
the biomech_infestation driver in biomech.mast and the brains in biomech_brains.mast.
"""
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.procedural.query import to_id, to_object, to_object_list
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.brain import brain_add
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.space_objects import delete_object
from sbs_utils.procedural.sides import side_set_object_side, side_keys_set

# The growth ladder: each key is a distinct shipData template (escalating stats).
BIOMECH_STAGE_ARTS = ["biomech_a", "biomech_b", "biomech_c", "biomech_d"]

# How far the collective mind reaches: attacking one hull wakes BioMechs within this
# radius (an area effect), not every BioMech in the sector. Tune per mission.
BIOMECH_AGGRO_RADIUS = 9000.0

# NEUTRAL UNTIL ENRAGED (per-object, so it stays bounded to the woken hive).
# BioMechs live on a neutral side (BIOMECH_PASSIVE_SIDE) that no one is hostile to, so a
# passive hull reads neutral and players will not auto-engage it. When a hull is roused,
# it switches PER-OBJECT to a registered hostile side (BIOMECH_ENRAGED_SIDE) - so only
# the woken hulls turn hostile, not the whole colony. Calming switches it back. The side
# switch is a no-op (guarded) if BIOMECH_ENRAGED_SIDE is not a registered side; the
# brain's force_shoot still makes an enraged hull fire regardless. Set BIOMECH_ENRAGED_SIDE
# to whatever hostile side the mission has registered (siege has 'raider').
BIOMECH_PASSIVE_SIDE = "biomech"
BIOMECH_ENRAGED_SIDE = "raider"


def _biomech_side_registered(side_key):
    """True if `side_key` is a registered side. Quiet (side_keys_set doesn't warn, unlike
    to_side_id, which prints 'Side not found' on a miss)."""
    if not side_key:
        return False
    key = side_key.strip().lower()
    return any(str(k).strip().lower() == key for k in side_keys_set())


def _biomech_set_side(obj_id, side_key):
    """Switch a hull's side, but only if `side_key` is a registered side (else no-op, so
    a mission that hasn't set up the side just falls back to brain-driven aggression)."""
    if _biomech_side_registered(side_key):
        side_set_object_side(obj_id, side_key)

# The BioMech brain: a Select of [hunt, feed]. hunt succeeds only while enraged (so an
# enraged hull chases + fires); otherwise it declines and the passive feed brain runs.
# Both labels live in biomech_brains.mast; metadata supplies throttle/stop_dist.
BIOMECH_BRAIN = ["ai_biomech_hunt", "ai_biomech_feed"]


def biomech_spawn(x, y, z, art="biomech_a", roles="biomech, raider", name="BioMech"):
    """THE single BioMech spawn path. Spawn one hull of the given stage `art` with the
    shared passive/hunt brain, so every BioMech gets the full shipData stats for its
    stage and starts PASSIVE. Remembers its `roles` so an evolve can respawn with the
    same roles. Returns the id."""
    obj = npc_spawn(x, y, z, name, roles, art, "behav_npcship")
    bid = to_id(obj)
    set_inventory_value(bid, "biomech:roles", roles)
    set_inventory_value(bid, "biomech:enraged", 0)     # passive until provoked
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


def biomech_enrage(hit_id, attacker_id=0, radius=None):
    """Collective mind, BOUNDED: wake every BioMech within `radius` of the hit hull and
    point them at `attacker_id`. This is the area effect - poking one hull rouses the
    nearby hive, not the whole sector. Returns how many hulls woke.

    Called from the //damage/object route (a player hit a BioMech) and from the Stage-4
    taunt comms."""
    if radius is None:
        radius = BIOMECH_AGGRO_RADIUS
    hit = to_object(hit_id)
    if hit is None:
        return 0
    hp = hit.pos
    r2 = radius * radius
    aid = to_id(attacker_id) if attacker_id else 0
    woke = 0
    for o in to_object_list(role("biomech")):
        d = o.pos - hp
        if d.dot(d) <= r2:
            set_inventory_value(o.id, "biomech:enraged", 1)
            if aid:
                set_inventory_value(o.id, "biomech:target", aid)
            _biomech_set_side(o.id, BIOMECH_ENRAGED_SIDE)   # neutral -> hostile (this hull)
            woke += 1
    return woke


def biomech_calm(center_id=None, radius=None):
    """Soothe the hive back to passive: clear enraged (and the remembered target) for
    every BioMech - or, if `center_id` is given, only those within `radius` of it.
    Returns how many hulls calmed. Used by the Stage-4 calm comms."""
    if center_id is None:
        targets = to_object_list(role("biomech"))
    else:
        if radius is None:
            radius = BIOMECH_AGGRO_RADIUS
        c = to_object(center_id)
        if c is None:
            return 0
        cp = c.pos
        r2 = radius * radius
        targets = [o for o in to_object_list(role("biomech")) if (o.pos - cp).dot(o.pos - cp) <= r2]
    n = 0
    for o in targets:
        set_inventory_value(o.id, "biomech:enraged", 0)
        set_inventory_value(o.id, "biomech:target", 0)
        _biomech_set_side(o.id, BIOMECH_PASSIVE_SIDE)       # hostile -> neutral (this hull)
        n += 1
    return n


def biomech_evolve():
    """Evolve one random pre-Stage-4 BioMech by RESPAWNING it at the next stage: spawn a
    fresh hull from the next shipData key (full stage stats - shields/hull/speed/roles)
    at the old hull's position, then delete the old hull. Carries the old hull's enraged
    state forward. Returns the new BioMech id, or 0 if every BioMech is already Stage 4.

    Respawn (not an art_id swap) is what actually promotes the stats: the engine only
    derives a hull's stats from its shipData key when the hull is created."""
    import random
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
    enraged = get_inventory_value(old.id, "biomech:enraged", 0)
    tgt = get_inventory_value(old.id, "biomech:target", 0)
    new_id = biomech_spawn(pos.x, pos.y, pos.z, BIOMECH_STAGE_ARTS[idx + 1], roles)
    if enraged:
        set_inventory_value(new_id, "biomech:enraged", 1)
        set_inventory_value(new_id, "biomech:target", tgt)
        _biomech_set_side(new_id, BIOMECH_ENRAGED_SIDE)     # stay hostile across the respawn
    delete_object(old.id)
    return new_id


def biomech_has_stage4():
    """True once at least one BioMech has matured to Stage 4 (biomech_d) - the stage
    that reproduces in the lore and can be hailed."""
    for o in to_object_list(role("biomech")):
        if o.art_id == BIOMECH_STAGE_ARTS[-1]:
            return True
    return False
