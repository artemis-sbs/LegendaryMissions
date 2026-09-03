"""Who a bridge can give orders to.

It used to be one role - `prefab_npc_defender` - added in exactly two places: the defender
prefab and the enemy-surrender route. So a SURRENDERED ENEMY got the orders menu and a
genuine ally did not. A fleet ship, an allied-faction escort, anything not spawned by that
one prefab got nothing, whatever the diplomacy said. Reported from the Gamma with a Q
playtest as "Comms cannot give orders to allied NPCs. It should be able to."

`side_are_allies` was already being used INSIDE the popup to decide which orders to offer,
so widening the gate to allies is the gate finally agreeing with the contents.

Prefixed `lm_` because every top-level function here becomes a MAST global in one flat,
mission-wide namespace and the last one loaded wins, silently.
"""
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.roles import has_roles
from sbs_utils.procedural.sides import side_are_allies


#: A ship carrying this role never appears in the orders menu, whatever its side.
#:
#: A STORY SHIP IS NOT A UNIT. An ally with somewhere to be can be ordered somewhere else
#: by a crew who has no idea it matters - the Enterprise-C running for the rift in Gamma
#: with a Q is allied, orderable by the rule above, and the subject of the trial she would
#: be ordered out of. A mission marks those and they stay out.
NO_ORDERS_ROLE = "no_orders"

#: What an ally with no orders of its own is offered. The defender set is already written,
#: already filtered by `valid_for` into allies / hostile / self, and is what every prefab
#: that CAN take orders already uses - a second list would be a second thing to maintain
#: for no gain.
DEFAULT_ORDERS = "objective/orders/defender"


def lm_can_take_orders(origin_id, selected_id):
    """Can `origin` give orders to `selected`?

    True for the historic defender role, and now also for any NPC the origin's side is
    allied with - unless the mission has marked it `no_orders`.
    """
    if selected_id is None:
        return False
    if has_roles(selected_id, NO_ORDERS_ROLE):
        return False
    if has_roles(selected_id, "prefab_npc_defender"):
        return True
    if not has_roles(selected_id, "__npc__"):
        return False
    try:
        return bool(side_are_allies(origin_id, selected_id))
    except Exception:                                   # noqa: BLE001
        return False


def lm_orders_type(selected_id):
    """The order list to build the menu from.

    THE GATE WAS NEVER THE ONLY BLOCKER. The menu is built from a per-ship
    `give_orders_type`, set by the prefabs - so widening the gate alone would have opened
    an EMPTY menu on every ally, which is a worse answer than no menu at all. An ally
    without one gets the defender set.
    """
    kind = get_inventory_value(selected_id, "give_orders_type", None)
    if kind:
        return kind
    # Remembered on the ship, so the popup and the carry-out path agree and the lookup
    # happens once rather than on every right-click.
    set_inventory_value(selected_id, "give_orders_type", DEFAULT_ORDERS)
    return DEFAULT_ORDERS


def lm_orders_block(obj):
    """Mark a ship as not orderable. For a mission with a story ship to protect."""
    from sbs_utils.procedural.roles import add_role
    target = to_object(obj)
    if target is None:
        return False
    add_role(target, NO_ORDERS_ROLE)
    return True
