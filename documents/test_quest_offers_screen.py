"""Offers and Quests are ONE screen (quest_tab.mast's quest_tab_screen) - driven for real.

Compiles the shipped quest_tab.mast, opens it in each mode on a Comms console, clicks a
list row and the Accept button the way the engine sends them, and asserts what moved:

  * Offers lists the untaken job and draws its description; Quests does not list it.
  * Accept on Offers makes the job ACTIVE.
  * After that, Quests lists it and Offers does not.

    cd documents
    PYTHONPATH=../../sbs_utils python -m unittest test_quest_offers_screen
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs
sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils.agent import Agent, clear_shared
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the gui/route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.quest import quest_add, quest_get_state, QuestState
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.spaceobject import SpaceObject

HERE = os.path.dirname(os.path.abspath(__file__))
CID = 0x8080000000000001          # a real console id (the console bit set)


def _source(mode):
    # The mode and console are baked into the source: Gui.push presents at once, so main
    # has reached the screen before a test could set a variable.
    return "\n".join([
        "shared SETTINGS = {}",
        "import quest_tab.mast",
        'CONSOLE_SELECT = "comms"',
        f'quest_tab_mode = "{mode}"',
        "jump quest_tab_screen",
        ""])


class ScreenPage(StoryPage):
    story = None


class _Sent:
    """What the page sent on the last present, by kind: (tag, props)."""

    def __init__(self):
        self.texts, self.buttons, self.clicks = [], [], []

    def install(self):
        self._orig = {}
        for name, sink in (("send_gui_text", self.texts),
                           ("send_gui_button", self.buttons),
                           ("send_gui_clickregion", self.clicks)):
            self._orig[name] = getattr(mock_sbs, name)
            setattr(mock_sbs, name, self._rec(sink, self._orig[name]))

    def _rec(self, sink, orig):
        def fn(client_id, parent, tag, props, *rect):
            sink.append((tag, props or ""))
            return orig(client_id, parent, tag, props, *rect)
        return fn

    def remove(self):
        for name, fn in self._orig.items():
            setattr(mock_sbs, name, fn)

    def clear(self):
        self.texts.clear(); self.buttons.clear(); self.clicks.clear()

    def all_text(self):
        return " ".join(p for _, p in self.texts + self.buttons)


class QuestScreenTests(unittest.TestCase):
    def setUp(self):
        from sbs_utils.handlerhooks import reset_mission_state
        reset_mission_state()
        clear_shared()
        SpaceObject.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)

        self.ship = npc_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser",
                              "behav_npcship")
        mock_sbs.assign_client_to_ship(CID, self.ship.id)
        quest_add(self.ship.id, "rocks", "Rock Breakers",
                  "Demolish the hazard rocks clogging the lane.")

        self.sent = _Sent()
        self.sent.install()
        self.errors = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.errors.append
        self.page = None

    def tearDown(self):
        self.sent.remove()
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        ScreenPage.story = None
        FrameContext.task = FrameContext.page = FrameContext.mast = None
        FrameContext.context = None
        SpaceObject.clear()

    # --- driving -------------------------------------------------------------------
    def open(self, mode):
        story = MastStory()
        story.basedir = HERE
        errors = story.compile(_source(mode), "questscreen_" + mode, story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        ScreenPage.story = story
        FrameContext.mast = story
        Gui.clients = {}
        Gui.widget_list_sent = {}
        self.page = ScreenPage()
        Gui.push(CID, self.page)
        self.present()

    def present(self, n=2):
        for _ in range(n):
            self.sent.clear()
            mock_sbs.sim._time_tick_counter += 30
            FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                           FakeEvent(CID, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(CID, "gui_present"))
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")

    def click(self, tag):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(CID, "gui_message"))
        Gui.on_message(FakeEvent(client_id=CID, tag="gui_message", sub_tag=tag))
        self.present()

    def qbox(self):
        return self.page.gui_task.get_variable("qbox")

    def select_title(self, title):
        """Click list rows (as the engine would) until the one titled `title` is held."""
        for tag, _ in list(self.sent.clicks):
            if not tag.endswith("__click"):
                continue
            self.click(tag)
            v = self.qbox().get_value()
            if v is not None and getattr(v, "get", None) and v.get("title") == title:
                return v
        self.fail(f"no list row titled {title!r}")

    def press(self, label):
        for tag, props in self.sent.buttons:
            if label in props:
                self.click(tag)
                return
        self.fail(f"no button {label!r}; buttons: {[p for _, p in self.sent.buttons]}")

    def titles(self):
        out = []
        for item in self.qbox().items or []:
            data = getattr(item, "data", None) if not hasattr(item, "get") else item
            if data is not None and data.get("key") is not None:
                out.append(data.get("title"))
        return out

    # --- the screen ----------------------------------------------------------------
    def test_offers_lists_the_job_and_quests_does_not(self):
        self.open("offers")
        self.assertEqual(self.titles(), ["Rock Breakers"])
        self.open("taken")
        self.assertEqual(self.titles(), [])

    def test_selecting_an_offer_shows_its_description(self):
        self.open("offers")
        self.select_title("Rock Breakers")
        self.assertIn("hazard rocks", self.sent.all_text())

    def test_accept_on_offers_moves_the_job_to_quests(self):
        self.open("offers")
        self.select_title("Rock Breakers")
        self.press("Accept")
        self.assertEqual(int(quest_get_state(self.ship.id, "rocks")), int(QuestState.ACTIVE))
        self.assertEqual(self.titles(), [], "an accepted job left Offers")
        self.open("taken")
        self.assertEqual(self.titles(), ["Rock Breakers"])


if __name__ == "__main__":
    unittest.main()
