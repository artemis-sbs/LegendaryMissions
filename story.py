from random import choice


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
