# Races

## Kralien {: #kralien}

| Fact | Value |
|---|---|
| Station prefix | KB |
| Faces | kralien |
| Call sign | KLMNQ |

The Kralien Union. The most numerous raiders, and the low-difficulty enemy the stock siege ladder nominates - it is the race that sits at 85% at difficulty 1 and falls to 10% at 11.

## Torgoth {: #torgoth}

| Fact | Value |
|---|---|
| Station prefix | TB |
| Faces | torgoth |
| Call sign | KLMNQ |

Torgoth heavies. Xenophobic, and less likely to surrender to what they read as an inferior race.

## Arvonian {: #arvonian}

| Fact | Value |
|---|---|
| Station prefix | AB |
| Faces | arvonian |
| Call sign | KLMNQ |

Arvonian carriers. Their nobility prides itself on honor and detests cowardice.

## Skaraan {: #skaraan}

| Fact | Value |
|---|---|
| Station prefix | SB |
| Faces | skaraan |
| Call sign | TR |

Skaraan elites - independent contractors who operate better alone, which is why the maps spawn them separately from the raiding fleets. \`TR\` call signs are theirs alone and were the one race \`name_random_hostile\` had ever heard of.

## Ximni {: #ximni}

| Fact | Value |
|---|---|
| Faces | ximni |
| Call sign | KLMNQ |
| Fleet scale | 2 |

No Station Prefix and no station hull: the Ximni have no starbase in shipData at all, which is the real reason borderwar and deepstrike list three races where the other maps list four. \`race_has_station\` is now what those maps ask, so this is a fact about the Ximni rather than a shortened literal in two map files.

Fleet Scale doubles their fleet count. singlefront and doublefront both carried \`if enemy == "Ximni": fleet_count = fleet_count\*2\` with the comment "Ximni fleets are typically only one ship" - a fact about the race, stated once here instead of twice there.

## Pirate {: #pirate}

| Fact | Value |
|---|---|
| Faces | pirate |
| Call sign | KLMNQ |

Pirates. Like the Ximni, no starbase hull, so they are excluded from the station maps by the same derived filter rather than by being left out of a list.

## Biomech {: #biomech}

| Fact | Value |
|---|---|
| Faces | terran |
| Call sign | KLMNQ |

Biomechs have hulls and interiors but no fleet ladder, so \`race_npc_list\` leaves them out of the raiding roster on its own. Listed here so the record is complete, and given terran faces because they have no portraits of their own - the fallback \`random_face\` would reach anyway, stated rather than left to chance.

## Terran {: #terran}

| Fact | Value |
|---|---|
| Station prefix | TSN |
| Faces | terran |

The players' own race. Never a raider - it has no fleet ladder - but it IS an origin in the ship table, so it appears in \`race_list()\` and wants a sane face race like any other.
