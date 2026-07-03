# Casino rules — player-facing copy

Cleaned rule text for the in-game rules panels, ported from the original
`nibble-info.html` / `gates-info.html`. Wording can be trimmed for the panel;
the numbers are authoritative.

---

## Nibble

**Goal.** Beat the dealer with the highest hand **20 or below**. Go over 20
and you bust. **The dealer wins all ties.**

**The dealer.** The house dealer takes cards and must keep hitting while its
total is below a set number (the casino table uses **15**).

**Scoring your hand.** Add the **face value** of each card, then add its
**filled-in castles** — but castles are worth more on every later card:

| Card | Each castle worth |
|---|---|
| 1st | 1 |
| 2nd | 2 |
| 3rd | 4 |
| 4th | 8 |
| 5th | 16 |
| 6th | 32 |
| 7th | 64 |

(So a castle on your fifth card is worth 16, not 1 — late castles are
dangerous.)

**Natural win.** Start with two 0s or two 7s (any castles) — a **natural**,
pays **double**.

**Reward (when you win)** — exponential in your hand size: bet x 2^(cards-2).
- 2 cards: 1x   - 3 cards: 2x   - 4 cards: 4x   - 5 cards: 8x   - 6 cards: 16x

**Cost (when you lose)** — linear in the dealer's hand size: bet x (cards-1).
- 2 cards: 1x   - 3 cards: 2x   - 4 cards: 3x   - 5 cards: 4x

---

## Gates

**Basics.** Each card is an Arvonian card showing a **value** and a **gate** in
its corner. A hand is `bit1`, then a card whose corner gate joins it to the
next value: the score folds `bit1 OPCODE bit2` (0-7). The gate used is the one
**printed on the joining card** — no hidden or random operators.

**Betting.** You bet on **which hand wins** — Banker or Player. Bet in units
of 10 to a pot (pot limit 30). Highest total wins. **Banker wins all ties.**

**Opcodes** are the corner gates **AND, OR, NOR, NAND** (the deck has no XOR).
A card's gate depends on its value and colour: `gate = (value + castle) % 4`.
Truth tables:

| A | B | AND | OR | NAND | NOR |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 1 | 1 |
| 0 | 1 | 0 | 1 | 1 | 0 |
| 1 | 0 | 0 | 1 | 1 | 0 |
| 1 | 1 | 1 | 1 | 0 | 0 |

Applied per bit across the 3-bit values, e.g. `5 AND 7 = 5`, `5 OR 7 = 7`,
`5 NAND 7 = 2`, `5 NOR 7 = 0`.

**Hit rule (optional table).** A third bit+opcode may be added:
`score = (bit1 OP bit2) OP bit3`.
- **Player draws** if player total <= 5 **and** banker is not 6 or 7.
- **Banker draws** (baccarat tableau, by banker total and the player's third card):

| Banker total | Draws if player's 3rd card is... |
|---|---|
| 0-1 | always draws |
| 2 | anything except 6 |
| 3 | 2, 3, 4, 5 |
| 4 | 4, 5 |
| 5 | never (stands) |
| 6-7 | stands |

---

## KoraTa — Ghost-Writing

**The head-to-head table.** You duel an opponent (the AI) over **5 rounds**. Each
of you is dealt **5 cards** and builds a scoring **run** — but *you* choose your
values while your *opponent* chooses the logic gates that fold them.

**Every card is two things.** Its **number** is a value; its **corner glyph** is a
gate (AND / OR / NOR / NAND — same as Gates). Play a card **on your own run** to add
its value; play it **on your opponent's run** to drop its gate into their fold. You
can only sabotage with the gates your cards carry.

**The run.** Three values with two gates between them: `v1 OP1 v2 OP2 v3`, folded
left. Your three values are yours; the two gates were placed by your opponent.
**Highest final score wins; ties push.**

**Rounds (V·O·V·O·V).** Value, then Opcode, then Value, Opcode, Value. You place 3
values on your run and 2 gates on your opponent's, one per round.

**Betting.** Ante to start. After **each** opcode round you may **Check, Raise, or
Fold** — Fold and you forfeit the pot. Both runs are face-up, so read the fold and
bet accordingly. Two bet rounds, then showdown.

**3-bit vs 4-bit.** Two tables: values 0–7 (tighter, more ties) or 0–15 (wider
scores). Same rules.
