# setup.json
A file that can be used to set the default operating settings for Legendary Missions

## AUTO_START
This will skip startup selection and start the mission as soon as it is selected.

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

