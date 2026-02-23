from sbs_utils.procedural.gui import gui_row, gui_text, gui_hole
from sbs_utils.procedural.links import linked_to
from sbs_utils.procedural.query import to_object
from sbs_utils.helpers import FrameContext
import sbs_utils.yaml as yaml
import json
from sbs_utils.vec import Vec3


# I need this because Vec3 has an __iter__
class JSONEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, Vec3):
                return {"x": o.x, "y": o.y, "z": o.z}
            return super().default(o)



def brain_scan_get_text_brain(b, indent):
    if int(b.brain_type.value)  == 0x100:
        t = f"{b.active}"
        try:
            d = json.dumps(b.data, cls=JSONEncoder)
            d = d.replace("{"," " )
            d = d.replace("}"," " )
        except Exception as e:
            d = f"data {e}"


        i = " " * (indent *2)
        res = f"[UNKNOWN]"
        if b.result == 100:
            res = "[FAIL]"
        elif b.result == 99:
            res = "[SUCCESS]"

        d = "\n"+ (" " * (((indent+1) * 2) + len(res))) +  "data:"  + d
        
        return f"{i} {res} {t}{d}"
    
    if int(b.brain_type.value) == 0x200:
        i = " " * (indent *2)
        c = len(b.children)
        res = f"[UNKNOWN]"
        if b.result == 100:
            res = "[FAIL]"
        elif b.result == 99:
            res = "[SUCCESS]"
        _ret = f"{i} {res} {b.label} {c} children"
        for c in b.children:
            _ret += "\n"
            _ret += brain_scan_get_text_brain(c, indent+1)
        return _ret

    if int(b.brain_type.value) == 0x400:
        i = " " * (indent *2)
        c = len(b.children)
        res = f"[UNKNOWN]"
        if b.result == 100:
            res = "[FAIL]"
        elif b.result == 99:
            res = "[SUCCESS]"
        _ret = f"{i} {res} {b.label} {c} children"
        for c in b.children:
            _ret += "\n"
            _ret += brain_scan_get_text_brain(c, indent+1)
        return _ret
    return f"Weird brain {b.brain_type.value}"


def brain_scan_get_text(obj):
    _text = f"$text:Brain for {obj.name}\n"

    objectives = linked_to(obj.id, "OBJECTIVE")
    if len(objectives)>0:

        _text += "OBJECTIVES: "
        for goal_id in objectives:
            goal = to_object(goal_id)
            if goal is None:
                continue
            desc = goal.get_inventory_value("desc", "No Desc")
            _text += "    " + desc

    _target_id = obj.get_inventory_value("blackboard:target")
    if _target_id is not None:
        _text += f"       TARGET ID: {_target_id}\n"
    _target = to_object(obj.get_inventory_value("blackboard:target"))
    if _target is not None:
        _text += f"       TARGET: {_target.name}\n"
    _target_pos = obj.get_inventory_value("blackboard:target_position")
    if _target_pos is not None:
        _text += f"       TARGET POSITION: {_target_pos.x:.2f}, {_target_pos.y:.2f}, {_target_pos.z:.2f}\n"

    ships = linked_to(obj.id, "ship_list")
    if len(ships)>0:
        _text += "       SHIPS: "
        for ship in ships:
            sob = to_object(ship)
            if sob is not None:
                _text += f"{sob.name} "
        _text += "\n"

    b = obj.get_inventory_value("__BRAIN__")
    _text += brain_scan_get_text_brain(b, 1)
    _text += ";"

    return _text

def brain_scan_selection_item(item):
    gui_row("row-height: 1.2em;padding:5px,0,5px,0;")
    gui_text(f"$text:{item.name};justify: left;","padding:0,0,0.1em,0;")
    
def brain_scan_selection_title():
    gui_row("row-height: 1.2em;padding:13px;background:#1578;")
    gui_text(f"$text:SHIP;justify: left;")
