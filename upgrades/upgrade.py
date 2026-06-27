# pickup_spawn / terrain_spawn_pickups moved to the items addon
# (items/items.py) as registry-driven, tier-weighted spawners. They remain
# available under the same names (shims there), so existing callers are
# unaffected. The legacy anomaly metadata is kept for any external readers.
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.comms import comms_broadcast


anom_data = {
    "carapaction_coil": {"art_id":"alien_2a", "name":"Carapaction Coil"},
    "infusion_pcoils": {"art_id":"danger_4a", "name":"Infusion PCoil"},
    "tauron_focuser": {"art_id":"alien_4a", "name": "Tauron Focuser"},
    "secret_codecase": {"art_id":"container_1a", "name": "Secret Code Case"},
    "hidens_powercell": {"art_id":"container_2a", "name": "HiDens Power Cell"},
    "vigoranium_nodule": {"art_id":"container_4a", "name": "Vigoranium Nodule"},
    "cetrocite_crystal": {"art_id":"container_small_6a", "name": "Cetrocite Crystal"},
    "lateral_array": {"art_id":"danger_5a", "name": "Lateral Array"},
    "haplix_overcharger": {"art_id":"alien_5a", "name": "Haplix Overcharger"},
    "escape-pod": {"art_id":"escape-pod", "name": "Escape Pod"}
}


def transfer_upgrades_of_type(giver_id, reciever_id, upgrade):
    """
    Transfer all upgrades of the specified type from one object to another.
    Args:
        giver_id (int): The ID of the object that has up the upgrades.
        reciever_id (int): The ID of the object that is recieving the upgrades
        upgrade (str): The name of the upgrades, e.g. carapaction_coil
    Return
        boolean: True if an upgrade is successfully transfered, otherwise False
    """
    if to_object(giver_id) is None:
        return False
    if to_object(reciever_id) is None:
        return False
    craft_count = get_inventory_value(giver_id, upgrade, 0)
    if not craft_count:
        return False
    if craft_count == 0:
        return False
    hangar_count = get_inventory_value(reciever_id, upgrade, 0)
    comms_broadcast(0, "{upgrade} in ship: {craft_count}")
    set_inventory_value(reciever_id, upgrade, craft_count + hangar_count)
    set_inventory_value(giver_id, upgrade, 0)
    return True


def get_anom_data():
    """
    Gets the anom_data dictionary contents (legacy). The discoverable registry
    in the items addon (items_get_list) is the source of truth going forward.
    """
    return anom_data
