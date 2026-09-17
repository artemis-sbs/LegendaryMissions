"""Retint the Synty EVA suit from its stock dark-grey atlas to the orange/grey
rescue-suit scheme of the reference.

  blender.exe -b <blend> --python retint.py -- --out <dir>

The Synty atlas is flat colour cells, so every face samples effectively one
colour: cluster the faces by that colour and give each cluster a flat material.
That keeps Synty's look exactly and makes the palette editable by name.
"""
import bpy, sys, os

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGV[ARGV.index(name) + 1] if name in ARGV else default


ATLAS = arg("--atlas", "E:/ai/kits/POLYGON_ScifiSpace_SourceFiles/Textures/"
                      "PolygonSciFiSpace_Texture_01_A.png")
OUT = arg("--out", os.path.dirname(__file__))
NAME = arg("--name", "crew_exosuit_seated")

# stock atlas colour  ->  (material name, linear-ish RGB, metallic, roughness)
PALETTE = {
    (0.24, 0.24, 0.24): ("suit_orange",      (0.78, 0.30, 0.05), 0.10, 0.50),
    (0.31, 0.31, 0.31): ("suit_orange_dark", (0.50, 0.19, 0.03), 0.10, 0.55),
    (0.37, 0.37, 0.37): ("plate_grey",       (0.48, 0.50, 0.53), 0.60, 0.42),
    (0.58, 0.58, 0.58): ("plate_light",      (0.70, 0.72, 0.74), 0.55, 0.38),
    (0.18, 0.18, 0.18): ("undersuit",        (0.14, 0.14, 0.16), 0.05, 0.72),
    (0.16, 0.16, 0.16): ("undersuit",        (0.14, 0.14, 0.16), 0.05, 0.72),
    (0.12, 0.13, 0.14): ("dark_metal",       (0.085, 0.092, 0.105), 0.75, 0.45),
    (0.11, 0.11, 0.12): ("dark_metal",       (0.085, 0.092, 0.105), 0.75, 0.45),
    (0.16, 0.17, 0.18): ("dark_metal",       (0.085, 0.092, 0.105), 0.75, 0.45),
    (0.50, 0.36, 0.27): ("helmet_liner",     (0.62, 0.60, 0.56), 0.00, 0.70),
    (1.00, 0.80, 0.68): ("face",             (0.80, 0.60, 0.48), 0.00, 0.62),
    (0.80, 0.70, 0.63): ("face_shadow",      (0.62, 0.46, 0.37), 0.00, 0.64),
    (0.31, 0.25, 0.18): ("hair",             (0.24, 0.17, 0.12), 0.00, 0.70),
    (0.00, 0.00, 0.00): ("eye",              (0.02, 0.02, 0.03), 0.00, 0.30),
    (0.28, 0.21, 0.16): ("hair",             (0.24, 0.17, 0.12), 0.00, 0.70),
    (0.16, 0.14, 0.11): ("hair",             (0.24, 0.17, 0.12), 0.00, 0.70),
}
FALLBACK = ("plate_grey", (0.48, 0.50, 0.53), 0.60, 0.42)

obj = bpy.data.objects[NAME]
me = obj.data
uv = me.uv_layers[0].data
img = bpy.data.images.load(ATLAS, check_existing=False)
w, h = img.size
px = img.pixels[:]
if not px:
    raise SystemExit("atlas has no pixels: " + ATLAS)


def make(spec):
    name, rgb, metallic, rough = spec
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    m.metallic = metallic
    m.roughness = rough
    return m


me.materials.clear()
slot = {}
for spec in list(PALETTE.values()) + [FALLBACK]:
    if spec[0] in slot:
        continue
    slot[spec[0]] = len(me.materials)
    me.materials.append(make(spec))

unmapped = {}
for p in me.polygons:
    u = sum(uv[l].uv[0] for l in p.loop_indices) / p.loop_total
    v = sum(uv[l].uv[1] for l in p.loop_indices) / p.loop_total
    x = int(min(max(u, 0), 0.9999) * w)
    y = int(min(max(v, 0), 0.9999) * h)
    i = (y * w + x) * 4
    key = (round(px[i], 2), round(px[i + 1], 2), round(px[i + 2], 2))
    spec = PALETTE.get(key)
    if spec is None:
        unmapped[key] = unmapped.get(key, 0) + 1
        spec = FALLBACK
    p.material_index = slot[spec[0]]

for k, n in sorted(unmapped.items(), key=lambda kv: -kv[1]):
    print("[retint] unmapped colour %s on %d faces -> fallback" % (k, n))
print("[retint] %d materials: %s" % (len(me.materials), [m.name for m in me.materials]))

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + ".blend"))
print("[retint] saved")
