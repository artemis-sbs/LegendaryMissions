# Casino card assets

Sprite sheets for the casino card games. Register sub-rects with
`gui_image_add_atlas` once at setup; draw cards anywhere with `gui_image` /
text-area `image://` using the keys below.

**Location:** the PNGs live in the LM media source at
`LegendaryMissions/media/LegendaryMissions/casino/` (not this folder), so they
resolve the same way as the hangar's media - the atlas path is
`media/LegendaryMissions/casino/<file>`, resolved against the running mission's
folder. `casino_media.py` (`CASINO_MEDIA`) centralizes this path. This file is
just the reference doc.

## arvonian_deck.png  (4096 x 1024)

The bit-based **Arvonian deck**, 64 cards. 16 value columns (0-15) x 4
**castle-type** rows, **256 x 256** per cell. Used by nibble (0-15), gates
(0-7 only), and Choga (0-15). The 0-value card carries the whale art.

- column = value: `col = value` (x = value * 256)
- row = **castle/type** (the 2-bit artwork variety, color-themed): 0 red,
  1 purple, 2 blue, 3 green (y = type * 256)

The row is the card's 2-bit `type` ("castle") — it is nibble's score field
(`popcount(type) * 2^position`) and Choga's flush grouping (a "flush" = 5
cards of the same castle-type/row). It is NOT a separate color axis; the
colors just theme the four types.

```python
CELL = 256
for castle in range(4):        # 0-3 = the 2-bit castle/type (= "suit")
    for value in range(16):
        gui_image_add_atlas(f"card_arv_{castle}_{value}",
            "media/arvonian_deck",
            value*CELL, castle*CELL, value*CELL+CELL, castle*CELL+CELL)
```

## terran_deck.png  (2470 x 1120)

Standard **Terran deck**, 52 cards. 13 rank columns x 4 suit rows,
**190 x 280** per cell. Source: Wikimedia Commons
`English_pattern_playing_cards_deck_PLUS_CC0.svg` (CC0 / public domain, no
attribution required). Used by blackjack and (later) poker.

- column = rank: A,2,3,4,5,6,7,8,9,10,J,Q,K -> col 0..12
- row = suit: 0 spades, 1 hearts, 2 diamonds, 3 clubs

```python
CW, CH = 190, 280
RANKS = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
SUITS = ["spades","hearts","diamonds","clubs"]
for s, suit in enumerate(SUITS):
    for c, rank in enumerate(RANKS):
        gui_image_add_atlas(f"card_ter_{suit}_{rank}",
            "media/terran_deck",
            c*CW, s*CH, c*CW+CW, s*CH+CH)
```

## arvonian_back.png  (256 x 256)

Card back for the Arvonian deck — slate-blue rounded card, diamond frame with
a faint binary bit-lattice, gate-node corner accents. Draw for face-down
Arvonian cards (nibble / gates / Choga). Full-image atlas key:
`gui_image_add_atlas("card_arv_back", "media/arvonian_back")`.

## terran_back.png  (190 x 280)

Single blue card back — draw for face-down Terran cards / other players'
hands. Register as a full-image atlas key:
`gui_image_add_atlas("card_ter_back", "media/terran_back")`.

## terran_jokers.png  (380 x 280)

Two jokers side by side (190px each). Not needed for blackjack/poker;
included for completeness. Left half = joker A, right half = joker B.

## Notes

- Backgrounds are transparent, so cards composite cleanly on any table felt.
- Both decks have a card back (`arvonian_back.png`, `terran_back.png`). The
  Arvonian back is procedurally generated (slate-blue bit-lattice), not from
  the card generator; regenerate to match if the deck theme changes.
- All sheets are the "red" generator theme; regenerate from
  `F:\c\gh\nibble-card-generator\build\sheets` if a different theme is
  chosen. Source cells are 512px; these are downscaled (Arvonian 256, Terran
  190x280) since cards render at ~100-150px on console pages.
