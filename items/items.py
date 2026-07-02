"""Market/economy for the discoverable item system.

The item registry and pickup spawning moved to ``sbs_utils.procedural.items`` so they
are available on the sbslib alone; they are re-exported below for backward
compatibility (all existing ``pickup_spawn`` / ``terrain_spawn_pickups`` / ``item_spawn``
call sites keep working unchanged). This module now owns the market/economy layer,
which reads the registry from core.
"""
import random
from sbs_utils import scatter
from sbs_utils.procedural.execution import labels_get_type
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.sides import to_side_id
from sbs_utils.procedural.signal import signal_emit

# Registry + spawning now live in core sbs_utils; re-export for backward compat.
from sbs_utils.procedural.items import (  # noqa: F401
    items_get_list, item_get, item_meta, item_keys, items_of_category,
    item_spawn, terrain_spawn_items, pickup_spawn, terrain_spawn_pickups,
)


# --- Market / economy --------------------------------------------------------
# Credits are a shared per-side pool. Station stock lives on the station agent
# (stock_<key>); a station is "seeded" finite, or treated as unlimited if not.
MARKET_SELL_FACTOR = 0.5
# A side can carry a buy-price subsidy (0..1): whoever funds it (e.g. the Open
# Universe Admiral console) writes the rate to the side agent's `market_subsidy`
# inventory, and that side's ships buy at (1 - rate) of the price. Selling is
# never subsidised. Capped so a subsidy can never approach free goods.
MARKET_SUBSIDY_MAX = 0.5


def market_subsidy_rate(side):
    """A side's active buy-price subsidy (0..MARKET_SUBSIDY_MAX). 0 when unset
    or invalid. `side` is a side key/id/agent (to_side_id resolves it)."""
    sid = to_side_id(side)
    if sid is None:
        return 0.0
    try:
        rate = float(get_inventory_value(sid, "market_subsidy", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(MARKET_SUBSIDY_MAX, rate))


def market_purchasable():
    """Item labels with a positive price (buyable/sellable)."""
    ret = []
    for lbl in labels_get_type("item/"):
        if (lbl.get_inventory_value("price", 0) or 0) > 0:
            ret.append(lbl)
    return ret


def market_is_seeded(station_id):
    return get_inventory_value(station_id, "market_seeded", 0) == 1


def market_stock(station_id, key):
    """Units of `key` a station has; a large number when not finite-seeded."""
    if not market_is_seeded(station_id):
        return 9999
    return get_inventory_value(station_id, "stock_" + key, 0)


def _disposition_for(seed_key, idx):
    """Per-(sector, item) price multiplier in [0.5, 1.5): low = producer
    (cheap, well-stocked), high = consumer (dear, wants it). Deterministic."""
    return 0.5 + random.Random(scatter._mix(int(seed_key), idx + 1000)).random()


def _purchasable_index(key):
    for i, lbl in enumerate(market_purchasable()):
        if lbl.get_inventory_value("key") == key:
            return i
    return None


def market_disposition(station_id, key):
    """Station's price disposition for an item (1.0 if not finite-seeded)."""
    seed_key = get_inventory_value(station_id, "market_seed_key", None)
    if seed_key is None:
        return 1.0
    idx = _purchasable_index(key)
    return 1.0 if idx is None else _disposition_for(int(seed_key), idx)


def market_price(station_id, key, ship_id=None):
    """Current buy price = base price x the station's disposition, discounted by
    the buyer side's subsidy when a `ship_id` is given (so the price shown, the
    affordability check, and the charge all agree). Omit `ship_id` for the
    undiscounted list price (e.g. sell payouts)."""
    lbl = item_get(key)
    base = (lbl.get_inventory_value("price", 0) or 0) if lbl is not None else 0
    price = base * market_disposition(station_id, key)
    if ship_id is not None:
        ship = to_object(ship_id)
        if ship is not None and ship.side:
            price *= (1.0 - market_subsidy_rate(ship.side))
    return int(round(price))


def market_sell_price(station_id, key):
    """What a station pays to buy an item from the player."""
    return int(market_price(station_id, key) * MARKET_SELL_FACTOR)


def market_seed(station_id, seed_key):
    """Deterministically stock a station's market (finite), keyed by seed_key.

    Same seed_key (e.g. a sector key) reproduces the same stock and prices.
    Producers (low disposition) are well-stocked; consumers (high) near-empty.
    """
    set_inventory_value(station_id, "market_seed_key", int(seed_key))
    for i, lbl in enumerate(market_purchasable()):
        k = lbl.get_inventory_value("key")
        disp = _disposition_for(int(seed_key), i)
        qty = max(0, round((1.6 - disp) * 4))
        set_inventory_value(station_id, "stock_" + k, qty)
    set_inventory_value(station_id, "market_seeded", 1)


def market_snapshot(station_id):
    """Current stock as {key: qty} (for persistence)."""
    snap = {}
    for lbl in market_purchasable():
        k = lbl.get_inventory_value("key")
        snap[k] = get_inventory_value(station_id, "stock_" + k, 0)
    return snap


def market_restore(station_id, snapshot):
    """Apply a saved stock snapshot to a station (marks it finite-seeded)."""
    if not isinstance(snapshot, dict):
        return
    for k, qty in snapshot.items():
        set_inventory_value(station_id, "stock_" + k, qty)
    set_inventory_value(station_id, "market_seeded", 1)


def _ship_side_id(ship_id):
    ship = to_object(ship_id)
    return to_side_id(ship.side) if ship is not None and ship.side else None


def market_buy(ship_id, station_id, key):
    """Buy one `key` for the ship from the station, paying side credits (the
    buyer side's subsidy discounts the price)."""
    if item_get(key) is None:
        return False
    price = market_price(station_id, key, ship_id)
    sid = _ship_side_id(ship_id)
    if sid is None or price <= 0:
        return False
    credits = get_inventory_value(sid, "credits", 0)
    if credits < price or market_stock(station_id, key) <= 0:
        return False
    set_inventory_value(sid, "credits", credits - price)
    set_inventory_value(ship_id, key, get_inventory_value(ship_id, key, 0) + 1)
    if market_is_seeded(station_id):
        set_inventory_value(station_id, "stock_" + key,
                            get_inventory_value(station_id, "stock_" + key, 0) - 1)
    signal_emit("item_bought", {"holder_id": ship_id, "station_id": station_id, "key": key})
    signal_emit("item_changed", {"holder_id": ship_id})
    return True


def market_sell(ship_id, station_id, key):
    """Sell one `key` from the ship to the station for side credits."""
    lbl = item_get(key)
    if lbl is None:
        return False
    owned = get_inventory_value(ship_id, key, 0)
    if owned <= 0:
        return False
    sid = _ship_side_id(ship_id)
    if sid is None:
        return False
    payout = market_sell_price(station_id, key)
    set_inventory_value(sid, "credits", get_inventory_value(sid, "credits", 0) + payout)
    set_inventory_value(ship_id, key, owned - 1)
    if market_is_seeded(station_id):
        set_inventory_value(station_id, "stock_" + key,
                            get_inventory_value(station_id, "stock_" + key, 0) + 1)
    signal_emit("item_sold", {"holder_id": ship_id, "station_id": station_id, "key": key})
    signal_emit("item_changed", {"holder_id": ship_id})
    return True
