## New Map system post 1.0
This will use a system of grids and tiles.

- galaxy systems pesudo endless grid of 1Mx1M system tiles
    - star tiles
    - planetary tiles

- planetary systems are 100kx100k with 10kx10k tiles
    - map tiles
        - terrain tiles
        - station 

    - ship tiles
        - fleet tiles
        - npc tiles
        - player tiles



### Galaxy level
The galaxy is a grid representing 'tiles' of star systems that are 1Mx1M

## Galaxy tiles
The star system  is 1Mx1M and a planetary system is 100kx100k
making a galaxy tile a 10x10 tile grid

A Galaxy Tile specifies the number of star section tiles . Think of it a as deck of cards with:
    - one-3 stars tiles are star being 500k - 1M in diameter cards
    - 7-15 planetary systems cards
    - with 83 - 93 dead space cards
    - it is not meant to make orbital sense

These cards are 'shuffled' and fill in the grid.
This can be done is a seeded pseudo random fashion so random, but repeatable if desired

It would be nice if the stars where visible in the sky box.
You can not travel to a star it is sure death.

### User defined galaxy tiles

digits specify stars
alpha specifies planetary systems

```
//tile/galaxy/lambda
"..c.......
"..1..a....
"..b.......
"..........
".....d....
"...g..2.e.
"....f.....
".h........
"..3.i.....
"..........

match TILE.code:
    case "a":
        TILE_OBJ.name = "Earth"

--- some_logic
# These are labels and can define logic

```


## A planetary system
A planetary system is 100kx100k or 100 10kx10k grid of 10K orbital system tiles

A orbital system Tile specifies the type of tile to place. 
    - one-4 moon tiles,  moons being 5k - 10k in diameter 
    - one-7 celestial event tiles, black hole etc. 5k - 10k in diameter
    - 7-15 station cards
    - 1-3 FTL tiles JUmp gates and other FTL constructs
    - with 71 - 90 terrain cards, dead space, asteroids, pickups, etc
    - it is not meant to make orbital sense

A star system contains the number of 'planets' and the number of stations and moons around a planet

```
//tile/station/command1 "Command Station" if tile_opts.is_friendly
":aA.A.:...
"A:...:....
".a........
".......p..
"..:mmm:...
"..m.s.m:..
"......:...
":.........
":::.....::
"::::...:::
"s=name:Beachwood Station;artid:starbase_command;side=tsn;

#
# 
#

```

### Scripted tiles

```
//tile/terrain/station "Io"
npc_spawn(...)

```


### Blackhole and moon
Blackhole and moons can be can be scripted 


```
//tile/terrain/black_hole "Black Hole"
#
# Completely scripted tile
#
x = TILE.pos.x
y = TILE.pos.y
z = TILE.pos.z

_prefix = "XEA"

bh_name_number = get_inventory_value(SHARED, "bh_name_number", 0)
r_name = f"{random.choice(_prefix)} {str(call_signs[bh_name_number]).zfill(2)}"
bh_name_number = (enemy_name_number+1)%99
set_inventory_value(SHARED, "bh_name_number", bh_name_number)

bh = to_object(terrain_spawn(x,y,z, r_name, "#,black_hole", "maelstrom", "behav_maelstrom"))
bh.engine_object.exclusion_radius = 100 # event horizon
blob = bh.data_set
blob.set("gravity_radius", gravity_radius, 0)
blob.set("gravity_strength", gravity_strength, 0)
blob.set("turbulence_strength", turbulence_strength, 0)
blob.set("collision_damage", collision_damage, 0)

```



## Fleet tiles
Used for defining fleets
an update to the current tables

```

//tile/fleet if tile_opts.difficulty==5
"..........
"..........
"..........
"....a.....
"...b.b....
"..c.c.c...
"...d.e....
"..........
"..........
"..........
"*side=tsn;
"*artid:tsn_escort;
"a=artid:tsn_destroyer;
"d=name:intrepid;artid:tsn_lightcrusier;
"e=tile=npc/wolf_spider;
#
# * denotes defaults if not specified
#

#
# These are still labels and 
# they run after a tile is spawned 
#
some_value = 5

--- fleet_logic
# this is the brain logic
# Default keeps formation?

jump fleet_logic

```

### NPC tile
Ideal for creating story character NPC

```
//tile/npc/wolf_spider "Wolf Spider"
"npc=name:intrepid;artid:tsn_lightcrusier;
#
# These are still labels and 
# they run after a tile is spawned 
#
some_value = 5

--- story_logic

... etc ...

```