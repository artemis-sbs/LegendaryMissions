"""Rundowns: the registry, the generators, and the union that actually plays.

The generators talk to the sim, so a fake world is injected through sys.modules the same way
test_director_screens does it. Everything else is pure.

Four of these guard behaviour that only shows up after a session has been running a while:

  * `test_dead_subjects_are_dropped` - a rundown of holds on destroyed contacts is what a
    long session turns into if the play set is captured once instead of recomputed.
  * `test_the_union_is_deduplicated` - two selected rundowns naming the same view must be
    one item, or the wall shows it twice while something else never gets airtime.
  * `test_generators_are_stable` - `role()` returns a SET. Without a total order the wall
    reshuffles every dwell, which reads as a fault rather than as direction.
  * `test_reset_clears_user_rundowns` - cosmos_dev reuses ONE interpreter across
    run_next_mission, so a module-level dict nothing clears is a run-2 bug.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_rundowns
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import director_rundowns as dr

# WARM THE REAL MODULES FIRST. The stubs below replace `sbs_utils.procedural.query` in
# sys.modules, and sbs_utils imports `from ..query import to_id` all over its own package -
# so a real module that has not been loaded YET would resolve those against the stub and
# ImportError. Importing what the generators reach, before any stubbing, puts the genuine
# modules in the cache where a later `from ... import` finds them without re-walking.
from sbs_utils.procedural.gui.camera import camera_orbit_lens as _warm_camera_orbit_lens


class _Obj:
    def __init__(self, oid, name):
        self.id = oid
        self.name = name


class _World:
    def __init__(self, roles=None, objects=None, exciting=None):
        self.roles = roles or {}
        self.objects = objects or {}
        self.exciting = exciting or {}


def _install(world):
    """Point the sim-facing imports at `world`. They are imported INSIDE each function, so a
    stub module in sys.modules is what reaches them."""
    roles_mod = types.ModuleType("sbs_utils.procedural.roles")
    roles_mod.role = lambda name: set(world.roles.get(name, ()))

    def any_role(spec):
        out = set()
        for part in spec.split(","):
            out |= set(world.roles.get(part.strip(), ()))
        return out

    roles_mod.any_role = any_role

    query_mod = types.ModuleType("sbs_utils.procedural.query")
    query_mod.to_object = lambda oid: world.objects.get(oid)
    query_mod.to_space_object = query_mod.to_object
    query_mod.get_data_set_value = lambda oid, key, idx=0: world.exciting.get(oid, 0.0)

    saved = {}
    for name, mod in (("sbs_utils.procedural.roles", roles_mod),
                      ("sbs_utils.procedural.query", query_mod)):
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    def restore():
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    return restore


class RegistryTests(unittest.TestCase):
    def setUp(self):
        dr.director_rundowns_reset()

    def tearDown(self):
        dr.director_rundowns_reset()

    def test_new_then_add_then_read_back(self):
        key = dr.director_rundown_new("Act One")
        dr.director_rundown_add_item(key, dr.director_item_con(901, "helm"))
        self.assertEqual(len(dr.director_rundown_items_of(key)), 1)

    def test_adding_the_same_item_twice_is_one_item(self):
        key = dr.director_rundown_new("Act One")
        self.assertTrue(dr.director_rundown_add_item(key, dr.director_item_con(901, "helm")))
        self.assertFalse(dr.director_rundown_add_item(key, dr.director_item_con(901, "helm")))
        self.assertEqual(len(dr.director_rundown_items_of(key)), 1)

    def test_a_rundown_is_ordered_and_can_be_reordered(self):
        key = dr.director_rundown_new("Act One")
        for console in ("helm", "science", "comms"):
            dr.director_rundown_add_item(key, dr.director_item_con(901, console))
        dr.director_rundown_item_move(key, 2, -1)
        order = [i["console"] for i in dr.director_rundown_items_of(key)]
        self.assertEqual(order, ["helm", "comms", "science"])

    def test_moving_off_the_end_does_nothing(self):
        key = dr.director_rundown_new("Act One")
        dr.director_rundown_add_item(key, dr.director_item_con(901, "helm"))
        self.assertIsNone(dr.director_rundown_item_move(key, 0, -1))
        self.assertIsNone(dr.director_rundown_item_move(key, 0, 1))

    def test_remove_and_delete(self):
        key = dr.director_rundown_new("Act One")
        dr.director_rundown_add_item(key, dr.director_item_con(901, "helm"))
        self.assertTrue(dr.director_rundown_item_remove(key, 0))
        self.assertFalse(dr.director_rundown_item_remove(key, 0))
        self.assertTrue(dr.director_rundown_delete(key))
        self.assertFalse(dr.director_rundown_delete(key))

    def test_key_for_maps_a_display_name_back(self):
        # A dropdown carries display TEXT, not keys, so the selection has to map back.
        key = dr.director_rundown_new("Act One")
        self.assertEqual(dr.director_rundown_key_for("Act One"), key)
        self.assertIsNone(dr.director_rundown_key_for("nothing called this"))

    def test_an_empty_name_makes_no_rundown(self):
        self.assertIsNone(dr.director_rundown_new("   "))

    def test_reset_clears_user_rundowns(self):
        dr.director_rundown_new("Act One")
        dr.director_rundowns_reset()
        self.assertEqual(dr.director_rundown_user_keys()[0], [])


class BeatTests(unittest.TestCase):
    """One SHOT can be several BEATS, and a rundown has to be able to hold them.

    THE REPORTED CASE, verbatim: "show a station with a lower third, dwell for 7, then show
    the same station without the lower third". Keyed on subject + mode alone, the second Add
    answered "already in that rundown" and did nothing - so a rundown could not hold more than
    one item per shot at all.
    """

    def setUp(self):
        dr.director_rundowns_reset()
        self.restore = _install(_World(objects={901: _Obj(901, "Phoenix")}))
        self.key = dr.director_rundown_new("Show")
        self.titled = dr.director_item_cam(
            901, "orbit", label="Station",
            overlays=[{"kind": "lower_third", "name": "<<name>>", "line": "<<class>>"}],
            hold=7)
        self.clean = dr.director_item_cam(901, "orbit", label="Station")

    def tearDown(self):
        self.restore()
        dr.director_rundowns_reset()

    def test_the_same_shot_twice_with_different_furniture_is_two_items(self):
        self.assertTrue(dr.director_rundown_add_item(self.key, self.titled))
        self.assertTrue(dr.director_rundown_add_item(self.key, self.clean))
        self.assertEqual(len(dr.director_rundown_items_of(self.key)), 2)

    def test_both_beats_survive_into_the_play_set(self):
        # Adding them was only half of it: the play set de-duplicated on the same coarse key,
        # so the second beat would have been dropped on the way to air even once it went in.
        dr.director_rundown_add_item(self.key, self.titled)
        dr.director_rundown_add_item(self.key, self.clean)
        self.assertEqual(len(dr.director_rundown_play_set([self.key])), 2)

    def test_a_different_hold_alone_is_a_different_beat(self):
        dr.director_rundown_add_item(self.key, dr.director_item_cam(901, "orbit", hold=3))
        self.assertTrue(dr.director_rundown_add_item(
            self.key, dr.director_item_cam(901, "orbit", hold=10)))

    def test_an_identical_item_is_still_refused(self):
        # A double-click must still collapse, or the guard is worthless.
        self.assertTrue(dr.director_rundown_add_item(self.key, self.titled))
        self.assertFalse(dr.director_rundown_add_item(self.key, dict(self.titled)))

    def test_the_two_beats_are_still_ONE_shot(self):
        # Which is what keeps the camera running across the cut: the player compares the shot
        # key to decide whether to re-route, and only the cards change here.
        self.assertEqual(dr.director_item_key(self.titled), dr.director_item_key(self.clean))
        self.assertNotEqual(dr.director_item_ident(self.titled),
                            dr.director_item_ident(self.clean))

    def test_overlay_order_matters_but_dict_order_does_not(self):
        # The fingerprint sorts each overlay's keys, so two identical cards written in a
        # different key order are the same beat.
        a = dr.director_item_cam(901, "orbit", overlays=[{"kind": "hero", "title": "A",
                                                          "subtitle": "B"}])
        b = dr.director_item_cam(901, "orbit", overlays=[{"subtitle": "B", "title": "A",
                                                          "kind": "hero"}])
        self.assertEqual(dr.director_item_ident(a), dr.director_item_ident(b))


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        dr.director_rundowns_reset()
        self.world = _World(
            roles={"__player__": {903, 901, 902}, "director_cam": {902},
                   "__npc__": {950, 951}, "station": {920}, "__terrain__": {930, 931}},
            objects={901: _Obj(901, "Artemis"), 902: _Obj(902, ""),
                     903: _Obj(903, "Intrepid"), 920: _Obj(920, "Phoenix"),
                     930: _Obj(930, "Black Hole"), 931: _Obj(931, ""),
                     950: _Obj(950, "Raider Alpha"), 951: _Obj(951, "Raider Bravo")},
            exciting={950: 4.0, 901: 1.0},
        )
        self.restore = _install(self.world)
        dr.director_bridge_consoles_set(["helm", "science"])

    def tearDown(self):
        self.restore()
        dr.director_rundowns_reset()

    def test_player_ships_excludes_the_director_cam(self):
        items = dr.director_rundown_gen_players()
        self.assertEqual([i["subject"] for i in items], [901, 903])

    def test_generators_are_stable(self):
        # role() is a SET; two evaluations must give the same order or the wall reshuffles.
        self.assertEqual([i["label"] for i in dr.director_rundown_gen_players()],
                         [i["label"] for i in dr.director_rundown_gen_players()])

    def test_bridge_is_one_console_item_per_console_per_ship(self):
        items = dr.director_rundown_gen_bridge()
        self.assertEqual(len(items), 4)                     # 2 ships x 2 consoles
        self.assertTrue(all(i["kind"] == "con" for i in items))

    def test_the_action_is_ranked_and_capped(self):
        items = dr.director_rundown_gen_action()
        self.assertEqual(items[0]["subject"], 950)          # most exciting first
        self.assertLessEqual(len(items), dr.DIRECTOR_ACTION_COUNT)

    def test_scenery_skips_unnamed_terrain(self):
        # A map carries a thousand asteroids; nobody wants a shot of one.
        subjects = [i["subject"] for i in dr.director_rundown_gen_scenery()]
        self.assertIn(920, subjects)
        self.assertIn(930, subjects)
        self.assertNotIn(931, subjects)


class PlaySetTests(unittest.TestCase):
    def setUp(self):
        dr.director_rundowns_reset()
        self.world = _World(
            roles={"__player__": {901}, "director_cam": set()},
            objects={901: _Obj(901, "Artemis")},
        )
        self.restore = _install(self.world)

    def tearDown(self):
        self.restore()
        dr.director_rundowns_reset()

    def test_the_union_is_deduplicated(self):
        a = dr.director_rundown_new("A")
        b = dr.director_rundown_new("B")
        dr.director_rundown_add_item(a, dr.director_item_con(901, "helm"))
        dr.director_rundown_add_item(b, dr.director_item_con(901, "helm"))
        dr.director_rundown_add_item(b, dr.director_item_con(901, "science"))
        self.assertEqual(len(dr.director_rundown_play_set([a, b])), 2)

    def test_selection_order_is_kept(self):
        a = dr.director_rundown_new("A")
        dr.director_rundown_add_item(a, dr.director_item_con(901, "helm"))
        dr.director_rundown_add_item(a, dr.director_item_con(901, "comms"))
        self.assertEqual([i["console"] for i in dr.director_rundown_play_set([a])],
                         ["helm", "comms"])

    def test_dead_subjects_are_dropped(self):
        a = dr.director_rundown_new("A")
        dr.director_rundown_add_item(a, dr.director_item_con(901, "helm"))
        dr.director_rundown_add_item(a, dr.director_item_con(999, "helm"))   # never existed
        self.assertEqual(len(dr.director_rundown_play_set([a])), 1)

    def test_nothing_selected_is_an_empty_set_not_a_crash(self):
        self.assertEqual(dr.director_rundown_play_set(None), [])
        self.assertEqual(dr.director_rundown_play_set([]), [])

    def test_rows_carry_a_live_count(self):
        a = dr.director_rundown_new("Act One")
        dr.director_rundown_add_item(a, dr.director_item_con(901, "helm"))
        labels, keys = dr.director_rundown_rows()
        self.assertEqual(len(labels), len(keys))
        self.assertTrue(any(l.startswith("Act One") and l.endswith("1") for l in labels),
                        labels)


if __name__ == "__main__":
    unittest.main()
