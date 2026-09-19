"""A station's AI wings: how many, launch, land and refit, bingo, and the per-wing menu.

The wings are NOT the hangar's craft - those are player ships a pilot climbs into, and an
NPC brain cannot fly a behav_playership. A wing is a count of AI fighters spawned as
behav_npcship on launch and removed again when they land.

Run from the LegendaryMissions folder with sbs_utils on the path:
    PYTHONPATH=../sbs_utils python -m unittest hangar.test_hangar_wing
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (import first to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs
from sbs_utils.agent import clear_shared
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.roles import has_role
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.procedural.sides import side_ensure, side_set_relations
from sbs_utils.procedural.space_objects import delete_object, set_pos
from sbs_utils.procedural import orders as O

from hangar import hangar_wing as W

SIZE = W.HANGAR_WING_DEFAULT_SIZE


class _Label:
    name = "wing_order"

    def __init__(self, **meta):
        self.meta = meta

    def get_inventory_value(self, key, default=None):
        return self.meta.get(key, default)


READY = _Label(wing_state="ready")
OUT = _Label(wing_state="out")


class WingBase(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        DeleteQueue.clear()
        clear_shared()
        SpaceObject.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent())
        side_ensure("tsn")
        self.hero = to_id(player_spawn(0, 0, 0, "Hero", "tsn", "tsn_light_cruiser"))
        # A command starbase has two wings; the others one.
        self.base = to_id(npc_spawn(5000, 0, 0, "DS 1", "tsn,station", "starbase_command", "behav_station"))
        self.depot = to_id(npc_spawn(9000, 0, 0, "Depot", "tsn,station", "starbase_industry", "behav_station"))
        self.cruiser = to_id(npc_spawn(1000, 0, 0, "Valiant", "tsn", "tsn_light_cruiser", "behav_npcship"))
        O.orders_caps_provider(W.hangar_wing_caps)
        # Sim time, under the test's control - refit is timed.
        self.now = 100.0
        self._real_now = W._hangar_wing_now
        W._hangar_wing_now = lambda: self.now

    def tearDown(self):
        W._hangar_wing_now = self._real_now
        FrameContext.context = None


class TestHowMany(WingBase):
    """Bays come from the hull's interior grid (fighter + shuttle slots), else baycount."""

    def spawn(self, hull, side="tsn"):
        return to_id(npc_spawn(0, 0, 7000, "Base", f"{side},station", hull, "behav_station"))

    def test_A_COMMAND_STARBASE_HAS_TWO_WINGS_FROM_ITS_GRID(self):
        self.assertEqual(8, W.hangar_wing_bays(self.base))
        self.assertEqual(["red", "gold"], W.hangar_wing_names(self.base))
        self.assertEqual(2 * SIZE, W.hangar_wing_ready(self.base))
        self.assertEqual(SIZE, W.hangar_wing_ready(self.base, "gold"))

    def test_THE_STOCK_LOADOUTS(self):
        """The table in the plan: bays -> wings of up to 4, the last takes the rest."""
        expect = {"starbase_command": [4, 4], "starbase_industry": [4, 4],
                  "starbase_science": [4], "starbase_kralien": [4],
                  "starbase_arvonian": [4, 4, 4, 2], "starbase_civil": [],
                  "starbase_skaraan": [], "starbase_torgoth": []}
        for hull, sizes in expect.items():
            sid = self.spawn(hull)
            got = [W.hangar_wing_size(sid, w) for w in W.hangar_wing_names(sid)]
            self.assertEqual(sizes, got, hull)

    def test_a_ship_without_bays_has_none(self):
        self.assertEqual([], W.hangar_wing_names(self.cruiser))

    def test_a_carrier_uses_its_baycount(self):
        carrier = to_id(npc_spawn(0, 0, 3000, "Carrier", "tsn", "arvonian_light_carrier", "behav_npcship"))
        self.assertEqual(8, W.hangar_wing_bays(carrier))
        self.assertEqual(["red", "gold"], W.hangar_wing_names(carrier))

    def test_a_mission_sets_wings_and_size(self):
        W.hangar_wing_set_size(self.depot, 2, count=3)
        self.assertEqual(["red", "gold", "blue"], W.hangar_wing_names(self.depot))
        self.assertEqual(6, W.hangar_wing_ready(self.depot))
        W.hangar_wing_set_size(self.depot, 0)
        self.assertEqual([], W.hangar_wing_names(self.depot))

    def test_FIGHTERS_BY_ORIGIN(self):
        self.assertEqual("tsn_fighter", W.hangar_wing_hull(self.base))                # Terran
        self.assertEqual("arvonian_fighter", W.hangar_wing_hull(self.spawn("starbase_arvonian")))
        self.assertEqual(W.HANGAR_WING_FALLBACK_HULL, W.hangar_wing_hull(self.spawn("starbase_kralien")))

    def test_display_names(self):
        self.assertEqual("Red wing", W.hangar_wing_display("red"))


class TestLaunchAndLand(WingBase):

    def test_LAUNCHING_ONE_WING_LEAVES_THE_OTHER_IN_THE_BAY(self):
        ids = W.hangar_wing_launch(self.base, wing="red")
        self.assertEqual(SIZE, len(ids))
        self.assertEqual(0, W.hangar_wing_ready(self.base, "red"))
        self.assertEqual(SIZE, W.hangar_wing_ready(self.base, "gold"))
        self.assertEqual(sorted(ids), W.hangar_wing_out(self.base, "red"))
        self.assertEqual([], W.hangar_wing_out(self.base, "gold"))
        for fid in ids:
            self.assertTrue(has_role(fid, "__npc__"))            # an AI can fly it
            self.assertEqual("behav_npcship", to_object(fid).behave_id)
            self.assertEqual(self.base, W.hangar_wing_home(fid))
            self.assertEqual("red", W.hangar_wing_of(fid))

    def test_launch_every_wing(self):
        self.assertEqual(2 * SIZE, len(W.hangar_wing_launch(self.base)))
        self.assertEqual(0, W.hangar_wing_ready(self.base))

    def test_launch_a_few(self):
        self.assertEqual(2, len(W.hangar_wing_launch(self.base, 2, "gold")))
        self.assertEqual(SIZE - 2, W.hangar_wing_ready(self.base, "gold"))

    def test_an_empty_bay_launches_nothing(self):
        W.hangar_wing_launch(self.base, wing="red")
        self.assertEqual([], W.hangar_wing_launch(self.base, wing="red"))

    def test_LANDING_REFITS_INTO_ITS_OWN_WING(self):
        fid = W.hangar_wing_launch(self.base, 1, "gold")[0]
        set_pos(fid, 20000, 0, 0)
        self.assertFalse(W.hangar_wing_land(fid))                   # too far
        set_pos(fid, 5100, 0, 0)
        self.assertTrue(W.hangar_wing_land(fid))
        self.assertEqual(1, W.hangar_wing_refitting(self.base, "gold"))
        self.assertEqual(0, W.hangar_wing_refitting(self.base, "red"))
        self.assertEqual(SIZE - 1, W.hangar_wing_ready(self.base, "gold"))
        self.assertEqual(W.HANGAR_WING_DEFAULT_REFIT, W.hangar_wing_refit_remaining(self.base, "gold"))
        self.now += W.HANGAR_WING_DEFAULT_REFIT
        self.assertEqual(SIZE, W.hangar_wing_ready(self.base, "gold"))

    def test_a_lost_fighter_never_comes_back(self):
        fid = W.hangar_wing_launch(self.base, 1, "red")[0]
        delete_object(fid)
        DeleteQueue.clear()
        self.assertEqual(SIZE - 1, W.hangar_wing_ready(self.base, "red"))

    def test_A_LAUNCH_SETS_BINGO_FUEL(self):
        from sbs_utils.procedural.timers import is_timer_set
        fid = W.hangar_wing_launch(self.base, 1, "red")[0]
        self.assertTrue(is_timer_set(fid, W.HANGAR_WING_BINGO))
        self.assertFalse(W.hangar_wing_is_bingo(fid))

    def test_REASSIGN_MOVES_ONE_WING_ONLY_AND_NOT_ITS_BINGO(self):
        red = W.hangar_wing_launch(self.base, 2, "red")
        gold = W.hangar_wing_launch(self.base, 1, "gold")
        W.hangar_wing_bingo_mark(red[0])
        again = W.hangar_wing_reassign(self.base, "red")
        self.assertIn(red[1], again)
        self.assertNotIn(red[0], again)                             # bingo, heading home
        self.assertNotIn(gold[0], again)                            # another wing
        self.assertEqual(SIZE - 1, len(again))                      # 1 still out + the rest of the bay
        self.assertEqual(0, W.hangar_wing_ready(self.base, "red"))
        self.assertEqual(SIZE - 1, W.hangar_wing_ready(self.base, "gold"))


class TestTheMenu(WingBase):

    def inst(self, label):
        return W.hangar_wing_instances(self.base, label)

    def test_BOTH_WINGS_OFFER_LAUNCH(self):
        self.assertEqual([("red", "Red wing (4/4)"), ("gold", "Gold wing (4/4)")], self.inst(READY))
        self.assertEqual([], self.inst(OUT))
        self.assertEqual({"launch", "wing_delegable"}, O.orders_caps(self.base))

    def test_A_WING_OUT_OFFERS_REASSIGN_THE_OTHER_STILL_LAUNCH(self):
        W.hangar_wing_launch(self.base, 1, "red")
        self.assertEqual([("gold", "Gold wing (4/4)")], self.inst(READY))
        self.assertEqual([("red", "Red wing (1 out)")], self.inst(OUT))
        self.assertEqual({"launch", "wing_out", "wing_delegable"}, O.orders_caps(self.base))

    def test_every_wing_out(self):
        W.hangar_wing_launch(self.base)
        self.assertEqual([], self.inst(READY))
        self.assertEqual({"wing_out", "wing_delegable"}, O.orders_caps(self.base))

    def test_a_wing_all_in_refit_offers_nothing(self):
        W.hangar_wing_set_size(self.depot, 1, count=1)
        fid = W.hangar_wing_launch(self.depot, wing="red")[0]
        set_pos(fid, 9100, 0, 0)
        self.assertTrue(W.hangar_wing_land(fid))
        self.assertEqual({"wing_delegable"}, O.orders_caps(self.depot))
        self.now += W.HANGAR_WING_DEFAULT_REFIT
        self.assertEqual({"launch", "wing_delegable"}, O.orders_caps(self.depot))

    def test_ONE_MENU_ENTRY_PER_WING(self):
        """Through the library's orders_items, the way the comms popup builds it."""
        side_set_relations(side_ensure("tsn"), side_ensure("raider"), mock_sbs.DIPLOMACY.HOSTILE)
        foe = to_id(npc_spawn(5000, 0, 4000, "Raider", "raider", "tsn_light_cruiser", "behav_npcship"))
        launch = _Label(type="objective/orders/launch/attack", display_name="Launch @",
                        valid_for="hostile", requires="launch",
                        instances=W.hangar_wing_instances, wing_state="ready")
        texts = [t for _, _, t in O.orders_items(self.hero, self.base, foe, labels=[launch])]
        self.assertEqual(["Launch Red wing (4/4)", "Launch Gold wing (4/4)"], texts)
        keys = [k for _, k, _ in O.orders_items(self.hero, self.base, foe, labels=[launch])]
        self.assertEqual(["red", "gold"], keys)

    def test_no_wing_no_orders(self):
        W.hangar_wing_set_size(self.depot, 0)
        self.assertEqual(set(), O.orders_caps(self.depot))

class TestAutonomy(WingBase):
    """Who runs a station's wings: its crew, or itself."""

    def enemy_base(self):
        side_set_relations(side_ensure("tsn"), side_ensure("kralien"), mock_sbs.DIPLOMACY.HOSTILE)
        return to_id(npc_spawn(0, 0, 20000, "Enemy Base", "kralien,station", "starbase_command", "behav_station"))

    def test_A_STATION_ON_A_CREWED_SIDE_WAITS_FOR_ORDERS(self):
        self.assertFalse(W.hangar_wing_is_autonomous(self.base))

    def test_A_STATION_WITH_NO_CREW_RUNS_ITSELF(self):
        self.assertTrue(W.hangar_wing_is_autonomous(self.enemy_base()))

    def test_an_allied_crew_counts(self):
        side_set_relations(side_ensure("tsn"), side_ensure("usfp"), mock_sbs.DIPLOMACY.ALLIED)
        ally_base = to_id(npc_spawn(0, 0, 20000, "Ally", "usfp,station", "starbase_command", "behav_station"))
        self.assertFalse(W.hangar_wing_is_autonomous(ally_base))

    def test_no_wings_never_autonomous(self):
        civ = to_id(npc_spawn(0, 0, 20000, "Civ", "kralien,station", "starbase_civil", "behav_station"))
        self.assertFalse(W.hangar_wing_is_autonomous(civ))

    def test_the_marks(self):
        from sbs_utils.procedural.roles import add_role
        add_role(self.base, W.HANGAR_WING_AUTONOMOUS_ROLE)
        self.assertTrue(W.hangar_wing_is_autonomous(self.base))
        enemy = self.enemy_base()
        add_role(enemy, W.HANGAR_WING_MANUAL_ROLE)
        self.assertFalse(W.hangar_wing_is_autonomous(enemy))

    def test_A_CREW_DELEGATES_AND_TAKES_IT_BACK(self):
        self.assertEqual({"launch", "wing_delegable"}, O.orders_caps(self.base))
        W.hangar_wing_delegate(self.base, True)
        self.assertTrue(W.hangar_wing_is_autonomous(self.base))
        self.assertEqual({"launch", "wing_delegated"}, O.orders_caps(self.base))
        W.hangar_wing_delegate(self.base, False)
        self.assertFalse(W.hangar_wing_is_autonomous(self.base))


class TestThink(WingBase):
    """The autonomous doctrine: defend, keep a reserve, cover allies, recall when clear."""

    def setUp(self):
        super().setUp()
        side_set_relations(side_ensure("tsn"), side_ensure("kralien"), mock_sbs.DIPLOMACY.HOSTILE)
        # An enemy base with no crew on its side, far from everything else.
        self.host = to_id(npc_spawn(0, 0, 50000, "Kralien Command", "kralien,station", "starbase_command", "behav_station"))

    def think(self):
        acts = W.hangar_wing_think(self.host)
        self.now += 60                       # always past the reaction delay for the next call
        return acts

    def intruder(self, z=47000, name="Intruder"):
        return to_id(npc_spawn(0, 0, z, name, "tsn", "tsn_light_cruiser", "behav_npcship"))

    def test_NOTHING_IN_RANGE_NOTHING_HAPPENS(self):
        self.assertEqual([], self.think())

    def test_A_HOSTILE_IN_RANGE_LAUNCHES_ONE_WING_AND_KEEPS_THE_RESERVE(self):
        a = self.intruder()
        self.assertEqual([("attack", "red", a)], self.think())

    def test_the_reaction_delay_paces_it(self):
        self.intruder()
        self.assertTrue(W.hangar_wing_think(self.host))
        self.assertEqual([], W.hangar_wing_think(self.host))       # same instant

    def test_A_HIT_ON_THE_STATION_SENDS_THE_RESERVE(self):
        a = self.intruder()
        W.hangar_wing_note_attacked(self.host, a)
        self.assertEqual([("attack", "red", a), ("attack", "gold", a)], self.think())

    def test_A_WING_WHOSE_TARGET_IS_GONE_IS_REASSIGNED(self):
        a = self.intruder()
        self.think()
        W.hangar_wing_launch(self.host, None, "red")               # the brain carries it out
        b = self.intruder(46000, "B")
        delete_object(a)                     # pending delete: object_exists is already False
        self.assertEqual([("reassign", "red", b)], self.think())

    def test_AN_ALLY_UNDER_THREAT_IS_COVERED_FIRST(self):
        friend = to_id(npc_spawn(0, 0, 45000, "Kralien Freighter", "kralien", "transport_ship", "behav_npcship"))
        self.intruder(44000, "Raider")
        self.assertEqual([("protect", "red", friend)], self.think())

    def test_ALL_CLEAR_FOR_A_WHILE_RECALLS_THE_WING(self):
        a = self.intruder()
        self.think()
        W.hangar_wing_launch(self.host, None, "red")
        delete_object(a)                     # pending delete: object_exists is already False
        self.assertEqual([], self.think())                         # clear starts counting
        self.assertEqual([("recall", "red", None)], self.think())  # 60s later: clear long enough

    def test_DIFFICULTY_WIDENS_AND_QUICKENS(self):
        from sbs_utils.procedural.execution import set_shared_variable
        set_shared_variable("DIFFICULTY", 1)
        r1, t1 = W.hangar_wing_radius(), W.hangar_wing_reaction()
        set_shared_variable("DIFFICULTY", 11)
        r11, t11 = W.hangar_wing_radius(), W.hangar_wing_reaction()
        self.assertGreater(r11, r1)
        self.assertLess(t11, t1)

    def test_TURRET_MOUNTS_FOLLOW_THE_THREAT(self):
        from sbs_utils.procedural.mount import mount_spawn
        from sbs_utils.procedural import turret as tr
        m = to_id(mount_spawn(self.host, "starbase_command", name="Mount", side="kralien"))
        tr.turret_make(m, range=1000)
        self.think()
        self.assertEqual("hold", O.orders_stance(m))
        self.intruder()
        self.think()
        self.assertEqual("free", O.orders_stance(m))

class TestLosses(WingBase):
    """Losses are permanent - and the crew can see them, in the menu and on a scan."""

    def test_A_DESTROYED_FIGHTER_IS_LOST_FOR_GOOD(self):
        ids = W.hangar_wing_launch(self.base, 2, "red")
        delete_object(ids[0])                        # pending delete: object_exists is False
        self.assertEqual(1, W.hangar_wing_lost(self.base, "red"))
        self.assertEqual(0, W.hangar_wing_lost(self.base, "gold"))
        self.now += 10 * W.HANGAR_WING_DEFAULT_REFIT
        self.assertEqual(1, W.hangar_wing_lost(self.base, "red"))      # never rebuilt

    def test_a_landed_fighter_is_not_lost(self):
        fid = W.hangar_wing_launch(self.base, 1, "red")[0]
        set_pos(fid, 5100, 0, 0)
        self.assertTrue(W.hangar_wing_land(fid))
        self.assertEqual(0, W.hangar_wing_lost(self.base, "red"))

    def test_THE_MENU_SHOWS_WHAT_IS_LEFT(self):
        ids = W.hangar_wing_launch(self.base, 1, "red")
        self.assertEqual([("red", "Red wing (1 out)")], W.hangar_wing_instances(self.base, OUT))
        self.assertEqual([("gold", "Gold wing (4/4)")], W.hangar_wing_instances(self.base, READY))
        delete_object(ids[0])
        self.assertEqual([("red", "Red wing (3/4)"), ("gold", "Gold wing (4/4)")],
                         W.hangar_wing_instances(self.base, READY))

    def test_A_WING_WITH_NOTHING_LEFT_OFFERS_NOTHING(self):
        for fid in W.hangar_wing_launch(self.base, wing="red"):
            delete_object(fid)
        self.assertEqual(SIZE, W.hangar_wing_lost(self.base, "red"))
        self.assertEqual([("gold", "Gold wing (4/4)")], W.hangar_wing_instances(self.base, READY))
        self.assertEqual([], W.hangar_wing_instances(self.base, OUT))

    def test_THE_SCAN_TEXT(self):
        for fid in W.hangar_wing_launch(self.base, wing="red"):
            delete_object(fid)
        W.hangar_wing_launch(self.base, 1, "gold")
        text = W.hangar_wing_scan_text(self.base)
        self.assertEqual(["Red wing: lost - all 4 fighters destroyed.",
                          "Gold wing: 3 ready, 1 out, 0 refitting, 0 lost."], text.splitlines())
        self.assertNotIn("{", text)
        self.assertEqual("", W.hangar_wing_scan_text(self.cruiser))

class TestEnemyScanIsAnEstimate(WingBase):
    """An enemy base's hangar reads as strength and state, never exact refit counts."""

    def test_A_FULL_WING_IN_THE_BAY(self):
        self.assertEqual(["Red wing: full strength, in the bay.", "Gold wing: full strength, in the bay."],
                         W.hangar_wing_scan_text(self.base, exact=False).splitlines())

    def test_LOSSES_AND_STATE(self):
        red = W.hangar_wing_launch(self.base, 2, "red")
        delete_object(red[0])                       # 1 of 4 lost, 1 out, 2 ready
        for fid in W.hangar_wing_launch(self.base, wing="gold"):
            delete_object(fid)                      # all of Gold lost
        self.assertEqual(["Red wing: under strength, partly airborne.", "Gold wing: destroyed."],
                         W.hangar_wing_scan_text(self.base, exact=False).splitlines())

    def test_rearming_and_badly_depleted(self):
        ids = W.hangar_wing_launch(self.base, wing="red")
        delete_object(ids[0])
        delete_object(ids[1])                       # half lost
        set_pos(ids[2], 5100, 0, 0)
        self.assertTrue(W.hangar_wing_land(ids[2]))
        set_pos(ids[3], 5100, 0, 0)
        self.assertTrue(W.hangar_wing_land(ids[3]))  # both survivors refitting, none ready
        self.assertEqual("Red wing: badly depleted, rearming.",
                         W.hangar_wing_scan_text(self.base, exact=False).splitlines()[0])

    def test_no_numbers_leak(self):
        W.hangar_wing_launch(self.base, 1, "red")
        text = W.hangar_wing_scan_text(self.base, exact=False)
        self.assertFalse(any(ch.isdigit() for ch in text), text)


if __name__ == "__main__":
    unittest.main()
