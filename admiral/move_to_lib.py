from sbs_utils import scatter
import random
from sbs_utils.procedural.ship_data import plain_asteroid_keys
from sbs_utils.procedural.spawn import terrain_spawn


def map_asteroid_scatter(t_min, t_max, x,y,z, w,h, d):

    spawn_points = scatter.box(random.randint(t_min,t_max), x,y,z, w, h, d, centered=True)

    asteroid_types = plain_asteroid_keys()
    for v in spawn_points:
        
        amount = random.randint(t_min+10,t_max+10)
        # the more you have give a bit more space
        ax = random.randint(-20,20)
        ay = random.randint(-150,150)
        az = random.randint(-20,20)
        #cluster_spawn_points = scatter_box(amount, v.x, 0,v.z, amount*50, amount*20,amount*200, centered=True, ax, ay, az )
        cluster_spawn_points = scatter.box(amount,  v.x, 0,v.z, amount*50, amount*5,amount*200, True, 0, ay, 0 )

        for v2 in cluster_spawn_points:
            a_type = random.choice(asteroid_types)

            asteroid = terrain_spawn(v2.x, v2.y, v2.z,None, "#,asteroid", a_type, "behav_asteroid")
            asteroid.engine_object.steer_yaw = random.uniform(0.0001, 0.003)
            asteroid.engine_object.steer_pitch = -random.uniform(0.0001, 0.003)
            asteroid.engine_object.steer_roll = random.uniform(0.0001, 0.003)

            sx = random.uniform(0.8, 3.5)
            sy = random.uniform(0.8, 3.5)
            sz = random.uniform(0.8, 3.5)
            sm = max(sx, sy)
            sm = max(sm, sz)
            #er = asteroid.blob.get("exclusionradius",0)
            #er *= sm

            asteroid.blob.set("local_scale_x_coeff", sx)
            asteroid.blob.set("local_scale_y_coeff", sy)
            asteroid.blob.set("local_scale_z_coeff", sz)
            #asteroid.blob.set("exclusionradius", er)

def map_nebula_scatter(t_min, t_max, x,y,z, w,h, d):
    #spawn_points = scatter.box(random.randint(t_min,t_max), 0,0,0, 100000, 1000, 100000, centered=True)
    spawn_points = scatter.box(random.randint(t_min,t_max), x,y,z, w, h, d, centered=True)
    for v in spawn_points:
        cluster_spawn_points = scatter.sphere(random.randint(t_min*2,t_min*4), v.x, 0,v.z, 1000, 10000, ring=False)
        for v2 in cluster_spawn_points:
            #v2.y = v2.y % 500.0
            v2.y = random.random() * 500.0-250
            nebula = terrain_spawn(v2.x, v2.y, v2.z,None, "#, nebula", "nebula", "behav_nebula")
            nebula.blob.set("local_scale_x_coeff", random.uniform(1.0, 5.5))
            nebula.blob.set("local_scale_y_coeff", random.uniform(1.0, 5.5))
            nebula.blob.set("local_scale_z_coeff", random.uniform(1.0, 5.5))


def map_mine_scatter(t_min, t_max, x,y,z, w,h, d):
    #spawn_points = scatter.box(random.randint(t_min,t_max), 0,0,0, 100000, 1000, 100000, centered=True)
    spawn_points = scatter.box(random.randint(t_min,t_max), x,y,z, w, h, d, centered=True)
    for v in spawn_points:
        
        amount = random.randint(t_min+10,t_max+10)
        # the more you have give a bit more space
        ax = random.randint(-20,20)
        ay = random.randint(-150,150)
        az = random.randint(-20,20)
        #cluster_spawn_points = scatter_box(amount, v.x, 0,v.z, amount*50, amount*20,amount*200, centered=True, ax, ay, az )
        cluster_spawn_points = scatter.box(amount,  v.x, 0,v.z, amount*50, amount*5,amount*200, True, 0, ay, 0 )

        for v2 in cluster_spawn_points:
            v2.y = v2.y % 500.0
            mine_obj = terrain_spawn( v2.x, v2.y + random.randrange(-300,300), v2.z,None, None, "danger_1a", "behav_mine")
            mine_obj.blob.set("damage_done", 5)
            mine_obj.blob.set("blast_radius", 1000)
            mine_obj.engine_object.blink_state = -5


def save_map():
    pass


def load_map():
    pass
