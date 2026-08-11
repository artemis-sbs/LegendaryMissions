# Siege Quests

## Repel the Siege {#siege-mission}

| Fact | Value |
|---|---|
| Scope | shared |
| State | active |
| Win | Victory! The starbases held. |

Break the siege on the starbases.

## Break the Siege {#break-siege}

| Fact | Value |
|---|---|
| Scope | shared |
| State | active |
| Parent | siege_mission |
| Required | true |
| Done when | signal siege_won |

Destroy the attacking fleets before they overwhelm the starbases.

## Hold the Starbases {#hold-stations}

| Fact | Value |
|---|---|
| Scope | shared |
| State | active |
| Parent | siege_mission |
| Critical | true |
| Fail on signal | siege_bases_lost |
| Lose | The starbases have fallen. |

Do not let every starbase fall - losing the last one loses the siege.

## Break It in Time {#beat-clock}

| Fact | Value |
|---|---|
| Scope | shared |
| State | active |
| Parent | siege_mission |
| Critical | true |
| Fail on signal | siege_time_lost |
| Lose | Time ran out - the siege was not broken. |

Break the siege before the clock runs out.
