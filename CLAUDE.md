# LegendaryMissions — Repo Guide for Claude

**LegendaryMissions (LM)** is two things at once:
1. A **playable mission** — the scenarios in `maps/` (siege, singlefront, doublefront,
   deepstrike, peacetime, borderwar, sandbox, …).
2. The **shared addon library** that most Cosmos missions build on — dozens of
   reusable **addons** (consoles, comms, fleets, docking, prefabs, quests, …) that
   get packaged as distributable `.mastlib`s.

Built on **sbs_utils** (the library/engine API). This file is the working guide for
an agent focused on LM.

---

## The dual nature (how loading & packaging work)

Each subfolder with an **`__init__.mast`** is an **addon**.

- **When LM runs as a mission**, *all* its local addon folders **auto-load** (its
  `story.mast` is empty and `story.json` lists only the sbslib — the folders load
  because they're in the mission). This is also how `maps/` loads — maps are just
  another addon.
- **For other missions to use LM**, the addons are **packaged as mastlibs** (zip
  files) listed in **`__lib__.json`**. Consumer missions (OpenUniverse,
  SecretMeeting, WalkTheLine, remote_mission_pick) load specific mastlibs via their
  own `story.json`.

So a subfolder can be:
- **Packaged** (in `__lib__.json`) → distributed as `artemis-sbs.LegendaryMissions.<addon>.<ver>.mastlib`.
- **Local-only** (has `__init__.mast` but NOT in `__lib__.json`) → part of LM's own
  mission only. Currently local-only: **`maps`** (the scenarios) and **`items`**.

---

## How it relates to the other repos

```
missions/
├── sbs_utils/         # the library + engine API LM builds on (the RUNTIME)
├── LegendaryMissions/ # THIS repo — addons + the maps mission
├── OpenUniverse/      # a consumer mission (loads LM addons incl. quests)
├── SecretMeeting/  WalkTheLine/  remote_mission_pick/   # more consumer missions
└── __lib__/           # built mastlibs live here (what consumers load)
```

- **sbs_utils** — the `sbs` API + `procedural/` helpers every addon calls. Loaded
  via `story.json` `sbslib`. For dev, run with `--use-working-tree` to use the live
  checkout.
- **Consumer missions** load LM **mastlibs** from `__lib__/`. **This is the key
  constraint: changing an addon's API can break consumer missions.** Treat addon
  labels/functions as a public API.
- The **Open Universe was extracted** into its own repo (`OpenUniverse`); it loads
  LM addons (including the **`quests`** mastlib) rather than living in `maps/`.

---

## Repo layout

```
LegendaryMissions/
├── script.py / story.mast (empty) / story.json (sbslib only)
├── __lib__.json            # packaging manifest: which addons -> mastlibs + version
├── settings.yaml           # difficulty / PLAYER_LIST / docking defaults
├── maps/                   # LOCAL addon: playable scenarios + mission_story, legendary_comms, game_objectives
├── quests/                 # quest system (quest_driver, hangar_board, bridge_story) - PACKAGED mastlib
├── items/                  # items/upgrades registry - LOCAL addon
└── <addon>/                # each is an addon with __init__.mast:
    ai, comms, consoles, damage, docking, fleets, prefabs, commerce,
    science_scans, hangar, upgrades, documents, data_panels, grid_comms,
    internal_comms, side_missions, basic_player_destroy, basic_random_skybox,
    collisions, autoplay, operator, admiral, admiral_comms, gamemaster,
    gamemaster_comms, director
```

---

## Running & testing (dev)

From the **sbs_utils** directory (where `cosmos_dev` lives):

```bash
cd ../sbs_utils

# Play a scenario in the browser (open http://localhost:8765/):
python -m cosmos_dev.mission_runner ../LegendaryMissions --gui --map siege --use-working-tree

# Headless conformance run:
python -m cosmos_dev.mission_runner ../LegendaryMissions --test 30 --map siege --use-working-tree
```

- Map names are the `@map/...` labels (siege, singlefront, doublefront, deepstrike,
  peacetime, borderwar, sandbox). Omit `--map` for the picker.
- `--use-working-tree` runs against the live sbs_utils checkout; the
  `sbslib not found ...v1.4.0.sbslib` warning is expected in dev.

### Rebuild mastlibs after editing an addon
Consumer missions load LM addons from `__lib__/`, **not** from this working tree.
After changing an addon, rebuild so consumers pick it up:

```bash
cd ..            # the missions/ folder
python sbs.pyz lib LegendaryMissions   # builds v1.4.0 mastlibs (per __lib__.json) into __lib__/
```

---

## Conventions & gotchas

- **`.mast` comments use `#`.** `//` at column 0 starts a **route** (`//comms`), not
  a comment. (`.amd` files use `//` for comments — the opposite. `.py` uses `#`.)
- **`import file.py` merges an addon's helpers into ONE shared MAST namespace** — no
  relative sibling imports (`from .x import …`); they fail in-engine. Use absolute
  `sbs_utils...` imports only.
- **Engine-rendered text is ASCII-only** (GUI text, console names, comms,
  objectives). Comments/docs are exempt.
- The **engine MAST compiler is stricter than the headless mock** — `--test` can
  pass while Cosmos fails to compile (watch `:` in inline comms button labels and
  `jump`-prefixed identifiers).
- Full references in the sibling library repo: `../sbs_utils/CLAUDE.md`,
  `../sbs_utils/MAST_CLAUDE.md`, `../sbs_utils/MAST_MISSION_CLAUDE.md`, and the AMD
  authoring guide `../AMD_AUTHORS_GUIDE.md`.

---

## Backward compatibility (LM's prime directive)

LM addons are consumed by **many** missions, so **addon/MAST changes must not break
existing scripts.** Adding labels/params is safe; renaming or changing the behavior
of an existing addon label/function is a breaking change — do it deliberately,
rebuild the mastlibs, and test the consumer missions (at minimum OpenUniverse,
SecretMeeting, WalkTheLine).

## Cross-repo coordination

Other agents may be editing **sbs_utils** (and the a2x layer) concurrently. Keep
sbs_utils edits minimal and coordinated — a branch+tag name collision once broke an
sbs_utils push. Prefer to make changes here in LM; when a change needs the library,
hand it off / batch it.

## Branches
- `main` (stable) and `v1.4.0_dev` (active development — do work here). Also
  `dev_djr`, `github_action`, `gh-pages`.
