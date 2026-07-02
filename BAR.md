# The Casino — Plan

A social/gambling area attached to the hangar experience. Pilots waiting in the
hangar (and later, bridge crew on docked player ships) can visit the casino:
drink at the bar, chat with NPC patrons, pick up rumors, and gamble side
credits at card tables. A pilot may decide their best play is to play the
games rather than fly — and that choice should have real benefits and
consequences for their side.

## Decisions (made 2026-07-02)

- **Navigation:** casino areas are hangar **tabs** (reuse `gui_tab_enable` /
  `//gui/tab/<area>` exactly like `airwing`). A floor-plan lobby image can be
  layered on later as its own tab; not required for v1.
- **Table presentation:** **shared table, seats around a center**. The center
  shows the dealer and shared state; seats around it show each seated
  player's face, call sign, bet, and hand (card backs for other players).
  The dealer games are player-vs-dealer, so logic is per-seat; only the
  presentation is shared. Seats are **player-only in v1**; NPC patrons
  filling seats (simple AI, atmosphere) can come later.
- **Stakes:** **chips bought from side credits** at the cage, capped **per
  client at 100 chips (1 chip = 1 credit)**, settings-tunable. Winnings cash
  out to side credits. Personal risk is bounded; the side treasury still
  feels wins and losses.
- **Rumor/chatter content:** authored in **.amd files** (movie-script style,
  like `quests/hangar_quests.amd`), with a data section marking truth and any
  linked quest/intel. Any new AMD syntax gets user sign-off before
  implementation.
- **Structure:** the casino is a **separate addon folder** (`casino/`,
  sibling of `hangar/`) that the hangar imports — cleaner for the future
  docked-console reuse and independent packaging.
- **Card sheet asset:** Claude merges the two 512px source sheets into one
  downscaled 64-card sheet at implementation (see Asset prep below); no
  generator regeneration needed unless the deck layout changes.
- **Terran deck art:** the CC0 Wikimedia English-pattern deck
  (`English_pattern_playing_cards_deck_PLUS_CC0.svg`), rasterized to a
  downscaled PNG sheet. Traditional look, no attribution required.

## What already exists (leverage, don't rebuild)

- **`hangar/bar.mast` — a working bar prototype, currently disconnected.**
  Torgoth barkeep "Bitters" with drinks stock (martinis/beer/vodka + DS1
  resupply hook), live patron listbox (every visiting client with face and
  call sign), shared "toast" message board, ambient banter task. Named NPC
  sketches in comments: Bitters (bartender), Cogs (mechanic, knows things),
  Ghost (pilot, rumors). The hangar "Bar" button is commented out at
  `hangar/hangar.mast:296`.
  - Known issues to fix on revival: message board push/pop bug (noted in the
    file), `bar_patrons.json` is not valid JSON (contains unquoted
    expressions — either make it a real data file or delete it in favor of
    AMD-authored patrons), banter lines are placeholder.
- **Tab navigation:** `gui_tab_enable_top()` / `gui_tab_enable("name")` /
  `//gui/tab/name` routes, already used for `airwing`.
- **Credits + market:** credits are per-side inventory values
  (`get/set_inventory_value(side_id, "credits", n)`). `items/items.py`
  provides `market_buy`/`market_sell` with per-station stock and prices.
  OpenUniverse spends the same pool (ceasefire, ransom, clan-quest rewards).
  Casino winnings therefore already buy items/upgrades with no new plumbing.
- **Reputation (OpenUniverse):** `universe/universe_reputation.py` —
  `reputation_get/adjust`, `clan_standing`, offer tiers, reward multipliers.
  Rumor truth-probability can key off this when OU is loaded; fall back to a
  per-NPC static reliability stat when it is not (casino must not hard-depend
  on OU).
- **Quest board:** `quests/hangar_quests.amd` pattern — a true rumor can seed
  a quest on the board.
- **Card assets:** generator at `F:\c\gh\nibble-card-generator`, sheets in
  `build/sheets/`: `sheet-full-octal-red.png` (4 suits x values 0-7,
  512x512 cells on a 10-column 5120x2048 sheet), `sheet-nibble-red.png`
  (values 8-15), `sheet-octal-red.png`. Card corners already carry the logic
  gate symbols (AND/OR/NOR/NAND), so one deck art serves all the bit games.
  - **Lore:** this is the **Arvonian deck** — Arvonians admire computers, so
    their playing cards are bit-based. Blackjack and poker use the **Terran
    deck** (standard 52 cards).
  - **Terran deck art (found, CC0):** Wikimedia Commons
    `English_pattern_playing_cards_deck_PLUS_CC0.svg` — CC0/public domain,
    54 faces (52 + 2 jokers) + backs, laid out 4 suit rows x 13 ranks
    (Ace->King), matching our `row = suit, col = rank` convention. Rasterize
    to a downscaled PNG sheet at implementation; register
    `card_terran_<suit>_<rank>` atlas keys. Fallback: Kenney "Playing Cards
    Pack" (CC0, ready-made PNG spritesheets, more cartoon style).
  - **Two Arvonian variants:** the **32-card octal deck** (4 suits x 0-7,
    used by gates) and the **64-card full nibble deck** (4 suits x 0-15 =
    both sheets, used by nibble and Choga). The octal deck is just the low
    half of the full deck.
  - **Asset prep (Claude, at implementation):** merge the two source sheets
    into one 64-card sheet at 256px cells (16 value columns x 4 suit rows =
    4096x1024 PNG) — one media file, direct key math (col = value,
    row = suit), no empty columns. Atlas keys `card_<suit>_<value>`; games
    draw whatever value range their deck uses.
- **Sprite rendering:** `gui_image_add_atlas(key, image, l, t, r, b)`
  registers a named sub-rect of a PNG usable anywhere image props are
  accepted (`gui_image_*`, icons, `gui_text_area` `image://key`). One setup
  loop over the merged sheet registers `card_<suit>_<value>` keys — no
  per-card PNGs needed. Cards render at ~100-150 px on console pages, so the
  256px merged cells are ample.

## Areas

### Bar (Phase 1)

Revive the prototype as the casino's social hub tab.

- Reconnect via a `bar` tab (replaces the commented-out button).
- Fix the message-board bug; keep drinks + toast board (they work and are fun).
- Patrons: the three named NPCs plus visiting clients. NPC chatter and
  reactions authored in a new `casino/bar.amd`. Phase 1 also creates the
  `casino/` addon skeleton and moves/wires the bar there (hangar imports it).
- Rumor delivery: talking to an NPC patron (select in the patron list ->
  dialogue) can yield a rumor. See Rumors below.

### Nibble table (Phase 2)

Player-vs-dealer, deck of values 0-15.

- Rules (from the web version): hit/stand to reach <= 20; hand value is card
  faces plus "castle" multipliers that double per successive card (1, 2, 4,
  ... 64 for the 7th); dealer plays a fixed rule (e.g. hit below 14); dealer
  wins ties; bust over 20 loses; naturals (two 0s or two 7s) pay double;
  payouts scale 2^(cards-1).
- Implementation: pure-Python game engine module (deck, hand scoring, dealer
  policy, payout) — unit-testable headless — plus a MAST/GUI layer.

### Gates table (Phase 3)

Player-vs-banker, bit cards 0-7 plus opcode cards (AND, OR, NOR, NAND, XOR).

- Rules: each hand gets bit + opcode + bit; score = bit1 OPCODE bit2
  (bitwise); bets in increments of 10 with a pot limit; conditional hit rules
  (player draws if total <= 5 and banker not 6-7; banker thresholds);
  three-card naturals bonus; banker wins ties.
- Reuses the table framework, seat layout, chips, and betting UI from
  Phase 2.

### Blackjack table (Phase 4)

Player-vs-dealer, standard 52-card deck. Similar in feel to nibble but a
distinct game — different deck, different rules — keep both.

- Standard rules: hit/stand to 21, dealer hits to 17, naturals pay 3:2;
  splits/doubles optional (decide during implementation).
- Reuses the table framework, seats, chips, and betting UI. The main new
  need is **standard 52-card deck art** (see open questions).

### Arvonian stud — "Choga" (Phase 5)

Poker-like game on the **full 64-card Arvonian nibble deck** (4 suits x
0-15 — the same deck nibble already uses, so no new assets),
**house-banked** (Caribbean-Stud style: every player makes a poker-style hand
and bets against the dealer, not each other) so it reuses the dealer-table
framework — no player-vs-player betting rounds needed.

- **Name (from Arvonian lore):** **Choga** — short for *chogaTa* ("Soul
  Tickle"), the canonical Arvonian art of subtle teasing and putdowns, i.e.
  the bluff. Perfect fit for poker. The dealer / house is flavored as **the
  Understander** ("Lilene"), the revered Arvonian master computer — so you
  bet against the machine, which also justifies the house-banked structure.
  An Arvonian "poker face" is a **fight face** (their martial-arts
  intimidation pattern) — good flavor for a bluff/tell mechanic.
  Alternates considered: "Understander" / "Beat the Understander",
  "Fight Face", "Lilene's Hand".
- Sketch (draft rules, to be play-balanced during implementation): ante, five
  cards dealt (some face up for table drama), one raise-or-fold decision,
  showdown vs the dealer's hand.
- Hand rankings adapted to the bit deck (draft, needs approval): high card;
  pair / two pair / three / four of a kind; straight (consecutive values);
  flush (same suit); **NOT pair** (x with 15-x, 4-bit complements);
  **checksum** (whole hand XORs to 0 — rare, near the top). Arvonians would
  absolutely rank a clean checksum above a flush.

### Future / deferred

- **Poker** (from the original concept, Terran 52-card deck): real
  multiplayer — shared pot and betting rounds *between players*, not vs a
  dealer — a much bigger lift. Revisit after the table framework proves out
  with the dealer games; Choga is the stepping stone (poker hands and
  raise/fold flow, without inter-player betting). Needs the Terran deck art.
- **Casino on docked player-ship consoles**: expose the casino tabs to a
  console when its ship is docked (dock-state gate + reuse the same labels).
  Design the labels now so nothing assumes the hangar client.
- **Floor-plan lobby tab**: clickable image map once art exists.

## Economy: chips, benefits, consequences

- **The cage:** buy chips from side credits, capped per client (default 100;
  settings.yaml-tunable). Cash out chips to side credits when leaving. Chips
  are a per-client inventory value; credits stay per-side.
- **Benefits**
  - Winnings become side credits -> items/upgrades via the existing market.
  - Hot streak comps: free drinks; a rumor from an impressed patron; at a
    high tier, a one-time market discount token at this station.
  - Rumors themselves are the intel economy: a true rumor can reveal a quest,
    a salvage location, or enemy intel.
- **Consequences**
  - Losses are real side credits (bounded by the per-client cage cap).
  - Chips are forfeit if you launch mid-hand (commitment to the table).
  - Optional escalation (later phases): a debt marker with a loan-shark NPC
    -> spawns a collection encounter or a quest to work it off; reputation
    loss with the station side for welching.
  - Time is a consequence by itself: a pilot at the table is not in a
    cockpit while the side is fighting.

## Rumors

- A rumor = one AMD-authored entry: speaker, flavor line(s), a truth flag,
  and an effect when true (seed quest, reveal intel, mark map) or when false
  (wasted trip, small reputation sting for the teller).
- Truth weighting: per-NPC reliability stat (Ghost mostly true, drunk patron
  coin-flip); when OpenUniverse is loaded, modulate by the teller's clan
  standing via `universe_reputation.py`.
- Delivery: select a patron in the bar -> short dialogue -> maybe a rumor.
  Buying a drink for a patron improves the odds of getting one.
- Exact AMD data-section syntax to be proposed and confirmed before
  implementation (keep it in the existing markdown-like AMD style).

## Phases

1. **Revive the bar** — tab wiring, bug fixes, AMD chatter for the three
   NPCs, patron dialogue skeleton (no rumors yet). Small.
2. **Nibble** — python game engine + tests, card atlas setup, shared-table
   GUI, cage/chips economy. Medium. The table framework built here is the
   reusable core.
3. **Gates** — second game on the same framework; betting UI generalized.
   Medium.
4. **Blackjack** — third game on the framework; rasterize the CC0 Wikimedia
   Terran deck to a sheet. Small-medium once the framework exists.
5. **Choga** — house-banked Arvonian stud on the framework; no new art
   needed (uses the full 64-card nibble deck). Rules draft needs approval +
   balancing. Medium.
6. **Rumors + consequences** — rumor pool in AMD, truth/reputation weighting,
   quest-board seeding, comps and (optional) debt hooks. Medium.

(Phases 4-6 can reorder freely — the games ride the framework independently,
rumors are independent of the tables.)

Each phase is shippable on its own; stop after any phase and the casino is
still coherent.

## Deliverables produced (non-code, ready for the coding session)

- **Card assets** in `casino/media/` — `arvonian_deck.png` (64 cards,
  16 values x 4 suits, 256px), `terran_deck.png` (52 cards, CC0),
  `terran_back.png`, `terran_jokers.png`. See `casino/media/README.md` for
  the atlas-key registration code (`card_arv_<suit>_<value>`,
  `card_ter_<suit>_<rank>`).
- **Rules spec** — `casino/CASINO_RULES.md`: implementation-ready engine spec
  for all four games. **Nibble and gates rules are now CONFIRMED** from the
  original `bundle.js` source (nibble = positional-castle scoring, natural =
  0/14, dealer hits to 15; gates = baccarat-style bet-on-hand with left-fold
  bitwise ops). Blackjack is standard. **Choga rankings are balanced by a
  3M-hand Monte-Carlo** — the proposed NOT-pair/checksum ranks were cut as
  too common (46% / 1-in-16) and the bit flavor moved to a checksum side
  bonus.
- **Atlas sub-rect verified** — `send_gui_image` supports `sub_rect`
  (four floats l,t,r,b) per `widget_stylestring_documentation.txt`, so the
  spritesheet-atlas approach is sound.
- **Player-facing rules copy** — `casino/rules_text.md`: cleaned rule text
  for both bit games (incl. logic-gate truth tables, worked examples,
  nibble castle/reward/cost tables), ported from the original info pages —
  drop into the in-game rules panels. Gates tie handling confirmed
  (**banker wins all ties**).
- **Table layout spec** — `casino/TABLE_LAYOUT.md`: the shared
  seats-around-a-dealer GUI (region geometry, per-game action buttons, seat
  model, watch/repaint live updates). This is the reusable framework Phase 2
  builds.
- **Game engines (written + tested)** — `casino/games/engines.py`: pure-Python
  nibble, gates, blackjack, choga (deck, scoring, dealer/banker policy,
  settlement), with `test_engines.py` (21 passing tests) and `sim.py`
  (house-edge Monte-Carlo). Deterministic, no MAST/GUI — the GUI layer just
  calls these. **The hardest logic is already done and verified**; Phase 2+
  is mostly wiring GUI to these engines.
- **Economy spec** — `casino/CASINO_ECONOMY.md`: cage buy/cash-out functions
  (side credits <-> per-client chips, 100 cap), `settings.yaml` `CASINO`
  block, comps tiers, consequences, debt hooks, and the data keys — all using
  the existing `inventory_value` conventions from `items.py`.
- **Package index** — `casino/README.md`: single map of the whole addon
  (contents, planned MAST file structure, build order, integration
  touch-points, open decisions).
- **Bar content** — `casino/bar.amd`: three patrons (Bitters, Cogs, Ghost)
  with reliability stats, a starter rumor pool (truth + effect keys), and
  ambient chatter. Uses only existing AMD data-section capability; the
  interpreted keys are listed at the top of the file for sign-off.

## Open questions

- ~~Chip cap default~~ — **decided: 100 chips per client, 1 chip = 1 credit**
  (settings-tunable). Antes/bets scale to that (e.g. blackjack min 5).
- ~~Terran deck art~~ — **decided: CC0 Wikimedia English-pattern deck**,
  already rasterized into `casino/media/terran_deck.png`.
- **Choga pay ladder** — rankings are data-backed (Monte-Carlo); the exact
  payout ladder + dealer-qualifier still want a house-edge sim on the final
  engine (~3-5% edge target) and @doug approval. See CASINO_RULES.md.
- **Nibble fidelity + edge** — rules confirmed from source, but the scoring
  is quirky (positional castle, natural=0/14) AND the house edge is very high
  (~37% under naive play, per `casino/games/sim.py`). Decide: clone exactly
  for authenticity vs soften (player wins ties / lower dealer `must`).
  Recommend clone + a clear rules panel, maybe soften ties.
- **Gates house edge** — ~0% under two-way betting (banker-tie edge only).
  Decide whether to add a small commission (baccarat-style ~5% on banker
  wins) if the casino should guaranteed-profit.
- **AMD rumor keys** — confirm the interpreted key names in `bar.amd`
  (`truth`, `effect`, `reliability`, `face_kind`, ...) before the loader is
  written.
