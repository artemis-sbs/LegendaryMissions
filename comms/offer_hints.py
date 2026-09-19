"""Say on the comms panel that this contact has work.

The panel already tells the crew WHO they have selected. It has never told them whether
there is any point hailing them - so the only way to find out a station has three jobs
waiting is to hail every station and read the button list.

This appends a short count to the selection title. It is the cheapest possible surface:
no new screen, no new button, nothing to learn, and it appears on a panel the crew are
already looking at in the moment they are deciding whether to press Hail.

Prefixed `lm_` because every top-level def in an addon becomes a MAST global in one flat,
mission-wide namespace, assigned unconditionally with last-loaded winning.
"""
from sbs_utils.procedural.offer import offers_for_object


#: The engine PARSES a selection title as a style-property string, so these two
#: characters are read as syntax rather than drawn - the same rule hail_answer_label
#: documents for a row label.
_BANNED = (":", ";")

#: Past this, the suffix is dropped rather than the name. Knowing WHO you clicked on
#: always beats knowing how many jobs they have.
LM_OFFER_TITLE_MAX = 48


def lm_offer_hint_text(selected_id, origin_id=None):
    """The suffix for this contact, or "" - `2 jobs`, `1 job`.

    Counts only what can be TAKEN. A `pending` offer is listed on the board so the crew
    know it exists, but it is not a reason to hail anybody, so it must not inflate a
    number that exists to answer "is it worth pressing Hail".
    """
    rows = [r for r in offers_for_object(selected_id, client_id=origin_id)
            if not r.get("pending")]
    if not rows:
        return ""
    n = len(rows)
    return "1 quest" if n == 1 else f"{n} quests"


def lm_comms_offer_title(origin_id, selected_id, title):
    """The comms selection annotator. Installed from offers.mast.

    Never lengthens a title past LM_OFFER_TITLE_MAX, never emits a character the engine
    would parse, and returns the title untouched when there is nothing to say - which is
    the overwhelmingly common case, so a quiet contact reads exactly as it always has.
    """
    hint = lm_offer_hint_text(selected_id, origin_id)
    if not hint:
        return title
    out = f"{title} - {hint}"
    for ch in _BANNED:
        out = out.replace(ch, "")
    if len(out) > LM_OFFER_TITLE_MAX:
        return title            # the name wins; the board still has the detail
    return out
