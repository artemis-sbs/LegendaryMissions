"""The Fabricate panel tells the engineer what is happening.

Two things it did not do, both reported from a real bridge:

  * pressing Build showed NOTHING. The page is built with `fab_building` False, so it
    parks in the plain `await gui()` rather than the 1-second self-tick branch that
    draws the countdown, and nothing woke it. The build was running the whole time.
  * finishing showed nothing either. The only completion signal was an overlay_toast,
    which is a LOG line now - it lands in the ambient strip and the Log tab, i.e.
    everywhere except the panel the engineer is watching.

So this drives the real panel: it clicks the real Build button and reads the text the
page actually emits, before and after. Measured against the pre-fix files, both
assertions here failed with an empty action band - which is exactly what "hitting build
doesn't update" and "no real indication it was built" look like from the chair.

Three things the harness has to get right, each of which fails SILENTLY:

  * **Compile through MAST's own `import`.** The compiler injects `signal_register(...)`
    for every `//` route into that file's MAIN. Concatenating the files into one source
    and parking at the top means no route is ever registered - the click emits and
    nothing answers, which reads as a broken handler. Compiling the files separately
    into one story instead wipes the label table.
  * **The park goes LAST**, after the imports, for the same reason.
  * **A SERVER page as well as the console one.** `//shared/signal` routes are filtered
    by `scheduler.is_server()` (client_id == 0). With only a client page the build
    routes are registered and then never run.

    PYTHONPATH=../sbs_utils python -m unittest fabrication.test_fabricate_panel
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

# recipes.py does `from sbs_utils...`, but the page pulls in modules that `import sbs`.
sys.modules.setdefault("sbs", mock_sbs)

FAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FAB)

from sbs_utils.agent import clear_shared
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers gui/route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.amd_doc import amd_document
from sbs_utils.procedural.gui.navigation import gui_reroute_client
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.spaceobject import SpaceObject

import recipes

CID = 1

# The addon's own helpers have to be MAST globals, exactly as the addon loader makes them.
for _n in dir(recipes):
    _f = getattr(recipes, _n)
    if callable(_f) and not _n.startswith("_") and getattr(_f, "__module__", "") == "recipes":
        MastGlobals.import_python_function(_f)

# Imports first so every route's signal_register lands in main; the park last so main
# stays alive for the page to reroute out of.
HARNESS_STORY = "\n".join([
    "import beacon_tabs.mast",
    "import fabrication.mast",
    "import beacon_workflow.mast",
    "gui_text('$text:harness;')",
    "await gui()",
    "",
])


class FabPage(StoryPage):
    story = None


class _Emitted:
    """Every text and button the page sent this present."""

    def __init__(self):
        self.texts = []
        self.buttons = []

    def install(self):
        self._orig = {}
        for name, sink in (("send_gui_text", self.texts),
                           ("send_gui_button", self.buttons)):
            self._orig[name] = getattr(mock_sbs, name)
            setattr(mock_sbs, name, self._rec(sink, self._orig[name]))

    def remove(self):
        for name, fn in self._orig.items():
            setattr(mock_sbs, name, fn)

    def _rec(self, sink, orig):
        def _fn(client_id, parent, tag, props, left, top, right, bottom):
            sink.append((tag, props or ""))
            return orig(client_id, parent, tag, props, left, top, right, bottom)
        return _fn

    def clear(self):
        self.texts.clear()
        self.buttons.clear()

    def text_with(self, needle):
        return [p for _t, p in self.texts if needle in p]

    def button_named(self, needle):
        return [t for t, p in self.buttons if needle in p]


class _Base(unittest.TestCase):
    def setUp(self):
        clear_shared()
        SpaceObject.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

        self.emitted = _Emitted()
        self.emitted.install()

        story = MastStory()
        story.basedir = FAB
        errors = story.compile(HARNESS_STORY, "fabharness", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        FabPage.story = story
        FrameContext.mast = story
        self.story = story

        self.rte = []
        self._orig_rte = MastScheduler.runtime_error
        MastScheduler.runtime_error = lambda s, message: self.rte.append(message)

        # The addon loads these from its media pack at story load; here the file is
        # right beside us.
        with open(os.path.join(FAB, "recipes.amd"), encoding="utf-8") as f:
            recipes.fabrication_load_recipes_amd(amd_document(f.read()))

        self.ship = player_spawn(0, 0, 0, "Engineer", "tsn", "tsn_light_cruiser")
        mock_sbs.assign_client_to_ship(CID, self.ship.id)

        self.tab = [k for k in story.labels if k.startswith("gui/tab/fabricate")][0]

        self.server = FabPage()
        Gui.push(0, self.server)
        self.page = FabPage()
        Gui.push(CID, self.page)
        self.present()
        self.open_tab()

    def tearDown(self):
        self.emitted.remove()
        MastScheduler.runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        FabPage.story = None
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
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def open_tab(self):
        """Re-enter the tab route, which re-runs the panel BUILDER.

        A present() only re-emits the tree the page already has, so a test that changes
        state and presents sees the old panel.
        """
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(CID, "gui_present"))
        gui_reroute_client(CID, self.tab)
        self.emitted.clear()
        self.present()

    def click(self, tag):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(CID, "gui_message"))
        Gui.on_message(FakeEvent(client_id=CID, tag="gui_message", sub_tag=tag))

    def stock(self, salvage=100, bio=5):
        set_inventory_value(self.ship.id, "salvage", salvage)
        set_inventory_value(self.ship.id, "bio_sample", bio)
        self.open_tab()

    def press_build(self):
        build = self.emitted.button_named("Build")
        self.assertTrue(build, "no Build button on screen")
        self.click(build[0])
        self.emitted.clear()
        self.present()


class TestBuildFeedback(_Base):
    def test_pressing_build_shows_the_countdown_at_once(self):
        """The reported bug. Before the fix this band was EMPTY."""
        self.stock()
        self.press_build()
        band = self.emitted.text_with("building")
        self.assertTrue(band, "pressing Build left the action band empty")
        self.assertIn("building 0:", band[0])

    def test_pressing_build_spends_the_materials(self):
        self.stock(salvage=100, bio=5)
        self.press_build()
        # Bio Beacon: bio_sample x1, salvage x5 (recipes.amd)
        self.assertEqual(get_inventory_value(self.ship.id, "salvage", 0), 95)
        self.assertEqual(get_inventory_value(self.ship.id, "bio_sample", 0), 4)

    def test_a_finished_build_says_so_and_says_where_it_went(self):
        """The second reported bug: no indication it was built and sent to cargo."""
        self.stock()
        self.press_build()
        self.present(70)          # past the 30s build
        self.emitted.clear()
        self.present()
        band = self.emitted.text_with("Built")
        self.assertTrue(band, "a finished build left the action band empty")
        self.assertIn("now in Cargo", band[0])
        self.assertIn("shark", band[0])

    def test_the_finished_beacon_really_is_in_cargo(self):
        """The panel's claim and the Cargo tab must agree - same name, same object."""
        self.stock()
        self.press_build()
        self.present(70)
        built = get_inventory_value(self.ship.id, "beacon_built", [])
        self.assertEqual(len(built), 1)
        cargo = recipes.cargo_list(self.ship.id)
        names = [c["name"] for c in cargo if c["ckind"] == "beacon"]
        self.assertEqual(names, [recipes.fabrication_last_built(self.ship.id)])

    def test_the_result_line_clears_when_the_next_build_starts(self):
        """It reports the LAST build, not any build ever."""
        self.stock()
        self.press_build()
        self.present(70)
        self.assertNotEqual(recipes.fabrication_last_built(self.ship.id), "")
        self.open_tab()
        self.press_build()
        self.assertEqual(recipes.fabrication_last_built(self.ship.id), "")
        self.assertFalse(self.emitted.text_with("Built"))

    def test_no_materials_means_no_build_button(self):
        self.stock(salvage=0, bio=0)
        self.assertFalse(self.emitted.button_named("Build"))
        self.assertTrue(self.emitted.text_with("need materials"))


if __name__ == "__main__":
    unittest.main()
