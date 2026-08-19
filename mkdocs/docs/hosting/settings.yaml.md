# settings.yaml

A file that can be used to set the default operating settings for Legendary Missions

!!! tip "setup.json"

    In versions prior to 1.1.x the setup.json file was used.
    setup.json is deprecated but still also looked for after settings.yaml


## AUTO_START
This will skip startup selection and start the mission as soon as it is selected.
When set, the game-results screen also auto-restarts the mission after a delay
(see AUTO_START_DELAY), so the mission loops unattended.

## AUTO_START_DELAY
Seconds to wait on the game-results screen before AUTO_START restarts the mission.
Defaults to 10. Measured in real (wall-clock) time, because the simulation is
paused at game end.

## RESTORE_LAST_SETUP
Come back on the setup screen with the settings the **last game started with**, instead of
the defaults below. Remembered per mission and per map, and it carries the crew's ship
names and hulls as well as the options.

Defaults to `false`, which is the behavior LegendaryMissions has always had: every game
starts from this file. That suits a venue or a convention, where each group should start
from the same known state. Set it to `true` when the same crew keeps replaying a setup -
after an early death, or while tuning one option at a time.

``` yaml
    RESTORE_LAST_SETUP: true
```

It is saved when a game **starts**, not when it ends, so a crash or a quit still leaves it
recorded. The file is `data/missions/common_data/game_codes/<mission>.yaml`, outside the
mission folder, so updating the mission does not lose it.

Prefer a **[profile](profiles.md)** when you have several standing setups rather than one
rolling one, and a **saved preset** when you want to name a setup and come back to it
later.

## OPERATOR_MODE

### enable
set "true" to enable the operator mode. "false" to disable

### logo
You can set an image file to display one the server screen. Useful for operators.

### show_logo_on_main
Set this to show the operator  logo on the server instead of the star options.
Start options will be in the admin console.

### pin
string needed to be typed to gain access to the operator and startup screen.
The default is 000000

# SHIP_PICK_READ_ONLY
Set true to disable helms ability to change ship values.
Set false (default) allows helm to change the ship properties.

# CAN_CHANGE_CONSOLE
Set true (default) to allow clients access to ship change console
Set to false will not allow clients change consoles


## Default selections
You set the default selection values for the startup settings screen.

### players_count
How many player ships are available foe the missions. Values are 1 to the number of ships in the player ship list.

### DIFFICULTY
1-11

### WORLD_SELECT
siege is the only valid selection currently

### TERRAIN_SELECT
none, few, some, lots, many

### LETHAL_SELECT
none, few, some, lots, many

### FRIENDLY_SELECT
none, few, some, lots, many

### MONSTER_SELECT
none, few, some, lots, many

### UPGRADE_SELECT
none, few, some, lots, many

### GAME_TIME_LIMIT
0 is unlimited any other values is the number of minutes the mission will last.
Pausing the mission will also pause this timer.

The remote admin screen can be used to pause the game.

### player_ships
A list of Player ships names, side and hull keys

You could add or reduce the number of options. e.g. Operators may Only want one player ship.

