# this will build all the add ons
import os
import zipfile
import pathlib

skip =  {"__pycache__"}
version = "v3.9.38"


def zipdir(path):
    # try: 
    #     os.mkdir('.addons')
    # except Exception:
    #     pass
    # finally:
    #     pass

    with zipfile.ZipFile(f"../__lib__/artemis-sbs.LegendaryMissions.{path}.{version}.mastlib", "w") as zf:
        

        for dirname, subdirs, files in os.walk(path):
            p = pathlib.Path(dirname)
            arc_dirname = str(pathlib.Path(*p.parts[1:]))
            print(f"{dirname} arc {arc_dirname}")
            if arc_dirname in skip:
                print("SKIP")
                continue

            if dirname != path:            
                zf.write(dirname)
                
            for filename in files:
                zf.write(os.path.join(dirname, filename), arcname=os.path.join(arc_dirname, filename))

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
zipdir("operator")
zipdir("science_scans")
zipdir("side_missions")
zipdir("upgrades")
zipdir("internal_comms")
zipdir("zadmiral")

