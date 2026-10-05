"""The Quest Log's right-hand pane shows what the writer wrote.

Found by the lesson "Markdown in twenty minutes", which measured what a quest's
description becomes on the crew's screen, and confirmed in the real engine 2026-10-04:

  * Selecting an ARC showed "Select a quest from the list." The screen hands the list
    box's HEADER to quest_log_parent_summary, which wanted the header's data.
  * A `{word}` in a description was a runtime error on the console showing it: the
    screen kept the text in a variable, and a string assigned in MAST is re-run as an
    f-string.
  * `40 years ago she was the pride of the fleet.` was drawn `1. years ago ...`;
    `[Static] Is anyone aboard?` was not drawn at all; `$500 says ...` and `-Find her.`
    each lost their first word; a plain line under a list was drawn `-Then come home.`

This drives the SHIPPED quest_tab.mast: the mission text is read by the game's own reader,
granted the way a template mission grants it, and each row is selected in turn.

    PYTHONPATH=../sbs_utils python -m unittest documents.test_quest_log_pane
"""
import os
import sys
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import cosmos_dev.mock.sbs as mock_sbs
sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils.agent import Agent, clear_shared
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast import Mast
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.spaceobject import SpaceObject

DOCS = os.path.dirname(os.path.abspath(__file__))
CID = 0x8080000000000001

SOURCE = "\n".join([
    "shared SETTINGS = {}",
    "import quest_tab.mast",
    'CONSOLE_SELECT = "comms"',
    'quest_tab_mode = "taken"',
    "jump quest_tab_screen",
    ""])

MISSION = """# [Sample Mission](sample_mission)

## [Quests](quests)

### [First Contact](first_contact)
---
Arc
Scope: shared
Starts when: at once
---
A derelict has drifted into the sector. Find out what happened to it.

#### [Find the Derelict](find)
---
Scope: shared
Starts when: at once
Done when: signal derelict_found
Then: reveal first_contact/study
---
BODY

#### [Study the Derelict](study)
---
Scope: shared
Starts when: revealed
Done when: signal derelict_scanned
---
Science should take a full scan of the hull.
"""


class _PanePage(StoryPage):
    story = None


class QuestLogPane(unittest.TestCase):
    def setUp(self):
        self.leave = Mast.leave_logs_alone
        Mast.leave_logs_alone = True
        self.addCleanup(setattr, Mast, "leave_logs_alone", self.leave)

    def pane(self, body):
        """{row title: [text of each line the pane draws]} and the runtime errors."""
        from sbs_utils.handlerhooks import reset_mission_state
        from sbs_utils.procedural.amd_doc import amd_section
        from sbs_utils.procedural.amd_mission import amd_mission_data
        from sbs_utils.procedural.quest import document_get_amd_file
        from sbs_utils.procedural.quest_driver import quest_grant_amd

        reset_mission_state()
        SpaceObject.clear()
        clear_shared()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)
        ship = npc_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser", "behav_npcship")
        mock_sbs.assign_client_to_ship(CID, ship.id)

        doc = document_get_amd_file(None, content=MISSION.replace("BODY", body),
                                    data_parser=amd_mission_data)
        quest_grant_amd(Agent.SHARED_ID, amd_section(doc, "quests"))

        sent, errors = [], []
        real_send = mock_sbs.send_gui_text
        real_error = MastScheduler.on_runtime_error

        def record(*args):
            sent.append(args)
            return real_send(*args)

        mock_sbs.send_gui_text = record
        MastScheduler.on_runtime_error = errors.append
        out = {}
        try:
            story = MastStory()
            story.basedir = DOCS
            self.assertEqual(story.compile(SOURCE, "pane", story), [])
            story.compiler_errors = []
            _PanePage.story = story
            FrameContext.mast = story
            page = _PanePage()
            Gui.push(CID, page)

            def present():
                for _ in range(2):
                    del sent[:]
                    mock_sbs.sim._time_tick_counter += 30
                    FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                                   FakeEvent(CID, "gui_present"))
                    page.gui_state = "repaint"
                    page.present(FakeEvent(CID, "gui_present"))

            present()
            count = len(page.gui_task.get_variable("qbox").items or [])
            for index in range(count):
                page.gui_task.get_variable("qbox").set_selected_index(index, False)
                present()
                row = page.gui_task.get_variable("qbox").get_value()
                if row is None:
                    continue
                data = row if hasattr(row, "get") else getattr(row, "data", None)
                title = data.get("title") if hasattr(data, "get") else None
                tag = str(page.gui_task.get_variable("qdesc").tag)
                lines = []
                for args in sent:
                    if str(args[2]).startswith(tag):
                        props = str(args[3])
                        lines.append(props.split("`")[1] if "`" in props else props)
                out[title or getattr(row, "label", None) or index] = lines
        finally:
            mock_sbs.send_gui_text = real_send
            MastScheduler.on_runtime_error = real_error
            Gui.clients = {}
            Gui.widget_list_sent = {}
            _PanePage.story = None
            FrameContext.task = FrameContext.page = FrameContext.mast = None
            SpaceObject.clear()
        return out, errors

    def body(self, text):
        panes, errors = self.pane(text)
        self.assertEqual(errors, [])
        return panes["Find the Derelict"]

    def test_an_arc_shows_its_own_description_and_its_steps(self):
        panes, errors = self.pane("Fly out and locate the drifting hulk.")
        self.assertEqual(errors, [])
        arc = panes["First Contact"]
        self.assertIn("A derelict has drifted into the sector. Find out what happened to it.", arc)
        self.assertIn("Find the Derelict", arc)
        self.assertNotIn("Select a quest from the list.", arc)

    def test_the_hint_for_hidden_steps_is_a_line_of_its_own(self):
        arc = self.pane("Fly out.")[0]["First Contact"]
        self.assertIn("... more to follow", arc)
        self.assertNotIn("-... more to follow", arc)
        self.assertNotIn("- ... more to follow", arc)

    def test_a_word_in_curly_brackets_is_text(self):
        self.assertIn("Fly out and locate the {drifting} hulk.",
                      self.body("Fly out and locate the {drifting} hulk."))

    def test_a_sentence_that_starts_with_a_number_keeps_it(self):
        self.assertIn("40 years ago she was the pride of the fleet.",
                      self.body("40 years ago she was the pride of the fleet."))

    def test_a_numbered_list_is_still_a_list(self):
        lines = self.body("1. Find her.\n2. Scan her.")
        self.assertEqual(lines[-2:], ["1. Find her.", "2. Scan her."])

    def test_a_word_in_square_brackets_does_not_cost_the_line(self):
        self.assertIn("[Static] Is anyone aboard?", self.body("[Static] Is anyone aboard?"))

    def test_a_link_to_the_web_is_drawn_as_typed(self):
        typed = "[Report](https://example.com/report) is where to start."
        self.assertIn(typed, self.body(typed))

    def test_a_dollar_sign_does_not_cost_the_word(self):
        self.assertIn("$500 says she is not empty.", self.body("$500 says she is not empty."))

    def test_a_hyphen_with_no_space_is_not_a_list(self):
        self.assertIn("-Find her.", self.body("-Find her."))

    def test_a_list_and_the_plain_line_under_it(self):
        lines = self.body("- Find her.\n- Scan her.\nThen come home.")
        self.assertEqual(lines[-3:], ["- Find her.", "- Scan her.", "Then come home."])


if __name__ == "__main__":
    unittest.main()
