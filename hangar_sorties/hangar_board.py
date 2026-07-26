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
