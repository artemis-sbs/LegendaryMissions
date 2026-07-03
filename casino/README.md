# casino — the Casino addon

A social/gambling area for the hangar experience: a bar with rumor-dealing
patrons and four card games (nibble, gates, blackjack, Choga). Separate addon
folder so it packages independently and can later be reused on docked
player-ship consoles. The hangar imports it.

**Status: all games built + compile; Python layer tested (32 passing).** Bar,
lobby+cage, and all four card games (nibble, blackjack, gates, choga) are
written, self-register via `//casino/game/<key>`, and compile clean. The
hangar imports the addon and the Casino tab self-registers. What remains:
**render-verify in the mockgui** (card sizing, layouts), the checksum side bonus
for choga, and polish. (Gates now folds each card's **printed corner opcode**
`(value+castle)%4` - OR/AND/NOR/NAND, no XOR - so no dedicated opcode-card art is
needed; see GAME_OPCODE.md for the deck's opcode mapping.)

## Package contents (what's here now)

| File | What |
|---|---|
| `../BAR.md` | The master plan: decisions, phases, deliverables, open Qs. |
| `CASINO_RULES.md` | Engine rules for all four games (confirmed from source). |
| `rules_text.md` | Player-facing rules copy for the in-game rules panels. |
| `TABLE_LAYOUT.md` | Shared seats-around-a-dealer GUI spec (the framework). |
| `CASINO_ECONOMY.md` | Cage/chips, comps, consequences, settings keys. |
| `bar.amd` | Bar patrons, rumors, chatter (content; DRAFT keys). |
| `games/engines.py` | Pure-Python game engines (tested). |
| `games/test_engines.py` | 21 passing unit tests. |
| `games/sim.py` | House-edge Monte-Carlo. |
| `media/` | Card decks, backs, jokers + atlas-key README. |

## MAST file structure  ([x] = written & compiles)

```
casino/
├── [x] __init__.mast       # entry: imports helpers + mast files
├── [x] casino.mast         # cage + lobby + area nav + //gui/tab/casino
├── [x] bar.mast            # bar logic (revived from hangar/bar.mast)
├── [x] casino_economy.py   # cage helpers (tested, 7 tests)
├── [x] casino_media.py     # card-atlas registration
├── [x] casino_gui.py       # shared draw helpers (casino_draw_hand)
├── [x] casino_game_label.py# //casino/game decorator node + casino_games_list
├── [x] nibble.mast         # game table (Arvonian, hit/stand)
├── [x] blackjack.mast      # game table (Terran, 21)
├── [x] gates.mast          # game table (baccarat-style, bet on hand)
├── [x] choga.mast          # game table (Arvonian house-banked stud)
├── [ ] blackjack.mast
├── [ ] choga.mast
├── [x] games/  media/  *.md   # engines (tested), assets, specs
```

## Adding a game (discoverable - no lobby edits)

Games are discovered via a decorator route, exactly like the engine's own
`//web` / `@map` / `//gui/tab` labels. To add one:

1. Write `mygame.mast` with a game entry label (e.g. `=== show_mygame ==`).
2. At its top level, declare the discoverable route. Put the game's help text in
   a `help` **metadata block** on the route so no lobby edit is needed (the
   metadata content + closing ` ``` ` fence must be at **column 0**):
   ```
   //casino/game/mygame "My Game"
   metadata: ``` yaml
   help: >
     My Game. One-liner on how to play, shown in the lobby detail panel.
   ```
       jump show_mygame
   ```
3. `import mygame.mast` in `__init__.mast` (after `casino_game_label.py`).

The lobby renders itself from `casino_games_list()` (which reads
`CasinoGameDecoratorLabel.all`) and navigates via `gui_task_jump` to the
route - so the new game appears automatically. `casino_game_help()` prefers the
route's `help` metadata (via the label's inventory) and falls back to the
`CASINO_GAME_HELP` dict in `casino_lobby.py` for games that predate metadata.
Card logic goes in `games/engines.py` (pure, unit-tested); shared drawing in
`casino_gui.py`.

## Build order (phases, see BAR.md)

1. **Bar** — revive `hangar/bar.mast` into `casino/`, wire a `bar` tab, add
   `bar.amd` chatter. Small.
2. **Nibble** — build the table framework (`tables.mast`) + cage economy +
   first game on `engines.nibble_*`. Medium (framework is the big lift).
3. **Gates** — second game on the framework.
4. **Blackjack** — third game (Terran deck art ready).
5. **Choga** — house-banked stud (engine + pay ladder ready).
6. **Rumors + consequences** — rumor pool wiring, comps, (optional) debt.

## Integration touch-points (OUTSIDE casino/ — flag before touching)

- `hangar/hangar.mast` — uncomment the Bar button, add casino tabs, import the
  addon.
- `__lib__.json` / a test-harness `story.json` — to package `casino/` as a
  mastlib and load it.

## Deferred: player identity + chip persistence

Chips currently live on the per-client agent inventory ("chips"), which
persists only for the session/console. To persist a player's chips across
sessions/ships we need a way for a player to **identify themselves** (a login
/ call-sign + PIN, or a claimed pilot profile) so their wallet follows them.
Design + implement much later; for now the one-time welcome stake
(`casino_ensure_stake`) keeps it playable. See BAR.md.

## Open decisions for @doug (none block starting)

- Nibble fidelity/edge (clone vs soften — it's ~37% house).
- Gates commission (add ~5% banker rake for a real edge?).
- Choga final pay ladder (validated ~2-3% edge; fine as-is).
- Confirm the `bar.amd` interpreted key names (`truth`, `effect`,
  `reliability`, `face_kind`, ...).
