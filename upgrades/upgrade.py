from sbs_utils.procedural.spawn import terrain_spawn
from sbs_utils import scatter
from sbs_utils.vec import Vec3
import random


anom_data = {
    "carapaction_coil": {"art_id":"alien_2a"},
    "infusion_pcoils": {"art_id":"danger_4a"},
    "tauron_focuser": {"art_id":"alien_4a"},
    "secret_codecase": {"art_id":"container_1a"},
    "hidens_powercell": {"art_id":"container_2a"},
    "vigoranium_nodule": {"art_id":"container_4a"},
    "cetrocite_crystal": {"art_id":"container_small_6a"},
    "lateral_array": {"art_id":"danger_5a"},
    "haplix_overcharger": {"art_id":"alien_5a"},
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


def terrain_spawn_pickups(upgrade_value, center=None):
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
