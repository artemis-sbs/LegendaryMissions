# Legendary  issions
A Missions from Artemis Space Ship Bridge simulator reeimagined for Artemis: Cosmos.

Written written using MAST (Multi-agent story telling).

Mast is a runtime written in python. It can be used via python. MAST also includes the MAST Language a python like language that simplifies the writing of mission scripts. Python and the MAST Language can be used together to create Mission script for Artemis: Cosmos.

---------------




``` py
//mission/deliver "Deliver Munitions" if has_role(SPAWNED_ID, "tsn, fighter")
" Pick up {torp_type} torpedoes at {station.name} and deliver them to {player.name}

init:
    " This is called when the mission is created 
    " Data created here can be used in the mission description text

    station = to_object(random.choice(role("tsn, station")))
    player = to_object(random.choice(role("tsn, __player__")))
    fighter = to_object(SPAWNED_ID)
    torp_type = random.choice(get_torp_types_for(player.id))

start:
    set_timer("pickup_bonus", minute=4)
    set_timer("deliver_bonus", minute=8)

abort:
    yield fail if not player.exists
    yield fail if not station.exists
    yield fail if not fighter.exists and not fighter.standby

complete:
    yield fail if not objectives_complete("deliver")
    fighter["XP"] += 100
    if objectives_complete("deliver/bonus"):
        fighter["XP"] += 50
    if objectives_complete("pickup/bonus"):
        fighter["XP"] += 50

objective/pickup "Pickup the stuff" :
    " Pick up the {torp_type} from {station.name}

    yield success if objectives_complete("pickup")
    dist = sbs.distance_id(fighter.id, station.id)
    yield fail if dist > 1000
    yield fail if not is_docked(fighter, station)
    yield success

objective/pickup/bonus "Pickup in 4 minutes":
    yield fail if objectives_complete("pickup")
    yield success if objectives_complete("pickup/bonus")
    yield success if not is_timer_complete("pickup_bonus")
    yield fail


objective/deliver "Deliver the stuff":
    " Deliver the {torp_type} to {player.name}
    
    yield success if objectives_complete("deliver")
    yield fail if not objectives_complete("pickup")

    dist = sbs.distance_id(player.id, station.id)
    yield fail if dist > 1000
    # is_docked doesn't exists but could
    yield fail if is_docked(fighter, player)
    yield success

objective/deliver/bonus "Deliver in 8 minutes":
    yield success if objectives_complete("deliver/bonus")
    yield fail if not objectives_complete("deliver")
    yield success if not is_timer_complete("deliver_bonus")
    yield fail



```