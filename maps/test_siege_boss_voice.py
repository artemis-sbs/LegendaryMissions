"""A Siege boss file can carry its own Characters and Dialogue.

A boss is one `.amd` file, and Siege read it for two things only: the boss's own lines and
QUESTS. So an author who typed the two sections they knew from a mission file -
`## [Characters](characters)` and `## [Dialogue](dialogue)` - got no cast and no call, and
six jobs on the board named "Characters", "The Probe Queen", "Dialogue" and so on. A
custom boss could not have a person of her own or a hail scene.

What is driven here is what Siege runs:

* `siege_boss.py` itself (the scan, `siege_boss_quests`, `siege_boss_voice`), pointed at
  a temporary boss folder so the author's own `common_data/bosses` is never read;
* the REAL `//shared/signal/siege_enemies_low` route, sliced out of `siege.mast` rather
  than copied, so the test cannot pass against a mission that has drifted;
* the library's own quest driver, hail queue and outcome verbs for the call: the Beat in
  the boss file places it (`Action: queen hails queen_calls`), and the answer in the boss
  file's scene finishes that Beat (`; completes parley`).

And the three shipped bosses - which have neither section - are read from their real files
and must be granted the very node they always were.

    PYTHONPATH=../sbs_utils python -m unittest maps.test_siege_boss_voice
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import importlib.util
import os
import re
import shutil
import sys
import tempfile
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils.agent import Agent
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.gui import Gui
from sbs_utils.handlerhooks import reset_mission_audit, reset_mission_state
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast_sbs import mast_sbs_procedural  # noqa: F401  (MAST globals)
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural import hail as H
from sbs_utils.procedural.amd_dialogue import dialogue_scene
from sbs_utils.procedural.amd_lifeforms import lifeform_of_key
from sbs_utils.procedural.quest import QuestState, quest_get, quest_get_state
from sbs_utils.procedural.quest_driver import quest_tick_actions
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.signal import signal_emit, signal_register
from sbs_utils.procedural.spawn import player_spawn

HERE = os.path.dirname(os.path.abspath(__file__))
LM = os.path.dirname(HERE)
SIEGE_MAST = os.path.join(HERE, "siege.mast")
SHIPPED = os.path.join(HERE, "bosses")
SIGNAL = "siege_enemies_low"

# LM's own words (`Boss`, `Trigger:`, `Low:`...), declared the way the mission declares
# them. Idempotent: registering the same meaning twice is not a clash.
sys.path.insert(0, LM)
import lm_amd  # noqa: E402,F401

PROBE = """// A probe boss with a voice of her own.

# [Probe Queen](probe_queen)
---
Boss
Trigger: enemies_low
Low: 100%
Fleets: 0
---
The Probe Queen arrives to see whether a boss file can talk.

## [Sink the Morrigan](sink_morrigan)
---
Quest
Scope: shared
State: active
Parent: siege_mission
Done when: signal siege_won
---
Sink her.

## [The Queen Calls](parley)
---
Beat
Parent: siege_mission
Action:
  - queen hails queen_calls
---
The Probe Queen is on the line. Comms should answer her.

## [Characters](characters)

### [The Probe Queen](queen)
---
Face: terran_female
---
Flies the Morrigan.

### [First Mate Orla](orla)
---
Face: terran_female
---
Runs the deck.

## [Dialogue](dialogue)

### [The Queen Calls](queen_calls)
---
Speaker: queen
When: hail
Title: The Probe Queen
Priority: 9
---
@queen
% You held longer than I was told you would.

- [We do not stand down.]() ; completes parley
"""

# A second custom boss, so "only the SELECTED boss's people" has something to exclude.
OTHER = """# [Other Boss](other_boss)
---
Boss
Trigger: enemies_low
Low: 100%
Fleets: 0
---
Somebody else entirely.

## [Characters](characters)

### [The Understudy](understudy)
---
Face: terran_male
---
Never goes on.

## [Dialogue](dialogue)

### [The Understudy Speaks](understudy_speaks)
---
Speaker: understudy
When: hail
---
% Nobody selected me.
"""

# A route fires on the SERVER task, so main has to still be alive when the signal lands.
_MAIN = """shared BOSS_SELECT = "{boss}"
shared DIFFICULTY = 5
---sbv_test_idle
    await delay_sim(60)
    jump sbv_test_idle

"""


def _route(name):
    """The named shared-signal route, verbatim from siege.mast, up to the next column-0
    label."""
    with open(SIEGE_MAST, encoding="utf-8") as handle:
        source = handle.read()
    match = re.search(r"^//shared/signal/" + name + r"\b.*?(?=^(?://|=|@))",
                      source, re.S | re.M)
    assert match is not None, f"route //shared/signal/{name} not found in siege.mast"
    return match.group(0)


def _load_siege_boss(folders):
    """`siege_boss.py` as its own module, reading `folders` and nothing else, with its
    functions published to MAST the way the mission's `import siege_boss.py` does."""
    spec = importlib.util.spec_from_file_location("sbv_siege_boss",
                                                  os.path.join(HERE, "siege_boss.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.siege_boss_folders = lambda: list(folders)
    mod.siege_boss_shared_folder = lambda: folders[-1]
    for name in dir(mod):
        fn = getattr(mod, name)
        if (callable(fn) and not name.startswith("_")
                and getattr(fn, "__module__", "") == mod.__name__):
            MastGlobals.import_python_function(fn)
    return mod


class SiegePage(StoryPage):
    story = None


class _Base(unittest.TestCase):
    boss = "Probe Queen"

    def setUp(self):
        reset_mission_state()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        DeleteQueue.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)

        self.tmp = tempfile.mkdtemp(prefix="sbv_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        mission = os.path.join(self.tmp, "mission")
        authors = os.path.join(self.tmp, "authors")
        # The mission's own bosses are the SHIPPED files; the author's folder holds the
        # two custom ones, as `common_data/bosses` would.
        shutil.copytree(SHIPPED, mission)
        os.makedirs(authors)
        for fname, text in (("probe_queen.amd", PROBE), ("other_boss.amd", OTHER)):
            with open(os.path.join(authors, fname), "w", encoding="utf-8",
                      newline="\n") as f:
                f.write(text)
        self.sb = _load_siege_boss([mission, authors])

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append
        self.story = None

    def tearDown(self):
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        SiegePage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        reset_mission_state()
        FrameContext.context = None

    # --- the real route --------------------------------------------------------------

    def start(self):
        """Compile the sliced route and stand a server page up on it."""
        self.story = MastStory()
        errors = self.story.compile(_MAIN.format(boss=self.boss) + _route(SIGNAL),
                                    "sbv", self.story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        FrameContext.mast = self.story
        SiegePage.story = self.story
        self.page = SiegePage()
        Gui.push(0, self.page)
        self.present()
        # The compiler appends the route's `signal_register` to the END of main - past
        # the idle loop that keeps this cut-down main alive. Run the same registration
        # by hand, on main's task, exactly as it would.
        label = next(n for n in self.story.labels
                     if n.startswith("__route__shared/signal/" + SIGNAL))
        FrameContext.task = self.page.story_scheduler.tasks[0]
        signal_register(SIGNAL, label, True)
        FrameContext.task = None
        self.ship = player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser")

    def present(self, n=1):
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                           FakeEvent(0, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(0, "gui_present"))
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def boss_arrives(self):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        signal_emit(SIGNAL)
        self.present(2)



class TheShippedBosses(_Base):
    """Warlord, Ragnarok and Infestation have neither section, so nothing about how they
    are read or granted may change - and Continuous, which is never granted, likewise."""

    def test_they_are_granted_the_very_node_they_always_were(self):
        names = list(self.sb.siege_boss_scan())
        for name in ("Warlord", "Ragnarok", "Infestation"):
            self.assertIn(name, names)
            node = self.sb.siege_boss_get(name)
            self.assertIs(self.sb.siege_boss_quests(name), node, name)
            self.assertIsNone(self.sb.siege_boss_section(name, "characters"), name)
            self.assertIsNone(self.sb.siege_boss_section(name, "dialogue"), name)

    def test_they_have_no_voice_and_loading_it_makes_nothing(self):
        before = (len(role("lifeform")), len(Agent.all))
        for name in self.sb.siege_boss_scan():
            if name in ("Probe Queen", "Other Boss"):
                continue
            self.assertEqual(self.sb.siege_boss_voice(name), (0, 0), name)
        self.assertEqual((len(role("lifeform")), len(Agent.all)), before)

    def test_none_is_nothing(self):
        for sel in ("None", "", None, "No Such Boss"):
            self.assertIsNone(self.sb.siege_boss_quests(sel))
            self.assertEqual(self.sb.siege_boss_voice(sel), (0, 0))


class WarlordArrives(_Base):
    """The real route with a shipped boss selected: her objective is granted and there is
    no cast, no scene."""

    boss = "Warlord"

    def test_her_objective_is_granted_and_nobody_is_spawned(self):
        # No fleets or flagships in the harness: the prefab labels are the mission's.
        self.sb.siege_boss_fleet_count = lambda sel: 0
        self.sb.siege_boss_named = lambda sel: []
        for fn in (self.sb.siege_boss_fleet_count, self.sb.siege_boss_named):
            fn.__name__ = fn.__qualname__ = ("siege_boss_fleet_count"
                                             if fn is self.sb.siege_boss_fleet_count
                                             else "siege_boss_named")
            MastGlobals.import_python_function(fn)
        self.start()
        self.boss_arrives()
        self.assertEqual(quest_get_state(Agent.SHARED_ID, "defeat_warlord"),
                         QuestState.ACTIVE)
        self.assertIsNone(lifeform_of_key("queen"))
        self.assertIsNone(dialogue_scene("queen_calls"))


class ABossWithAVoice(_Base):
    def test_the_file_is_found_in_the_authors_folder(self):
        self.assertIn("Probe Queen", self.sb.siege_boss_scan())

    def test_her_sections_are_not_quests(self):
        node = self.sb.siege_boss_quests("Probe Queen")
        self.assertIsNot(node, self.sb.siege_boss_get("Probe Queen"))
        self.assertEqual([c["key"] for c in node["children"]], ["sink_morrigan", "parley"])
        # The scanned node is left whole: the next reader still finds the sections.
        self.assertEqual([c["key"] for c in self.sb.siege_boss_get("Probe Queen")["children"]],
                         ["sink_morrigan", "parley", "characters", "dialogue"])

    def test_a_quest_that_happens_to_be_keyed_dialogue_is_still_a_quest(self):
        node = self.sb.siege_boss_get("Probe Queen")
        node["children"].append({"key": "dialogue", "display_text": "Talk her down",
                                 "data": {"__kind__": "quest"}, "children": []})
        kept = [c["display_text"] for c in self.sb.siege_boss_quests("Probe Queen")["children"]]
        self.assertIn("Talk her down", kept)
        self.assertNotIn("Dialogue", kept)

    def test_her_people_and_scenes_load(self):
        self.assertEqual(self.sb.siege_boss_voice("Probe Queen"), (2, 1))
        queen = lifeform_of_key("queen")
        self.assertIsNotNone(queen)
        self.assertEqual(queen.name, "The Probe Queen")
        self.assertIsNotNone(lifeform_of_key("orla"))
        scene = dialogue_scene("queen_calls")
        self.assertIsNotNone(scene)
        self.assertEqual(scene["data"]["speaker"], "queen")

    def test_only_the_selected_boss(self):
        self.sb.siege_boss_voice("Probe Queen")
        self.assertIsNone(lifeform_of_key("understudy"))
        self.assertIsNone(dialogue_scene("understudy_speaks"))

    def test_loading_twice_makes_nobody_twice(self):
        self.sb.siege_boss_voice("Probe Queen")
        queen, count = lifeform_of_key("queen"), len(Agent.all)
        self.assertEqual(self.sb.siege_boss_voice("Probe Queen"), (2, 1))
        self.assertIs(lifeform_of_key("queen"), queen)
        self.assertEqual(len(Agent.all), count)

    def test_a_restart_is_clean_and_she_loads_again(self):
        """Keyed, not latched: nothing remembers "already loaded" across a mission reset
        in the same interpreter, so the second run gets her people again."""
        self.sb.siege_boss_voice("Probe Queen")
        reset_mission_state()
        for name in ("dialogue scenes", "lifeforms"):
            self.assertNotIn(name, reset_mission_audit())
        mock_sbs.create_new_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        self.assertIsNone(dialogue_scene("queen_calls"))
        self.assertIsNone(lifeform_of_key("queen"))
        self.assertEqual(self.sb.siege_boss_voice("Probe Queen"), (2, 1))
        self.assertIsNotNone(lifeform_of_key("queen"))
        self.assertIsNotNone(dialogue_scene("queen_calls"))


class TheQueenArrives(_Base):
    """The whole of it, through the real route."""

    def setUp(self):
        super().setUp()
        self.start()
        self.boss_arrives()

    def test_her_objectives_are_granted(self):
        # A boss's objectives are granted by their own keys, beside Siege's.
        for step in ("sink_morrigan", "parley"):
            self.assertEqual(quest_get_state(Agent.SHARED_ID, step),
                             QuestState.ACTIVE, step)

    def test_her_cast_and_her_scenes_are_NOT_handed_out_as_quests(self):
        for key in ("characters", "characters/queen", "characters/orla", "dialogue",
                    "dialogue/queen_calls"):
            self.assertIsNone(quest_get(Agent.SHARED_ID, key), key)

    def test_her_people_are_in_the_game_and_her_scene_is_ready(self):
        self.assertIsNotNone(lifeform_of_key("queen"))
        self.assertIsNotNone(dialogue_scene("queen_calls"))
        self.assertIsNone(lifeform_of_key("understudy"))

    def test_she_calls_and_the_answer_finishes_her_quest(self):
        # The Beat was granted running, so its `Action:` is owed to the driver's tick.
        self.assertEqual(quest_tick_actions(), 1)
        waiting = H.hail_pending(self.ship)
        self.assertEqual(len(waiting), 1, "queen hails queen_calls must place a call")
        self.assertEqual(waiting[0].get("scene"), "queen_calls")
        self.assertIsNotNone(H.hail_accept(self.ship))
        while H.hail_advance(self.ship):
            pass
        choices = H.hail_choices(self.ship)
        self.assertEqual([c.get("label") for c in choices], ["We do not stand down."])
        self.assertTrue(H.hail_answer(self.ship, 0))
        self.assertEqual(quest_get_state(Agent.SHARED_ID, "parley"),
                         QuestState.COMPLETE)

    def test_a_second_arrival_makes_nothing_twice(self):
        queen, count = lifeform_of_key("queen"), len(role("lifeform"))
        self.boss_arrives()
        self.assertIs(lifeform_of_key("queen"), queen)
        self.assertEqual(len(role("lifeform")), count)


if __name__ == "__main__":
    unittest.main()
