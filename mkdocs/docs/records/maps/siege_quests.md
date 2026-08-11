# Siege Quests

## Repel the Siege {#siege-mission}

| Fact | Value |
|---|---|
| At start | active |
| Scope | shared |
| Win | Victory! The starbases held. |

Break the siege on the starbases.

## Break the Siege {#break-siege}

| Fact | Value |
|---|---|
| At start | active |
| Done when | signal siege_won |
| Part of | [Repel the Siege](#siege-mission) |
| Scope | shared |
| Required | true |

Destroy the attacking fleets before they overwhelm the starbases.

## Hold the Starbases {#hold-stations}

| Fact | Value |
|---|---|
| At start | active |
| Part of | [Repel the Siege](#siege-mission) |
| Scope | shared |
| Fatal | true |
| Lose | The starbases have fallen. |
| Fail on signal | `siege_bases_lost` |

Do not let every starbase fall - losing the last one loses the siege.

## Break It in Time {#beat-clock}

| Fact | Value |
|---|---|
| At start | active |
| Part of | [Repel the Siege](#siege-mission) |
| Scope | shared |
| Fatal | true |
| Lose | Time ran out - the siege was not broken. |
| Fail on signal | `siege_time_lost` |

Break the siege before the clock runs out.
