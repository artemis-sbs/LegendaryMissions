"""Subject bindings: the chain, and the ways it is allowed to fail.

A bound item is what lets one rundown be re-pointed mid-show, so the interesting tests here
are the failure modes rather than the happy path - a binding that resolves to the WRONG thing
would put a stranger on air and look deliberate.

  * `test_an_unset_console_selection_is_not_object_zero` - `get_weapons_selection` reads the
    blob and the engine's "no target" value is 0, NOT None. Treating that as an id is a live
    bug on a real bridge and invisible in the mock. The fallback does not excuse it: a `is
    None` check would hand object ZERO to the camera instead of falling back.
  * the fallback group - a hop that leads nowhere holds the last LIVE object rather than
    failing, so "chase what the selected ship is shooting at" is a shot of that ship when it
    is shooting at nothing. A fight is full of those moments.
  * `test_an_unknown_token_kills_the_chain` - the one failure that does NOT fall back, and the
    opposite of the overlay resolver's rule on purpose. A visible `<<shpi>>` on a card is
    informative; a camera quietly pointed at the selection by a typo looks deliberate.
  * `test_a_dead_selection_does_not_resolve` - the seed is validated too, because every later
    hop falls back to it.
  * `test_reset_forgets_the_selection` - cosmos_dev reuses ONE interpreter across
    run_next_mission, so a module-level container nothing clears is a run-2 bug.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_bind
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# WARM THE REAL LIBRARY FIRST - see test_director_play for why. `_install` shadows
# sbs_utils.procedural.query, and a first-time import of the gui package while the stub is in
# place fails with an ImportError that reads like a real bug.
import sbs_utils.procedural.gui  # noqa: F401

import director_bind as db


class _Obj:
    def __init__(self, oid, name):
        self.id = oid
        self.name = name


def _install(objects, selections=None):
    """A fake world: `objects` is id -> obj, `selections` is (id, console) -> id.

    The console selections are a dict rather than a blob because that is the only shape these
    hops care about - and `0` is spelled out in the tests that need it, since a missing key
    and a key holding 0 are the two different things this module has to tell apart.
    """
    selections = selections or {}
    query_mod = types.ModuleType("sbs_utils.procedural.query")
    query_mod.to_object = lambda oid: objects.get(oid)
    query_mod.get_weapons_selection = lambda oid: selections.get((oid, "weapons"))
    query_mod.get_science_selection = lambda oid: selections.get((oid, "science"))
    query_mod.get_comms_selection = lambda oid: selections.get((oid, "comms"))
    query_mod.get_grid_selection = lambda oid: selections.get((oid, "grid"))
    saved = sys.modules.get("sbs_utils.procedural.query")
    sys.modules["sbs_utils.procedural.query"] = query_mod

    def restore():
        if saved is None:
            sys.modules.pop("sbs_utils.procedural.query", None)
        else:
            sys.modules["sbs_utils.procedural.query"] = saved

    return restore


class SelectionTests(unittest.TestCase):
    def setUp(self):
        db.director_selection_reset()
        self.restore = _install({1: _Obj(1, "Artemis")})

    def tearDown(self):
        self.restore()
        db.director_selection_reset()

    def test_it_starts_empty(self):
        self.assertIsNone(db.director_selection())
        self.assertEqual(db.director_selection_label(), "nothing selected")

    def test_setting_and_reading(self):
        self.assertEqual(db.director_selection(1), 1)
        self.assertEqual(db.director_selection(), 1)
        self.assertEqual(db.director_selection_label(), "Artemis")

    def test_clearing(self):
        db.director_selection(1)
        self.assertIsNone(db.director_selection(clear=True))

    def test_a_deleted_selection_reads_as_gone(self):
        # Not "nothing selected": the operator DID select something and it blew up, and those
        # are different things to say on the panel.
        db.director_selection(7)
        self.assertEqual(db.director_selection_label(), "gone")

    def test_reset_forgets_the_selection(self):
        db.director_selection(1)
        db.director_selection_reset()
        self.assertIsNone(db.director_selection())


class ChainTests(unittest.TestCase):
    def setUp(self):
        db.director_selection_reset()

    def tearDown(self):
        self.restore()
        db.director_selection_reset()

    def _world(self, objects, selections=None):
        self.restore = _install(objects, selections)

    def test_the_identity_hop(self):
        self._world({1: _Obj(1, "Artemis")})
        db.director_selection(1)
        self.assertEqual(db.director_bind_resolve("<<selected_id>>"), 1)

    def test_one_hop_on(self):
        self._world({1: _Obj(1, "Artemis"), 2: _Obj(2, "Raider")},
                    {(1, "weapons"): 2})
        db.director_selection(1)
        self.assertEqual(
            db.director_bind_resolve("<<selected_id>><<weapons_selection>>"), 2)

    def test_the_chain_seeds_from_the_selection(self):
        # `<<weapons_selection>>` alone means the same as spelling the seed out. That is not a
        # parser convenience - it is what makes "Selection > weapons target" read as one
        # sentence in the picker instead of forcing a prefix nobody would ever omit.
        self._world({1: _Obj(1, "Artemis"), 2: _Obj(2, "Raider")},
                    {(1, "weapons"): 2})
        db.director_selection(1)
        self.assertEqual(db.director_bind_resolve("<<weapons_selection>>"),
                         db.director_bind_resolve("<<selected_id>><<weapons_selection>>"))

    def test_two_hops_on(self):
        # What the selected ship's weapons officer is shooting at, and what THAT ship's science
        # officer is looking at. Nobody has asked for this, but the chain is a chain.
        self._world({1: _Obj(1, "A"), 2: _Obj(2, "B"), 3: _Obj(3, "C")},
                    {(1, "weapons"): 2, (2, "science"): 3})
        db.director_selection(1)
        self.assertEqual(
            db.director_bind_resolve(
                "<<selected_id>><<weapons_selection>><<science_selection>>"), 3)

    def test_nothing_selected_does_not_resolve(self):
        self._world({1: _Obj(1, "Artemis")})
        self.assertIsNone(db.director_bind_resolve("<<selected_id>>"))

    def test_a_dead_selection_does_not_resolve(self):
        # The seed is validated too, because every later hop falls back to it - a dead one
        # would otherwise be what the whole chain settled on.
        self._world({1: _Obj(1, "Artemis")})
        db.director_selection(7)
        self.assertIsNone(db.director_bind_resolve("<<selected_id>><<weapons_selection>>"))

    # --- a hop that leads nowhere falls back to the ship it was asked about ----------------
    #
    # "Chase what the selected ship is shooting at" is a shot of that SHIP when it is shooting
    # at nothing. A fight is full of moments with no target, and a gap in the rotation every
    # time the weapons officer drops theirs is worse direction than the ship itself.

    def test_an_unset_console_selection_is_not_object_zero(self):
        # THE ONE THAT BITES, and the fallback does not excuse it: get_weapons_selection pulls
        # weapon_target_UID straight out of the blob and the engine's "no target" is 0, not
        # None. A `is None` check would hand object ZERO to the camera instead of falling back.
        self._world({1: _Obj(1, "Artemis")}, {(1, "weapons"): 0})
        db.director_selection(1)
        self.assertEqual(db.director_bind_resolve("<<selected_id>><<weapons_selection>>"), 1)

    def test_a_missing_console_selection_falls_back(self):
        self._world({1: _Obj(1, "Artemis")})
        db.director_selection(1)
        self.assertEqual(db.director_bind_resolve("<<selected_id>><<weapons_selection>>"), 1)

    def test_a_dead_hop_target_falls_back(self):
        # The weapons officer is still holding a target that has been destroyed. The chain
        # arrives at an id and that id names nothing, so the ship stands.
        self._world({1: _Obj(1, "Artemis")}, {(1, "weapons"): 99})
        db.director_selection(1)
        self.assertEqual(db.director_bind_resolve("<<selected_id>><<weapons_selection>>"), 1)

    def test_a_hop_that_raises_falls_back(self):
        # A blob read on a tombstoned object can throw from inside the engine. It must come
        # back as the ship, not as a raise that ends the player task.
        def _boom(_oid):
            raise RuntimeError("dangling data set")

        self._world({1: _Obj(1, "Artemis")})
        sys.modules["sbs_utils.procedural.query"].get_weapons_selection = _boom
        db.director_selection(1)
        self.assertEqual(db.director_bind_resolve("<<selected_id>><<weapons_selection>>"), 1)

    def test_a_broken_middle_hop_holds_what_it_had(self):
        # Two hops, and the FIRST one succeeds. The fallback is the last live object, not the
        # seed - so this is a shot of the raider, not of the ship that was aiming at it.
        self._world({1: _Obj(1, "A"), 2: _Obj(2, "Raider")},
                    {(1, "weapons"): 2})
        db.director_selection(1)
        self.assertEqual(
            db.director_bind_resolve(
                "<<selected_id>><<weapons_selection>><<science_selection>>"), 2)

    def test_an_unknown_token_kills_the_chain(self):
        # The ONE failure that does not fall back. It is an authoring error rather than a
        # runtime state, and pointing at the selection instead would look deliberate.
        # Deliberately NOT the overlay resolver's rule, which leaves an unknown token literal.
        self._world({1: _Obj(1, "Artemis")})
        db.director_selection(1)
        self.assertIsNone(db.director_bind_resolve("<<selcted_id>>"))

    def test_the_grid_hop_is_not_offered(self):
        # `grid_selected_UID` names a room or a system on a ship's INTERNAL grid, not a space
        # object - there is nothing out there to point a camera at.
        self.assertNotIn("grid_selection", db.director_bind_tokens())
        self._world({1: _Obj(1, "Artemis")})
        db.director_selection(1)
        self.assertIsNone(db.director_bind_resolve("<<selected_id>><<grid_selection>>"))

    def test_a_string_with_no_tokens_does_not_resolve(self):
        self._world({1: _Obj(1, "Artemis")})
        db.director_selection(1)
        self.assertIsNone(db.director_bind_resolve("selected_id"))
        self.assertIsNone(db.director_bind_resolve(""))


class ShapeTests(unittest.TestCase):
    """What is a binding, what does it read as, and what does the picker offer."""

    def test_is_a_binding(self):
        self.assertTrue(db.director_bind_is("<<selected_id>>"))
        self.assertFalse(db.director_bind_is(901))
        self.assertFalse(db.director_bind_is(""))
        self.assertFalse(db.director_bind_is(None))

    def test_the_label_names_every_hop(self):
        self.assertEqual(db.director_bind_label("<<selected_id>>"), "Selection")
        self.assertEqual(
            db.director_bind_label("<<selected_id>><<weapons_selection>>"),
            "Selection > weapons target")

    def test_the_label_spells_out_an_implicit_seed(self):
        # The seed is implicit in the STRING; it is not implicit in a row an operator reads.
        self.assertEqual(db.director_bind_label("<<weapons_selection>>"),
                         "Selection > weapons target")

    def test_the_two_ends_of_the_picker_round_trip(self):
        # "" and None are both falsy and mean completely different items, so a picker that
        # could not tell them apart would turn every fixed shot into a title card.
        values, labels = db.director_bind_choices()
        self.assertIn(db.DIRECTOR_BIND_FIXED, values)
        self.assertIn(db.DIRECTOR_BIND_NONE, values)
        for value, label in zip(values, labels):
            self.assertEqual(db.director_bind_for(label), value)
            self.assertEqual(db.director_bind_label_of(value), label)

    def test_an_unrecognized_label_falls_back_to_fixed(self):
        # Fixed, not None: an unreadable dropdown value must not silently turn a shot into an
        # overlay-only beat.
        self.assertEqual(db.director_bind_for("nonsense"), db.DIRECTOR_BIND_FIXED)

    def test_the_picker_list_survives_a_list_property(self):
        # The labels reach the wire as one `list: a,b,c;` property, so a comma or a semicolon
        # in one of them would silently become two entries or end the property early.
        for label in db.director_bind_choices()[1]:
            self.assertNotIn(",", label)
            self.assertNotIn(";", label)

    def test_a_hand_typed_chain_still_gets_a_readable_label(self):
        self.assertEqual(db.director_bind_label_of("<<selected_id>><<comms_selection>>"),
                         "Selection > comms target")


if __name__ == "__main__":
    unittest.main()
