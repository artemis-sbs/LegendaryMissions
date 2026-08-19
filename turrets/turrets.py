"""Deployable defense turrets - hull registration and the one way to place one.

`lm_turret_deploy_tower` is deliberately PYTHON rather than a MAST label. Every route to a
turret (mission prefab, player deploy, GM console) needs the new turret's id back, and a
MAST label's `yield result` is only readable by the specific callers built to await it -
a plain function hands the id to all of them and cannot drift into three variants.

Every function here is prefixed `lm_turret_` - addon functions land in one flat,
mission-wide MAST namespace where the last loaded wins silently, so an unprefixed
`declare_ships` would be a collision waiting to happen (`sbs lint` ns-duplicate-function).
"""

import os

from sbs_utils.procedural.brain import brain_add
from sbs_utils.procedural.execution import log
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.prefab import prefab_autoname
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.roles import remove_role
from sbs_utils.procedural.ship_data import add_extra
from sbs_utils.procedural.signal import signal_emit
from sbs_utils.procedural.timers import set_timer
from sbs_utils.procedural.space_objects import clear_target
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.procedural.mount import mount_ring
from sbs_utils.procedural.turret import turret_make

#: Hull every tower uses unless told otherwise. MUST be one of ours - engine-measured, a
#: behav_station on a STOCK hull never fires (see extraShipData_turrets.yaml).
LM_TURRET_DEFAULT_HULL = "lm_turret_beam"

#: Brain label a deployed tower runs.
LM_TURRET_BRAIN = "lm_turret_engage"

#: Hull used for turrets bolted onto a ship or station.
LM_TURRET_MOUNT_HULL = "lm_turret_mount"

#: Default behavior for a tower. behav_station never steers, so it holds position for
#: free - but it also NEVER launches drones (engine-measured), which is why a drone tower
#: overrides this with behav_npcship.
LM_TURRET_BEHAVE = "behav_station"

#: Hull for an undeployed kit crate.
LM_TURRET_CRATE_HULL = "lm_turret_crate"

#: Most live TOWERS one side may have at once. Mounts on a ship do not count - they are
#: limited by the ship carrying them, and a fleet action would otherwise eat the cap.
LM_TURRET_CAP = 8

#: Seconds a deployed tower lasts before it powers down and is removed. Deployables that
#: never expire turn every map into a minefield of somebody's old hardware.
LM_TURRET_LIFETIME = 1200

#: Shots a tower has before it goes dormant. Engine-measured: //damage/object carries
#: DAMAGE_ORIGIN_ID for beam damage, so upkeep can be charged PER SHOT rather than by a
#: timer that punishes a turret nothing ever flew past.
LM_TURRET_CHARGE = 60


#: Mod tag the turret entries carry, so a hand-authored mission entry always wins
#: a key collision.
LM_TURRET_MOD = "LegendaryMissions"

#: Logical media path of the turret hulls, WITHOUT its extension - the engine tries
#: `.yaml` then `.json` itself. It rides the LM media pack rather than the turrets
#: mastlib because a mastlib is a ZIP and the engine cannot read inside one; a media
#: pack is unpacked to disk once, under `__lib__/media/<pack>/`, which is a real
#: folder the engine can be pointed at.
LM_TURRET_SHIP_FILE = "turrets/extraShipData_turrets"


def lm_turret_declare_ships():
    """Declare the turret hulls so the engine knows them. Call at story TOP LEVEL.

    The addon used to read this file out of its own mastlib and hand the TEXT to the
    library, which then wrote every merged entry into the mission's shared
    `extraShipData.json` just before `create_new_sim()`. That worked, and cost a
    generated file in everyone's mission folder that the library also read back -
    the same hulls arriving twice, 51 becoming 102 from the second run on.

    Now the file simply EXISTS, in the media pack, named for the addon that owns it,
    and both readers are pointed at it: `add_extra` merges it into
    sbs_utils (so headless, the mock and `get_ship_data_for` all still see the hulls)
    and registers it with the engine (which is what makes a `behav_station` actually
    fire - engine-measured, LM_TestRange test_turret_probe).

    Returns:
        True when the engine was told, False when only the library was - which is
        also what a missing file degrades to. Never raises: no turrets is a worse
        mission, a dead mission is a worse outcome.
    """
    reached = add_extra(LM_TURRET_SHIP_FILE, mod=LM_TURRET_MOD)
    if not reached:
        log("turret hulls not registered with the engine - if the file is missing "
            "from the media pack, turrets will not fire", "turrets", "warning")
    return reached


def lm_turret_deploy_tower(x, y, z, side="tsn", hull=None, acquire_range=2500, targets=None,
                           name="Turret #", owner=0, behave=None):
    """Place a live, autonomous defense turret and return its id.

    The single entry point every deployment path goes through - mission prefab, player
    tow-and-release, GM map click. Callers that are player-triggered must reach it from a
    `//shared/signal` route (server, once), never `//signal`, which runs once PER
    CONNECTED CONSOLE and would place one turret per bridge crew member.

    Args:
        x, y, z (float): Where to put it.
        side (str): Side key. Also decides who it shoots, via diplomacy.
        hull (str, optional): shipData key. Defaults to
            :data:`LM_TURRET_DEFAULT_HULL`. Must be an entry from
            extraShipData_turrets.yaml or the turret will never fire.
        acquire_range (float): Acquisition range. Keep in step with the hull's beam range -
            beam stats are not readable from a live object, so nothing can check this
            for you.
        targets (str, optional): Role expression of what to engage. Defaults to the
            library default (ships, fighters, stations, players).
        name (str): Display name; a `#` is auto-numbered.
        owner (int): Optional id of whoever deployed it, for caps and scoring.
        behave (str, optional): Engine behavior. Defaults to
            :data:`LM_TURRET_BEHAVE` (``behav_station``), which holds position for
            free. Pass ``behav_npcship`` for a DRONE tower - engine-measured, a
            ``behav_station`` never launches drones no matter what its hull says.

    Returns:
        int | None: The turret's id, or None if the spawn failed.
    """
    behave = behave or LM_TURRET_BEHAVE
    side = side or "tsn"
    obj = npc_spawn(x, y, z, prefab_autoname(name), side + ",turret",
                    hull or LM_TURRET_DEFAULT_HULL, behave)
    tid = to_id(obj)
    if tid is None:
        log("turret deploy failed: npc_spawn returned nothing for hull "
            + str(hull or LM_TURRET_DEFAULT_HULL), "turrets", "warning")
        return None

    # The art's own roles are applied at spawn. Strip `station` if a hull ever grows it:
    # a turret that reads as a station inherits LM docking, market, repair, nav proxies
    # and every "protect the station" objective in the game.
    remove_role(tid, "station")

    turret_make(tid, range=acquire_range, targets=targets)
    # ALWAYS written, even when 0. A reader asking "who owns this?" must get an answer
    # rather than a missing key it has to guess the meaning of, and 0 is a real answer:
    # mission hardware, owned by nobody.
    owner_id = to_id(owner) or 0
    set_inventory_value(tid, "turret:owner", owner_id)

    # The two balance levers every deployed tower carries. A tower with neither is a
    # permanent free gun, and the map fills up with them.
    set_inventory_value(tid, "turret:charge", LM_TURRET_CHARGE)
    set_timer(tid, "turret_life", seconds=LM_TURRET_LIFETIME)

    # Start cold - no weapons lock, no throttle, no destination. The brain acquires on
    # its first pass; until then the turret must not be holding a stale target id.
    # clear_target also pins target_pos to the turret's own position, which is exactly
    # what an emplacement wants.
    clear_target(tid)

    # A behav_npcship HAS a helm, so an emplacement on it must be nailed down: throttle 0
    # and a destination that is where it already is. Measured at 0.0u drift over 90s.
    # The bulwark pattern - belt and braces, so nothing that later writes a throttle can
    # send a "tower" flying across the map after its target.
    if behave != "behav_station":
        so = to_object(tid)
        if so is not None:
            so.data_set.set("throttle", 0, 0)
            so.data_set.set("target_pos_x", x, 0)
            so.data_set.set("target_pos_y", y, 0)
            so.data_set.set("target_pos_z", z, 0)
    brain_add(tid, LM_TURRET_BRAIN)
    # A DICT, and this is not style. Signal data keys become task variables in the
    # handling route, and MastAsyncTask.start_task merges them with `dict | inputs` - so a
    # bare int raises TypeError inside THIS function the moment anyone writes
    # //signal/lm_turret_deployed. It was silent only while nothing listened.
    signal_emit("lm_turret_deployed", {"TURRET_ID": tid, "TURRET_SIDE": side,
                                       "TURRET_OWNER_ID": owner_id})
    return tid


def lm_turret_bolt_ring(host, count=4, hull=None, acquire_range=1200, targets=None,
                        radius=None, delete_with_host=True):
    """Bolt a ring of autonomous turrets onto a ship or a station.

    The SAME call for both, because the offsets are body-frame and the engine's tractor
    holds them there: a station host and a hard-maneuvering ship behave identically, and
    neither needs a per-tick reposition.

    Args:
        host (Agent | int): Ship or station to fit.
        count (int): How many turrets, evenly spaced around the hull.
        hull (str, optional): shipData key. Defaults to
            :data:`LM_TURRET_MOUNT_HULL`. Must be one of ours or it will never fire.
        acquire_range (float): Acquisition range; keep in step with the hull's beam range.
        targets (str, optional): Role expression of what to engage.
        radius (float, optional): Ring radius. Defaults to just outside the host's
            exclusion radius.
        delete_with_host (bool): Destroy the turrets with the host (default), or leave
            them as salvageable debris.

    Returns:
        list[int]: The turret ids fitted.
    """
    hid = to_id(host)
    if hid is None:
        return []
    side = getattr(to_object(hid), "side", None) or "tsn"
    ids = mount_ring(hid, hull or LM_TURRET_MOUNT_HULL, count, radius=radius,
                     name="", side=side + ",turret",
                     delete_with_host=delete_with_host)
    for tid in ids:
        # A mount must not inherit `station` from its art, same as a tower.
        remove_role(tid, "station")
        turret_make(tid, range=acquire_range, targets=targets)
        clear_target(tid)
        brain_add(tid, LM_TURRET_BRAIN)
    if ids:
        signal_emit("lm_turret_bolted", {"TURRET_HOST_ID": hid, "TURRET_IDS": ids,
                                         "TURRET_SIDE": side})
    return ids


def lm_turret_is_tower(id_or_obj):
    """A deployed TOWER - a turret that is not bolted to a host."""
    from sbs_utils.procedural.mount import mount_is
    from sbs_utils.procedural.turret import turret_is
    tid = to_id(id_or_obj)
    return bool(tid and turret_is(tid) and not mount_is(tid))


def lm_turret_side_count(side):
    """How many live towers a side has deployed."""
    from sbs_utils.procedural.turret import turret_all
    key = side if isinstance(side, str) else getattr(to_object(side), "side", None)
    n = 0
    for tid in turret_all():
        if not lm_turret_is_tower(tid):
            continue
        if getattr(to_object(tid), "side", None) == key:
            n += 1
    return n


def lm_turret_cap():
    """The per-side tower cap. A mission can raise or lower it with a shared."""
    from sbs_utils.procedural.execution import get_shared_variable
    v = get_shared_variable("LM_TURRET_CAP")
    return int(v) if v else LM_TURRET_CAP


def lm_turret_at_cap(side):
    """Whether a side may deploy no more towers."""
    return lm_turret_side_count(side) >= lm_turret_cap()


def lm_turret_spawn_crate(x, y, z, side, prefab, name=None, owner=0):
    """Place an undeployed turret kit at a POINT.

    The kit is a real OBJECT rather than an inventory row on purpose: deploying is then a
    crew job - tow it where you want it with the grav tether and unfold it - not a button
    press. The crate remembers which prefab it becomes, so adding a tower kind needs a new
    prefab and a new item and no code here.

    The positional half of the pair. :func:`lm_turret_eject_crate` knows only "400u off
    the bow", which is the ITEM's gesture; a mission handing out kits wants them where it
    says. Both produce the same crate - same roles, same prefab key, same owner - so the
    tow popup and the deploy route cannot tell them apart.

    Args:
        owner (int): Who the kit belongs to, for scoring. 0 = mission hardware.

    Returns:
        int | None: The crate's id.
    """
    crate = npc_spawn(x, y, z, name or "Turret Kit", (side or "tsn") + ",turret_crate",
                      LM_TURRET_CRATE_HULL, "behav_station")
    cid = to_id(crate)
    if cid is None:
        return None
    remove_role(cid, "station")
    set_inventory_value(cid, "turret_prefab", str(prefab))
    # `turret:owner` - the SAME key the deployed tower uses, and the namespace
    # turret_config already owns. The crate used to write `turret_owner`, so the owner a
    # player earned by ejecting a kit was never the owner the resulting tower carried.
    set_inventory_value(cid, "turret:owner", to_id(owner) or 0)
    clear_target(cid)
    signal_emit("lm_turret_kit_ejected", {"CRATE_ID": cid, "TURRET_SIDE": side or "tsn",
                                          "TURRET_OWNER_ID": to_id(owner) or 0})
    return cid


def lm_turret_eject_crate(ship, prefab, name=None):
    """Eject an undeployed turret kit ahead of a ship - the item's gesture.

    Returns:
        int | None: The crate's id.
    """
    sid = to_id(ship)
    so = to_object(sid) if sid else None
    if so is None:
        return None
    try:
        eo = so.engine_object
        p, f = eo.pos, eo.forward_vector()
        x, y, z = p.x + f.x * 400, p.y + f.y * 400, p.z + f.z * 400
    except Exception:
        return None
    side = getattr(so, "side", None) or "tsn"
    return lm_turret_spawn_crate(x, y, z, side, prefab, name, sid)


def lm_turret_crate_prefab(crate):
    """Which tower prefab a crate unfolds into."""
    cid = to_id(crate)
    return None if cid is None else get_inventory_value(cid, "turret_prefab", None)


def lm_turret_owner(id_or_obj):
    """Who owns this crate or tower. 0 = nobody / mission hardware.

    ONE key for one concept. The crate wrote `turret_owner` and the tower wrote
    `turret:owner`, and nothing carried the value from one to the other - so a
    player-deployed turret was owned by no one and could not be scored.
    """
    tid = to_id(id_or_obj)
    return 0 if tid is None else (get_inventory_value(tid, "turret:owner", 0) or 0)


def lm_turret_spend_charge(id_or_obj, n=1):
    """Charge a tower for firing. Returns the charge left; 0 means it just went dormant.

    Towers only - a mount draws from its host and has no magazine of its own.
    """
    from sbs_utils.procedural.turret import turret_config, turret_disengage, turret_set
    tid = to_id(id_or_obj)
    if tid is None or not lm_turret_is_tower(tid):
        return None
    left = turret_config(tid, "charge", None)
    if left is None:
        return None
    left = max(0, int(left) - int(n))
    turret_set(tid, "charge", left)
    if left <= 0:
        turret_disengage(tid)
        signal_emit("lm_turret_dormant", {"TURRET_ID": tid,
                                          "TURRET_OWNER_ID": lm_turret_owner(tid)})
    return left


def lm_turret_recharge(id_or_obj, amount=None):
    """Refill a dormant tower's magazine (a resupply run, a repair crew)."""
    from sbs_utils.procedural.turret import turret_config, turret_set
    tid = to_id(id_or_obj)
    if tid is None:
        return None
    amount = LM_TURRET_CHARGE if amount is None else int(amount)
    turret_set(tid, "charge", amount)
    signal_emit("lm_turret_recharged", {"TURRET_ID": tid, "TURRET_CHARGE": amount,
                                        "TURRET_OWNER_ID": lm_turret_owner(tid)})
    return amount


def lm_turret_is_dormant(id_or_obj):
    """Out of charge: still standing, still a target, but not shooting."""
    from sbs_utils.procedural.turret import turret_config
    tid = to_id(id_or_obj)
    if tid is None:
        return False
    left = turret_config(tid, "charge", None)
    return left is not None and int(left) <= 0


def lm_turret_lifetime():
    """Seconds a deployed tower lasts. A mission can override with a shared."""
    from sbs_utils.procedural.execution import get_shared_variable
    v = get_shared_variable("LM_TURRET_LIFETIME")
    return int(v) if v else LM_TURRET_LIFETIME


def lm_turret_gm_side(gm_id):
    """Which side a Game Master's turret should belong to.

    The GM rides a detached camera that carries a side like any other object, so its own
    side is the right default - a GM working a scenario is usually acting for one. Falls
    back to the first PLAYER side so a camera with no side set still places something
    useful rather than spawning turrets onto a side nobody is playing.
    """
    from sbs_utils.procedural.roles import role
    side = getattr(to_object(gm_id), "side", None)
    if side:
        return side
    for pid in role("__player__"):
        s = getattr(to_object(pid), "side", None)
        if s:
            return s
    return "tsn"
