# Upgrade -> Item System Redesign

> Status: design proposal, not yet implemented. A flexible, discoverable,
> modifier- and prefab-driven replacement for the LegendaryMissions upgrade
> system, designed to persist in the Open Universe and support a station market
> and economy.

---

## 1. Problem - the current system

Four places enumerate the same 9 items, all hardcoded:

| Concern | Location | Issue |
|---|---|---|
| Definition | `anom_data` dict, `upgrades/upgrade.py` | 9 fixed keys (art + name) |
| Spawn | `terrain_spawn_pickups` | `if upg == 1..9` chain (has a `TODO: needs extensible system`) |
| Collect | `upgrades/pickup_common.mast` | ~110-line `if/elif`, one near-identical copy per item |
| Activate / effects | `upgrades/upgrade.mast` | ~600-line GUI tab, one block + hardcoded timer/effect per item |

Storage is per-type inventory **counts**. Adding one upgrade means editing four
files. About 850 lines that the consoles/maps systems would express as data.

---

## 2. Reuse - building blocks already in the codebase

- **`labels_get_type("item/")`** (`sbs_utils/procedural/execution.py`) - discovers
  any label by its `metadata: type:` prefix. The registry mechanism, already used
  for maps/media. **No new syntax required.**
- **Prefab pattern** - items are ordinary `=== label`s with a `type:` (exactly
  like `prefab_fleet_empty`, `prefab_side_generic`).
- **`Modifier` system** (`sbs_utils/procedural/modifiers.py`) - flat / additive /
  multiplicative `data_set` modifiers with auto-expiring timers = upgrade effects.
- **`Upgrade` / `upgrade_add`** (`sbs_utils/procedural/upgrades.py`) - runs an
  item's label against **any** target and tracks its modifiers.

---

## 3. Design

### 3.1 An item = a prefab label with a `type`

    === prefab_item_carapaction_coil
    metadata: ``` yaml
    type: item/upgrade/defense          # discovered via labels_get_type("item/")
    display_text: Carapaction Coil
    art: alien_2a
    tier: 2
    price: 250
    mode: consumable                    # consumable | install | resource
    duration: 300
    targets: ship, cockpit              # which agent kinds it can apply to
    consoles: weapons, engineering      # which console(s) may activate it (omit = any)
    effect: { key: shields, mod: multiplicative, value: 1.5 }
    ```
        # default effect = the metadata modifier; body only for custom logic
        modifier_add(UPGRADE_AGENT_ID, "shields", 1.5, "carapaction_coil", mult, timer=duration)
        yield result UPGRADE_AGENT_ID

### 3.2 Registry

- `items_get_list()` = `labels_get_type("item/")`; `item_get(key)`.
- Category / tier from the `type` path + metadata. Single source of truth.

### 3.3 Generic pipeline (replaces all hardcoded chains)

- **Spawn** - one `item_spawn(key, pos)` (reads `art`); one weighted
  `terrain_spawn_items()` sampling the registry by tier / rarity.
- **Collect** - one `//collision/interactive if has_role(...,"item")`: read key
  -> add to holder's item inventory -> particle -> delete.
- **Activate / GUI** - one generic panel listing the holder's items *from the
  registry* (icon / name / count / desc / cooldown), activating via the item's
  label. The activate button appears only when the player is on a console listed
  in the item's `consoles` metadata (matched against `CONSOLE_TYPE`/`ctype`),
  preserving today's per-upgrade console gating (e.g. codecase = comms, lateral
  array = science). Omitting `consoles` means any console can activate it.

### 3.4 Effects

`modifier_add` (timed for consumables, permanent for installs), run through
`upgrade_add`. Targets **any** agent - player ships, **stations**, fleets,
cockpit craft. Expanded uses: stat mods, granted abilities, heal / repair,
spawned helpers, passive auras, set bonuses, crafting components.

### 3.5 Server authority (avoid the current console-side bug)

The existing system's main bugs come from running activation **logic in the
client/console GUI task** (the `@gui/tab/upgrade` button handlers call
`set_inventory_value`, set timers, apply effects inline). On a console that
means effects can apply per-console, double-apply across clients, or diverge
from the server's authoritative state.

Rule for the new system: **the console only renders state and captures intent;
all state changes run on the server.**

- The GUI reads inventory/counts/cooldowns for display (server-authoritative
  shared state - read is fine).
- A button press does **not** mutate anything; it delegates to the server -
  e.g. `upgrade_add(holder, item_label, activate=True)` (which already runs the
  effect label via `task_schedule_server`) or a `signal_emit` handled by a
  server route.
- **Collection** (`//collision`), **activation effects** (the item label /
  `modifier_add`), **market buy/sell**, and **persistence writes** all execute
  server-side. Nothing that changes game state lives in a client task.

### 3.6 Storage & persistence

- Per-agent **count-based item inventory** + a **resource ledger** + a `credits`
  value.
- Persisted in the Open Universe **delta save**; **installs re-apply** their
  modifiers on load / jump; **station** inventories / markets persist per sector.

### 3.7 Signals / events (decoupling & extension points)

Lean on signals so producers (collect / activate / market) are decoupled from
reactors (effects, GUI repaint, quests, economy, sfx), and so activation stays
server-authoritative (§3.5): the client **emits intent**, a server `//signal`
route **does the work** and **emits a result event** anyone can hook.

Event vocabulary (all data dicts carry `holder_id` + `key`):

| Signal | Emitted by | Typical reactors |
|---|---|---|
| `item_collected` | collect route (after crediting) | GUI repaint, quests, sfx |
| `item_activate` | GUI button (intent, client) | server `//signal/item_activate` route (runs the item label) |
| `item_activated` | activation (server) | GUI repaint, effects, sfx (mirrors `upgrade_activated`) |
| `item_expired` | timed modifier ending | GUI repaint, "buff ended" notice |
| `item_bought` / `item_sold` | market route | credits/stock deltas, economy, persistence save |
| `item_changed` | any of the above (generic) | upgrade panel `on signal item_changed:` repaint |

This makes the system extensible like consoles/maps: a mission or addon adds a
`//signal/item_*` route to react - no edits to the item core. Activation never
runs in a client task; the button only `signal_emit`s.

### 3.8 Market & economy

- Station service: buy / sell from the registry (filtered to purchasable) for
  **credits**.
- **Keyed deterministic prices / stock** per sector + station kind now; hooks
  (price modifiers, supply / demand) for **dynamic later**. Trade goods /
  resources sell against scarcity -> trade routes emerge.

---

## 4. Decisions (locked)

| Decision | Choice |
|---|---|
| Registry | Prefab labels with `type: item/...`, discovered via `labels_get_type` - no new syntax |
| Scope | Unified items (upgrades + resources + trade goods, by category) |
| Packaging | New `items` addon, shim the old API, then retire `upgrades` |
| Item model | Count-based inventory + resource ledger |
| Economy | Keyed static prices first, dynamic-ready |

---

## 5. Phases (each its own sign-off)

1. **Registry** + the 9 existing items as `type: item/...` prefab labels.
2. **Generic spawn + collect** (replace both hardcoded chains; old API shimmed).
3. **Generic upgrade GUI** (list-from-registry + activate -> modifiers); retire
   the 600-line tab.
4. **Persistence** (item inventory + credits in the universe save; re-apply
   installs on load).
5. **Market + credits** at stations (keyed stock + deltas).
6. **Economy** (price model / supply-demand; resources & trade goods).

---

## 6. Backward compatibility

Re-express the 9 items as the first `type: item/...` labels (same keys / art);
shim `anom_data` / `pickup_spawn` / `terrain_spawn_pickups` / inventory-count
reads onto the registry. Existing missions keep working; honors "MAST changes
must not break existing scripts."

---

## 7. Open questions

- Install vs consumable: do ships / stations get **upgrade slots / capacity**, or
  unlimited installs?
- Credits scope: **per-ship, per-side, or shared** (co-op)?
- Resource ledger: which base resources / trade goods to seed (mining? salvage
  from wrecks / enemies?)?
