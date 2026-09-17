"""What Science reads on a contact that has work for you.

Comms can say "DS 1 - 2 jobs" on the selection title, but only once the crew have already
picked that contact on the COMMS console. Science is where a bridge finds out what is out
there in the first place, so a contact with open work should say so on a scan.

One line, on the INTEL tab:

    Open work at last scan - 2 jobs. Hail to take.

**A tab is a STORED string, not a live render.** `science_update_scan_data` writes it and
nothing re-runs it - re-selecting a contact does not rebuild the tab. That is why the
wording says *at last scan* rather than a bare count: a scan taken before a job appeared
is genuinely out of date, and the line says so instead of quietly lying. The Offers board
and the comms title are the current surfaces; this is the pointer that sends a crew to
them. Same constraint, and the same push, that `science_status.py` documents.

Only contacts a science officer has ALREADY scanned are touched, so the walk is over a
handful of objects rather than the whole sim.

Prefixed `lm_` because every top-level def in an addon becomes a MAST global in one flat,
mission-wide namespace.
"""
from sbs_utils.procedural.offer import offers_for_object
from sbs_utils.procedural.query import object_exists, to_id, to_id_list
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.science import (science_has_scan_data,
                                          science_update_scan_data)

#: The tab this writes. NOT "scan": that one is always present and carries the object's
#: own description, so a mission's prose would be displaced. "intel" is already the
#: conditionally-populated tab, which is exactly what this is.
LM_OFFER_SCAN_TAB = "intel"


def lm_science_offer_line(target_id, origin_id=None):
    """The line for this contact, or "" when it has no untaken work.

    Counts only what can be TAKEN - a `pending` offer is listed on the board so the crew
    know it exists, but it is not a reason to fly over and hail somebody.
    """
    rows = [r for r in offers_for_object(target_id, client_id=origin_id)
            if not r.get("pending")]
    if not rows:
        return ""
    n = len(rows)
    what = "1 job" if n == 1 else f"{n} jobs"
    return f"Open work at last scan - {what}. Hail to take."


def lm_science_offers_push(origin_id, target_id):
    """Write the line onto one already-scanned contact. Returns True if it wrote."""
    if not object_exists(target_id):
        return False
    if not science_has_scan_data(origin_id, target_id):
        return False                # not scanned yet; the scan itself will carry it
    line = lm_science_offer_line(target_id, origin_id)
    if not line:
        return False
    science_update_scan_data(origin_id, target_id, line, tab=LM_OFFER_SCAN_TAB)
    return True


def lm_science_offers_tick():
    """Refresh the line on contacts this side has already scanned.

    Walks the scanned contacts, not the sim: a science tab the crew have never opened
    does not need keeping true, and a full walk would cost a great deal for nothing.
    Returns how many lines were written.
    """
    wrote = 0
    for origin_id in to_id_list(role("__player__")):
        for target_id in to_id_list(role("station")):
            if lm_science_offers_push(origin_id, target_id):
                wrote += 1
    return wrote
