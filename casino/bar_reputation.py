"""Patron reputation - the trust economy behind bar rumors.

Reputation is a shared 0.0-1.0 reliability stored on the patron dict (patrons
live in the shared bar_pilots/bar_customers dicts, so the whole crew shares
it). A rumor's truth is rolled against reputation; acting on a rumor that pans
out (or doesn't) nudges the patron's reputation, so the crew learns who to
trust over a session.

OpenUniverse blend: when OU is loaded the teller's clan standing can modulate
truth. The casino must not hard-depend on OU, so callers pass an optional
``ou_standing`` (0.0-1.0, or None); the bar resolves it at runtime and passes
None when OU isn't present. See patron_ou_standing().
"""
import random as _random

# Starting reliability for the named NPC patrons; everyone else starts middling.
PATRON_BASE_REP = {"ghost": 0.9, "cogs": 0.8, "barkeep": 0.55}
DEFAULT_REP = 0.5
_OU_WEIGHT = 0.4          # how much OU clan standing pulls the blended truth odds


# ---- pure helpers ----------------------------------------------------------
def clamp01(x):
    return max(0.0, min(1.0, x))

def blended_truth_odds(rep, ou_standing=None):
    """Truth probability: patron reputation, pulled toward OU clan standing when
    one is provided."""
    if ou_standing is None:
        return clamp01(rep)
    return clamp01((1.0 - _OU_WEIGHT) * rep + _OU_WEIGHT * ou_standing)

def trust_label(rep):
    if rep >= 0.8: return "trusted"
    if rep >= 0.6: return "reliable"
    if rep >= 0.4: return "so-so"
    if rep >= 0.2: return "shaky"
    return "unreliable"


# ---- patron-facing (patron is a dict) --------------------------------------
def patron_reputation(patron):
    r = patron.get("reputation")
    return r if r is not None else DEFAULT_REP

def patron_rep_adjust(patron, delta):
    patron["reputation"] = clamp01(patron_reputation(patron) + delta)
    return patron["reputation"]

def patron_trust_label(patron):
    return trust_label(patron_reputation(patron))

def patron_rumor_is_true(patron, ou_standing=None, rng=None):
    """Roll a rumor's truth against the patron's (OU-blended) reliability."""
    odds = blended_truth_odds(patron_reputation(patron), ou_standing)
    return (rng or _random).random() < odds

def patron_seed_base_rep(patron, key):
    """Give a patron its starting reputation once (idempotent)."""
    if patron.get("reputation") is None:
        patron["reputation"] = PATRON_BASE_REP.get(key, DEFAULT_REP)
    return patron["reputation"]


def max_patron_reputation(patrons):
    """Best reputation across a list of patron dicts - the player's standing for
    grey-market access. 0.0 if none."""
    best = 0.0
    for p in patrons:
        r = patron_reputation(p)
        if r > best:
            best = r
    return best


def patron_ou_standing(patron):
    """Hook: return the teller's OpenUniverse clan standing as 0.0-1.0, or None
    when OU isn't loaded. Left as a stub so the casino stays OU-optional; OU (or
    a bridge) can override this to read universe_reputation.clan_standing."""
    return None
