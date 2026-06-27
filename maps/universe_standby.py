"""Engine-network culling for the Open Universe (Epic A2).

`sbs.push_to_standby_list` removes an object from the engine sim + network
replication while its py-side Agent (roles/links/inventory) persists - so
distant, irrelevant objects stop costing the network without losing script
state. (Confirmed: physics/replication iterate sim.space_objects; standby pulls
the object out of it.)

Brains are MAST tasks independent of the sim, so a parked NPC's brain would keep
acting on a non-simulated object. Therefore only park brain-less STATIC objects
here - terrain (asteroid/nebula), which is also the bulk of objects. A parked
object isn't in normal space, so its position is cached at park time.
"""
import sbs
from sbs_utils.procedural.query import to_object_list
from sbs_utils.procedural.roles import role

# id -> (x, y, z), captured when parked (parked objects aren't in normal space).
_parked_pos = {}


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
            pp = obj.pos
            x, y, z = pp.x, pp.y, pp.z
        near = False
        for (px, py, pz) in pts:
            dx, dy, dz = px - x, py - y, pz - z
            if dx * dx + dy * dy + dz * dz <= r2:
                near = True
                break
        if near and parked:
            sbs.retrieve_from_standby_list_id(oid)
            _parked_pos.pop(oid, None)
        elif (not near) and not parked:
            _parked_pos[oid] = (x, y, z)
            sbs.push_to_standby_list_id(oid)


def universe_cull_clear():
    """Retrieve everything parked and forget it - call before clearing a system
    on a jump, so parked terrain returns to normal space and gets despawned with
    the rest (delete-by-box only sees objects in normal space, not standby)."""
    for oid in list(_parked_pos.keys()):
        sbs.retrieve_from_standby_list_id(oid)
    _parked_pos.clear()


def universe_cull_count():
    """How many objects are currently parked (diagnostics)."""
    return len(_parked_pos)
