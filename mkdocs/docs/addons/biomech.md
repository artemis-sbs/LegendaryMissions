# BioMech

**BioMechs** are a self-contained creature: a swarm that drifts **neutral**, feeds on
asteroids, and only turns on you when provoked — then wakes as a **collective mind**,
**evolves through four stages**, and (at Stage 4) **breeds** and can be **hailed**.
They power the Siege **Infestation** boss, but the addon is reusable in any mission.

Cosmos has no built-in BioMech AI, so the whole lifecycle is scripted here.

> This page is for **authors**. BioMechs appear in play as the Siege
> [Infestation boss](../script/bosses.md).

---

## Add it to your mission

Add the `biomech` addon (it uses the `ai` brains and `prefabs`) to your `story.json`
`mastlib` list:

```json
{
    "mastlib": [
        "artemis-sbs.LegendaryMissions.ai.v1.4.0.mastlib",
        "artemis-sbs.LegendaryMissions.biomech.v1.4.0.mastlib"
    ]
}
```

The four stages are shipData keys **`biomech_a` … `biomech_d`** (art Drone1–4). Each is
a full ship template, so a stage's stats come from its shipData — see
[Evolving](#evolving-by-respawn).

---

## Spawning

One spawn path, `biomech_spawn`, is shared by everything — so stage art, roles, and the
brain are defined once.

```
# Python-callable from MAST:
bid = biomech_spawn(x, y, z, art="biomech_a", roles="biomech, raider", name="BioMech")
```

Or via the prefab (a thin wrapper over `biomech_spawn`):

```
prefab_spawn(prefab_biomech, {"START_X": x, "START_Y": y, "START_Z": z})
```

A fresh BioMech spawns **passive** (Stage 1) on the neutral side.

### The infestation driver

`biomech_infestation` is a ready-made, self-contained swarm: spawn an initial group,
evolve them, and — once a Stage 4 matures — breed litters of Stage 1, bounded by a
population cap and a fixed cycle count so it stays winnable. Schedule it, or name it as
a boss `Hook:`. All data vars are optional:

| Var | Default | Meaning |
|---|---|---|
| `INFEST_COUNT` | 8 | Initial swarm size. |
| `INFEST_CAP` | 12 | Population cap (plus `DIFFICULTY`). |
| `INFEST_CYCLES` | 10 | How many grow/breed cycles before it stops. |
| `INFEST_WAVE` | 25 | Seconds between cycles. |
| `INFEST_ROLES` | `biomech, raider` | Roles for each spawn. |
| `INFEST_X/Y/Z` | 0 | Center of the infestation. |

```
prefab_spawn(biomech_infestation, {"INFEST_COUNT": 10, "INFEST_X": px, "INFEST_Z": pz})
```

---

## Behavior

### Passive & neutral (Stages 1–3)

BioMechs live on a neutral side (`BIOMECH_PASSIVE_SIDE`, default `biomech`) that nothing
is hostile to — so players won't auto-engage a feeding hull. The `ai_biomech_feed` brain
drifts each hull toward the nearest **asteroid** to feed; it does not shoot. (Give the
map asteroids, or passive hulls simply idle.)

### Collective mind — provoked, and bounded

Attacking any BioMech wakes the hive — but **bounded to an aggro radius**
(`BIOMECH_AGGRO_RADIUS`, default 9000), an area effect, not the whole sector. The woken
hulls flip to **enraged**, target the attacker, and switch **per-object** to a hostile
side (`BIOMECH_ENRAGED_SIDE`, default `raider`) — so only the local swarm turns hostile.
`ai_biomech_hunt` then chases and fires. This is wired automatically via a
`//damage/object` route.

```
biomech_enrage(hit_id, attacker_id)   # wake the hive around hit_id (also fired by the damage route)
biomech_calm(center_id=None)          # soothe back to passive/neutral (whole hive, or around a center)
```

> If `BIOMECH_ENRAGED_SIDE` isn't a registered side in your mission, the side switch is a
> safe no-op and the swarm still fights (the brain fires regardless) — it just won't
> recolor on radar.

### Stage 4 — sentient

A mature (`biomech_d`) hull is **hailable**: a `//comms` route lets your comms officer
**calm** the hive (a chance to soothe it) or **taunt** it (enrage). Comms only opens on a
BioMech the mission has **science-scanned** — listen for the `biomech_stage4` signal and
scan that hull so the hail becomes available exactly when it matters.

### Evolving by respawn

Evolving **respawns** a hull at the next stage's shipData key (full stage stats) at the
old hull's position, then deletes the old one — it is **not** an `art_id` swap (that
would change only the model and keep the earlier stage's stats). An enraged hull stays
enraged across the respawn.

```
biomech_evolve()          # promote one random pre-Stage-4 hull; returns the new id (0 if all Stage 4)
```

---

## Signals

React with a `//signal/<name>` route. The addon stays quest-agnostic — bridge these to
`quest_signal` yourself if a quest should react.

| Signal | Data | Fires |
|---|---|---|
| `biomech_enraged` | `{attacker, woke}` | the hive wakes (passive → enraged); once on the transition, not per hit |
| `biomech_calmed` | `{}` | the whole hive returns to passive |
| `biomech_evolved` | `{id, stage, art}` | a hull evolves a stage (`stage` is 0-based; 3 = Stage 4) |
| `biomech_stage4` | `{id}` | the **first** hull reaches Stage 4 (breeds + hailable) |

```
//signal/biomech_stage4
    # A Stage 4 has matured - scan it so the hail comms opens.
    science_set_scan_data(role("__player__"), SIGNAL_DATA["id"], "")
    ->END
```

---

## API summary

| Function | Purpose |
|---|---|
| `biomech_spawn(x,y,z,art,roles,name)` | The single spawn path (hull + brain). Returns the id. |
| `biomech_evolve()` | Respawn one hull at the next stage. |
| `biomech_enrage(hit_id, attacker_id, radius=None)` | Wake the hive around `hit_id` (bounded). |
| `biomech_calm(center_id=None, radius=None)` | Soothe hulls back to passive/neutral. |
| `biomech_count()` | Live BioMech count. |
| `biomech_stage(obj)` | Stage index 0–3 of a hull. |
| `biomech_has_stage4()` | Whether any hull has reached Stage 4. |

**Config constants** (override per mission): `BIOMECH_AGGRO_RADIUS`,
`BIOMECH_PASSIVE_SIDE`, `BIOMECH_ENRAGED_SIDE`, `BIOMECH_STAGE_ARTS`, `BIOMECH_BRAIN`.
