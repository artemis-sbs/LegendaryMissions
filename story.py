from random import choice
from sbs_utils.fs import load_json_data, get_mission_dir_filename


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


def story_get_mission_setup():

    defaults = {
            "auto_play": {
            "enable": True
        },
            "operator_mode": {
            "enable": False,
            "logo": "media/operator",
            "show_logo_on_main": True,
            "pin": "000000"
        },
        "auto_start": False,
        "world_select": "siege",
        "terrain_select": "some",
        "lethal_select": "none",
        "friendly_select": "few",
        "monster_select": "none",
        "upgrade_select": "many",
        "seed_value": 0,
        "game_started": False,
        "game_ended": False,
        "difficulty": 5,
        "player_count": 1,
        "grid_theme": 0,
        "player_list": [
            {
                "name": "Artemis",
                "id": None,
                "side": "tsn",
                "ship": "tsn_battle_cruiser",
                "face": "terran",
            },
            {
                "name": "Intrepid",
                "id": None,
                "side": "tsn",
                "ship": "tsn_battle_cruiser",
                "face": "terran",
            },
            {
                "name": "Aegis",
                "id": None,
                "side": "tsn",
                "ship": "tsn_battle_cruiser",
                "face": "terran",
            },
            {
                "name": "Horatio",
                "id": None,
                "side": "tsn",
                "ship": "tsn_battle_cruiser",
                "face": "terran",
            },
            {
                "name": "Excalibur",
                "id": None,
                "side": "tsn",
                "ship": "tsn_battle_cruiser",
                "face": "terran",
            },
            {
                "name": "Hera",
                "id": None,
                "side": "tsn",
                "ship": "tsn_battle_cruiser",
                "face": "terran",
            },
            {
                "name": "Ceres",
                "id": None,
                "side": "tsn",
                "ship": "tsn_battle_cruiser",
                "face": "terran",
            },
            {
                "name": "Diana",
                "id": None,
                "side": "tsn",
                "ship": "tsn_battle_cruiser",
                "face": "terran",
            },
        ],
    }
    setup_data = load_json_data(get_mission_dir_filename("setup.json"))
    if setup_data is not None:
        return defaults | setup_data
    return defaults



