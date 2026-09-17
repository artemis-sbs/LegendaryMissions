"""Close the EVA helmet with a glass bubble.

  blender.exe -b <blend> --python add_visor.py -- --out <dir>

The helmet opening is not a named feature of the mesh, but the tan liner ring that
borders it IS its own atlas colour (the `helmet_liner` material after retint), so
the ring's faces give the opening's centre, its outward normal and its radius.
Fit a spherical cap to that and the glass lands on the rim whatever the head is
doing - no hand-placed numbers to go stale when the pose changes.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector, Matrix

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGV[ARGV.index(name) + 1] if name in ARGV else default


OUT = arg("--out", os.path.dirname(__file__))
NAME = arg("--name", "crew_exosuit_seated")
BULGE = float(arg("--bulge", "1.00"))     # cap depth as a fraction of its radius
GROW = float(arg("--grow", "1.02"))       # radius scale relative to the rim
WRAP = float(arg("--wrap", "0.06"))       # how far past the equator the glass wraps
PUSH = float(arg("--push", "0.12"))       # shift along the look axis, + is forward
RIM_SLICE = float(arg("--rim-slice", "0.30"))   # leading fraction of the liner
# Smoked, not bright blue.  The glass ships as one cell of a palette texture whose
# ALPHA the engine may or may not honour on ship art (unverified), so pick a colour
# that reads as a tinted visor if it is ignored rather than as a teal bauble.
ALPHA = float(arg("--alpha", "0.34"))

obj = bpy.data.objects[NAME]
me = obj.data


def verts_of(mat_names):
    idx = {i for i, m in enumerate(me.materials) if m.name in mat_names}
    if not idx:
        raise SystemExit("no materials named %s - run retint.py first" % (mat_names,))
    vs = {v for p in me.polygons if p.material_index in idx for v in p.vertices}
    if not vs:
        raise SystemExit("no faces use %s" % (mat_names,))
    return [me.vertices[i].co.copy() for i in vs]


# Fit the bubble to the HEAD, not to the helmet's liner.  An earlier version
# averaged the liner ring's normal, but that ring is the interior BOWL - its
# faces mostly look upward, so the cap came out tilted 56 degrees and sliced
# across the face.  The head is unambiguous: its own centre, and a forward axis
# taken from where the face sits relative to it.
if "head_dir" not in obj:
    raise SystemExit("no head_dir on the object - re-run pose_suit.py")
nrm = Vector(obj["head_dir"]).normalized()

# Fit the bubble to the helmet's RIM.  Two earlier attempts missed: averaging the
# liner ring's normal gave a cap tilted 56 degrees (that ring is the interior bowl,
# whose faces mostly look upward), and sizing off the head gave a bubble wider than
# the helmet itself.  The rim is the front-most edge of the liner along the look
# axis, so take the liner's verts, keep the leading slice, and fit a circle to it.
liner_idx = {i for i, m in enumerate(me.materials) if m.name == "helmet_liner"}
if not liner_idx:
    raise SystemExit("no helmet_liner material - run retint.py first")
liner = [me.vertices[i].co.copy()
         for p in me.polygons if p.material_index in liner_idx
         for i in p.vertices]
if not liner:
    raise SystemExit("no faces use helmet_liner")
proj = [v.dot(nrm) for v in liner]
cut = min(proj) + (max(proj) - min(proj)) * (1.0 - RIM_SLICE)
rim = [v for v, d in zip(liner, proj) if d >= cut]
rim_ctr = sum(rim, Vector()) / len(rim)
radius = max((v - rim_ctr - nrm * (v - rim_ctr).dot(nrm)).length for v in rim) * GROW

# Take the RADIUS from the rim but the CENTRE from the head.  The liner's leading
# slice is the helmet's lower lip, not a ring around the face, so centring on it
# drops the glass to chin height and leaves the eyes out in the open.
if "donor_head" not in obj.vertex_groups:
    raise SystemExit("no donor_head vertex group - re-run pose_suit.py")
_gi = obj.vertex_groups["donor_head"].index
skull = [v.co.copy() for v in me.vertices
         if any(g.group == _gi and g.weight > 0.5 for g in v.groups)]
if not skull:
    raise SystemExit("donor_head vertex group is empty")
ctr = sum(skull, Vector()) / len(skull) + nrm * (PUSH * radius)
print("[visor] rim r=%.3f (%d of %d liner verts); centre from %d head verts "
      "= (%.3f,%.3f,%.3f)  facing=(%.2f,%.2f,%.2f)"
      % (radius, len(rim), len(liner), len(skull),
         ctr.x, ctr.y, ctr.z, nrm.x, nrm.y, nrm.z))

# Spherical cap: a sphere flattened along the opening axis, with the back half cut.
z = nrm
up = Vector((0, 0, 1)) if abs(z.z) < 0.92 else Vector((0, 1, 0))
x = up.cross(z).normalized()
y = z.cross(x)
M = Matrix((x, y, z)).transposed().to_4x4()
M.translation = ctr

bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=14, radius=1.0)
cap = bpy.context.object
cap.name = "visor_glass"
cap.matrix_world = M @ Matrix.Diagonal((radius, radius, radius * BULGE, 1.0))
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bm = bmesh.new()
bm.from_mesh(cap.data)
kill = [f for f in bm.faces
        if (f.calc_center_median() - ctr).dot(nrm) < -WRAP * radius]
bmesh.ops.delete(bm, geom=kill, context='FACES')
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
for f in bm.faces:
    f.smooth = False
bm.to_mesh(cap.data)
bm.free()

glass = bpy.data.materials.get("visor_glass")
if glass is None:
    glass = bpy.data.materials.new("visor_glass")
    glass.use_nodes = True
    b = glass.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.09, 0.19, 0.22, 1.0)
    b.inputs["Metallic"].default_value = 0.20
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Alpha"].default_value = ALPHA
    try:
        glass.surface_render_method = 'BLENDED'
    except Exception:
        pass
    glass.diffuse_color = (0.09, 0.19, 0.22, ALPHA)
    glass.metallic = 0.20
    glass.roughness = 0.08
cap.data.materials.append(glass)

bpy.ops.object.select_all(action='DESELECT')
cap.select_set(True)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.join()

tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
print("[visor] joined: verts=%d faces=%d tris=%d materials=%d"
      % (len(obj.data.vertices), len(obj.data.polygons), tris, len(obj.data.materials)))

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + ".blend"))
print("[visor] saved")
