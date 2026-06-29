"""Engine-network culling for the Open Universe (Epic A2).

`sbs.push_to_standby_list` removes an object from the engine sim + network
replication while its py-side Agent (roles/links/inventory) persists - so
distant, irrelevant objects stop costing the network without losing script
state. (Confirmed: physics/replication iterate sim.space_objects; standby pulls
the object out of it.)

Brains are MAST tasks independent of the sim, so a parked NPC's brain would keep
acting on a non-simulated object - so the culler pauses a parked object's brain
(brain_pause) and resumes it on retrieve. That makes terrain AND self-brained
NPCs/POIs safe to cull. A parked object isn't in normal space, so its position is
cached.

Fleets are handled as a unit (universe_cull_fleets): a fleet's brain lives on the
fleet agent (role raider_fleet), not its ships (linked via "ship_list"), so we
park/retrieve all the fleet's ships together and pause/resume the one fleet brain
- the whole formation goes dark when no player is near any of its ships.
"""
import sbs
from sbs_utils.procedural.query import to_object_list, to_object
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.links import linked_to
from sbs_utils.procedural.brain import brain_pause, brain_resume

# id -> (x, y, z), captured when parked (parked objects aren't in normal space).
_parked_pos = {}
# fleet_id -> [ship_id, ...], the fleets whose ships are parked + brain paused.
_parked_fleets = {}


def universe_cull_step(candidates, radius):
    """Park candidates with no player within `radius` (out of the engine
    network); retrieve parked ones once a player comes near. Static, brain-less
    objects only. `candidates` is an iterable of Agents (e.g. a role set)."""
    players = to_object_list(role("__player__"))
    if not players:
        return
    pts = []
    for p in players:
        pp = p.pos
        pts.append((pp.x, pp.y, pp.z))
    r2 = radius * radius
    for obj in candidates:
        oid = obj.id
        parked = oid in _parked_pos
        if parked:
            x, y, z = _parked_pos[oid]
        else:
            pp = getattr(obj, "pos", None)
            if pp is None:
                continue   # skip non-space agents that share a role
            x, y, z = pp.x, pp.y, pp.z
        near = False
        for (px, py, pz) in pts:
            dx, dy, dz = px - x, py - y, pz - z
            if dx * dx + dy * dy + dz * dz <= r2:
                near = True
                break
        if near and parked:
            sbs.retrieve_from_standby_list_id(oid)
            brain_resume(oid)            # no-op if the object has no brain
            _parked_pos.pop(oid, None)
        elif (not near) and not parked:
            _parked_pos[oid] = (x, y, z)
            brain_pause(oid)             # a self-brained NPC stops acting while parked
            sbs.push_to_standby_list_id(oid)


def _player_points():
    """(x,y,z) of every player, or None if there are no players."""
    players = to_object_list(role("__player__"))
    if not players:
        return None
    pts = []
    for p in players:
        pp = p.pos
        pts.append((pp.x, pp.y, pp.z))
    return pts


def _near_any(x, y, z, pts, r2):
    for (px, py, pz) in pts:
        dx, dy, dz = px - x, py - y, pz - z
        if dx * dx + dy * dy + dz * dz <= r2:
            return True
    return False


def universe_cull_fleets(fleet_role, radius):
    """Park/retrieve whole fleets by proximity. A fleet (an agent with `fleet_role`
    whose ships are linked under "ship_list") is parked when no player is within
    `radius` of ANY of its ships: every ship goes to standby and the fleet's brain
    is paused (it lives on the fleet agent). It is retrieved the moment a player
    comes near again. Treating the formation as one unit keeps the fleet brain from
    steering non-simulated ships."""
    pts = _player_points()
    if pts is None:
        return
    r2 = radius * radius
    for fleet in to_object_list(role(fleet_role)):
        fid = fleet.id
        parked = fid in _parked_fleets
        if parked:
            ship_ids = _parked_fleets[fid]
        else:
            ship_ids = list(linked_to(fid, "ship_list"))
        if not ship_ids:
            continue
        # Near if any member ship is within radius (cached pos for parked ships).
        near = False
        for sid in ship_ids:
            if sid in _parked_pos:
                x, y, z = _parked_pos[sid]
            else:
                so = to_object(sid)
                sp = getattr(so, "pos", None) if so is not None else None
                if sp is None:
                    continue
                x, y, z = sp.x, sp.y, sp.z
            if _near_any(x, y, z, pts, r2):
                near = True
                break
        if near and parked:
            for sid in ship_ids:
                sbs.retrieve_from_standby_list_id(sid)
                _parked_pos.pop(sid, None)
            brain_resume(fid)
            _parked_fleets.pop(fid, None)
        elif (not near) and not parked:
            for sid in ship_ids:
                so = to_object(sid)
                sp = getattr(so, "pos", None) if so is not None else None
                if sp is not None:
                    _parked_pos[sid] = (sp.x, sp.y, sp.z)
                sbs.push_to_standby_list_id(sid)
            brain_pause(fid)          # the fleet brain stops steering parked ships
            _parked_fleets[fid] = ship_ids


def universe_cull_clear():
    """Retrieve everything parked and forget it - call before clearing a system
    on a jump, so parked terrain returns to normal space and gets despawned with
    the rest (delete-by-box only sees objects in normal space, not standby)."""
    for oid in list(_parked_pos.keys()):
        sbs.retrieve_from_standby_list_id(oid)
        brain_resume(oid)
    for fid in list(_parked_fleets.keys()):
        brain_resume(fid)            # ships already retrieved via _parked_pos above
    _parked_pos.clear()
    _parked_fleets.clear()


def universe_cull_count():
    """How many objects are currently parked (diagnostics): loose objects + fleet
    ships."""
    return len(_parked_pos)
