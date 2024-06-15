from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.procedural.space_objects import clear_target

def typhon_classic_spawn(x,y,z):
    monster = npc_spawn(x,y,z,"ZZ", "monster,typhon,classic", "-", "behav_typhon")
    monster.engine_object.exclusion_radius = 200

    monster.blob.set("body_1_color", "purple", 0)
    monster.blob.set("body_2_color", "purple", 0)
    monster.blob.set("body_1_diffuse_bitmap_file", "drone_diffuse", 0)
    monster.blob.set("body_2_diffuse_bitmap_file", "drone_diffuse", 0)

    monster.blob.set("particle_color_1", "purple", 0)
    monster.blob.set("particle_color_2", "purple", 0)
    monster.blob.set("particle_color_3", "purple", 0)
    monster.blob.set("beamColor", "yellow",0)
    clear_target(monster.id)
    return monster

