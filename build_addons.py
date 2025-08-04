# this will build all the add ons
import os
import zipfile
import pathlib


skip =  {"__pycache__"}
version = os.environ.get('VERSION')


def zipdir(folder_path, ext="mastlib"):
    # try: 
    #     os.mkdir('.addons')
    # except Exception:
    #     pass
    # finally:
    #     pass

    with zipfile.ZipFile(f"../__lib__/artemis-sbs.LegendaryMissions.{folder_path}.{version}.{ext}", "w") as zf:
        for root, subdirs, files in os.walk(folder_path):
            p = pathlib.Path(root)
            arc_dirname = str(pathlib.Path(*p.parts[1:]))
            print(f"{root} arc {arc_dirname}")
            if arc_dirname in skip:
                print("SKIP")
                continue

            # if root != folder_path:            
            #     zf.write(root)
                
            for file in files:
                file_path = os.path.join(root, file)
                archive_path = os.path.relpath(file_path, folder_path)
                zf.write(file_path, archive_path)
                #zf.write(os.path.join(root, filename), arcname=os.path.join(arc_dirname, filename))

zipdir("autoplay")
zipdir("ai")
zipdir("comms")
zipdir("commerce")
zipdir("consoles")
zipdir("damage")
zipdir("docking")
zipdir("fleets")
zipdir("grid_comms")
zipdir("hangar")
### Don't copy Legendary maps
# zipdir("maps")
zipdir("internal_comms")
zipdir("operator")
zipdir("science_scans")
zipdir("side_missions")
zipdir("upgrades")
zipdir("admiral")
zipdir("admiral_comms")
zipdir("gamemaster")
zipdir("gamemaster_comms")
zipdir("prefabs")
zipdir("basic_player_destroy")
zipdir("basic_random_skybox")
zipdir("collisions")
zipdir("data_panels")
zipdir("media", "zip")

