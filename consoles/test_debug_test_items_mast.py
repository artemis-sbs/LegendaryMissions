"""The "Test Items" MAST body actually RUNS - not just compiles.

A compile is not the check that matters here. A MAST story that parses can still die on
its first tick, and the loop this covers uses three things that each have a history:
tuple unpacking in a `for` (unsupported until 2026-07-04, and it used to DESYNC the
parser rather than error), a dict subscript inside a call argument, and a keyword
argument. So this compiles and TICKS the real scheduler, with `item_spawn` swapped for a
recorder, and asserts what the engine would have been asked to spawn.

The MAST below is copied verbatim from `spawn_test_items` in debug.mast, minus the
ship-position preamble - if that line is edited there, edit it here.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_debug_test_items_mast
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import unittest

from sbs_utils.mast.mast import Mast
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers Cosmos nodes)
from sbs_utils.agent import clear_shared
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.helpers import FrameContext, Context, FakeEvent

import sbs_utils.procedural.execution as ex  # noqa: F401
MastGlobals.import_python_module('sbs_utils.procedural.execution')

from cosmos_dev.mock import sbs



class _RaisingScheduler(MastScheduler):
    """A silent MAST runtime error is the failure mode being guarded against."""

    def runtime_error(self, message):
        raise AssertionError(f"RUNTIME ERROR: {message}")


class _FakeSim:
    def __init__(self):
        self.time_tick_counter = 0


# Verbatim from spawn_test_items, with the ship position stubbed in.
# NOT named `main` - MAST creates that label implicitly, so declaring it is
# "Duplicate label" and every following line then fails as "Bad indentation".
LOOP = """
=== run_items ===
    _pos_x = 1000
    _pos_y = 0
    _pos_z = 2000
    _plan = debug_test_item_plan()
    ->END if not _plan
    for _i, _drop in enumerate(_plan):
        item_spawn(_drop["key"], _pos_x + 125 + 75 * (_i % 6), _pos_y, _pos_z + 450 + 75 * (_i // 6), qty=_drop["qty"])
    ->END
"""


class TestSpawnTestItemsRuns(unittest.TestCase):
    def setUp(self):
        self.spawned = []
        self.saved = {k: MastGlobals.globals.get(k)
                      for k in ("item_spawn", "debug_test_item_plan")}
        MastGlobals.globals["item_spawn"] = self._record
        MastGlobals.globals["debug_test_item_plan"] = self._plan

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                MastGlobals.globals.pop(k, None)
            else:
                MastGlobals.globals[k] = v

    def _record(self, key, x, y, z, **kw):
        self.spawned.append({"key": key, "x": x, "y": y, "z": z,
                             "qty": kw.get("qty")})

    def _plan(self):
        return [{"key": "salvage", "qty": 20}, {"key": "salvage", "qty": 20},
                {"key": "salvage", "qty": 20}, {"key": "bio_sample", "qty": 4},
                {"key": "ore", "qty": 1}, {"key": "hacking_virus", "qty": 1},
                {"key": "turret_kit_beam", "qty": 1}]

    def _run(self, code=LOOP):
        mast = Mast()
        clear_shared()
        errors = mast.compile(code, "test_items", mast)
        self.assertEqual(errors, [], f"MAST did not compile: {errors}")
        FrameContext.context = Context(_FakeSim(), sbs, FakeEvent())
        FrameContext.mast = mast
        runner = _RaisingScheduler(mast)
        runner.start_task("run_items")
        for _ in range(50):
            if not runner.tick():
                break
        return runner

    def test_it_runs_and_spawns_every_row(self):
        self._run()
        self.assertEqual(len(self.spawned), 7)

    def test_the_quantities_survive_the_keyword_argument(self):
        self._run()
        by_key = {}
        for s in self.spawned:
            by_key[s["key"]] = by_key.get(s["key"], 0) + s["qty"]
        self.assertEqual(by_key["salvage"], 60)
        self.assertEqual(by_key["bio_sample"], 4)
        self.assertEqual(by_key["ore"], 1)

    def test_the_grid_is_six_across(self):
        self._run()
        # Row 0 is x 1125..1500 at z 2450; row 1 restarts x at 1125, z 2525.
        self.assertEqual([s["x"] for s in self.spawned[:6]],
                         [1125, 1200, 1275, 1350, 1425, 1500])
        self.assertEqual([s["z"] for s in self.spawned[:6]], [2450] * 6)
        self.assertEqual(self.spawned[6]["x"], 1125)
        self.assertEqual(self.spawned[6]["z"], 2525)

    def test_an_empty_plan_ends_cleanly(self):
        """A mission with no item addons loaded must not error."""
        MastGlobals.globals["debug_test_item_plan"] = lambda: []
        self._run()
        self.assertEqual(self.spawned, [])


if __name__ == "__main__":
    unittest.main()
