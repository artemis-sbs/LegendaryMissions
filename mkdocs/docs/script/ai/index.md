# AI in Legendary Missions

There are several areas that need to have NPC Agents to have behavior.

The various npc ships: raiders, friendly, civilian, stations.
As well the npcs in Engineering: damcons, etc.

The AI wi be described in this section.

``` mermaid
stateDiagram-v2
    [*] --> handle_route_spawn
    state route <<choice>>
    handle_route_spawn --> route
        route --> ai_player: if has_role("__player__")
        route --> ai_task_friendly: if has_roles("tsn, friendly")
        route --> spawn_task_station: if has_roles("tsn, station")
        route --> raider_start: if has_role("raider") 
    
```
