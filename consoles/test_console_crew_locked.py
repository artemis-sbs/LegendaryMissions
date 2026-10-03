"""A locked cast at the console picker: the line is who you are, and there is no Edit.

A roster that says `Names: locked` puts the script's people on the bridge. The picker has
to agree with that in two places, and it used to agree in neither: the identity line was
built from whatever name the player had saved on their own machine, and the Edit button
offered to change it.

    python -m unittest test_console_crew_locked
"""
import os
import re
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes            # noqa: F401  breaks a circular import
from cosmos_dev.mock import sbs
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.amd_doc import amd_document
from sbs_utils.procedural.amd_crew import amd_crew_data, crew_from_document
from sbs_utils.procedural.execution import set_shared_variable
import sbs_utils.procedural.crew as crew

from common_console_selection import console_crew_identity

CAST = """# [Rosters](rosters)

## [Galaxy Class](galaxy)
---
crew
Hull: tsn_battle_cruiser
Race: terran
{names}---

### [Data](data)
---
Rank: Lt. Commander
Console: science
---
"""

CID = 0x8000000000000001
HULL = "tsn_battle_cruiser"


class _Case(unittest.TestCase):
    NAMES = ""

    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        crew.crew_clear()
        crew.crew_names_clear()
        set_shared_variable("CREW_SELECT", "")
        crew.crew_declare(crew_from_document(
            amd_document(CAST.format(names=self.NAMES), data_parser=amd_crew_data)))
        self.addCleanup(crew.crew_clear)
        self.addCleanup(crew.crew_names_clear)

    def ident(self, console, name=""):
        return console_crew_identity(CID, 0, HULL, console, name, "", "", "")


class TestALockedCast(_Case):
    NAMES = "Names: locked\n"

    def test_a_saved_name_does_not_reach_the_line(self):
        self.assertEqual(self.ident("science", name="Doug").label, "Lt. Commander Data")

    def test_the_line_says_it_is_locked(self):
        self.assertTrue(self.ident("science", name="Doug").locked)

    def test_a_seat_the_cast_does_not_fill_is_not_locked(self):
        line = self.ident("helm", name="Doug")
        self.assertEqual(line.name, "Doug")
        self.assertFalse(line.locked)


class TestAnEditableCast(_Case):
    def test_a_saved_name_still_wins_and_nothing_is_locked(self):
        line = self.ident("science", name="Doug")
        self.assertEqual(line.name, "Doug")
        self.assertFalse(line.locked)


class TestThePickerDropsEdit(unittest.TestCase):
    """Static, because nothing headless reaches the picker page (see the fallthrough test)."""

    def test_the_edit_button_is_gated_on_the_lock(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "common_console_select.mast"), encoding="utf-8") as f:
            src = f.read()
        gate = re.search(r"^(\s*)if ([^\n]*):\n\1    on gui_message\(gui_button\(\"Edit\"", src, re.M)
        self.assertIsNotNone(gate, "the Edit button is no longer where this test looks")
        self.assertIn("CREW_EDIT", gate.group(2))
        self.assertIn("crew_ident.locked", gate.group(2))


if __name__ == "__main__":
    unittest.main()
