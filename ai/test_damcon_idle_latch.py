"""A damage-control team that finishes a job on the spot does not retire (GWQ-1).

Reported as "damcons get stuck when they have competing work orders, I think? I thought
we addressed this once." It HAD been addressed once - `4de500c` stopped the brain
oscillating between two damaged rooms - and this is a different fault behind it.

THE LATCH. `ai_idle_at_room` writes `idle_state = "done"` when it finishes a job and then
refuses to run again while it reads "done". In `prefab_lifeform_damcons` the only other
writer of `idle_state` is `ai_lifeform_move_to_location`, because `ai_grid_moving` -
which would set it "stopped" unconditionally - is COMMENTED OUT of that tree. So the one
branch that bailed without touching `idle_state`, "I am already standing on the target",
retired the team permanently: standing on damage, doing nothing, still holding its work
order. Two teams, two orders, and one of them silently out of the game.

These drive the real `.mast` label rather than a reading of it, because the fault is
entirely in which branch runs.
"""
import io
import os
import sys
import unittest

_ADDON = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_ADDON))
# A mastlib's .py files sit FLAT beside each other and import each other that way, so
# the addon folder itself has to be importable and not just its parent.
sys.path.insert(0, _ADDON)

from sbs_utils.fs import test_set_exe_dir

test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401,E402  (first, to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs  # noqa: E402  (installs itself as sys.modules['sbs'])
import sbs_utils.mast_sbs.mast_sbs_procedural  # noqa: F401,E402
from sbs_utils.agent import clear_shared  # noqa: E402
from sbs_utils.helpers import Context, FakeEvent, FrameContext  # noqa: E402
from sbs_utils.mast.mast import Mast  # noqa: E402
from sbs_utils.mast_sbs.maststoryscheduler import StoryScheduler  # noqa: E402
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value  # noqa: E402
from sbs_utils.procedural.query import to_object  # noqa: E402
from sbs_utils.procedural.spawn import grid_spawn, player_spawn  # noqa: E402
from sbs_utils.spaceobject import SpaceObject  # noqa: E402

import grid_ai  # noqa: E402  (the addon's own functions, published below)
from sbs_utils.mast.mast_globals import MastGlobals  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_LABEL = "ai_lifeform_move_to_location"


class _StoryOnlyPage:
    def __init__(self, story):
        self.story = story
        self.gui_task = None


class TheTreeStillHasOneWriter(unittest.TestCase):
    """The premise the fix rests on, pinned so it cannot rot silently.

    If `ai_grid_moving` is ever put back into `prefab_lifeform_damcons`, `idle_state`
    gains a second writer that clears the latch every tick and the branch below stops
    being the only way out. That would not be wrong - but the reasoning in the fix would
    be, and it should be re-read rather than trusted.
    """

    def test_ai_grid_moving_is_not_in_the_damcon_tree(self):
        with io.open(os.path.join(_HERE, "grid_brains.mast"), encoding="utf-8") as f:
            src = f.read()
        start = src.index("=== prefab_lifeform_damcons")
        tree = src[start:src.index("=== ", start + 10)]
        live = [ln for ln in tree.splitlines() if not ln.strip().startswith("#")]
        self.assertFalse(any("ai_grid_moving" in ln for ln in live),
                         "ai_grid_moving is live in the damcon tree now - the idle-latch "
                         "fix in ai_lifeform_move_to_location assumes it is not")


class MoveToLocationBranches(unittest.TestCase):
    """`ai_lifeform_move_to_location` driven as the real compiled label.

    On a REAL grid object on a REAL hull, not a stand-in: the label reaches its team
    through `get_inventory_value(id, ...)`, which resolves an id against the agent
    registry, so a hand-rolled double records its writes somewhere nothing reads and
    every assertion below passes or fails for the wrong reason. (It did, first time.)
    """

    def setUp(self):
        mock_sbs.create_new_sim()
        SpaceObject.clear()
        clear_shared()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent())
        # The addon's own functions reach .mast the way the engine publishes them -
        # without this the label dies on grid_damcons_detailed_status_update.
        MastGlobals.register_mission_functions(grid_ai)
        MastGlobals.globals["sim"] = mock_sbs.sim

        with io.open(os.path.join(_HERE, "grid_brains.mast"), encoding="utf-8") as f:
            source = f.read()
        self.mast = Mast()
        errors = self.mast.compile(source, "damcon_idle_test", self.mast)
        self.assertFalse(errors, f"compile errors: {errors}")
        FrameContext.mast = self.mast
        self.runner = StoryScheduler(self.mast)
        FrameContext.page = _StoryOnlyPage(self.mast)
        self.assertIn(_LABEL, self.mast.labels,
                      "the label under test is not in the compiled story")

        ship = player_spawn(0, 0, 0, "Probe", "tsn", "tsn_battle_cruiser")
        self.ship_id = getattr(ship, "id", ship)
        self.team = to_object(grid_spawn(self.ship_id, "DC1", "dc1", 2, 2,
                                         137, "white", "damcons").id)
        self.assertIsNotNone(self.team, "the damcon team did not spawn")

    def _run(self, cell, target, idle_pos, prev_pos, idle_state, path_length):
        """Put the team in a given state, run the label once, return its idle_state."""
        team = self.team
        team.data_set.set("curx", cell[0], 0)
        team.data_set.set("cury", cell[1], 0)
        team.data_set.set("path_length", path_length, 0)
        team.set_inventory_value("idle_state", idle_state)
        set_inventory_value(team.id, "blackboard:target_pos", target)
        set_inventory_value(team.id, "blackboard:idle_pos", idle_pos)
        set_inventory_value(team.id, "blackboard:prev_target_pos", prev_pos)
        task = self.runner.start_task(self.mast.labels[_LABEL],
                                      {"BRAIN_AGENT": team, "BRAIN_AGENT_ID": team.id})
        for _ in range(40):
            if task.done:
                break
            task.tick()
        return team.get_inventory_value("idle_state")

    def test_standing_on_the_new_target_CLEARS_the_done_latch(self):
        """The bug. While it reads `done` the team never runs ai_idle_at_room again."""
        state = self._run((4, 4), target=(4, 4), idle_pos=(4, 4), prev_pos=None,
                          idle_state="done", path_length=0)
        self.assertEqual(state, "stopped",
                         "the team stayed 'done' while standing on its next job")

    def test_clearing_the_latch_forces_the_room_to_be_rescanned(self):
        """`new_location` is `idle_pos != boost_pos`. Leaving boost_pos alone sends
        ai_idle_at_room back to the room it just FINISHED instead of the one underfoot."""
        set_inventory_value(self.team.id, "blackboard:boost_pos", (4, 4))
        self.team.set_inventory_value("idle_room", "the room it just finished")
        self._run((4, 4), target=(4, 4), idle_pos=(4, 4), prev_pos=None,
                  idle_state="done", path_length=0)
        self.assertEqual(get_inventory_value(self.team.id, "blackboard:boost_pos"),
                         (-1, -1))
        self.assertIsNone(self.team.get_inventory_value("idle_room"))

    def test_a_team_merely_idling_there_is_left_alone(self):
        """The guard. Only the latch is cleared - ordinary idling is correct behavior."""
        set_inventory_value(self.team.id, "blackboard:boost_pos", (4, 4))
        state = self._run((4, 4), target=(4, 4), idle_pos=(4, 4), prev_pos=None,
                          idle_state="idling", path_length=0)
        self.assertEqual(state, "idling")
        self.assertEqual(get_inventory_value(self.team.id, "blackboard:boost_pos"),
                         (4, 4))

    def test_a_real_move_still_reports_moving(self):
        state = self._run((4, 4), target=(9, 9), idle_pos=(4, 4), prev_pos=None,
                          idle_state="done", path_length=6)
        self.assertEqual(state, "moving")

    def test_arriving_reports_stopped(self):
        """`path_length < 0.01` with a previous target is the ARRIVAL branch - which is
        why the mock has to maintain path_length at all. Left unset it reads 0 from the
        blob's typed default and every team is 'there' the moment it is told to go."""
        state = self._run((9, 9), target=(9, 9), idle_pos=None, prev_pos=(9, 9),
                          idle_state="moving", path_length=0)
        self.assertEqual(state, "stopped")


if __name__ == "__main__":
    unittest.main()
