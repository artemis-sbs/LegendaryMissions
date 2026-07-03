# Casino game rules — implementation spec

Implementation-ready rules for the four card games. Each game is a **pure
Python engine module** (deck, deal, scoring, dealer/banker policy, payout) —
headless and unit-testable — wrapped by a MAST/GUI layer. This doc is the
spec the engine is built from.

**Confidence flags:**
- **[CONFIRMED]** — standard or agreed.
- **[DRAFT]** — reverse-engineered from the web originals or newly designed;
  **confirm against the real game / approve before building.**

All games are **house-banked** (player vs dealer/banker), so seats are
independent and no player-vs-player betting is needed. Stakes are **chips**
(per-client, bought from side credits at the cage; see BAR.md).

---

## Common engine shape

```
class Card: value/rank, suit
class Deck: build(), shuffle(seed), draw()      # seed for deterministic tests
class Hand: cards[], plus per-game score()
def dealer_policy(hand) -> "hit"|"stand"
def settle(player_hand, dealer_hand, bet) -> payout_delta   # +win / -loss
```

Engine takes an injected RNG seed so unit tests are deterministic. No GUI, no
MAST imports in the engine module.

---

## 1. Nibble  (Arvonian deck)  [CONFIRMED from source]

Blackjack-like race to <=20. Verified against the original `bundle.js`
(module 8, `PlayDeck`). The scoring is deliberately quirky — replicate it
exactly, or consciously choose to adapt (see fidelity note).

**Deck / card encoding.** The engine card int packs **three independent
fields**: `num` (face value), `type` (0-3, the 2-bit **castle**), and `color`
(a separate field). They are decoded by bitmask in `deal()`. `maxnum` selects
the value range: `maxnum<=8` -> 0-7 (3-bit); `maxnum>8` -> 0-15 (4-bit).

- **The castle (`type`) bits carry scoring value** — see `getScore` below.
  The castle is decorative artwork (4 variants: `STSB/FTSB/STFB/FTFB`, the two
  bits = two castle features) that also drives the score. This is the field
  that matters for games.
- **`color` is independent in the engine, but on our art it is locked to the
  castle** (`color = mala(type)`: 0 red, 1 purple, 2 blue, 3 green). That's
  why color and castle look like the same thing on the sheet — the generator
  color-codes each castle-type. Our art does **not** vary color
  independently.
- **Playable deck for our games = 16 values x 4 castle-types = 64 cards**,
  exactly `arvonian_deck.png` (16 columns = value, 4 rows = castle/type). Use
  the castle/type row as the "suit" for Choga flushes.

Shipped game uses **2 hands** (player + dealer). Optional "Facecards" adds
negative-index face cards; skip for v1.

**Scoring** (`getScore`): with cards in draw order, `multi` = 2^index
(1,2,4,...):
```
numScore   = sum of card.num over all cards            # flat face total
castle     = sum of popcount(card.type) * 2^index      # positional doubling
total      = numScore + castle
```
So the gate glyph (`type`, 0-3) contributes its set-bit count weighted by
card position; later cards' castles are worth exponentially more.

**Rules:**
- Initial hand size 2. Player hits/stays.
- **Bust:** `total > 20` -> lose immediately.
- **Natural:** a 2-card hand whose `numScore` is exactly **0 or 14** (two 0s
  or two 7s). Player natural pays 2x bet; dealer natural forces a loss
  (cost >= 2x bet).
- **Dealer policy (shipped):** `DEALER_MUST` with threshold **15** -> dealer
  keeps drawing while `total < 15`. (Dice-based dealers exist in source but
  are commented out.)
- **Ties: dealer wins** (the final `else` is a loss).
- **Payout:** `reward = bet * 2^(playerCards - 2)` (2 cards ->1x, 3 ->2x,
  4 ->4x). `cost = max(bet, bet * (scoredHandCards - 1))`.
- Money starts 100, default bet 10 (matches our chip cap nicely).

> FIDELITY NOTE (@doug): the positional-castle scoring + "natural = 0 or 14"
> are faithful to the web game but obscure to a new player. Decide: (a)
> clone exactly for authenticity, or (b) adapt to a cleaner rule (e.g. plain
> face-sum to 20). Recommend (a) with a good in-game rules panel — the
> quirk is the Arvonian flavor.

---

## 2. Gates  (Arvonian deck, bit values + opcodes)  [CONFIRMED from source]

**Baccarat-style** — you bet on which of two logic-hands (Player or Banker)
scores higher. Verified against `bundle.js` module 12.

**Opcodes:** `OR=0, AND=1, NOR=2, NAND=3` — the corner glyphs **printed on the
cards**. Confirmed from `arvonian_deck.png`: a card's operator is
`arv_opcode(value, castle) = (value + castle) % 4`, and **there is no XOR on the
deck**. Gates deals real Arvonian cards; the gate folded in when a card joins is
that card's own printed corner glyph (so the operators match the art, not an
invented random pool). A hand alternates bit, opcode, bit, opcode, bit... where
each opcode is the incoming card's corner.

**Scoring** (`getScore`): fold left over the hand —
```
score = cards[0].num
for i in 2,4,6...:  score = score OPCODE(cards[i-1]) cards[i].num
```
(NAND/NOR use JS `~`, so mask the result to the value width, e.g. `& 7`.)

**Rules** (confirmed against `gates-info.html`):
- Player **wagers on Player hand or Banker hand** (a pot; `betOn`), then deal.
- Both hands dealt bit+opcode+bit; totals are 0-7.
- **Banker wins all ties.** Higher total wins the pot.
- Betting in units of 10, pot limit 30.
- **Optional hit rule** (`hitRule` on): a third bit+opcode is added,
  `score = (bit1 OP bit2) OP bit3`, per the baccarat tableau:
  - Player draws if player total <= 5 and banker is not 6-7.
  - Banker: total 0-1 always draws; 2 draws unless player's 3rd was 6; 3
    draws if player's 3rd in {2,3,4,5}; 4 draws if in {4,5}; 5+ stands.

> Full player-facing rules (incl. the logic-gate truth tables and worked
> examples like `5 NAND 7 = 2`) are ported in `casino/rules_text.md` — drop
> straight into the in-game rules panels.

---

## 3. Blackjack  (Terran deck, standard 52)

Standard casino blackjack — the well-known baseline, no reverse-engineering
needed.

- **[CONFIRMED]** Deck: standard 52 (one or more shoes — start with 1).
- **[CONFIRMED]** Card values: 2-10 face; J/Q/K = 10; Ace = 1 or 11 (soft).
- **[CONFIRMED]** Target: highest total <= 21; over 21 busts.
- **[CONFIRMED]** Dealer hits to 16, stands on 17 (stand on **all** 17s to
  start; soft-17 rule is a config flag).
- **[CONFIRMED]** Blackjack (A + ten-card) pays **3:2**; beats a non-blackjack 21.
- **[CONFIRMED]** Player actions v1: **hit / stand**. Double and split are
  **optional** flags, deferred unless quick.
- **[CONFIRMED]** Push (tie) returns the bet.

Cleanest game to build first as the framework proof if nibble's rules stay
unconfirmed.

---

## 4. Choga  (Arvonian deck, values 0-15) — house-banked stud  [DRAFT]

Poker-like, Caribbean-Stud structure. **Whole game is new design — approve
the ranking + payout table before building.** Name/flavor: *chogaTa* ("Soul
Tickle") = the Arvonian art of the bluff; the house/dealer is flavored as
**the Understander** (the revered master computer).

**Flow:**
1. Player antes.
2. Deal 5 cards to player, 5 to the dealer (dealer shows 1).
3. Player sees their hand and the dealer's up-card, then **raises** (2x ante)
   or **folds** (forfeit ante).
4. Dealer qualifies (see below); showdown; settle.

**Deck:** Arvonian 4 suits x values 0-15 (64 cards). "Suit" = the 4 colors.

**Hand rankings** — standard poker, **re-ordered for this deck** and
**balanced by a 3M-hand Monte-Carlo** (see freq column). The originally
proposed bit-hands (NOT-pair, checksum-as-rank) were **cut** — the sim showed
NOT-pair hits ~46-49% of hands and checksum ~1-in-16, far too common to be
high tiers. The Arvonian bit flavor lives in a **side bonus** instead.

| Rank | Hand | 1-in (this deck) | Suggested raise pay |
|---|---|---|---|
| 1 | High card | 1.7 | lose (below qualifier) |
| 2 | Pair | 2.7 | 1:1 |
| 3 | Two pair | 31 | 2:1 |
| 4 | Three of a kind | 70 | 3:1 |
| 5 | **Straight** | 612 | 6:1 |
| 6 | **Flush** | 445 | 5:1 |
| 7 | Full house ("full byte") | 1367 | 10:1 |
| 8 | Four of a kind | 8108 | 50:1 |
| 9 | Straight flush | 428571 | 200:1 |

> DECK QUIRK: with only 16 values x 4 suits, a **straight is rarer than a
> flush** (1-in-612 vs 1-in-445) — the opposite of a 52-card deck. So straight
> outranks flush here. Keep this; it's a genuine, explainable property of the
> Arvonian deck (and good bar trivia).

**Checksum side bonus (the Arvonian flavor):** independent of the hand rank,
if the 5 card values **XOR to 0** ("a clean checksum"), pay a flat side bonus
(~1-in-16, so a **10:1** side bet is roughly fair; tune for house edge). This
keeps the bit theme without breaking the ranking. Optional second novelty:
"complement pair" (a value and its 15-x both present) as a tiny consolation —
but note it's ~50% so at most cosmetic.

**Dealer qualifies:** dealer plays only with **Pair or better** (~41% of
hands). If the dealer doesn't qualify, ante pays 1:1 and the raise pushes
(standard Caribbean Stud) — confirm this vs a simpler "dealer always plays".

> STATUS: rankings + frequencies are now **data-backed**; the exact pay
> ladder and qualifier still want a house-edge sim on the final engine
> (target ~3-5% edge). @doug to approve the ladder.

---

## 5. KoraTa — "Ghost-Writing"  (Arvonian, 2-player vs AI)  [DESIGN LOCKED]

The casino's only **head-to-head** game — you vs an **AI**, with **poker-style
betting**. *KoraTa* ("Ghost-Writing") is the Arvonian art of inscribing corrupting
instructions into a rival's run — sibling to *chogaTa* (Choga). You build a scoring
"run" from your own cards while your opponent sabotages it with the logic-gate
opcodes their cards carry. Design verified against the real deck art (2026-07-03).

**Two versions** (two lobby entries, one engine/table, differ only in width):

| Route | Values | Deck | Score mask |
|---|---|---|---|
| `//casino/game/korata3 "KoraTa - Ghost-Writing (3-bit)"` | 0–7 | 32-card subset | `0b111` |
| `//casino/game/korata4 "KoraTa - Ghost-Writing (4-bit)"` | 0–15 | full 64 | `0b1111` |

**The card.** A real Arvonian card carries **both** a value (center diamond) and an
opcode (corner glyph). The opcode is derived from the art:
`arv_opcode(value, castle) = (value + castle) % 4` over `[OR, AND, NOR, NAND]` —
**no XOR** (same mapping Gates now uses; see §2). Spend a card **on your run** → its
**value**; **on your opponent's run** → its **opcode**. You can only sabotage with
the gates your dealt cards happen to carry.

**Deal & run.** Each player is dealt **5 cards** and builds a **run** = 3 values + 2
opcodes → a left-fold `v1 OP1 v2 OP2 v3`, masked to `bits`. Your 3 values are cards
you played; your 2 opcodes were placed by your **opponent**. Highest final score
wins; **ties push**.

**Turn structure — 5 rounds, V·O·V·O·V** (you = P1, AI = P2; P1 acts first each
phase):

| # | Phase | You | AI | Then |
|---|---|---|---|---|
| 1 | Value | value → your run | value → its run | — |
| 2 | Opcode | opcode → AI's run | opcode → your run | **Bet round 1** |
| 3 | Value | value → your run | value → its run | show scores |
| 4 | Opcode | opcode → AI's run | opcode → your run | **Bet round 2** |
| 5 | Value | value → your run | value → its run | showdown |

Each player spends all 5 cards: 3 as values (onto own run), 2 as opcodes (onto the
opponent's). Both runs are **open information** (face-up). The whole strategy is
*which* card to burn as a value vs. as a gate.

**Betting (poker streets).** Ante (default 10) seeds the pot. The two opcode phases
double as two betting rounds resolved after both opcodes land: **Check / Raise /
Fold** (fixed raise unit, capped); the AI responds **Call / Raise / Fold** from its
policy. **Fold forfeits the pot**; showdown after phase 5 pays the higher score,
**tie returns contributions**. Chip flow reuses the cage: track `pot`/`player_put`/
`ai_put`, settle via `casino_bet_apply(client_id, delta)`.

**AI (greedy, 1-ply).** Value phase → pick the card whose value maximizes the AI's
current fold. Opcode phase → pick the card whose carried opcode minimizes your
**expected** next fold (mean over `X in 0..mask`). Bet → from `edge = ai_score -
your_score`: raise when ahead, call when close, fold when well behind and the call
is dear. Limited to the gates its cards carry, same as you.

**House edge.** PvP-vs-AI, so no built-in edge. Either add a small **rake** on won
pots (~5%) or leave it a fair bar amusement; confirm with a seeded AI-vs-random
Monte-Carlo (`games/sim.py`) that the AI wins ~50%.

> IMPLEMENTATION: engine `KORATA` section in `games/engines.py` (`korata_deck/
> deal/apply/run_score`, `korata_ai_*`, `korata_showdown/pot_settle`,
> `korata_card_key`), `TestKoraTa` in `test_engines.py`, table in `casino/
> korata.mast` (phase state machine + betting, modeled on `gates.mast`). Wiring:
> `import korata.mast`, two `CASINO_GAME_HELP` strings, this rules copy.

---

## Payout / chip flow (all games)

- Bet is chips (int). Engine returns a signed payout delta; the MAST layer
  applies it to the client's chip balance and never touches side credits
  mid-game.
- Cash-out at the cage converts chips <-> side credits (see BAR.md economy).
- Every engine has a deterministic-seed unit test proving: correct scoring,
  correct dealer/banker policy, correct settlement sign, and house edge > 0
  over a large seeded sample (sanity that the house isn't losing money).
