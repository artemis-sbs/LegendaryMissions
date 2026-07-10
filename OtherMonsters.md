# Bestiary Expansion — Other Monsters

Five classic Artemis space monsters — **Shark, Dragon, Piranha, Charybdis,
Insect (NSECT)** — as LegendaryMissions bestiary prefabs, plus a **shared age system**
factored out of the Typhon.

> **STATUS: IMPLEMENTED** (headless-verified; browser pass pending). All five species
> ship as role-scoped prefabs over `behav_typhon`, alongside the existing bestiary
> (Typhon/Grazer/Ravener/Sparkfeeder/Reaver/Warden/Leech/Bulwark). Nothing touches
> `behav_typhon` or the base typhon path. What's built, and what still needs the
> browser, is tracked in **"Implementation status"** below; the design detail for each
> species follows, and the original wiki lore is in the appendix.

## Implementation status

**Done & headless-verified** (spawned all species in the LM `sandbox` map, ran 20s,
`PASS - no runtime errors`; packaged `--test` compiles clean):

- [x] **Shared age system** — `monster_roll_age` / `monster_bake_age` in
      [prefabs/prefab_helpers.py](prefabs/prefab_helpers.py); `prefab_typhon_classic`
      migrated onto it (Young Typhon hp=5000 confirmed).
- [x] **Insect** — [prefabs/insect.mast](prefabs/insect.mast) (hp 1500).
- [x] **Piranha** + **swarm** — [prefabs/piranha.mast](prefabs/piranha.mast)
      (`prefab_piranha` + `prefab_piranha_swarm`; 6-member swarm confirmed).
- [x] **Shark** — [prefabs/shark.mast](prefabs/shark.mast); new `ai_shark_hunt`
      (hunt prey / retaliate if provoked); age tiers (Mature Shark hp=6000).
- [x] **Charybdis** — [prefabs/charybdis.mast](prefabs/charybdis.mast); `ai_charybdis_drift`,
      teleport-attacker route, capped nebula trail (hp 20000).
- [x] **Dragon** — [prefabs/dragon.mast](prefabs/dragon.mast); apex chase + `dragon_regen`
      (black-hole-paused); biggest age tiers (Ancient Dragon hp=40000).
- [x] **Wreck → Piranha nest** hook (~30%) in [damage/destroy.mast](damage/destroy.mast).
- [x] **Registered** in [prefabs/__init__.mast](prefabs/__init__.mast) and added to the
      GM spawn menu ([gamemaster_comms/gamemaster_spawn.mast](gamemaster_comms/gamemaster_spawn.mast)).

**Still needs the browser** (damage-driven / render-only — the headless mock can't
drive these): Charybdis **teleport throw** + **nebula-trail render**, the
**wreck→swarm eruption** in live combat, and all **looks + bite-damage tuning**.

**Deferred:** Dragon's lootable **lair** (wiki 2.7) — not implemented this pass.

**Decisions taken** (change via metadata if desired): Shark `prey_role` defaults to
`grazer` (no space whale in Cosmos); Charybdis throws the attacker 30k–60k with an 8s
cooldown; Dragon heals +250/2s, paused within 6000u of a black hole.

---

## The bestiary pattern (what every new monster follows)

The existing species — `prefab_grazer`, `prefab_ravener`, `prefab_sparkfeeder`,
`prefab_typhon_classic` in [prefabs/](prefabs/) — are the template. Each new monster
is one `.mast` file in [prefabs/](prefabs/) containing:

1. **`=== prefab_<species>`** with a `metadata:` block (`type: prefab/monster`,
   `side: monster`, `health`, `scale`, and a `brain:` list of AI nodes + data).
2. Spawn as `npc_spawn(START_X, START_Y, START_Z, "<Name>", side + ",monster,<species>", "-", "behav_typhon")`.
   - `role("monster")` is the **umbrella** every generic system queries (spawn
     counts, `MONSTER_SELECT`). `role("<species>")` **scopes** the brain, damage
     routes and science routes so nothing leaks onto other monsters.
3. Set `monster_health` / `monster_health_max` / `local_scale_coeff` /
   `exclusion_radius` from metadata.
4. Set the **look** via `blob.set(...)` — `body_*_geom_filename`,
   `body_*_color`, `particle_color_*`, `beamColor`, and `beamDamage` for harmless
   species. (Available typhon geoms seen so far: `typhon-big-cube`, `typhon-balls`,
   `typhon-panel`; classic uses the default `drone_diffuse` bitmap.)
5. `clear_target(monster.id)`, `brain_add(monster, brain)`, `yield result to_id(monster)`.
6. **Damage routes** (`//damage/object if has_role(DAMAGE_TARGET_ID, "<species>")`)
   for reactive behaviour, and **science routes**
   (`//enable/science` + `//science if has_role(SCIENCE_SELECTED_ID, "<species>")`)
   with a `<scan>` block that teaches players what the creature is.
7. Register the file in [prefabs/__init__.mast](prefabs/__init__.mast).

**Reusable brain nodes** (LM [ai/npc_brains.mast](ai/npc_brains.mast)):
`ai_chase_player`, `ai_chase_npc`, `ai_chase_station`, `ai_chase_current`,
`ai_stay_close` (mini-jump to keep a monster in range), `ai_full_stop`,
`goto_object_or_location`. Species-specific behaviour goes in a new
`ai_<species>_*` node in the same file (see grazer's `ai_grazer_retaliate`).

---

## Cosmos calibration (READ before picking numbers)

The Quick-Stats in the appendix are **Artemis 2.x** values and are **not** Cosmos
numbers. Cosmos monster health is an order of magnitude higher — `prefab_typhon_classic`
runs 5000 / 15000 / 30000 by age; grazer 20000, ravener 8000, sparkfeeder 3000.
Preserve the **relative ranking** from the wiki (Insect < Piranha-individual <
Shark < Charybdis < Dragon) but scale into the Cosmos band. Proposed starting
points (tune in-engine):

| Monster    | Role       | Health (start)        | Scale | Speed feel | Reuse brain            | New mechanic |
|------------|------------|-----------------------|-------|------------|------------------------|--------------|
| Insect     | `insect`   | 1500                  | 0.5   | very fast  | `ai_chase_player` (high throttle) | none — simplest |
| Piranha    | `piranha`  | 800 (individual, swarm) | 0.4 | medium     | `ai_chase_npc/player`  | **wreck spawning + swarm** |
| Shark      | `shark`    | 6000                  | 1.0   | slow-hunt / fast-strike | new prey-hunt + retaliate | **hunt-prey-else-retaliate** |
| Charybdis  | `charybdis`| 20000                 | 1.3   | very slow  | drift / retaliate      | **teleport-attacker + nebula trail** |
| Dragon     | `dragon`   | 25000 (+ regen)       | 1.4   | fast       | `ai_chase_player/npc/station` | **self-regen + optional lair loot** |

Damage per bite scales up similarly — start near the base hull default and tune;
Dragon should bite hardest, Insect/Piranha weakest.

The Health column above is the **base / Mature** value. Shark and Dragon vary it by
life stage via the **shared age system** (Young/Mature/Ancient health + scale);
Insect, Piranha and Charybdis stay effectively flat. See "Shared age system" below.

---

## Per-monster implementation specs

### 1. Insect (NSECT) — easiest, do first
- **Behaviour:** weak, very fast, aggressive, always solo. Persistently chases the
  nearest ship, one bite per pass.
- **Implementation:** `prefab_insect` + `ai_chase_player` with a high `throttle`
  (e.g. 2.6) and a wide `SIZE_X`. Low health, small scale, cosmetic look. No new
  brain node needed.
- **Science scan:** "NSECT — a fast, aggressive but weak lifeform; more nuisance
  than threat."
- **Open Q:** none. This is the reference-simplicity build to validate the pattern
  against the merged typhon code.

### 2. Piranha — swarm from wrecks
- **Behaviour:** individually trivial, deadly in numbers; lurks in wrecks and rushes
  out at passing ships/monsters.
- **Implementation:** `prefab_piranha` = a single weak fast biter (`ai_chase_npc` +
  `ai_chase_player`). Then a **swarm spawner**: a `prefab_piranha_swarm` (or a
  helper label) that spawns N individuals in a tight cluster.
- **Wreck tie-in — mechanic already exists.** [damage/destroy.mast](damage/destroy.mast)
  already spawns `behav_wreck` terrain (`role("wreck")`) when a raider dies. Add a
  route/chance for a wreck to be a **piranha nest**: on wreck creation (or when the
  wreck is shot) roll a chance to `task_schedule` the swarm spawn at the wreck's
  position. This makes Piranha the one monster that can appear independent of the
  Monsters setting (matching the wiki).
- **Open Qs:**
  - Spawn-on-wreck-creation vs spawn-on-wreck-shot vs both? (wiki says both occur.)
  - Swarm size / difficulty scaling — fixed N, or tied to `DIFFICULTY`?
  - Do swarm members share an aggro target or each pick their own?

### 3. Shark — hunts whales, defends if attacked
- **Behaviour:** normally hunts/devours prey (space whales) and ignores ships;
  turns on ships **only if attacked**, then reverts to hunting when the attacker
  leaves. Slow while hunting, fast on the strike; one attack per pass.
- **Implementation:** `prefab_shark` + a new **`ai_shark_hunt`** node:
  1. If provoked (aggro timer running, like `ai_grazer_retaliate`) → chase the
     attacker, `force_shoot`.
  2. Else → seek nearest prey and pursue slowly.
  A `//damage/object if has_role(DAMAGE_TARGET_ID, "shark")` route sets the aggro
  timer (mirror grazer's retaliate route).
- **Prey question — needs the typhon-work answer.** The prey is "space whales."
  Confirm what role/prefab a whale is in the merged tree (a `behav_whale`? a tame
  bestiary species?). If no whale exists yet, either (a) make the grazer the shark's
  prey, or (b) ship the shark hunt-target as a configurable role in metadata
  (`prey_role: whale`) defaulting to whatever placid species exists.
- **Science scan:** "SHARK — a predator that hunts space whales; ignores ships
  unless provoked, then defends aggressively."
- **Age:** uses the **shared age system** (below) with meaningful tiers — declare an
  `ages:` block (Young/Mature/Ancient health + scale). Damage stays flat per the wiki.
- **Open Qs:** what is the canonical prey role?

### 4. Charybdis — peaceful teleporter, nebula trail
- **Behaviour:** largely peaceful; drifts slowly. If attacked, fires a "mouth" beam
  that **teleports the attacker across the map** (jump-drive effect) instead of
  dealing normal damage. Continuously **belches nebulae**, leaving a trail that caps
  speed to Warp 1 in its wake. Very tanky.
- **Implementation:** `prefab_charybdis`, mostly-drift brain + a
  `//damage/object if has_role(DAMAGE_TARGET_ID, "charybdis")` route that, instead of
  (or in addition to) retaliating, **relocates `DAMAGE_ORIGIN_ID`** to a random far
  point (jump effect). Plus a **nebula-trail sub-task**: periodically
  `terrain_spawn(...)` a nebula at the monster's current position (reuse the
  `terrain_spawn_nebula_*` helpers or a nebula prefab), on a timer, capped to a max
  trail length.
- **Open Qs:**
  - Teleport target — truly random, or pushed a fixed large distance along a random
    vector? Any cooldown so it can't chain-teleport a ship forever?
  - Nebula trail: spawn cadence, lifespan/cleanup (don't leak terrain), and whether
    the Warp-1 cap is real engine behaviour inside nebula or needs enforcing.
  - Is the teleport a *replacement* for damage or *in addition*? (wiki: it's the
    creature's weapon; it's otherwise passive.)

### 5. Dragon — apex predator, regen, optional lair
- **Behaviour:** extremely powerful, nearly always aggressive, prizes ships; closes
  fast, bites hard, grabs/drags a ship after a hit; **heals rapidly**; Ancients much
  tougher. Has a lootable **lair**. Can be baited into attacking enemy ships.
- **Implementation:** `prefab_dragon` + `ai_chase_player` / `ai_chase_npc` /
  `ai_chase_station` (highest priority on players), high health + biggest scale +
  hardest bite. **Self-regen:** a sub-task or `//damage` reaction that tops
  `monster_health` back toward `monster_health_max` over time (contrast ravener,
  which heals *only on being hit*; the dragon heals *passively/continuously*). Uses
  the **shared age system** (below) with the biggest tiers — Ancients much tougher
  and larger, damage unchanged.
- **Lair (stretch):** optional — a lootable lair object dropping torpedoes/energy
  like a raided pirate cache. Defer to a second pass; note it in metadata but don't
  block the core dragon on it.
- **Open Qs:**
  - Regen rate and whether it's exempt near a black hole (so it stays killable via
    the maelstrom, like ravener).
  - "Grab/drag" mechanic — is there engine support for latching onto a ship, or do
    we approximate with a `ai_stay_close` mini-jump + reduced ongoing damage?
  - Lair: in-scope now or explicitly deferred?

---

## New shared mechanics to build (cross-cutting)

These aren't per-species and may warrant helpers/nodes shared across the bestiary:

1. **Prey-hunting brain node** (`ai_hunt_prey` / `ai_shark_hunt`) — seek nearest
   member of a configurable prey role, pursue at a slow throttle. Reusable beyond
   Shark.
2. **Wreck → swarm hook** — extend [damage/destroy.mast](damage/destroy.mast) so a
   wreck can seed a Piranha swarm (chance-gated, difficulty-aware).
3. **Teleport-attacker** — relocate `DAMAGE_ORIGIN_ID` to a distant point with a
   cooldown; usable by Charybdis and potentially future creatures.
4. **Nebula trail sub-task** — timed nebula emission behind a moving object, with a
   capped trail and cleanup.
5. **Passive self-regen** — a sub-task that heals `monster_health` toward max over
   time, black-hole-exempt; Dragon uses it, others may opt in via metadata.
6. **Shared age system** — the Young/Mature/Ancient life-stage mechanic, factored
   out of `prefab_typhon_classic` into one reusable helper. **Full spec below.**

---

## Shared age system (first-class mechanic — build this first)

Every classic monster has a **life stage** — Young / Mature / Ancient — rolled once
at spawn and baked in permanently (Artemis 2.7+). Today that logic is copy-pasted
inline in `prefab_typhon_classic`. Factor it into **one shared helper** that every
age-varying species calls, so the roll, the health/scale bake, the stage role, and
the naming are defined in exactly one place.

**Home:** [prefabs/prefab_helpers.py](prefabs/prefab_helpers.py) (plain Python, the
existing helper module — imported into MAST via `import prefab_helpers.py`).

**API (two calls: roll before spawn so the name is right; bake after spawn):**

```python
MONSTER_AGE_STAGES = ("young", "mature", "ancient")

def monster_roll_age(ages):
    """Roll a life stage. `ages` is the metadata dict:
         { "weights": (y,m,a)|None,
           "young":  {"health": int, "scale": float, "label": "Young"},
           "mature": {...}, "ancient": {...} }
       Returns (stage:str, cfg:dict). Default weights 50/35/15 (young-heavy)."""
    weights = ages.get("weights", (50, 35, 15))
    stage = random.choices(MONSTER_AGE_STAGES, weights=weights)[0]
    return stage, ages[stage]

def monster_bake_age(monster, cfg, base_exclusion=200):
    """Apply a rolled stage's cfg onto a freshly spawned monster:
       monster_health(_max), local_scale_coeff, exclusion_radius. The stage ROLE
       is added at spawn (in the roles CSV) so it's queryable; caller passes the
       already-resolved name. Returns nothing."""
    monster.blob.set("monster_health_max", cfg["health"], 0)
    monster.blob.set("monster_health",     cfg["health"], 0)
    monster.blob.set("local_scale_coeff",  cfg["scale"], 0)
    monster.engine_object.exclusion_radius = int(base_exclusion * cfg["scale"])
```

**Metadata schema** — an age-varying prefab declares an `ages:` block instead of
flat `health`/`scale`. Optional `weights` biases the roll:

```
=== prefab_shark
metadata: ```
type: prefab/monster
side: monster
ages:
    weights: [50, 35, 15]
    young:   { health: 4000,  scale: 0.8,  label: Young }
    mature:  { health: 6000,  scale: 1.0,  label: Mature }
    ancient: { health: 9000,  scale: 1.3,  label: Ancient }
brain:
    - label: ai_shark_hunt
      data: { hunt_throttle: 0.8, strike_throttle: 2.4 }
```
    stage, cfg = monster_roll_age(ages)
    monster = npc_spawn(START_X, START_Y, START_Z, cfg["label"] + " Shark", side + ",monster,shark," + stage, "-", "behav_typhon")
    monster_bake_age(monster, cfg)
    # ... look, clear_target, brain_add, yield result ...
```

**Notes & rules:**
- The stage lands as a **role** (`young`/`mature`/`ancient`) via the spawn CSV, so
  brains and routes can gate on it — e.g. `ai_typhon_seek_death` already keys on
  `has_role(BRAIN_AGENT_ID, "ancient")`. Keep that contract: the shared roll writes
  the same three role names.
- **Age changes health + scale only — never damage** (wiki-accurate across all
  species). Bite/beam damage stays a per-species constant.
- **Ancient lifespan → seek-death** stays where it is (the `ancient` stage + a
  `lifespan` timer + `ai_typhon_seek_death`). Any species that should die of old age
  into a black hole rolls `ancient`, gets the timer, and includes that brain node.
- **Migrate `prefab_typhon_classic` onto the helper** as part of this work (replace
  its inline if/elif ladder with `monster_roll_age` + `monster_bake_age`) so there's
  a single implementation and the typhon is the proof it still behaves.
- **Which species use it:** Shark and Dragon get **meaningful** age tiers
  (health + size scale). Insect, Piranha and Charybdis had ages in 2.7 with little/no
  effect — give them age **optionally**: they may declare a flat single-stage `ages`
  (or skip the block and stay flat) so the science scan can still report a stage
  without materially changing the fight. Don't force tiers where the source game had
  none.

---

## Registration & verification checklist

- [x] One `prefabs/<species>.mast` per monster (Piranha ships `prefab_piranha` +
      `prefab_piranha_swarm` in one file).
- [x] Each `import <species>.mast` added to [prefabs/__init__.mast](prefabs/__init__.mast).
- [x] Species-specific brains (`ai_shark_hunt`, `ai_charybdis_drift`) live in each
      prefab file (same convention as grazer/ravener); no new shared brain file needed.
- [x] Wreck→Piranha hook added to [damage/destroy.mast](damage/destroy.mast).
- [x] Each species has a `//science` `<scan>` describing it (teach-by-scanning).
- [x] `--test` compiles clean; sandbox exercise ran all species 20s with no runtime
      errors. **Browser** pass still owed for look / teleport / nebula / regen render —
      never sign off on `--test` alone (the engine compiler is stricter than the mock
      and those effects are only real in-engine).
- [x] Confirmed nothing touched `behav_typhon` or the base typhon path — each species
      is role-scoped.
- [x] Rebuilt the prefabs mastlib into `__lib__`; **rerelease on push** so missions
      pick up the new species.

---

## Summary target sheet

| Monster    | Health   | Top Speed | Pod? | Damage    | Range   |
|------------|----------|-----------|------|-----------|---------|
| Shark      | 100-200  | 1.8       | N    | 30        | Contact |
| Dragon     | 700-1300 | 1.8       | N    | 168       | Contact |
| Piranha    | 27-31    | 1.2       | Y    | 6         | Contact |
| Charybdis  | 400      | 0.8       | N    | Teleport  | 1000    |
| NSect      | 60-100   | 2.4       | N    | 10        | Contact |

*(Artemis 2.x reference values — see Cosmos calibration above; scale up, keep the
ranking.)*

---

# Appendix — original Artemis lore & stats (reference)

Preserved verbatim from the Artemis wiki for flavour text, science-scan copy, and
behaviour intent. Prefab names in the source game: `monster_shark`, `monster_dragon`,
`monster_piranha`, `monster_charybdis`, `monster_insect`.

## Shark
Common Name: Shark — Scientific Name: Celestius Megalodonis

Science-screen description: "A ferocious predator that feeds on starships and their
crews, posing a danger to commercial and military shipping. Unlike whales, no
government protects sharks and some encourage hunting them to extinction."

The Space Shark is a predatory space-dwelling creature that feeds on Space Whales.
Despite its chitinous exoskeleton and fearsome appearance, it shares features with
the Space Whale (fluked tail; jelly-like structure under its carapace — arthropod-like).
It normally hunts and devours Space Whales, ignoring all other monsters and ships. If
attacked, it defends itself aggressively — only slightly stronger than the NSECT
(~2× its damage capacity), considerably slower when hunting but reacts with surprising
speed if a ship gets in range. Its jagged teeth do respectable hull/shield damage;
after attacking it must circle around for another pass, and it loses interest if a
ship moves away, resuming its hunt. Age (2.7+) sets health: Young 100, Mature 150,
Ancient 200; age does not change damage. Drops two or three anomalies when killed.

## Dragon
Common Name: Dragon — Scientific Name: Draconis Colligator

Science-screen description: "A very tough and dangerous creature known to hoard items
found in deep space, including entire vessels and their crews. Some dragons have shown
signs of intelligence."

The Space Dragon is a dangerous predator feared by Transports. Instinctively attracted
to bright/shiny metal; clamps down with massive jaws and drags prey back to its lair
(hence the "hoarding" name). Extremely powerful and nearly always aggressive; can be
baited into attacking enemy ships (risky to the TSN captain too). Fan-like "wings"
propel it with remarkable speed (keeps up with a Light Cruiser at 300% impulse; no
warp). Jaws do great damage (can drop a Light Cruiser's shields, seriously damage a
Dreadnought/Battleship) but it typically stops attacking once it grasps a ship to drag
it; once shields are down it only does 1 point of system damage per bite. Can be evaded;
may lose interest at distance — but may switch to a friendly vessel or base. As of 2.7:
in-game lootable lair; bites harder; heals rapidly; Ancients much larger/tougher (no
change to damage/speed). Drops lots of anomalies (4+). High health + regen means it may
take several ships firing nukes together to kill, especially an Ancient.

## Piranha
Common Name: Piranha — Scientific Name: Dentosicus Scorpius

Science-screen description: "Swarming creatures with an affinity for nebulae, sometimes
attack passing ships and feed on their cargo."

Vicious, ravenous scavenger that feeds exclusively on metal. Individually weak, but
travels in swarms able to tear apart even powerful starships. Lurks in empty hulks of
destroyed ships and springs out at salvagers. Not usually found in open space — instead
derelicts labelled "WRECK" appear; when an enemy ship is destroyed a WRECK appears too.
Some wrecks are harmless (drop a few anomalies when shot); some house a swarm that
rushes out at passing ships/monsters; some spawn only when the wreck is shot. Chews
through the toughest shields, then devours hull. 2.7 age has no significant effect on
Piranha. Roaming Piranha require "Lethal Terrain" ≠ None, but they spawn from Wrecks
regardless — the only monster that can appear regardless of the Monsters setting.

## Charybdis
Common Name: Charybdis — Scientific Name: Consectrus Plicatus

Science-screen description: "A hardy, mysterious creature capable of folding the fabric
of space itself. Its life functions produce nebula clouds as a waste product. Its
methods of feeding and reproduction are unknown."

A mystery. Hardened outer carapace TSN sensors can't penetrate; possibly a Doomsday
Weapon rather than a living thing. Largely peaceful; theorised to absorb stellar
background radiation (more active in star systems). Its byproduct is nebulae — it belches
them out, leaving a trail in its wake. Massive shell withstands 3 direct Nuke hits; the
nebulae act as natural defence, preventing travel faster than Warp 1. If attacked, it
circles and fires a beam from its "mouth" causing its attacker to **Jump across the map**
(Jump-Drive-like effect). Much more dangerous alongside other threats — combined with a
Typhon it's doubly dangerous (caps speed to Warp 1, preventing escape). 2.7 age doesn't
change health; always generates the original purple nebula. Drops a huge amount of
anomalies (8+) when killed.

## Insect (NSECT)
Common Name: Insect / Bug — Scientific Name: Pulciem Subunae

Science-screen description: "Mildly dangerous creature with a pronounced stinger. Its
sting can paralyze other space creatures or occasionally damage a starship."

The weakest spacegoing organism in TSN space (individual Piranha are weaker but swarm).
Voracious; feeds on metallic and organic material; often harasses BioMechs. Fairly weak
and easily destroyed (absorbs about as much as an unshielded ship) but extremely
aggressive and persistent; bite deals little damage and it must circle for another
attack. Small size makes it extremely fast — regularly outruns BioMechs and moves across
the sector faster than any sublight ship (no warp). Only ever found alone (fortunately —
a swarming NSECT would be a serious threat). 2.7 age: Young 60 / Mature 80 / Ancient 100
health; older individuals slightly larger. Typically drops two anomalies when killed.
</content>
</invoke>
