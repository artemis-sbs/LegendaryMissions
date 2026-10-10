"""`comms/enemy_surrender.mast`: "Take as prize", and a ship that strikes at home.

Two things, both driven through the REAL file (copied beside the real
`boarding/deck_wiring.mast` and compiled through MAST's own `import`), with the comms
buttons read as the engine is sent them and pressed as the engine presses them:

  * **"Take as prize" finishes what waits on the prize.** With the deck wiring loaded,
    on a ship a party could be sent aboard (or is aboard), the button sends the same
    story beat as the answer in her brig - `boarding_deck_take`, raw and as a quest
    milestone - so `Done when: signal boarding_deck_take` completes. With a party
    aboard it is that ending: they come home and she is taken, ONCE. Without the deck
    wiring, or on a hull with no plan, or with no deck art, it sends nothing and is
    exactly what it was.

  * **A ship that surrenders within 500 of her spawn point is not deleted at once.**
    She gets `SURRENDER_HOME_GRACE` seconds (180). A ship that had to fly home is still
    removed on arriving, as before.

    cd ../sbs_utils && MAST_LEAVE_LOGS=1 PYTHONPATH=.;../LegendaryMissions \\
        python -m unittest comms.test_take_as_prize

(Run from OUTSIDE this folder: `DEBUG()` opens `debug.log` with mode "w" in the current
folder, and this repo tracks one.)
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import shutil
import sys
import tempfile
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

COMMS_DIR = os.path.dirname(os.path.abspath(__file__))
LM = os.path.dirname(COMMS_DIR)

from sbs_utils.agent import Agent
from sbs_utils.consoledispatcher import ConsoleDispatcher
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.gui import Gui
from sbs_utils.handlerhooks import reset_mission_state
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the route nodes)
import sbs_utils.mast_sbs.mast_sbs_procedural  # noqa: F401
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural import boarding as B
from sbs_utils.procedural import boarding_deckplan as D
from sbs_utils.procedural import crew
from sbs_utils.procedural import tilemap as T
from sbs_utils.procedural import tilemap_art as TA
from sbs_utils.procedural.amd_doc import amd_document, amd_section
from sbs_utils.procedural.amd_mission import amd_mission_data
from sbs_utils.procedural.grid import grid_merge_ascii
from sbs_utils.procedural.internal_damage import grid_interior_reset
from sbs_utils.procedural.inventory import set_inventory_value
from sbs_utils.procedural.links import link
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.quest import QuestState, quest_get_state
from sbs_utils.procedural.quest_driver import quest_grant_amd, quest_on_signal
from sbs_utils.procedural.roles import has_role
from sbs_utils.procedural.routes import follow_route_select_comms
from sbs_utils.procedural.science import science_set_scan_data
from sbs_utils.procedural.sides import side_ensure, side_surrender
from sbs_utils.procedural.signal import signal_observe, signal_unobserve
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.tickdispatcher import TickDispatcher

PRIZE_HELM = 0x8000000000000011
PRIZE_BUTTON = "Take as prize"
BOARD_BUTTON = "Send a boarding party"

PRIZE_QUEST = """# [Mission](mission)

## [Quests](quests)

### [Take the Gull](prize)
---
Beat
Starts when: at once
Done when: signal boarding_deck_take
---
Bring her in.
"""


def _prize_story(wiring):
    """The real files, through `import`; what LegendaryMissions' other files give them
    (two colors, the stats, the difficulty); the park; and the standing-orders label
    the `prefabs` addon would bring."""
    return "\n".join([
        'shared raider_color = "red"',
        'shared surrender_color = "yellow"',
        "shared game_stats = {}",
        "shared DIFFICULTY = 5",
        "import deck_wiring.mast" if wiring else "",
        "import enemy_surrender.mast",
        "import harness_enable.mast",
        "gui_text('$text:harness;')",
        "await gui()",
        "",
        "=== objective_protect_area",
        "    yield success",
        "",
    ])


class PrizePage(StoryPage):
    story = None


class _PrizeBase(unittest.TestCase):
    wiring = True
    hull = "pirate_brigantine"
    art = True
    at_home = False

    def setUp(self):
        reset_mission_state()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        DeleteQueue.clear()
        TickDispatcher.clear()
        crew.crew_clear()
        grid_interior_reset()
        T.tilemap_clear_tilesets()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)

        with open(os.path.join(LM, "races", "pirate_brigantine.grid"), encoding="utf-8") as f:
            grid_merge_ascii(f.read(), "races")

        self._orig_find = TA.tilemap_art_find
        TA.tilemap_art_find = lambda name: ("media/tileart/" + name) if self.art else None
        self._orig_art = D._deck_art
        D._deck_art = lambda tileset: bool(self.art)

        self.buttons = []
        self._orig_btn = mock_sbs.send_comms_button_info
        self._orig_sel = mock_sbs.send_comms_selection_info
        mock_sbs.send_comms_button_info = \
            lambda ship, color, text, tag: self.buttons.append((text, tag))
        mock_sbs.send_comms_selection_info = \
            lambda ship, face, color, title: self.buttons.clear()

        # THE REAL FILES, side by side so one `import` each finds them.
        self.tmp = tempfile.mkdtemp(prefix="take_as_prize_")
        shutil.copyfile(os.path.join(COMMS_DIR, "enemy_surrender.mast"),
                        os.path.join(self.tmp, "enemy_surrender.mast"))
        shutil.copyfile(os.path.join(LM, "boarding", "deck_wiring.mast"),
                        os.path.join(self.tmp, "deck_wiring.mast"))
        # Comms OPENS on a neutral ship only where something enables it: in the game
        # that is `internal_comms`, or the deck wiring's own route for a ship that can
        # be boarded. Here it is said outright, so the button under test can be reached
        # on a hull with no plan too.
        with open(os.path.join(self.tmp, "harness_enable.mast"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write('//enable/comms if has_role(COMMS_ORIGIN_ID, "__player__")\n')
        story = MastStory()
        story.basedir = self.tmp
        errors = story.compile(_prize_story(self.wiring), "takeasprize", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        PrizePage.story = story
        FrameContext.mast = story

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append
        self.seen = []
        signal_observe(self._watch)

        side_ensure("tsn")
        side_ensure("pirate")
        self.ship = to_object(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        self.prize = to_object(npc_spawn(3000, 0, 0, "Black Gull", "pirate", self.hull,
                                         "behav_npcship"))
        self.prize.spawn_pos = mock_sbs.vec3(3000.0 if self.at_home else 20000.0, 0.0, 0.0)
        side_surrender(self.prize)
        science_set_scan_data(self.ship, self.prize, "identified")

        self.server = PrizePage()
        Gui.push(0, self.server)
        mock_sbs.assign_client_to_ship(PRIZE_HELM, self.ship.id)
        self.page = PrizePage()
        Gui.push(PRIZE_HELM, self.page)
        set_inventory_value(PRIZE_HELM, "CONSOLE_TYPE", "helm")
        link(self.ship.id, "consoles", PRIZE_HELM)
        crew.crew_assign(PRIZE_HELM, self.ship.id, "helm")
        self.present()
        # A quest that waits on the prize - granted AFTER the first present, which
        # starts the story and resets the shared agent.
        doc = amd_document(PRIZE_QUEST, data_parser=amd_mission_data)
        quest_grant_amd(Agent.SHARED_ID, amd_section(doc, "quests"))

    def tearDown(self):
        signal_unobserve(self._watch)
        mock_sbs.send_comms_button_info = self._orig_btn
        mock_sbs.send_comms_selection_info = self._orig_sel
        MastScheduler.on_runtime_error = self._orig_rte
        TA.tilemap_art_find = self._orig_find
        D._deck_art = self._orig_art
        Gui.clients = {}
        Gui.widget_list_sent = {}
        PrizePage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        TickDispatcher.clear()
        crew.crew_clear()
        reset_mission_state()
        grid_interior_reset()
        T.tilemap_clear_tilesets()
        FrameContext.context = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- driving it ------------------------------------------------------------------
    def _watch(self, name, data=None):
        self.seen.append((name, dict(data) if isinstance(data, dict) else data))
        if name == "quest_signal" and isinstance(data, dict):
            # What `quests/quest_driver.mast` does with it, word for word (pinned by
            # `test_the_quest_route_is_still_that_call`).
            quest_on_signal(data.get("SIGNAL_NAME"))

    def count(self, name):
        return len([1 for n, _ in self.seen if n == name])

    def present(self, n=2):
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                           FakeEvent(0, "gui_present"))
            self.server.gui_state = "repaint"
            self.server.present(FakeEvent(0, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(PRIZE_HELM, "gui_present"))
            TickDispatcher.dispatch_tick()
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def select(self):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(PRIZE_HELM, "select_space_object"))
        follow_route_select_comms(self.ship.id, self.prize.id)
        self.present()

    def texts(self):
        return [t for t, _g in self.buttons]

    def press(self, text):
        tags = [g for t, g in self.buttons if t == text]
        self.assertTrue(tags, f"no comms button {text!r}: {self.texts()}")
        ev = FakeEvent(client_id=PRIZE_HELM, tag="press_comms_button", sub_tag=tags[0],
                       origin_id=self.ship.id, selected_id=self.prize.id)
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, ev)
        ConsoleDispatcher.dispatch_message(ev, "comms_target_UID")
        self.present()

    def quest(self):
        return quest_get_state(Agent.SHARED_ID, "prize")

    def milestones(self):
        return [d.get("SIGNAL_NAME") for n, d in self.seen
                if n == "quest_signal" and isinstance(d, dict)]


class TakeAsPrizeFinishesTheQuest(_PrizeBase):

    def test_the_quest_route_is_still_that_call(self):
        with open(os.path.join(LM, "quests", "quest_driver.mast"), encoding="utf-8") as f:
            text = f.read()
        at = text.index("//shared/signal/quest_signal")
        self.assertIn("quest_on_signal(SIGNAL_NAME)", text[at:at + 600])

    def test_the_button_takes_her_and_the_quest_is_done(self):
        self.assertEqual(self.quest(), QuestState.ACTIVE)
        self.select()
        self.assertIn(PRIZE_BUTTON, self.texts())
        self.press(PRIZE_BUTTON)
        self.assertEqual(self.prize.side, "tsn")
        self.assertTrue(has_role(self.prize, "prefab_npc_defender"))
        self.assertEqual(self.count("boarding_deck_take"), 1)
        self.assertEqual(self.milestones(), ["boarding_deck_take"])
        self.assertEqual(self.quest(), QuestState.COMPLETE)

    def test_with_a_party_aboard_it_is_the_ending_and_happens_once(self):
        self.select()
        self.press(BOARD_BUTTON)
        self.assertIsNotNone(B.boarding_visiting(), "the button opened no party")
        self.assertEqual(D.boarding_deck_target(), self.prize.id)
        self.select()
        self.press(PRIZE_BUTTON)
        self.assertIsNone(B.boarding_visiting(), "the party was left aboard")
        self.assertIsNone(D.boarding_deck_target())
        self.assertEqual(self.count("boarding_visit_ended"), 1)
        self.assertEqual(self.prize.side, "tsn")
        self.assertTrue(has_role(self.prize, "prefab_npc_defender"))
        self.assertEqual(self.count("boarding_deck_take"), 1)
        self.assertEqual(self.milestones(), ["boarding_deck_take"])
        self.assertEqual(self.quest(), QuestState.COMPLETE)


class WithNoDeckWiring(_PrizeBase):
    """The `comms` addon without the `boarding` addon: the button is what it was."""
    wiring = False

    def test_she_is_taken_and_nothing_is_sent(self):
        self.assertIsNot(Agent.SHARED.get_inventory_value("BOARDING_DECK_WIRING"), True)
        self.select()
        self.assertNotIn(BOARD_BUTTON, self.texts())
        self.press(PRIZE_BUTTON)
        self.assertEqual(self.prize.side, "tsn")
        self.assertTrue(has_role(self.prize, "prefab_npc_defender"))
        self.assertEqual(self.count("boarding_deck_take"), 0)
        self.assertEqual(self.milestones(), [])
        self.assertEqual(self.quest(), QuestState.ACTIVE)


class OnAHullNobodyCouldBoard(_PrizeBase):
    hull = "pirate_longbow"            # the engine's grid data gives her no rooms

    def test_she_is_taken_and_nothing_is_sent(self):
        self.assertFalse(D.boarding_deck_ready(self.prize))
        self.select()
        self.press(PRIZE_BUTTON)
        self.assertEqual(self.prize.side, "tsn")
        self.assertEqual(self.count("boarding_deck_take"), 0)
        self.assertEqual(self.milestones(), [])


class WithNoDeckArt(_PrizeBase):
    art = False

    def test_she_is_taken_and_nothing_is_sent(self):
        self.select()
        self.press(PRIZE_BUTTON)
        self.assertEqual(self.prize.side, "tsn")
        self.assertEqual(self.count("boarding_deck_take"), 0)
        self.assertEqual(self.milestones(), [])


# --- a ship that strikes where she spawned ---------------------------------------------

class StruckAtHome(_PrizeBase):
    at_home = True

    def test_she_is_not_deleted_at_once(self):
        """`agent_c3d_report.md` defect 5: gone in under 8 seconds."""
        prize = self.prize.id
        self.present(12)                                 # two passes of the task
        self.assertIsNotNone(to_object(prize), "deleted where she struck")
        self.select()
        self.assertIn(PRIZE_BUTTON, self.texts())
        self.assertIn(BOARD_BUTTON, self.texts())

    def test_she_is_still_there_two_minutes_on_and_gone_after_the_grace(self):
        prize = self.prize.id
        self.present(120)
        self.assertIsNotNone(to_object(prize))
        self.present(75)                                 # 180 s and two passes more
        self.assertIsNone(to_object(prize), "never removed")

    def test_taken_as_a_prize_in_that_time_she_stays(self):
        prize = self.prize.id
        self.select()
        self.press(PRIZE_BUTTON)
        self.present(200)
        self.assertIsNotNone(to_object(prize))
        self.assertEqual(self.prize.side, "tsn")

    def test_a_mission_can_set_the_grace(self):
        prize = self.prize.id
        Agent.SHARED.set_inventory_value("SURRENDER_HOME_GRACE", 20)
        self.present(12)
        self.assertIsNotNone(to_object(prize))
        self.present(25)
        self.assertIsNone(to_object(prize))


class FlownHome(_PrizeBase):
    def test_a_ship_that_had_to_fly_home_is_removed_on_arriving_as_before(self):
        prize = self.prize.id
        self.present(7)
        self.assertEqual(self.prize.data_set.get("throttle", 0), 1.5)
        self.assertIsNotNone(to_object(prize))
        mock_sbs.sim.space_objects[prize].pos.x = 19800.0
        self.present(7)
        self.assertIsNone(to_object(prize), "a ship that flew home waited at the door")


if __name__ == "__main__":
    unittest.main()
