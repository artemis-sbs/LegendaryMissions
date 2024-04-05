# setup.json
A file that can be used to set the default operating settings for Legendary Missions

## auto_start
This will skip startup selection and start the mission as soon as it is selected.

## operator_mode

### enable
set "true" to enable the operator mode. "false" to disable

### logo
You can set an image file to display one the server screen. Useful for operators.

### remote_console_select
For future use

### pin
string needed to be typed to gain access to the operator and startup screen.
The default is 000000


## Default selections
You set the default selection values for the startup settings screen.

### players_count
How many player ships are available foe the missions. Values are 1 to the number of ships in the player ship list.

### difficulty
1-11

### world_select
siege is the only valid selection currently

### terrain_select
none, few, some, lots, many

### lethal_select
none, few, some, lots, many

### friendly_select
none, few, some, lots, many

### monster_select
none, few, some, lots, many

### upgrade_select
none, few, some, lots, many

### game_time_limit
0 is unlimited any other values is the number of minutes the mission will last.
Pausing the mission will also pause this timer.

The remote admin screen can be used to pause the game.

### player_ships
A list of Player ships names, side and hull keys

You could add or reduce the number of options. e.g. Operators may Only want one player ship.

