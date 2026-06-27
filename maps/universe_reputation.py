"""Per-captain reputation with clans (Open Universe, Epic F).

Distinct from diplomacy (which is side-wide "are we at war?"): reputation is how a
clan sees a *captain*. Stored on the captain's ship agent (the inventory key
"reputation") so every read/write point - comms origin, kill credit, scans,
persistence - keys the same way; persisted per ship name with items/quests.

Model: 7 axes, each a signed spectrum -100..+100. Authors use either POLE name
(e.g. "honest" / "liar"); a pole maps to a canonical axis + sign, so gating on
either pole works (honest>40 == liar<-40). See UNIVERSE_CHANGES.md (Epic F).
"""
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value

REP_MIN = -100
REP_MAX = 100

# pole -> (canonical axis, sign). +pole raises the axis, -pole lowers it.
REP_POLES = {
    "honest": ("honesty", 1),        "liar": ("honesty", -1),
    "fearsome": ("nerve", 1),        "cowardly": ("nerve", -1),
    "peaceful": ("temperament", 1),  "violent": ("temperament", -1),
    "generous": ("generosity", 1),   "selfish": ("generosity", -1),
    "kind": ("kindness", 1),         "cruel": ("kindness", -1),
    "resourceful": ("method", 1),    "by_the_book": ("method", -1),
    "intellectual": ("intellect", 1), "foolish": ("intellect", -1),
}


def _rep_map(agent_id):
    return get_inventory_value(agent_id, "reputation", None) or {}


def _axis_sign(pole):
    return REP_POLES.get(pole, (pole, 1))


def reputation_get(agent_id, clan, pole, default=0):
    """Reputation of a captain (agent) with a clan along a pole.

    Returns the value oriented to the POLE asked for: reading "honest" gives the
    honesty axis, reading "liar" gives its negation. Unset -> default.
    """
    axis, sign = _axis_sign(pole)
    cm = _rep_map(agent_id).get(clan)
    if not isinstance(cm, dict) or axis not in cm:
        return default
    return sign * cm[axis]


def reputation_adjust(agent_id, clan, pole, delta):
    """Shift a captain's reputation with a clan along a pole (clamped).

    delta is in the pole's direction (adjust "honest" +10 raises honesty; adjust
    "liar" +10 lowers it). Returns the new canonical axis value.
    """
    axis, sign = _axis_sign(pole)
    reps = _rep_map(agent_id)
    cm = reps.get(clan)
    if not isinstance(cm, dict):
        cm = {}
        reps[clan] = cm
    val = max(REP_MIN, min(REP_MAX, cm.get(axis, 0) + sign * delta))
    cm[axis] = val
    set_inventory_value(agent_id, "reputation", reps)
    return val


def reputation_apply(agent_id, rep_block):
    """Apply a declarative rep block: { clan: { pole: delta, ... }, ... }."""
    if not isinstance(rep_block, dict):
        return
    for clan, poles in rep_block.items():
        if isinstance(poles, dict):
            for pole, delta in poles.items():
                reputation_adjust(agent_id, clan, pole, delta)
