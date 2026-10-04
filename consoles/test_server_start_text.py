"""A mission's description may contain a brace.

Found by the lesson "Just enough MAST". The server's start screen built its text as a
quoted string in `server_console.mast`, with the description interpolated into it. An
assigned string is formatted, so `the {last} log` in a description was a FORMAT String
error on the first frame and the start screen never drew. No lint, no compile error.

Runs a real MAST assignment through the real helper, and checks the real `.mast` uses it.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_server_start_text
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

CONSOLES = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CONSOLES)

from sbs_utils.agent import clear_shared
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast import Mast
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast.mast_node import MastDataObject
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401

import server_console

SEEN = []
DESC = ["A dying hulk and a log."]


def sst_overview():
    return MastDataObject({"display_name": "Salvage Run", "desc": DESC[0]})


def sst_show(text):
    SEEN.append(text)


MastGlobals.import_python_function(server_console.server_start_text)
MastGlobals.import_python_function(sst_overview)
MastGlobals.import_python_function(sst_show)

STORY = "o = sst_overview()\nSTART_TEXT = server_start_text(o)\nsst_show(START_TEXT)\n"


class _Scheduler(MastScheduler):
    errors = []

    def runtime_error(self, message):
        _Scheduler.errors.append(str(message))


class StartTextTests(unittest.TestCase):
    def run_story(self, desc):
        DESC[0] = desc
        del SEEN[:]
        _Scheduler.errors = []
        mast = Mast()
        clear_shared()
        self.assertEqual(mast.compile(STORY, "sst", mast), [])
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        FrameContext.mast = mast
        self.addCleanup(setattr, FrameContext, "mast", None)
        self.addCleanup(setattr, FrameContext, "context", None)
        runner = _Scheduler(mast)
        runner.start_task("main")
        for _ in range(10):
            if not runner.tick():
                break
        return list(SEEN), list(_Scheduler.errors)

    def setUp(self):
        mock_sbs.create_new_sim()

    def test_a_plain_description(self):
        seen, errors = self.run_story("A dying hulk and a log.")
        self.assertEqual(errors, [])
        self.assertEqual(seen, ["$t Salvage Run:\n\nA dying hulk and a log."])

    def test_a_description_with_braces_is_shown_as_written(self):
        for desc in ("Bring home the {last} log.", "A lone {", "} then {x} and {{y}}"):
            with self.subTest(desc=desc):
                seen, errors = self.run_story(desc)
                self.assertEqual(errors, [])
                self.assertEqual(seen, ["$t Salvage Run:\n\n" + desc])

    def test_the_server_console_uses_it(self):
        with open(os.path.join(CONSOLES, "server_console.mast"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("START_TEXT = server_start_text(mission_overview)", text)
        self.assertNotIn("{mission_overview.desc}", text)


class PickerRowTests(unittest.TestCase):
    """The row the mission picker draws for a map: its name and its description.

    This is the one the lesson hit. Both widgets fill `{name}` in the text they are given,
    so `a {missing} lifeboat` in a map's description - or a brace in its name - was a
    FORMAT String error against the picker's own `await gui()`, on every frame.
    """

    STORY = "\n".join([
        "item = sst_map()",
        "gui_section(style='area: 0, 0, 100, 100;')",
        "main_mission_select_template(item)",
        "await gui()",
        ""])

    def setUp(self):
        from sbs_utils.gui import Gui
        from sbs_utils.mast.maststory import MastStory
        from sbs_utils.mast_sbs.maststorypage import StoryPage
        from sbs_utils.spaceobject import SpaceObject
        mock_sbs.create_new_sim()
        clear_shared()
        SpaceObject.clear()
        Gui.clients = {}
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        MastGlobals.import_python_function(server_console.main_mission_select_template)
        MastGlobals.import_python_function(sst_map)
        story = MastStory()
        self.assertEqual(story.compile(self.STORY, "pickerrow", story), [])

        class _Page(StoryPage):
            pass

        _Page.story = story
        FrameContext.mast = story
        self.errors = []
        orig = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.errors.append
        self.addCleanup(setattr, MastScheduler, "on_runtime_error", orig)
        self.sent = []
        for name in ("send_gui_text", "send_gui_text_area"):
            real = getattr(mock_sbs, name, None)
            if real is None:
                continue

            def tap(client_id, parent, tag, props, *a, _real=real, **k):
                self.sent.append(props)
                return _real(client_id, parent, tag, props, *a, **k)

            setattr(mock_sbs, name, tap)
            self.addCleanup(setattr, mock_sbs, name, real)
        self.page_class = _Page
        self.addCleanup(self.reset)

    def reset(self):
        from sbs_utils.gui import Gui
        Gui.clients = {}
        FrameContext.task = FrameContext.page = FrameContext.mast = None
        FrameContext.context = None

    def draw(self, name, desc):
        from sbs_utils.gui import Gui
        MAP[0] = MastDataObject({"display_name": name, "desc": desc})
        self.page = self.page_class()
        Gui.push(0, self.page)
        for _ in range(2):
            mock_sbs.sim._time_tick_counter += 30
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(0, "gui_present"))
        return " | ".join(str(s) for s in self.sent)

    def test_braces_in_the_description_and_the_name_are_drawn_as_written(self):
        drawn = self.draw("Salvage {Run}", "A dying hulk, a {missing} lifeboat.")
        self.assertEqual(self.errors, [], self.errors)
        self.assertIn("a {missing} lifeboat", drawn)
        self.assertIn("Salvage {Run}", drawn)
        self.assertNotIn("{{", drawn)

    def test_a_plain_map_is_unchanged(self):
        drawn = self.draw("Salvage Run", "A dying hulk and a log.")
        self.assertEqual(self.errors, [])
        self.assertIn("A dying hulk and a log.", drawn)


MAP = [None]


def sst_map():
    return MAP[0]


if __name__ == "__main__":
    unittest.main()
