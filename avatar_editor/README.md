# avatar_editor (LegendaryMissions addon)

An opt-in, in-game **face customizer** with a live WYSIWYG preview. It is built
directly over `sbs_utils.faces` — `faces.FACE_FEATURES` (the per-race feature list)
and `faces.build_face()` (assembles the layered face string) — so it has no
dependency on the `modding_tools` mission.

Where the VS Code AMD extension's face builder is *blind* (a face renders only in
the engine), this runs **inside Cosmos**, so the `gui_face` preview updates live as
you move the sliders.

## Use it

Add the mastlib to your mission's `story.json`:

```json
"mastlib": [ "artemis-sbs.LegendaryMissions.avatar_editor.v1.4.0.mastlib" ]
```

Then reach the editor one of three ways:

```
# 1. Run it as its own page, wait, and read the result:
await task_schedule(avatar_editor_show, {"av_race": "terran"})
chosen = AVATAR_FACE

# 2. React to the Done signal (data = the face string):
//signal/avatar_editor_done
    set_face(some_id, EVENT.value)

# 3. Run it inline in an existing GUI task and return:
#    (set av_return to the label to come back to)
jump avatar_editor_show
```

## Inputs (task vars / metadata defaults)

| var | default | meaning |
|---|---|---|
| `av_race` | `terran` | starting race |
| `av_title` | `AVATAR EDITOR` | title-bar text |
| `av_done_signal` | `avatar_editor_done` | signal emitted on Done (data = face string) |
| `av_return` | `""` | label to return to on Done (`""` → ends the task) |

## Output

- **`shared AVATAR_FACE`** — the built face string, updated live and on Done.
- The face is also **copied to the clipboard** on every change, so an author can
  paste it straight into a `.amd` `Face:` field (the AMD extension's Inspector has
  **Face… → Paste from Avatar Editor** for exactly this).
