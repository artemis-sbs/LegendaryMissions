"""A surrendered ship can be boarded, with nothing written per mission.

`deck_wiring.mast` is routes only, so this compiles the REAL file through MAST's own
`import`, and drives it the way the engine does:

  * the comms menu of a SURRENDERED pirate brigantine - read from the buttons the engine
    would be sent - offers "Send a boarding party" when her hull has a plan (the shipped
    `races/pirate_brigantine.grid`) and the `station` tile art is installed, and offers
    NOTHING new when either is false, or she has not surrendered;
  * pressing it opens a party onto her own deck, and she is held where she is;
  * `boarding_deck_take`, `boarding_deck_scuttle` and `boarding_deck_leave` - the signals
    a scene sends with `; signal` - bring the party home and take her, destroy her, or
    leave her as she was;
  * with two consoles connected each of those still happens ONCE;
  * the real `take_surrendered_home` (sliced out of `comms/enemy_surrender.mast` and
    scheduled by that file's own first line) flies a ship nobody boards home and deletes
    her EXACTLY as before, and leaves one with a party aboard alone.

Harness rules, each of which fails silently (see `boarding/test_eva_wiring`): compile
through `import` with `story.basedir` set, park LAST, and push a SERVER page - the three
endings are `//shared/signal`, which only client 0 runs.

    cd ../sbs_utils && MAST_LEAVE_LOGS=1 PYTHONPATH=.;../LegendaryMissions \\
        python -m unittest boarding.test_deck_wiring

(Run from OUTSIDE this folder: `DEBUG()` opens `debug.log` with mode "w" in the current
folder, and this repo tracks one.)
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import re
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

BOARDING = os.path.dirname(os.path.abspath(__file__))
LM = os.path.dirname(BOARDING)

from sbs_utils.agent import Agent
from sbs_utils.consoledispatcher import ConsoleDispatcher
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.gui import Gui
from sbs_utils.handlerhooks import reset_mission_state
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers the route nodes)
import sbs_utils.mast_sbs.mast_sbs_procedural  # noqa: F401  (what makes boarding_deck_* MAST globals)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural import boarding as B
from sbs_utils.procedural import boarding_combat as K
from sbs_utils.procedural import boarding_deckplan as D
from sbs_utils.procedural import boarding_props as P
from sbs_utils.procedural import crew
from sbs_utils.procedural import tilemap as T
from sbs_utils.procedural import tilemap_art as TA
from sbs_utils.procedural.grid import grid_merge_ascii, grid_get_grid_data
from sbs_utils.procedural.internal_damage import grid_interior_reset
from sbs_utils.procedural.inventory import set_inventory_value
from sbs_utils.procedural.links import link
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.roles import has_role, add_role
from sbs_utils.procedural.routes import follow_route_select_comms
from sbs_utils.procedural.science import science_set_scan_data
from sbs_utils.procedural.sides import side_ensure, side_surrender
from sbs_utils.procedural.signal import signal_emit, signal_observe, signal_unobserve
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.tickdispatcher import TickDispatcher

HELM = 0x8000000000000001
COMMS = 0x8000000000000002

BUTTON = "Send a boarding party"


def _take_surrendered_home():
    """The real label, cut out of the real file - up to the end of it."""
    with open(os.path.join(LM, "comms", "enemy_surrender.mast"), encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^=+ *take_surrendered_home *=+ *\n.*", text, re.S | re.M)
    assert m, "comms/enemy_surrender.mast no longer has a take_surrendered_home label"
    first = next((line for line in text.split("\n")
                  if "task_schedule(take_surrendered_home)" in line), None)
    assert first and not first.startswith((" ", "#")), \
        "comms/enemy_surrender.mast no longer starts its homing task at top level"
    return first, m.group(0)


_SCHEDULE_LINE, _HOME_LABEL = _take_surrendered_home()

# The file under test; then the one line `comms/enemy_surrender.mast` starts its homing
# task with; the park; and that task's own label, which MAST only falls into from its
# own file when it comes after the park.
HARNESS_STORY = "\n".join([
    "import deck_wiring.mast",
    _SCHEDULE_LINE,
    "gui_text('$text:harness;')",
    "await gui()",
    "",
    _HOME_LABEL,
    "",
])


class DeckPage(StoryPage):
    story = None


class _Base(unittest.TestCase):
    hull = "pirate_brigantine"
    surrendered = True
    art = True
    consoles = (HELM,)

    def setUp(self):
        reset_mission_state()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        DeleteQueue.clear()
        TickDispatcher.clear()
        crew.crew_clear()
        grid_interior_reset()
        T.tilemap_clear_tilesets()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)

        # THE SHIPPED PLAN, merged the way `races/__init__.mast` merges it.
        with open(os.path.join(LM, "races", "pirate_brigantine.grid"), encoding="utf-8") as f:
            grid_merge_ascii(f.read(), "races")

        # Is the `station` art installed? The answer is the library's own question
        # (`tilemap_art_find`), made yes or no here on purpose.
        self._orig_find = TA.tilemap_art_find
        TA.tilemap_art_find = lambda name: ("media/tileart/" + name) if self.art else None
        # ...and nothing here draws, so nothing is read from that folder.
        self._orig_art = D._deck_art
        D._deck_art = lambda tileset: bool(self.art)

        self.buttons = []
        self._orig_btn = mock_sbs.send_comms_button_info
        self._orig_sel = mock_sbs.send_comms_selection_info
        mock_sbs.send_comms_button_info = \
            lambda ship, color, text, tag: self.buttons.append((text, tag))
        mock_sbs.send_comms_selection_info = \
            lambda ship, face, color, title: self.buttons.clear()

        story = MastStory()
        story.basedir = BOARDING
        errors = story.compile(HARNESS_STORY, "deckwiring", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        DeckPage.story = story
        FrameContext.mast = story

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append
        self.seen = []
        signal_observe(self._watch)

        side_ensure("tsn")
        side_ensure("pirate")
        self.ship = to_object(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        self.prize = to_object(npc_spawn(3000, 0, 0, "Black Gull", "pirate", self.hull,
                                         "behav_npcship"))
        # Spawned well away from where she lies, so "flown home" is a thing to see.
        self.prize.spawn_pos = mock_sbs.vec3(20000.0, 0.0, 0.0)
        if self.surrendered:
            side_surrender(self.prize)
        science_set_scan_data(self.ship, self.prize, "identified")

        self.server = DeckPage()
        Gui.push(0, self.server)
        self.pages = []
        for cid in self.consoles:
            mock_sbs.assign_client_to_ship(cid, self.ship.id)
            page = DeckPage()
            Gui.push(cid, page)
            self.pages.append((cid, page))
            set_inventory_value(cid, "CONSOLE_TYPE", "helm" if cid == HELM else "comms")
            link(self.ship.id, "consoles", cid)
            crew.crew_assign(cid, self.ship.id, "helm" if cid == HELM else "comms")
        self.present()

    def tearDown(self):
        signal_unobserve(self._watch)
        mock_sbs.send_comms_button_info = self._orig_btn
        mock_sbs.send_comms_selection_info = self._orig_sel
        MastScheduler.on_runtime_error = self._orig_rte
        TA.tilemap_art_find = self._orig_find
        D._deck_art = self._orig_art
        Gui.clients = {}
        Gui.widget_list_sent = {}
        DeckPage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        TickDispatcher.clear()
        crew.crew_clear()
        reset_mission_state()
        grid_interior_reset()
        T.tilemap_clear_tilesets()
        FrameContext.context = None

    # --- driving it ------------------------------------------------------------------
    def _watch(self, name, data=None):
        self.seen.append(name)

    def present(self, n=2):
        """One second each: both pages painted, then the tick the engine runs after."""
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                           FakeEvent(0, "gui_present"))
            self.server.gui_state = "repaint"
            self.server.present(FakeEvent(0, "gui_present"))
            for cid, page in self.pages:
                page.gui_state = "repaint"
                page.present(FakeEvent(cid, "gui_present"))
            TickDispatcher.dispatch_tick()
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def select(self, target=None, cid=HELM):
        target = self.prize if target is None else target
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(cid, "select_space_object"))
        follow_route_select_comms(self.ship.id, to_id(target))
        self.selected = to_id(target)
        self.present()

    def texts(self):
        return [t for t, _g in self.buttons]

    def press(self, text, cid=HELM):
        tags = [g for t, g in self.buttons if t == text]
        self.assertTrue(tags, f"no comms button {text!r}: {self.texts()}")
        ev = FakeEvent(client_id=cid, tag="press_comms_button", sub_tag=tags[0],
                       origin_id=self.ship.id, selected_id=self.selected)
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, ev)
        ConsoleDispatcher.dispatch_message(ev, "comms_target_UID")
        self.present()

    def board(self):
        self.select()
        self.press(BUTTON)
        self.assertIsNotNone(B.boarding_visiting(), "the button opened no party")

    def emit(self, name):
        """What `- [Take her]() ; signal boarding_deck_take` does: a bare emit."""
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        signal_emit(name)
        self.present()

    def home(self):
        self.assertIsNone(B.boarding_visiting())
        self.assertIsNone(B.boarding_invitation())
        self.assertIsNone(T.tilemap_area("deck"))
        self.assertIsNone(D.boarding_deck_target())
        self.assertEqual(self.seen.count("boarding_visit_ended"), 1)


# --- when the button shows ---------------------------------------------------------------

class TheButton(_Base):
    def test_the_file_says_it_is_loaded(self):
        self.assertIs(Agent.SHARED.get_inventory_value("BOARDING_DECK_WIRING"), True)

    def test_the_endings_are_server_only(self):
        with open(os.path.join(BOARDING, "deck_wiring.mast"), encoding="utf-8") as f:
            routes = [line for line in f.read().split("\n") if line.startswith("//")]
        self.assertEqual(len(routes), 5, routes)
        self.assertEqual(sorted(r.split()[0] for r in routes),
                         ["//comms", "//enable/comms",
                          "//shared/signal/boarding_deck_leave",
                          "//shared/signal/boarding_deck_scuttle",
                          "//shared/signal/boarding_deck_take"])

    def test_a_surrendered_ship_with_a_plan_and_the_art_offers_it(self):
        self.select()
        self.assertEqual(self.texts().count(BUTTON), 1, self.texts())

    def test_it_is_her_real_shipped_plan(self):
        self.assertTrue(D.boarding_deck_has_plan(self.prize))
        self.assertTrue(D.boarding_deck_ready(self.prize))

    def test_nothing_is_built_by_looking(self):
        self.select()
        self.assertIsNone(T.tilemap_area("deck"))
        self.assertIsNone(B.boarding_invitation())
        self.assertFalse(has_role(self.prize, "boarding_target"))


class NotSurrendered(_Base):
    surrendered = False

    def test_no_button(self):
        self.select()
        self.assertNotIn(BUTTON, self.texts())


class NoArt(_Base):
    art = False

    def test_no_button_and_nothing_else(self):
        self.assertFalse(D.boarding_deck_ready(self.prize))
        self.select()
        self.assertNotIn(BUTTON, self.texts())
        self.assertIsNone(T.tilemap_area("deck"))


class NoPlan(_Base):
    """The engine's own grid data lists this hull with no rooms at all - which is what
    LegendaryMissions itself has for a pirate when Pirate is not a playable race."""
    hull = "pirate_longbow"

    def test_no_button_and_nothing_else(self):
        self.assertEqual(grid_get_grid_data().get("pirate_longbow", {}).get("grid_objects"), [])
        self.assertFalse(D.boarding_deck_has_plan(self.prize))
        self.select()
        self.assertNotIn(BUTTON, self.texts())
        self.assertIsNone(T.tilemap_area("deck"))


class NotAPlayerShip(_Base):
    def test_an_admirals_camera_is_not_offered_it(self):
        from sbs_utils.procedural.roles import remove_role
        remove_role(self.ship, "__player__")
        add_role(self.ship, "admiral")
        self.select()
        self.assertNotIn(BUTTON, self.texts())


# --- pressing it -------------------------------------------------------------------------

class Pressed(_Base):
    def test_it_opens_a_party_onto_her_deck(self):
        self.board()
        visit = B.boarding_visiting()
        self.assertTrue(visit.get("tile"))
        self.assertEqual(visit.get("area"), "deck")
        self.assertEqual(visit.get("ship"), self.ship.id)
        self.assertEqual(B.boarding_invite_title(), "Black Gull")
        self.assertEqual(D.boarding_deck_target(), self.prize.id)
        self.assertTrue(has_role(self.prize, "boarding_target"))
        for mark in ("room:brig", "room:captains-cabin", "room:plunder-hold", "hallway"):
            self.assertTrue(T.tilemap_mark_cells("deck", mark), mark)

    def test_her_crew_is_aboard_and_calm(self):
        self.board()
        crowd = [K.boarding_hostile(k) for k in K.boarding_hostiles("deck")]
        self.assertGreaterEqual(len(crowd), 2)
        self.assertTrue(all(r["state"] == "calm" and r.get("generated") for r in crowd))

    def test_the_button_is_gone_while_they_are_aboard(self):
        self.board()
        self.select()
        self.assertNotIn(BUTTON, self.texts())

    def test_a_party_already_out_somewhere_opens_nothing(self):
        self.select()
        other = to_object(npc_spawn(0, 0, 9000, "Wreck", "pirate", "pirate_brigantine",
                                    "behav_npcship"))
        B.boarding_invite_crew(self.ship.id, "Somewhere else")
        self.press(BUTTON)
        self.assertIsNone(B.boarding_visiting())
        self.assertIsNone(T.tilemap_area("deck"))
        self.assertFalse(has_role(self.prize, "boarding_target"))
        self.assertIsNotNone(other)


# --- the three endings -------------------------------------------------------------------

class TakeHer(_Base):
    def test_the_party_comes_home_and_she_joins_their_side(self):
        self.board()
        self.emit("boarding_deck_take")
        self.home()
        self.assertEqual(self.prize.side, "tsn")
        self.assertFalse(has_role(self.prize, "surrendered"))
        self.assertTrue(has_role(self.prize, "captured"))
        self.assertTrue(has_role(self.prize, "prefab_npc_defender"))
        self.assertFalse(has_role(self.prize, "boarding_target"))
        self.assertIsNotNone(to_object(self.prize.id))

    def test_sent_with_nobody_aboard_it_takes_nothing(self):
        """The signal is a name anybody can send. With no party aboard it is a no-op."""
        self.emit("boarding_deck_take")
        self.assertEqual(self.prize.side, "surrendered")
        self.assertTrue(has_role(self.prize, "surrendered"))


class ScuttleHer(_Base):
    def test_the_party_comes_home_and_then_she_is_destroyed(self):
        self.board()
        prize = self.prize.id
        order = []

        def watch(name, data=None):
            if name == "boarding_visit_ended":
                order.append(("home", to_object(prize) is not None))
        signal_observe(watch)
        self.addCleanup(signal_unobserve, watch)
        self.emit("boarding_deck_scuttle")
        self.home()
        self.assertEqual(order, [("home", True)])        # she was still there for that
        self.assertIsNone(to_object(prize))

    def test_sent_with_nobody_aboard_it_destroys_nothing(self):
        self.emit("boarding_deck_scuttle")
        self.assertIsNotNone(to_object(self.prize.id))


class LeaveHer(_Base):
    def test_the_party_comes_home_and_she_is_as_she_was(self):
        self.board()
        self.emit("boarding_deck_leave")
        self.home()
        self.assertEqual(self.prize.side, "surrendered")
        self.assertTrue(has_role(self.prize, "surrendered"))
        self.assertFalse(has_role(self.prize, "boarding_target"))
        self.select()
        self.assertEqual(self.texts().count(BUTTON), 1)          # and can be boarded again

    def test_she_can_be_boarded_a_second_time(self):
        self.board()
        self.emit("boarding_deck_leave")
        self.seen.clear()
        self.board()
        self.assertTrue(has_role(self.prize, "boarding_target"))


class TwoConsoles(_Base):
    """A plain `//signal` would run each ending once per console."""
    consoles = (HELM, COMMS)

    def test_she_is_taken_once(self):
        self.board()
        self.emit("boarding_deck_take")
        self.home()                                      # ended once, not once each
        self.assertEqual(self.prize.side, "tsn")
        self.assertEqual(self.seen.count("boarding_deck_take"), 1)

    def test_one_button_each_and_one_party(self):
        self.select(cid=COMMS)
        self.assertEqual(self.texts().count(BUTTON), 1)
        self.press(BUTTON, cid=COMMS)
        self.assertIsNotNone(B.boarding_visiting())
        self.assertEqual(self.seen.count("boarding_went_down"), 0)   # nobody was sent


# --- a ship nobody boards is flown home as before -----------------------------------------

class TakenHome(_Base):
    def far(self):
        return abs(self.prize.pos.x - 20000.0) > 500

    def test_NOBODY_BOARDS_HER_AND_SHE_IS_FLOWN_HOME_AS_BEFORE(self):
        prize = self.prize.id
        self.present(7)                                  # one pass: `await delay_sim(5)`
        blob = self.prize.data_set
        self.assertEqual(blob.get("throttle", 0), 1.5)
        self.assertEqual(blob.get("target_pos_x", 0), 20000.0)
        self.assertIsNotNone(to_object(prize))           # not home yet
        # Within 500 of where she spawned: deleted, as before.
        mock_sbs.sim.space_objects[prize].pos.x = 19800.0
        self.present(7)
        self.assertIsNone(to_object(prize))

    def test_WITH_A_PARTY_ABOARD_SHE_IS_LEFT_ALONE(self):
        prize = self.prize.id
        self.board()
        self.present(12)                                 # two passes
        blob = self.prize.data_set
        self.assertEqual(blob.get("throttle", 0), 0)     # held, not sent home
        mock_sbs.sim.space_objects[prize].pos.x = 19800.0
        self.present(12)
        self.assertIsNotNone(to_object(prize), "deleted with a boarding party aboard")
        self.assertIsNotNone(B.boarding_visiting())

    def test_left_she_is_flown_home_again(self):
        prize = self.prize.id
        self.board()
        self.emit("boarding_deck_leave")
        self.present(7)
        self.assertEqual(self.prize.data_set.get("throttle", 0), 1.5)
        mock_sbs.sim.space_objects[prize].pos.x = 19800.0
        self.present(7)
        self.assertIsNone(to_object(prize))


if __name__ == "__main__":
    unittest.main()
