"""Per-system POI deck for the Open Universe (Epic B - richer systems).

A system = a **template core** (the primary station / garrison / anomaly, spawned
by universe.mast's kind if/elif) + a keyed, weighted **deck** of extra POIs. This
module is the deck: given a system's key + kind + owner, it returns a list of POI
descriptors (MastDataObject: type + x/y/z + params), drawn deterministically from
the key so a system looks the same each visit. universe.mast spawns whatever the
deck returns.

Keeping the deck here (pure Python, stdlib only) makes the content + weights
data-driven and unit-testable, separate from the MAST spawn calls. POI types:
loot (trade-good cache), derelict (scannable wreck), outpost (secondary clan
holding), mines (lethal field in foe territory). See UNIVERSE_CHANGES.md
Appendix D.
"""
import math
import random
from sbs_utils.mast.mast_node import MastDataObject

_LOOT_KEYS = ["ore", "gas", "provisions", "tech", "contraband"]
_OUTPOST_ART = {
    "trader": ["starbase_industry", "starbase_civil"],
    "settler": ["starbase_civil"],
    "military": ["starbase_command", "starbase_industry"],
    "mercenary": ["starbase_industry", "starbase_command"],
    "pirate": ["starbase_industry"],
    "cult": ["starbase_science"],
}
_OUTPOST_ART_DEFAULT = ["starbase_civil", "starbase_industry"]


def _ring_pos(r, rmin, rmax):
    """A random point on a flat ring (y near 0) - returns (x, y, z)."""
    ang = r.uniform(0, 2 * math.pi)
    dist = r.uniform(rmin, rmax)
    return (math.cos(ang) * dist, r.uniform(-300.0, 300.0), math.sin(ang) * dist)


def universe_system_deck(key, kind, owner, archetype=None, foe=False, difficulty=5):
    """POI descriptors for a system, drawn deterministically from its key.

    key       int system key (universe_system_key)
    kind      effective kind ('home'/'station'/'enemy'/'nebula'/'anomaly'/'empty')
    owner     owning clan key, or None
    archetype owning clan's archetype (flavors outpost art), or None
    foe       True if the owner is hostile to the player side
    difficulty mission difficulty (scales mine count)

    Returns a list of MastDataObject, each with .type and .x/.y/.z plus:
      loot     -> .item_key
      derelict -> (position only)
      outpost  -> .side, .art   (a secondary clan holding; tagged station+outpost)
      mines    -> .count
    """
    r = random.Random()
    r.seed(key + 101)
    pois = []

    # Loot caches - trade-good pickups, denser in nebula/anomaly.
    n_loot = r.randint(0, 2)
    if kind == "nebula" or kind == "anomaly":
        n_loot += 2
    for _ in range(n_loot):
        x, y, z = _ring_pos(r, 8000, 40000)
        pois.append(MastDataObject({
            "type": "loot", "item_key": r.choice(_LOOT_KEYS), "x": x, "y": y, "z": z}))

    # Derelict - a scannable wreck POI. Hidden wrecks are likelier in nebulae.
    p_der = 0.7 if kind == "nebula" else 0.4
    if r.random() < p_der:
        x, y, z = _ring_pos(r, 10000, 35000)
        pois.append(MastDataObject({"type": "derelict", "x": x, "y": y, "z": z}))

    # Secondary outpost - clan systems sometimes have a second, smaller holding
    # (extra clan-work giver / capture-adjacent flavor). Clan systems only, so the
    # side is always a real registered side.
    if owner is not None and r.random() < 0.4:
        arts = _OUTPOST_ART.get(archetype, _OUTPOST_ART_DEFAULT)
        x, y, z = _ring_pos(r, 12000, 30000)
        pois.append(MastDataObject({
            "type": "outpost", "side": owner, "art": r.choice(arts), "x": x, "y": y, "z": z}))

    # Mine field - foe territory seeds lethal terrain to clear or avoid.
    if foe and r.random() < 0.5:
        x, y, z = _ring_pos(r, 6000, 18000)
        pois.append(MastDataObject({
            "type": "mines", "count": 3 + int(difficulty) // 3, "x": x, "y": y, "z": z}))

    return pois
