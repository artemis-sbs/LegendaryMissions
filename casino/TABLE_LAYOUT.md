# Casino table layout — GUI spec

The shared table view every card game reuses. **Presentation is shared**
(everyone sees the same dealer + the other seats), **logic is per-seat**
(each console acts on its own hand vs the dealer). Built once as a table
framework; each game plugs in its card area + action buttons.

## Screen regions (percent coords, within the hangar tab content area)

```
+-----------------------------------------------------------+  <- hangar tabs
|                     DEALER  (0,0 - 100,30)                 |
|   [dealer face]      [dealer cards]         [message]      |
+-------------+-------------------------------+-------------+
|  OTHER      |                               |  OTHER      |
|  SEATS      |        TABLE / MY HAND        |  SEATS      |
|  (left)     |        (25,30 - 75,72)        |  (right)    |
| 0,30-25,88  |   my face-up cards, big       | 75,30-100,88|
|  seat panel |   shared pot / state          |  seat panel |
|  seat panel |                               |  seat panel |
+-------------+-------------------------------+-------------+
|          MY SEAT + CONTROLS  (0,88 - 100,100)             |
|  chips: NNN   bet: [-][10][+]    [Hit] [Stand] / [Raise]  |
+-----------------------------------------------------------+
```

### Region details
- **Dealer strip** `gui_section("area:0,0,100,30;")` — dealer `gui_face`, the
  dealer's cards (one up during play, rest revealed at showdown), and the
  status/result message. In Choga/gates the "dealer" is flavored **the
  Understander**.
- **Table / my hand** `gui_section("area:25,30,75,72;")` — the acting
  player's own cards, large and face-up, plus any shared state (gates pot,
  Choga ante/raise). This is the only region whose card widgets differ much
  per game.
- **Other seats** — two columns, `gui_section("area:0,30,25,88;")` and
  `("area:75,30,100,88;")`. Each occupied seat is a small panel: `gui_face`,
  call sign, current bet, and **card backs** (`card_arv_back` /
  `card_ter_back`) for their concealed hand. Reuse the existing bar patron
  listbox styling (`list_box_control` with face + title) — the bar already
  renders a live multi-client list, so lift that.
- **My seat + controls** `gui_section("area:0,88,100,100;")` — my chip
  balance, a bet stepper (bounded by the per-client 100-chip cap), and the
  game action buttons.

## Per-game action buttons (only this differs)
- **Nibble / Blackjack:** `Hit`, `Stand`. (Blackjack later: `Double`,
  `Split`.)
- **Gates:** bet phase `Bet Player` / `Bet Banker`; then `Deal`. (You wager
  on a hand, you don't "hit" yourself.)
- **Choga:** `Ante` -> after seeing cards `Raise` / `Fold`.

## Seat model
Seats are **player-only in v1**. A seat = `{client_id, call_sign, face, bet,
hand, state}`. The acting console owns exactly one seat (its own); all seats
are drawn from a shared table object so every console shows the same
occupancy. Max seats per table: cap at ~4-6 (two side columns); overflow
players wait or open a second table instance.

## Live updates (watch / repaint)
Use the established watch pattern (see MAST_MISSION_CLAUDE.md "Watch /
repaint"): a `gui_sub_task_schedule("watch")` polls the shared table object;
when another seat's bet/hand/state changes, `gui_task_jump("repaint")` so the
side-seat panels refresh without a full rebuild. Card widgets update in place
via the dirty system (set `.value`/props; `gui_represent` is deprecated).

## Notes
- Card sizing: cells render ~100-150px; a hand of 5 fits the table region at
  ~12-15% width each with slight overlap (fan). Use `gui_image` with the
  atlas keys; overlap by drawing into a row with negative spacing or absolute
  offsets.
- Keep the framework game-agnostic: a `table_render(table, my_seat,
  card_area_fn, buttons)` shape where only `card_area_fn` and `buttons` vary
  per game. That is the "reusable core" Phase 2 (nibble) should build.
- Same labels must not assume the hangar client, so the future docked-console
  casino can reuse them (see BAR.md deferred).
