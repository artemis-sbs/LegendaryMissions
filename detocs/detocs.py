"""DETOCS - the reactive half of the mail pack.

Every word the crew reads lives in `detocs.amd`. This module is only the
arbitration that keeps a joke a joke: a DETOCS advert after every hull hit is
spam, and one that arrives ninety seconds after the crew nearly died is the
punchline. So a taunt is rate limited, capped for the whole mission, and fired
at most once for the events that only happen once.

Two house rules are load-bearing here:

- Every top-level `def` becomes a MAST global in one flat, mission-wide
  namespace, assigned unconditionally, last loaded wins. Hence the `detocs_`
  prefix on everything public and the leading underscore on everything else.
- `__file__` does not exist in a MAST-loaded module, so this file cannot read
  `detocs.amd` itself. The `.mast` reads it with `media_read_relative_file` and
  hands the parsed document to `detocs_configure`.
"""
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.amd_chatter import chatter_scenes, chatter_line
from sbs_utils.procedural.amd_doc import amd_section
from sbs_utils.procedural.messages import message_mail
from sbs_utils.procedural.query import get_data_set_value
from sbs_utils.procedural.roles import has_role

# The sender every unscheduled taunt comes from. The scheduled pack in the .amd
# uses two more voices; a taunt is always marketing.
SENDER = "DETOCS Admissions"

# Sim seconds between taunts, the mission-long cap, and the keys that fire at
# most once no matter what. Tuned so a bad fight produces ONE advert.
COOLDOWN = 180
CAP = 4
ONCE = ("destroyed", "game_over")

# Below these fractions a facing counts as gone. Two shields both this low is
# the "you are about to die" case; one is merely embarrassing.
HULL_LOW_SHIELD = 0.15
SHIELD_DOWN = 0.05

# Per-mission state. Reset by detocs_reset(), which detocs_configure() calls -
# and detocs_configure() runs from the .mast top level, i.e. once per mission
# load. Without that, cosmos_dev's reused interpreter would carry a spent cap
# into run 2 and the taunts would simply stop appearing.
_SCENES = {}
_SUBJECTS = {}
_REPLIES = {}
_REPLY_SUBJECTS = {}
_STATE = {"last": None, "fired": set(), "count": 0}


def detocs_reset():
    """Forget the cooldown, the fired keys and the mission cap."""
    _STATE["last"] = None
    _STATE["fired"] = set()
    _STATE["count"] = 0


def detocs_configure(doc):
    """Take the taunt pools out of the parsed `detocs.amd` document.

    The scheduled mail is loaded separately by `message_load_amd`, which walks
    the same document and keeps only headings whose fence has a `From:` - so the
    taunt section is invisible to it and one file serves both.

    Args:
        doc: the parsed AMD document.

    Returns:
        int: how many taunt pools were found.
    """
    global _SCENES, _SUBJECTS, _REPLIES, _REPLY_SUBJECTS
    _SCENES, _SUBJECTS = _pools(doc, "detocs_taunts")
    _REPLIES, _REPLY_SUBJECTS = _pools(doc, "detocs_replies")
    detocs_reset()
    return len(_SCENES)


def _pools(doc, section_key):
    """One section -> (line pools, subject line per key)."""
    section = amd_section(doc, section_key)
    subjects = {}
    if section is not None:
        for n in section.get("children", []):
            key = n.get("key")
            if key:
                subjects[key] = n.get("display_text") or "DETOCS"
    return chatter_scenes(section), subjects


def _now():
    return int(FrameContext.sim_seconds or 0)


def _allowed(key):
    """Whether this taunt may be sent now.

    `destroyed` and `game_over` skip the cooldown - they are the best version of
    the joke and they only happen once anyway - but they still spend the cap and
    still fire only once each.
    """
    if _STATE["count"] >= CAP:
        return False
    if key in _STATE["fired"] and key in ONCE:
        return False
    if key in ONCE:
        return True
    last = _STATE["last"]
    return last is None or (_now() - last) >= COOLDOWN


def detocs_taunt(key, to="*", **fields):
    """Send one taunt for an event key, if the arbitration allows it.

    Args:
        key (str): a heading key from the `detocs_taunts` section.
        to (str): console, comma list, or `*`.
        **fields: `{placeholder}` values for the line (an unknown one is left
            literal, never a crash).

    Returns:
        bool: True when a message was actually sent.
    """
    if not _allowed(key):
        return False
    line = chatter_line(_SCENES, key, **fields)
    if not line:
        return False
    subject = chatter_line({"s": [_SUBJECTS.get(key, "DETOCS")]}, "s", **fields)
    message_mail(line, to=to, sender=SENDER, subject=subject)
    _STATE["last"] = _now()
    _STATE["fired"].add(key)
    _STATE["count"] += 1
    return True


def _shield_fraction(ship_id, facing):
    """How full one shield facing is, 0..1, or None when the ship has no shields.

    The third positional argument of `get_data_set_value` is the SLOT, not a
    default - front is 0, rear is 1 - and the engine answers `None` for a field
    that was never set where the mock answers a typed default. Hence `default=`.
    """
    mx = get_data_set_value(ship_id, "shield_max_val", facing, default=0) or 0
    if mx <= 0:
        return None
    val = get_data_set_value(ship_id, "shield_val", facing, default=0) or 0
    return val / mx


def detocs_taunt_damage(target_id):
    """`//damage/object` - taunt only when the hit actually meant something.

    This route fires continuously in a fight, so almost every call here is
    expected to do nothing. The cooldown does most of the work; the thresholds
    decide which of the two lines is the right one.
    """
    if target_id is None or not has_role(target_id, "__player__"):
        return False
    front = _shield_fraction(target_id, 0)
    rear = _shield_fraction(target_id, 1)
    if front is None and rear is None:
        return False
    worst = min(f for f in (front, rear) if f is not None)
    best = max(f for f in (front, rear) if f is not None)
    if best <= HULL_LOW_SHIELD:
        return detocs_taunt("hull_low")
    if worst <= SHIELD_DOWN:
        return detocs_taunt("shields_down")
    return False


def detocs_taunt_internal(ship_id, system):
    """`//damage/internal` - the damaged system's name is `EVENT.sub_tag`."""
    if ship_id is None or not has_role(ship_id, "__player__"):
        return False
    name = str(system or "").replace("_", " ").strip() or "ship"
    return detocs_taunt("system_damaged", system=name)


def detocs_reply(target, console=None, sender=None):
    """DETOCS writes back after a reply button.

    Driven by `//shared/signal/message_reply`, which is the only signal carrying
    who pressed the button. That fires for EVERY answered message in the mission,
    so an unrecognized target is a silent no-op and LM's own mail passes through
    untouched.

    Not rate limited and not capped: the crew asked for this one, and it goes
    back to the console that asked rather than to the whole ship.

    Args:
        target (str): the `(key)` on the reply line - a heading in the
            `detocs_replies` section.
        console (str, optional): who replied (`MESSAGE_CONSOLE`). Everyone when
            it is not known.
        sender (str, optional): who they were replying TO (`MESSAGE_FROM`), used
            only as a second guard.

    Returns:
        bool: True when a message was sent.
    """
    if sender and not str(sender).startswith("DETOCS"):
        return False
    line = chatter_line(_REPLIES, target)
    if not line:
        return False
    message_mail(line, to=console or "*", sender=SENDER,
                 subject=_REPLY_SUBJECTS.get(target, "DETOCS"))
    return True


def detocs_pool_count():
    """How many taunt pools loaded. A probe for tests and for the soak."""
    return len(_SCENES)


def detocs_taunt_count():
    """How many taunts have been sent this mission."""
    return _STATE["count"]
