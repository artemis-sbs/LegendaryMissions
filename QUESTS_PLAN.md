# Quest System Plan

> Status: design proposal. Turn the passive, state-only quest system into a
> discoverable, AMD-authored, signal-driven quest layer with rewards - prototyped
> at the hangar (cockpit-filtered quest board) and growing into the Open Universe
> and full-crew story quests.

---

## 1. What exists today

- **AMD** (`documents/amd_doc.md`): markdown + extensions. Headings as a quest
  tree (`# [Title](id?state=COMPLETE)`); **`--- yaml ---` data sections attach
  script-accessible data to a quest**; embeds (`ship:`/`face:`/`image:`); styles.
- **Quest API** (`sbs_utils/procedural/quest.py`): per-agent quests, states
  (IDLE/ACTIVE/SECRET/FAILED/COMPLETE); `document_get_amd_file` parses AMD into a
  quest tree; `quest_flatten_list` merges **game (SHARED) + client + ship**
  quests; signals `quest_activated`/`quest_completed`.
- **Quest tab** (`documents/quest_tab.mast`): real but **dev-only**, renders AMD.
- **Hangar** (`hangar/`): a per-craft static `briefing` string + ad-hoc random
  "story missions", a rumor bar, loosely split fighter/shuttle.

**Gap**: quests only *track* state - nothing advances them; no rewards; the tab
is dev-only; the hangar briefing is a static string.

---

## 2. Decisions (locked)

| Decision | Choice |
|---|---|
| Quest logic | Declarative YAML triggers in the AMD data section + a MAST `label:` escape hatch for custom logic |
| First slice | Hangar quest board (fighter/shuttle), end-to-end |
| Rewards | Credits (to side) + items (to ship) via the item/economy system |
| Driver | Reuse existing signals (kills, item_collected/bought, docking, comms, universe arrival) |
| Availability (for now) | Show all authored quests filtered by cockpit; sector-keyed subset comes with the universe (Q3) |
| Bar | Kept separate for now |
| Sortie persistence | Ephemeral for now; universe persistence in Q3 |

---

## 3. Authoring shape (AMD)

A quest is an AMD heading-link with a YAML data section carrying its triggers,
rewards, and scoping; the prose below is the briefing/narrative.

    # [Patrol the Frontier](patrol1)
    ---
    cockpit: fighter
    objective: Destroy 5 raiders
    on_kill: { role: raider, count: 5 }
    reward: { credits: 300, items: { tech: 1 } }
    ---
    Command needs the approaches swept. Hunt down the raider probes...

Trigger vocab (declarative): `on_kill {role,count}`, `on_collect {key,count}`,
`on_reach {poi|sector|object}`, `on_comms {with,option}`, `on_dock {station}`.
Actions on complete: `reward {credits,items}`, `reveal <subquest_id>`,
`spawn <prefab>`, `signal <name>`. Escape hatch: `label: <mast_label>` runs a
MAST label for bespoke logic (like a prefab/brain).

---

## 4. The quest driver (signal-driven)

A `quests` addon that makes quests progress:

- On `quest_activated`, the quest's YAML triggers become live for its agent.
- Hooks existing signals - `//damage/destroy` (kills), `item_collected` /
  `item_bought`, docking, comms, universe arrival - and, on a matching event,
  advances the relevant active quests' progress counters (stored in quest data).
- When a condition is met: `quest_complete`, apply `reward` (side credits + ship
  items), and `reveal` any SECRET sub-quests.
- If a quest declares `label:`, the driver runs that MAST label instead of (or
  in addition to) the declarative handling.

Scope resolution: a kill/collect by a cockpit advances that **client's** quests;
crew objectives advance the **ship's**; story beats advance **game (SHARED)**;
faction goals advance the **side** (shared credits / future admiral RTS).

---

## 5. First slice - hangar quest board (Q2)

1. `hangar_quests.amd` with ~2 fighter + ~2 shuttle quests (declarative triggers).
2. Hangar GUI: replace the static `briefing` panel with a **board** listing
   available quests filtered by the selected cockpit's `cockpit:` type; selecting
   renders that quest's AMD narrative as the briefing.
3. **Launch assigns** the quest to the cockpit/client and activates it.
4. Driver hooks the relevant signals; on complete -> reward + "mission complete"
   comms.

---

## 6. Cockpit-type quests

- **Fighter** (combat): patrol, intercept, escort, destroy-target, recon.
- **Shuttle** (utility): deliver cargo/personnel, rescue, ferry resources, survey,
  repair-assist (ties to items/economy).

Quests declare `cockpit: fighter | shuttle | any`; the board filters, making the
cockpit choice meaningful.

---

## 7. Full-crew (bridge) quests

Bridge-scope quests whose sub-objectives map to consoles (helm navigate, science
scan, weapons engage, comms negotiate, eng manage); branching via comms choices;
side/faction campaign quests tied to the shared-credit economy. Productionize the
quest tab (gate by setting, not dev-only) with accept/abandon + narrative view.

---

## 8. Open Universe integration

- Sectors/POIs **seed quests deterministically** (station quest-givers, anomaly
  mysteries); story quests span sectors (deliver A->B, synergizing with trade).
- Quest state persists in the universe save (per ship/side), like items/credits.
- Galaxy map marks quest objectives. Quests become the universe's content layer.

---

## 9. Siege

Keep lean: at most a couple of **optional bonus objectives** ("defend station X
for N min", "kill the flagship") via the same system for rewards. The full
narrative system doesn't fit siege's fast survival loop.

---

## 10. Phasing

1. **Q1** - quest driver + AMD trigger vocab (core; verify kill->complete->reward).
2. **Q2** - hangar quest board (cockpit-filtered) + a few fighter/shuttle quests.
3. **Q3** - Open Universe sector/POI quests + persistence.
4. **Q4** - crew/bridge story quests + productionize the quest tab.
5. **Q5** - optional siege bonus objectives.

Reuses the item/economy system (Phases 1-6) for rewards; stays
server-authoritative; honors MAST backward compatibility.
