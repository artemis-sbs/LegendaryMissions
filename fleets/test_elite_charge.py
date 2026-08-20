"""The elite ability brain, driven through the REAL .mast nodes.

The Python helpers are covered next door (science_scans/test_science_status.py). What
this pins is the glue those tests cannot see: that gate -> charge -> activate actually
runs in that order against a live agent, that an elite spends its warm-up visibly
committed to one ability, and that the commitment ends when the ability fires.

Getting this wrong is silent - a behavior tree that never succeeds looks exactly like an
elite that has not had an opening yet - which is why it is worth compiling the real
files rather than trusting a reading of them.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest fleets.test_elite_charge
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs   # installs itself as sys.modules['sbs']
import sbs_utils.mast_sbs.mast_sbs_procedural  # noqa: F401  (publishes the library's MAST globals; needs `sbs`)
from sbs_utils.agent import clear_shared
from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.mast.mast import Mast
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast_sbs.maststoryscheduler import StoryScheduler
from sbs_utils.procedural.brain import brains_run_all
from sbs_utils.procedural.inventory import get_inventory_value
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.roles import add_role
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.spaceobject import SpaceObject

from fleets import elite_abilitites as E
from science_scans import science_status as S

_HERE = os.path.dirname(os.path.abspath(__file__))


class _StoryOnlyPage:
    """Just enough page for `labels_get_type` to find the story's labels. The ability
    registry is built by walking them, so without this every list below is empty and
    the tests pass by measuring nothing."""

    def __init__(self, story):
        self.story = story
        self.gui_task = None


def _source(name):
    with io.open(os.path.join(_HERE, name), encoding="utf-8") as f:
        return f.read()


class EliteBrainRuns(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        SpaceObject.clear()
        clear_shared()
        S.science_status_clear_all()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent())

        # The addon's own functions reach .mast the same way the engine publishes them.
        MastGlobals.register_mission_functions(E)
        MastGlobals.register_mission_functions(S)
        # `sim` is bound once at import, before create_new_sim() exists. Point it at
        # this test's sim or an ability body dies on its first engine call.
        MastGlobals.globals["sim"] = mock_sbs.sim

        self.mast = Mast()
        # elite_abilities.mast FIRST: its top-level lines sit at column 0 and
        # would otherwise read as an indented continuation of the prefabs file's
        # last label body.
        source = _source("elite_abilities.mast") + chr(10) + _source("elite_abilities_prefabs.mast")
        errors = self.mast.compile(source, "elite_test", self.mast)
        self.assertFalse(errors, f"compile errors: {errors}")
        FrameContext.mast = self.mast
        self.runner = StoryScheduler(self.mast)
        # `labels_get_type` walks the PAGE's story, and there is no console here.
        FrameContext.page = _StoryOnlyPage(self.mast)
        E.elite_build_abilities()
        self.assertIn("elite/cloak", E.elite_get_non_engine(),
                      "the ability registry is empty - nothing below is being measured")

        # An elite that can only do one thing, so the choice is not a coin toss.
        self.elite = to_id(npc_spawn(0, 0, 0, "Raider One", "raider,skaraan",
                                     "tsn_battleship", "behav_npcship"))
        add_role(self.elite, "elite")
        add_role(self.elite, "elite/cloak")
        # Something hostile to use it on - the gate refuses when nobody is near.
        self.prey = to_id(npc_spawn(2000, 0, 0, "Artemis", "tsn",
                                    "tsn_light_cruiser", "behav_npcship"))

    def tearDown(self):
        FrameContext.context = None
        FrameContext.mast = None
        FrameContext.page = None
        S.science_status_clear_all()
        SpaceObject.clear()
        clear_shared()

    def attach(self):
        self.host = self.runner.start_task("handle_elite_abilities",
                                           inputs={"ELITE_ID": self.elite})
        self.host.tick()
        return self.host

    def beats(self, n=3):
        """One pass of the brain, the way the tick dispatcher drives it. A brain node
        is started FROM a task, so there has to be one in context."""
        for _ in range(n):
            FrameContext.task = self.host
            brains_run_all(None)
            FrameContext.task = None
            self.runner.tick()

    def test_the_labels_the_brain_names_all_exist(self):
        """A tree naming a label that is not there is not an error - the node is just
        dropped, and the elite quietly does nothing."""
        for name in ("elite_bt_gate", "elite_bt_charge", "elite_bt_activate"):
            self.assertIn(name, self.mast.labels, name)

    def test_scheduling_the_entry_point_attaches_the_tree(self):
        self.attach()
        self.assertIsNotNone(get_inventory_value(self.elite, "__BRAIN__", None))
        self.assertTrue(get_inventory_value(self.elite, E.ELITE_BRAIN_FLAG, False))

    def test_the_elite_COMMITS_to_an_ability_and_says_so(self):
        """The whole point of the ticket: the decision is made in the open, some time
        before the ability is used, and Science can read it."""
        self.attach()
        self.beats(4)
        self.assertEqual(get_inventory_value(self.elite, "ELITE_PENDING_ABILITY", None),
                         "elite/cloak")
        self.assertRegex(S.science_status_text(self.elite),
                         r"Preparing to cloak - \d+s$")

    def test_it_is_still_charging_a_beat_later_rather_than_firing(self):
        self.attach()
        self.beats(4)
        self.beats(4)
        self.assertIsNone(get_inventory_value(self.elite, "ELITE_TASK", None))
        self.assertIn("Preparing to cloak", S.science_status_text(self.elite))

    def test_when_the_warm_up_ends_the_ability_fires_and_the_tell_goes(self):
        self.attach()
        self.beats(4)
        # Stand at the end of the warm-up rather than waiting out 25 sim-seconds.
        E.clear_timer(self.elite, E.ELITE_WARMUP_TIMER)
        self.beats(4)
        # The cloak really ran: it stashes the hull it is hiding before it swaps art.
        self.assertIsNotNone(get_inventory_value(self.elite, "visible_art_id", None))
        self.assertIsNone(get_inventory_value(self.elite, "ELITE_PENDING_ABILITY", None))
        self.assertNotIn("Preparing", S.science_status_text(self.elite))

    def test_losing_the_target_calls_the_charge_off(self):
        """A tell has to stop being shown the moment it stops being true - the old
        writer had no way to take one down at all."""
        self.attach()
        self.beats(4)
        self.assertIn("Preparing", S.science_status_text(self.elite))
        # Out of reach rather than destroyed - same gate branch, and it does not depend
        # on how the mock retires a dead hull from a broad test.
        to_object(self.prey).pos = mock_sbs.vec3(500000, 0, 0)
        self.beats(4)
        self.assertIsNone(get_inventory_value(self.elite, "ELITE_PENDING_ABILITY", None))
        self.assertNotIn("Preparing", S.science_status_text(self.elite))


if __name__ == "__main__":
    unittest.main()
