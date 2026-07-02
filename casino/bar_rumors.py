"""Bar rumor pool. Each patron has tips; asking picks one, its truth is rolled
against the patron's (OU-blended) reputation, and acting on it pays off or
busts and nudges the patron's reputation - so the crew learns who to trust.

Inline for now; this is the content that moves to bar.amd once the AMD keys are
signed off (truth is rolled from reputation, so entries only need tip + payoff).
"""
import random as _random

# key -> list of {tip (what they say), intel (payoff shown if it pans out)}
RUMORS = {
    "ghost": [
        {"tip": "A raider wolfpack is massing past the belt.",
         "intel": "Ghost was right - their staging point is marked. Hit them before they strike."},
        {"tip": "A convoy's coming through the approaches light on escort.",
         "intel": "The convoy's there, just as Ghost said. Easy work for a patrol."},
        {"tip": "Someone's running upgrades through the far station, quiet-like.",
         "intel": "The upgrade cache checks out. Worth a run."},
    ],
    "cogs": [
        {"tip": "There's working tech in the debris field nobody's swept.",
         "intel": "Cogs called it - salvage coordinates logged to your board."},
        {"tip": "That coil batch is bad. Check yours before you launch.",
         "intel": "Two ships limped home with the same fault. Cogs saved you a tow."},
    ],
    "barkeep": [
        {"tip": "DS1's holding a shipment of the good stuff next rotation.",
         "intel": "The restock run pays out - Bitters' tip was solid."},
        {"tip": "Fella swore he saw a derelict cruiser, lights on, nobody aboard.",
         "intel": "There really is a derelict out there. Bitters, you old softie."},
    ],
}

def patron_rumor_pool(key):
    return RUMORS.get(key, [])

def patron_has_rumors(key):
    return len(RUMORS.get(key, [])) > 0

def pick_rumor(key, rng=None):
    pool = patron_rumor_pool(key)
    if not pool:
        return None
    return (rng or _random).choice(pool)
