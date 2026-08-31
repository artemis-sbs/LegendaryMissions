# Items & upgrades

Crates drift in the debris of every map. Some are cargo worth money, some are a
five-minute edge in a fight, and one or two change what your ship is good at for the
rest of the game.

## Getting hold of them

- **Find them.** Pickups scatter through the map. Fly into one and it is aboard &mdash;
  Weapons can also **Grav Reel** one in from a distance rather than chasing it.
- **Take them off the dead.** Destroyed hostiles drop trade goods; wrecks and dead
  space creatures leave Salvage and Bio Samples.
- **Buy them.** Hail any friendly station and pick **Market**. Prices move from station
  to station &mdash; a place that produces something sells it cheap and buys it back for
  little, so there is money in carrying cargo somewhere that wants it.
- **Build them.** The Fabricator turns Salvage into gear. See
  [Fabrication & Beacons](../addons/fabrication.md).

## Using one

Everything you are carrying is on the **Upgrades** tab, on every console &mdash; including
the things you have *not* found yet, so you can read what a crate does before you go
looking for one.

Two rules worth knowing. Most upgrades name **which console** may fire them, and the tab
tells you when you are at the wrong one. And while an upgrade is running, its tile shows
a countdown instead of a button &mdash; you cannot stack a second one on top of it.

## Ship upgrades

Each is a one-shot: it is spent when used and runs for the time shown.

| Upgrade | What it does | Lasts | Console | ~Price |
|---|---|---|---|---|
| **Carapaction Coil** | Shields x3 | 5 min | Weapons, Engineering | 250 |
| **Infusion P-Coils** | Impulse and turn x3 | 5 min | Helm | 250 |
| **Tauron Focuser** | Beams and tubes x2 | 5 min | Weapons | 250 |
| **Haplix Overcharger** | Beams x3 | 5 min | Engineering, Weapons | 400 |
| **Cetrocite Crystal** | System cooling x2 | 5 min | Engineering | 250 |
| **Lateral Array** | Sensors x2 | 5 min | Science | 250 |
| **Vigoranium Nodule** | Restores your damage-control teams | instant | Engineering | 250 |
| **HiDens Power Cell** | +500 energy, the moment you touch it | instant | any | 150 |
| **Secret Codecase** | Arms a one-shot enemy auto-surrender, played from Comms | 5 min | Comms | 400 |

## Tug rigs

Towing something heavier than you is slow, drinks your reserves, and on a starbase is
frankly a job for more than one ship. A tug rig makes your hull count for more on the
beam &mdash; the load comes in faster, costs you less speed, and the strain readout drops a
notch.

| Rig | Worth | Lasts | Where |
|---|---|---|---|
| **Heavy Tug Rig** | four ships' pull | permanent | **bought** at a station, ~600 |
| **Tug Rig Mk I** | two and a half ships' pull | 10 minutes | **found** in the world |

The Heavy rig is fitted once and stays fitted &mdash; the crate is used up in the fitting,
so there is nothing left in the hold to sell. The Mk I is an old unit that burns itself
out; it is worth saving for the delivery rather than the trip out to it.

**They stack.** A ship with the Heavy rig still gets the full benefit of a Mk I on top,
so a rig you find is never wasted.

Neither changes what your ship *weighs*, so fitting one will not make you harder for
somebody else to grab, and will not make your own wreck worth more.

!!! tip "Bring a friend before you bring a rig"
    Every ship on the same beam pulls harder **and** takes a share of the power bill. A
    rig makes the haul quicker; a second ship makes it *last*, which on a station is
    usually what stops you. Weapons shows the crew count as **TOW &times;2**, **&times;3**,
    and the beam says so outright when it is overloaded.

## Cargo & materials

Not upgrades &mdash; these are what you sell, and what the Fabricator eats.

| Cargo | Notes | ~Price |
|---|---|---|
| **Contraband** | Illicit. Lucrative where there is demand | 200 |
| **Tech Components** | High-value trade good | 120 |
| **Volatile Gas** | Compressed industrial gas | 60 |
| **Bio Sample** | From a dead space creature; programs a Bio Beacon | 60 |
| **Raw Ore** | Bulk commodity | 40 |
| **Provisions** | Food and supplies. Always wanted somewhere | 30 |
| **Salvage** | Hull plate, wiring, parts. The Fabricator's raw material | 20 |

Salvage arrives in caches rather than one crate per unit, and there is a second way to
earn it: tow a derelict home and a friendly station pays out by its mass.

## Turret kits

Bought at a station, ejected as a crate, **towed into position** with the grav-tether and
unfolded where you want it.

| Kit | Notes | ~Price |
|---|---|---|
| **Beam Turret Kit** | A beam emplacement | 450 |
| **Heavy Turret Kit** | Longer reach, harder hitting, slower | 900 |
| **Drone Turret Kit** | Launches attack drones on its own | 900 |

## Carried, not used

- **Escape Pod** &mdash; a life-support capsule. Carry it home and dock to deliver whoever
  is inside. It never appears as an upgrade because there is nothing to activate.
- **Hacking Virus** &mdash; a trap, not a prize. Whoever trips it takes weapons and engine
  damage.

## Fighter fits

Hangar craft carry their own fits &mdash; **Cockpit Shields**, a **Torpedo Bay** and a
**Torpedo Autoloader** &mdash; applied to the craft when it launches rather than picked up
in space. See the [hangar](../addons/index.md).

---

Prices above are the base; what a station actually charges depends on how badly it wants
the thing. Everything here is defined in the mission's `items` add-on, so a mod can add
to it &mdash; see [Adding an item or upgrade](https://artemis-sbs.github.io/sbs_utils/build/custom-upgrades/).
