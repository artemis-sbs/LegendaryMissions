# Profiles

A **profile** is one named file that decides how the mission runs - its settings, and
which add-ons and art packs it loads. You select it by name on the command line and
nothing else changes:

``` text
Artemis3-x64-release.exe autostartserver defaultmission=LegendaryMissions profile=eastern_front
```

This is the answer to *"I run three different setups and I am tired of retyping them"*,
and it replaces the older advice of copying the whole mission folder per setup.

## Where a profile lives

Two places are searched, in this order:

| | | |
|---|---|---|
| `LegendaryMissions/profiles/<name>.yaml` | the mission's own | settings, add-ons and art packs |
| `data/missions/common_data/profiles/<name>.yaml` | **yours** | settings only |

The mission's own wins on a name collision.

**Put your house setups in `common_data/profiles/`.** It sits beside the missions rather
than inside one, so updating or re-extracting LegendaryMissions cannot lose it. Add-on and
art-pack selection is not available there, because those only mean something against one
specific mission - a shared profile that names them is refused, with a message saying so,
and its settings still apply.

## What goes in one

Any key from [settings.yaml](settings.yaml.md), spelled the same way:

``` yaml title="data/missions/common_data/profiles/eastern_front.yaml"
DIFFICULTY: 7
PLAYER_COUNT: 4
WORLD_SELECT: "siege"
TERRAIN_SELECT: "lots"
GAME_TIME_LIMIT: 45
```

A profile beats `settings.yaml`, and a single `var.NAME=` on the command line beats the
profile - so you can name a configuration and still change one thing for tonight:

``` text
... profile=eastern_front var.DIFFICULTY=9
```

LegendaryMissions ships three of its own as examples, in its `profiles/` folder:
`autoplay7` (a full settings setup), and `a28_add` / `a28_skies` (which swap the skyboxes
for the Artemis 2.8 set - the add-on half, which only a mission-local profile can do).

## Profile, preset, or RESTORE_LAST_SETUP?

Three different needs, three different answers:

| You want | Use |
|---|---|
| Several standing setups, chosen when the server starts | a **profile** |
| To save the setup you just built on screen, and pick it again later | a **preset** ([Saved setups](index.md#saved-setups)) |
| The next game to just start the way the last one did | **`RESTORE_LAST_SETUP: true`** |

Presets and the last-used setup are saved by the game and live in
`data/missions/common_data/game_codes/`. A profile is written by you, in a text editor.

Full reference, including add-on and art-pack selection:
[Profiles in the sbs_utils documentation](https://artemis-sbs.github.io/sbs_utils/tooling/profiles/).
