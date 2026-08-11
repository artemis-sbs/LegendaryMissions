# Ragnarok {#ragnarok}

| Fact | Value |
|---|---|
| Trigger | enemies_low |
| Low | 30% |
| Flies | pirate |
| Fleets | 3 |
| Difficulty | +2 |
| Named | Ragnarok tsn_juggernaut, XORN tsn_light_cruiser |

The 42 Fleet warps in under the renegade Admiral Ragnarok - a Terran juggernaut and its honor guard.

## Defeat Ragnarok {#ragnarok-defeat-ragnarok}

| Fact | Value |
|---|---|
| At start | active |
| Done when | signal siege_won |
| Part of | `siege_mission` |
| Scope | shared |
| Reward | 800 credits |
| Required | true |

Destroy the juggernaut Ragnarok to break the 42 Fleet.

## Turn Xorn {#ragnarok-turn-xorn}

| Fact | Value |
|---|---|
| At start | active |
| Done when | signal xorn_defected |
| Part of | `siege_mission` |
| Scope | shared |
| Reward | 400 credits |

Hail the light cruiser XORN and appeal to their honor - convince them to turn on Ragnarok.
