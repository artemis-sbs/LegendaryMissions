"""What the Weapons hold-click is allowed to offer - driven through the real route.

This pins the bug behind "if a ship does a grav lock on a black hole, the whole game is
hosed". The menu used to choose its mode by a BLACKLIST:

    if not has_any_role(WEAPONS_POPUP_ID, "item,upgrade,station,asteroid,__npc__"):
        + "Grav Lock"

A black hole carries `#, black_hole, terrain, __space_object__, __terrain__` and none of
those, so it fell into the catch-all and a gunner was offered a RIGID lock on it. That
makes the hole the LOAD: the beam reels it onto the hull, `_enforce_impulse` caps the ship
to impulse so it cannot warp away, and `black_hole_lethal_watch` explodes anything within
500u of a hole every tick - then the hole stays parked wherever it was dropped. The same
branch also offered a rigid lock on every nebula, mine, planet, marker and GM camera rig.

So this fires the REAL `//popup/weapons` route from the real file and reads the menu string
the engine would have been sent, rather than asserting on the source text - a test that
greps cannot tell a fixed menu from a renamed one.
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import logging
import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from sbs_utils.agent import clear_shared
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import mast_sbs_procedural  # noqa: F401  (MAST globals)
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.gui import Gui
from sbs_utils.mast.maststory import MastStory
from sbs_utils.procedural import grav_tether as gt
from sbs_utils.procedural.inventory import get_inventory_value
from sbs_utils.procedural.popup import PopupPromise, start_popup_selected
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.procedural.orbit import orbit_release_all
from sbs_utils.procedural.terrain import terrain_spawn_black_hole
from sbs_utils.spaceobject import SpaceObject

import tether_fighter          # noqa: F401  (registers lm_tether_* globals)
import tether_growth
import tether_salvage

ADDON_MAST = os.path.join(HERE, "grav_tether.mast")

# The addon's own top level plus an idle loop: a popup route runs on the SERVER task, so
# the page's main task has to still be alive when the hold-click lands.
_MAIN = """default shared LM_TETHER_BREAK_DAMAGE = 15
---gt_popup_idle
    await delay_sim(60)
    jump gt_popup_idle

"""


def _source():
    with open(ADDON_MAST, encoding="utf-8") as handle:
        return _MAIN + handle.read()


class AddonPage(StoryPage):
    story = None


class TestWeaponsPopupTargets(unittest.TestCase):
    def setUp(self):
        clear_shared()
        SpaceObject.clear()
        gt.grav_tether_clear_all()
        gt.grav_tether_set_attach_policy(None)
        gt.grav_tether_set_grab_speed_limit(None)
        gt.grav_tether_set_mass_fn(None)
        gt.grav_tether_set_anchor_roles(gt.ANCHOR_ROLES)
        PopupPromise.popup_promises = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))

        # The route calls the addon's OWN functions (lm_tether_haulable,
        # lm_tether_hole_in_reach, lm_tether_swing_hole), which reach MAST only through
        # this registration - the same path __init__.mast's `import x.py` takes.
        for mod in (tether_fighter, tether_growth, tether_salvage):
            MastGlobals.register_mission_functions(mod)

        self.story = MastStory()
        errors = self.story.compile(_source(), "gt_popup", self.story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        FrameContext.mast = self.story

        # The class-level seam, not MastScheduler.runtime_error: StoryScheduler OVERRIDES
        # the instance method, so patching that one binds something nothing calls. Plus a
        # log handler, because a failed EXPRESSION only warns on mast.runtime.
        self.errors = []
        self._orig_seam = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.errors.append
        test_self = self

        class _Sink(logging.Handler):
            def emit(self, record):
                test_self.errors.append(record.getMessage())

        self._sink = _Sink(level=logging.WARNING)
        logging.getLogger("mast.runtime").addHandler(self._sink)

        Gui.clients = {}
        Gui.widget_list_sent = {}
        AddonPage.story = self.story
        self.page = AddonPage()
        Gui.push(0, self.page)
        self._present()

        self.ship = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        self.hulk = npc_spawn(1500, 0, 0, "Hulk", "tsn", "tsn_light_cruiser",
                              "behav_npcship")
        self.hole = terrain_spawn_black_hole(3000, 0, 0, gravity_radius=5000)

    def _present(self):
        mock_sbs.sim._time_tick_counter += 30
        self.page.gui_state = "repaint"
        self.page.present(FakeEvent(0, "gui_present"))

    def tearDown(self):
        # A live carrier outlives the mock reset - and so does its TOMBSTONE. delete_object
        # only queues; DeleteQueue._pending is a module global that create_new_sim does not
        # touch, and the mock hands out the same ids to the next sim. Left undrained, the
        # next test's freshly spawned carrier is born with a dead id and object_exists says
        # it was never there. (Production is covered: handlerhooks drains per event and
        # registers the queue in the reset ledger.)
        orbit_release_all()
        DeleteQueue.drain()
        MastScheduler.on_runtime_error = self._orig_seam
        logging.getLogger("mast.runtime").removeHandler(self._sink)
        Gui.clients = {}
        Gui.widget_list_sent = {}
        AddonPage.story = None
        PopupPromise.popup_promises = {}
        FrameContext.page = None
        gt.grav_tether_clear_all()
        FrameContext.mast = None
        FrameContext.task = None
        FrameContext.context = None
        SpaceObject.clear()

    def _menu_for(self, target):
        """The hold-menu string the engine would be sent for a hold-click on `target`."""
        target_id = getattr(target, "id", target)
        seen = []
        real = mock_sbs.send_hold_menu
        mock_sbs.send_hold_menu = lambda cid, subj, obj, extra, text: seen.append(text)
        try:
            event = FakeEvent(client_id=0, tag="popup", sub_tag="weapons",
                              origin_id=self.ship.id, selected_id=target_id,
                              parent_id=target_id)
            FrameContext.context = Context(mock_sbs.sim, mock_sbs, event)
            promise = start_popup_selected(event)
            self.assertIsNotNone(promise, "the popup never opened")
            promise.initial_poll()
            self._present()
        finally:
            mock_sbs.send_hold_menu = real
            FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        return " ".join(seen)

    # --- the bug ------------------------------------------------------------

    def test_a_black_hole_is_never_offered_a_grav_lock(self):
        menu = self._menu_for(self.hole)
        self.assertNotIn("Grav Lock", menu, f"menu was: {menu!r}")
        self.assertNotIn("Grav Tow", menu, f"menu was: {menu!r}")
        self.assertNotIn("Grav Reel", menu, f"menu was: {menu!r}")
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")

    def test_a_black_hole_in_reach_is_offered_the_slingshot(self):
        # The one thing a tether may do with a hole - and the rope is clamped clear of
        # the gravity well by lm_tether_swing_hole.
        self.assertIn("Slingshot", self._menu_for(self.hole))

    def test_a_hole_out_of_reach_is_offered_nothing(self):
        # _tick_swing pulls a ship onto the rope circle from ANY distance, so an ungated
        # button would yank a cruiser across the sector.
        far = terrain_spawn_black_hole(90000, 0, 0, gravity_radius=5000)
        menu = self._menu_for(far)
        self.assertNotIn("Slingshot", menu, f"menu was: {menu!r}")
        self.assertNotIn("Grav Lock", menu, f"menu was: {menu!r}")

    def test_the_library_refuses_the_pull_even_if_a_menu_offers_it(self):
        # Belt and braces: the menu is LM's half, the anchor rule is the library's.
        before = (self.hole.pos.x, self.hole.pos.z)
        self.assertIsNone(gt.grav_tether_lock(self.ship, self.hole))
        for _ in range(5):
            gt.grav_tether_tick()
        self.assertEqual((self.hole.pos.x, self.hole.pos.z), before,
                         "nothing may drag a black hole")

    def test_both_passes_are_offered(self):
        # The crew picks the radius: wide is clamped clear of the well, close is inside it.
        menu = self._menu_for(self.hole)
        self.assertIn("Slingshot (wide)", menu, f"menu was: {menu!r}")
        self.assertIn("Slingshot (close)", menu, f"menu was: {menu!r}")

    def test_a_ship_mid_slingshot_is_offered_nothing(self):
        # The arc commandeers the helm for a few seconds. Letting go half way round would
        # drop the ship on an arbitrary bearing, so the whole menu stands down.
        tether_growth.lm_tether_slingshot_hole(self.ship.id, self.hole.id)
        self.assertTrue(tether_growth.lm_tether_sling_is(self.ship.id))
        self.assertEqual(self._menu_for(self.hole).strip(), "")

    def test_a_cooling_ship_is_not_offered_the_slingshot(self):
        tether_growth.lm_tether_slingshot_hole(self.ship.id, self.hole.id)
        tether_growth.lm_tether_sling_finish(self.ship.id)      # out the far side
        self.assertFalse(tether_growth.lm_tether_sling_ready(self.ship.id))
        self.assertNotIn("Slingshot", self._menu_for(self.hole))

    def test_the_slingshot_will_not_start_twice(self):
        self.assertIsNotNone(tether_growth.lm_tether_slingshot_hole(self.ship.id, self.hole.id))
        self.assertIsNone(tether_growth.lm_tether_slingshot_hole(self.ship.id, self.hole.id))

    def test_a_close_pass_is_inside_the_well_and_clear_of_the_kill_radius(self):
        # The two numbers that make "close" a real decision rather than a label.
        close = tether_growth.lm_tether_hole_close_rope(self.hole.id)
        gravity = tether_growth.lm_tether_hole_gravity(self.hole.id)
        self.assertLess(close, gravity, "a close pass must be INSIDE the gravity well")
        self.assertGreater(close, 500 * 4, "but nowhere near the 500u lethal radius")

    def test_a_close_pass_costs_a_system_and_a_wide_one_does_not(self):
        # The engine's own pull is the real danger and the mock does not simulate it, so
        # the deterministic half is what a headless test can actually hold.
        tether_growth.lm_tether_slingshot_hole(
            self.ship.id, self.hole.id, tether_growth.lm_tether_hole_close_rope(self.hole.id))
        self.assertTrue(get_inventory_value(self.ship.id, "sling:close", False))

    def test_a_ship_already_towing_is_offered_Release(self):
        gt.grav_tether_tow(self.ship.id, self.hulk.id, 500)
        menu = self._menu_for(self.hulk)
        self.assertIn("Release", menu, f"menu was: {menu!r}")
        self.assertNotIn("Grav Tow", menu, f"menu was: {menu!r}")

    # --- what must still work ------------------------------------------------

    def test_an_npc_can_still_be_towed_and_locked(self):
        menu = self._menu_for(self.hulk)
        self.assertIn("Grav Tow", menu, f"menu was: {menu!r}")
        self.assertIn("Grav Lock", menu, f"menu was: {menu!r}")
        self.assertEqual(self.errors, [], f"runtime errors: {self.errors}")

    def test_a_pickup_is_still_offered_the_reel(self):
        pod = npc_spawn(500, 0, 0, "Pod", "tsn,item,upgrade", "tsn_light_cruiser",
                        "behav_npcship")
        self.assertIn("Grav Reel", self._menu_for(pod))

    def test_the_allowlist_covers_the_salvage_roles(self):
        # Towing a hulk home is the payoff the tether exists for; under the old blacklist
        # a derelict reached the menu only if it happened to carry __npc__.
        for role_name in tether_salvage.LM_SALVAGE_ROLES.split(","):
            wreck = npc_spawn(700, 0, 0, f"W {role_name}", f"tsn,{role_name}",
                              "tsn_light_cruiser", "behav_npcship")
            self.assertTrue(tether_salvage.lm_tether_haulable(wreck.id), role_name)

    def test_the_allowlist_excludes_terrain_and_markers(self):
        self.assertFalse(tether_salvage.lm_tether_haulable(self.hole.id))


if __name__ == "__main__":
    unittest.main()
