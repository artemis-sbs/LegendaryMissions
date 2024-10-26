from sbs_utils import scatter
import random
from sbs_utils.procedural.ship_data import plain_asteroid_keys
from sbs_utils.procedural.spawn import terrain_spawn, npc_spawn
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.inventory import set_inventory_value

from sbs_utils.scatter import ring as scatter_ring
from sbs_utils.faces import set_face, random_terran
from sbs_utils.vec import Vec3
from monster import typhon_classic_spawn

import math


def terrain_spawn_stations(difficulty, lethal_value, x_min=-32500, x_max=32500, center=None):
    if center is None:
        center = Vec3(0,0,0)

    _station_weights  = {"starbase_industry": 5,"starbase_command": 3,"starbase_civil": 1,"starbase_science": 1}
    # make the list of stations we will create -----------------------------------------------
    station_type_list = []
    total_weight = (12-difficulty) *2

    while total_weight > 0:
        station_type = random.choice(list(_station_weights.keys()))
        station_weight = _station_weights[station_type]

        # Force big stations first
        if total_weight > 8 and station_weight==1:
            continue

        total_weight -= station_weight
        station_type_list.append(station_type)

    pos = Vec3(center)
    startZ = -50000
    num_stations = len(station_type_list)
    station_step = 100000/num_stations

    #print(f"Station Center at: {pos.x} {pos.y} {pos.z}")
    # for each station
    for index in range(num_stations):
        stat_type = station_type_list[index]
        pos.x = center.x + random.uniform(x_min, x_max)
        pos.y = center.y + random.random()*2000-1000
        pos.z = center.z + startZ #+ random.random()*station_step/3  -   station_step/6
    #    _spawned_pos.append(pos)
        startZ += station_step

        #make the station ----------------------------------
        #print(f"Station at: {pos.x} {pos.y} {pos.z} - {startZ} {station_step}")
        name = f"DS {index+1}"
        s_roles = f"tsn, station"
        station_object = npc_spawn(*pos, name, s_roles, stat_type, "behav_station")
        ds = to_id(station_object)
        set_face(ds, random_terran(civilian=True))

        # wrap a minefield around the station ----------------------------
        if lethal_value > 0:
            startAngle = random.randrange(0,359)
            angle = random.randrange(90,170)
            angle = 170
            endAngle = startAngle + angle
            
            
            depth = 1   #random.randrange(2,3)
            width = int(5 * lethal_value)
            widthArray = [int(angle / 5.0)]
            inner = random.randrange(1200,1500)
            cluster_spawn_points = scatter_ring(width, depth, pos.x,pos.y,pos.z, inner, inner, startAngle, endAngle)
            
            # Random type, but same for cluster
            for v2 in cluster_spawn_points:
                #keep value between -500 and 500??
                mine_obj = terrain_spawn( v2.x, v2.y + random.randrange(-300,300), v2.z,None, "#,mine", "danger_1a", "behav_mine")
                mine_obj.blob.set("damage_done", 5)
                mine_obj.blob.set("blast_radius", 1000)
                mine_obj.engine_object.blink_state = -5


def peacetime_spawn_stations(difficulty, lethal_value, x_min=-35000, x_max=35000):
    _station_weights  = {"starbase_industry": 5,"starbase_command": 3,"starbase_civil": 1,"starbase_science": 1}
    # make the list of stations we will create -----------------------------------------------
    station_type_list = []
    total_weight = (12-difficulty) *2

    while total_weight > 0:
        station_type = random.choice(list(_station_weights.keys()))
        station_weight = _station_weights[station_type]

        # Force big stations first
        if total_weight > 8 and station_weight==1:
            continue

        total_weight -= station_weight
        station_type_list.append(station_type)

    while len(station_type_list) < 5:
        station_type_list.append("starbase_civil")

    pos = Vec3()
    startZ = -50000
    num_stations = len(station_type_list)
    station_step = 100000/num_stations


    # for each station
    for index in range(num_stations):
        stat_type = station_type_list[index]
        pos.x = random.uniform(x_min, x_max)
        pos.y = random.random()*2000-1000
        pos.z = startZ + random.random()*station_step/3  -   station_step/6
    #    _spawned_pos.append(pos)
        startZ += station_step

        #make the station ----------------------------------
        name = f"DS {index+1}"
        s_roles = f"tsn, station, ds{index+1}"
        station_object = npc_spawn(*pos, name, s_roles, stat_type, "behav_station")
        ds = to_id(station_object)
        set_face(ds, random_terran(civilian=True))

        # wrap a minefield around the station ----------------------------
        if lethal_value > 0:
            startAngle = random.randrange(0,359)
            angle = random.randrange(90,170)
            angle = 170
            endAngle = startAngle + angle
            
            
            depth = 1   #random.randrange(2,3)
            width = int(5 * lethal_value)
            widthArray = [int(angle / 5.0)]
            inner = random.randrange(1200,1500)
            cluster_spawn_points = scatter_ring(width, depth, pos.x,pos.y,pos.z, inner, inner, startAngle, endAngle)
            
            # Random type, but same for cluster
            for v2 in cluster_spawn_points:
                #keep value between -500 and 500??
                mine_obj = terrain_spawn( v2.x, v2.y + random.randrange(-300,300), v2.z,None, "#,mine", "danger_1a", "behav_mine")
                mine_obj.blob.set("damage_done", 5)
                mine_obj.blob.set("blast_radius", 1000)
                mine_obj.engine_object.blink_state = -5


# make a few random clusters of Asteroids
def terrain_asteroid_clusters(terrain_value, center=None):
    if center is None:
        center = Vec3(0,0,0)

    #t_min = terrain_value * 7
    #t_max = t_min * 3
    t_max_pick = [0,8,10, 12,16]
    t_min = t_max_pick[terrain_value]
    t_max = t_min * 2
    spawn_points = scatter.box(random.randint(t_min,t_max), center.x, center.y, center.z, 100000, 1000, 100000, centered=True)

    asteroid_types = plain_asteroid_keys()
    for v in spawn_points:
        
        amount = random.randint(t_min,t_max)//2
        size = amount *3
        # the more you have give a bit more space
        ax = random.randint(-20,20)
        ay = random.randint(-150,150)
        az = random.randint(-20,20)
        #cluster_spawn_points = scatter_box(amount, v.x, 0,v.z, amount*50, amount*20,amount*200, centered=True, ax, ay, az )
        cluster_spawn_points = scatter.box(amount,  v.x, 0,v.z, size*150, size*50,size*200, True, 0, ay, 0 )

        scatter_pass = 0
        for v2 in cluster_spawn_points:
            a_type = random.choice(asteroid_types)

            asteroid = terrain_spawn(v2.x, v2.y, v2.z,None, "#,asteroid", a_type, "behav_asteroid")
            asteroid.engine_object.steer_yaw = random.uniform(0.0001, 0.003)
            asteroid.engine_object.steer_pitch = -random.uniform(0.0001, 0.003)
            asteroid.engine_object.steer_roll = random.uniform(0.0001, 0.003)

            # Some big, some small
            # big are more spherical
            # 1 in 4 big
            if scatter_pass%4 != 0:
                sx = random.uniform(7.0, 15.0)
                sy = sx + random.uniform(-1.2, 1.2)
                sz = sx + random.uniform(-1.2, 1.2)
                sm = min(sx, sy)
                sm = min(sm, sz)
                er = asteroid.engine_object.exclusion_radius
                er *= sm/2
                asteroid.engine_object.exclusion_radius = er
            else:
                sx = random.uniform(2.5, 5)
                sy = random.uniform(2.5, 5)
                sz = random.uniform(2.5, 5)
                sm = min(sx, sy)
                sm = min(sm, sz)
            scatter_pass += 1
            #er = asteroid.blob.get("exclusionradius",0)
            #er *= sm

            asteroid.blob.set("local_scale_x_coeff", sx)
            asteroid.blob.set("local_scale_y_coeff", sy)
            asteroid.blob.set("local_scale_z_coeff", sz)
            

            # if scatter_pass==0:
            #     continue
            # # else:
            # #     continue

            # #
            # # Sphere od smaller asteroids
            # #
            this_amount = random.randint(7,12)
            little = scatter.box(this_amount,  v2.x, 0,v2.z, amount*150, amount*50,amount*200, True)
            #little = scatter.sphere(random.randint(2,6), v2.x, v2.y, v2.z, 300, 800)
            # little = scatter.sphere(random.randint(12,26), v2.x, v2.y, v2.z, 800)
            
            for v3 in little: 
                a_type = random.choice(asteroid_types)

                asteroid = terrain_spawn(v3.x, v3.y, v3.z,None, "#,asteroid", a_type, "behav_asteroid")
                asteroid.engine_object.steer_yaw = random.uniform(0.0001, 0.003)
                asteroid.engine_object.steer_pitch = -random.uniform(0.0001, 0.003)
                asteroid.engine_object.steer_roll = random.uniform(0.0001, 0.003)
                sx1 = random.uniform(0.3, 1.0)
                sy1 = random.uniform(0.3, 1.0)
                sz1 = random.uniform(0.3, 1.0)
                sm1 = max(sx, sy)
                sm1 = max(sm, sz)
                er = asteroid.engine_object.exclusion_radius
                er *= sm1
                asteroid.engine_object.exclusion_radius = 0
                

                asteroid.blob.set("local_scale_x_coeff", sx1)
                asteroid.blob.set("local_scale_y_coeff", sy1)
                asteroid.blob.set("local_scale_z_coeff", sz1)

def terrain_to_value(dropdown_select, default=0):
    if "few" == dropdown_select:
        return 1

    if "some" == dropdown_select:
        return 2

    if "lots" == dropdown_select:
        return 3

    if "many" == dropdown_select:
        return 4
    return default


def terrain_spawn_nebula_clusters(terrain_value, center=None):
    if center is None:
        center = Vec3(0,0,0)

    t_min = terrain_value * 6
    t_max = t_min * 2
    spawn_points = scatter.box(random.randint(t_min,t_max), center.x, center.y, center.z, 100000, 1000, 100000, centered=True)
    for v in spawn_points:
        cluster_spawn_points = scatter.sphere(random.randint(terrain_value*2,terrain_value*4), v.x, 0,v.z, 1000, 10000, ring=False)
        for v2 in cluster_spawn_points:
            v2.y = v2.y % 500.0
            nebula = terrain_spawn(v2.x, v2.y, v2.z,None, "#, nebula", "nebula", "behav_nebula")
            nebula.blob.set("local_scale_x_coeff", random.uniform(1.0, 5.5))
            nebula.blob.set("local_scale_y_coeff", random.uniform(1.0, 5.5))
            nebula.blob.set("local_scale_z_coeff", random.uniform(1.0, 5.5))

def terrain_spawn_monsters(monster_value, center=None):
    if center is None:
        center = Vec3(0,0,0)

    spawn_points = scatter.box(monster_value, center.x,center.y, center.z, 75000, 1000, 75000, centered=True)
    for v in spawn_points:
        typhon_classic_spawn(*v.xyz)

call_signs = []
enemy_name_number = 0
call_signs.extend(range(1,100))
#print(f"call_signs size = {len(call_signs)}")
random.shuffle(call_signs)


def terrain_spawn_black_hole(x,y,z, gravity_radius= 1500, gravity_strength=1.0, turbulence_strength= 1.0, collision_damage=200):
    global enemy_name_number

    _prefix = "XEA"
    r_name = f"{random.choice(_prefix)} {str(call_signs[enemy_name_number]).zfill(2)}"
    enemy_name_number = (enemy_name_number+1)%99

    bh = to_object(terrain_spawn(x,y,z, r_name, "#,black_hole", "maelstrom", "behav_maelstrom"))
    bh.engine_object.exclusion_radius = 100 # event horizon
    blob = bh.data_set
    blob.set("gravity_radius", gravity_radius, 0)
    blob.set("gravity_strength", gravity_strength, 0)
    blob.set("turbulence_strength", turbulence_strength, 0)
    blob.set("collision_damage", collision_damage, 0)
    # Note this returns the object, not spawn data. SpawnData is deprecated 
    return bh


def terrain_spawn_black_holes(lethal_value, center=None):
    if center is None:
        center = Vec3(0,0,0)

    spawn_points = scatter.box(lethal_value, center.x,center.y, center.z, 75000, 500, 75000, centered=True)
    for v in spawn_points:
        terrain_spawn_black_hole(*v.xyz)


"""

def terrain_spawn_stations_old(difficulty, lethal_value):
    _station_weights  = {"starbase_command": 3,"starbase_civil": 1,"starbase_industry": 5,"starbase_science": 1}

    spawn_points = scatter.box(10000, 0,0,0, 65000, 1000, 65000, centered=True)
    num = 1
    total_weight = (12-difficulty) *2
    _spawned_pos = []

    for station in spawn_points:
        #
        # Pick a type of station
        #
        if total_weight <= 0:
            break

        station_type = random.choice(list(_station_weights.keys()))
        station_weight = _station_weights[station_type]
        #
        #
        if total_weight < station_weight:
            continue

        # Force big stations first
        if total_weight > 8 and station_weight==1:
            continue

        total_weight -= station_weight

        name = f"DS {num}"
        #
        # Space stations
        #
        _pos = station
        dist = 15000 * 15000
        move = True
        while move:
            move = False
            for _prev in _spawned_pos:
                distv = _pos - _prev
                _dist_test = distv.dot(distv)
                if _dist_test < dist:
                    move = True
                    #print("Move Station")
                    _pos = next(spawn_points)
                    break
        _spawned_pos.append(_pos)

        station_object = npc_spawn(*_pos, name, "tsn, station", station_type, "behav_station")
        #
        #
        
        
        ds = to_id(station_object)
        #
        #
        #
        apos = station_object.engine_object.pos
        #
        # Make sure not too close
        #

        set_face(ds, random_terran(civilian=True))

        #wrap a minefield around the station
        if lethal_value > 0:
            startAngle = random.randrange(0,359)
            angle = random.randrange(90,170)
            endAngle = startAngle + angle

            depth = 1#random.randrange(2,3)
    #        width = random.randrange(int(angle/6), int(angle/3))
            width = int(5 * lethal_value)
            widthArray = [int(angle / 5.0)]
            inner = random.randrange(1200,1500)
            cluster_spawn_points = scatter_ring(width, depth, apos.x,apos.y,apos.z, inner, inner, startAngle, endAngle)
    #        cluster_spawn_points = scatter_ring_density(widthArray, apos.x,apos.y,apos.z, inner, 0, startAngle, endAngle)
            # Random type, but same for cluster
            # a_type = f"danger_{1}{ship_data'a'}"
            for v2 in cluster_spawn_points:
                #keep value between -500 and 500??
        #                v2.y = abs(v2.y) % 500 * (v2.y/abs(v2.y))
                mine_obj = terrain_spawn( v2.x, v2.y + random.randrange(-300,300), v2.z,None, None, "danger_1a", "behav_mine")
                mine_obj.blob.set("damage_done", 5)
                mine_obj.blob.set("blast_radius", 1000)
                mine_obj.engine_object.blink_state = -5

        num += 1
"""