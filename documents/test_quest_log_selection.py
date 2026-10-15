"""The Quest Log keeps the quest you selected selected, whatever else changes.

Seen in the real engine while filming: the selected row in the Quests screen moved by
itself. The log repaints whenever any listed quest changes state, from anywhere, and each
repaint re-sorts the rows (active, then complete, then failed). The selection was carried
across by INDEX, so when a quest above the selected one completed, the same index landed
on a different quest.

This drives the SHIPPED quest_tab.mast: three game quests, the third selected, then the
first completes - which moves it below the other two.

    PYTHONPATH=../sbs_utils python -m unittest documents.test_quest_log_selection
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

### [Alpha](alpha)
---
Scope: shared
Starts when: at once
Done when: signal alpha_done
---
The first.

### [Bravo](bravo)
---
Scope: shared
Starts when: at once
Done when: signal bravo_done
---
The second.

### [Charlie](charlie)
---
Scope: shared
Starts when: at once
Done when: signal charlie_done
---
The third.
"""


class _LogPage(StoryPage):
    story = None


class QuestLogSelection(unittest.TestCase):
    def setUp(self):
        from sbs_utils.handlerhooks import reset_mission_state
        from sbs_utils.procedural.amd_doc import amd_section
        from sbs_utils.procedural.amd_mission import amd_mission_data
        from sbs_utils.procedural.quest import document_get_amd_file
        from sbs_utils.procedural.quest_driver import quest_grant_amd

        leave = Mast.leave_logs_alone
        Mast.leave_logs_alone = True
        self.addCleanup(setattr, Mast, "leave_logs_alone", leave)

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

        doc = document_get_amd_file(None, content=MISSION, data_parser=amd_mission_data)
        quest_grant_amd(Agent.SHARED_ID, amd_section(doc, "quests"))

        self.errors = []
        real_error = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.errors.append
        self.addCleanup(setattr, MastScheduler, "on_runtime_error", real_error)

        story = MastStory()
        story.basedir = DOCS
        self.assertEqual(story.compile(SOURCE, "selection", story), [])
        story.compiler_errors = []
        _LogPage.story = story
        FrameContext.mast = story
        self.page = _LogPage()
        Gui.push(CID, self.page)
        self.addCleanup(self._teardown)
        self.present()

    def _teardown(self):
        Gui.clients = {}
        Gui.widget_list_sent = {}
        _LogPage.story = None
        FrameContext.task = FrameContext.page = FrameContext.mast = None
        SpaceObject.clear()

    def present(self, n=3):
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                           FakeEvent(CID, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(CID, "gui_present"))
        self.assertEqual(self.errors, [], f"MAST runtime errors: {self.errors}")

    def qbox(self):
        return self.page.gui_task.get_variable("qbox")

    def titles(self):
        out = []
        for item in self.qbox().items or []:
            out.append(item.get("title") if hasattr(item, "get") else getattr(item, "label", None))
        return out

    def selected_title(self):
        row = self.qbox().get_value()
        return row.get("title") if hasattr(row, "get") else None

    def select(self, title):
        self.qbox().set_selected_index(self.titles().index(title), False)
        self.present()
        self.assertEqual(self.selected_title(), title)

    def test_the_selection_follows_the_quest_when_the_list_reorders(self):
        self.assertEqual(self.titles(), ["Game", "Alpha", "Bravo", "Charlie"])
        self.select("Charlie")
        before = self.qbox()
        from sbs_utils.procedural.quest_driver import quest_mark_complete
        quest_mark_complete(Agent.SHARED_ID, "alpha")
        self.present(4)
        self.assertIsNot(self.qbox(), before, "the log did not repaint on the change")
        # Completed quests sort after active ones, so Charlie moved up one row.
        self.assertEqual(self.titles(), ["Game", "Bravo", "Charlie", "Alpha"])
        self.assertEqual(self.selected_title(), "Charlie",
                         "the selection stayed on the old INDEX instead of the quest")

    def test_a_quest_that_left_the_list_leaves_nothing_selected(self):
        """Not its neighbor - which is what the selection hint's own index would pick."""
        self.select("Bravo")
        from sbs_utils.procedural.quest import quest_set_key, QuestState
        quest_set_key(Agent.SHARED_ID, "bravo", "state", QuestState.SECRET)
        self.present(4)
        # Charlie now sits where Bravo was.
        self.assertEqual(self.titles(), ["Game", "Alpha", "Charlie"])
        self.assertIsNone(self.qbox().get_value(),
                          f"selected {self.selected_title()!r}, the quest's neighbor")


if __name__ == "__main__":
    unittest.main()
