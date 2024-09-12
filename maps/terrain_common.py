from sbs_utils import scatter
import random
from sbs_utils.procedural.ship_data import plain_asteroid_keys
from sbs_utils.procedural.spawn import terrain_spawn

# make a few random clusters of Asteroids
def terrain_asteroid_clusters(terrain_value):
    #t_min = terrain_value * 7
    #t_max = t_min * 3
    t_max_pick = [0,8,10, 12,16]
    t_min = t_max_pick[terrain_value]
    t_max = t_min * 2
    spawn_points = scatter.box(random.randint(t_min,t_max), 0,0,0, 100000, 1000, 100000, centered=True)

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

#
# Original
#

# t_min = terrain_value * 7
# t_max = t_min * 3
# spawn_points = scatter.box(random.randint(t_min,t_max), 0,0,0, 100000, 1000, 100000, centered=True)

# asteroid_types = ship_data_plain_asteroid_keys()
# for v in spawn_points:
    
#     amount = random.randint(t_min+10,t_max+10)
#     # the more you have give a bit more space
#     ax = random.randint(-20,20)
#     ay = random.randint(-150,150)
#     az = random.randint(-20,20)
#     #cluster_spawn_points = scatter_box(amount, v.x, 0,v.z, amount*50, amount*20,amount*200, centered=True, ax, ay, az )
#     cluster_spawn_points = scatter_box(amount,  v.x, 0,v.z, amount*50, amount*5,amount*200, True, 0, ay, 0 )

#     for v2 in cluster_spawn_points:
#         a_type = random.choice(asteroid_types)

#         asteroid = terrain_spawn(v2.x, v2.y, v2.z,None, "#,asteroid", a_type, "behav_asteroid")
#         asteroid.engine_object.steer_yaw = random.uniform(0.0001, 0.003)
#         asteroid.engine_object.steer_pitch = -random.uniform(0.0001, 0.003)
#         asteroid.engine_object.steer_roll = random.uniform(0.0001, 0.003)

#         sx = random.uniform(0.8, 3.5)
#         sy = random.uniform(0.8, 3.5)
#         sz = random.uniform(0.8, 3.5)
#         sm = max(sx, sy)
#         sm = max(sm, sz)
#         #er = asteroid.blob.get("exclusionradius",0)
#         #er *= sm

#         asteroid.blob.set("local_scale_x_coeff", sx)
#         asteroid.blob.set("local_scale_y_coeff", sy)
#         asteroid.blob.set("local_scale_z_coeff", sz)
#         #asteroid.blob.set("exclusionradius", er)
