# Casino economy — cage, chips, comps, consequences

How money moves. Two ledgers:
- **Side credits** — the shared crew wallet, per side:
  `get/set_inventory_value(side_id, "credits", n)`. Same pool the market and
  OpenUniverse use. `side_id = to_side_id(to_object(ship_id).side)`.
- **Chips** — personal, per client: `get/set_inventory_value(client_id,
  "chips", n)`. Bought from side credits at the cage; only chips are wagered.

## The cage

Buy chips from the side wallet (capped per client), cash out chips back to the
side wallet. 1 chip = 1 credit (`chip_rate`, tunable).

```
casino_chips_get(client_id) -> int
    return get_inventory_value(client_id, "chips", 0)

casino_chips_buy(client_id, ship_id, amount) -> bool
    # cap: chips on hand + amount must not exceed chip_cap (default 100)
    # cost: amount * chip_rate credits from the ship's side wallet
    have  = casino_chips_get(client_id)
    if have + amount > CHIP_CAP: amount = CHIP_CAP - have      # clamp, or reject
    sid   = to_side_id(to_object(ship_id).side)
    cost  = amount * CHIP_RATE
    if amount <= 0 or get_inventory_value(sid,"credits",0) < cost: return False
    set_inventory_value(sid,"credits", credits - cost)
    set_inventory_value(client_id,"chips", have + amount)
    return True

casino_chips_cash_out(client_id, ship_id, amount=None) -> int
    # amount None -> cash out all; add amount*chip_rate credits to side wallet
    ...returns credits paid

casino_bet_apply(client_id, delta) -> int
    # delta is the signed payout from an engine settle(); clamp so chips never
    # go below 0 in v1 (no credit/debt). returns new chip balance
    new = max(0, casino_chips_get(client_id) + delta)
    set_inventory_value(client_id,"chips", new); return new
```

**Cap is per client** (default 100). Enforce at buy time. Chips persist across
tables within a docking; **cash out (or forfeit) on undock / launch**.

## settings.yaml

```yaml
CASINO:
    enable: true
    chip_cap: 100          # max chips a client may hold
    chip_rate: 1           # credits per chip
    table_min:
        nibble: 5
        gates: 10          # gates bets in units of 10 (pot limit 30)
        blackjack: 5
        choga: 5           # ante; raise = 2x
    comps: true
    debt: false            # loan-shark escalation (deferred)
```

Read via `settings_get_defaults()` like the rest of LM.

## Benefits (why gamble)

- **Winnings -> side credits -> items/upgrades** through the existing market.
  No new plumbing; cashing out feeds the crew's buying power.
- **Comps** (if `comps: true`) keyed off a session net-win tracker
  (`inventory_value(client_id, "casino_net", 0)`):
  | Net chips up | Comp |
  |---|---|
  | +50 | free drink at the bar (skip the drinks-stock cost) |
  | +100 | an impressed patron passes a rumor (see bar.amd) |
  | +250 | one-time market discount token at this station |
- **Rumors as intel** — a true rumor can seed a hangar quest, reveal a
  salvage location, or mark the map (see bar.amd / rumors in BAR.md).

## Consequences

- **Losses are real side credits** (bounded by the per-client 100-chip cap
  per docking — you can only lose what you bought in).
- **Forfeit on launch mid-hand** — chips staked at an active table are lost if
  the player launches (commitment to the table).
- **Time cost** — a pilot at the table isn't in a cockpit while the side
  fights. This is the core "play vs fly" tension; no code needed.
- **Debt (deferred, `debt: false`):** allow chips < 0 up to a limit -> a
  loan-shark NPC marks the debt; spawns a collection encounter or a
  work-it-off quest; unpaid debt dings side standing with the station.

## Data keys (for the loader / persistence)

| Key | On | Meaning |
|---|---|---|
| `chips` | client | current chip balance |
| `casino_net` | client | session net win/loss (for comps) |
| `credits` | side | shared wallet (existing) |
| `casino_comp_<tier>` | client | comp already granted this session |

All are plain inventory values, consistent with `items.py`/market.
