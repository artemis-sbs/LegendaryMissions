# Avatar Editor

An opt-in, in-game **face customizer** with a live WYSIWYG preview. Pick a race,
move the per-feature sliders, and watch a `gui_face` preview update **inside
Cosmos** as you go. On every change the finished face string is **copied to your
clipboard**, ready to paste into a `.amd` `Face:` field.

Where the VS Code AMD extension's face builder is *blind* — a face only renders once
the engine draws it — this runs in the engine, so you see exactly what you're
building.

The editor is built directly over `sbs_utils.faces` (`faces.FACE_FEATURES`, the
per-race feature list, and `faces.build_face()`, which assembles the layered face
string), so it has **no dependency on the `modding_tools` mission**.

---

## Add it to your mission

Add the `avatar_editor` addon to your `story.json` `mastlib` list:

```json
{
    "mastlib": [
        "artemis-sbs.LegendaryMissions.avatar_editor.v1.4.0.mastlib"
    ]
}
```

The editor is a single label, `avatar_editor_show`. It uses only `sbs_utils.faces`,
so no other LegendaryMissions addon is required.

---

## Use it

Reach the editor one of three ways.

**1. Run it as its own page, wait, and read the result.** `AVATAR_FACE` is a shared
variable holding the built face string:

```
await task_schedule(avatar_editor_show, {"av_race": "terran"})
chosen = AVATAR_FACE
set_face(some_id, chosen)
```

**2. React to the Done signal** (the emitted data is the face string):

```
//signal/avatar_editor_done
    set_face(some_id, EVENT.value)
    ->END
```

**3. Run it inline in an existing GUI task and come back.** Set `av_return` to the
label to return to on Done, then jump in:

```
av_return = "my_next_screen"
jump avatar_editor_show
```

---

## Inputs

Pass these as schedule/jump data, or rely on the metadata defaults.

| Var | Default | Meaning |
|---|---|---|
| `av_race` | `terran` | Starting race (`arvonian`, `kralien`, `skaraan`, `terran`, `torgoth`, `ximni`). |
| `av_title` | `AVATAR EDITOR` | Title-bar text. |
| `av_done_signal` | `avatar_editor_done` | Signal emitted on Done; data is the face string. |
| `av_return` | `""` | Label to return to on Done. `""` ends the task instead. |

An unknown `av_race` shows a small "unknown race" panel with a Close button rather
than erroring.

---

## Output

- **`shared AVATAR_FACE`** — the built face string, updated **live** on every change
  and again on Done.
- The face is **copied to the clipboard** on every change, so an author can paste it
  straight into a `.amd` `Face:` field (the AMD extension's Inspector has
  **Face… → Paste from Avatar Editor** for exactly this).
- On Done, `av_done_signal` fires with the face string as its data.

---

## How the controls map to a face

Each race exposes a different set of features, read from `faces.FACE_FEATURES`:

| Race | Features |
|---|---|
| Arvonian | Eyes, Mouth, Crown\*, Jewels\* |
| Kralien | Eyes, Mouth, Scalp\*, Extra\* |
| Skaraan | Eyes, Mouth, Horn\*, Hat\* |
| Torgoth | Eyes, Mouth, Hair\*, Extra\*, Hat\* |
| Ximni | Eyes, Mouth, Horns\*, Mask\*, Tattoo\* |
| Terran | Body, Eyes, Mouth, Hair\*, Long Hair\*, Facial Hair\*, Extra\*, Uniform\*, Skin Tone, Hair Tone |

\* **Optional** feature — a checkbox turns it on/off; when off it's left out of the
face entirely. Required features are plain sliders. Every change rebuilds the face
via `faces.build_face(race, values, enables)` and refreshes the preview.
