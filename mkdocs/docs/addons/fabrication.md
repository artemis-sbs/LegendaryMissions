# Fabrication & Sensor Beacons

The **fabrication** addon adds an Engineering **Fabricate** tab that turns materials
into gear over a **build timer**, and a **Cargo** tab that manages what the ship
carries. Its headline content is **Beacons** — a **fabricate-only** ordnance the crew
builds, delivers to the tube, fires, and later recovers.

Beacons fold in the old Artemis 2.8 **Probe**: the passive **Sensor Beacon** kind *is*
the Probe brought forward (see [Porting](#porting-from-28-probe)).

> This page is for **authors**. Recipes are authored as **data** (AMD), so a mission
> can add its own beacons and craftables without touching the addon.

---

## Add it to your mission

Add the `fabrication` addon to your `story.json` `mastlib` list. It uses the standard
`consoles` (for the Engineering tab), `items`, and `prefabs`:

```json
{
    "mastlib": [
        "artemis-sbs.LegendaryMissions.consoles.v1.4.0.mastlib",
        "artemis-sbs.LegendaryMissions.items.v1.4.0.mastlib",
        "artemis-sbs.LegendaryMissions.prefabs.v1.4.0.mastlib",
        "artemis-sbs.LegendaryMissions.fabrication.v1.4.0.mastlib"
    ]
}
```

Loading it puts the **Fabricate** and **Cargo** tabs on the Engineering console (via a
`//gui/normal_engi` route) and registers the built-in recipes.

---

## The build → deliver → fire loop

Beacons are **fabricate-only**: a player ship carries beacon *capacity* (`Beacon_MAX`)
but spawns with **0 loaded rounds** — a `//spawn` route zeroes `Beacon_NUM` so the
prefab registrar can't top it off. The only way to a loadable round is to build one.

By design the loop is **slow and comms-heavy — the coordination is two humans talking**:

1. **Weapons tells Engineering what to make** — which beacon, and (for a Bio Beacon)
   which monster and whether to **attract** or **repel**. There is no request signal;
   it's a spoken hand-off.
2. **Engineering fabricates** it on the **Fabricate** tab: pick the recipe, set its
   program, and **Build**. The build consumes the recipe's **Inputs** and runs a
   **build timer**; the finished beacon lands in cargo (`beacon_built`), built but
   **not yet loaded**.
3. **Engineering delivers** one from the **Cargo** tab — **Deliver to Weapons**. Only
   delivery raises the ship's loadable tube count (`Beacon_NUM`, capped at
   `Beacon_MAX`) and queues the beacon's **program** (FIFO, matching fire order).
4. **Weapons fires** the Beacon through the stock tube UI. The fired round is harmless;
   on `//launch/missile` the addon drops a **real broadcasting beacon ~635u aft**,
   stamped with the next queued program.

Engineering can also **Eject** a built beacon from Cargo — it drops as an **inert but
recoverable** anomaly instead of being delivered.

---

## Beacons in space

A deployed beacon is a scannable object (role `beacon`) that lives until its power
fades:

- **Bio Beacon** — broadcasts an ultrawave carrier that **attracts** or **repels**
  matching [space monsters](biomech.md) across a wide radius (default 50 000u), steering
  them toward the beacon or away from it until it expires (~120s).
- **Sensor Beacon** — a passive **sensor relay** (the 2.8 Probe). It drops and scans
  like any beacon; its program carries a `range` (`medium` / `long`) for the sensor
  sweep to read.
- **Science** can scan any beacon to read its program (kind, target, attract/repel).
- **Recover** a beacon by **flying over it** — it adds a loadable round back
  (`Beacon_NUM` +1) and re-queues its program, so the recovered round keeps its
  behaviour when relaunched.

---

## Recipes are data (AMD)

Recipes live in `recipes.amd` — one heading per recipe. The Fabricate tab lists them;
a build consumes the **Inputs** and, after **Time** seconds, yields the **Output**.
Beacon recipes (`Output: Beacon`) also carry a **Program** (the beacon `kind`) and a
**Properties** grid — the monster and attract/repel the Weapons officer asked for,
chosen at build time. A non-beacon recipe just grants its Output into the ship
inventory.

<!-- amd:begin excerpt fabrication/recipes.amd#recipe_beacon_bio -->
```amd
## [Bio Beacon](recipe_beacon_bio)
---
Output: Beacon
Inputs: bio_sample x1, salvage x5
Time: 30
Build at: engineering
Program: kind=bio
Properties:
  Monster: 'gui_drop_down("list: shark, dragon, piranha, leech, charybdis, grazer, any", var="monster")'
  Mode: 'gui_drop_down("list: attract, repel", var="mode")'
Defaults:
  monster: shark
  mode: attract
---
A distress-beacon hull rewired to broadcast an ultrawave carrier that attracts or repels a
chosen space monster across the sector.
```
<!-- amd:end -->

<!-- amd:begin excerpt fabrication/recipes.amd#recipe_beacon_sensor -->
```amd
## [Sensor Beacon](recipe_beacon_sensor)
---
Output: Beacon
Inputs: salvage x8
Time: 20
Build at: engineering
Program: kind=sensor, range=medium
---
A passive relay that brightens sensor returns around its position - a future kind; drops and
scans like any beacon. The standard (medium-range) build. Replaces the 2.8 Probe.
```
<!-- amd:end -->

The addon ships with **Bio Beacon**, **Sensor Beacon**, **Sensor Beacon (Long Range)**,
and a non-beacon **Coolant Cell** (proving the Fabricator builds more than beacons). A
mission can author its own `.amd` recipes and load them with
`fabrication_load_recipes_amd(...)`.

---

## Porting from 2.8 (Probe)

The 2.8 **Probe** has no Cosmos torpedo type, so the [`a2x` porting
layer](https://artemis-sbs.github.io/sbs_utils/mast/porting-2x/) maps it to a **Sensor
Beacon**:

| 2.8 property | a2x behaviour |
|---|---|
| `missileStoresProbe`, `countProbe` (set) | writes the loadable count `Beacon_NUM` |
| `missileStoresProbe`, `countProbe` (add-to) | fabricates that many Sensor Beacons into cargo (`beacon_built`) |
| `missileStoresBeacon`, `countBea` | maps directly to the `Beacon_NUM` store |

So a converted 2.8 mission that stocked Probes comes across as Sensor Beacons the crew
can deliver and fire.

---

## Signals & state

The console tabs only emit `//shared/signal` intents; the state changes live
server-side (once) in `beacon_workflow.mast` / `fabrication.mast`.

| Signal | Data | Does |
|---|---|---|
| `beacon_build` | `{ship_id, recipe, program}` | consume inputs, start the build timer |
| `beacon_deliver` | `{ship_id, kind, monster, mode}` | raise `Beacon_NUM`, queue the program |
| `beacon_eject` | `{ship_id, kind, monster, mode}` | drop a built beacon as an inert pickup |
| `fabricate_recipe` | `{ship_id, key}` | build a non-beacon recipe into inventory |
| `cargo_eject` | `{ship_id, key}` | jettison one held item/material |
| `item_changed` | `{holder_id}` | refresh any open Fabricate/Cargo panel |

**Per-ship state:**

- `beacon_built` (inventory) — list of `{kind, monster, mode}` built-but-undelivered beacons.
- `Beacon_NUM` (data_set) — the loadable tube count; **only delivery raises it**.
- `beacon_program_queue` (inventory) — FIFO of programs, one per delivered-but-unfired round.

---

## API summary

| Function | Purpose |
|---|---|
| `fabrication_recipes()` | All recipes (for the Fabricate list). |
| `fabrication_get_recipe(key)` | Resolve one recipe by key. |
| `fabrication_recipe_affordable(ship_id, key)` | Can the ship afford the inputs? |
| `fabrication_recipe_consume(ship_id, key)` | Spend the recipe's inputs. |
| `fabrication_load_recipes_amd(doc)` | Register recipes from an AMD document. |
| `cargo_list(ship_id)` | Everything the ship carries (beacons + items + materials). |
