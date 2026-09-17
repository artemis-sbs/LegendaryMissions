"""Orbit renders of the suit.  blender.exe -b <blend> --python render_suit.py -- --out <dir>"""
import bpy, sys, os, math
from mathutils import Vector

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGV[ARGV.index("--out") + 1] if "--out" in ARGV else "."
TAG = ARGV[ARGV.index("--tag") + 1] if "--tag" in ARGV else "view"
os.makedirs(OUT, exist_ok=True)

obj = bpy.data.objects["crew_exosuit_seated"]
bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
ctr = (lo + hi) * 0.5
span = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)

scn = bpy.context.scene
try:
    scn.render.engine = 'BLENDER_WORKBENCH'
except Exception as ex:
    print("workbench unavailable", ex)
sh = scn.display.shading
sh.light = 'STUDIO'
sh.color_type = 'MATERIAL'
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.show_object_outline = False
scn.display.render_aa = '16'
scn.render.resolution_x = 700
scn.render.resolution_y = 900
scn.render.film_transparent = False
scn.world = bpy.data.worlds.new("w") if scn.world is None else scn.world
scn.world.color = (0.09, 0.10, 0.12)

cam_data = bpy.data.cameras.new("cam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = span * 1.32
cam = bpy.data.objects.new("cam", cam_data)
scn.collection.objects.link(cam)
scn.camera = cam

# (label, azimuth degrees measured from +Y = facing, elevation degrees)
VIEWS = [
    ("front", 0, 6),
    ("q34", 38, 10),
    ("side", 90, 4),
    ("back", 180, 8),
    ("top34", 45, 42),
]
for name, az, el in VIEWS:
    a = math.radians(az)
    e = math.radians(el)
    d = span * 3.0
    pos = ctr + Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))) * d
    cam.location = pos
    look = (ctr - pos).normalized()
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    scn.render.filepath = os.path.join(OUT, "%s_%s.png" % (TAG, name))
    bpy.ops.render.render(write_still=True)
    print("[render]", scn.render.filepath)
