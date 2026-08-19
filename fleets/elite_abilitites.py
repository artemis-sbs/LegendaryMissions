import random
from sbs_utils.procedural.execution import get_shared_variable, labels_get_type
from sbs_utils.procedural.query import object_exists, to_space_object
from sbs_utils.helpers import FrameContext

engine_abilities = {
        # Blob flags (Always On)
        "elite_low_vis": "LowVis",
        "elite_main_scn_invis": "Invs",
        "elite_drone_launcher": "Drones",
        "elite_anti_mine": "AntiMine",
        "elite_anti_torpedo": "AntiTorp"
}

abilities = {}

all_abilities = abilities | engine_abilities


def elite_build_abilities():
    """Rebuild abilities based off labels

    """
    global all_abilities, abilities
    abilities = {}
    labels = labels_get_type("elite/")
    for l in labels:
        display_name = l.get_inventory_value("display_name", None)
        r = l.get_inventory_value("type",None)
        if r is None or display_name is None:
            print(f"Elite Label missing meta data {l.name}")
        abilities[r] = l

    all_abilities = abilities | engine_abilities




def elite_is_engine_ability(ab):
    return ab in engine_abilities.keys()

def elite_get_non_engine():
    script_abilities = get_shared_variable("elite_script_abilities", {})
    return abilities | script_abilities

def elite_get_all_abilities():
    script_abilities = get_shared_variable("elite_script_abilities", {})
    return all_abilities | script_abilities

def elite_get_abilities_scan(id_or_obj):
    ship_obj = to_space_object(id_or_obj)
    if ship_obj is None:
        return ""
    abi = []
    roles = ship_obj.get_roles()
    for role in roles:
        ab = all_abilities.get(role, None)
        if ab is None:
            continue
        # Support Engine abilities for now
        if isinstance(ab, str):
            abi.append(ab)
        else:
            display_name = ab.get_inventory_value("display_name", None)
            abi.append(display_name)

    return ",".join(abi)

#all_bits = [2**x for x in range(len(all_abilities))]
# Adding extra for script created elite
all_bits = [2**x for x in range(32)]
def random_bits(bits, count):
    bits = min(bits, len(all_bits))
    pick = list(all_bits[:bits])
    ret = 0
    random.shuffle(pick)
    p = pick[:count]
    for b in p:
        ret |= b
        
    return ret



#
# Elite tractor snare
#
# The engine tether is not a rope: a connection left attached pulls its target all the
# way into the source hull no matter what pull_distance says (measured in the grav_tether
# data harness, 1500 -> ~165). The first cut of the ability handed the engine the capture
# distance and walked away, so every catch ended up sitting inside the elite - which is
# what made the tether particle look wrong, since it was drawing between two overlapping
# hulls. So the beam is driven per tick instead: pull hard while the catch is outside the
# standoff, cut the moment it is inside. It still cannot run, and it stays a ship's length
# or two away where the effect reads.
#

#: Clear space the beam parks its catch in, ON TOP of both hulls, so this is the gap
#: between the two ships rather than between their centers.
ELITE_TRACTOR_STANDOFF = 500.0

#: The connection's ``.offset`` is the engine's pull rate: 0 locks the target to the
#: source instantly, higher is springier. 1.0 is a hard haul that still takes a beat, so
#: a ship caught at 2500 is visibly dragged in rather than teleported.
ELITE_TRACTOR_STIFFNESS = 1.0


def _elite_hull_radius(id_or_obj):
    """Physics radius of a hull, 0 if it cannot be read. A ship is a hull, not a dot -
    holding two centers 500 apart is not the same as holding two ships 500 apart."""
    obj = to_space_object(id_or_obj)
    if obj is None:
        return 0.0
    try:
        return float(obj.engine_object.exclusion_radius) or 0.0
    except Exception:
        return 0.0


def elite_tractor_hold_distance(elite_id, target_id):
    """Center-to-center distance the beam holds its catch at."""
    return (ELITE_TRACTOR_STANDOFF + _elite_hull_radius(elite_id)
            + _elite_hull_radius(target_id))


def elite_tractor_pull(elite_id, target_id, hold):
    """One tick of the snare. Returns False once there is nothing left to hold (either
    ship gone), so the caller can drop the beam and move on."""
    if not object_exists(elite_id) or not object_exists(target_id):
        return False
    sim = FrameContext.sim
    sbs = FrameContext.context.sbs
    if sbs.distance_id(elite_id, target_id) > hold:
        con = sim.GetTractorConnection(elite_id, target_id)
        if con is None:
            con = sim.AddTractorConnection(elite_id, target_id, sbs.vec3(0, 0, 0), hold)
        if con is not None:
            con.offset = ELITE_TRACTOR_STIFFNESS
    else:
        sim.DeleteTractorConnection(elite_id, target_id)
    return True


def elite_tractor_release(elite_id, target_id, emittor_id=None):
    """Drop the beam and its particle. Safe when either ship is already gone."""
    sim = FrameContext.sim
    sbs = FrameContext.context.sbs
    try:
        sim.DeleteTractorConnection(elite_id, target_id)
    except Exception:
        pass
    if emittor_id is not None:
        try:
            sbs.delete_particle_emittor(emittor_id)
        except Exception:
            pass
