"""Bake the posed suit down to a Cosmos art set: one .obj plus the
diffuse / emissive / normal / specular PNGs the engine expects beside it.

  blender.exe -b <blend> --python build_artset.py -- --out <dir> --art-name <Name>

The model is FLAT COLOUR - every material is a single value - so there is nothing
for a Cycles bake to capture that a lookup table cannot hold exactly.  Instead of
unwrapping and baking, give each material one cell of a small palette texture and
point every one of its faces at that cell's centre.  The result is exact (no seam
or filtering artifacts, no bake noise), a few KB instead of a few MB, and the
palette stays editable one pixel at a time.

Cells are deliberately large (64 px for a 12-entry palette) so mipmapping and
bilinear filtering cannot bleed one colour into its neighbour at distance.
"""
import bpy, sys, os, math

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGV[ARGV.index(name) + 1] if name in ARGV else default


NAME = arg("--name", "crew_exosuit_seated")
ART = arg("--art-name", "LM_CrewExosuitSeated")
OUT = arg("--out", os.path.dirname(__file__))
SIZE = int(arg("--size", "256"))
os.makedirs(OUT, exist_ok=True)

obj = bpy.data.objects[NAME]
me = obj.data
mats = list(me.materials)
n = len(mats)
grid = max(1, math.ceil(math.sqrt(n)))
cell = SIZE // grid
if cell < 8:
    raise SystemExit("palette cells too small - raise --size")
print("[art] %d materials -> %dx%d grid of %dpx cells in a %dpx texture"
      % (n, grid, grid, cell, SIZE))


def props(m):
    """Base colour, metallic, roughness and alpha off the Principled node."""
    b = m.node_tree.nodes.get("Principled BSDF") if m.use_nodes else None
    if b is None:
        c = m.diffuse_color
        return (c[0], c[1], c[2]), m.metallic, m.roughness, 1.0
    c = b.inputs["Base Color"].default_value
    return ((c[0], c[1], c[2]),
            b.inputs["Metallic"].default_value,
            b.inputs["Roughness"].default_value,
            b.inputs["Alpha"].default_value)


# NOTE on colour space, measured rather than guessed: a material's Base Color is
# already LINEAR, and Blender sRGB-encodes image pixels on save, so writing the
# base colour straight into the palette round-trips exactly - the texture path and
# the material preview land on the same pixel.  An sRGB->linear conversion here
# looks like the obvious fix and is wrong: it darkens the whole set by a stop
# (the orange goes to blood red, the greys to near-black).


def new_image(name, fill, non_color=False):
    img = bpy.data.images.new(name, SIZE, SIZE, alpha=True)
    img.generated_color = fill
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    return img


diffuse = new_image(ART + "_diffuse", (0, 0, 0, 1))
emissive = new_image(ART + "_emissive", (0, 0, 0, 1))
specular = new_image(ART + "_specular", (0, 0, 0, 1))
normal = new_image(ART + "_normal", (0.5, 0.5, 1.0, 1.0), non_color=True)

dpx = list(diffuse.pixels)
spx = list(specular.pixels)
epx = list(emissive.pixels)


def cell_box(i):
    col, row = i % grid, i // grid
    return col * cell, (grid - 1 - row) * cell     # x0, y0 with y counted from the bottom


for i, m in enumerate(mats):
    rgb, metallic, rough, alpha = props(m)
    x0, y0 = cell_box(i)
    # A metal reads as metal through the specular map; the undersuit must not.
    s = metallic * (1.0 - rough * 0.5)
    for y in range(y0, y0 + cell):
        base = y * SIZE * 4
        for x in range(x0, x0 + cell):
            p = base + x * 4
            dpx[p:p + 4] = [rgb[0], rgb[1], rgb[2], alpha]
            spx[p:p + 4] = [s, s, s, 1.0]
            epx[p:p + 4] = [0.0, 0.0, 0.0, 1.0]

diffuse.pixels = dpx
specular.pixels = spx
emissive.pixels = epx

# Point every face at the centre of its material's cell.
uvname = "palette"
for lay in list(me.uv_layers):
    if lay.name != uvname:
        me.uv_layers.remove(lay)
uv = me.uv_layers.new(name=uvname)
me.uv_layers.active = uv
uv = me.uv_layers[uvname].data
for p in me.polygons:
    col, row = p.material_index % grid, p.material_index // grid
    u = (col + 0.5) / grid
    v = 1.0 - (row + 0.5) / grid
    for l in p.loop_indices:
        uv[l].uv = (u, v)

# Collapse to the single material the art set ships with.
single = bpy.data.materials.new(ART)
single.use_nodes = True
nt = single.node_tree
bsdf = nt.nodes["Principled BSDF"]
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = diffuse
tex.interpolation = 'Closest'
tex.location = (-380, 220)
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
nt.nodes.active = tex
me.materials.clear()
me.materials.append(single)
for p in me.polygons:
    p.material_index = 0

for img, suffix in ((diffuse, "_diffuse"), (emissive, "_emissive"),
                    (normal, "_normal"), (specular, "_specular")):
    path = os.path.join(OUT, ART + suffix + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    print("[art] wrote", os.path.basename(path))

bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
objpath = os.path.join(OUT, ART + ".obj")
# EXPORT THE MATERIAL, and write the .mtl beside the mesh.
#
# Measured against a hull that works in engine 1.3.11 (Cosmos-TNG-Mod's CRD_Damar): it
# carries `mtllib` and `usemtl`, and this exporter was writing NEITHER. A mesh with no
# material gives the engine nothing to bind its textures to, and what it draws instead is
# the UNKNOWN PLACEHOLDER - silently, with nothing in any log.
# FORWARD IS +Z IN COSMOS, and the exporter's default sends this mesh out facing the
# other way - so the suit flew BACKWARDS in engine, visor to the stern.
#
# Measured, not assumed, because every step of it is easy to get wrong:
#   * Cosmos forward is +Z - `forward_vector()` is (0,0,1) at identity, and TNG's
#     FED_Galaxy.obj puts the SAUCER (565 wide) at +Z with the nacelles trailing to -Z.
#   * this suit faces +Y in BLENDER. Renders settle it; the material centroids do NOT -
#     the `face` material sits at Y=-0.246, on the far side from the visor, because the
#     head was grafted from another model and its skin material is inside the helmet.
#     Do not re-derive the facing from material positions.
#   * the default `forward_axis="NEGATIVE_Z"` therefore lands the chest at OBJ -Z.
# `forward_axis="Z"` is a 180-degree turn about up, not a mirror - the exporter builds a
# proper rotation from the forward/up pair, so winding and normals stay right-handed.
bpy.ops.wm.obj_export(filepath=objpath, export_selected_objects=True,
                      export_materials=True, export_triangulated_mesh=True,
                      export_normals=True, export_uv=True,
                      forward_axis="Z", up_axis="Y")

# Verify the export has geometry: Blender's OBJ exporter writes a SHARED mesh once
# per instance group, so "selected only" on an instanced mesh can produce a header
# with no v/f lines at all - which the engine answers with an assert, not an error.
with open(objpath, encoding="utf-8") as fh:
    lines = fh.read().splitlines()
v = sum(1 for l in lines if l.startswith("v "))
f = sum(1 for l in lines if l.startswith("f "))
vt = sum(1 for l in lines if l.startswith("vt "))
print("[art] wrote %s: %d verts, %d uvs, %d triangles" % (os.path.basename(objpath), v, vt, f))
if v == 0 or f == 0:
    raise SystemExit("exported OBJ has no geometry")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, ART + "_artset.blend"))
print("[art] done")
