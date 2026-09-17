"""Import the Synty EVA suit, pose it SEATED with arms bent forward, bake to a
static mesh, and save/export.

  blender.exe --background --python pose_suit.py -- --out <dir>

The FBX arrives in Synty's UE-ish space: the armature object carries a 0.01 scale
and a Y/Z swap, so inside ARMATURE space  +X = the figure's left, +Y = world up,
+Z = the direction it faces.  All the target directions below are written in that
armature space.  At the end the baked mesh is rotated so the finished object faces
+Y with Z up and its origin on the deck between the boots.
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector, Matrix

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGV[ARGV.index(name) + 1] if name in ARGV else default


KIT = "E:/ai/kits/POLYGON_ScifiSpace_SourceFiles"
SRC = arg("--fbx", KIT + "/Characters/FBX 2013/SK_Chr_BR_EVA_Suit_01.fbx")
TEX = arg("--tex", KIT + "/Textures/PolygonSciFiSpace_Texture_01_A.png")
OUT = arg("--out", os.path.dirname(__file__))
NAME = arg("--name", "crew_exosuit_seated")
SPINE_PITCH = float(arg("--spine", "0"))     # degrees, + leans forward
NECK_PITCH = float(arg("--neck", "0"))
HEAD_FBX = arg("--head", KIT + "/Characters/FBX 2013/SK_Chr_Crew_Male_01.fbx")
if HEAD_FBX in ("none", "None", ""):
    HEAD_FBX = None
# Stock atlas cells that are skin, hair or eye - everything else on the donor head
# is its own headgear.
HEAD_SCALE = float(arg("--head-scale", "0.90"))
# centimetres in the donor's own space: +X left, +Y up, +Z forward
HEAD_OFFSET = tuple(float(x) for x in arg("--head-offset", "0,-4.5,-1.0").split(","))
SKIN_KEYS = {(1.0, 0.8, 0.68), (0.8, 0.7, 0.63), (0.5, 0.36, 0.27),
             (0.31, 0.25, 0.18), (0.28, 0.21, 0.16), (0.16, 0.14, 0.11),
             (0.0, 0.0, 0.0)}
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
bpy.ops.import_scene.fbx(filepath=SRC, automatic_bone_orientation=True)

arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')


def graft_head(donor_fbx, groups=("head", "eyes", "eyebrows")):
    """The EVA suit ships HEADLESS - its helmet is a hollow shell meant to be
    filled by a head from another character in the pack.  Import one, throw away
    everything not weighted to the head, point it at our armature (the pack shares
    one skeleton) and join it in before posing so it deforms with the rest."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=donor_fbx, automatic_bone_orientation=True)
    added = [o for o in bpy.data.objects if o not in before]
    d_arm = next(o for o in added if o.type == 'ARMATURE')
    d_mesh = next(o for o in added if o.type == 'MESH')

    keep = {d_mesh.vertex_groups[g].index for g in groups if g in d_mesh.vertex_groups}
    doomed = [v.index for v in d_mesh.data.vertices
              if not any(g.group in keep and g.weight > 0.01 for g in v.groups)]
    bm = bmesh.new()
    bm.from_mesh(d_mesh.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in doomed], context='VERTS')
    bm.to_mesh(d_mesh.data)
    bm.free()
    # The crew character wears its own cap/visor, which came along with the head
    # bone and pokes out of the EVA helmet.  Synty atlases are flat colour cells,
    # so drop every face that is not skin, hair or eye coloured and a bare head is
    # what is left.
    if SKIN_KEYS:
        img = bpy.data.images.load(TEX, check_existing=True)
        w, h = img.size
        px = img.pixels[:]
        uv = d_mesh.data.uv_layers[0].data
        cut = []
        for f in d_mesh.data.polygons:
            u = sum(uv[l].uv[0] for l in f.loop_indices) / f.loop_total
            v = sum(uv[l].uv[1] for l in f.loop_indices) / f.loop_total
            i = (int(min(max(v, 0), 0.9999) * h) * w +
                 int(min(max(u, 0), 0.9999) * w)) * 4
            if (round(px[i], 2), round(px[i + 1], 2), round(px[i + 2], 2)) not in SKIN_KEYS:
                cut.append(f.index)
        bm = bmesh.new()
        bm.from_mesh(d_mesh.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in cut], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bm.to_mesh(d_mesh.data)
        bm.free()
    # Seat the donor head inside the EVA helmet: it belongs to a bare-headed crew
    # character, so at native size the crown pokes through the helmet shell.  Scale
    # and shift about the head BONE, in the donor's own (centimetre, Y-up) space.
    pivot = d_arm.data.bones["head"].head_local
    for v in d_mesh.data.vertices:
        v.co = pivot + (v.co - pivot) * HEAD_SCALE + Vector(HEAD_OFFSET)
    print("[suit] head donor: kept %d verts / %d faces (scale %.2f offset %s)" %
          (len(d_mesh.data.vertices), len(d_mesh.data.polygons), HEAD_SCALE, HEAD_OFFSET))

    for m in list(d_mesh.modifiers):
        if m.type == 'ARMATURE':
            m.object = arm
    d_mesh.parent = arm
    d_mesh.matrix_parent_inverse = arm.matrix_world.inverted()
    d_mesh.matrix_world = mesh.matrix_world.copy()

    # Tag the donor verts so later steps can find the head exactly.  Picking it out
    # by atlas colour does not work: the skin and hair cells also appear on suit
    # details, which makes the "head" measure twice its real size.
    vg = d_mesh.vertex_groups.new(name="donor_head")
    vg.add([v.index for v in d_mesh.data.vertices], 1.0, 'REPLACE')

    bpy.ops.object.select_all(action='DESELECT')
    d_mesh.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.join()

    bpy.ops.object.select_all(action='DESELECT')
    d_arm.select_set(True)
    bpy.ops.object.delete()


if HEAD_FBX:
    graft_head(HEAD_FBX)

# The FBX 2013 export carries custom split normals that Blender's importer mangles
# - most of the 37 armor shells come in dark and faceted into shards, with only
# the odd one correct.  Drop them and recalculate per shell.  Synty POLYGON art is
# FLAT shaded by design, so no smoothing is wanted afterwards either.
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
try:
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
except Exception as ex:
    print("[suit] no custom split normals to clear:", ex)


def recalc_per_shell(obj, flip_only=True):
    """Fix normals one connected shell at a time - a blanket pass over a soup of
    separate closed pieces can flip whole bodies inside out.  With flip_only the
    winding is left alone and a shell is flipped only when its signed volume says
    it is genuinely inside out, which keeps Synty's own hand-made windings (the
    head shell comes out as a bowl if you recalc it).""" 
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    seen = set()
    shells = 0
    flipped = []
    for v in bm.verts:
        if v.index in seen:
            continue
        shells += 1
        group, stack = [], [v]
        while stack:
            x = stack.pop()
            if x.index in seen:
                continue
            seen.add(x.index)
            group.append(x)
            for e in x.link_edges:
                stack.append(e.other_vert(x))
        faces = [f for f in {f for g in group for f in g.link_faces}]
        if flip_only:
            vol = 0.0
            for f in faces:
                vs = f.verts[:]
                for i in range(1, len(vs) - 1):
                    a, b, c = vs[0].co, vs[i].co, vs[i + 1].co
                    vol += a.dot(b.cross(c)) / 6.0
            if vol < 0:
                bmesh.ops.reverse_faces(bm, faces=faces)
                flipped.append(shells)
        else:
            bmesh.ops.recalc_face_normals(bm, faces=faces)
    for f in bm.faces:
        f.smooth = False
    bm.to_mesh(obj.data)
    bm.free()
    print("[suit] %d shells, flipped %d: %s" % (shells, len(flipped), flipped))


recalc_per_shell(mesh)

# ---------------------------------------------------------------- posing
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')


def bone(name):
    """Synty mixes bone-name casing (Foot_L but calf_l), so resolve either."""
    for cand in (name, name[:-1] + name[-1].swapcase()):
        if cand in arm.pose.bones:
            return cand
    raise KeyError("no bone named %r" % name)


def point(name, target, twist=0.0):
    """Swing a bone so it points along `target` (armature space), then twist it
    about its own new axis by `twist` radians."""
    name = bone(name)
    bpy.context.view_layer.update()
    pb = arm.pose.bones[name]
    cur = (pb.tail - pb.head).normalized()
    tgt = Vector(target).normalized()
    head = pb.head.copy()
    q = cur.rotation_difference(tgt)
    R = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head)
    pb.matrix = R @ pb.matrix
    if twist:
        bpy.context.view_layer.update()
        pb = arm.pose.bones[name]
        head = pb.head.copy()
        T = Matrix.Translation(head) @ Matrix.Rotation(twist, 4, tgt) @ \
            Matrix.Translation(-head)
        pb.matrix = T @ pb.matrix
    bpy.context.view_layer.update()


# Armature space: +X left, +Y up, +Z forward.
for sx, L in ((+1, "l"), (-1, "r")):
    U = L.upper()
    # legs: thighs forward and level, shins down, feet flat on the deck
    point("Thigh_%s" % U, (sx * 0.13, -0.10, 0.99))
    point("calf_%s" % L, (sx * 0.02, -0.96, 0.27))
    point("Foot_%s" % L, (0, -0.30, 0.95))
    point("ball_%s" % L, (0, -0.05, 1.00))

    # arms: upper arm down and slightly forward, forearm bent forward, hands out
    point("UpperArm_%s" % U, (sx * 0.30, -0.90, 0.32))
    point("lowerarm_%s" % L, (sx * 0.05, -0.10, 0.99))
    point("Hand_%s" % U, (sx * 0.04, -0.34, 0.94))

    # light finger curl so the hands read as resting on controls
    for f in ("indexFinger", "finger"):
        for j, ang in ((1, 0.55), (2, 0.65), (3, 0.55)):
            b = "%s_0%d_%s" % (f, j, L)
            if b in arm.pose.bones:
                pb = arm.pose.bones[b]
                pb.rotation_mode = 'XYZ'
                pb.rotation_euler.x = -ang
    for j, ang in ((1, 0.30), (2, 0.45)):
        b = "thumb_0%d_%s" % (j, L)
        if b in arm.pose.bones:
            pb = arm.pose.bones[b]
            pb.rotation_mode = 'XYZ'
            pb.rotation_euler.x = -ang

# A little life in the spine: RELATIVE nudges only.  These bones do not all point
# along the body axis in rest (head runs forward through the skull), so aiming them
# at an absolute direction swings them 60 degrees and shreds the skinning.
def nudge(name, pitch):
    pb = arm.pose.bones[bone(name)]
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler.x += pitch
    bpy.context.view_layer.update()


nudge("spine_01", math.radians(SPINE_PITCH))
nudge("spine_02", math.radians(SPINE_PITCH * 0.8))
nudge("neck_01", math.radians(NECK_PITCH))

bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()

# Record where the head is pointing while the armature still exists.  Nothing in
# the baked mesh says which way the face looks - the skin CELLS cannot answer it,
# because Synty bakes lighting into them, so the lit cells are the top of the head
# rather than its front.  add_visor.py fits the bubble off these.
_hb = arm.pose.bones[bone("head")]
HEAD_POS_W = arm.matrix_world @ _hb.head.copy()
HEAD_DIR_W = (arm.matrix_world.to_3x3() @ (_hb.tail - _hb.head)).normalized()

# ---------------------------------------------------------------- bake to static
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
for m in list(mesh.modifiers):
    if m.type == 'ARMATURE':
        bpy.ops.object.modifier_apply(modifier=m.name)
mesh.parent = None
mesh.matrix_world = arm.matrix_world @ mesh.matrix_basis
bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True)
bpy.ops.object.delete()

bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Face +Y (the FBX faces -Y), then drop the boots onto z = 0 and centre in x/y.
mesh.matrix_world = Matrix.Rotation(math.pi, 4, 'Z') @ mesh.matrix_world
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bb = [Vector(c) for c in mesh.bound_box]
lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
shift = Vector((-(lo.x + hi.x) * 0.5, -(lo.y + hi.y) * 0.5, -lo.z))
mesh.matrix_world = Matrix.Translation(shift) @ mesh.matrix_world
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

FINAL = Matrix.Translation(shift) @ Matrix.Rotation(math.pi, 4, 'Z')
head_pos = FINAL @ HEAD_POS_W
head_dir = (FINAL.to_3x3() @ HEAD_DIR_W).normalized()
mesh["head_pos"] = list(head_pos)
mesh["head_dir"] = list(head_dir)
print("[suit] head at (%.3f,%.3f,%.3f) looking (%.2f,%.2f,%.2f)"
      % (head_pos.x, head_pos.y, head_pos.z, head_dir.x, head_dir.y, head_dir.z))

mesh.name = NAME
mesh.data.name = NAME

# ---------------------------------------------------------------- material
m = mesh.data.materials[0]
m.use_nodes = True
nt = m.node_tree
bsdf = nt.nodes.get("Principled BSDF")
if os.path.exists(TEX):
    img = bpy.data.images.load(TEX, check_existing=True)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = 'Closest'          # Synty atlases are flat colour cells
    tex.location = (-380, 220)
    nt.nodes.active = tex                  # Workbench "texture" shading reads this
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    bsdf.inputs["Metallic"].default_value = 0.10
else:
    print("[suit] WARNING texture not found:", TEX)

bpy.ops.object.shade_flat()          # Synty POLYGON art is flat shaded

tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
bb = [mesh.matrix_world @ Vector(c) for c in mesh.bound_box]
lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
print("[suit] verts=%d faces=%d tris=%d" %
      (len(mesh.data.vertices), len(mesh.data.polygons), tris))
print("[suit] size = %.3f x %.3f x %.3f m  (w x d x h)" %
      (hi.x - lo.x, hi.y - lo.y, hi.z - lo.z))

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + ".blend"))
print("[suit] saved", os.path.join(OUT, NAME + ".blend"))
