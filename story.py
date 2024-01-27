from random import choice
from sbs_utils.procedural.query import get_science_selection, to_object


def skybox_get_random():
    sky_boxes = [
        "sky1",
        "sky1-blue",
        "sky1-ds9",
        "sky1-rainbow",
        "sky1-bored-alice",
        "sky-delight",
        "sky-neb2-rvb",
    ]

    return choice(sky_boxes)


def get_dock_name(so):
    dock = get_science_selection(so)
    if not dock: return ""
    dock = to_object(dock)
    if not dock: return ""
    return f":  {dock.name}"
