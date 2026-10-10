"""`races/__init__.mast`: every race's floor plans are there to be READ, and only the
playable races' are interiors.

The file used to load a race's `.grid` plans only when the race was in `PLAYABLE_RACES`
("TSN, Ximni" in LegendaryMissions), so a Kralien, Torgoth, Skaraan, Biomech or pirate
hull had no plan at all here - and a surrendered one could not be boarded.

Compiles the REAL file through MAST, with LegendaryMissions' own setting, and asks:

  * the GRID DATA - what an interior is built from, and what `grid_count_grid_data`
    counts a hull's fighter and shuttle bays from - is byte for byte what the same file
    left before the change (the playable races' plans merged, nothing else touched);
  * every one of the 63 shipped hulls now has a plan a boarding party's deck can be
    drawn from (`boarding_deck_has_plan`);
  * a Kralien's deck is what her plan says: her systems, and no brig;
  * with every race playable (the library default) every plan is merged, as before, and
    none is kept aside.

    cd ../sbs_utils && MAST_LEAVE_LOGS=1 PYTHONPATH=.;../LegendaryMissions \\
        python -m unittest races.test_races_plans

(Run from OUTSIDE this folder: `DEBUG()` opens `debug.log` with mode "w" in the current
folder, and this repo tracks one.)
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import copy
import glob
import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

RACES = os.path.dirname(os.path.abspath(__file__))
LM = os.path.dirname(RACES)

from sbs_utils.agent import Agent
from sbs_utils.gui import Gui
from sbs_utils.handlerhooks import reset_mission_state
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401
import sbs_utils.mast_sbs.mast_sbs_procedural  # noqa: F401
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural import boarding_deckplan as D
from sbs_utils.procedural import grid as G
from sbs_utils.procedural.grid_ascii import grid_ascii_parse
from sbs_utils.procedural.internal_damage import grid_count_grid_data
from sbs_utils.procedural.settings import settings_get_defaults

RACES_STORY = "\n".join([
    "import __init__.mast",
    "gui_text('$text:harness;')",
    "await gui()",
    "",
])

#: Which race each shipped plan belongs to, as `__init__.mast` groups them.
RACES_OF = {"tsn": "TSN", "xim": "Ximni", "arvonian": "Arvonian", "torgoth": "Torgoth",
            "skaraan": "Skaraan", "kralien": "Kralien", "biomech": "Biomech",
            "pirate": "Pirate"}


class RacesPage(StoryPage):
    story = None


def _races_plans():
    """{hull key: the plan's text} for every `.grid` file shipped."""
    out = {}
    for path in sorted(glob.glob(os.path.join(RACES, "*.grid"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        out[grid_ascii_parse(text)["ship"]] = text
    return out


class _RacesBase(unittest.TestCase):
    playable = "TSN, Ximni"                 # LegendaryMissions' settings.yaml

    def setUp(self):
        reset_mission_state()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)
        settings = settings_get_defaults()
        had = settings.get("PLAYABLE_RACES", self)
        settings["PLAYABLE_RACES"] = self.playable
        self.addCleanup(lambda: settings.pop("PLAYABLE_RACES", None) if had is self
                        else settings.__setitem__("PLAYABLE_RACES", had))
        # The engine's own table, before any plan is merged into it.
        self.stock = copy.deepcopy(G.grid_get_grid_data())
        self.plans = _races_plans()

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append
        story = MastStory()
        story.basedir = RACES
        errors = story.compile(RACES_STORY, "racesplans", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        RacesPage.story = story
        FrameContext.mast = story
        Gui.push(0, RacesPage())
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def tearDown(self):
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        RacesPage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        reset_mission_state()
        FrameContext.context = None

    def race_of(self, hull):
        return RACES_OF.get(hull.split("_", 1)[0], "USFP")

    def is_playable(self, hull):
        return self.race_of(hull).lower() in [r.strip().lower()
                                              for r in self.playable.split(",")]

    def expected_grid_data(self):
        """What the file left in the grid data BEFORE the change: the stock table, with
        the playable races' plans merged over it and nothing else."""
        G.grid_reset_caches()
        for hull, text in self.plans.items():
            if self.is_playable(hull):
                G.grid_merge_ascii(text, "races")
        want = copy.deepcopy(G.grid_get_grid_data())
        G.grid_reset_caches()
        return want


class AsLegendaryMissionsRunsIt(_RacesBase):

    def test_there_are_63_plans_and_the_file_names_every_one(self):
        self.assertEqual(len(self.plans), 63)
        with open(os.path.join(RACES, "__init__.mast"), encoding="utf-8") as f:
            text = f.read()
        for path in glob.glob(os.path.join(RACES, "*.grid")):
            name = os.path.basename(path)
            self.assertEqual(text.count('grid_merge_ascii(media_read_relative_file("%s")' % name), 1, name)
            self.assertEqual(text.count('grid_plan_ascii(media_read_relative_file("%s")' % name), 1, name)

    def test_the_grid_data_is_exactly_what_it_was(self):
        got = copy.deepcopy(G.grid_get_grid_data())
        self.assertEqual(got, self.expected_grid_data())

    def test_a_raiders_hull_is_still_not_an_interior(self):
        for hull in ("kralien_battleship", "torgoth_leviathan", "skaraan_executor",
                     "pirate_brigantine", "biomech_a"):
            with self.subTest(hull=hull):
                self.assertEqual(G.grid_get_grid_data().get(hull), self.stock.get(hull))
                self.assertFalse(G.grid_get_layout(hull))
                for role in ("fighter", "shuttle"):
                    self.assertEqual(grid_count_grid_data(hull, role, 0), 0)

    def test_a_stations_bays_are_counted_as_before(self):
        """The friendly stations' defensive craft are counted from these."""
        for hull in ("starbase_command", "starbase_civil", "starbase_industry",
                     "starbase_science"):
            for role in ("fighter", "shuttle"):
                had = sum(1 for o in (self.stock.get(hull) or {}).get("grid_objects") or []
                          if role in [r.strip() for r in o["roles"].split(",")])
                self.assertEqual(grid_count_grid_data(hull, role, 0), had, (hull, role))

    def test_every_shipped_hull_has_a_deck_to_board(self):
        missing = [hull for hull in self.plans if not D.boarding_deck_has_plan(hull)]
        self.assertEqual(missing, [])

    def test_the_raiders_are_the_ones_that_gained_one(self):
        gained = sorted(hull for hull in self.plans
                        if not (self.stock.get(hull) or {}).get("grid_objects")
                        and not self.is_playable(hull))
        self.assertTrue(gained)
        for hull in gained:
            self.assertTrue(D.boarding_deck_has_plan(hull), hull)
            self.assertEqual(D.boarding_deck_plan(hull)["source"], "grid text", hull)
        races = {self.race_of(hull) for hull in gained}
        for race in ("Kralien", "Torgoth", "Skaraan", "Biomech", "Pirate"):
            self.assertIn(race, races)

    def test_a_kraliens_deck_is_her_systems_and_no_brig(self):
        plan = D.boarding_deck_plan("kralien_battleship")
        kinds = {D.boarding_deck_room_kind(name) for name in plan["cells"].values()}
        self.assertIn("hallway", kinds)
        for kind in ("brig", "quarters", "cargo", "sickbay", "mess", "lab"):
            self.assertNotIn(kind, kinds)
        self.assertTrue(kinds & {"warp", "impulse", "beam", "shield", "sensor",
                                 "maneuver", "torpedo"})

    def test_a_playable_hull_is_an_interior_and_is_not_kept_aside(self):
        self.assertTrue(G.grid_get_layout("tsn_light_cruiser"))
        self.assertEqual(G.grid_get_grid_data()["tsn_light_cruiser"].get("#mod"), "races")
        self.assertEqual(G.grid_plans_kept(), sum(1 for h in self.plans
                                                  if not self.is_playable(h)))


class WithEveryRacePlayable(_RacesBase):
    """The library default (and a mission that lists them all): as it always was."""
    playable = "TSN, USFP, Ximni, Arvonian, Torgoth, Skaraan, Kralien, Biomech, Pirate"

    def test_every_plan_is_merged_and_none_is_kept_aside(self):
        self.assertEqual(G.grid_plans_kept(), 0)
        self.assertTrue(G.grid_get_layout("kralien_battleship"))
        self.assertTrue(D.boarding_deck_has_plan("kralien_battleship"))
        # (Last: working out what it should be starts the table over.)
        self.assertEqual(copy.deepcopy(G.grid_get_grid_data()), self.expected_grid_data())


if __name__ == "__main__":
    unittest.main()
