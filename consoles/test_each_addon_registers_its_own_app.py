"""A PADD app is registered by the addon that has its screen.

`consoles` used to register every tile - Upgrades, Cargo, Fabricate, Airwing, Casino,
Help, Library, Quests - while their `//gui/app` routes lived in `items`, `fabrication`,
`hangar`, `casino` and `documents`. A mission that loaded `consoles` without one of those
(anything made from the starter template) logged

    ePADD: app 'upgrade' has no //gui/app/upgrade route - it cannot be opened ...

for each one, on every console that connected. A logged error fails a headless test run,
so every new author's first mission failed its own check.

The rule this pins: within one addon folder, every `gui_app_register("x", ...)` has a
`//gui/app/x` route in the same folder.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_each_addon_registers_its_own_app
"""
import glob
import os
import re
import unittest

MISSION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REGISTER = re.compile(r'^\s*gui_app_register\(\s*"([a-z_]+)"', re.M)
ROUTE = re.compile(r"^//gui/app/([a-z_]+)", re.M)


def _addons():
    for init in sorted(glob.glob(os.path.join(MISSION, "*", "__init__.mast"))):
        yield os.path.dirname(init)


def _scan(folder):
    registered, routed = set(), set()
    for path in glob.glob(os.path.join(folder, "*.mast")):
        with open(path, encoding="utf-8") as f:
            src = f.read()
        registered.update(REGISTER.findall(src))
        routed.update(ROUTE.findall(src))
    return registered, routed


class EachAddonRegistersItsOwnAppTests(unittest.TestCase):
    def test_every_registration_has_its_route_in_the_same_addon(self):
        orphans = []
        for folder in _addons():
            registered, routed = _scan(folder)
            for tab in sorted(registered - routed):
                orphans.append("%s registers %r and has no //gui/app/%s"
                               % (os.path.basename(folder), tab, tab))
        self.assertEqual(orphans, [])

    def test_the_fixture_is_real(self):
        """The scan finds the registrations it is supposed to be judging."""
        found = {}
        for folder in _addons():
            registered, _routed = _scan(folder)
            for tab in registered:
                found[tab] = os.path.basename(folder)
        self.assertEqual(found.get("messages"), "consoles")
        self.assertEqual(found.get("fabricate"), "fabrication")
        self.assertEqual(found.get("upgrade"), "items")
        self.assertEqual(found.get("airwing"), "hangar")
        self.assertEqual(found.get("casino"), "casino")
        self.assertEqual(found.get("quest"), "documents")

    def test_no_app_is_registered_twice(self):
        seen, twice = {}, []
        for folder in _addons():
            registered, _routed = _scan(folder)
            for tab in registered:
                if tab in seen:
                    twice.append("%r in %s and %s" % (tab, seen[tab], os.path.basename(folder)))
                seen[tab] = os.path.basename(folder)
        self.assertEqual(twice, [])


if __name__ == "__main__":
    unittest.main()
