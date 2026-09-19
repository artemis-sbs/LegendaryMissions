"""One quiet line when the work on offer CHANGES.

The badge and Available Quests are pull surfaces: they answer a question the crew thought
to ask. This is the one push, and it is deliberately the smallest push available - a line
filed in the log and shown in the ambient strip, on the consoles that can actually accept
a job. It never raises a panel, never speaks, never takes the screen.

Three rules keep it from becoming the noise it exists to replace:

* **Only on CHANGE.** A digest that repeats the same number every few minutes is exactly
  the spam this whole feature is trying to remove. The key set is diffed, so a quiet
  system says nothing, forever.
* **It yields to a voice.** If anything has spoken unprompted in the last few seconds,
  the digest waits - a line arriving underneath a character talking is a line nobody
  reads. It does NOT stamp that clock itself: a filed log line never took the screen, so
  it has no claim on the speech budget and must not starve an urge of its turn.
* **Only who can act.** QUEST_ACCEPT_CONSOLES already knows who may accept a job. The
  people who cannot do not need telling what is acceptable.

Per-client memory lives in CLIENT INVENTORY, not a module dict, so it is dropped with
Agent.clear() on a mission reset and cannot leak into the next run.

Prefixed `lm_` because every top-level def in an addon becomes a MAST global in one flat,
mission-wide namespace.
"""
from sbs_utils.procedural.execution import get_shared_variable
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.offer import offers
from sbs_utils.procedural.announce import announce_last_traffic
from sbs_utils.procedural.urge import URGE_GLOBAL_FLOOR
from sbs_utils.procedural.gui.log_panel_gui import log_notify_all
from sbs_utils.procedural.log_panel import TAB_MISSION
from sbs_utils.helpers import FrameContext


#: Inventory keys on the CLIENT: what it was last told, and when.
_KEY_SEEN = "__offer_digest_seen__"
_KEY_WHEN = "__offer_digest_when__"

#: A console is not told twice inside this, even if the set keeps moving.
LM_OFFER_DIGEST_FLOOR = 180


def _kinds_phrase(rows):
    """`2 quests` - one word for everything a crew can take on. The kinds (job, sortie,
    contact) are an author's vocabulary; a player sees quests."""
    n = len(rows)
    return "1 quest" if n == 1 else f"{n} quests"


def lm_offer_digest_text(rows, fresh):
    """The line. ASCII, one sentence, and it names what is NEW when anything is.

    `fresh` are the offers this console has not been told about yet.
    """
    head = f"Quests available - {_kinds_phrase(rows)}."
    names = [str(r.get("title")) for r in fresh][:2]
    if names:
        head += " New: " + ", ".join(names) + "."
    return head + " See Available Quests."


def _ship_of(cid):
    """The console's HOME ship - not get_ship_of_client, which answers with the SUBJECT
    of a cinematic on a main screen, so a digest would count the enemy's jobs. The same
    rule the log panel's own scope follows."""
    try:
        from sbs_utils.procedural.gui.viewscreen import viewscreen_home_ship
        return viewscreen_home_ship(cid) or None
    except Exception:
        return None


def lm_offer_digest_due(client_id, now=None):
    """Whether this console is owed a digest, and what to say.

    Returns ``(text, keys)`` or ``(None, None)``. Pure apart from reading the clock, so
    the decision is testable without a tick.
    """
    if not get_shared_variable("OFFER_DIGEST_ENABLED", True):
        return (None, None)
    cid = client_id if client_id is not None else FrameContext.client_id
    ship = _ship_of(cid)
    rows = [r for r in offers(client_id=cid, ship_id=ship) if not r.get("pending")]
    keys = sorted(str(r.get("key")) for r in rows)
    seen = list(get_inventory_value(cid, _KEY_SEEN, None) or [])

    if keys == seen:
        return (None, None)                 # nothing moved; say nothing
    if not keys:
        # The board emptied. Worth REMEMBERING (so the next job counts as new) but not
        # worth a line - "there is no work" is not news anybody needs interrupting for.
        set_inventory_value(cid, _KEY_SEEN, keys)
        return (None, None)

    now = FrameContext.sim_seconds if now is None else now
    last = get_inventory_value(cid, _KEY_WHEN, None)
    if last is not None and (now - last) < LM_OFFER_DIGEST_FLOOR:
        return (None, None)                 # too soon; the set is remembered next time

    # Yield to anything speaking. Deliberately does NOT stamp the traffic clock: this
    # took no screen, so it owes the speech budget nothing.
    spoke = announce_last_traffic()
    if spoke is not None and (now - spoke) < URGE_GLOBAL_FLOOR:
        return (None, None)

    fresh = [r for r in rows if str(r.get("key")) not in seen]
    return (lm_offer_digest_text(rows, fresh), keys)


def lm_offer_digest_send(client_id=None, now=None):
    """Work out whether to speak, and file the line if so. Returns the text, or None."""
    cid = client_id if client_id is not None else FrameContext.client_id
    text, keys = lm_offer_digest_due(cid, now)
    if text is None:
        return None
    set_inventory_value(cid, _KEY_SEEN, keys)
    set_inventory_value(cid, _KEY_WHEN,
                        FrameContext.sim_seconds if now is None else now)
    # Client-scoped, not ship-scoped: gui_log_tail unions [ship_of(cid), cid], so a
    # client id reaches exactly one console. (The hail echo is ship-scoped for the
    # opposite reason - a hail is addressed to the ship, not to whoever pressed answer.)
    log_notify_all([cid], text, category=TAB_MISSION, severity="")
    return text


def lm_offer_digest_consoles():
    """Which console types are owed a digest - whoever may accept a job."""
    spec = get_shared_variable("OFFER_DIGEST_CONSOLES", None)
    if spec in (None, ""):
        spec = get_shared_variable("QUEST_ACCEPT_CONSOLES", "comms,admiral")
    return str(spec)


def lm_offer_digest_tick():
    """One pass: tell every console that can accept a job and is owed a line.

    Returns how many were told, so a caller (or a test) can see it did something.
    """
    from sbs_utils.procedural.roles import any_role
    from sbs_utils.procedural.query import to_id_list
    told = 0
    # Each console asks its OWN question - its ship, its memory - so the client id is
    # passed explicitly rather than leaned on from the frame context, which during a
    # background pump belongs to whatever ticked last.
    for cid in to_id_list(any_role(lm_offer_digest_consoles())):
        if lm_offer_digest_send(cid) is not None:
            told += 1
    return told
