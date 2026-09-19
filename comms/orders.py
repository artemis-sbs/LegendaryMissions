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
from sbs_utils.procedural.query import to_object, object_exists
from sbs_utils.procedural.orders import orders_available, orders_can_take, orders_items


#: A ship carrying this role never appears in the orders menu, whatever its side.
#:
#: A STORY SHIP IS NOT A UNIT. An ally with somewhere to be can be ordered somewhere else
#: by a crew who has no idea it matters - the Enterprise-C running for the rift in Gamma
#: with a Q is allied, orderable by the rule above, and the subject of the trial she would
#: be ordered out of. A mission marks those and they stay out.
NO_ORDERS_ROLE = "no_orders"

#: What an object with no order set of its own is offered: EVERY order, filtered by what
#: it can do (sbs_utils procedural/orders.py). A prefab narrows it by writing a longer
#: prefix into `give_orders_type`.
DEFAULT_ORDERS = "objective/orders/"

#: The one set there used to be. A ship still carrying it is widened to DEFAULT_ORDERS:
#: it was never a choice to be narrow, only the only list that existed.
_LEGACY_ORDERS = "objective/orders/defender"


def lm_can_take_orders(origin_id, selected_id):
    """Can `origin` give `selected` any order it can actually carry out?

    Who may be commanded is unchanged - the defender role, or an NPC on your side or an
    allied one, unless it is marked `no_orders`. What is NEW is the second half: it must
    also have at least one order its capabilities allow. A stock station has no engine and,
    engine-measured, no guns, so it is no longer "orderable" - which is what put stations
    in the comms Can order chip.
    """
    if selected_id is None:
        return False
    lm_orders_type(selected_id)            # widen a legacy order set before asking
    return orders_can_take(origin_id, selected_id)


def lm_orders_for(origin_id, selected_id, target_id=0, at_point=False):
    """The order labels for `selected` aimed at `target` - the ONE list the right-click
    popup and drag both build their buttons from. `target_id` 0 or `selected` itself asks
    for the orders it gives itself; `at_point` is an empty spot in space."""
    lm_orders_type(selected_id)
    target = target_id if target_id else None
    return orders_available(origin_id, selected_id, target, at_point=at_point)


def lm_order_items(origin_id, selected_id, target_id=0, at_point=False):
    """The menu entries for `selected` aimed at `target`: `[(label, instance, text)]` -
    one per order, or one per INSTANCE of an order that has them (a station's wings).
    What the right-click popup and drag build their buttons from."""
    lm_orders_type(selected_id)
    target = target_id if target_id else None
    return orders_items(origin_id, selected_id, target, at_point=at_point)


def lm_orders_type(selected_id):
    """The order-set prefix for `selected`: its own `give_orders_type`, or every order.

    Rewrites the legacy defender set on the ship, since the library reads the value
    directly and would otherwise narrow the ship to the four orders that set holds.
    """
    kind = get_inventory_value(selected_id, "give_orders_type", None)
    if kind and kind != _LEGACY_ORDERS:
        return kind
    if kind == _LEGACY_ORDERS:
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


# DRAG TO ORDER. Dragging a unit onto something on the comms console opens //comms/orders
# for that unit (see drag_orders.mast). Three objects take part - the ship giving the order,
# the unit being ordered, the thing the order is about - and comms only carries two, so the
# third is remembered here until the menu is built.
#
# Kept on the PLAYER SHIP, one per ship: two bridges dragging the same unit must not
# overwrite each other's target. Ids only - an object reference would outlive a delete.
_DRAG_ORDERS_KEY = "lm_drag_orders"


def lm_drag_orders_set(ship_id, source_id, target_id):
    """Remember that `ship` dragged `source` onto `target`."""
    set_inventory_value(ship_id, _DRAG_ORDERS_KEY, {"source": source_id, "target": target_id})


def lm_drag_orders_target(ship_id, source_id):
    """The pending drag target for `ship` ordering `source`, or 0.

    0 unless the record is for THIS unit and the ship, the unit and the target all still
    exist - a stale record must never produce an order.
    """
    record = get_inventory_value(ship_id, _DRAG_ORDERS_KEY, None)
    if not record or record.get("source") != source_id:
        return 0
    target_id = record.get("target", 0)
    if not target_id:
        return 0
    for an_id in (ship_id, source_id, target_id):
        if not object_exists(an_id):
            return 0
    return target_id


def lm_drag_orders_clear(ship_id):
    """Forget `ship`'s pending drag order."""
    set_inventory_value(ship_id, _DRAG_ORDERS_KEY, None)


# --- helpers the order labels (order_labels.mast) call ------------------------------

def lm_orders_designate(agent_id, target_id):
    """Point a unit's FIXED guns at a target: the turret itself, and every turret mount
    it carries. Returns how many guns took the designation - 0 means it has none, and a
    mobile ship is then steered by the order's brain instead. Pass target 0 to release."""
    from sbs_utils.procedural.orders import orders_mounted_turrets
    from sbs_utils.procedural.turret import turret_is, turret_designate
    guns = ([agent_id] if turret_is(agent_id) else []) + orders_mounted_turrets(agent_id)
    for g in guns:
        turret_designate(g, target_id or None)
    return len(guns)


def lm_orders_nearest_base(agent_id):
    """The nearest station on the unit's own side or an allied one, or None."""
    from sbs_utils.procedural.query import to_object_list
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.sides import side_are_allies, to_side_id
    me = to_object(agent_id)
    if me is None:
        return None
    my_side = to_side_id(agent_id, warn=False)
    best, best_d = None, None
    for st in to_object_list(role("station")):
        if st.id == agent_id:
            continue
        if to_side_id(st.id, warn=False) != my_side and not side_are_allies(agent_id, st.id):
            continue
        d = (st.pos - me.pos).length()
        if best_d is None or d < best_d:
            best, best_d = st.id, d
    return best


def lm_orders_retreat_point(agent_id, distance=8000, radius=10000):
    """A point `distance` away from the threats within `radius`, directly away from
    their centroid - or straight back along its own heading when none are near."""
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.sides import side_are_enemies
    from sbs_utils.procedural.query import to_object_list
    from sbs_utils.procedural.space_objects import broad_test_around
    from sbs_utils.vec import Vec3
    me = to_object(agent_id)
    if me is None:
        return None
    near = broad_test_around(agent_id, radius * 2, radius * 2, 0xf0) & (role("__npc__") | role("__player__"))
    foes = [o for o in to_object_list(near) if side_are_enemies(agent_id, o.id)]
    pos = me.pos
    if foes:
        cx = sum(o.pos.x for o in foes) / len(foes)
        cy = sum(o.pos.y for o in foes) / len(foes)
        cz = sum(o.pos.z for o in foes) / len(foes)
        away = pos - Vec3(cx, cy, cz)
    else:
        away = Vec3(0, 0, 0)
    if away.length() < 1:
        # Nothing to run from, or sitting on top of it: fall back to "back off".
        away = Vec3(0, 0, -1)
    return pos + away.unit() * distance


def lm_orders_repair_step(agent_id, fraction=0.02):
    """Recharge a docked unit's shields by `fraction` of their maximum. Returns True when
    every shield is full. Shields only: an NPC's hull has no repair path to drive."""
    so = to_object(agent_id)
    if so is None:
        return True
    blob = so.data_set
    count = blob.get("shield_count", 0) or 0
    full = True
    for i in range(count):
        mx = blob.get("shield_max_val", i) or 0
        cur = blob.get("shield_val", i) or 0
        if cur < mx:
            blob.set("shield_val", min(mx, cur + mx * fraction), i)
            full = False
    return full


def lm_orders_scan_report(agent_id, target_id):
    """Mark the target scanned for the unit's side, the way the comms Investigate order
    reports back. Returns the report line."""
    from sbs_utils.procedural.science import science_set_scan_data
    from sbs_utils.procedural.sides import side_get_display_name, to_side_id
    t = to_object(target_id)
    me = to_object(agent_id)
    if t is None or me is None:
        return ""
    side = getattr(t, "side", "") or ""
    side_name = side_get_display_name(side) or side or "unknown"
    text = f"{t.name}: {side_name}. Surveyed by {me.name}."
    science_set_scan_data(agent_id, target_id, {"scan": text})
    return text
