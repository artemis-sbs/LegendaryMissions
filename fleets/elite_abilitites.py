import random
from sbs_utils.procedural.brain import brain_add
from sbs_utils.procedural.execution import get_shared_variable, labels_get_type, log
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import object_exists, to_space_object
from sbs_utils.procedural.signal import signal_emit
from sbs_utils.procedural.timers import clear_timer, set_timer
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

#
# How long an ability takes to charge, and how long before it can be picked again
#
# Both numbers are AUTHORED ON THE ABILITY, in its label metadata (`warm_up:` /
# `cool_down:`, seconds), and scaled here by how good the crew opposite is. An ability
# with no `warm_up:` charges instantly, which is what every ability outside cloak /
# warp / the two teleports should do - and what a mission's own ability injected through
# `elite_script_abilities` keeps doing without changing a line.
#

#: The DIFFICULTY at which an authored baseline plays exactly as authored.
ELITE_LEVEL_MID = 6

#: How much each level away from mid is worth. Low difficulty buys the science officer
#: more warning; high difficulty takes it away.
ELITE_LEVEL_STEP = 0.08

#: However short the scaling wants to make it, a tell nobody can read is not a tell.
ELITE_TIME_MIN = 3.0


def elite_level_for(elite_id=None, ability=None):
    """The skill level an elite's timings scale against.

    Today that is DIFFICULTY for every ship. The per-ability inventory override is read
    FIRST and nothing writes it - it is the seam a per-ability tech level plugs into
    later (LM #270 asks for one, and neither tech levels nor the game mode that would
    set them exist yet), so that feature becomes a writer rather than a rework.
    """
    if elite_id is not None and ability is not None:
        level = get_inventory_value(elite_id, f"{ability}_tech_level", None)
        if level is not None:
            return float(level)
    level = get_shared_variable("DIFFICULTY", ELITE_LEVEL_MID)
    if level is None:
        level = ELITE_LEVEL_MID
    return float(level)


def elite_scale_time(base_seconds, level=None):
    """An authored baseline, scaled for one crew.

    Multiplicative rather than the flat `100 - 5 * difficulty` the ticket suggests, so
    one knob holds for a 25-second cloak and a 10-second cooldown alike, and so an
    ability that wants to be quick stays quick at every difficulty.
    """
    if not base_seconds:
        return 0.0
    if level is None:
        level = ELITE_LEVEL_MID
    scaled = float(base_seconds) * (1.0 + (ELITE_LEVEL_MID - float(level)) * ELITE_LEVEL_STEP)
    return max(ELITE_TIME_MIN, scaled)


def elite_ability_label(ability):
    """The label behind an ability key, or None for an engine ability (which is a
    display-name string, not a label, and has no metadata to read)."""
    label = elite_get_all_abilities().get(ability, None)
    if label is None or isinstance(label, str):
        return None
    return label


def elite_ability_meta(ability, key, default=None):
    """One metadata field off an ability's label."""
    label = elite_ability_label(ability)
    if label is None:
        return default
    return label.get_inventory_value(key, default)


def elite_ability_warm_up(elite_id, ability):
    """Seconds this elite spends visibly charging `ability` before it fires. 0 when the
    ability declares no `warm_up:` - the ability then behaves exactly as it always has."""
    return elite_scale_time(elite_ability_meta(ability, "warm_up", 0),
                            elite_level_for(elite_id, ability))


def elite_ability_cool_down(elite_id, ability):
    """Seconds before this elite may pick `ability` again."""
    return elite_scale_time(elite_ability_meta(ability, "cool_down", 0),
                            elite_level_for(elite_id, ability))


def elite_ability_warm_up_text(ability):
    """What Science reads while the ability charges."""
    text = elite_ability_meta(ability, "warm_up_text", None)
    if text:
        return str(text)
    display_name = elite_ability_meta(ability, "display_name", None)
    if display_name:
        return f"Preparing to use {display_name}"
    return "Preparing an elite ability"


#
# What Science is told, while it is true
#
# The tell is a CONTRACT OF TWO INVENTORY KEYS rather than a call into the science
# addon, so `fleets` and `science_scans` can be loaded in either order, or one without
# the other. The science side reads them; nothing here needs to know it exists.
#
ELITE_TELL_KEY = "science_status_tell"
ELITE_TELL_TIMER_KEY = "science_status_tell_timer"

#: The warm-up clock. One name, because an elite charges one ability at a time.
ELITE_WARMUP_TIMER = "elite_warmup"


def elite_charge_begin(elite_id, ability):
    """Commit to an ability and start charging it, in the open."""
    seconds = elite_ability_warm_up(elite_id, ability)
    if seconds <= 0:
        return 0.0
    set_timer(elite_id, ELITE_WARMUP_TIMER, seconds)
    log(f"{ability} charging for {round(seconds)}s", "elites")
    set_inventory_value(elite_id, ELITE_TELL_KEY, elite_ability_warm_up_text(ability))
    set_inventory_value(elite_id, ELITE_TELL_TIMER_KEY, ELITE_WARMUP_TIMER)
    signal_emit("science_status_dirty", {"STATUS_ID": elite_id})
    return seconds


def elite_charge_clear(elite_id):
    """The charge is spent - the ability just launched. Take the tell down.

    Every path out of a charge goes through here or through `elite_charge_abort`. A tell
    that outlived what it described is the defect this is here to prevent: the old
    per-ability loop wrote "Cloak was activated" and never wrote anything again, so an
    enemy that cloaked once read as cloaking for the rest of the mission.
    """
    clear_timer(elite_id, ELITE_WARMUP_TIMER)
    set_inventory_value(elite_id, ELITE_TELL_KEY, None)
    set_inventory_value(elite_id, ELITE_TELL_TIMER_KEY, None)
    signal_emit("science_status_dirty", {"STATUS_ID": elite_id})


def elite_status_set(elite_id, status):
    """Say something about this elite on the science status tab, with no countdown.

    The back-compat path for `elite_update_science_status`, and what an ability uses
    while it is RUNNING rather than charging (the tractor says it is holding someone).
    An empty status is a no-op, as it always was - an ability that wants its line taken
    down calls `elite_charge_clear`.
    """
    if elite_id is None or not status:
        return
    set_inventory_value(elite_id, ELITE_TELL_KEY, str(status))
    set_inventory_value(elite_id, ELITE_TELL_TIMER_KEY, None)
    signal_emit("science_status_dirty", {"STATUS_ID": elite_id})


def elite_charge_abort(elite_id):
    """The charge was called off - suppressed, or nothing left to use it on. Forget the
    pending ability as well as the tell, so the next opening is chosen fresh."""
    pending = get_inventory_value(elite_id, "ELITE_PENDING_ABILITY", None)
    if pending is None and get_inventory_value(elite_id, ELITE_TELL_KEY, None) is None:
        return
    set_inventory_value(elite_id, "ELITE_PENDING_ABILITY", None)
    elite_charge_clear(elite_id)


#
# Attaching the ability tree
#
ELITE_BRAIN_FLAG = "__ELITE_BRAIN__"


def elite_brain_attach(elite_id, brain_spec):
    """Attach the elite ability tree, once, as the FIRST thing the ship considers.

    Two things make this more than a `brain_add` call.

    FIRST, because the root of a brain is a Select and a Select stops at the first child
    that succeeds. An elite that already carries a movement brain - a siege boss chasing
    a player, say - would otherwise have an ability tree that never runs at all: no
    error, no ability, and nothing to see.

    ONCE on its own flag, because `brain_add` appends. The guard this replaces asked
    whether the ship had ANY brain, which meant exactly the ships above never got the
    tree; asking whether it has THIS tree lets both coexist without stacking duplicates
    each time the label is scheduled again (the GM add-ability button does that).
    """
    if elite_id is None:
        return False
    if get_inventory_value(elite_id, ELITE_BRAIN_FLAG, False):
        return False
    root = get_inventory_value(elite_id, "__BRAIN__", None)
    before = len(root.children) if root is not None else 0
    brain_add(elite_id, brain_spec, None, 0, None)
    root = get_inventory_value(elite_id, "__BRAIN__", None)
    if root is not None and before:
        added = root.children[before:]
        del root.children[before:]
        root.children[0:0] = added
    set_inventory_value(elite_id, ELITE_BRAIN_FLAG, True)
    return True


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
