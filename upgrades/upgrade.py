from sbs_utils.procedural.spawn import terrain_spawn
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
