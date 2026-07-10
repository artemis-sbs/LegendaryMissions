from sbs_utils.procedural.execution import get_shared_variable
from sbs_utils.procedural.query import to_space_object
import random


def get_defender_name(side="tsn", allow_canuck=True):
    if side == "terran":
        side = "tsn"

    shipname_data = get_shared_variable("SHIP_NAME_DATA")
    if shipname_data is None:
        return "SHIP DATA FAILED"

    tsnname_list = shipname_data.get(side)
    canuck_list = shipname_data.get("canadian")

    name = f"TSN {tsnname_list.pop(random.randrange(len(tsnname_list)))}"
    if allow_canuck and random.randint(1,1867) == 1867: ### This is an inside joke for our Canadian players. 
        name = f"TSN {canuck_list.pop(random.randrange(len(canuck_list)))}"

    return name

MONSTER_AGE_STAGES = ("young", "mature", "ancient")


def monster_roll_age(ages):
    """Roll a monster life stage from a prefab's `ages:` metadata block.

    `ages` is a dict:
        { "weights": [y, m, a] | None,
          "young":  {"health": int, "scale": float, "label": "Young"},
          "mature": {...}, "ancient": {...} }

    Missing stages fall back to whatever stage is present (so a species can declare a
    single flat stage and still report an age on science). Returns (stage, cfg).
    """
    present = [s for s in MONSTER_AGE_STAGES if s in ages]
    if not present:
        # No age block at all - synthesize a flat "mature" from top-level health/scale.
        return "mature", {"health": ages.get("health", 5000),
                          "scale": ages.get("scale", 1.0),
                          "label": ages.get("label", "")}
    weights = ages.get("weights")
    if weights is not None:
        weights = [w for s, w in zip(MONSTER_AGE_STAGES, weights) if s in ages]
    stage = random.choices(present, weights=weights)[0]
    return stage, ages[stage]


def monster_bake_age(monster, cfg, base_exclusion=200):
    """Bake a rolled stage's cfg onto a freshly spawned monster: health, scale,
    exclusion radius. The stage ROLE is added at spawn time (in the roles CSV) and
    the name is resolved by the caller, so this only touches the physical stats."""
    health = cfg.get("health", 5000)
    scale = cfg.get("scale", 1.0)
    monster.blob.set("monster_health_max", health, 0)
    monster.blob.set("monster_health", health, 0)
    monster.blob.set("local_scale_coeff", scale, 0)
    monster.engine_object.exclusion_radius = int(base_exclusion * scale)


def get_location_text(t, tp, defa):
    t = to_space_object(t) 
    if t is not None:
        return t.name
    if tp is not None:
        z = chr(64 + int(tp.z // 20000 + 13) % 26)
        x = int(tp.x // 20000 + 12) % 100

        return f"grid {z}{x:02d}"
        
    return defa



