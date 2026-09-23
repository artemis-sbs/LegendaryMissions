"""The per-side scan queue.

Drives the real module against the mock and a real compiled story, not a fake. The
queue's whole job is to read live object state (side, range, sensor range) and then hand
completion to the library's own path - `science_ensure_scan` synthesizes a real
`science_scan_complete` event through the promise machinery - so a stubbed completion
would only prove the stub agrees with itself. The harness below is the smallest story
that makes that path real: an `//enable/science` that passes and a `//science` with two
tabs, which is exactly what a mission provides.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

from cosmos_dev.mock import sbs as mock_sbs                        # noqa: E402
from sbs_utils.agent import Agent                                  # noqa: E402
from sbs_utils.gui import Gui                                      # noqa: E402
from sbs_utils.helpers import Context, FakeEvent, FrameContext     # noqa: E402
from sbs_utils.mast.maststory import MastStory                     # noqa: E402
from sbs_utils.mast.mastscheduler import MastScheduler             # noqa: E402
from sbs_utils.mast_sbs import story_nodes                         # noqa: E402,F401
from sbs_utils.mast_sbs.maststorypage import StoryPage             # noqa: E402
from sbs_utils.spaceobject import SpaceObject                      # noqa: E402
from sbs_utils.procedural.query import to_object                   # noqa: E402
from sbs_utils.procedural.science import science_set_scan_data     # noqa: E402
from sbs_utils.procedural.sides import side_ensure                 # noqa: E402
from sbs_utils.procedural.space_objects import delete_object       # noqa: E402
from sbs_utils.procedural.spawn import npc_spawn, player_spawn     # noqa: E402

import science_queue as sq                                         # noqa: E402

CID = 1

# The smallest story that makes a scan real. Without a PASSING //enable/science,
# start_science_selected ends the task and nothing is scanned - which would look exactly
# like a queue that never completes.
HARNESS_STORY = '''gui_text("$text:harness;")
await gui()

//enable/science

//science
    + "scan":
        <scan>
            % A kralien cruiser.
    + "status":
        <scan>
            % Its engines are damaged.
'''


class QueuePage(StoryPage):
    story = None


class ScanQueueTest(unittest.TestCase):
    def setUp(self):
        from sbs_utils.handlerhooks import reset_mission_state
        reset_mission_state()
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        SpaceObject.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)
        side_ensure("tsn")
        side_ensure("raider")
        sq.lm_sci_queue_clear()

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append

        story = MastStory()
        story.basedir = os.path.dirname(os.path.abspath(__file__))
        errors = story.compile(HARNESS_STORY, "sciqueueharness", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        QueuePage.story = story
        FrameContext.mast = story

        self.player = to_object(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        self.player.data_set.set("ship_base_scan_range", 25000.0, 0)
        self.target = to_object(npc_spawn(1000, 0, 0, "K19", "raider",
                                          "tsn_light_cruiser", "behav_npcship"))
        mock_sbs.assign_client_to_ship(CID, self.player.id)

        self.server = QueuePage()
        Gui.push(0, self.server)
        self.page = QueuePage()
        Gui.push(CID, self.page)
        self._present()

    def tearDown(self):
        MastScheduler.on_runtime_error = self._orig_rte
        sq.lm_sci_queue_clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        QueuePage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        FrameContext.context = None
        SpaceObject.clear()

    def _present(self, n=2):
        """Paint both pages, the way the drag-orders harness does. The pages have to
        actually run for the server page to own a gui_task, which is what
        `FrameContext.server_task` resolves through and therefore what
        `science_ensure_scan` needs to schedule its scan task."""
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "gui_present"))
            self.server.gui_state = "repaint"
            self.server.present(FakeEvent(0, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(CID, "gui_present"))
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def _advance(self, seconds, step=0.5):
        """Run the beat for `seconds` of SIM time, the way the mast beat does."""
        now = float(mock_sbs.sim.time_tick_counter) / 30.0
        end = now + seconds
        while now < end:
            now += step
            mock_sbs.sim._time_tick_counter = int(now * 30)
            sq.lm_sci_queue_tick()

    # --- membership ---------------------------------------------------------

    def test_add_is_keyed_by_side_not_ship(self):
        self.assertTrue(sq.lm_sci_queue_add(self.player, self.target, "scan"))
        self.assertEqual(len(sq.lm_sci_queue_list("tsn")), 1)
        self.assertEqual(sq.lm_sci_queue_list("raider"), [])

    def test_duplicate_is_a_noop(self):
        self.assertTrue(sq.lm_sci_queue_add(self.player, self.target, "scan"))
        self.assertFalse(sq.lm_sci_queue_add(self.player, self.target, "scan"))
        self.assertEqual(len(sq.lm_sci_queue_list("tsn")), 1)

    def test_a_different_tab_is_a_separate_entry(self):
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        sq.lm_sci_queue_add(self.player, self.target, "status")
        self.assertEqual(len(sq.lm_sci_queue_list("tsn")), 2)

    def test_already_scanned_is_never_queued(self):
        science_set_scan_data(self.player, self.target, {"scan": "A kralien cruiser."})
        self.assertFalse(sq.lm_sci_queue_add(self.player, self.target, "scan"))

    # --- order --------------------------------------------------------------

    def test_position_reports_head_first(self):
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        sq.lm_sci_queue_add(self.player, self.target, "status")
        self.assertEqual(sq.lm_sci_queue_position("tsn", self.target, "scan"), 1)
        self.assertEqual(sq.lm_sci_queue_position("tsn", self.target, "status"), 2)

    def test_remove_promotes_the_next_entry(self):
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        sq.lm_sci_queue_add(self.player, self.target, "status")
        self.assertTrue(sq.lm_sci_queue_remove("tsn", self.target, "scan"))
        self.assertEqual(sq.lm_sci_queue_position("tsn", self.target, "status"), 1)

    def test_move_to_front_restarts_progress(self):
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        sq.lm_sci_queue_add(self.player, self.target, "status")
        self._advance(2.0)
        self.assertGreater(sq.lm_sci_queue_percent("tsn", self.target, "scan"), 0)
        self.assertTrue(sq.lm_sci_queue_move_to_front("tsn", self.target, "status"))
        # Percent earned at the back of the queue is not sensor time the ship spent.
        self.assertEqual(sq.lm_sci_queue_percent("tsn", self.target, "status"), 0)

    def test_only_the_head_advances(self):
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        sq.lm_sci_queue_add(self.player, self.target, "status")
        self._advance(2.0)
        self.assertEqual(sq.lm_sci_queue_percent("tsn", self.target, "status"), 0)

    # --- completion ---------------------------------------------------------

    def test_a_scan_completes_and_writes_real_scan_data(self):
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        self._advance(sq.LM_SCI_SCAN_SLOWEST + 1.0)
        self.assertEqual(sq.lm_sci_queue_list("tsn"), [])
        self.assertTrue(sq.lm_sci_queue_is_scanned(self.player, self.target, "scan"))
        self.assertEqual(self.rte, [])

    def test_completion_promotes_the_next_entry(self):
        """Advance for ONE scan, not a fixed guess: the time is now a function of range,
        so a fixed window finished both entries and the promotion went unmeasured."""
        one = sq.lm_sci_scan_seconds(self.player.id, self.target.id)
        self.assertIsNotNone(one)
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        sq.lm_sci_queue_add(self.player, self.target, "status")
        self._advance(one + 0.5)
        self.assertEqual(sq.lm_sci_queue_position("tsn", self.target, "status"), 1,
                         "the next entry did not become the head")
        self.assertEqual(len(sq.lm_sci_queue_list("tsn")), 1,
                         "both entries completed - the window was too wide")

    # --- attrition ----------------------------------------------------------

    def test_a_dead_target_drops_out(self):
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        delete_object(self.target)
        self._advance(1.0)
        self.assertEqual(sq.lm_sci_queue_list("tsn"), [])

    def test_scan_revealed_elsewhere_is_dropped_not_rescanned(self):
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        science_set_scan_data(self.player, self.target, {"scan": "Revealed by a mission."})
        self._advance(1.0)
        self.assertEqual(sq.lm_sci_queue_list("tsn"), [])

    # --- timing -------------------------------------------------------------

    def _seconds_at(self, metres):
        self.target.pos = mock_sbs.vec3(float(metres), 0.0, 0.0)
        return sq.lm_sci_scan_seconds(self.player.id, self.target.id)

    def test_a_scan_costs_the_farthest_delay_at_sensor_range(self):
        """The fallback curve runs from point-blank to the ship's OWN sensor range."""
        self.assertAlmostEqual(self._seconds_at(25000), sq.LM_SCI_FARTHEST_SECONDS,
                               places=2)

    def test_closing_on_a_contact_makes_the_scan_faster(self):
        """The rate used to be capped, so every contact INSIDE sensor range took exactly
        the same time and closing bought you nothing."""
        far, mid, near = (self._seconds_at(25000), self._seconds_at(12500),
                          self._seconds_at(2500))
        self.assertLess(mid, far)
        self.assertLess(near, mid)

    def test_distance_keeps_costing_beyond_sensor_range(self):
        """Not clamped at range: a contact twice as far is twice as far along the line,
        so closing always buys time. The cap is on the RESULT, not the distance."""
        self.assertGreater(self._seconds_at(50000), self._seconds_at(25000))

    def test_the_result_is_bounded_at_both_ends(self):
        self.assertGreaterEqual(self._seconds_at(1), sq.LM_SCI_SCAN_FASTEST)
        self.assertLessEqual(self._seconds_at(100_000_000), sq.LM_SCI_SCAN_SLOWEST)

    def test_the_engine_delays_win_over_our_constants(self):
        """`closest_scan_delay` / `farthest_scan_delay` are the engine's own numbers. If a
        bridge publishes them, ours must not be used at all."""
        self.player.data_set.set("closest_scan_delay", 1.0, 0)
        self.player.data_set.set("farthest_scan_delay", 4.0, 0)
        self.assertAlmostEqual(self._seconds_at(25000), 4.0, places=2)
        self.assertAlmostEqual(self._seconds_at(12500), 2.5, places=2)

    # --- what Engineering and the hull contribute ---------------------------

    def test_powering_sensors_up_makes_scans_faster(self):
        """One number, two consoles: the same `sensor_damage_coeff` Engineering shows."""
        base = self._seconds_at(12500)
        self.player.data_set.set("sensor_damage_coeff", 2.0, 0)
        self.assertLess(self._seconds_at(12500), base)

    def test_damaged_sensors_make_scans_slower_but_never_endless(self):
        base = self._seconds_at(12500)
        self.player.data_set.set("sensor_damage_coeff", 0.5, 0)
        hurt = self._seconds_at(12500)
        self.assertGreater(hurt, base)
        self.assertLessEqual(hurt, sq.LM_SCI_SCAN_SLOWEST)

    def test_wrecked_sensors_are_floored_not_fatal(self):
        """A scan that can never finish reads as a bug rather than as damage."""
        from science_scan_time import LM_SCI_SENSOR_COEFF_MIN, lm_sci_sensor_coeff
        self.player.data_set.set("sensor_damage_coeff", 0.001, 0)
        self.assertEqual(lm_sci_sensor_coeff(self.player.id), LM_SCI_SENSOR_COEFF_MIN)

    def test_an_unset_coefficient_means_one_not_zero(self):
        """The engine answers a typed default for a field nothing wrote, and the mock
        answers 0.0 - read literally that divides by zero and no scan ever finishes."""
        from science_scan_time import lm_sci_sensor_coeff, lm_sci_hull_scan_coeff
        self.assertEqual(lm_sci_sensor_coeff(self.player.id), 1.0)
        self.assertEqual(lm_sci_hull_scan_coeff(self.player.id), 1.0)

    def test_a_stronger_hull_scans_faster(self):
        """`scan_strength_coeff` is per HULL, from shipData - a science ship should
        out-scan a freighter."""
        base = self._seconds_at(12500)
        self.player.data_set.set("scan_strength_coeff", 2.0, 0)
        self.assertLess(self._seconds_at(12500), base)

    def test_a_closer_scan_really_does_finish_sooner(self):
        """The curve is only a number until the beat uses it."""
        self.target.pos = mock_sbs.vec3(25000.0, 0.0, 0.0)
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        self._advance(3.0)
        far_pct = sq.lm_sci_queue_percent("tsn", self.target, "scan")
        sq.lm_sci_queue_clear()
        self.target.pos = mock_sbs.vec3(2500.0, 0.0, 0.0)
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        self._advance(3.0)
        self.assertGreater(sq.lm_sci_queue_percent("tsn", self.target, "scan"), far_pct,
                           "the same 3 seconds should buy more progress up close")

    # --- bookkeeping --------------------------------------------------------

    def test_clear_empties_the_reset_ledger_probe(self):
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        self.assertEqual(sq._queue_probe(), 1)
        sq.lm_sci_queue_clear()
        self.assertEqual(sq._queue_probe(), 0)

    def test_revision_moves_on_a_structural_change(self):
        before = sq.lm_sci_queue_revision("tsn")
        sq.lm_sci_queue_add(self.player, self.target, "scan")
        self.assertNotEqual(before, sq.lm_sci_queue_revision("tsn"))


if __name__ == "__main__":
    unittest.main()
