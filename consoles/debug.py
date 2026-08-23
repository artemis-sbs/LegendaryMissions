from sbs_utils.procedural.gui import gui_row, gui_icon, gui_text
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.query import to_data_set

def debug_menu_template(item):
    gui_row("row-height: 48px;padding:3px")
    gui_icon(f"icon_index: {item['icon']};color:white;")
    gui_row("row-height: 1.2em")
    gui_text(f"$text:{item['text']};justify:left;")
    

def debug_dump_mast():
    from sbs_utils.helpers import FrameContext

    
    task = FrameContext.server_task
    _mast = task.main.mast 
    scheds = _mast.schedulers
    s = len(scheds)
    print(f"Scheduler count {s}")
    task_count = 0
    sub_task_count = 0

    active_labels = {}
    for s in scheds:
        for t in s.tasks:
            task_count += 1
            l = t.active_label
            lc = active_labels.get(l, 0)
            lc += 1
            active_labels[l] = lc
            for st in t.sub_tasks:
                sub_task_count += 1
                # May need recursion
    print(f"Task count {task_count} sub task count {sub_task_count}")
    for l in active_labels:
        c = active_labels[l]
        print(f"Label: {l} count: {c}")


def debug_dump_nebula():
    with open("nebula_dump.log", "w") as f:
        for n in role("nebula"):
            blob = to_data_set(n)
            size = blob.get("display_size", 0)
            denisty = blob.get("density", 0)
            f.write(f"{size:0.2f} {denisty:0.2f}\n")
        










def debug_test_item_plan(salvage=60, bio=4, cache=20):
    """What "Test Items" should drop: every registered item that is NOT an upgrade,
    plus a stockpile of the Fabricator's raw materials.

    Returns a list of ``{"key": str, "qty": int}``, beacon materials first.

    READ OFF THE REGISTRY, not a literal list, and that is the point. `Test Upgrades`
    next door hardcodes nine keys and has silently missed `hacking_virus` since it was
    added; a hardcoded twin here would rot the same way and would also be WRONG per
    mission, because which items exist depends on which addons are loaded - turret kits
    come from `turrets`, cockpit loadouts from `hangar`, salvage and bio samples from
    `fabrication`. Anything an addon registers as `type: item/...` shows up here for
    free, and anything that is not loaded simply is not offered.

    The defaults are sized to the beacon recipes rather than picked round: a Sensor
    Beacon is 8 salvage, Long Range 16, Bio 5 salvage + 1 bio_sample, and a Coolant Cell
    4. 60 salvage and 4 bio samples covers three sensor beacons, one long-range, two bio
    and a coolant cell with a little slack - "a few beacons" without a scavenging run.

    Bulk arrives as CACHES (`qty` on one pickup) rather than 60 separate collectibles:
    that is what `item_spawn(qty=)` is for, and 60 objects to fly through one at a time
    is the grind the qty field was added to remove.
    """
    from sbs_utils.procedural.items import items_get_list, items_of_category

    # Skip what the Test Upgrades button already drops, so the two buttons compose
    # instead of doubling up.
    skip = set()
    for lbl in items_of_category("upgrade"):
        skip.add(lbl.get_inventory_value("key"))

    bulk = {"salvage": salvage, "bio_sample": bio}
    materials = []
    others = []
    for lbl in items_get_list():
        key = lbl.get_inventory_value("key")
        if not key or key in skip:
            continue
        if key not in bulk:
            others.append({"key": key, "qty": 1})
            continue
        # One cache per `cache` units, so the stack size stays readable on the toast.
        left = bulk[key]
        while left > 0:
            take = min(cache, left)
            materials.append({"key": key, "qty": take})
            left -= take
    # Materials first: they are what the button is FOR, so they land nearest the ship.
    return materials + others
