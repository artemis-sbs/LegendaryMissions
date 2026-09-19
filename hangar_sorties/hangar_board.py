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


# --- Sorties are ordinary quests ----------------------------------------------------
#
# A sortie is a quest for a pilot. It used to be a separate kind of thing - not a quest
# until taken, published through its own offer provider with its own "take" - which gave
# players a second name and a second path for the same idea. Now the moment a pilot picks
# a craft, that craft's sorties are granted to the PILOT as untaken quests, exactly like a
# mission's job board: they appear under Available Quests, are accepted there, and then
# sit on the Quests tab.
#
# The pilot (the CLIENT) holds them, not the craft: `quest_tab_items` reads the shared
# agent, the client and the console's ship, and on the flight deck the console is
# assigned to the dock, not the fighter - a quest on the craft would be shown by nothing.


def hangar_sortie_keys(doc):
    """Every sortie key in the doc, whatever craft it is for."""
    if doc is None:
        return []
    return [n.get("key") for n in doc.get("children", []) if n.get("key")]


def hangar_offer_sorties(client_id, craft):
    """Put `craft`'s sortie orders on this pilot's list as untaken quests.

    Called whenever the pilot picks a craft. A shuttle and a fighter are handed different
    work, so an UNTAKEN order for the other kind of craft is withdrawn; an order already
    accepted (or finished) is the pilot's and is never touched. Idempotent: an order
    already on the list is left as it is.
    """
    from sbs_utils.procedural.execution import get_shared_variable
    from sbs_utils.procedural.quest import quest_get, quest_get_state, quest_remove, QuestState
    from sbs_utils.procedural.quest_driver import quest_grant_amd
    doc = get_shared_variable("HANGAR_QUEST_DOC", None)
    if doc is None or client_id is None or craft is None:
        return 0
    wanted = hangar_quests_for(doc, hangar_cockpit_type(craft))
    wanted_keys = {n.get("key") for n in wanted}
    for key in hangar_sortie_keys(doc):
        if key in wanted_keys:
            continue
        if quest_get(client_id, key) is not None and \
                int(quest_get_state(client_id, key) or 0) == int(QuestState.IDLE):
            quest_remove(client_id, key)
    quest_grant_amd(client_id, {"children": wanted})
    return len(wanted)
