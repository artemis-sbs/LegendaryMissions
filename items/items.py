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
from sbs_utils.procedural.timers import is_timer_finished, format_time_remaining
from sbs_utils.procedural.gui import gui_row, gui_text

# Registry + spawning now live in core sbs_utils; re-export for backward compat.
from sbs_utils.procedural.items import (  # noqa: F401
    items_get_list, item_get, item_meta, item_keys, items_of_category,
    item_spawn, terrain_spawn_items, pickup_spawn, terrain_spawn_pickups,
)


# --- Upgrades console tab ----------------------------------------------------
def _fmt_duration(secs):
    """Human duration for an item's effect length: whole minutes as 'N min',
    otherwise 'N sec'."""
    secs = int(secs)
    if secs >= 60 and secs % 60 == 0:
        return f"{secs // 60} min"
    return f"{secs} sec"


def item_describe(lbl):
    """The item's description, with the placeholder phrase 'for a time' expanded
    to the actual effect length when the item declares a `duration` (so timed
    upgrades read 'for 5 min' instead of the vague 'for a time', and stay correct
    if the duration is retuned)."""
    desc = lbl.get_inventory_value("desc", "") or ""
    dur = lbl.get_inventory_value("duration", 0) or 0
    if dur and dur > 0 and "for a time" in desc:
        desc = desc.replace("for a time", "for " + _fmt_duration(dur))
    return desc


def items_upgrade_tab_list(ship_id):
    """Rows for the Upgrades console tab (item_gui.mast): the ship's owned
    activatable items, plus any consumable still counting down (its `have` may be
    0 after activation) so the timer stays visible. Trade goods are cargo (sold
    at markets), not upgrades, so they are excluded. Each row is a dict carrying
    live cooldown state; the tab rebuilds the list each repaint."""
    rows = []
    for lbl in items_get_list():
        k = lbl.get_inventory_value("key")
        have = get_inventory_value(ship_id, k, 0)
        ready = is_timer_finished(ship_id, "item_cd_" + k)
        if have <= 0 and ready:
            continue
        if "trade" in (lbl.get_inventory_value("type", "") or ""):
            continue
        rows.append({
            "key": k,
            "name": lbl.get_inventory_value("display_text", k),
            "desc": item_describe(lbl),
            "have": have,
            "consoles": lbl.get_inventory_value("consoles", "") or "",
            "ready": ready,
            "cd": "" if ready else format_time_remaining(ship_id, "item_cd_" + k),
        })
    return rows


def item_upgrade_row(item):
    """List-box row template for the Upgrades tab: name x count, marked active
    while it is counting down."""
    gui_row("row-height: 1.1em; padding:10px;")
    tag = "" if item.get("ready", True) else "  (active)"
    gui_text(f"$text:{item.get('name', '?')}  x{item.get('have', 0)}{tag};justify:left;")


def item_upgrade_title():
    gui_row("row-height: 1.1em; padding:10px; background:#1578;")
    gui_text("$text:Upgrades;justify:center;")


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
