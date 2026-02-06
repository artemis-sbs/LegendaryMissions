import random
from sbs_utils.procedural.execution import get_shared_variable, labels_get_type
from sbs_utils.procedural.query import to_space_object

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

