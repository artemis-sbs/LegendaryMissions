from sbs_utils.agent import Agent, get_story_id
from sbs_utils.mast.label import label
from sbs_utils.procedural.execution import task_schedule, jump, AWAIT
from sbs_utils.procedural.timers import delay_sim, is_timer_finished, set_timer, is_timer_set, clear_timer
from sbs_utils.procedural.query import to_object, to_id, object_exists, to_object_list, get_side
from sbs_utils.procedural.space_objects import target, closest, broad_test_around, target_pos
from sbs_utils.procedural.roles import role, all_roles, add_role, remove_role, any_role
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.procedural.links import get_dedicated_link, set_dedicated_link
from sbs_utils.vec import Vec3


import random

import sbs

class NpcCAG(Agent):
    #--------------------------------------------------------------------------------------
    def __init__(self):
        super().__init__()


        self.id = get_story_id()
        self.add()
        self.add_role("npccag")

        task_schedule(self.tick_fighter_launch)
        task_schedule(self.tick_fighter_manage)

    #--------------------------------------------------------------------------------------
    def get_fighter_key(self, carrier_race):
        # TODO: This is not good enough for modding
        if carrier_race is None:
            return "arvonian_fighter"
        
        if carrier_race=="xim":
            carrier_race = "ximni"


        match carrier_race:
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

        # Look for a player capital ship or single-seat craft nearby
        if None is the_target:
            the_target = closest(fighter_id, local_arena & any_role("__player__,cockpit") - role(get_side(fighter_id)))

        # Look for a station or friendly npc ship nearby
        if None == the_target:
            # Can't use the TSN role currently because that includes the gamemaster ship
            the_target = closest(fighter_id, local_arena & any_role("station,defender,civilian") - role(get_side(fighter_id)))

        return to_id(the_target)

    #--------------------------------------------------------------------------------------
    # Fighter complement model (dwindling, never refilling):
    #   Each carrier owns two link lists keyed on the CARRIER (not the CAG):
    #     active_fighter_list   - fighters currently out on patrol
    #     inactive_fighter_list - survivors docked on standby, ready to relaunch
    #   The starting complement (bay_count) is a hard ceiling. Fighters cycle
    #   active <-> inactive as they launch and return, but the total only ever
    #   stays the same or SHRINKS: a destroyed fighter is dropped from both lists
    #   and is never replaced. We spawn exactly once (first launch); afterwards we
    #   only ever relaunch the survivors we still have.
    #--------------------------------------------------------------------------------------
    @label()
    def tick_fighter_launch(self):
        for e in to_object_list(all_roles("npc,carrier")):   # roles npc,carrier
            # If the carrier doesn't exist skip it
            if not object_exists(e):
                continue

            fighter_key = self.get_fighter_key(e.race)
            start_pos = e.pos
            carrier_side = e.side

            # set up the refit timer for this carrier
            if not e.has_role("fighter_refit_timer"):
                e.add_role("fighter_refit_timer")
                set_timer(e, "fighter_refit", seconds = 1)

            # Only launch when the refit window has elapsed
            if not (is_timer_set(e, "fighter_refit") and is_timer_finished(e, "fighter_refit")):
                continue

            # find a fighter target within 8k? - nothing to target, don't launch
            target_id = self.find_fighter_target_id(e.id)
            if target_id is None:
                continue

            if not e.has_role("cag_initialized"):
                # First launch: spawn the starting complement into the active list.
                # This is the ONLY place fighters are created - the ceiling is set here.
                e.add_role("cag_initialized")
                fighter_count = e.data_set.get("bay_count", 0)
                for g in range(fighter_count):
                    # launch an npc fighter
                    nam = f"{e.name} {str(random.randint(0,99)).zfill(2)}"
                    spawn_data = npc_spawn(start_pos.x, start_pos.y, start_pos.z, nam, f"{carrier_side}, fighter", fighter_key, "behav_npcship")
                    spawn_id = to_id(spawn_data)
                    # link them to me
                    e.add_link("active_fighter_list", spawn_id)
                    # set their bingo timer
                    set_timer(spawn_id, "bingo", seconds=120)
                    set_dedicated_link(spawn_id, "my_carrier", to_id(e))
                    # set them on the right path
                    target(spawn_id, target_id)
            else:
                # Relaunch: pull the surviving docked fighters back off standby.
                # No new fighters are ever created here - if none survived, nothing launches.
                # Copy the set first: retrieving mutates the live link collection.
                inactive = list(e.get_link_set("inactive_fighter_list"))
                for f in inactive:
                    e.remove_link("inactive_fighter_list", f)
                    craft = to_object(f)
                    # A docked fighter is on the standby list (out of normal space),
                    # so object_exists() is False for it - do NOT use that here or we
                    # would discard every survivor. to_object() is None only when the
                    # fighter is truly gone (deleted / carrier teardown); drop those.
                    if craft is None:
                        continue   # died while docked - drop it, don't relaunch
                    e.add_link("active_fighter_list", f)
                    sbs.retrieve_from_standby_list(craft.engine_object)
                    add_role(f, carrier_side)
                    set_timer(f, "bingo", seconds=120)
                    target(f, target_id)

            clear_timer(e, "fighter_refit")

        yield AWAIT(delay_sim(seconds=10))
        yield jump(self.tick_fighter_launch)



    #--------------------------------------------------------------------------------------
    @label()
    def tick_fighter_manage(self):
        # Manage each carrier's own active fighters. get_link_list returns a copy,
        # so removing from the list while iterating is safe.
        for e in to_object_list(all_roles("npc,carrier")):
            if not object_exists(e):
                continue

            for fighter_id in e.get_link_list("active_fighter_list"):
                craft = to_object(fighter_id)
                # Destroyed fighter: drop it from the complement (dwindle) and skip.
                if craft is None or not object_exists(craft):
                    e.remove_link("active_fighter_list", fighter_id)
                    continue

                # check the bingo timer
                if not is_timer_finished(fighter_id, "bingo"):
                    # find a target to direct them to
                    t_id = self.find_fighter_target_id(fighter_id)
                    t_obj = to_object(t_id)
                    if None is not t_id and None is not t_obj:
                        pos = Vec3(t_obj.pos)
                        difference = Vec3(pos) - Vec3(craft.pos)
                        if difference.length() < 2500:
                            pos = pos.rand_offset(300, 600)
                            target_pos(fighter_id, *pos, target_id=t_id)
                        else:
                            target(fighter_id, t_id)
                    continue

                # Bingo timer is finished - get them back to their carrier
                carrier = to_object(get_dedicated_link(fighter_id, "my_carrier"))
                if carrier is None:
                    continue

                target(fighter_id, carrier, shoot=False) # going home to my carrier
                # if they get close enough to their carrier
                difference = Vec3(carrier.pos) - Vec3(craft.pos)
                if difference.length() < 500:
                    # Docked: move active -> inactive (standby) and arm the relaunch
                    # timer. The fighter object survives; it is NOT counted again.
                    remove_role(fighter_id, carrier.side)
                    e.remove_link("active_fighter_list", fighter_id)
                    e.add_link("inactive_fighter_list", fighter_id)
                    set_timer(carrier, "fighter_refit", seconds=60)
                    sbs.push_to_standby_list(craft.engine_object)

        yield AWAIT(delay_sim(seconds=2))
        yield jump(self.tick_fighter_manage)


_npc_cag = None
#--------------------------------------------------------------------------------------
def start_npc_cag():
    global _npc_cag
    if None is _npc_cag:
        _npc_cag = NpcCAG()
    return _npc_cag




