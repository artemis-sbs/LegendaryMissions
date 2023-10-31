# BasicSiegeMast
A Basic Siege written in the Mast (Multi-agent story telling) language



DONE: Docking - add damcons regen.
DONE: Mines won't load when ship docks.
DONE: No info on how long to produce homing/nuke/mine/etc.

ADDED: Repair Damaged rooms when Docked 
ADDED: Main screen console option
ADDED: random skybox
ADDED: is_dev_build() to fs. 
ADDED: Debug screen tab if is_dev_build
ADDED: pickup_spawn function (upgrade.py)
ADDED: add friendly to "eyes"

INPROG: Currently a bug/feature: can fire while docked.
INPROG: Currently a bug/feature: can still dock if enemies are nearby.


Munitions production takes too long



General/Upgrades:

Upgrade button supposed to change to console name, sometimes doesn't
change "upgrade"

After ship is destroyed, sometimes beams and shields are "stuck" on
regenerated ship.

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
Needs bigger/more obvious selection box on grid map.
"Crew is hungry" messages were distracting during combat, turn off for
Red Alert?

Comms:
Needs a "hostile" or "enemy ship" grouping.
Maybe add "nearest" grouping to show closest targets?
Change text color for different groups:
 - Same ship (internal) should be light blue/grey
 - Friendly ships should be green
 - Stations should be... different green/blue?
 - Enemy threats/responses should be red
 - Surrender messages yellow, etc.