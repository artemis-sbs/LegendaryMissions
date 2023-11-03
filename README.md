# BasicSiegeMast
A Basic Siege written in the Mast (Multi-agent story telling) language



DONE: Docking - add damcons regen.
DONE: Mines won't load when ship docks.
DONE: No info on how long to produce homing/nuke/mine/etc.
DONE: Needs bigger/more obvious selection box on grid map. (now alpha blended yellow square)
DONE: Munitions production takes too long
DONE: Currently a bug/feature: can still dock if enemies are nearby.
DONE: "Crew is hungry" messages were distracting during combat, 
    INPROG: turn off forRed Alert?

ADDED: Repair Damaged rooms when Docked 
ADDED: Main screen console option
ADDED: random skybox
ADDED: is_dev_build() to fs. 
ADDED: Debug screen tab if is_dev_build
ADDED: pickup_spawn function (upgrade.py)
ADDED: add friendly to "eyes"
ADDED: More terrain and Terrain uses the None, Few, Some, Lots, Many
ADDED: Spawn variants of station, uses a weighting system to spawn balanced
ADDED: Spread out station and terrain to fill space better


INPROG: Currently a bug/feature: can fire while docked.
  Still true, but without lock so waste torps


Proximity autoscan - is this coded? (Is the distance hard coded?)





Upgrade button supposed to change to console name, sometimes doesn't
change "upgrade"

Destroyed ships should sometimes drop upgrades (certain upgrades

should be more common with certain races)
 - Arvonian: Lateral Array, Carapaction Coil, Infusion P-Coils (fighter only)
 - Kralien: Lateral Array, Cetrocite Crystal
 - Skaraan: Any (equal %)
 - Torgoth: Carapaction Coil, Haplix Overcharger, Cetrocite Crystal
 - Ximni: Tauron Focuser, Infusion P-Coil, HiDens


Science:
Upgrades - Add science scanning, and change icon to "unknown/generic"
when unscanned.

Proximity autoscan - is this coded? (Is the distance hard coded?)



Engineering:


Comms:
Needs a "hostile" or "enemy ship" grouping.
Maybe add "nearest" grouping to show closest targets?
Change text color for different groups:
 - Same ship (internal) should be light blue/grey
 - Friendly ships should be green
 - Stations should be... different green/blue?
 - Enemy threats/responses should be red
 - Surrender messages yellow, etc.