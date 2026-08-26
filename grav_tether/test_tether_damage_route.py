"""A hit heavy enough shakes a tether loose - and the route can still READ the threshold.

This pins a bug that shipped: the "how big a hit breaks a tether" number was a Python
module constant in `tether_mass.py`, and only FUNCTIONS are exported to the MAST
namespace. So the number read fine in Python, was invisible to the `//damage/object`
route that is its only reader, and the first shot fired at a towing ship produced

    NameError: name 'LM_TETHER_BREAK_DAMAGE' is not defined

- a runtime error, per hit, for the rest of the mission. Nothing catches that at compile
time and nothing catches it in a headless run that never fires a shot at a tow.

So this fires the real route from the real file, with a real tether open, and checks the
tether actually let go. The route body is `.mast` in this folder rather than a fixture,
so the test cannot pass against a copy that has drifted.
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import logging
import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils.agent import clear_shared
from sbs_utils.damagedispatcher import DamageDispatcher
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import mast_sbs_procedural  # noqa: F401  (MAST globals)
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.gui import Gui
from sbs_utils.mast.maststory import MastStory
from sbs_utils.procedural import grav_tether as gt
from sbs_utils.procedural.routes import HandleDamage
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.spaceobject import SpaceObject

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_MAST = os.path.join(HERE, "grav_tether.mast")
ADDON_INIT = os.path.join(HERE, "__init__.mast")


# The addon's own top level plus an idle loop. The loop is not decoration: routes fire on
# the SERVER task, so the page's main task has to still be alive when the hit lands - a
# main that has ended takes the whole page down with it.
_MAIN = """default shared LM_TETHER_BREAK_DAMAGE = 15
---gt_test_idle
    await delay_sim(60)
    jump gt_test_idle

"""


def _source():
    with open(ADDON_MAST, encoding="utf-8") as handle:
        return _MAIN + handle.read()


class AddonPage(StoryPage):
    story = None


class TestTetherBreaksUnderFire(unittest.TestCase):
    def setUp(self):
        clear_shared()
        SpaceObject.clear()
        gt.grav_tether_clear_all()
        gt.grav_tether_set_attach_policy(None)
        gt.grav_tether_set_grab_speed_limit(None)
        DamageDispatcher.clear()
        HandleDamage.just_once = set()
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

        self.story = MastStory()
        errors = self.story.compile(_source(), "gt_addon", self.story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        FrameContext.mast = self.story

        # CATCHING RUNTIME ERRORS TAKES TWO HOOKS, AND THE OBVIOUS ONE IS THE WRONG ONE.
        # `StoryScheduler` OVERRIDES `runtime_error`, so patching
        # `MastScheduler.runtime_error` (as this test used to) binds a method nothing
        # calls - the assertion looked strict and was vacuous. What the story scheduler
        # does call is the class-level `MastScheduler.on_runtime_error` seam, which is
        # also what cosmos_dev's verdict uses.
        #
        # That covers the FATAL path only. `eval_code_checked(end_on_exception=False)`
        # reports a failed expression as a WARNING on the `mast.runtime` logger and
        # returns EVAL_ERROR without ending anything, so a whole class of failure never
        # reaches the seam at all. Hence the log handler as well.
        self.errors = []
        self._orig_seam = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.errors.append

        test_self = self

        class _Sink(logging.Handler):
            def emit(self, record):
                test_self.errors.append(record.getMessage())

        self._sink = _Sink(level=logging.WARNING)
        logging.getLogger("mast.runtime").addHandler(self._sink)

        # Running main is what REGISTERS the routes (route_damage_object), and a route
        # fires on the SERVER task - so the addon needs a real server page behind it,
        # not just a scheduler.
        Gui.clients = {}
        Gui.widget_list_sent = {}
        AddonPage.story = self.story
        self.page = AddonPage()
        Gui.push(0, self.page)
        self._present()

        self.ship = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        self.load = npc_spawn(1500, 0, 0, "Hulk", "tsn", "tsn_light_cruiser",
                              "behav_npcship")

    def _present(self):
        mock_sbs.sim._time_tick_counter += 30
        self.page.gui_state = "repaint"
        self.page.present(FakeEvent(0, "gui_present"))

    def tearDown(self):
        MastScheduler.on_runtime_error = self._orig_seam
        logging.getLogger("mast.runtime").removeHandler(self._sink)
        Gui.clients = {}
        Gui.widget_list_sent = {}
        AddonPage.story = None
        FrameContext.page = None
        gt.grav_tether_clear_all()
        DamageDispatcher.clear()
        HandleDamage.just_once = set()
        FrameContext.mast = None
        FrameContext.task = None
        FrameContext.context = None
        SpaceObject.clear()

    def _hit(self, amount, target=None):
        # `target` is what got SHOT (DAMAGE_TARGET_ID). It defaults to the towing ship,
        # but the interesting case is shooting the LOAD - see the tests below.
        target_id = self.ship.id if target is None else target
        event = FakeEvent(client_id=0, tag="damage", sub_tag="beam",
                          origin_id=self.load.id, selected_id=target_id)
        event.sub_float = float(amount)
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, event)
        DamageDispatcher.dispatch_damage(event)
        self._present()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

    def test_the_threshold_is_declared_where_mast_can_read_it(self):
        # The fix, stated as the thing that has to stay true. A Python constant would
        # satisfy a grep and not the route.
        with open(ADDON_INIT, encoding="utf-8") as handle:
            init = handle.read()
        self.assertIn("LM_TETHER_BREAK_DAMAGE", init,
                      "the break threshold must be a MAST variable - only FUNCTIONS are "
                      "exported to the MAST namespace, so a Python constant is invisible "
                      "to the //damage/object route that reads it")

    def test_a_heavy_hit_breaks_the_tow_without_a_runtime_error(self):
        gt.grav_tether_tow(self.ship, self.load, 500)
        self._hit(50)
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")
        self.assertFalse(gt.grav_tether_involves(self.ship),
                         "a heavy hit should have shaken the tether loose")

    def test_a_stray_shot_does_not_cost_the_haul(self):
        gt.grav_tether_tow(self.ship, self.load, 500)
        self._hit(1)
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")
        self.assertTrue(gt.grav_tether_involves(self.ship),
                        "a light hit must not drop the load")

    def test_an_untethered_ship_is_left_alone(self):
        self._hit(50)
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")

    def test_shooting_the_LOAD_breaks_the_tow_and_tells_the_hauler(self):
        """The common case, and the one the route got wrong.

        `grav_tether_involves` is true for EITHER end, so the route fires whether the
        towing ship or its load takes the hit. It used to answer by broadcasting to
        DAMAGE_TARGET_ID - the object that was shot - which for this case is a hulk. A
        hulk is not a player ship and has no waterfall, so the message went nowhere even
        when it did not raise.
        """
        gt.grav_tether_tow(self.ship, self.load, 500)
        self._hit(50, target=self.load.id)
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")
        self.assertFalse(gt.grav_tether_involves(self.ship),
                         "a heavy hit on the load should shake the tether loose")

    def test_a_hit_that_DESTROYS_the_load_does_not_raise(self):
        """The bug the soak harness found.

        One hit both shakes the tether loose and destroys what was on the end of it. The
        object is gone by the time the route speaks, and comms_broadcast on a freed id
        raises "invalid space object while calling SendMessageToPlayerShip". Because a
        failing expression STOPS the command, the route ended there - silently, once per
        qualifying hit, for the rest of the mission.

        The tether registry is keyed by id and does not care that the object was freed,
        so `grav_tether_involves` is still true and the route still runs. That is what
        makes this reachable rather than theoretical.
        """
        gt.grav_tether_tow(self.ship, self.load, 500)
        load_id = self.load.id
        mock_sbs.delete_object(load_id)
        self.assertFalse(mock_sbs.sim.space_object_exists(load_id),
                         "precondition: the load must really be gone")
        self._hit(50, target=load_id)
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")
        self.assertFalse(gt.grav_tether_involves(self.ship),
                         "the tether must still be released when the load is destroyed")


if __name__ == "__main__":
    unittest.main()
