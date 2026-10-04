"""The record of finished games is never thrown away by the label that adds to it.

`save_game_results_yaml` read the file, and treated "could not parse it" the same as
"there is no file yet": it started an empty list and saved that over the top. Ten headless
runs finishing in the same second met in the file; one read it half-written; two hundred
games of history became twenty six, with nothing in any log.

This runs the REAL route and the REAL label out of `game_results.mast`, with the missions
folder pointed at a temporary one.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_game_results_save
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import tempfile
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

CONSOLES = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CONSOLES)

from sbs_utils import fs
from sbs_utils.agent import Agent, clear_shared
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers gui/route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.execution import set_shared_variable
from sbs_utils.procedural.signal import signal_emit
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.spaceobject import SpaceObject

import results_helpers

CID = 0x8080000000000001

for _n in dir(results_helpers):
    _f = getattr(results_helpers, _n)
    if callable(_f) and not _n.startswith("_") and getattr(_f, "__module__", "") == "results_helpers":
        MastGlobals.import_python_function(_f)

SAVE_STORY = "\n".join([
    "import game_results.mast",
    "gui_text('$text:harness;')",
    "await gui()",
    "",
])

# Cut off inside a quoted string, which is what a reader meets part way through a write.
HALF = "- time: '2026-09-01 20:00:00'\n  mission: LegendaryMissions\n  outcome: 'All shi"
GAMES = ("- time: '2026-09-01 20:00:00'\n  mission: LegendaryMissions\n"
         "- time: '2026-09-02 20:00:00'\n  mission: SecretMeeting\n")


class SavePage(StoryPage):
    story = None


class HelperTests(unittest.TestCase):
    """`game_results_load`: a list, and nothing is ever thrown away."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "game_results.yaml")

    def put(self, text):
        with open(self.path, "w") as f:
            f.write(text)

    def aside(self):
        return [n for n in os.listdir(self.dir.name) if n.startswith("game_results.unreadable-")]

    def test_no_file_yet_and_an_empty_one_start_a_new_record(self):
        self.assertEqual(results_helpers.game_results_load(self.path), [])
        self.put("")
        self.assertEqual(results_helpers.game_results_load(self.path), [])
        self.assertEqual(self.aside(), [])

    def test_the_games_on_record_come_back(self):
        self.put(GAMES)
        self.assertEqual([g["mission"] for g in results_helpers.game_results_load(self.path)],
                         ["LegendaryMissions", "SecretMeeting"])
        self.assertEqual(self.aside(), [])

    def test_a_file_that_is_not_a_list_of_games_is_kept(self):
        for text in ("mission: [unclosed\n", "just: a mapping\n"):
            with self.subTest(text=text):
                self.setUp()
                self.put(text)
                self.assertEqual(results_helpers.game_results_load(self.path), [])
                kept = self.aside()
                self.assertEqual(len(kept), 1)
                with open(os.path.join(self.dir.name, kept[0])) as f:
                    self.assertEqual(f.read(), text)


class LabelTests(unittest.TestCase):
    """The real route and label, writing into a missions folder of its own."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        os.makedirs(os.path.join(self.dir.name, "missions"))
        self.path = os.path.join(self.dir.name, "missions", "game_results.yaml")
        real = fs.get_artemis_data_dir
        fs.get_artemis_data_dir = lambda: self.dir.name.replace("\\", "/")
        self.addCleanup(setattr, fs, "get_artemis_data_dir", real)

        clear_shared()
        SpaceObject.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

        story = MastStory()
        story.basedir = CONSOLES
        errors = story.compile(SAVE_STORY, "saveharness", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        SavePage.story = story
        FrameContext.mast = story

        self.rte = []
        orig = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append
        self.addCleanup(setattr, MastScheduler, "on_runtime_error", orig)
        self.addCleanup(self.reset)

        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)
        self.ship = player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser")
        mock_sbs.assign_client_to_ship(CID, self.ship.id)
        self.server = SavePage()
        Gui.push(0, self.server)
        self.page = SavePage()
        Gui.push(CID, self.page)
        self.present()

        set_shared_variable("START_TEXT", "Mission accomplished")
        set_shared_variable("GAME_ENDED", False)
        set_shared_variable("SETTINGS", {})
        set_shared_variable("DIFFICULTY", 5)
        set_shared_variable("CONSOLE_SELECT", "helm")
        set_shared_variable("WORLD_SELECT", None)

    def reset(self):
        Gui.clients = {}
        Gui.widget_list_sent = {}
        SavePage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        FrameContext.context = None
        SpaceObject.clear()

    def present(self, n=1):
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            self.server.gui_state = "repaint"
            self.server.present(FakeEvent(0, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(CID, "gui_present"))

    def end_the_game(self):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "signal"))
        FrameContext.task = self.server.story_scheduler.tasks[0]
        signal_emit("show_game_results", None)
        self.present(3)
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def files(self):
        return sorted(os.listdir(os.path.join(self.dir.name, "missions")))

    def test_a_finished_game_is_added_to_the_ones_on_record(self):
        with open(self.path, "w") as f:
            f.write(GAMES)
        self.end_the_game()
        games = fs.load_yaml_data(self.path)
        self.assertEqual(len(games), 3)
        self.assertEqual(games[-1]["outcome"], "Mission accomplished")
        self.assertEqual(self.files(), ["game_results.yaml"])

    def test_a_half_written_file_is_kept_not_replaced(self):
        with open(self.path, "w") as f:
            f.write(HALF)
        self.end_the_game()
        kept = [n for n in self.files() if n.startswith("game_results.unreadable-")]
        self.assertEqual(len(kept), 1, self.files())
        with open(os.path.join(self.dir.name, "missions", kept[0])) as f:
            self.assertEqual(f.read(), HALF)
        self.assertEqual(len(fs.load_yaml_data(self.path)), 1)

    def test_a_run_that_is_not_a_game_leaves_no_record(self):
        with open(self.path, "w") as f:
            f.write(GAMES)
        set_shared_variable("SETTINGS", {"GAME_RESULTS_SAVE": False})
        self.end_the_game()
        with open(self.path) as f:
            self.assertEqual(f.read(), GAMES)
        self.assertTrue(Agent.SHARED.get_inventory_value("GAME_ENDED", False))


if __name__ == "__main__":
    unittest.main()
