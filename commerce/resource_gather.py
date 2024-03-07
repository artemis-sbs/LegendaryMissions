from sbs_utils.procedural.routes import RouteDamageObject
from sbs_utils.procedural.execution import get_variable
from sbs_utils.procedural.roles import has_role
from sbs_utils.procedural.query import to_blob
import math
import sbs

@RouteDamageObject
def resource_handle_damage():
    
    source = get_variable("DAMAGE_SOURCE_ID")
    target = get_variable("DAMAGE_TARGET_ID")
    # Get out quickly if don't care
    if source is None or target is None:
        return
    if not has_role(source, "__player__") or has_role(source, "harvester"):
        return

    if not has_role(target, "asteroid"):
        return
    
    blob = to_blob(target)
    if blob is None:
        return
    x = blob.get("local_scale_x_coeff",0)
    y = blob.get("local_scale_y_coeff",0)
    z = blob.get("local_scale_z_coeff",0)



    xf, xi = math.modf(x)
    yf, yi = math.modf(x)
    zf, zi = math.modf(x)

    if xi == 0 and yi == 0 and zi== 0 and (xf+yf+zf) < 2.0:
        sbs.delete_object(target)
        return

    # coeff
    coeff = 0.95
    blob.set("local_scale_x_coeff",x*coeff, 0)
    blob.set("local_scale_y_coeff",y*coeff,0)
    blob.set("local_scale_z_coeff",z*coeff,0)

