# pickup_spawn / terrain_spawn_pickups moved to the items addon
# (items/items.py) as registry-driven, tier-weighted spawners. They remain
# available under the same names (shims there), so existing callers are
# unaffected. The legacy anomaly metadata is kept for any external readers.
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value


anom_data = {
    "carapaction_coil": {"art_id":"alien_2b", "name":"Carapaction Coil"},
    "infusion_pcoils": {"art_id":"alien_4b", "name":"Infusion PCoil"},
    "tauron_focuser": {"art_id":"alien_4a", "name": "Tauron Focuser"},
    "secret_codecase": {"art_id":"container_1a", "name": "Secret Code Case"},
    "hidens_powercell": {"art_id":"container_2b", "name": "HiDens Power Cell"},
    "vigoranium_nodule": {"art_id":"container_2c", "name": "Vigoranium Nodule"},
    "cetrocite_crystal": {"art_id":"container_3c", "name": "Cetrocite Crystal"},
    "lateral_array": {"art_id":"alien_3c", "name": "Lateral Array"},
    "haplix_overcharger": {"art_id":"alien_5c", "name": "Haplix Overcharger"},
    "escape-pod": {"art_id":"escape-pod", "name": "Escape Pod"}
}


def get_anom_data():
    """
    Gets the anom_data dictionary contents (legacy). The discoverable registry
    in the items addon (items_get_list) is the source of truth going forward.
    """
    return anom_data
