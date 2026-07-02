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

**Opcodes:** `OR=0, AND=1, NOR=2, NAND=3, XOR=4` (the corner glyphs). A hand
alternates bit, opcode, bit, opcode, bit...

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

## Payout / chip flow (all games)

- Bet is chips (int). Engine returns a signed payout delta; the MAST layer
  applies it to the client's chip balance and never touches side credits
  mid-game.
- Cash-out at the cage converts chips <-> side credits (see BAR.md economy).
- Every engine has a deterministic-seed unit test proving: correct scoring,
  correct dealer/banker policy, correct settlement sign, and house edge > 0
  over a large seeded sample (sanity that the house isn't losing money).
