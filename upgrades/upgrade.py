from sbs_utils.procedural.spawn import terrain_spawn
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils import scatter
from sbs_utils.vec import Vec3
import random


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


def pickup_spawn(x, y, z, roles, blink=None, yaw=None, name=None, art_id=None,):
    if blink is None:
        blink=random.randint(1,2)
    if yaw is None:
        yaw=random.uniform(0.03,0.08)
    if not roles.startswith("upgrade"):
        roles = "upgrade,"+roles
    # Surpress
    roles = "#,"+roles
    if art_id is None:
        art_id = "unknown"
        for anom in anom_data:
            if anom in roles:
                art_id = anom_data[anom]["art_id"]
                break

    sd = terrain_spawn(x, y, z, name, roles, art_id, "behav_pickup")
    sd.engine_object.steer_yaw = yaw
    sd.engine_object.blink_state = int(blink)


def terrain_spawn_pickups(upgrade_value, center=None, points=None):
    """
    Spawn pickups around the given position.
    Args:
        upgrade_value (int): The density of upgrades to spwan. Acceptable values are 1-4.
        center (Vec3): The point around which to spawn the upgrades. If None, turns into Vec3(0,0,0). Default is None.
        points iter: Optional is passed it will sample points 
    """
    if center is None:
        center = Vec3(0,0,0)

    num_upgrade = 0
    if upgrade_value==1:
        random.randint(1,3)
    elif upgrade_value==2:
        num_upgrade = random.randint(3,5)
    elif upgrade_value==3:
        num_upgrade = random.randint(5,10)
    elif upgrade_value==4:
        num_upgrade = random.randint(10,15)

    # TODO: I think that instead of using explicit numbers to represent each upgrade, we need a more extensible system.
    # So we should use something like this instead:
    # upg = random.randint(1, len(anom_data.values()))
    # for upg in anom_data.values()):
    #     pickup_spawn(v.x, v.y, v.z, anom_data[upg])
    if points is not None:
        try:
            spawn_points = random.sample(points, num_upgrade)
        except Exception:
            return

    spawn_points = scatter.box(num_upgrade, *center.xyz, 75000, 1000, 75000, centered=True)
    for v in spawn_points:
        upg = random.randint(1,9)
        if upg == 1:
            pickup_spawn(v.x, v.y, v.z, "carapaction_coil")

        if upg == 2:
            pickup_spawn(v.x, v.y, v.z,  "infusion_pcoils")

        if upg == 3:
            pickup_spawn(v.x, v.y, v.z, "tauron_focuser")

        if upg == 4:
            pickup_spawn(v.x, v.y, v.z, "secret_codecase")

        if upg == 5:
            pickup_spawn(v.x, v.y, v.z, "hidens_powercell")

        if upg == 6:
            pickup_spawn(v.x, v.y, v.z, "vigoranium_nodule")

        if upg == 7:
            pickup_spawn(v.x, v.y, v.z, "cetrocite_crystal")

        if upg == 8:
            pickup_spawn(v.x, v.y, v.z, "lateral_array")

        if upg == 9:
            pickup_spawn(v.x, v.y, v.z, "haplix_overcharger")

from sbs_utils.procedural.comms import comms_broadcast
def transfer_upgrades_of_type(giver_id, reciever_id, upgrade):
    """
    Transfer all upgrades of the specified type from one object to another.
    Args:
        giver_id (int): The ID of the object that has up the upgrades.
        hangar_id (int): The ID of the object that is recieving the upgrades
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
    print("{upgrade} in craft: {craft_count}")
    if craft_count == 0:
        return False
    hangar_count = get_inventory_value(reciever_id, upgrade, 0)
    comms_broadcast(0, "{upgrade} in ship: {craft_count}")
    set_inventory_value(reciever_id, upgrade, craft_count + hangar_count)
    set_inventory_value(giver_id, upgrade, 0)
    return True

def get_anom_data():
    """
    Gets a the anom_data dictionary contents.
    This contains the internal name of the upgrade as the key, and the art_id, and the name of the upgrade.
    """
    return anom_data
