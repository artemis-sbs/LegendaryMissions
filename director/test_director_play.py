"""The two feeds, and the invariant that stops an overlay getting stuck.

Pure arithmetic, so most of these need no world at all except for `exciting`, which is stubbed.

Five guard behaviour that is only visible with several windows open, or only after the fault
has already happened:

  * `test_reset_releases_before_it_forgets` - THE ONE. `_SLOTS` is the only record of which
    overlay slots are up, and `overlay_clear` needs the slot name. Dropping the record while
    cards are on screen orphans them permanently, and Send used to do exactly that - which is
    why a stuck lower third outlived Stop.
  * `test_entering_a_screen_clears_whatever_it_carried` - the invariant six separate leaks
    turned out to be instances of. Every reroute target calls it first.
  * `test_furniture_only_changes_do_not_reroute` - preview restages on every keystroke, and a
    reroute per keystroke would rebuild the page and restart the camera each time.
  * `test_forgetting_is_over_both_feeds_at_once` - pruning per feed would have the program
    pass forget every preview screen and vice versa, so everything would read as changed on
    every tick and both feeds would rebuild continuously.
  * `test_auto_holds_through_noise` - two contacts trading a fractionally higher score would
    otherwise swap the feed several times a minute, which reads as a fault, not as direction.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_play
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import director_rundowns as dr
import director_play as dp


def _install(exciting):
    """Only `exciting` needs a world here."""
    query_mod = types.ModuleType("sbs_utils.procedural.query")
    query_mod.get_data_set_value = lambda oid, key, idx=0, default=None: exciting.get(oid, 0.0)
    # to_object as well: this module SHADOWS the real query module, and director_item_cam
    # reaches for it to name an unlabelled item. A partial stub fails as an ImportError from
    # inside library code, which reads like a real bug rather than a gap in the harness.
    query_mod.to_object = lambda oid: None
    saved = sys.modules.get("sbs_utils.procedural.query")
    sys.modules["sbs_utils.procedural.query"] = query_mod

    def restore():
        if saved is None:
            sys.modules.pop("sbs_utils.procedural.query", None)
        else:
            sys.modules["sbs_utils.procedural.query"] = saved

    return restore


def _items(n):
    return [dr.director_item_con(900 + i, "helm", "item" + str(i)) for i in range(n)]


class FeedTests(unittest.TestCase):
    """Which item each feed shows, and the hold that stops it flickering."""

    def setUp(self):
        dp.director_play_reset()
        self.restore = _install({})

    def tearDown(self):
        self.restore()
        dp.director_play_reset()

    def _prog(self, items, **kw):
        return dp.director_play_feeds(items, **kw)["program"]

    def _prev(self, items, **kw):
        return dp.director_play_feeds(items, **kw)["preview"]

    # --- program -------------------------------------------------------------------------

    def test_one_item_for_every_program_screen(self):
        # Broadcast, not a wall. Two program screens show the SAME thing.
        item = self._prog(_items(3))
        plan = dp.director_play_plan(item, [10, 11, 12])
        self.assertEqual([p["item"]["label"] for p in plan], [item["label"]] * 3)

    def test_it_starts_at_the_front(self):
        self.assertEqual(self._prog(_items(3))["label"], "item0")

    def test_the_dwell_advances_it(self):
        items = _items(3)
        got = [self._prog(items)["label"]]
        for _ in range(4):
            got.append(self._prog(items, elapsed=99)["label"])
        self.assertEqual(got, ["item0", "item1", "item2", "item0", "item1"])

    def test_nothing_moves_without_an_advance(self):
        items = _items(3)
        self._prog(items)
        for _ in range(12):
            self.assertEqual(self._prog(items)["label"], "item0")

    def test_a_reordered_play_set_does_not_move_the_feed(self):
        # THE FLICKER. The play set is rebuilt every tick - twelve times per dwell - and "The
        # action" re-sorts it by live excitement each time, so its order is different on nearly
        # every evaluation. Anything positional followed the sort instead of the dwell.
        items = _items(3)
        self.assertEqual(self._prog(items)["label"], "item0")
        for shuffled in ([items[2], items[0], items[1]],
                         [items[1], items[2], items[0]],
                         [items[2], items[1], items[0]]):
            self.assertEqual(self._prog(shuffled)["label"], "item0")

    def test_an_advance_follows_the_CURRENT_order(self):
        # Held by identity, but the step is taken in the list as it stands now - so a rundown
        # that legitimately reordered is honored at the moment the dwell fires.
        items = _items(3)
        self._prog(items)                                   # holding item0
        reordered = [items[0], items[2], items[1]]
        self.assertEqual(self._prog(reordered, elapsed=99)["label"], "item2")

    def test_a_vanished_item_falls_to_the_front(self):
        # Its subject died, or the operator deselected the rundown carrying it. Taking the old
        # POSITION in a re-sorted list is exactly the bug; the front is the honest answer.
        items = _items(3)
        self._prog(items, elapsed=99)                     # holding item1
        self.assertEqual(self._prog([items[0], items[2]])["label"], "item0")

    def test_an_empty_play_set_is_nothing_on_air(self):
        # Leaving the last shot frozen on air would be worse than an empty screen: it looks
        # live and is not.
        self.assertIsNone(self._prog([]))

    def test_an_empty_play_set_forgets_the_hold(self):
        items = _items(3)
        self._prog(items, elapsed=99)                     # holding item1
        self._prog([])
        self.assertEqual(self._prog(items)["label"], "item0")

    def test_no_screens_is_an_empty_plan_not_a_crash(self):
        self.assertEqual(dp.director_play_plan(_items(1)[0], []), [])

    # --- preview -------------------------------------------------------------------------

    def test_staged_wins(self):
        staged = dr.director_item_cam(999, "orbit", label="STAGED")
        dp.director_play_stage(staged)
        self.assertEqual(self._prev(_items(3))["label"], "STAGED")

    def test_nothing_staged_shows_what_the_next_advance_will_take(self):
        # A preview screen that goes blank whenever the operator is not staging reads as broken
        # rather than as idle - and "next up" is the other thing a director wants to see.
        items = _items(3)
        feeds = dp.director_play_feeds(items)
        self.assertEqual(feeds["program"]["label"], "item0")
        self.assertEqual(feeds["preview"]["label"], "item1")
        # And it is not a guess: advancing takes exactly what preview promised.
        self.assertEqual(self._prog(items, elapsed=99)["label"], "item1")

    def test_clearing_the_stage_falls_back(self):
        dp.director_play_stage(dr.director_item_cam(999, "orbit", label="STAGED"))
        dp.director_play_stage(clear=True)
        self.assertEqual(self._prev(_items(3))["label"], "item1")

    def test_nothing_at_all_is_nothing(self):
        self.assertIsNone(self._prev([]))

    def test_the_two_feeds_differ(self):
        feeds = dp.director_play_feeds(_items(3))
        self.assertNotEqual(feeds["program"]["label"], feeds["preview"]["label"])

    def test_a_single_item_is_both_feeds(self):
        # One item and nowhere to go. Preview showing the same thing is right; a blank preview
        # or a crash would not be.
        feeds = dp.director_play_feeds(_items(1))
        self.assertEqual(feeds["program"]["label"], "item0")
        self.assertEqual(feeds["preview"]["label"], "item0")


class ChangeTrackingTests(unittest.TestCase):
    def setUp(self):
        dp.director_play_reset()
        self.restore = _install({})

    def tearDown(self):
        self.restore()
        dp.director_play_reset()

    def test_the_first_plan_changes_everything(self):
        plan = dp.director_play_plan(_items(1)[0], [10, 11])
        self.assertTrue(all(p["changed"] for p in plan))

    def test_unchanged_screens_are_not_re_issued(self):
        item = _items(1)[0]
        dp.director_play_plan(item, [10, 11])
        plan = dp.director_play_plan(item, [10, 11])
        self.assertTrue(all(not p["changed"] for p in plan))

    def test_an_advance_changes_every_screen(self):
        items = _items(3)
        dp.director_play_plan(items[0], [10, 11])
        plan = dp.director_play_plan(items[1], [10, 11])
        self.assertTrue(all(p["changed"] for p in plan))

    def test_an_idle_screen_settles(self):
        # None is a real state, not an absence. A screen released to its holding page must not
        # read as changed on the next tick, or it would be released and rerouted twice a
        # second, forever.
        dp.director_play_plan(None, [10])
        plan = dp.director_play_plan(None, [10])
        self.assertFalse(plan[0]["changed"])

    def test_release_does_not_forget_what_a_screen_shows(self):
        # Same reason: popping `_LAST` here would make the very next tick read the screen as
        # changed, release it again and reroute it again, twice a second, forever.
        camera_mod = types.ModuleType("sbs_utils.procedural.gui.camera")
        camera_mod.camera_auto = lambda cids: None
        overlay_mod = types.ModuleType("sbs_utils.procedural.gui.overlay")
        overlay_mod.overlay_clear = lambda slot, to=None: None
        overlay_mod._KIND_DEFAULT_SLOT = {}
        overlay_mod.overlay_kind = lambda kind, to=None, slot=None, **f: None
        saved = {}
        for name, mod in (("sbs_utils.procedural.gui.camera", camera_mod),
                          ("sbs_utils.procedural.gui.overlay", overlay_mod)):
            saved[name] = sys.modules.get(name)
            sys.modules[name] = mod
        try:
            dp.director_play_plan(None, [10])
            dp.director_play_release(10)
            self.assertFalse(dp.director_play_plan(None, [10])[0]["changed"])
        finally:
            for name, mod in saved.items():
                if mod is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = mod

    def test_forgetting_is_over_both_feeds_at_once(self):
        program = _items(1)[0]
        preview = dr.director_item_cam(999, "orbit", label="PV")
        dp.director_play_plan(program, [10])
        dp.director_play_plan(preview, [20])
        dp.director_play_forget_absent([10, 20])
        # Neither pass may have forgotten the other's screen.
        self.assertFalse(dp.director_play_plan(program, [10])[0]["changed"])
        self.assertFalse(dp.director_play_plan(preview, [20])[0]["changed"])

    def test_a_screen_that_left_and_came_back_is_re_applied(self):
        # It may have been driven elsewhere while it was gone, so assuming it still shows what
        # we last sent would leave it stuck.
        item = _items(1)[0]
        dp.director_play_plan(item, [10, 11])
        dp.director_play_forget_absent([10])
        plan = dp.director_play_plan(item, [10, 11])
        self.assertFalse(plan[0]["changed"])
        self.assertTrue(plan[1]["changed"])

    def test_reset_forgets_everything(self):
        item = _items(1)[0]
        dp.director_play_plan(item, [10, 11])
        dp.director_play_reset()
        plan = dp.director_play_plan(item, [10, 11])
        self.assertTrue(all(p["changed"] for p in plan))


class AutoDirectorTests(unittest.TestCase):
    def tearDown(self):
        self.restore()
        dp.director_play_reset()

    def _setup(self, exciting):
        dp.director_play_reset()
        self.restore = _install(exciting)

    def test_auto_leads_with_the_most_exciting(self):
        self._setup({901: 5.0, 900: 1.0, 902: 0.0})
        order = dp.director_play_auto_order(_items(3))
        self.assertEqual(order[0]["label"], "item1")

    def test_auto_picks_the_program_item(self):
        self._setup({902: 5.0})
        item = dp.director_play_feeds(_items(3), auto=True)["program"]
        self.assertEqual(item["label"], "item2")

    def test_auto_still_honors_the_dwell(self):
        # "Switching too soon" is the complaint this guards. Auto decides WHICH item, the dwell
        # decides WHEN - so a fight that swings the excitement wildly cannot cut the feed twelve
        # times a dwell.
        self._setup({900: 9.0})
        self.assertEqual(dp.director_play_feeds(_items(3), auto=True)["program"]["label"],
                         "item0")
        self.restore()
        self.restore = _install({902: 99.0})
        for _ in range(12):
            self.assertEqual(dp.director_play_feeds(_items(3), auto=True)["program"]["label"],
                             "item0")
        self.assertEqual(
            dp.director_play_feeds(_items(3), elapsed=99, auto=True)["program"]["label"],
            "item2")

    def test_auto_steps_on_rather_than_sitting_forever(self):
        # The leader is already on air and nothing has changed. Staying put would make a
        # two-item action rundown a single static shot.
        self._setup({900: 9.0})
        dp.director_play_feeds(_items(3), auto=True)
        self.assertEqual(
            dp.director_play_feeds(_items(3), elapsed=99, auto=True)["program"]["label"],
            "item1")

    def test_auto_holds_through_noise(self):
        self._setup({900: 1.0, 901: 0.0})
        first = dp.director_play_auto_order(_items(2))
        self.assertEqual(first[0]["label"], "item0")
        # item1 edges ahead by less than the margin: the shot must not move.
        self.restore()
        self.restore = _install({900: 1.0, 901: 1.0 + dp.DIRECTOR_AUTO_MARGIN / 2})
        held = dp.director_play_auto_order(_items(2))
        self.assertEqual(held[0]["label"], "item0")

    def test_auto_cuts_when_something_really_happens(self):
        self._setup({900: 1.0, 901: 0.0})
        dp.director_play_auto_order(_items(2))
        self.restore()
        self.restore = _install({900: 1.0, 901: 9.0})
        moved = dp.director_play_auto_order(_items(2))
        self.assertEqual(moved[0]["label"], "item1")

    def test_a_quiet_moment_keeps_the_operator_order(self):
        # Everything reads 0.0 - a lull, or a headless run where nothing populates `exciting`
        # at all. The rundown order the operator built is the answer.
        self._setup({})
        order = dp.director_play_auto_order(_items(3))
        self.assertEqual([i["label"] for i in order], ["item0", "item1", "item2"])

    def test_auto_on_an_empty_set_is_empty(self):
        self._setup({})
        self.assertEqual(dp.director_play_auto_order([]), [])


class PunchTests(unittest.TestCase):
    """Send to Program overrides the rundown and HOLDS.

    Holding is the whole feature: on a six-second dwell an item that did not hold would be
    overwritten on the very next advance, and the button would read as doing nothing.
    """

    def setUp(self):
        dp.director_play_reset()
        self.restore = _install({})
        self.punch = dr.director_item_cam(999, "orbit", label="PUNCH")

    def tearDown(self):
        self.restore()
        dp.director_play_reset()

    def test_a_punch_goes_to_every_program_screen(self):
        item = dp.director_play_feeds(_items(3), punch=self.punch)["program"]
        plan = dp.director_play_plan(item, [10, 11, 12])
        self.assertEqual([p["item"]["label"] for p in plan], ["PUNCH"] * 3)

    def test_a_punch_ignores_the_advance(self):
        for _ in range(4):
            item = dp.director_play_feeds(_items(3), elapsed=99, punch=self.punch)["program"]
            self.assertEqual(item["label"], "PUNCH")

    def test_a_punch_ignores_the_auto_director(self):
        item = dp.director_play_feeds(_items(3), auto=True, punch=self.punch)["program"]
        self.assertEqual(item["label"], "PUNCH")

    def test_a_punch_works_with_no_rundown_at_all(self):
        # Send to Program from the editor, before anything has been sent. It must not need a
        # play set to have something to override.
        self.assertEqual(dp.director_play_feeds([], punch=self.punch)["program"]["label"],
                         "PUNCH")

    def test_a_take_freezes_the_clock(self):
        # Resume must hand the feed back exactly where it was. If the clock ran under the take,
        # the first tick after Resume would find the dwell long expired and cut immediately -
        # so Resume would look like Skip.
        dp.director_play_feeds(_items(3), elapsed=0.0)                   # acquire item0
        dp.director_play_feeds(_items(3), elapsed=99)                    # advance to item1
        for _ in range(5):
            out = dp.director_play_feeds(_items(3), elapsed=99, punch=self.punch)
            self.assertEqual(out["program"]["label"], "PUNCH")
            self.assertEqual(out["elapsed"], 99)
        self.assertEqual(dp.director_play_feeds(_items(3))["program"]["label"], "item1")


class BeatTests(unittest.TestCase):
    """Two beats of one shot, on air. The reported case, at the player level."""

    def setUp(self):
        dp.director_play_reset()
        self.restore = _install({})
        self.titled = dr.director_item_cam(
            901, "orbit", label="Station",
            overlays=[{"kind": "lower_third", "name": "Phoenix", "line": "starbase"}], hold=7)
        self.clean = dr.director_item_cam(901, "orbit", label="Station")

    def tearDown(self):
        self.restore()
        dp.director_play_reset()

    def test_the_feed_advances_from_one_beat_to_the_other(self):
        # Held by the SHOT key, `_index_of` would find the first of the two and advancing from
        # the titled beat would snap straight back to it - a rundown that never moved.
        items = [self.titled, self.clean]
        first = dp.director_play_feeds(items, elapsed=0.0, dwell=6)["program"]
        self.assertEqual(first["overlays"][0]["name"], "Phoenix")
        second = dp.director_play_feeds(items, elapsed=99, dwell=6)["program"]
        self.assertEqual(second["overlays"], [])

    def test_the_titled_beat_gets_its_own_hold(self):
        items = [self.titled, self.clean]
        dp.director_play_feeds(items, elapsed=0.0, dwell=3)
        # dwell 3, but this beat asked for 7.
        self.assertEqual(
            dp.director_play_feeds(items, elapsed=5, dwell=3)["program"]["overlays"][0]["name"],
            "Phoenix")
        self.assertEqual(dp.director_play_feeds(items, elapsed=7, dwell=3)["program"]["overlays"],
                         [])

    def test_the_cut_between_them_does_not_reroute(self):
        # Same subject, same mode: the camera keeps running and only the cards swap. A reroute
        # would rebuild the page and restart the orbit, which reads as a jump cut on a shot
        # that is meant to be continuous.
        dp.director_play_plan(self.titled, [10])
        plan = dp.director_play_plan(self.clean, [10])
        self.assertFalse(plan[0]["changed"])


class ClockTests(unittest.TestCase):
    """The dwell, and a per-item hold that overrides it.

    The clock lives in `director_play_feeds` because whether to advance depends on the HELD
    item's own hold - a caller that decided first would have to know what is held before asking
    what is held.
    """

    def setUp(self):
        dp.director_play_reset()
        self.restore = _install({})

    def tearDown(self):
        self.restore()
        dp.director_play_reset()

    def test_the_clock_runs_until_the_dwell(self):
        items = _items(3)
        dp.director_play_feeds(items, elapsed=0.0, dwell=6)          # acquire item0
        for elapsed in (0.5, 3.0, 5.5):
            out = dp.director_play_feeds(items, elapsed=elapsed, dwell=6)
            self.assertEqual(out["program"]["label"], "item0")
            self.assertEqual(out["elapsed"], elapsed)

    def test_acquiring_an_item_restarts_the_clock(self):
        # The held item died or left the play set, so the feed takes the front - and the
        # replacement gets a full dwell rather than inheriting the dead item's spent clock and
        # being cut a tick later.
        items = _items(3)
        out = dp.director_play_feeds(items, elapsed=99, dwell=6)
        self.assertEqual(out["program"]["label"], "item0")
        self.assertEqual(out["elapsed"], 0.0)

    def test_reaching_the_dwell_advances_and_resets_it(self):
        items = _items(3)
        dp.director_play_feeds(items, elapsed=0.5, dwell=6)
        out = dp.director_play_feeds(items, elapsed=6.0, dwell=6)
        self.assertEqual(out["program"]["label"], "item1")
        self.assertEqual(out["elapsed"], 0.0)

    def test_no_clock_at_all_is_a_pure_read(self):
        items = _items(3)
        dp.director_play_feeds(items, elapsed=0.0, dwell=6)          # acquire item0
        dp.director_play_feeds(items, elapsed=99, dwell=6)           # advance to item1
        for _ in range(5):
            self.assertEqual(dp.director_play_feeds(items)["program"]["label"], "item1")

    def test_an_items_own_hold_beats_the_dwell(self):
        # An establishing shot of a starbase wants ten seconds next to action beats that want
        # three, and the rundown is where that belongs.
        slow = dr.director_item_cam(901, "orbit", label="SLOW", hold=20)
        fast = dr.director_item_cam(902, "orbit", label="FAST")
        items = [slow, fast]
        self.assertEqual(dp.director_play_feeds(items, elapsed=8, dwell=6)["program"]["label"],
                         "SLOW")
        self.assertEqual(dp.director_play_feeds(items, elapsed=20, dwell=6)["program"]["label"],
                         "FAST")

    def test_a_short_hold_cuts_before_the_dwell(self):
        quick = dr.director_item_cam(901, "orbit", label="QUICK", hold=2)
        items = [quick, dr.director_item_cam(902, "orbit", label="NEXT")]
        self.assertEqual(dp.director_play_feeds(items, elapsed=1, dwell=30)["program"]["label"],
                         "QUICK")
        self.assertEqual(dp.director_play_feeds(items, elapsed=2, dwell=30)["program"]["label"],
                         "NEXT")

    def test_the_hold_that_counts_is_the_one_on_air(self):
        # Not the one being advanced TO. The item on screen is what the operator is watching
        # the clock against.
        slow = dr.director_item_cam(901, "orbit", label="SLOW", hold=20)
        quick = dr.director_item_cam(902, "orbit", label="QUICK", hold=2)
        items = [slow, quick]
        self.assertEqual(dp.director_play_feeds(items, elapsed=3, dwell=6)["program"]["label"],
                         "SLOW")

    def test_no_hold_means_the_dwell(self):
        self.assertEqual(dp.director_play_hold(dr.director_item_cam(901, "orbit"), 6), 6)
        self.assertEqual(dp.director_play_hold(None, 6), 6)

    def test_zero_is_no_opinion_not_an_instant_cut(self):
        # The control is a slider, and its bottom stop has to mean something. A half-second
        # shot would be unwatchable, so 0 reads as "use the dwell".
        item = dr.director_item_cam(901, "orbit", hold=0)
        self.assertIsNone(item["hold"])
        self.assertEqual(dp.director_play_hold(item, 6), 6)

    def test_a_junk_hold_falls_back_rather_than_raising(self):
        self.assertIsNone(dr.director_item_cam(901, "orbit", hold="soon")["hold"])
        self.assertEqual(dp.director_play_hold({"hold": "soon"}, 6), 6)

    def test_the_hold_is_not_part_of_an_items_identity(self):
        # Two rundowns naming the same shot with different holds are still one shot; the play
        # set de-duplicates them and the first one in wins.
        a = dr.director_item_cam(901, "orbit", hold=3)
        b = dr.director_item_cam(901, "orbit", hold=30)
        self.assertEqual(dr.director_item_key(a), dr.director_item_key(b))


class _OverlayHarness(unittest.TestCase):
    """A fake overlay module, so `show` and `clear` can be counted."""

    def setUp(self):
        dp.director_play_reset()
        self.shown = []
        self.cleared = []
        overlay_mod = types.ModuleType("sbs_utils.procedural.gui.overlay")
        overlay_mod._KIND_DEFAULT_SLOT = {"lower_third": "lower_third", "hero": "center_hero",
                                          "banner": "top_banner", "letterbox": "fullscreen"}
        overlay_mod.overlay_kind = lambda kind, to=None, slot=None, **f: self.shown.append((kind, slot, f))
        overlay_mod.overlay_clear = lambda slot, to=None: self.cleared.append(slot)
        self.saved_overlay = sys.modules.get("sbs_utils.procedural.gui.overlay")
        sys.modules["sbs_utils.procedural.gui.overlay"] = overlay_mod
        self.restore_query = _install({})

    def tearDown(self):
        self.restore_query()
        if self.saved_overlay is None:
            sys.modules.pop("sbs_utils.procedural.gui.overlay", None)
        else:
            sys.modules["sbs_utils.procedural.gui.overlay"] = self.saved_overlay
        dp.director_play_reset()

    def _item(self, *kinds, **fields):
        overlays = []
        for kind in kinds:
            entry = {"kind": kind}
            entry.update(fields)
            overlays.append(entry)
        return dr.director_item_cam(901, "orbit", overlays=overlays)


class OverlayTests(_OverlayHarness):
    def test_several_overlays_all_go_up(self):
        dp.director_play_overlays(10, self._item("lower_third", "banner"))
        self.assertEqual(sorted(k for k, _s, _f in self.shown), ["banner", "lower_third"])

    def test_the_previous_ones_are_cleared_first(self):
        dp.director_play_overlays(10, self._item("lower_third"))
        self.cleared[:] = []
        dp.director_play_overlays(10, self._item("hero"))
        self.assertEqual(self.cleared, ["lower_third"])

    def test_an_item_with_none_still_clears(self):
        # Advancing from an overlay-carrying shot to a bare one must take the furniture down.
        dp.director_play_overlays(10, self._item("lower_third"))
        self.cleared[:] = []
        dp.director_play_overlays(10, dr.director_item_cam(901, "orbit"))
        self.assertEqual(self.cleared, ["lower_third"])

    def test_templates_are_resolved_on_the_way_out(self):
        # One line before overlay_kind, because banner and lower_third are CYCLE kinds: their
        # text is word-wrapped and split into timed segments, so an unresolved token could be
        # split across two of them.
        dp.director_play_overlays(10, self._item("banner", text="<<name|nobody>>"))
        self.assertEqual(self.shown[0][2]["text"], "nobody")


class ScreenEnterTests(_OverlayHarness):
    def test_entering_a_screen_clears_whatever_it_carried(self):
        # THE INVARIANT. Six separate leaks were all instances of this: a transition with no
        # clear on it. Every reroute target calls it first.
        dp.director_play_overlays(10, self._item("lower_third"))
        self.cleared[:] = []
        dp.director_screen_enter(10)
        self.assertEqual(self.cleared, ["lower_third"])

    def test_entering_stops_a_running_camera(self):
        # cam item -> tactical item used to leave a camera stepping its legs at a 2D view.
        dp._SHOTS[10] = {"mode": "orbit", "subject": 901, "prom": None, "yaw": 0.0, "leg": 0}
        dp.director_screen_enter(10)
        self.assertNotIn(10, dp._SHOTS)

    def test_entering_a_clean_screen_is_harmless(self):
        dp.director_screen_enter(10)
        self.assertEqual(self.cleared, [])

    def test_it_only_touches_the_screen_it_was_given(self):
        dp.director_play_overlays(10, self._item("lower_third"))
        dp.director_play_overlays(11, self._item("hero"))
        self.cleared[:] = []
        dp.director_screen_enter(10)
        self.assertEqual(self.cleared, ["lower_third"])

    def test_reset_releases_before_it_forgets(self):
        # THE #1 LEAK, and it beat Stop. `_SLOTS` is the only record of which slots are up and
        # `overlay_clear` needs the slot name, so dropping the record with cards on screen
        # orphaned them permanently - Stop then found an empty `_SLOTS` and cleared nothing.
        dp.director_play_overlays(10, self._item("lower_third"))
        dp.director_play_overlays(11, self._item("hero"))
        self.cleared[:] = []
        dp.director_play_reset()
        self.assertEqual(sorted(self.cleared), ["center_hero", "lower_third"])


class FurnitureOnlyTests(_OverlayHarness):
    def test_furniture_only_changes_do_not_reroute(self):
        # Preview restages on every keystroke. A reroute per keystroke would rebuild the page
        # and restart the camera each time, which makes a preview screen unwatchable.
        dp.director_play_plan(self._item("banner", text="a"), [10])
        self.shown[:] = []
        plan = dp.director_play_plan(self._item("banner", text="ab"), [10])
        self.assertFalse(plan[0]["changed"])
        self.assertEqual([k for k, _s, _f in self.shown], ["banner"])
        self.assertEqual(self.shown[0][2]["text"], "ab")

    def test_identical_furniture_is_not_re_shown(self):
        dp.director_play_plan(self._item("banner", text="a"), [10])
        self.shown[:] = []
        dp.director_play_plan(self._item("banner", text="a"), [10])
        self.assertEqual(self.shown, [])

    def test_a_new_shot_still_reroutes(self):
        dp.director_play_plan(self._item("banner", text="a"), [10])
        plan = dp.director_play_plan(dr.director_item_cam(902, "orbit"), [10])
        self.assertTrue(plan[0]["changed"])


class StatusTests(unittest.TestCase):
    def test_it_says_why_nothing_happened(self):
        # Pressing Send with nothing declared is the commonest confusion, and the reason is
        # never visible on screen otherwise.
        self.assertIn("no program or preview", dp.director_play_status(None, 0, 0, False, False))
        self.assertIn("rundown", dp.director_play_status(None, 2, 0, False, False))

    def test_it_names_what_is_on_air(self):
        item = dr.director_item_con(901, "helm", "Helm - Artemis")
        line = dp.director_play_status(item, 2, 1, False, False)
        self.assertIn("ON AIR", line)
        self.assertIn("Helm - Artemis", line)
        self.assertIn("2 program", line)
        self.assertIn("1 preview", line)

    def test_a_hold_beats_the_auto_director_in_the_line(self):
        # Both can be true at once, and "held" is the one that explains why the feed is not
        # moving - which is what the operator is looking at the line to find out.
        item = dr.director_item_con(901, "helm", "Helm")
        self.assertIn("held", dp.director_play_status(item, 1, 0, True, True))
        self.assertIn("auto-director", dp.director_play_status(item, 1, 0, True, False))


if __name__ == "__main__":
    unittest.main()
