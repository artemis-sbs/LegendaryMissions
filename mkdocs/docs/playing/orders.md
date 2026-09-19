# Giving orders

Comms can command anything on your side, or on a side you are allied with: warships,
freighters, turrets and starbases. What you can tell a unit to do depends on what it
**can** do. A freighter can be sent somewhere but not into a fight, a turret can pick a
target but not move, and a starbase commands its fighter wings.

## How to give an order

- **Right-click** a friendly unit on the comms map to get its menu. Right-click the unit
  itself for orders about itself (Full Stop, Hold fire...), or right-click something else
  with the unit selected for orders about that thing (Attack it, Escort it...).
- **Drag** a friendly unit onto its target: a hostile, an ally or a marker. Comms opens
  with only the orders that make sense for that pair.

The **Can order** chip at the top of the comms map filters the view to everything you can
currently give an order to.

## The orders

| Order | Given to | Aimed at | What it does |
|---|---|---|---|
| Head to location | anything that moves | anything | flies there and stops |
| Attack | armed ships | a hostile | hunts it down |
| Guard | anything that moves | an ally or a marker | holds near it and engages hostiles that come close |
| Escort | anything that moves | an ally | stays with it and fights off anything that gets near |
| Patrol | anything that moves | a marker | flies back and forth between where it is and the marker, engaging on the way |
| Guard here | anything that moves | itself | holds its current position and engages what comes near |
| Investigate | anything that moves | any contact | flies out and scans it for your side, then reports |
| Return to base | anything that moves | itself | heads to the nearest friendly station and recharges its shields there |
| Retreat | anything that moves | itself | breaks off, holds fire and gets clear of the nearest threats |
| Full Stop | anything that moves | itself | stops where it is |
| Fire on | anything armed, including turrets | a hostile | holds position and shoots that target |
| Hold fire / Weapons free | anything armed | itself | stops or resumes choosing its own targets. A Fire on order still stands during Hold fire |

A ship marked by the mission as having somewhere to be (a story ship) takes no orders.

## Markers: pointing at a place

The comms map cannot pick an empty point in space, so science names places instead.
**Right-click empty space on the science map** and choose *Drop marker Alpha*; the next
one is Bravo, then Charlie. Each side has its own set, and every marker is already
scanned for your side so comms can use it straight away. Right-click a marker to remove
it, or clear them all.

Then aim orders at the marker like any other contact: drag a ship onto *Bravo* to send
it there, Guard it, or Patrol to it.

The **Markers** chip on the comms map shows every named marker in view.

## Starbase fighter wings

A starbase with hangar bays holds **wings** of AI fighters, named Red, Gold, Blue... Each
wing is ordered on its own from the starbase's menu:

| While the wing is... | You can order |
|---|---|
| in the bay, ready | **Launch Red wing (4/4)** at a hostile, or **Launch Red wing to protect** an ally or a marker |
| out flying | **Reassign Red wing (2 out)** onto a new target, or **Recall Red wing** |

The numbers show what the wing has left. **Losses are permanent**: a fighter shot down is
gone, and a wing that has lost every fighter disappears from the menu.

- **Bingo fuel.** Fighters launch with a few minutes of fuel. When it runs out they head
  home on their own, whatever they were doing, and a Reassign leaves them alone.
- **Refit.** A fighter that lands spends a minute refueling and rearming before it is
  ready to launch again.
- **Scan a station** and the *hangar* tab shows each wing: ready, out, refitting and lost for
  your own side and allies. An **enemy** base only gives an estimate - "Red wing: under
  strength, airborne", "Gold wing: destroyed" - so you know it is weakened, not exactly
  when its next wing is ready.

### Starbases that run themselves

A starbase whose side has no crew runs its own wings: it launches at hostiles that come
near, keeps one wing home as a reserve until the station itself is hit, covers allies
under threat, and recalls its fighters when the area is clear. **Enemy bases do this
too.**

On your own side you can hand a station to its AI with **Act on your own**, and take it
back with **Await orders**. Any wing order from a bridge also takes it back.

### What each base carries

Enemy maps build a mix of base kinds for whichever race you are fighting. The smaller
kinds draw as smaller copies of the race's base when the host has extra ship data turned
on.

| Kind | Fighter wings |
|---|---|
| Command | Red 4, Gold 4 |
| Industrial | Red 4 |
| Science | Red 2 |
| Civil | none |

Friendly Terran starbases carry wings from their own hangar bays: Command and Industrial
two wings of 4, Science one wing of 4, Civilian none.

## Turrets

Deployable defense turrets are back where the host's install supports them. They only work
when **EXTRA_SHIP_DATA** is on in the mission's settings or profile, because their hulls
come from the mission's own ship data. Without it they are switched off and no turret, kit
or turret job appears. Once deployed, a turret takes Fire on and Hold fire from comms.
