"""Casino cage: side-credits <-> per-client chips, plus bet settlement.

Pure helpers (``clamp_buy``, ``chips_after_delta``) hold the logic and are
unit-tested. The ``casino_*`` wrappers touch the procedural inventory API and
are thin. Imported into MAST as a helper module (``import casino_economy.py``).

Ledgers:
  side credits : get/set_inventory_value(side_id, "credits", n)   (shared)
  chips        : get/set_inventory_value(client_id, "chips", n)   (per client)
  casino_net   : per-client session net win/loss (for comps)
"""
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.sides import to_side_id

DEFAULT_CHIP_CAP = 100
DEFAULT_CHIP_RATE = 1
CASINO_WELCOME_STAKE = 50   # one-time free chips so the casino is playable


# ---- pure helpers (no sbs) ------------------------------------------------
def clamp_buy(have, requested, cap):
    """How many chips can actually be bought: non-negative, capped at room."""
    if requested <= 0:
        return 0
    room = cap - have
    return max(0, min(requested, room))

def chips_after_delta(have, delta):
    """New balance after a signed payout; never below 0 (no debt in v1)."""
    return max(0, have + delta)


# ---- sbs wrappers ---------------------------------------------------------
def _side_of_ship(ship_id):
    ship = to_object(ship_id)
    if ship is None or not getattr(ship, "side", None):
        return None
    return to_side_id(ship.side)

def casino_side_of_client(client_id):
    """Resolve the side whose wallet a client draws chips from.
    Prefers the client's current ship; falls back to a stashed ``side`` key."""
    ctx = FrameContext.context
    if ctx is not None and ctx.sbs is not None:
        ship = ctx.sbs.get_ship_of_client(client_id)
        if ship:
            sid = _side_of_ship(ship)
            if sid is not None:
                return sid
    key = get_inventory_value(client_id, "side", None)
    return to_side_id(key) if key else None

def casino_chips_get(client_id):
    return get_inventory_value(client_id, "chips", 0)

def casino_ensure_stake(client_id, amount=CASINO_WELCOME_STAKE):
    """Grant a one-time welcome stake so the casino is playable even before the
    cage works (in the hangar the client has no ship-side wallet, and a mission
    may not seed side credits). Returns chips granted (0 if already given)."""
    if get_inventory_value(client_id, "casino_started", 0):
        return 0
    set_inventory_value(client_id, "casino_started", 1)
    have = casino_chips_get(client_id)
    if have < amount:
        set_inventory_value(client_id, "chips", amount)
        return amount - have
    return 0

def casino_chips_buy(client_id, side_id, amount,
                     cap=DEFAULT_CHIP_CAP, rate=DEFAULT_CHIP_RATE):
    """Buy chips. Spends side credits when a wallet resolves; otherwise the
    house stakes you (no ship-side wallet in the hangar / no economy yet), so a
    player can always buy back in and never gets locked out. Returns chips
    actually bought. See CASINO_ECONOMY.md."""
    have = casino_chips_get(client_id)
    amount = clamp_buy(have, amount, cap)
    if amount <= 0:
        return 0
    if side_id is None:
        set_inventory_value(client_id, "chips", have + amount)   # house comp
        return amount
    credits = get_inventory_value(side_id, "credits", 0)
    if credits < amount * rate:
        amount = credits // rate            # buy only what the wallet affords
        if amount <= 0:
            return 0
    set_inventory_value(side_id, "credits", credits - amount * rate)
    set_inventory_value(client_id, "chips", have + amount)
    return amount

def casino_chips_cash_out(client_id, side_id, amount=None, rate=DEFAULT_CHIP_RATE):
    """Cash chips back to a side wallet. amount=None cashes out all.
    Returns credits paid."""
    have = casino_chips_get(client_id)
    if amount is None or amount > have:
        amount = have
    if amount <= 0 or side_id is None:
        return 0
    set_inventory_value(client_id, "chips", have - amount)
    credits = get_inventory_value(side_id, "credits", 0)
    set_inventory_value(side_id, "credits", credits + amount * rate)
    return amount * rate

def casino_bet_apply(client_id, delta):
    """Apply a signed engine payout to the client's chips (clamped >=0).
    Also tracks session net for comps. Returns the new chip balance."""
    have = casino_chips_get(client_id)
    new = chips_after_delta(have, delta)
    set_inventory_value(client_id, "chips", new)
    net = get_inventory_value(client_id, "casino_net", 0)
    set_inventory_value(client_id, "casino_net", net + (new - have))
    return new

def casino_net(client_id):
    """Session net win/loss for comp thresholds."""
    return get_inventory_value(client_id, "casino_net", 0)


# Hot-streak comps: (net-win threshold, bonus chips, name). One-time each.
CASINO_COMP_TIERS = [(50, 10, "hot streak"), (100, 25, "high roller"),
                     (250, 50, "the house's favorite")]

def casino_check_comps(client_id):
    """Grant any newly-earned one-time streak comps (bonus chips) based on the
    session net win. Returns a message for the highest comp just granted, or
    None. Comps are gifts - they don't count toward casino_net."""
    net = casino_net(client_id)
    msg = None
    for threshold, bonus, name in CASINO_COMP_TIERS:
        if net >= threshold:
            flag = "casino_comp_%d" % threshold
            if not get_inventory_value(client_id, flag, 0):
                set_inventory_value(client_id, flag, 1)
                set_inventory_value(client_id, "chips",
                                    casino_chips_get(client_id) + bonus)
                msg = "The house comps you %d chips - %s!" % (bonus, name)
    return msg


# ---- market wallet: prices are in chips; spend chips first, then side credits
# (the cage's exchange rate), so big-ticket gear exceeds the chip cap and draws
# the crew wallet. Selling refunds to side credits.
def casino_buying_power(client_id, side_id, rate=DEFAULT_CHIP_RATE):
    """Total spendable, in chip-equivalents (chips + affordable side credits)."""
    credits = get_inventory_value(side_id, "credits", 0) if side_id else 0
    return casino_chips_get(client_id) + (credits // rate)

def casino_market_spend(client_id, side_id, price, rate=DEFAULT_CHIP_RATE):
    """Pay `price` (in chips) from chips first, then side credits. True if paid."""
    if price <= 0:
        return True
    chips = casino_chips_get(client_id)
    if chips >= price:
        set_inventory_value(client_id, "chips", chips - price)
        return True
    remainder = price - chips                       # still owed, in chips
    credits = get_inventory_value(side_id, "credits", 0) if side_id else 0
    if credits < remainder * rate:
        return False
    set_inventory_value(client_id, "chips", 0)
    set_inventory_value(side_id, "credits", credits - remainder * rate)
    return True

def casino_market_refund(client_id, side_id, amount, rate=DEFAULT_CHIP_RATE):
    """Refund a sale to the side wallet (amount in chips-equivalent)."""
    if amount <= 0 or side_id is None:
        return 0
    credits = get_inventory_value(side_id, "credits", 0)
    set_inventory_value(side_id, "credits", credits + amount * rate)
    return amount * rate
