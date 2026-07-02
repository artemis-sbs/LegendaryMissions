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

**Basics.** Each hand gets a **bit card**, then an **opcode card**, then a
second **bit card**. The hand's score is `bit1 OPCODE bit2` (0-7).

**Betting.** You bet on **which hand wins** — Banker or Player. Bet in units
of 10 to a pot (pot limit 30). Highest total wins. **Banker wins all ties.**

**Opcodes** are logic gates: **AND, OR, NOR, NAND, XOR** (XOR appears on face
cards). Truth tables:

| A | B | AND | OR | NAND | NOR | XOR |
|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 1 | 1 | 0 |
| 0 | 1 | 0 | 1 | 1 | 0 | 1 |
| 1 | 0 | 0 | 1 | 1 | 0 | 1 |
| 1 | 1 | 1 | 1 | 0 | 0 | 0 |

Applied per bit across the 3-bit values, e.g. `5 AND 7 = 5`, `5 OR 7 = 7`,
`5 NAND 7 = 2`, `5 NOR 7 = 0`, `5 XOR 7 = 2`.

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
