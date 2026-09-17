# Crew exosuit — seated

A heavy EVA / exo suit crew figure, posed **seated with the arms bent forward**, for use
as a bridge or cockpit prop.

Ships as `media/ships/LM_CrewExosuitSeated.{obj,_diffuse,_emissive,_normal,_specular}`.

| | |
|---|---|
| Triangles | 6,758 |
| Vertices | 3,520 |
| Size | 1.296 × 0.948 × 1.420 m (w × d × h) |
| Origin | on the deck, centred between the boots |
| Facing | +Y, Z up |
| Texture | one 256 px palette PNG, 12 cells |

The seat itself is not modelled — the figure sits as if on a ~0.50 m seat, so whatever
it is placed on should put its surface near z = 0.50.

## Source

`SK_Chr_BR_EVA_Suit_01` from the Synty **POLYGON Sci-Fi Space** pack
(`E:/ai/kits/POLYGON_ScifiSpace_SourceFiles`), reposed and retinted. The kit is a
purchased asset; what ships here is derived geometry and a palette of our own colours,
not the pack's source files or atlas.

## Rebuilding

Each step writes `crew_exosuit_seated.blend` back out, so they run in order:

```
B="C:/b/stable/blender-5.2.1-lts.*/blender.exe"

$B --background --python pose_suit.py   -- --out .              # import, pose, graft head
$B --background crew_exosuit_seated.blend --python retint.py    -- --out .
$B --background crew_exosuit_seated.blend --python add_visor.py -- --out .
$B --background crew_exosuit_seated.blend --python build_artset.py -- --out ./artset
```

Then copy `artset/LM_CrewExosuitSeated.*` into `media/ships/`.

To look at any stage: `render_suit.py` (orbit of five views), `headshot.py` (head
close-ups), `verify_artset.py` (renders the **shipped** `.obj` + `_diffuse.png` rather
than the working blend, which is the only render that proves the artifact).

Useful knobs: `pose_suit.py --spine/--neck` (degrees of forward lean),
`--head-scale/--head-offset` (how the head seats in the helmet), `add_visor.py
--grow/--push/--wrap/--alpha`, `build_artset.py --art-name/--size`. The palette itself
is the `PALETTE` dict at the top of `retint.py`.

## Things that cost time, so they are written down

**The suit ships headless.** Its helmet is a hollow shell; the head comes from
`SK_Chr_Crew_Male_01` (the pack shares one skeleton, so it grafts on and deforms with
the same bones). The donor brings its own cap and visor, which are dropped by atlas
colour, and the donor verts are tagged into a `donor_head` vertex group because later
steps cannot find the head any other way.

**The FBX 2013 export carries custom split normals Blender's importer mangles** — 35 of
the 37 armour shells import dark and faceted into shards. Clear them, then fix winding
one shell at a time, flipping only shells whose *signed volume* says they are inside
out. A blanket `recalc_face_normals` over the whole soup turns the head into a bowl.
Synty POLYGON art is **flat** shaded; smoothing it makes the shard look worse.

**Do not aim spine, neck or head bones at an absolute direction.** The `head` bone
points *forward through the skull* in rest, so "aim it up" is a 60° swing that shreds
the skinning. Those are relative nudges. Limbs are fine to aim, and are.

**Skin colour cannot tell you which way the face looks** — Synty bakes lighting into the
atlas, so the lit cells are the top of the skull. `pose_suit.py` records the head bone's
world direction onto the object (`head_dir`) while the armature still exists, and
`add_visor.py` fits the bubble off that.

**The visor is fitted, not placed**: radius from the helmet's rim (the leading slice of
the liner along the look axis), centre from the head. Centring on the rim instead drops
the glass to chin height; sizing off the head makes a bubble wider than the helmet.

**The texture is a palette, not a bake.** Every material is a single flat colour, so
there is nothing a Cycles bake would capture that a lookup table cannot hold exactly.
Each material gets one 64 px cell and every one of its faces points at that cell's
centre — 2 KB instead of megabytes, no seams, and the PNG's bytes *are* the palette, so
it can be edited a pixel at a time. Cells are large on purpose so mipmapping cannot
bleed one colour into its neighbour at distance.

**Colour space: write the Base Color straight in.** It is already linear and Blender
handles the encoding on save. Converting sRGB→linear first looks like the obvious fix
and darkens the whole set by a stop (the orange goes blood red, the greys near-black).

## Unverified

- **This has not been loaded in the engine.** Mod ship art has a history of crashing on
  derived-art generation (see the Venus notes), and nothing here has been tested against
  a real Cosmos build. Treat engine loading as unproven.
- **Diffuse alpha is unproven on ship art.** The visor cell carries alpha 87/255. If the
  engine honours it the face shows through; if not, the smoked colour still reads as a
  tinted visor rather than a bright bauble — which is why it is smoked.
- `media/` is packaged as the **shared media pack**, so a fetched mission will not see
  these files until the pack is rebuilt and re-released.
