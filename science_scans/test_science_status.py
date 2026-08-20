"""The enemy STATUS tab (science_scans/science_status.py) and the elite tell behind it.

Two things these pin, because both were defects rather than gaps:

* the line is REBUILT from the ship's blob and the declared tell every time, so a line
  that stopped being true stops being shown - the old splice-into-my-own-output writer
  left "Cloak was activated" on the console for the rest of the mission;
* the elite ability tree is attached FIRST and once, so an elite that already carries a
  movement brain still gets to use its abilities. A Select stops at the first child that
  succeeds, so getting this wrong is silent.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest science_scans.test_science_status
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs
from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.mast.mast_node import MastNode
from sbs_utils.procedural.brain import brain_add
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.procedural.timers import set_timer
from sbs_utils.spaceobject import SpaceObject

from science_scans import science_status as S
from fleets import elite_abilitites as E


class _FakeLabel(MastNode):
    """Stands in for an ability label. `brain_add` takes a MastNode straight through,
    and `elite_ability_meta` only ever asks a label for metadata."""

    def __init__(self, name, meta=None):
        self.name = name
        self._meta = meta or {}

    def get_inventory_value(self, key, default=None):
        return self._meta.get(key, default)


class _Base(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        SpaceObject.clear()
        S.science_status_clear_all()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent())
        self.enemy = to_id(npc_spawn(0, 0, 0, "Raider One", "raider,skaraan",
                                     "tsn_battleship", "behav_npcship"))

    def tearDown(self):
        FrameContext.context = None
        S.science_status_clear_all()
        SpaceObject.clear()

    def blob(self):
        from sbs_utils.procedural.query import to_object
        return to_object(self.enemy).data_set


class ConditionLine(_Base):
    """The resting half of the line - what the tab says about an ordinary enemy, which
    until now was a placeholder telling the officer the software could not do this."""

    def test_an_undamaged_ship_is_ready_for_combat(self):
        self.assertEqual(S.science_condition_text(self.enemy), S.SCIENCE_STATUS_OK)

    def test_the_engine_tracks_all_four_systems_on_an_npc(self):
        """The whole line rests on these fields existing on a spawned NPC. If they do
        not, everything below is measuring the fallback rather than the ship."""
        blob = self.blob()
        for index in range(len(S.SCIENCE_SYSTEMS)):
            self.assertGreater(blob.get("system_max_damage", index) or 0, 0)

    def test_a_damaged_system_is_named(self):
        self.blob().set("system_damage", 3.0, 1)      # 1 == engines
        self.assertEqual(S.science_condition_text(self.enemy),
                         "Its engines are damaged.")

    def test_the_worst_system_wins(self):
        self.blob().set("system_damage", 1.0, 0)
        self.blob().set("system_damage", 4.0, 2)      # 2 == sensors
        self.assertIn("sensors", S.science_condition_text(self.enemy))

    def test_repairing_is_only_said_when_the_damage_is_actually_FALLING(self):
        """Nothing in this mission repairs an NPC's systems, so a flat "repairing"
        would be a standing lie. It is a delta, not a state."""
        self.blob().set("system_damage", 4.0, 1)
        S.science_status_track(self.enemy, self.enemy)     # take the first sample
        self.assertEqual(S.science_condition_text(self.enemy),
                         "Its engines are damaged.")
        self.blob().set("system_damage", 2.0, 1)
        self.assertEqual(S.science_condition_text(self.enemy),
                         "Repairing damage to its engines.")

    def test_a_dropped_shield_facet_is_named(self):
        self.blob().set("shield_val", 0.0, 0)
        self.assertEqual(S.science_condition_text(self.enemy),
                         "Its forward shields are down.")

    def test_a_partial_facet_reads_as_weakened_not_down(self):
        most = self.blob().get("shield_max_val", 1)
        self.blob().set("shield_val", most / 2.0, 1)
        self.assertEqual(S.science_condition_text(self.enemy),
                         "Its aft shields are weakened.")

    def test_a_rising_facet_reads_as_rebuilding(self):
        most = self.blob().get("shield_max_val", 0)
        self.blob().set("shield_val", most * 0.2, 0)
        S.science_status_track(self.enemy, self.enemy)
        self.blob().set("shield_val", most * 0.6, 0)
        self.assertEqual(S.science_condition_text(self.enemy),
                         "Rebuilding its forward shields.")

    def test_systems_are_reported_ahead_of_shields(self):
        self.blob().set("system_damage", 2.0, 0)
        self.blob().set("shield_val", 0.0, 0)
        self.assertIn("weapons", S.science_condition_text(self.enemy))

    def test_a_ship_that_is_not_there_says_nothing(self):
        """A contact can die between the tick that queued it and the tick that renders
        it, and a status line is not worth an exception."""
        self.assertEqual(S.science_condition_text(999999), "")
        self.assertEqual(S.science_condition_text(None), "")

    def test_the_line_never_contains_a_BRACE(self):
        """MAST re-runs f-string formatting on an assigned string, so a brace in this
        text would raise at the caller's assignment, pointing at their code."""
        self.blob().set("system_damage", 2.0, 1)
        set_inventory_value(self.enemy, S.SCIENCE_TELL_KEY, "Preparing to cloak")
        line = S.science_status_text(self.enemy)
        self.assertNotIn("{", line)
        self.assertNotIn("}", line)
        self.assertTrue(line.isascii())


class TheTell(_Base):
    """The declared half - what a system elsewhere says is true right now."""

    def test_no_tell_leaves_just_the_condition(self):
        self.assertEqual(S.science_status_text(self.enemy), S.SCIENCE_STATUS_OK)

    def test_a_tell_is_appended_to_the_condition(self):
        set_inventory_value(self.enemy, S.SCIENCE_TELL_KEY, "Preparing to cloak")
        self.assertEqual(S.science_status_text(self.enemy),
                         S.SCIENCE_STATUS_OK + " Preparing to cloak")

    def test_a_tell_with_a_timer_counts_down(self):
        """The countdown is what makes the tell actionable - the officer can say how
        long the bridge has, not just that something is coming."""
        set_timer(self.enemy, E.ELITE_WARMUP_TIMER, 25)
        set_inventory_value(self.enemy, S.SCIENCE_TELL_KEY, "Preparing to cloak")
        set_inventory_value(self.enemy, S.SCIENCE_TELL_TIMER_KEY, E.ELITE_WARMUP_TIMER)
        self.assertRegex(S.science_status_text(self.enemy), r"Preparing to cloak - \d+s$")

    def test_a_tell_whose_timer_has_run_out_drops_the_countdown(self):
        set_inventory_value(self.enemy, S.SCIENCE_TELL_KEY, "Preparing to cloak")
        set_inventory_value(self.enemy, S.SCIENCE_TELL_TIMER_KEY, E.ELITE_WARMUP_TIMER)
        self.assertTrue(S.science_status_text(self.enemy).endswith("Preparing to cloak"))

    def test_clearing_the_tell_takes_the_line_down(self):
        """The defect this whole module exists for: the old writer never cleared, so a
        ship that cloaked once read as cloaking forever."""
        set_inventory_value(self.enemy, S.SCIENCE_TELL_KEY, "Preparing to cloak")
        self.assertIn("cloak", S.science_status_text(self.enemy))
        E.elite_charge_clear(self.enemy)
        self.assertEqual(S.science_status_text(self.enemy), S.SCIENCE_STATUS_OK)

    def test_the_line_is_rebuilt_not_spliced(self):
        """Two different tells in a row must not both appear - there is no accumulated
        string to parse, which is what retires the "starts with Dynamic" sentinel."""
        set_inventory_value(self.enemy, S.SCIENCE_TELL_KEY, "Preparing to cloak")
        S.science_status_text(self.enemy)
        set_inventory_value(self.enemy, S.SCIENCE_TELL_KEY, "Preparing to warp")
        line = S.science_status_text(self.enemy)
        self.assertIn("warp", line)
        self.assertNotIn("cloak", line)


class Pushing(_Base):
    def test_an_untracked_ship_is_never_written(self):
        self.assertFalse(S.science_status_push(self.enemy))

    def test_a_push_no_ops_when_nothing_moved(self):
        """It runs once a second per contact; a push that always wrote would rewrite
        the console for nothing."""
        S.science_status_track(self.enemy, self.enemy)
        self.assertFalse(S.science_status_push(self.enemy))

    def test_a_dead_contact_is_dropped_from_the_registry(self):
        S.science_status_track(self.enemy, self.enemy)
        SpaceObject.clear()
        S.science_status_tick()
        self.assertFalse(S.science_status_push(self.enemy))


class AbilityTiming(_Base):
    """Warm-up and cooldown are authored on the ability and scaled for the crew."""

    def setUp(self):
        super().setUp()
        self._saved = dict(E.abilities)
        E.abilities = {
            "elite/cloak": _FakeLabel("elite_cloak_start",
                                      {"display_name": "Cloak", "warm_up": 25,
                                       "cool_down": 10,
                                       "warm_up_text": "Preparing to cloak"}),
            "elite/eft": _FakeLabel("elite_turn_start",
                                    {"display_name": "HET", "cool_down": 10}),
        }
        E.all_abilities = E.abilities | E.engine_abilities

    def tearDown(self):
        E.abilities = self._saved
        E.all_abilities = E.abilities | E.engine_abilities
        super().tearDown()

    def test_an_authored_baseline_plays_as_authored_at_mid_difficulty(self):
        self.assertEqual(round(E.elite_scale_time(25, E.ELITE_LEVEL_MID)), 25)

    def test_a_weaker_crew_gets_more_warning(self):
        self.assertGreater(E.elite_scale_time(25, 1), E.elite_scale_time(25, 6))

    def test_a_stronger_crew_gets_less(self):
        self.assertLess(E.elite_scale_time(25, 11), E.elite_scale_time(25, 6))

    def test_a_tell_never_scales_below_readable(self):
        self.assertGreaterEqual(E.elite_scale_time(4, 11), E.ELITE_TIME_MIN)

    def test_an_ability_with_no_warm_up_charges_instantly(self):
        """The whole back-compat story: an ability a mission injected through
        elite_script_abilities declares nothing and behaves exactly as it always did."""
        self.assertEqual(E.elite_ability_warm_up(self.enemy, "elite/eft"), 0.0)
        self.assertEqual(E.elite_charge_begin(self.enemy, "elite/eft"), 0.0)
        self.assertIsNone(get_inventory_value(self.enemy, E.ELITE_TELL_KEY, None))

    def test_an_engine_ability_has_no_metadata_and_does_not_raise(self):
        self.assertEqual(E.elite_ability_warm_up(self.enemy, "elite_low_vis"), 0.0)

    def test_charging_puts_the_ability_s_own_words_on_the_tab(self):
        E.elite_charge_begin(self.enemy, "elite/cloak")
        self.assertIn("Preparing to cloak", S.science_status_text(self.enemy))

    def test_an_ability_without_its_own_words_still_says_something(self):
        E.abilities["elite/cloak"] = _FakeLabel("x", {"display_name": "Cloak",
                                                      "warm_up": 25})
        E.all_abilities = E.abilities | E.engine_abilities
        self.assertEqual(E.elite_ability_warm_up_text("elite/cloak"),
                         "Preparing to use Cloak")

    def test_aborting_forgets_the_pending_ability_as_well_as_the_tell(self):
        E.elite_charge_begin(self.enemy, "elite/cloak")
        set_inventory_value(self.enemy, "ELITE_PENDING_ABILITY", "elite/cloak")
        E.elite_charge_abort(self.enemy)
        self.assertIsNone(get_inventory_value(self.enemy, "ELITE_PENDING_ABILITY", None))
        self.assertEqual(S.science_status_text(self.enemy), S.SCIENCE_STATUS_OK)

    def test_every_shipped_scripted_ability_declares_a_cooldown(self):
        """A missing key is silent - the ability just loses its cooldown - so the set
        is checked rather than trusted."""
        E.abilities = self._saved
        E.all_abilities = E.abilities | E.engine_abilities
        for ability in E.abilities:
            self.assertTrue(E.elite_ability_meta(ability, "cool_down", 0),
                            f"{ability} declares no cool_down")


class BrainAttach(_Base):
    """A Select stops at the first child that succeeds, so where the tree lands is the
    difference between an elite that uses its abilities and one that never does."""

    def test_it_attaches_to_a_ship_with_no_brain(self):
        self.assertTrue(E.elite_brain_attach(self.enemy, _FakeLabel("elite_tree")))
        root = get_inventory_value(self.enemy, "__BRAIN__", None)
        self.assertEqual(len(root.children), 1)

    def test_a_ship_that_ALREADY_HAS_a_brain_still_gets_the_tree(self):
        """The guard this replaces asked whether the ship had any brain at all, so a
        boss or prefab enemy that arrived with a movement brain never got one."""
        brain_add(self.enemy, _FakeLabel("movement"))
        self.assertTrue(E.elite_brain_attach(self.enemy, _FakeLabel("elite_tree")))
        root = get_inventory_value(self.enemy, "__BRAIN__", None)
        self.assertEqual([c.label.name for c in root.children],
                         ["elite_tree", "movement"])

    def test_the_tree_goes_FIRST_or_a_chasing_elite_starves_it(self):
        brain_add(self.enemy, _FakeLabel("chase"))
        E.elite_brain_attach(self.enemy, _FakeLabel("elite_tree"))
        root = get_inventory_value(self.enemy, "__BRAIN__", None)
        self.assertEqual(root.children[0].label.name, "elite_tree")

    def test_attaching_twice_adds_one_tree(self):
        """The GM add-ability button schedules the attach label again every time."""
        E.elite_brain_attach(self.enemy, _FakeLabel("elite_tree"))
        self.assertFalse(E.elite_brain_attach(self.enemy, _FakeLabel("elite_tree")))
        root = get_inventory_value(self.enemy, "__BRAIN__", None)
        self.assertEqual(len(root.children), 1)


if __name__ == "__main__":
    unittest.main()
