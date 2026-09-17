"""Render the SHIPPED .obj + _diffuse.png, not the working blend - so what gets
checked is the artifact the engine would load."""
import bpy, sys, os, math
from mathutils import Vector
ARGV=sys.argv[sys.argv.index("--")+1:]
SRC=ARGV[ARGV.index("--obj")+1]; OUT=ARGV[ARGV.index("--out")+1]
os.makedirs(OUT,exist_ok=True)
bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
bpy.ops.wm.obj_import(filepath=SRC, forward_axis='NEGATIVE_Z', up_axis='Y')
o=bpy.context.selected_objects[0]
tex_path=os.path.splitext(SRC)[0]+"_diffuse.png"
m=bpy.data.materials.new("art"); m.use_nodes=True
nt=m.node_tree; b=nt.nodes["Principled BSDF"]
t=nt.nodes.new("ShaderNodeTexImage"); t.image=bpy.data.images.load(tex_path)
t.interpolation='Closest'; nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
nt.nodes.active=t
o.data.materials.clear(); o.data.materials.append(m)
bpy.ops.object.shade_flat()
bb=[o.matrix_world @ Vector(c) for c in o.bound_box]
lo=Vector((min(v.x for v in bb),min(v.y for v in bb),min(v.z for v in bb)))
hi=Vector((max(v.x for v in bb),max(v.y for v in bb),max(v.z for v in bb)))
ctr=(lo+hi)*0.5; span=max(hi.x-lo.x,hi.y-lo.y,hi.z-lo.z)
print("[verify] imported size %.3f x %.3f x %.3f  tris=%d"
      % (hi.x-lo.x,hi.y-lo.y,hi.z-lo.z, sum(len(p.vertices)-2 for p in o.data.polygons)))
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
sh=scn.display.shading; sh.light='STUDIO'; sh.color_type='TEXTURE'
sh.show_cavity=True; sh.cavity_type='BOTH'; sh.show_object_outline=False
scn.display.render_aa='16'
scn.render.resolution_x=600; scn.render.resolution_y=760
if scn.world is None: scn.world=bpy.data.worlds.new("w")
scn.world.color=(0.10,0.11,0.13)
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=span*1.32
cam=bpy.data.objects.new("c",cd); scn.collection.objects.link(cam); scn.camera=cam
for name,(az,el) in {"art_front":(0,6),"art_q34":(38,12),"art_side":(90,4)}.items():
    a=math.radians(az); e=math.radians(el)
    pos=ctr+Vector((math.sin(a)*math.cos(e),math.cos(a)*math.cos(e),math.sin(e)))*span*3
    cam.location=pos
    cam.rotation_euler=(ctr-pos).normalized().to_track_quat('-Z','Y').to_euler()
    scn.render.filepath=os.path.join(OUT,name+".png")
    bpy.ops.render.render(write_still=True)
print("[verify] ok")
