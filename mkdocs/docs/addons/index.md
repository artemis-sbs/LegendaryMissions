# Addon reference

LegendaryMissions is both a set of playable missions **and** a library of reusable
**addons** you can load into your own mission. Each addon is a `.mastlib` you list
in your mission's `story.json`; it registers labels, comms trees, consoles, and
prefabs into the global namespace.

> New to mission scripting? The language, GUI/comms/science/AI recipes, and the
> API live in the [sbs_utils documentation](https://artemis-sbs.github.io/sbs_utils/).
> This section is specifically about what the LegendaryMissions addons provide.

## Loading addons

```json
{
    "sbslib": ["artemis-sbs.sbs_utils.v1.4.0.sbslib"],
    "mastlib": [
        "artemis-sbs.LegendaryMissions.consoles.v1.4.0.mastlib",
        "artemis-sbs.LegendaryMissions.fleets.v1.4.0.mastlib",
        "artemis-sbs.LegendaryMissions.docking.v1.4.0.mastlib",
        "artemis-sbs.LegendaryMissions.comms.v1.4.0.mastlib",
        "artemis-sbs.LegendaryMissions.prefabs.v1.4.0.mastlib",
        "artemis-sbs.LegendaryMissions.damage.v1.4.0.mastlib"
    ]
}
```

Load only the addons you use &mdash; each one adds labels to the global namespace.

## The addons

| Addon | Provides |
|---|---|
| `fleets` | `spawn_players`, enemy fleet prefabs (`prefab_fleet_raider`, ...) |
| `docking` | player/station docking logic (`docking_standard_player_station`) |
| `prefabs` | sides (`prefab_side_generic`), station/terrain prefabs |
| `comms` | enemy taunt/surrender comms, player comms menus |
| `ai` | brain behaviors (chase, patrol, station, civilian) |
| `consoles` | standard helm/weapons/science/engineering/comms/main-screen consoles |
| `damage` | destroy handlers for ships/stations, wrecks |
| `upgrades` | pickup/upgrade collection handlers |
| `science_scans` | science scan response handlers |
| `gamemaster` / `gamemaster_comms` | GM console + spawn/message/map tools |
| `hangar` | landing bay, bar, hangar comms, sorties |
| `biomech` | [BioMech](biomech.md) creatures — a passive/collective/evolving swarm |
| `avatar_editor` | [Avatar Editor](avatar.md) — in-game WYSIWYG face customizer |
| `internal_comms` | crew department comms (sickbay, security, ...) |
| `operator` | operator/admin console for venue use |
| `side_missions` | structured optional objectives |

**A standard multi-console combat mission** typically loads: `fleets`, `docking`,
`prefabs`, `comms`, `consoles`, `damage`.

## Minimum without LegendaryMissions

A mission can also skip LegendaryMissions entirely and route consoles, spawn
players, and build GUI itself &mdash; see the
[sbs_utils cookbook](https://artemis-sbs.github.io/sbs_utils/build/).
