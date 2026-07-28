# Peacetime multiplayer — quest isolation, leaderboard, and claim-jumping

A plan to make the peacetime job board safe (and fun) with **multiple player ships**.
Today the board is single-crew in spirit but multi-ship in practice, and the wiring
makes multi-ship *forced co-op with shared fate* — including accidental griefing. This
plan adds a per-job **ownership mode** so a mission can pick its social contract:

| Mode | Targets | Credit | Interference | Use |
|---|---|---|---|---|
| **shared** | one set, spawned once | **all** holders | n/a (co-op) | co-op crews (legacy default) |
| **owned** | **per accepter**, owner-tagged | **owner only** | blocked (no grief) | **Peacetime default — no claim jumping** |
| **contested** | shared/contested set | **whoever delivers** | allowed (tether-steal etc.) | opt-in competitive / grief-as-mechanic |

**Peacetime ships as `owned`.** A dedicated competitive variant can flip jobs to
`contested`. `shared` stays for cooperative missions.

---

## 1. What happens today (the problem)

Jobs are granted **per ship** (each player ship has its own copy of every quest), but
**targets and completion are shared/global**:

- Two ships can accept the same job, but the targets spawn **once** (`pr_job_active` =
  "any player accepted" → `pr_job_dispatch` spawns one set, once-guarded).
- Completion is a **broadcast** `quest_signal` (`barge_delivered`, `drone_down`, …) and
  `quest_on_signal` advances **every** ship holding that quest → one ship's delivery
  **pays everyone** who accepted, and one ship destroying a "don't-destroy" target
  **fails it for everyone**.
- The nested arcs are worse: a single server sequencer advances **all** holders off
  global step signals, and a **late accepter** misses the already-done steps and can
  never complete the parent (latent bug).

Root causes: **one shared set of world objects**, and **credit goes to "everyone
holding the quest," not to whoever did the work.**

---

## 2. Building blocks

### 2a. Ownership model
On accept, tag each accepter's targets with the owner:
- `set_inventory_value(target, "quest_owner", ship_id)`
- `add_role(target, "owned")` and `link(ship_id, "quest_targets", target)` (so a ship's
  set is queryable / cleanable).
- Helpers: `quest_owner_of(target)`, `is_quest_owner(ship, target)`,
  `quest_owned_targets(ship)`.

### 2b. Spawn-per-accept (instancing)
Replace "spawn once for the first accepter" with "spawn a set **for each** accepter"
for `owned`/`contested` jobs:
- `pr_job_dispatch` tracks a **per-ship spawned set** (not a single flag) so re-accept
  doesn't double-spawn, and a *late* accepter still gets their instance.
- **Spatial isolation:** place each ship's instance in its own pocket — near the owner,
  or a per-ship offset lane — so instances don't overlap/collide.
- **Cap** concurrent instances (perf); only ACCEPTED jobs instance (already true), and
  bound N ships × M jobs. Log any cap hit.

### 2c. Owner-scoped completion
The quest driver **already** credits the actor for some triggers — `on_kill` credits the
killer, `on_scan` the scanner, `on_dock` the docker. The peacetime jobs currently throw
that away by converting everything to a **broadcast `signal`** via routes. The fix is
per job-type:

- **Kill / scan / dock jobs** → author the goal as the **native actor trigger**
  (`Goal: kill N …`, `Goal: scan N …`, `Goal: dock …`) so the *actor* is credited,
  **plus** an ownership gate so a ship only gets credit for **its own** targets (check
  `quest_owner == actor` in the `//damage`/`//science` route before crediting).
- **Delivery / proximity jobs** (tow to DS 1, tow to a point) have no native actor
  event — a **server watcher** detects the *owned* object at its destination and credits
  **only the owner** (advance the owner's quest directly instead of broadcasting).
- **Multi-step arcs** → a **per-ship sequencer**: each accepter runs their own arc
  instance over their own targets, so steps/credit are isolated *and* the late-join race
  disappears (no shared sequencer).

### 2d. The mode dial
- Per-job AMD field `Mode: shared|owned|contested` (default from a mission setting, e.g.
  `QUEST_MODE`, peacetime → `owned`).
- Read at grant/dispatch time; drives instancing + completion + guarding.

### 2e. Interaction gating (the "no grief" guard)
For `owned`, a non-owner must not be able to *complete, steal, or ruin* a task:
- **Soft (cheap, do first):** non-owner actions **don't credit and don't consume** — the
  completion watcher ignores non-owner deliveries/kills; the object stays the owner's.
- **Hard (full protection):** a non-owner physically **can't touch** an owned target:
  - **Grav-tether policy:** `grav_tether_attach` refuses when the target is owned by
    another ship (a policy hook on the sbs_utils primitive).
  - **Damage protection:** owned targets ignore non-owner weapon damage (a mission-side
    damage guard / data_set flag), so a stray or malicious shot can't fail the owner.
- For `contested`, gating is **off** — interference is the point.

---

## 3. The competitive layer

### 3a. Per-ship earnings + leaderboard
Credits currently bank on the **side** (`to_side_id`), so same-side ships share a pool —
useless for a race. Add a **per-ship earned** tally (`set_inventory_value(ship,
"pt_earned", …)` on each owner-scoped completion) and:
- a live standings widget (helm/comms) and
- a **ranked** Credits-Earned table on the results screen (extends the row we just added).

### 3b. Claim-jumping (`contested`)
Built on the same ownership tags, but the rules invert:
- targets are shared/contested (or ownership transfers to whoever grabs them),
- **delivery credits the deliverer**, others get nothing (or keep contesting),
- interference is allowed — and the **grav-tether is the star**: snatch a rival's
  salvage, tow their barge off course, reel their cargo away. This is where "allow
  griefing" becomes a *feature*, cleanly separated from peacetime's `owned` default.

---

## 4. Phased build order

- **Phase 0 — Primitives.** Ownership tag/query helpers; the `Mode` field + `QUEST_MODE`
  setting; per-ship spawned-set tracking in the dispatcher.
- **Phase 1 — OWNED proof (one job).** Instance the **Barge** per accepter (owner tag +
  per-ship spawn + owner-scoped delivery watcher + **soft** guard). Verify with **two
  browser-mock clients** that A's barge ≠ B's barge and only the tower is paid.
- **Phase 2 — Hard guard.** Grav-tether refuses non-owner targets; owned targets ignore
  non-owner damage. Re-verify no-grief with two clients.
- **Phase 3 — Roll OWNED across peacetime.** Convert kill/scan/dock jobs to native actor
  triggers + ownership gate; delivery jobs to owner watchers; arcs to **per-ship
  sequencers** (also fixes the late-join race). Peacetime setting → `owned`.
- **Phase 4 — Leaderboard.** Per-ship `pt_earned`; live standings; ranked results table.
- **Phase 5 — CONTESTED.** Claim-jumping mode + the tether-steal mechanic; a competitive
  peacetime variant that sets `QUEST_MODE = contested`.

Phases 0–3 deliver **safe multi-ship peacetime** (the priority). 4 adds the fun race. 5
is the spicy stretch.

---

## 5. Risks / unknowns

- **Perf & clutter:** N ships × accepted jobs × targets. Only accepted jobs instance;
  cap concurrent instances; reuse per-ship lanes; despawn on complete/abandon.
- **Spatial layout:** where each ship's instance goes without instances colliding or a
  ship stumbling into another's. Per-ship offset lanes, or spawn relative to the owner.
- **Driver crediting:** confirm exactly which triggers are actor-scoped vs broadcast
  (`on_kill`/`on_scan`/`on_dock` credit the actor; `on_signal` broadcasts) — the plan
  leans on the actor-scoped ones + ownership gates.
- **Grav-tether ownership hook** lives in sbs_utils (the primitive) — a policy callback
  so LM can veto a non-owner attach without hard-coding quest logic into the library.
- **Shared `quest_driver` changes** touch every LM mission — keep behavior identical for
  `shared` (the default) so nothing regresses; `owned`/`contested` are opt-in.
- **Testing multiplayer** is browser-mock-only headless (two `/client` tabs get distinct
  IDs); the unit suite can cover the ownership helpers + owner-scoped completion logic,
  but the feel needs two live clients.

---

## 6. Decisions — LOCKED (2026-07-25)

- **Instancing = shared space, tag-only** (no spatial separation). This flips the model
  from "instance per accepter" to a **shared pool of targets with per-target ownership
  claiming**, which is simpler and handles counted jobs naturally:
  - Targets spawn as today (one pool, by count).
  - A ship **claims** a target by working it (accept + target/tether/scan it) → the
    target's `quest_owner` is set to that ship.
  - Single-target jobs become **first-to-claim**; counted jobs let each ship claim
    different targets from the pool.
- **Hard guard from the start.** A non-owner physically **cannot** touch a claimed
  target: `grav_tether_attach` refuses it (a policy hook in the sbs_utils primitive) and
  the target ignores non-owner weapon damage (mission `//damage` guard). No soft phase.
- **Mode chosen by a MAP PROPERTY at launch** — `Quest Mode: Protected | Claim-jump`
  (default **Protected** = no grief), with an optional per-job AMD `Mode:` override. In
  **Protected**, a claim hard-locks to the claimer. In **Claim-jump**, claims are
  stealable and delivery credits the deliverer (grief-as-feature; the guard is off).
- **Scope = full system** — Protected + Claim-jump + the per-ship leaderboard, built in
  verifiable phases (below), not one commit.

### Revised phases (given the locked model)
- **Phase 0 — Foundations.** (a) sbs_utils `grav_tether` **attach-policy hook** (veto a
  non-owner attach) + tests. (b) LM ownership helpers (`quest_claim`/`quest_owner_of`/
  `is_quest_owner`) + the `QUEST_MODE` map property + per-job `Mode` override.
- **Phase 1 — Claim + hard guard on ONE job (Barge).** Claim on tether; owner-only
  delivery credit; non-owner tether refused + damage ignored. Verify with two browser
  clients (Protected: B can't touch A's barge; Claim-jump: B can).
- **Phase 2 — Roll across peacetime.** Kill/scan/dock jobs → native actor triggers +
  ownership gate; delivery jobs → owner watchers; arcs → per-ship sequencers (fixes the
  late-join race).
- **Phase 3 — Leaderboard.** Per-ship `pt_earned` tally (credits bank per side, so a
  race needs per-ship); ranked results table + live standings.
- **Phase 4 — Claim-jump polish.** The tether-steal loop, contested delivery, and the
  map-property toggle end to end.
