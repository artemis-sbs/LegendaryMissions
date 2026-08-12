# Fabricator Recipes {: #recipes}

Recipes for the Fabricator, authored as data. One heading per recipe. The Engineering Fabricate tab lists these; a build consumes the Inputs and, after Time seconds, yields the Output. Beacon recipes (Output: Beacon) also carry a Program (kind) and take a monster + attract/repel chosen at build time; non-beacon recipes just produce their Output into the ship inventory.

## Bio Beacon {: #recipes-recipe-beacon-bio}

| Fact | Value |
|---|---|
| Output | Beacon |
| Inputs | bio_sample x1, salvage x5 |
| Time | 30 |
| Build at | engineering |
| Program | kind=bio |
| Properties | Monster: 'gui_drop_down("list: shark, dragon, piranha, leech, charybdis, grazer, any", var="monster")' Mode: 'gui_drop_down("list: attract, repel", var="mode")' |
| Defaults | monster: shark mode: attract |

A distress-beacon hull rewired to broadcast an ultrawave carrier that attracts or repels a chosen space monster across the sector.

## Sensor Beacon {: #recipes-recipe-beacon-sensor}

| Fact | Value |
|---|---|
| Output | Beacon |
| Inputs | salvage x8 |
| Time | 20 |
| Build at | engineering |
| Program | kind=sensor, range=medium |

A passive relay that brightens sensor returns around its position - a future kind; drops and scans like any beacon. The standard (medium-range) build. Replaces the 2.8 Probe.

## Sensor Beacon (Long Range) {: #recipes-recipe-beacon-sensor-long}

| Fact | Value |
|---|---|
| Output | Beacon |
| Inputs | salvage x16 |
| Time | 30 |
| Build at | engineering |
| Program | kind=sensor, range=long |

A wider-reaching sensor relay: greater range costs more materials (2x salvage) and build time. The beacon's program carries range=long for the sensor sweep to read.

## Coolant Cell {: #recipes-recipe-coolant-cell}

| Fact | Value |
|---|---|
| Output | coolant_cell |
| Inputs | salvage x4 |
| Time | 15 |
| Build at | engineering |

A general (non-beacon) example: fabricates a spare coolant cell into the ship inventory, proving the Fabricator builds more than beacons.
