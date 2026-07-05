# Writing a Siege boss

The **Siege** map can end with a **boss** — a named flagship, reinforcement fleets,
or a bespoke threat that arrives when the raiders thin out. Bosses are **data-driven
and folder-scanned**: drop a file in `maps/bosses/` and it appears in the Siege
**Boss** dropdown automatically, with no code change.

A boss is up to two co-located files:

| File | Required? | Holds |
|---|---|---|
| `maps/bosses/<key>.amd` | **yes** | the boss **config** (how it spawns) + its **objectives** |
| `maps/bosses/<key>.mast` | optional | boss-specific **logic / comms** (only if the boss needs bespoke behavior) |

The `.amd` is authored in the **shared AMD quest vocabulary** — the same grammar
Open Universe uses — so learning to write a Siege boss is a stepping stone to
authoring a full universe.

---

## The config file: `<key>.amd`

One heading defines the boss; its fenced block is the spawn config. `##` sub-headings
below it are the boss's objectives (see [Objectives](#objectives)).

```amd
# [Warlord](warlord)
---
Trigger: enemies_low
Low: 25%
Flies: 50% Kralien, 50% Torgoth
Fleets: 2
Difficulty: +1
Named: Warlord kralien_dreadnought
---
A raider warlord and their honor guard warp in to break the defenders.
```

The heading text (`Warlord`) is what shows in the **Boss** dropdown; the key
(`warlord`) matches the filename.

### Config fields

| Field | Meaning | Example |
|---|---|---|
| `Trigger:` | How the boss arrives. `enemies_low` = spawn once when the raiders thin; `continuous` = respawn waves until the clock runs out. | `enemies_low` |
| `Low:` | (enemies_low) Fraction of the **peak** enemy count the raiders must drop below before the boss triggers. | `25%` |
| `Flies:` | Race makeup for the boss's fleets — a single race or a weighted mix. | `50% Kralien, 50% Torgoth` |
| `Fleets:` | How many fleets to spawn (wave size). | `2` |
| `Difficulty:` | Boss difficulty relative to the game's, or absolute. `+2` / `-1` / `7`. | `+1` |
| `Named:` | Named flagship hulls — `Name shipDataKey`, comma-separated. | `Warlord kralien_dreadnought` |
| `Wave:` | (continuous) Seconds between waves. | `45` |
| `Hook:` | A MAST label to run for bespoke behavior beyond the config spawn (see [Hooks](#hooks)). | `biomech_infestation` |

Only the fields a boss needs. A pure "named flagship + reinforcements" boss (Warlord)
needs no `.mast` file at all — the generic engine spawns everything from the config.

### Objectives

Each `##` sub-heading is a quest attached to the siege. Author it in the shared quest
vocabulary and parent it to `siege_mission` so it joins the siege's mission tree:

```amd
## [Defeat the Warlord](defeat_warlord)
---
Scope: shared
State: active
Parent: siege_mission
Required: true
Goal: destroy 1 warlord
Pays: 500 credits
---
Destroy the raider Warlord to break the siege for good.
```

| Key | Meaning |
|---|---|
| `Parent: siege_mission` | Joins the siege's mission tree (so it counts toward the end-game). |
| `Required: true` | The siege isn't won until this objective completes. |
| `Critical: true` | Failing this objective **loses** the game. |
| `Goal:` | The completion trigger — `destroy N <role>`, `scan`, `dock`, `reach`, `collect`, … |
| `When: signal <name>` | Complete when a signal fires (e.g. `When: signal xorn_defected`). |
| `Pays:` | Reward on completion (credits / items). |

`Goal: destroy 1 warlord` counts kills of anything with the `warlord` role — which
the `Named:` flagship carries automatically.

---

## Hooks

A `Hook:` names a MAST label the boss runs (once) after its config spawn, for behavior
the config can't express. The label is scheduled with the boss config in scope, so it
can read `BOSS_SELECT`. This is how the **Infestation** boss drives its swarm:

```amd
# [Infestation](infestation)
---
Trigger: enemies_low
Low: 40%
Hook: biomech_infestation
---
```

`biomech_infestation` lives in the reusable **biomech** addon, not the boss file —
**reusable behavior belongs in an addon**, and the boss just points at it. Keep
boss-*specific* logic in the boss's own `.mast`.

---

## The logic file: `<key>.mast`

When a boss needs bespoke logic or comms, put it in `maps/bosses/<key>.mast`, beside
its config, and import it from `maps/__init__.mast`:

```
# maps/__init__.mast
import bosses/ragnarok.mast
import bosses/continuous.mast
```

**Gate every route/label so it's inert unless that boss is active.** Ragnarok's Xorn
defection is a `//comms` route gated on the `xorn` role (only present when Ragnarok
spawns) and `SIEGE_ACTIVE`, so loading it for every game never mis-fires:

```
//comms if SIEGE_ACTIVE and has_role(COMMS_SELECTED_ID, "xorn") and not has_role(COMMS_SELECTED_ID, "defected")
    + "Appeal to Xorn: turn on Ragnarok":
        <<[cyan] "XORN"
            % Ragnarok betrayed the fleet. I am yours.
        remove_role(COMMS_SELECTED_ID, "raider")
        add_role(COMMS_SELECTED_ID, "defected")
        COMMS_SELECTED.side = COMMS_ORIGIN.side
        brain_clear(COMMS_SELECTED_ID)
        brain_add(COMMS_SELECTED_ID, "ai_chase_npc", {"force_shoot": True, "throttle": 2.2})
        signal_emit("quest_signal", {"SIGNAL_NAME": "xorn_defected"})
```

The `signal_emit("quest_signal", …)` completes the `When: signal xorn_defected`
objective — this is how boss logic and boss objectives talk to each other.

---

## Add a boss in three steps

1. **Write `maps/bosses/<key>.amd`** — a `# [Display](key)` heading with the config
   fields, and one or more `##` objectives parented to `siege_mission`.
2. **(Optional) add `maps/bosses/<key>.mast`** for bespoke comms/logic, gated on your
   boss's role/flag, and `import bosses/<key>.mast` in `maps/__init__.mast`.
3. **Playtest** — the boss is already in the **Boss** dropdown (folder scan). Verify
   headless first (`sbs debug . --no-gui --map siege`), then in the engine.

---

## The shipped bosses

| Boss | Trigger | Highlight |
|---|---|---|
| **Warlord** | enemies_low | Named enemy flagship + reinforcement fleets. Config-only, no `.mast`. |
| **Continuous** | continuous | Endless waves until the clock nears its end, then the attackers break off (defender win). Logic in `continuous.mast`. |
| **Ragnarok** | enemies_low | The renegade "42 Fleet" — a juggernaut you beat, or hail **XORN** to defect. Logic in `ragnarok.mast`. |
| **Infestation** | enemies_low | A **BioMech** swarm that evolves and breeds, via the biomech addon `Hook`. |

Read those four in `maps/bosses/` as working templates.
