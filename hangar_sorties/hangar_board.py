"""Hangar sortie board: pick and assign a quest to a launched cockpit from the
parsed AMD sortie doc.

The generic quest ENGINE (trigger advancement, rewards, state writers, AMD
granting, Quests-tab gating) lives in sbs_utils
(``sbs_utils.procedural.quest_driver``) and is exposed to MAST as globals from
there. This ``hangar_sorties`` addon only supplies the sortie-board helpers and
content (``hangar_quests.amd``); the hangar's guarded board panel
(``hangar/hangar.mast``) reads them via the shared ``HANGAR_QUEST_DOC``. Like the
casino addon, loading this mastlib is optional — the hangar runs without it.
"""
from sbs_utils.procedural.quest import quest_add
from sbs_utils.procedural.quest_driver import quest_mark_active
from sbs_utils.procedural.roles import has_role
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.gui import gui_row, gui_text
from sbs_utils.mast.mast_node import MastDataObject


# --- Hangar quest board ------------------------------------------------------
def hangar_quests_for(doc, cockpit_type):
    """Quest nodes from the parsed AMD doc whose cockpit matches (or 'any').

    AMD nodes are plain dicts with list "children" and a "key" id; the
    "--- yaml ---" section is parsed into "data".
    """
    if doc is None:
        return []
    out = []
    for n in doc.get("children", []):
        ck = (n.get("data") or {}).get("cockpit", "any")
        if ck == cockpit_type or ck == "any":
            out.append(n)
    return out


def hangar_assign_quest(cockpit_id, doc, cockpit_type, quest_id):
    """Add+activate the chosen sortie quest on the cockpit. Returns the node."""
    for n in hangar_quests_for(doc, cockpit_type):
        if n.get("key") == quest_id:
            quest_add(cockpit_id, n.get("key"), n.get("display_text"),
                      n.get("description", ""), data=n.get("data"))
            quest_mark_active(cockpit_id, n.get("key"))
            return n
    return None


def hangar_cockpit_type(ride):
    """Cockpit class for board filtering: 'shuttle' if the craft has that role,
    else 'fighter'. None ride -> 'fighter'."""
    rid = to_id(ride)
    if rid is not None and has_role(rid, "shuttle"):
        return "shuttle"
    return "fighter"


def hangar_quest_items(doc, cockpit_type):
    """Selectable list-box items (MastDataObject) for the cockpit's sorties."""
    items = []
    for n in hangar_quests_for(doc, cockpit_type):
        items.append(MastDataObject({
            "key": n.get("key"),
            "title": n.get("display_text"),
            "objective": (n.get("data") or {}).get("objective", ""),
            "desc": (n.get("description") or "").strip(),
        }))
    return items


def hangar_quest_template(item):
    """List-box row renderer for a sortie quest."""
    gui_row("row-height: 1.2em;padding:13px;")
    gui_text(f"$text:{item.title};justify: left;")
    obj = item.get("objective", "")
    if obj:
        gui_row("row-height: 1.1em;padding:13px;")
        gui_text(f"$text:{obj};justify: left;font:gui-1")


def hangar_quest_title_template():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text("$text:Sortie Orders;justify: left;")


# --- The sortie board, as OFFERS --------------------------------------------
#
# The board used to be a panel on the flight deck, which made a sortie the one kind of
# work you could only see from one screen - and only after walking to it. It is an OFFER
# like any other now: something the world has for you that you have not taken. That puts
# it in the PADD, where it is reachable from any console and from the cockpit, and gives
# the flight deck back the lower third of its screen.
#
# The board is still the authority on WHICH sorties suit a craft; this only publishes it.

#: The role a console carries while it is flying a craft, and the key the hangar stores
#: the craft on. Both already exist - this reads them rather than inventing state.
HANGAR_CRAFT_LINK = "craft_id"


#: Where the flight deck leaves the craft the pilot has SELECTED but not yet launched.
#: The screen holds that in a MAST task variable (`ride_choice_id`), which no Python can
#: read - so the deck publishes it here for anything that needs it.
HANGAR_RIDE_KEY = "hangar_ride_id"


def hangar_offer_craft(client_id):
    """The craft this console is flying, or about to fly. None when it is neither.

    TWO SOURCES, and missing the second one is why the Offers tile never appeared on the
    flight deck. In the COCKPIT the craft is a dedicated link, set at launch. On the DECK
    nothing is launched yet - the pilot has only picked a row - and that selection lives
    in the screen's own task scope where no provider can see it, so the deck publishes it
    to inventory and this reads it.

    Without the deck half, the one console where a sortie is chosen offered none: no
    craft, so no sorties, so `offer_count_here()` is zero and the route's own condition
    hides the whole app.
    """
    from sbs_utils.procedural.inventory import get_inventory_value
    from sbs_utils.procedural.links import get_dedicated_link
    try:
        flying = to_id(get_dedicated_link(client_id, HANGAR_CRAFT_LINK))
    except Exception:                                    # noqa: BLE001
        flying = None
    if flying:
        return flying
    try:
        return to_id(get_inventory_value(client_id, HANGAR_RIDE_KEY, None)) or None
    except Exception:                                    # noqa: BLE001
        return None


def hangar_offer_provider(ctx):
    """The `hangar` offer provider: this craft's sortie orders, as offer records.

    Registered from hangar_board.mast. Quiet when the sortie addon's doc never loaded,
    which is the ordinary state of a mission that does not use sorties at all.
    """
    from sbs_utils.procedural.execution import get_shared_variable
    from sbs_utils.procedural.offer import offer_record
    from sbs_utils.procedural.quest import quest_get_state

    # A per-OBJECT question has no sortie answer: an order is held by a cockpit, not by
    # the thing you clicked on.
    if ctx.get("object_id") is not None:
        return []
    doc = get_shared_variable("HANGAR_QUEST_DOC", None)
    if doc is None:
        return []
    cid = ctx.get("client_id")
    craft = hangar_offer_craft(cid)
    if not craft:
        return []
    kind = hangar_cockpit_type(craft)
    out = []
    for item in hangar_quest_items(doc, kind):
        key = item.get("key")
        # Already flying it is not an offer.
        if quest_get_state(craft, key) != 0:
            continue
        out.append(offer_record(
            key="sortie:%s:%s" % (craft, key),
            title=str(item.get("title") or key),
            detail=str(item.get("objective") or ""),
            kind="sortie",
            source="Flight Hangar",
            where="Hangar - pick a craft first",
            # NO `app="quest"`. That is where a quest is accepted, and a sortie is not a
            # quest until it is ASSIGNED - so sending a pilot there to take one showed
            # them a list that could not contain the thing they had just clicked. It is
            # taken HERE instead.
            take=hangar_take_sortie,
            sort=15,
            data={"sortie": key, "craft": craft, "cockpit": kind},
        ))
    return out


def hangar_take_sortie(client_id, record):
    """Take a sortie order: assign it to the craft the offer was built for.

    This is what the board's old selection did at LAUNCH, moved to the moment the pilot
    actually chooses - which is both earlier and clearer, and it means the order is a
    real quest on the craft from then on. So it leaves the Offers list (the provider
    skips anything already active), appears in the Quests app like every other job, and
    the launch needs to carry nothing.
    """
    from sbs_utils.procedural.execution import get_shared_variable
    data = (record or {}).get("data") or {}
    craft = data.get("craft")
    sortie = data.get("sortie")
    doc = get_shared_variable("HANGAR_QUEST_DOC", None)
    if not craft or not sortie or doc is None:
        return False
    node = hangar_assign_quest(craft, doc, data.get("cockpit"), sortie)
    return node is not None


def hangar_offers_register():
    """Install the provider. Called once from hangar_board.mast."""
    from sbs_utils.procedural.offer import offer_register
    offer_register("hangar", hangar_offer_provider, domain="hangar")
    return True
