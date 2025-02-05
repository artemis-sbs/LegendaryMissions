
from sbs_utils.agent import Agent, get_story_id
from sbs_utils.mast.label import label
from sbs_utils.procedural.execution import task_schedule, jump, AWAIT, get_variable
from sbs_utils.procedural.timers import delay_sim
from sbs_utils.procedural.query import to_object, to_id, object_exists, get_side
from sbs_utils.procedural.space_objects import target_pos, closest, broad_test_around
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.inventory import get_inventory_value
from sbs_utils import faces
from sbs_utils.vec import Vec3
from sbs_utils.scatter import rect_fill


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

        task_schedule(self.tick)

#        self.set_inventory_value("anger_map",{})
#        self.set_link_value("ship_list",{})

    #--------------------------------------------------------------------------------------
    @label()
    def tick(self):
        #get average center of all my ships
        #self.add_link("ship_list", ship_id)
        #self.remove_link("ship_list", ship_id)

        ship_set = self.get_link_objects("ship_list")
        if len(ship_set) < 1:
            yield AWAIT(delay_sim(seconds=5))
            yield jump(self.tick)

        average = Vec3(0,0,0)
        for e in ship_set:
            if object_exists(e):
                average.x += e.engine_object.pos.x
                average.y += e.engine_object.pos.y
                average.z += e.engine_object.pos.z
            else:
                # cull this object from the linked objects
                self.remove_link("ship_list", e.id)

        average /= len(ship_set)

        #that's my point
        self.position = average

        use_path = False

        #--------------------------------------------------------------------
        #move my point in the direction I want to go (perhaps 1000m?)

        difference = Vec3(self.destination) - Vec3(self.position)
        lengthA = difference.length()
#        if lengthA > 3000:
#            use_path = True
        difference = difference.unit()
        pushA = min(lengthA, 2000)
        difference *= pushA
        self.position += difference


        #--------------------------------------------------------------------
        # am I angry at someone?
        best_id = None
        best_anger = 0
        anger_as_set = set()
        for e in self.anger_dict:
            if 0 == e:
                return
            anger_as_set.add(e)
            that_anger = self.anger_dict[e]
            if best_anger < that_anger:
                best_anger = that_anger
                best_id = e
            self.anger_dict[e] = max(0,that_anger-1) # reduce heat over time

        if None != best_id:   # someone to be angry at
            # if so, we should move towards him
            enemy = Agent.get(best_id)
            if None != enemy:
                self.position = enemy.pos
                use_path = False

        #--------------------------------------------------------------------
        # if it's time, find a path




        #--------------------------------------------------------------------

        #--------------------------------------------------------------------
        # find target to move to and attack

        # Look for a station near 
        lead_ship_id = to_id(ship_set[0])
        #
        # Limit some tests to area around the fleet
        #
        local_arena = broad_test_around(lead_ship_id, 3000,3000, 0xF0)

        #
        # Target who you're most angry with first
        # Look for anything in anger list
        # This should include fighters and or friendlies as well as players
        #
        the_target = None
        

        if the_target is None and len(anger_as_set)>0:
            if best_anger in local_arena:
                the_target = best_anger
            else:
                the_target = closest(lead_ship_id, local_arena & anger_as_set )


        if the_target is None:
            the_target = closest(lead_ship_id, local_arena & role("Station") - role(get_side(lead_ship_id)))

        # Look for a player near 
        if the_target is None:
            the_target = closest(lead_ship_id, local_arena & role("__player__") & role("cockpit") - role(get_side(lead_ship_id)))

        # Otherwise look for a tsn station
        if the_target is None:
            the_target = closest(lead_ship_id, role("Station")- role(get_side(lead_ship_id)))

        # If any of these check resulted in a target
        if the_target is not None:
            self.destination = Vec3(to_object(the_target).engine_object.pos)

        difference = Vec3(self.destination) - Vec3(self.position)
        lengthA = difference.length()
        throttle = 1.0
        if lengthA > 50000:
            throttle = 2.0
        elif lengthA > 30000:
            throttle = 1.5
            
        # Set the target position, optionally shot at something
        #target_pos(ship_set, *self.position.xyz, throttle, the_target, stop_dist=500)
        # count = len(ship_set)
        # pos = Vec3(self.position)
        # points = rect_fill(count, 2, pos.x, pos.y, pos.z, 2000, 2000, random=False, ax=0,ay=0,az=0, degrees=True)
        points = ship_set
        
        for _id in points:
            pos = Vec3(self.position)
            pos = pos.rand_offset(300, 500, ring=True)
            target_pos(_id, *pos.xyz, throttle, the_target, stop_dist=500)
            # count -= 1
            # if count <=0:
            #     break
        

        yield AWAIT(delay_sim(seconds=10))
        yield jump(self.tick)

    #--------------------------------------------------------------------------------------
    def ship_takes_damage(self, my_ship_id, attacker_id):
        if 0 == attacker_id:
            print(f"0 == attacker_id:     WTF!")
            return

        self.anger_dict[attacker_id] = 100  # how long I will be angry

    def get_heat_for(self, an_id_or_obj):
        id = to_id(an_id_or_obj)
        return self.anger_dict.get(id, 0)

    def make_enraged_by(self, an_id_or_obj):
        id = to_id(an_id_or_obj)
        if id is None:
            return
        self.anger_dict[id] = 100  # how long I will be angry

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