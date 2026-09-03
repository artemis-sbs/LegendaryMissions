
from sbs_utils.procedural.execution import get_shared_variable
from sbs_utils.procedural.query import to_id, to_object, to_blob #, object_exists, to_object_list, get_side
from sbs_utils.procedural.sides import side_set_hostile_to_players
from sbs_utils.procedural.roles import add_role
from sbs_utils.procedural.routes import follow_route_select_science
from sbs_utils.procedural.spawn import npc_spawn, terrain_spawn
from sbs_utils.procedural.links import link, unlink
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils import faces as faces
from sbs_utils.faces import set_face, random_face
from sbs_utils.names import name_random_hostile
from sbs_utils.vec import Vec3
import random
from fleet import fleet_spawn
from sbs_utils.procedural.fleet_tables import (
    fleet_table_get, fleet_table_races, fleet_table_pick_race)
from sbs_utils.procedural.ship_data import art_key_for
from elite_abilitites import elite_get_all_abilities, elite_is_engine_ability, random_bits



def player_ship_update_friendly(player_id, friends, initial_scan = False):
    blob = to_blob(player_id)
    num_ids = 0 # blob.get("num_extra_scan_sources",0)
    print("NOTE: player_ship_update_friendly is depreicated")
    print("use link(player_ship. 'extra_scan_source', the_scan_sources)  ")
    print("system will update")


    for friend in friends:
        blob.set("extra_scan_source", to_id(friend), num_ids)
        num_ids += 1
        if initial_scan:
            follow_route_select_science(to_id(player_id), to_id(friend))

    blob.set("num_extra_scan_sources",num_ids,0)





# The stock theater, declared in races/theaters.amd. Used when nothing else is selected, so
# the maps have no enemy roster of their own to fall back to any more.
STOCK_THEATER = "legendary"


def _fleet_can_raid(eligible=None):
    """`eligible`, ANDed with "this race is an enabled NPC race with a fleet ladder".

    The ladder half is `fleet_table_can_field`, which names a rostered race it cannot
    field once per mission - a theater naming a race nothing can build is a data error in
    the theater, and the quiet version of it is a faction written into the roster that
    simply never turns up.

    THE NPC_RACES HALF IS THE ANSWER TO "Skaraan show up even when they aren't NPC
    races" (GWQ-12), and it is here rather than anywhere else because a THEATER roster is
    not the NPC_RACES setting and never has been. The stock `legendary` theater rosters
    skaraan; a TNG game excludes skaraan from NPC_RACES; and the only thing standing
    between the two was that the ladder happens to be registered behind the same setting,
    over in `races/__init__.mast`. That is a second gate in another addon's top-level
    code, and addon load order is not deterministic - so "is the ladder registered yet"
    was doing duty for "is this race allowed", which it only resembles.

    Asking the setting directly makes the rule the rule: a race the operator has turned
    off cannot be PICKED, whatever any theater rosters and whoever loaded first. Note
    this gates the random/theater pick only - `fleet_create` uses an explicitly named
    race as given, so a map that deliberately spawns one faction (siege's Skaraan
    "independent contractors") is untouched.
    """
    from sbs_utils.procedural.fleet_tables import fleet_table_can_field
    from sbs_utils.procedural.settings import settings_race_is_npc

    def test(race):
        # An EMPTY NPC_RACES means "no restriction", not "no races" - that is the
        # setting's own contract, so this cannot empty a mission that never set it.
        if not settings_race_is_npc(race):
            return False
        if not fleet_table_can_field(race):
            return False
        return eligible is None or eligible(race)

    return test


def fleet_pick_enemy_race(race_list=None, weights=None, difficulty=None, eligible=None):
    """This map's enemy race, from the active THEATER's ladder.

    THE MAPS USED TO CARRY THIS AS TWO POSITIONAL ARRAYS - a four-name
    ``enemyTypeNameList`` and a table of weight rows zipped against it by position. Nothing
    read data, so who a mission fought was a literal no profile and no mod could reach, and
    a roster was four long because a table was four columns wide. A total conversion could
    therefore only ALIAS its factions onto the four stock names; that is why every theater in
    the TNG pack rosters the same four and differs only in its art.

    Weights are keyed by race now (``kralien:70``), so the ladder has no length and no order
    to get wrong, and a roster can mix mod and stock races freely.

    Args:
        race_list: the caller's own spelling of the races it knows, when it has one. NOT a
            gate - a race the theater rosters is returned even if this map has never heard of
            it. Kept because a caller that still compares against its own literals wants a
            match rather than a lower-cased roster entry.
        weights: a caller-supplied row, used only if the theater declares none.
        difficulty: which ``Weights <n>:`` tier to read - the 1-based DIFFICULTY.
        eligible: what the race must be able to DO, ON TOP of being able to raid at all.
            borderwar and deepstrike pass `race_has_station`, because they build enemy
            starbases and not every race has one - which is what their shortened
            three-name list was really encoding.

    EVERY CALLER OF THIS IS ABOUT TO BUILD A FLEET, so having a registered ladder is not
    the caller's constraint to remember - it is the floor. A theater may roster a race the
    ship table knows and no ladder covers: the TNG pack's Breen is a real shipData side
    with one hull, rostered at 4-20% in two theaters, and it had no `fleets.yaml`. That
    made `fleet_create` print and return None, and `prefab_fleet_raider` then died on
    `brain_add(fleet.id, ...)` with `'NoneType' object has no attribute 'id'` - a runtime
    error for a whole slice of the roster, on a mission that otherwise looked fine. The
    race is dropped from the pick here instead, so the mission gets one of the theater's
    other factions rather than an exception.
    """
    from sbs_utils.procedural.amd_theater import theater_pick_race, theater_get
    eligible = _fleet_can_raid(eligible)
    pick = theater_pick_race(weights, names=race_list, difficulty=difficulty,
                             eligible=eligible)
    if pick is None and theater_get() is None:
        # No theater selected at all - use the stock ladder by name rather than a literal.
        pick = theater_pick_race(weights, names=race_list, key=STOCK_THEATER,
                                 difficulty=difficulty, eligible=eligible)
    if pick is not None:
        return pick
    # Last resort: whatever the caller knows. Reached when the selected theater rosters
    # nothing this map can use - every race filtered out by `eligible`, say - and returning
    # None here would leave the map with no enemy at all.
    fallback = [r for r in (race_list or []) if eligible(r)] or fleet_enemy_races(eligible)
    if not fallback:
        return None
    if weights and len(weights) == len(fallback):
        return random.choices(fallback, weights=weights)[0]
    return random.choice(fallback)


def fleet_enemy_races(eligible=None):
    """Every race that can raid, honoring ``eligible``. The roster, with no literal in it.

    ``race_npc_list`` is three gates at once - in the ship table, enabled in NPC_RACES, and
    carrying a fleet ladder - because each of those failing on its own is invisible: a race
    with no ladder makes `fleet_create` print and return None, which reads as "this mission
    has no enemies".
    """
    from sbs_utils.procedural.races import race_npc_list
    races = race_npc_list()
    if eligible is not None:
        races = [r for r in races if eligible(r)]
    return races


def fleet_remove_ship(id_or_obj):
    ship_id = to_id(id_or_obj)
    if ship_id is None:
        return
    fleet_id = get_inventory_value(ship_id, "my_fleet_id")
    unlink(fleet_id,"ship_list", ship_id)



#--------------------------------------------------------------------------------------
def fleet_create(race, fleet_diff, posx, posy, posz, fleet_roles = "RaiderFleet", ship_roles=None, faction_side=False):
    """Create a new fleet and add the appropriate amount of ships

    Args:
        race (str): 
        fleet_diff (int): DIFFICULTY -1 to use as index for fleet lists
        posx (float): location
        posy (float): location
        posz (float): location
        fleet_roles (str, optional): Role for the fleet. Defaults to "RaiderFleet".
        ship_roles (str, optional): Roles for the ships. Defaults to None.

    Returns:
        fleet (Fleet): The created fleet
    """
    # At this point it is an index 0-10
    diff = get_shared_variable("DIFFICULTY", 4)
    # If it is -1 use the default
    if  fleet_diff == -1:
        fleet_diff = diff
    # if it < -99, adjust diffulty minus the hundreds place
    # it is an add either way negative is same as subtract
    if  fleet_diff < -99 or fleet_diff>99:
            fleet_diff = diff+(fleet_diff//100)

    fleet_diff = max(0, min(10,fleet_diff))
    #print(f"FLEET {fleet_diff}")

    # The ladders used to be six literals in this file behind an if/elif chain, with the
    # roster of raiding factions written as a random.choice([...]) beside it - so adding a
    # race meant editing a mission library and no mod could add one at all. They now live
    # in each race_* addon as fleets.yaml and register themselves, gated on NPC_RACES.
    race = (race or "").strip().lower()
    if race in ("", "random"):
        # "random" used to mean a FLAT pick over every registered ladder, with a literal
        # "kralien" behind it - so a mission that set a theater still got an even mix from
        # any path that said "random", and the theater's ladder was quietly bypassed.
        race = fleet_pick_enemy_race() or fleet_table_pick_race() or "kralien"
        race = str(race).strip().lower()
    siege_fleet = fleet_table_get(race, fleet_diff)
    if not siege_fleet:
        # A race with no registered ladder - not in NPC_RACES, or a typo. Say so: the
        # silent alternative is a fleet that spawns nothing and a mission that quietly
        # has no enemies.
        known = ", ".join(fleet_table_races()) or "none"
        print(f"fleet_create: no fleet table for race '{race}' "
              f"(is it in the NPC_RACES setting? registered: {known})")
        return None


    
    num_ships = len(siege_fleet)
#    max_carriers = int(max_carriers)
    fleet_obj = fleet_spawn(Vec3(posx, posy, posz), fleet_roles)

#    ship_key_list = filter_ship_data_by_side(None, race, "ship", True)

    # Allow the script to extend abilities
    script_abilities = get_shared_variable("elite_script_abilities", [])
    #all_abilities = []
    #all_abilities.extend(abilities)
    #all_abilities.extend(engine_abilities)
    #all_abilities.extend(script_abilities)
    all_abilities_copy = elite_get_all_abilities().copy()
    # These are keyed by each ability label's `type:` value, which is a PATH. Spelled
    # with underscores ("elite_cloak", "elite_jump_back") they matched nothing, so only
    # low-vis was ever held back and easy fleets have been cloaking and teleporting away
    # at every difficulty.
    hard = ["elite/cloak", "elite_low_vis", "elite/jump/back"]
    # remove more difficult abilities
    if fleet_diff <5:
        for h in hard:
            all_abilities_copy.pop(h, None)

    # Per-faction (opt-in): put the ships on the RACE's OWN side, hostile to the
    # players, instead of the shared "raider" side. Register the side + relations
    # once here; each ship keeps the "raider" role (compat + combat scope) but its
    # SIDE is the faction, so a ceasefire / multi-faction setup works via diplomacy.
    # Default (faction_side False) keeps the historical shared "raider" side.
    if faction_side:
        side_set_hostile_to_players(race)

#    carrier_count = 0
    for b in range(num_ships):
        # ART ONLY. A fleet ladder names its hulls OUTRIGHT, class by class, so a wave keeps
        # its shape - which means these never reach RACE_ART, the faction-lookup route the
        # basic_enemy/defender prefabs use. They get the key map instead, so a mod can
        # re-point them while the ladder's choices (battleship stays a battleship) survive.
        # No-op unless ART_KEYS is set, and it falls back to the stock key when the
        # replacement is not in the ship table.
        #
        # `roles` below - and therefore the side, and therefore diplomacy - is untouched.
        art_id = art_key_for(siege_fleet[b])
        if faction_side:
            roles = f"{race},{ship_roles}" if ship_roles is not None else f"{race},raider"
        else:
            roles = f"{ship_roles},{race}" if ship_roles is not None else f"raider,{race}"
        
        r_name = name_random_hostile(race)                           #  f"{random.choice(enemy_prefix)} {str(call_signs[enemy_name_number]).zfill(2)}"

        spawn_data = npc_spawn(posx, posy, posz, r_name, roles, art_id, "behav_npcship")
        raider = spawn_data.py_object
        set_inventory_value(raider.id, "my_fleet_id", fleet_obj.id)
        link(fleet_obj.id,"ship_list", raider.id)

        if ship_roles is None:
            ship_roles = ""
        skar_chance = 1 # max(int((10 - fleet_diff)*0.5), 1)
        if "elite" in ship_roles or (race == "skaraan" and random.randint(1,skar_chance) == 1):
            
            add_role(raider.id, "elite")
            max_abi = len(all_abilities_copy)
            abits = random_bits(max_abi, max(1, (fleet_diff+2)//2))  #random.randint(0,pow(2,max_abi))
            # set_inventory_value(raider.id, "elite_abilities", abits)
            # bit field
            # & 0x1 == Cloak  
            # & 0x2 == Jump Back
            # & 0x4 == Jump forward
            # & 0x8 == Jump Back
            for count, ab in enumerate(all_abilities_copy):
                bit = 2**count
                if (abits & bit)  == bit:
                    #
                    # Set the flag in engine for always on 
                    #
                    if elite_is_engine_ability(ab):
                        raider.data_set.set(ab, 1,0)
                    add_role(raider.id, ab)
            


        # Should add a common function to call to get the face based on race
        set_face(raider.id, random_face(race))
    return fleet_obj

