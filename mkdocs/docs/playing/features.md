# Game features

Features that shape a match, whether you're playing or hosting.

## Map size

A **Map Size** option scales the playing field &mdash; from tight knife-fights to
sprawling campaigns. Pick it when you set up the game.

## Repeatable maps and seeds

Terrain is built from phased, keyed seeding, so the **same seed always lays out the
same battlefield** (no surprise spawns inside an asteroid). Each map exposes **seed
options** you can set.

## Shareable game codes, and saved setups

A **game code** captures the exact setup &mdash; map, size, seed, and options &mdash; so
crews can replay an **identical** match. Share the code and everyone gets the same
challenge. It does **not** carry your ship names: those are yours, not part of the match.

The same machinery is also a **saved setup**. On the server screen: build the setup you
want, type a name beside the Presets dropdown, and press the save icon. It is there in
the dropdown afterwards &mdash; including after restarting the mission. Presets are kept
per map, and a *saved* setup does bring your crew's ship names and hulls back with it.

Loading one puts those ships straight on the picker, so helm can still change them and
the change sticks.

If you would rather not press anything, `RESTORE_LAST_SETUP` brings back whatever the
last game started with, automatically. It is off by default; see
[Settings](../hosting/settings.yaml.md#restore_last_setup).

Saved setups live in `data/missions/common_data/game_codes/`, outside the mission folder,
so updating the mission keeps them. A map chooses which options its code carries with a
`GameCode:` list in its metadata; leave that out and it carries everything on the Options
panel, plus the ships.

## The Flight Wing

Pilots have quests of their own. On the flight deck and in the cockpit, the quest
screens list your own quests, the game's, and your side's **Flight Wing** &mdash; the
quests every pilot of your side shares &mdash; rather than the carrier's. Pick a fighter
or a shuttle and its sorties appear under **Available Quests**; accept them right there,
on the flight deck or in the seat.

## Bonus objectives

Optional **bonus objectives** give skilled crews extra goals to chase beyond simply
surviving.

## Quests offered { #side-jobs }

Peacetime's patrol quests &mdash; gunnery drills, hazard rocks, poachers, rescues, tows and
the multi-console arcs &mdash; are no longer tied to one map. A **Quests Offered** option on
the setup panel deals a random hand of them under **Available Quests**:

| Quests Offered | What is offered |
|---|---|
| **none** | nothing |
| **few** | about a quarter of them |
| **some** | about half |
| **max** | all of them |

Each quest waits under Available Quests until somebody **Accepts** it &mdash; select one to
read what it asks and what it pays. Its targets only appear once it is taken on, and from
then on it is on the **Quests** tab.

**A seed deals the same hand.** Set the map's Seed and the same quests come up every time,
so a shared game code gives everyone the same set. Seed 0 deals a fresh hand each game.

Where you will find it:

- **Peacetime Remastered** &mdash; Quests Offered defaults to **some**. It sits beside the
  map's **Quest Size** option: *Quests Offered* picks **which** quests are offered, *Quest
  Size* sets **how big** each one is (how many drones, rocks or hulks it takes).
- **Siege** &mdash; Quests Offered defaults to **none**, so a siege plays as it always has
  until you ask for work between waves. The gunnery hulks are target practice, not part of
  the assault: you do not have to clear them to win.

A host can change either default in [settings.yaml](../hosting/settings.yaml.md#siege_jobs)
(`SIEGE_JOBS`, `PR_SIDE_JOBS`).

## Engineering: wear, tuning and work orders

Systems are no longer just broken or fine. Every room and system on the interior view
now has a **condition** as well as a state, and Engineering can see it and change it.

| Tier | On the grid | Effectiveness |
|---|---|---|
| **Damaged** | crimson | nothing |
| **Worn** | gold | 75% |
| **Nominal** | its own color | 100% |
| **Tuned** | cyan | 110% |

**A damage-control team patches a room; it does not rebuild it.** Anything your teams
repair in flight comes back **worn** &mdash; working, but not what it was. Only a
dockyard repair makes it new. Wear also builds from use: firing a beam wears the beam,
launching a torpedo wears the tube, a hit wears the shield facing that took it, and
everything ages slowly with the clock &mdash; faster at warp than at impulse.

**Tuning is the reward for looking after the ship.** Send a team to a system that is
perfectly healthy and they will bring it *above* spec &mdash; a tuned beam pool fires at
110 percent. Nobody tunes anything on their own initiative: it has to be ordered.

**Giving the order.** Select a room or system on the interior view and open comms on
it. There is one button &mdash; **Repair** or **Tune** &mdash; showing how many teams are
already on the job. It opens a short menu: who to send, who to call off, and raise or
lower the priority. A job raised above the others turns the nearest team around; teams
finish what they were sent to do rather than wandering onto whatever they pass.

**The Engineering panel** on the right of the console has three tabs:

| Tab | Shows |
|---|---|
| **Selected** | The room or team you picked on the interior view, in full. |
| **Orders** | Every work order on the ship, most urgent first, with raise and cancel on each row. |
| **Systems** | The four system pools, and the eight efficiency numbers &mdash; beam, tube, impulse, warp, turn, sensor, and both shield facings &mdash; each colored by how healthy it is. |

The cockpit's system lights show the same tiers.

## The Director console

The **Director** console (formerly Console View) lets you pair and rotate multiple
views, with a **cinematic mode** for the big screen &mdash; great for spectating,
streaming, or running a venue.

## Game results & scorekeeping

The end-of-game screen is a **tabbed results board**, and it keeps score.

**The tabs:**

| Tab | Shows |
|---|---|
| **Summary** | Difficulty, enemies destroyed, tonnage destroyed, damage dealt, surrenders, game time. |
| **Fleet** | Each surviving player bridge ship: kills, tonnage, damage, hull remaining. |
| **Air Wing** | Each fighter/shuttle **pilot by call sign**: sorties, kills, tonnage, objectives. |
| **Quests** | Game and per-ship quests with their final state (secret quests stay hidden). |
| **Enemies** | Ships destroyed, broken down by race. |

**How the score works:**

- **Kills** &mdash; every destroyed enemy is credited to the ship (or pilot) that
  landed the **final blow**.
- **Tonnage** &mdash; flavor "tonnage sunk," scaled by the destroyed hull's size, so
  killing a capital ship is worth far more than a fighter.
- **Damage dealt** &mdash; raw damage, so a crew that softens targets for others
  still shows up on the board.
- Bridge-ship credit and fighter/shuttle (cockpit) credit are tracked separately, so
  the two **never double-count**.

**Saved every game.** Each result is written to a rolling history with an even
denser per-ship / per-pilot / per-quest breakdown than the screen displays.

## Elite enemies, and what Science can see

Some enemies &mdash; Skaraans especially &mdash; carry **elite abilities**. They come in
two kinds, and the difference is what your Science officer can do about them.

**Always on.** Low visibility, main-screen invisibility, drones, anti-mine and
anti-torpedo defenses are part of the ship. Nothing switches them on, so there is
nothing to catch. Science reads them off the **Intel** tab as soon as the contact is
scanned, which is your warning.

**Chosen.** Cloak, warp, and the two teleports have to be decided on and powered up
first, and an elite can only charge one at a time. The moment it commits, its **Status**
tab says so, with a countdown:

> Ready for combat. Preparing to cloak - 18s

That is the window. Call it out, and the bridge gets to act on it &mdash; hold fire for
the cloak, close the range so the teleport is wasted, or kill it before the charge
finishes. Talk it out of the idea &mdash; a Tag torpedo, or simply nothing left worth
using the ability on &mdash; and the line disappears.

The window is **wider on lower difficulty and tighter on higher**: the same cloak that
gives you thirty-five seconds at difficulty 1 gives you fifteen at 11.

**Status is worth reading on any enemy**, elite or not. When nothing is charging it
reports the ship's condition &mdash; a damaged system, a shield facet that is down, or
one visibly coming back up:

> Rebuilding its forward shields.

## Running a tournament

The pieces above combine into a simple, fair competition format &mdash; handy for
**convention operators** and league nights:

1. Set up a match and share its **game code** (map, size, seed, and options), or just
   agree on a **seed** &mdash; every crew now plays the **identical** battlefield and
   enemy layout.
2. Each crew plays the match; the **Fleet** and **Air Wing** boards give you kills,
   tonnage, and damage per ship and per pilot.
3. Rank crews (or individual pilots) by whichever number you're scoring on. The saved
   result gives you the full breakdown after the fact.

Use the **Director** console for a spectator / big-screen view of the action while
crews compete.
