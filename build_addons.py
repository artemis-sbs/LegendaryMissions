# this will build all the add ons
import os
import zipfile
import pathlib

skip =  {"__pycache__"}


def zipdir(path):
    try: 
        os.mkdir('addons')
    except Exception:
        pass
    finally:
        pass

    with zipfile.ZipFile(f"addons/{path}.zip", "w") as zf:
        

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
zipdir("consoles")
zipdir("damage")
zipdir("docking")
zipdir("grid_comms")
zipdir("hangar")
zipdir("maps")
zipdir("operator")
zipdir("science_scans")
zipdir("side_missions")
zipdir("upgrades")
zipdir("internal_comms")
zipdir("zadmiral")

