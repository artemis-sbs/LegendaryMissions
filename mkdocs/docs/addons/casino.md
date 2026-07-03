# The Casino

Give your crew somewhere to unwind. The **Casino** is a hangar-bay hangout: a
**bar** with regulars who trade gossip, six **games of chance**, and a **pilot
market** where winnings buy real ship upgrades. It runs on an Arvonian card
deck &mdash; the computer-loving Arvonians play with bit-based cards, and the
house dealer in some games is flavored as **the Understander**, their revered
master computer.

It's optional and self-contained. Add it and a **Casino** tab appears in the
bay; leave it out and nothing changes.

> Looking for the rules of each game as a **player**? See
> [How to play the Casino](../playing/casino.md). This page is for **authors**
> adding the casino to a mission.

---

## Add it to your mission

You need the **hangar** (the casino lives in the bay) and the **casino** addon.
In your mission's `story.json`, add both to the `mastlib` list:

```json
{
    "mastlib": [
        "artemis-sbs.LegendaryMissions.hangar.v1.4.0.mastlib",
        "artemis-sbs.LegendaryMissions.casino.v1.4.0.mastlib"
    ]
}
```

That's the whole setup. When a pilot is in the hangar, a **Casino** tab shows
up. No other wiring, and the hangar still works fine if you ever remove the
casino line.

Every visitor starts with a small stack of chips so they can play right away,
and they can always buy back in &mdash; nobody gets stuck.

---

## What your crew finds

- **The bar.** Bitters the Torgoth barkeep pours drinks; regulars like **Ghost**
  (a quiet pilot) and **Cogs** (a mechanic who hears things) sit around. Buy a
  patron a drink, toast the room, or ask them for a rumor.
- **Six games.** Pick one from the lobby list; each has a "how to play" blurb
  and a **Play** button.

    | Game | Feel |
    |---|---|
    | **Nibble** | Blackjack-ish on the Arvonian deck &mdash; a tough table |
    | **Gates** | Bet on which logic-gate hand wins (baccarat-style) |
    | **Choga** | Arvonian stud poker vs. the Understander |
    | **Blackjack** | Classic 21 |
    | **Video Poker** | Jacks-or-Better, hold and draw |
    | **Parity** | A fast "wheel" &mdash; bet even/odd or high/low |

- **The pilot market.** Spend winnings on **craft upgrades** and gear. Chips go
  first, then the crew's shared credits, so a big upgrade can dip into the ship's
  funds.
- **Trust and rumors.** Every patron has a **reputation**. A tip from a trusted
  patron usually pans out; a burned one loses your trust and starts steering you
  wrong. Earn enough trust and the market's **grey market** opens up.

---

## Make it your own

You don't need to be a programmer to change the flavor. The whole social layer
of the bar &mdash; the regulars, their rumors, and the ambient chatter &mdash;
is one authored file, **`casino/bar.amd`**. It reads like a script: copy a
block, change the words.

### Add a rumor a patron can tell

In **`casino/bar.amd`**, each patron is a `#` heading and each rumor is a `##`
heading under them. The line the patron **says** is the prose under the heading;
the payoff shown if it pans out is the `intel:` line. Add one under a patron:

```
## [rumor: minefield](ghost_r4)
---
intel: "Ghost was right - and it's carrying salvage."
---
Something big is squatting in the old minefield.
```

Whether a rumor turns out **true** is rolled against that patron's reputation,
so you don't mark it true or false yourself &mdash; just write the line they say
and the good outcome. Give each new rumor a unique key in the `(parentheses)`.

### Add a bar regular

Add another `#` heading in **`casino/bar.amd`**. The `---` block sets their
call sign, face, and starting trust; the prose beneath is their vibe:

```
# [Sparks](sparks)
---
call_sign: Sparks
face_kind: terran_male
reliability: 0.6
---
A comms rating who overhears half the sector and repeats a third of it.
```

`face_kind` is `torgoth_male`, `terran_male`, or `terran_female`;
`reliability` (0.0&ndash;1.0) is how often their rumors ring true to start.
Ambient one-liners the regulars mutter live in the `# [Chatter]` block at the
bottom of the same file &mdash; add lines to its `lines:` list for more color.

### Add a drink

The bar's drink stock is in **`casino/bar.mast`** (the top few lines):

```
shared bar_martinis = 10        # change the numbers to restock
shared bar_beer = 10
shared bar_vodka = 8
```

### Add something to the market

Open **`casino/casino_market.py`** and add a line to the catalog. Each item has
a short **name**, a **price** in chips, a **section**, and a one-line **desc**:

```python
{"key": "targeting_uplink", "name": "Targeting Uplink", "price": 900,
 "section": "upgrade", "desc": "Sharper weapons lock for your craft."},
```

Sections are `upgrade`, `consumable`, `cosmetic`, or `blackmarket` (grey-market
items only appear once the pilot has earned a patron's trust &mdash; set how
much with `"min_rep": 0.8`).

> Prices are in chips. Big-ticket upgrades are meant to cost a lot &mdash; a
> pilot has to win big, or the crew chips in from shared credits.

---

## Add your own game (a bit more advanced)

Every lobby entry &mdash; games and the market alike &mdash; is just a labelled
"room" the casino discovers automatically. To add one, make a new file in
`casino/` with a route at the top:

```
//casino/game/roulette "Roulette"
    jump show_roulette

=== show_roulette ==
    # ...your screen here...
```

...then add `import roulette.mast` to `casino/__init__.mast`. It appears in the
lobby on its own &mdash; no other edits. The simplest existing game,
`parity.mast`, is a good one to copy from.

The rules and payouts for each game live in `casino/games/` as plain,
testable Python, kept separate from the screens &mdash; so a designer can tune
odds without touching the display.
