"""Casino pilot market catalog (pure - no sbs). Goods reference real LM item
keys where they apply to a craft (cockpit upgrades). Prices are in chips (spent
chips-first, then side credits). Grey-market goods are gated by the player's
best bar reputation, tying the bar's trust system to the store.

Cockpit craft upgrades are the example goods and are priced HIGH for now - you
have to win big (or dip into the crew wallet) to afford one.
"""

# section: upgrade | consumable | cosmetic | blackmarket
# key matches an LM item key where one exists (cockpit_shields / torp_bay are
# item/loadout/*, carapaction_coil is item/upgrade/*) so a later pass can apply
# them to the pilot's craft via upgrade_add(); the rest are casino-local.
CASINO_MARKET = [
    {"key": "cockpit_shields", "name": "Cockpit Shields", "price": 800,
     "section": "upgrade", "desc": "Reinforce your craft's shields (x2)."},
    {"key": "torp_bay", "name": "Torpedo Bay", "price": 1200,
     "section": "upgrade", "desc": "Bolt a torpedo bay onto your craft."},
    {"key": "carapaction_coil", "name": "Carapaction Coil", "price": 1500,
     "section": "upgrade", "desc": "Hull-hardening plating."},
    {"key": "coolant_pack", "name": "Coolant Pack", "price": 120,
     "section": "consumable", "desc": "An emergency coolant reserve."},
    {"key": "damcon_kit", "name": "Damcon Kit", "price": 150,
     "section": "consumable", "desc": "Field repair supplies."},
    {"key": "gold_trim", "name": "Gold Trim", "price": 250,
     "section": "cosmetic", "desc": "Flashy gold hull trim - pure swagger."},
    {"key": "call_title", "name": "Call-Sign Title", "price": 200,
     "section": "cosmetic", "desc": "An honorific to flash on your call sign."},
    {"key": "overcharge_core", "name": "Overcharge Core", "price": 4000,
     "section": "blackmarket", "min_rep": 0.75,
     "desc": "Unstable power core. Runs hot. No warranty."},
    {"key": "phase_cloak", "name": "Phase Cloak", "price": 6000,
     "section": "blackmarket", "min_rep": 0.85,
     "desc": "Grey-market cloaking rig. Don't ask where it came from."},
]

SECTION_NAMES = {"upgrade": "Craft Upgrades", "consumable": "Consumables",
                 "cosmetic": "Flair", "blackmarket": "Grey Market"}

def market_goods(max_rep=0.0):
    """Goods on offer at the player's current standing. Grey-market items only
    appear once the player's best patron reputation meets their min_rep."""
    out = []
    for g in CASINO_MARKET:
        if g.get("section") == "blackmarket" and max_rep < g.get("min_rep", 1.0):
            continue
        out.append(g)
    return out

def market_item(key):
    for g in CASINO_MARKET:
        if g["key"] == key:
            return g
    return None

def market_sell_price(g):
    """Buy-back value - ~40% of list."""
    return int(g.get("price", 0) * 0.4)

def market_owned_flag(key):
    """Client-inventory key recording ownership."""
    return "casino_owns_" + key
