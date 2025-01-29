import random
from sbs_utils.procedural.spawn import terrain_spawn
from sbs_utils.procedural.ship_data import plain_asteroid_keys
from sbs_utils import scatter

def test_spawn_asteroid_box(x,y,z, size=10000, amount= 20):
    asteroid_types = plain_asteroid_keys()
    a_type = random.choice(asteroid_types)

    cluster_spawn_points = scatter.box(amount,  x, y,z, x+size, 500, z+size, False, 0, 0, 0 )

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

        # # #
        # # # Sphere od smaller asteroids
        # # #
        # this_amount = random.randint(7,12)
        # little = scatter.box(this_amount,  v2.x, 0,v2.z, amount*150, amount*50,amount*200, True)
        # #little = scatter.sphere(random.randint(2,6), v2.x, v2.y, v2.z, 300, 800)
        # # little = scatter.sphere(random.randint(12,26), v2.x, v2.y, v2.z, 800)
        
        # for v3 in little: 
        #     a_type = random.choice(asteroid_types)

        #     asteroid = terrain_spawn(v3.x, v3.y, v3.z,None, "#,asteroid", a_type, "behav_asteroid")
        #     asteroid.engine_object.steer_yaw = random.uniform(0.0001, 0.003)
        #     asteroid.engine_object.steer_pitch = -random.uniform(0.0001, 0.003)
        #     asteroid.engine_object.steer_roll = random.uniform(0.0001, 0.003)
        #     sx1 = random.uniform(0.3, 1.0)
        #     sy1 = random.uniform(0.3, 1.0)
        #     sz1 = random.uniform(0.3, 1.0)
        #     sm1 = max(sx, sy)
        #     sm1 = max(sm, sz)
        #     er = asteroid.engine_object.exclusion_radius
        #     er *= sm1
        #     asteroid.engine_object.exclusion_radius = 0
            

        #     asteroid.blob.set("local_scale_x_coeff", sx1)
        #     asteroid.blob.set("local_scale_y_coeff", sy1)
        #     asteroid.blob.set("local_scale_z_coeff", sz1)



def test_spawn_nebula_box(x,y,z, size=10000, amount= 10):
    if amount==0:
        return
    cluster_spawn_points = scatter.box(amount,  x, y,z, x+size, 500, z+size, False, 0, 0, 0 )
    for v2 in cluster_spawn_points:
        v2.y = v2.y % 500.0
        nebula = terrain_spawn(v2.x, v2.y, v2.z,None, "#, nebula", "nebula", "behav_nebula")
        nebula.blob.set("local_scale_x_coeff", random.uniform(1.0, 5.5))
        nebula.blob.set("local_scale_y_coeff", random.uniform(1.0, 5.5))
        nebula.blob.set("local_scale_z_coeff", random.uniform(1.0, 5.5))

