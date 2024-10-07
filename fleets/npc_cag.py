from sbs_utils.objects import Npc
from sbs_utils.agent import Agent, get_story_id
from sbs_utils.mast.label import label
from sbs_utils.tickdispatcher import TickDispatcher
from sbs_utils.procedural.execution import task_schedule, jump, AWAIT, get_variable
from sbs_utils.procedural.timers import delay_sim, is_timer_set_and_finished, is_timer_finished, set_timer, is_timer_set, clear_timer
from sbs_utils.procedural.query import to_object, to_id, object_exists, to_object_list, get_side
from sbs_utils.procedural.space_objects import target, closest, broad_test_around, target_pos
from sbs_utils.procedural.roles import role, all_roles, get_race, add_role, remove_role
from sbs_utils.procedural.science import science_set_scan_data
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.procedural.links import get_dedicated_link, set_dedicated_link, unlink, link
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils import faces
from sbs_utils.scatter import sphere
from sbs_utils.vec import Vec3


from enum import IntEnum
import random

import sbs

class NpcCAG(Agent):
    #--------------------------------------------------------------------------------------
    def __init__(self):
        super().__init__()

        #print("NpcCAG(Agent): START")

        self.id = get_story_id()
        self.add()
        self.add_role("npccag")

        task_schedule(self.tick_fighter_launch)
        task_schedule(self.tick_fighter_manage)

    #--------------------------------------------------------------------------------------
    def get_fighter_key(self, carrier_race):
        race = ""
        r_type = carrier_race
        race = r_type[0].split("_")
        race = race[0]
        if race=="xim":
            race = "ximni"

        match race:
            case "tsn":
                return "tsn_fighter"
            case "pirate":
                return "pirate_fighter"
            case "ximni":
                return "xim_avenger"

        return "arvonian_fighter"

    #--------------------------------------------------------------------------------------
    def find_fighter_target_id(self, fighter_id):
        the_target = None
        local_arena = broad_test_around(fighter_id, 8000,8000, 0xF0)

        # Look for a player near 
        if None is the_target:
            the_target = closest(fighter_id, local_arena & role("__player__") & role("cockpit") - role(get_side(fighter_id)))

        # Look for a station near 
        if None == the_target:
            the_target = closest(fighter_id, local_arena & role("Station") - role(get_side(fighter_id)))

        return to_id(the_target)

    #--------------------------------------------------------------------------------------
    @label()
    def tick_fighter_launch(self):
        for e in to_object_list(all_roles("npc,carrier")):   # roles npc,carrier
            # If the carrier doesn't exist skip it
            if not object_exists(e):
                continue  

            blob = e.data_set
            fighter_count = blob.get("bay_count",0)
            fighter_count = get_inventory_value(e, "fighters_in_bay", fighter_count)
            fighter_key = self.get_fighter_key(get_race(e))
            start_pos = e.pos

            #print(f"tick_fighter_launch: managing {e.name} carrier")

            # set up the refit timer for this carrier
            if not e.has_role("fighter_refit_timer"):
                e.add_role("fighter_refit_timer")
                set_timer(e, "fighter_refit", seconds = 1)

            if is_timer_set(e, "fighter_refit") and is_timer_finished(e, "fighter_refit"):
                #find a fighter target within 8k?
                target_id = self.find_fighter_target_id(e.id)
                # Nothing to target don't launch
                if target_id is None:
                    continue
#                        target_ref = to_object(target_id)

                #print(f"Launching {fighter_count} fighters")
                inactive = self.get_link_set("inactive_fighter_list")
                if len(inactive) > 0:
                    for f in inactive:
                        self.add_link("active_fighter_list", f)
                        self.remove_link("inactive_fighter_list", f)
                        craft = to_object(f)
                        sbs.retrieve_from_standby_list(craft.engine_object)
                        add_role(f, "raider")
                        set_timer(f, "bingo", seconds=120)
                        target(f, target_id)
                else:
                    for g in range(fighter_count):
                        # launch an npc fighter
                        nam = f"{e.name} {str(random.randint(0,99)).zfill(2)}"
                        spawn_data = npc_spawn(start_pos.x, start_pos.y, start_pos.z, nam, "raider,fighter", fighter_key, "behav_npcship")
                        spawn_id = to_id(spawn_data)
                        # link them to me
                        self.add_link("active_fighter_list", spawn_id)

                        # set their bingo timer
                        set_timer(spawn_id, "bingo", seconds=120)
                        set_dedicated_link(spawn_id, "my_carrier", to_id(e))
                        # set them on the right path
                        target(spawn_id, target_id)

                set_inventory_value(e, "fighters_in_bay", 0)
                clear_timer(e, "fighter_refit")

        yield AWAIT(delay_sim(seconds=10))
        yield jump(self.tick_fighter_launch)



    #--------------------------------------------------------------------------------------
    @label()
    def tick_fighter_manage(self):
        # look at all my active fighters
        fighter_set = self.get_link_list("active_fighter_list")
        for fighter_id in fighter_set:
            craft = to_object(fighter_id)            
            if craft is None:
                continue
            if not object_exists(craft):
                continue
            #print(f"managing {e.name} fighter")

            
            # check the bingo timer
            if not is_timer_finished(fighter_id, "bingo"):
                # find a target to direct them to
                t_id = self.find_fighter_target_id(fighter_id)
                t_obj = to_object(t_id)
                if None is not t_id and None is not t_obj:
                    pos = Vec3(t_obj.pos)
                    difference = Vec3(pos) - Vec3(craft.pos)
                    if difference.length() < 2500:
                        #print("CAG: scattering")
                        pos = pos.rand_offset(300, 600)
                        target_pos(fighter_id, *pos, target_id=t_id)
                    else:
                        #print("CAG: targeting")
                        target(fighter_id, t_id)
                continue

            # Bingo timer is finished
            # get them back to their carrier
            carrier = to_object(get_dedicated_link(fighter_id, "my_carrier"))
            if carrier is None:
                continue
            
            target(fighter_id, carrier, shoot=False) # going to my fighter
            # if they get close enough to their carrier
            difference = Vec3(carrier.pos) - Vec3(craft.pos)
            if difference.length() < 500:

                #print(f"recovering {e.name} fighter")
                # destroy them and reset the carrier's launch timer
                fv = get_inventory_value(carrier, "fighters_in_bay",0)
                set_inventory_value(carrier, "fighters_in_bay", fv+1)
                remove_role(fighter_id, "raider")

                set_timer(carrier, "fighter_refit",seconds=60)
                carrier.remove_link("active_fighter_list", fighter_id)
                carrier.add_link( "inactive_fighter_list", fighter_id)
                # unlink(e, "my_carrier", to_id(carrier))
                sbs.push_to_standby_list(craft.engine_object)
                # sbs.delete_object(fighter_id)

        

        yield AWAIT(delay_sim(seconds=2))
        yield jump(self.tick_fighter_manage)


_npc_cag = None
#--------------------------------------------------------------------------------------
def start_npc_cag():
    global _npc_cag
    if None is _npc_cag:
        _npc_cag = NpcCAG()
    return _npc_cag




