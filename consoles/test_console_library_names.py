"""Every library function a console's .mast calls must be reachable from MAST.

Twice in one session a console shipped a call to a function that existed, was tested,
and was INVISIBLE to MAST because it was not re-exported from `sbs_utils.procedural.gui`
- the package that `mast_sbs_procedural` registers wholesale as MAST globals. Both times
the failure was `name '...' is not defined`, raised when a player opened the console, and
neither the unit suite nor a headless `--test` could see it: headless never enters a
console page (`gui 0/9`), so the line never runs.

This is the cheap guard for that class. It is static - it reads the .mast files and
checks the names against the package - so it needs no engine, no page and no browser.

It does NOT prove the console works; it proves that nothing it calls is missing. The
rest still needs a real session.
"""
import os
import re
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.procedural.gui as gui_pkg


HERE = os.path.dirname(os.path.abspath(__file__))

# Library API families a console reaches for. Deliberately a list of PREFIXES rather
# than "every identifier": a .mast is full of mission-local names, and a check that
# cannot tell those apart from library ones is a check nobody keeps passing.
LIBRARY_PREFIXES = ("viewscreen_", "gui_", "overlay_", "camera_", "science_", "comms_",
                    "crew_")

CALL = re.compile(r"\b([a-z_][a-z0-9_]*)\s*\(")


def _local_defs():
    """Functions the addon defines ITSELF (its own .py files, imported by
    __init__.mast). A mission helper called gui_screen_tabs is not a library call, and a
    check that cannot tell the difference is a check nobody keeps passing."""
    names = set()
    for name in os.listdir(HERE):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(HERE, name), encoding="utf-8") as f:
            names.update(re.findall(r"^def\s+([a-z_][a-z0-9_]*)", f.read(), re.M))
    return names


def _mast_files():
    for name in sorted(os.listdir(HERE)):
        if name.endswith(".mast"):
            yield os.path.join(HERE, name)


class TestConsoleLibraryNames(unittest.TestCase):
    def test_every_library_call_resolves(self):
        missing = {}
        local = _local_defs()
        for path in _mast_files():
            with open(path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    code = line.split("#", 1)[0]
                    for name in CALL.findall(code):
                        if not name.startswith(LIBRARY_PREFIXES):
                            continue
                        if name in local:
                            continue
                        if hasattr(gui_pkg, name):
                            continue
                        if _resolves_elsewhere(name):
                            continue
                        missing.setdefault(name, []).append(
                            f"{os.path.basename(path)}:{lineno}")
        self.assertEqual(
            missing, {},
            "console .mast calls a library function MAST cannot see - export it from "
            f"sbs_utils.procedural.gui: {missing}")


def _resolves_elsewhere(name):
    """Some families live in their own procedural modules, which mast_sbs_procedural
    registers separately. Only a name found NOWHERE is a finding."""
    import importlib
    for mod in ("sbs_utils.procedural.science", "sbs_utils.procedural.comms",
                "sbs_utils.procedural.query", "sbs_utils.procedural.roles",
                "sbs_utils.procedural.inventory", "sbs_utils.procedural.links",
                "sbs_utils.procedural.execution", "sbs_utils.procedural.settings",
                "sbs_utils.procedural.quest", "sbs_utils.procedural.maps",
                "sbs_utils.procedural.crew", "sbs_utils.procedural.amd_crew",
                "sbs_utils.procedural.amd_doc", "sbs_utils.procedural.media"):
        try:
            if hasattr(importlib.import_module(mod), name):
                return True
        except Exception:
            continue
    return False


if __name__ == "__main__":
    unittest.main()
