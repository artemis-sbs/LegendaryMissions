import bpy, sys, os, math
from mathutils import Vector
ARGV=sys.argv[sys.argv.index("--")+1:]; OUT=ARGV[ARGV.index("--out")+1]
os.makedirs(OUT,exist_ok=True)
o=bpy.data.objects["crew_exosuit_seated"]
bb=[o.matrix_world @ Vector(c) for c in o.bound_box]
hi=max(v.z for v in bb)
ctr=Vector((0.0,-0.10,hi-0.17))
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
sh=scn.display.shading; sh.light='STUDIO'; sh.color_type='MATERIAL'
sh.show_cavity=True; sh.cavity_type='BOTH'; sh.show_object_outline=False
scn.display.render_aa='16'
scn.render.resolution_x=520; scn.render.resolution_y=520
if scn.world is None: scn.world=bpy.data.worlds.new("w")
scn.world.color=(0.10,0.11,0.13)
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=0.62
cam=bpy.data.objects.new("c",cd); scn.collection.objects.link(cam); scn.camera=cam
for name,(az,el) in {"head_front":(0,0),"head_q":(35,12),"head_up":(0,-25)}.items():
    a=math.radians(az); e=math.radians(el)
    pos=ctr+Vector((math.sin(a)*math.cos(e),math.cos(a)*math.cos(e),math.sin(e)))*2.0
    cam.location=pos
    cam.rotation_euler=(ctr-pos).normalized().to_track_quat('-Z','Y').to_euler()
    scn.render.filepath=os.path.join(OUT,name+".png")
    bpy.ops.render.render(write_still=True)
    print("[head]",name)
