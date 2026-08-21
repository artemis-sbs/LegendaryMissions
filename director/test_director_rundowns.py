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
import director_bind as db

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

    def test_replace_swaps_in_place(self):
        key = dr.director_rundown_new("Act One")
        for console in ("helm", "science", "comms"):
            dr.director_rundown_add_item(key, dr.director_item_con(901, console))
        self.assertTrue(dr.director_rundown_item_replace(
            key, 1, dr.director_item_con(901, "engineering")))
        order = [i["console"] for i in dr.director_rundown_items_of(key)]
        self.assertEqual(order, ["helm", "engineering", "comms"])

    def test_replace_does_NOT_dedupe(self):
        # Add's "you already have it" is right for Add. Replace means "make row 1 be this", and
        # refusing because row 2 already matches would leave the operator staring at a row that
        # did not change with nothing to say why.
        key = dr.director_rundown_new("Act One")
        dr.director_rundown_add_item(key, dr.director_item_con(901, "helm"))
        dr.director_rundown_add_item(key, dr.director_item_con(901, "science"))
        self.assertTrue(dr.director_rundown_item_replace(
            key, 0, dr.director_item_con(901, "science")))
        order = [i["console"] for i in dr.director_rundown_items_of(key)]
        self.assertEqual(order, ["science", "science"])

    def test_replace_off_the_end_does_nothing(self):
        key = dr.director_rundown_new("Act One")
        dr.director_rundown_add_item(key, dr.director_item_con(901, "helm"))
        self.assertFalse(dr.director_rundown_item_replace(key, 5, dr.director_item_con(901, "x")))
        self.assertFalse(dr.director_rundown_item_replace(key, None, dr.director_item_con(901, "x")))
        self.assertFalse(dr.director_rundown_item_replace(key, 0, None))
        self.assertEqual(len(dr.director_rundown_items_of(key)), 1)

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


class TreeTests(unittest.TestCase):
    """The main page's list: rundowns as headers, items as children, green for what is on air.

    `test_a_label_does_not_change_as_the_feed_moves` is the load-bearing one. A listbox decides
    what is SELECTED by comparing items with `==`, so if the green were baked into the row text
    the operator's selection would be dropped every time the show advanced.
    """

    def setUp(self):
        dr.director_rundowns_reset()
        self.restore = _install(_World(
            roles={"__player__": {901}, "director_cam": set(), "station": {950}},
            objects={901: _Obj(901, "Artemis"), 950: _Obj(950, "Phoenix")}))
        self.key = dr.director_rundown_new("My Show")
        self.titled = dr.director_item_cam(
            950, "orbit", overlays=[{"kind": "lower_third", "name": "a", "line": "b"}], hold=7)
        self.clean = dr.director_item_cam(950, "orbit")
        dr.director_rundown_add_item(self.key, self.titled)
        dr.director_rundown_add_item(self.key, self.clean)

    def tearDown(self):
        self.restore()
        dr.director_rundowns_reset()

    def _headers(self, items):
        from sbs_utils.procedural.gui.listbox import gui_list_box_is_header
        return [i for i in items if gui_list_box_is_header(i)]

    def _rows(self, items):
        from sbs_utils.procedural.gui.listbox import gui_list_box_is_header
        return [i.label for i in items if not gui_list_box_is_header(i)]

    def test_items_mode_shows_rundowns_and_their_items(self):
        items, keys = dr.director_rundown_tree_rows(None, True)
        self.assertEqual(len(items), len(keys))
        self.assertTrue(self._headers(items))
        self.assertTrue(self._rows(items))

    def test_rundowns_mode_shows_ONLY_rundowns(self):
        # Not collapsed branches - absent. The items are not the unit of choice there.
        items, keys = dr.director_rundown_tree_rows(None, False)
        self.assertEqual(self._rows(items), [])
        self.assertTrue(all(k[0] == "run" for k in keys))

    def test_keys_are_parallel_to_items(self):
        # get_selected_index() walks unfiltered_items, so index i of a selection has to be
        # index i of the keys - a header slot cannot be skipped.
        for with_items in (True, False):
            items, keys = dr.director_rundown_tree_rows(None, with_items)
            self.assertEqual(len(items), len(keys))

    def test_the_on_air_item_and_its_rundown_go_green(self):
        items, _keys = dr.director_rundown_tree_rows(dr.director_item_ident(self.titled), True)
        green = dr._TREE_GREEN
        self.assertTrue(any(h.label in green for h in self._headers(items)))
        self.assertEqual(len([r for r in self._rows(items) if r in green]), 1)

    def test_the_rundown_goes_green_even_with_its_items_hidden(self):
        # A headers-only list still has to say where the show is.
        items, _keys = dr.director_rundown_tree_rows(dr.director_item_ident(self.titled), False)
        self.assertTrue(any(h.label in dr._TREE_GREEN for h in self._headers(items)))

    def test_nothing_on_air_is_nothing_green(self):
        dr.director_rundown_tree_rows(None, True)
        self.assertEqual(dr._TREE_GREEN, set())

    def test_green_is_rebuilt_not_accumulated(self):
        dr.director_rundown_tree_rows(dr.director_item_ident(self.titled), True)
        first = set(dr._TREE_GREEN)
        dr.director_rundown_tree_rows(dr.director_item_ident(self.clean), True)
        self.assertNotEqual(first, dr._TREE_GREEN)

    def test_a_label_does_not_change_as_the_feed_moves(self):
        # THE ONE THAT MATTERS. Green lives in a set beside the rows, never in the text - a row
        # whose label changed when the show advanced would drop the operator's selection.
        a, _ = dr.director_rundown_tree_rows(dr.director_item_ident(self.titled), True)
        b, _ = dr.director_rundown_tree_rows(dr.director_item_ident(self.clean), True)
        self.assertEqual([str(x) for x in self._rows(a)], [str(x) for x in self._rows(b)])

    def test_rows_are_unique(self):
        # A tree makes duplicates likely: the same shot can sit in two rundowns.
        items, _keys = dr.director_rundown_tree_rows(None, True)
        labels = [i.label for i in self._headers(items)] + self._rows(items)
        self.assertEqual(len(labels), len(set(labels)), labels)

    def test_a_row_says_what_the_item_carries(self):
        items, _keys = dr.director_rundown_tree_rows(None, True)
        titled_row = [r for r in self._rows(items) if "7s" in r]
        self.assertTrue(titled_row)
        self.assertIn("lower third", titled_row[0])

    def test_selecting_an_item_names_its_rundown(self):
        self.assertEqual(dr.director_tree_selected_rundowns([("item", self.key, 0)]), [self.key])

    def test_selecting_headers_names_the_rundowns(self):
        self.assertEqual(dr.director_tree_selected_rundowns([("run", "action"), ("run", "players")]),
                         ["action", "players"])

    def test_a_rundown_is_named_once_however_it_was_picked(self):
        self.assertEqual(
            dr.director_tree_selected_rundowns([("run", self.key), ("item", self.key, 1)]),
            [self.key])

    def test_the_selected_item_is_the_item(self):
        picked = dr.director_tree_selected_item([("item", self.key, 0)])
        self.assertEqual(dr.director_item_ident(picked), dr.director_item_ident(self.titled))

    def test_a_header_selection_is_not_an_item(self):
        # Rundowns mode selects headers, and taking one to air would be meaningless.
        self.assertIsNone(dr.director_tree_selected_item([("run", self.key)]))

    def test_a_stale_index_is_not_a_crash(self):
        # The rundown shrank between the build and the click.
        self.assertIsNone(dr.director_tree_selected_item([("item", self.key, 99)]))
        self.assertIsNone(dr.director_tree_selected_item([("item", "nope", 0)]))

    def test_an_empty_selection_is_nothing(self):
        self.assertEqual(dr.director_tree_selected_rundowns([]), [])
        self.assertIsNone(dr.director_tree_selected_item(None))

    def test_item_rows_carry_the_listboxs_own_indent(self):
        # LayoutListbox indents a row by `item.indent * indent_pixels`, read off the ITEM - so
        # a plain string row has nothing to read and draws flush under its header. Carrying the
        # attribute is what puts the children in from the rundown.
        items, _keys = dr.director_rundown_tree_rows(None, True)
        from sbs_utils.procedural.gui.listbox import gui_list_box_is_header
        rows = [i for i in items if not gui_list_box_is_header(i)]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row.indent, 1)
            self.assertEqual(row.visual_indent, 1)
        for head in self._headers(items):
            self.assertEqual(head.indent, 0)

    def test_collapse_survives_a_rebuild(self):
        # THE ONE THE OPERATOR FELT. A rebuild makes NEW header objects and the listbox toggles
        # the OLD ones in place, so without a memory every repaint re-opened every branch - and
        # this page repaints whenever the feed advances.
        class _LB:
            def __init__(self, items):
                self.unfiltered_items = list(items)

        items, keys = dr.director_rundown_tree_rows(None, True)
        for item, key in zip(items, keys):
            if key[0] == "run" and key[1] == self.key:
                item.collapse = True
        dr.director_tree_remember_collapse(_LB(items), keys)
        items2, keys2 = dr.director_rundown_tree_rows(None, True)
        shut = [k[1] for i, k in zip(items2, keys2)
                if k[0] == "run" and getattr(i, "collapse", False)]
        self.assertEqual(shut, [self.key])

    def test_a_mission_reset_opens_every_branch(self):
        class _LB:
            def __init__(self, items):
                self.unfiltered_items = list(items)

        items, keys = dr.director_rundown_tree_rows(None, True)
        for item, key in zip(items, keys):
            if key[0] == "run":
                item.collapse = True
        dr.director_tree_remember_collapse(_LB(items), keys)
        dr.director_rundowns_reset()
        items2, keys2 = dr.director_rundown_tree_rows(None, True)
        self.assertFalse(any(getattr(i, "collapse", False) for i in items2))

    def test_remembering_from_nothing_is_not_a_crash(self):
        # The FIRST build has no previous listbox to read.
        dr.director_tree_remember_collapse(None, None)

    def test_collapsible_and_selectable_are_opposite_header_modes(self):
        # The listbox gives the header's whole section the collapse click ONLY when it is not
        # selectable; ask for both and the section becomes the select and collapse is handed to
        # the template instead. So picking rundowns gets selectable headers and picking items
        # gets collapsible ones.
        runs, _k = dr.director_rundown_tree_rows(None, False)
        items, _k2 = dr.director_rundown_tree_rows(None, True)
        self.assertTrue(all(h.selectable for h in self._headers(runs)))
        self.assertFalse(any(h.selectable for h in self._headers(items)))

    def test_a_carried_selection_is_filtered_to_what_the_mode_can_select(self):
        picked = [("run", self.key), ("item", self.key, 0)]
        self.assertEqual(dr.director_tree_keep_selectable(picked, True), [("item", self.key, 0)])
        self.assertEqual(dr.director_tree_keep_selectable(picked, False), [("run", self.key)])
        self.assertEqual(dr.director_tree_keep_selectable(None, True), [])


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

    def test_the_stock_rundowns_carry_furniture(self):
        # They are the first thing a new operator sends to air, and a bare shot of an unnamed
        # ship is the least the console can do rather than a demonstration of it.
        for item in dr.director_rundown_gen_players():
            self.assertEqual([o["kind"] for o in item["overlays"]], ["lower_third"])
        for item in dr.director_rundown_gen_action():
            self.assertEqual([o["kind"] for o in item["overlays"]], ["banner"])
        for item in dr.director_rundown_gen_scenery():
            self.assertEqual([o["kind"] for o in item["overlays"]], ["hero"])

    def test_generated_furniture_is_a_TEMPLATE(self):
        # THE WHOLE REASON a generator can carry furniture at all: it makes one item per ship,
        # so there is nowhere to type "Artemis". Baking the name at generate time would name the
        # wrong ship for every other item - and for a BOUND beat, for every other click.
        item = dr.director_rundown_gen_players()[0]
        self.assertEqual(item["overlays"][0]["name"], "<<name>>")
        self.assertNotIn("Artemis", str(item["overlays"]))

    def test_each_generated_item_gets_its_own_overlay_dict(self):
        # They are shared module constants; handing the same dict to two items would let an
        # edit to one silently change the other.
        items = dr.director_rundown_gen_players()
        self.assertIsNot(items[0]["overlays"][0], items[1]["overlays"][0])

    def test_the_bridge_wall_is_gone(self):
        # Its premise died with the screen-distribution model: with one program feed showing one
        # item, twelve console beats are a rotation, not a wall.
        self.assertFalse(hasattr(dr, "director_rundown_gen_bridge"))
        self.assertEqual(dr.director_rundown_items_of("bridge"), [])

    def test_follow_names_no_object_at_all(self):
        items = dr.director_rundown_gen_follow()
        self.assertEqual(len(items), 3)
        for item in items:
            self.assertTrue(db.director_bind_is(item["subject"]), item)

    def test_crew_is_bound_console_beats(self):
        items = dr.director_rundown_gen_crew()
        self.assertEqual(len(items), len(dr.DIRECTOR_CREW_CONSOLES))
        for item in items:
            self.assertEqual(item["kind"], "con")
            self.assertTrue(db.director_bind_is(item["ship"]), item)

    def test_crew_offers_no_mainscreen_or_cinematic(self):
        # Neither is a crew view, and a `cinematic` console beat is the worse of the two: a
        # full-screen 3dview with no camera applied to it.
        consoles = [i["console"] for i in dr.director_rundown_gen_crew()]
        self.assertNotIn("mainscreen", consoles)
        self.assertNotIn("cinematic", consoles)

    def test_a_bound_console_item_is_labelled_from_the_binding(self):
        # to_object on a binding answers None, which used to label every one "Helm - no ship".
        item = dr.director_rundown_gen_crew()[0]
        self.assertIn("Selection", item["label"])
        self.assertNotIn("no ship", item["label"])

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


class BoundSubjectTests(unittest.TestCase):
    """Items whose subject is the Director's SELECTION rather than a baked id.

    The whole value of these is that the item survives being re-pointed, so the tests that
    matter are the ones about IDENTITY - an item that changed identity when the operator
    clicked would lose the feed's place and snap the show back to its first beat.
    """

    def setUp(self):
        dr.director_rundowns_reset()
        db.director_selection_reset()
        self.world = _World(
            roles={"__player__": {901, 902}, "director_cam": set()},
            objects={901: _Obj(901, "Artemis"), 902: _Obj(902, "Raider")},
        )
        self.restore = _install(self.world)
        # The bind resolver reaches for its own selection getters, which the rundowns harness
        # has no reason to carry. Add them to the same stub module.
        query = sys.modules["sbs_utils.procedural.query"]
        self.weapons = {}
        query.get_weapons_selection = lambda oid: self.weapons.get(oid)
        query.get_science_selection = lambda oid: None
        query.get_comms_selection = lambda oid: None
        query.get_grid_selection = lambda oid: None

    def tearDown(self):
        self.restore()
        dr.director_rundowns_reset()
        db.director_selection_reset()

    def test_the_label_names_the_binding_not_a_ship(self):
        # Baking "Artemis" into the row would be a lie the moment the operator clicked
        # anything else - and it is the row that tells them what the item actually does.
        db.director_selection(901)
        item = dr.director_item_cam("<<selected_id>>", "orbit")
        self.assertIn("Selection", item["label"])
        self.assertNotIn("Artemis", item["label"])

    def test_the_subject_resolves_to_whatever_is_selected(self):
        item = dr.director_item_cam("<<selected_id>>", "orbit")
        db.director_selection(901)
        self.assertEqual(dr.director_item_subject_id(item), 901)
        db.director_selection(902)
        self.assertEqual(dr.director_item_subject_id(item), 902)

    def test_the_declared_subject_stays_the_binding(self):
        item = dr.director_item_cam("<<selected_id>>", "orbit")
        db.director_selection(901)
        self.assertEqual(dr.director_item_subject(item), "<<selected_id>>")

    def test_identity_does_not_move_with_the_selection(self):
        # THE LOAD-BEARING ONE. director_play_feeds holds its place by ident; if this moved,
        # _index_of would lose _PROGRAM_HELD and the program would snap to order[0] with the
        # dwell clock reset - on every click.
        item = dr.director_item_cam("<<selected_id>>", "orbit")
        db.director_selection(901)
        before = dr.director_item_ident(item)
        db.director_selection(902)
        self.assertEqual(dr.director_item_ident(item), before)

    def test_a_bound_item_is_skipped_while_it_cannot_resolve(self):
        a = dr.director_rundown_new("A")
        dr.director_rundown_add_item(a, dr.director_item_con(901, "helm"))
        dr.director_rundown_add_item(a, dr.director_item_cam("<<selected_id>>", "orbit"))
        self.assertEqual(len(dr.director_rundown_play_set([a])), 1)
        db.director_selection(902)
        self.assertEqual(len(dr.director_rundown_play_set([a])), 2)

    def test_it_comes_back_the_moment_it_resolves_again(self):
        # Skipping is not removal. A show that dropped a beat permanently the first time the
        # operator deselected would be unusable.
        a = dr.director_rundown_new("A")
        dr.director_rundown_add_item(a, dr.director_item_cam("<<selected_id>>", "orbit"))
        db.director_selection(901)
        self.assertEqual(len(dr.director_rundown_play_set([a])), 1)
        db.director_selection(clear=True)
        self.assertEqual(len(dr.director_rundown_play_set([a])), 0)
        db.director_selection(901)
        self.assertEqual(len(dr.director_rundown_play_set([a])), 1)

    def test_a_console_beat_needs_a_PLAYER_ship(self):
        # Clicking a rock ignores the console list. cv_show would otherwise assign a screen to
        # the asteroid and draw helm widgets for it.
        self.world.roles["__terrain__"] = {930}
        self.world.objects[930] = _Obj(930, "Black Hole")
        a = dr.director_rundown_new("A")
        dr.director_rundown_add_item(a, dr.director_item_con("<<selected_id>>", "helm"))
        db.director_selection(930)
        self.assertEqual(len(dr.director_rundown_play_set([a])), 0)
        db.director_selection(901)
        self.assertEqual(len(dr.director_rundown_play_set([a])), 1)

    def test_the_player_ship_rule_is_CONSOLE_only(self):
        # A camera beat pointed at a rock is a perfectly good shot of a rock.
        self.world.roles["__terrain__"] = {930}
        self.world.objects[930] = _Obj(930, "Black Hole")
        a = dr.director_rundown_new("A")
        dr.director_rundown_add_item(a, dr.director_item_cam("<<selected_id>>", "orbit"))
        db.director_selection(930)
        self.assertEqual(len(dr.director_rundown_play_set([a])), 1)

    def test_a_console_beat_on_a_director_cam_is_skipped(self):
        # Cams are stripped of __player__ at spawn, which is exactly what keeps a camera POINT
        # from being mistaken for a crewable ship.
        self.world.roles["director_cam"] = {940}
        self.world.objects[940] = _Obj(940, "")
        a = dr.director_rundown_new("A")
        dr.director_rundown_add_item(a, dr.director_item_con("<<selected_id>>", "helm"))
        db.director_selection(940)
        self.assertEqual(len(dr.director_rundown_play_set([a])), 0)

    def test_a_hop_resolves_through_the_selected_ship(self):
        a = dr.director_rundown_new("A")
        dr.director_rundown_add_item(
            a, dr.director_item_cam("<<selected_id>><<weapons_selection>>", "chase"))
        db.director_selection(901)
        # No target yet, so the hop falls back to the SHIP - the beat still plays, as a chase
        # of the ship that is not shooting at anything.
        played = dr.director_rundown_play_set([a])
        self.assertEqual(len(played), 1)
        self.assertEqual(dr.director_item_subject_id(played[0]), 901)
        # Now it has one, and the same authored item follows it.
        self.weapons[901] = 902
        played = dr.director_rundown_play_set([a])
        self.assertEqual(len(played), 1)
        self.assertEqual(dr.director_item_subject_id(played[0]), 902)

    def test_two_bindings_are_two_items(self):
        # They resolve to the same ship right now, which is not the same as being one beat.
        a = dr.director_rundown_new("A")
        self.assertTrue(dr.director_rundown_add_item(
            a, dr.director_item_cam("<<selected_id>>", "orbit")))
        self.assertTrue(dr.director_rundown_add_item(
            a, dr.director_item_cam("<<selected_id>>", "chase")))
        self.assertEqual(len(dr.director_rundown_items_of(a)), 2)


class OverlayItemTests(unittest.TestCase):
    """Items that are furniture and nothing else - a title, an intro, an outro."""

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

    def _title(self):
        return dr.director_item_overlay(
            overlays=[{"kind": "hero", "title": "Act One", "subtitle": ""}])

    def test_it_declares_no_subject(self):
        item = self._title()
        self.assertIsNone(dr.director_item_subject(item))
        self.assertIsNone(dr.director_item_subject_id(item))

    def test_it_survives_the_play_set(self):
        # The liveness filter drops what cannot name a live object. An ovl item names nothing
        # ON PURPOSE, and the two have to be told apart or no title ever goes to air.
        a = dr.director_rundown_new("A")
        dr.director_rundown_add_item(a, self._title())
        self.assertEqual(len(dr.director_rundown_play_set([a])), 1)

    def test_every_overlay_item_shares_one_shot_key(self):
        # It has no shot, so it must never read as a NEW one - that is what stops it causing a
        # reroute and cutting away from the shot it is supposed to be drawn over.
        other = dr.director_item_overlay(overlays=[{"kind": "banner", "text": "hi"}])
        self.assertEqual(dr.director_item_key(self._title()), dr.director_item_key(other))

    def test_but_they_are_still_different_items(self):
        other = dr.director_item_overlay(overlays=[{"kind": "banner", "text": "hi"}])
        self.assertNotEqual(dr.director_item_ident(self._title()),
                            dr.director_item_ident(other))

    def test_the_default_label_names_what_it_carries(self):
        # An empty row reads as a broken item, and the row is all the operator has.
        self.assertEqual(self._title()["label"], "hero")

    def test_the_row_tag_says_which_kind_it_is(self):
        self.assertEqual(dr.director_item_row_tag(self._title()), "ovl  ")


if __name__ == "__main__":
    unittest.main()
