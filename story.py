from random import choice
from sbs_utils.fs import load_json_data, get_mission_dir_filename
from sbs_utils import faces as faces
from sbs_utils.mast.label import label
from sbs_utils.procedural.execution import AWAIT, task_schedule, jump
from sbs_utils.procedural.timers import delay_sim
import os
import sbs
# Expose monster.py
from monster import *




@label()
def test_delay():
    yield AWAIT(delay_sim(5))
    print("test tick") 
    yield jump(test_delay)



def story_get_console_type():
    return os.environ.get("cosmos_start_mode")


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




def get_face_from_data(face_style):
    match face_style:
        case "terran":
            return faces.random_terran()
        case "terran_male":
            return faces.random_terran_male()
        case "terran_female":
            return faces.random_terran_female()
        case "terran_fluid":
            return faces.random_terran_fluid()
        case "terran_civilian":
            return faces.random_terran_fluid()
        case "torgoth":
            return faces.random_torgoth()
        case "skaraan":
            return faces.random_skaraan()
        case "ximni":
            return faces.random_ximni()
        case "arvonian":
            return faces.random_arvonian()
        case "kralien":
            return faces.random_kralien()
        case "random":
            return faces.random_face()
    return face_style
