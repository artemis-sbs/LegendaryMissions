"""ePADD glue for LegendaryMissions: the Messages badge, and the mail this ship carries.

Prefixed `lm_epadd_` because every top-level def in an addon becomes a MAST global in
one flat, mission-wide namespace, assigned unconditionally with last-loaded winning.

The mail itself is READ IN THE .mast, not here: `media_read_relative_file` resolves
against the addon the calling LABEL came from, and an addon ships as its own zip, so
there is no path from Python to the file. `__file__` is not defined here either -
Cosmos embeds the interpreter and a MAST-loaded module never gets one.
"""
from sbs_utils.procedural.messages import message_deliver_due, message_unread


def lm_epadd_unread():
    """The Messages tile's badge. Empty when there is nothing to read, so the tile
    stays quiet rather than saying '0 unread'."""
    n = message_unread()
    if not n:
        return ""
    return f"{n} new"


def lm_epadd_offers():
    """The Quests tile's badge: how many jobs are on offer that nobody has taken.

    Empty at zero, so the tile stays quiet rather than saying "0 available" - the same
    rule the Messages badge follows.

    Counts OFFERS, not quests: an accepted job is work in hand and does not belong in a
    number whose whole promise is "there is something here you have not done". POSTING
    jobs are excluded by offer_count for the same reason - they are listed so you know
    they exist, but something else has to hand them to you.
    """
    from sbs_utils.procedural.offer import offer_count_here
    n = offer_count_here()
    if not n:
        return ""
    return f"{n} available"


def lm_epadd_deliver_mail():
    """Send whatever is due. Called on a slow tick - mail that arrives while the crew
    is flying is the point; a pile that all landed at t=0 would be a document."""
    return message_deliver_due()


def lm_epadd_reporting():
    """The Status tile's own badge: how many apps have something to say.

    Deliberately does not count itself - a board that reports on its own existence
    is noise, and it would never read zero.
    """
    from sbs_utils.procedural.gui.status_gui import status_rows
    n = len([r for r in status_rows() if r.get("tab") != "status"])
    if not n:
        return ""
    return f"{n} reporting"


def lm_epadd_boarding():
    """The Boarding Party tile's badge: whether a party is forming, or where you are.

    Says nothing on a bridge console with no party open, so the tile stays quiet.
    """
    from sbs_utils.procedural.boarding import (boarding_invitation, boarding_open_roster,
                                           boarding_invite_title)
    from sbs_utils.procedural.gui.boarding_gui import boarding_who
    if boarding_who() is not None:
        return boarding_invite_title()
    if boarding_invitation() is None:
        return ""
    free = len(boarding_open_roster())
    if not free:
        return "full"
    return f"{free} place" if free == 1 else f"{free} places"
