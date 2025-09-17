
from sbs_utils.agent import Agent, get_story_id
from sbs_utils.procedural.execution import get_variable
from sbs_utils.procedural.query import to_object, to_id
from sbs_utils.procedural.links import link, unlink


from sbs_utils.helpers import FrameContext

from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.vec import Vec3


import sbs
from sbs_utils.procedural.routes import  RouteDamageObject

class Fleet(Agent):
    #--------------------------------------------------------------------------------------
    def __init__(self, position, side):
        super().__init__()

        self.id = get_story_id()
        self.add()
        self.side = side
        self.position = Vec3(position.x, position.y, position.z) #Vec3(0,0,0)
        self.destination = Vec3(0,0,0)
        self.anger_dict = {}
        self.add_role("fleet")
        self.name = f"fleet {self.id&0x0000FFFFFFFFFFFF}"

        if side is not None:
            if isinstance(side, str):
                roles = side.split(",")
            else:
                roles = side
            side = roles[0].strip()
            if side != "#":
#                obj.side = side
                self.side = side
#            self.update_comms_id()
            for role in roles:
                self.add_role(role)
        
        
        #task_schedule(self.tick)


    def get_best_anger(self):
        sim = FrameContext.sim
        if sim is None:
            return
        best_id = None
        best_anger = 0
        new_anger = {}
        for e in self.anger_dict:
            if 0 == e:
                continue
            if to_object(e) is None:
                continue

            end_time = self.anger_dict[e]
            time_now = sim.time_tick_counter
            that_anger = (end_time - time_now) # Not needed// 30 # 30 Sim FPS
            that_anger = max(0, that_anger)
            if best_anger < that_anger:
                best_anger = that_anger
                best_id = e
            # Keep it in angry if still angry
            if that_anger >0:
                new_anger[e] = end_time
        self.anger_dict = new_anger

        return best_id

    #--------------------------------------------------------------------------------------
    def ship_takes_damage(self, my_ship_id, attacker_id):
        if 0 == attacker_id:
            print(f"0 == attacker_id:     WTF!")
            return

        self.make_enraged_by(attacker_id) 
        #self.anger_dict[attacker_id] = 100  # how long I will be angry

    def get_heat_for(self, an_id_or_obj):
        sim = FrameContext.sim
        if sim is None:
            return
        id = to_id(an_id_or_obj)
        end_time =  self.anger_dict.get(id, None)
        if end_time is None:
            return 0
        time_now = sim.time_tick_counter
        left = max(end_time-time_now, 0)
        left //= 30
        return left
    
    def make_enraged_by(self, an_id_or_obj):
        id = to_id(an_id_or_obj)
        if 0 == id or id is None:
            return
        sim = FrameContext.sim
        if sim is None:
            return
        # 30 Per Second and 120 seconds
        end_time = sim.time_tick_counter + 30 *120

        self.anger_dict[id] = end_time  # how long I will be angry

#--------------------------------------------------------------------------------------
@RouteDamageObject 
def ship_takes_damage():#event):
    event = get_variable("EVENT")
#    print(f"fleet  ship_takes_damage {event.tag} {event.sub_tag}")

    # parent is 0 for ship as origin, ship for ordinance 
    attacker_id = event.parent_id
    if 0 == attacker_id:
        attacker_id = event.origin_id

    if 0 == attacker_id:
         # Probably a mine
        return
    victim_id = event.selected_id
    my_fleet = to_object(get_inventory_value(victim_id, "my_fleet_id"))
    if None != my_fleet:
        my_fleet.ship_takes_damage(victim_id, attacker_id)

#--------------------------------------------------------------------------------------
def fleet_spawn(position, side):
    return Fleet(position, side)


def fleet_add(fleet_id, npc_id):
    fleet_id = to_id(fleet_id)
    fleet_obj = to_object(fleet_id)
    

    npc_id = to_id(npc_id)
    npc_obj = to_object(npc_id)

    if fleet_obj is None or npc_obj is None:
        return
    
    # Make sure it is on the proper side
    npc_obj.side = fleet_obj.side
    
    set_inventory_value(npc_id, "my_fleet_id", fleet_id)
    link(fleet_id,"ship_list", npc_id)


def fleet_remove(fleet_id, npc_id):
    fleet_id = to_id(fleet_id)
    npc_id = to_id(npc_id)

    set_inventory_value(npc_id, "my_fleet_id", None)
    unlink(fleet_id,"ship_list", npc_id)
    



"""

Fleet

contains a list of ships that belong to it
position
destination
path to target
anger management



Tick()
get average center of all my ships
that's my point
move my point in the direction I want to go (perhaps 1000m?)
tell all my ships to go to that point (and go throttle 1.0)

make decisions about where the fleet goes
	naviagitn ghte existing path
	refreshing a stale path

reduce all heats by 1

anger:
ship takes damage from emeny:
	set enemy heat to 100

if best heat > 0
	tell all ships to move to and attack heat target


"""