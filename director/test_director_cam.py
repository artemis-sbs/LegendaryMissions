"""The Director console stays seated on its own camera. This is the regression test.

THE BUG THIS GUARDS, in full, because it cost a session to find and will come back:

  Staging a shot calls `shot_apply` -> `camera_track`, and `camera_track` does
  `sbs.assign_client_to_ship(cid, dolly)`. It MUST - the engine only honors a camera change
  when the console and the lens ride the same object. So a Director console that has
  previewed anything is no longer assigned to its own cam.

  Everything the stage tab does is gated on `has_roles(SCIENCE_ORIGIN_ID, "director_cam")`,
  and `SCIENCE_ORIGIN_ID` is exactly `sbs.get_ship_of_client(client_id)`. So after ONE visit
  to the shot tab, `//focus/science` and `//enable/science` silently stopped matching,
  clicking the 2D view selected nothing, and NOTHING WAS LOGGED. It was reported as
  "in stage, selecting a subject eventually gets broken" - eventually, because it broke the
  first time the operator opened the shot tab and only a trip back through the main page,
  the one label that re-seated, ever fixed it.

`director_cam_ensure` is the fix and every tab calls it. These tests use the real mock sim
rather than stubs, because the whole bug lives in what `get_ship_of_client` answers.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_cam
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cosmos_dev.mock import sbs
from sbs_utils.helpers import Context, FrameContext, FakeEvent
from sbs_utils.agent import Agent
from sbs_utils.gui import Gui, GuiClient
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.roles import role, has_role
from sbs_utils.procedural.spawn import player_spawn
from sbs_utils.procedural.query import to_id

import director_cam as dc

CLIENT = 0x8080000000000001


def _fresh_client():
    """A clean sim with a REGISTERED client agent.

    The client agent matters: `set_inventory_value(client_id, ...)` only sticks on an agent
    that exists, and in production one always does - `GuiClient` is an Agent and registers
    itself when a console connects. Without this the cam id would be written nowhere, every
    call would spawn a second cam, and the tests would be measuring the harness.
    """
    sbs.create_new_sim()
    SpaceObject.clear()
    Gui.clients.clear()
    Gui.clients[CLIENT] = GuiClient(CLIENT)
    return Gui.clients[CLIENT]


class DirectorCamTests(unittest.TestCase):
    def setUp(self):
        _fresh_client()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())

    def tearDown(self):
        SpaceObject.clear()
        FrameContext.context = None

    def test_it_spawns_a_cam_and_seats_the_client(self):
        cam_id = dc.director_cam_ensure(CLIENT)
        self.assertIsNotNone(cam_id)
        self.assertEqual(sbs.get_ship_of_client(CLIENT), cam_id)
        self.assertTrue(has_role(cam_id, "director_cam"))

    def test_the_cam_is_not_a_player(self):
        # The ONE thing keeping it out of every role("__player__") query: the ship pickers,
        # the generators, scoring, end-game checks, NPC targeting.
        cam_id = dc.director_cam_ensure(CLIENT)
        self.assertNotIn(cam_id, role("__player__"))

    def test_it_is_idempotent(self):
        first = dc.director_cam_ensure(CLIENT)
        second = dc.director_cam_ensure(CLIENT)
        self.assertEqual(first, second)
        self.assertEqual(len(role("director_cam")), 1)

    def test_it_reseats_a_client_a_shot_stole(self):
        # THE REGRESSION. camera_track reassigns the console to the shot subject; without
        # the re-seat every //focus route gated on the cam role stops matching, in silence.
        cam_id = dc.director_cam_ensure(CLIENT)
        subject = to_id(player_spawn(5000, 0, 5000, "Artemis", "tsn", "tsn_light_cruiser"))
        sbs.assign_client_to_ship(CLIENT, subject)
        self.assertNotEqual(sbs.get_ship_of_client(CLIENT), cam_id)
        self.assertFalse(has_role(sbs.get_ship_of_client(CLIENT), "director_cam"))

        dc.director_cam_ensure(CLIENT)

        self.assertEqual(sbs.get_ship_of_client(CLIENT), cam_id)
        self.assertTrue(has_role(sbs.get_ship_of_client(CLIENT), "director_cam"))

    def test_cam_of_answers_while_a_shot_is_live(self):
        # Which is why nothing may ask get_ship_of_client for "this console's own ship".
        cam_id = dc.director_cam_ensure(CLIENT)
        subject = to_id(player_spawn(5000, 0, 5000, "Artemis", "tsn", "tsn_light_cruiser"))
        sbs.assign_client_to_ship(CLIENT, subject)
        self.assertEqual(dc.director_cam_of(CLIENT), cam_id)
        self.assertNotEqual(sbs.get_ship_of_client(CLIENT), dc.director_cam_of(CLIENT))

    def test_a_lost_cam_is_respawned(self):
        # The RESTART GUARD: the DIRECTOR_CAM inventory value survives a sim_create() that
        # took the object with it, so testing the id alone would seat the client on a hull
        # that no longer exists.
        first = dc.director_cam_ensure(CLIENT)
        stale = Gui.clients[CLIENT].get_inventory_value("DIRECTOR_CAM", None)
        self.assertEqual(stale, first)
        # A sim_create() takes the object but NOT the inventory value pointing at it - which
        # is the whole reason the guard tests to_object() and not just the id.
        SpaceObject.clear()
        sbs.create_new_sim()
        Gui.clients[CLIENT] = GuiClient(CLIENT)
        Gui.clients[CLIENT].set_inventory_value("DIRECTOR_CAM", stale)
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        second = dc.director_cam_ensure(CLIENT)
        # NOT `second != first`: the mock restarts its id counter with the sim, so the new
        # cam can legitimately reuse the old id and that assertion would be measuring the
        # harness. What matters is that the id now names a LIVE object and the client is on
        # it - which is exactly what seating on the stale id would fail to do.
        from sbs_utils.procedural.query import to_object
        self.assertIsNotNone(second)
        self.assertIsNotNone(to_object(second))
        self.assertTrue(has_role(second, "director_cam"))
        self.assertEqual(sbs.get_ship_of_client(CLIENT), second)

    def test_the_cam_takes_a_side_from_the_console_previous_ship(self):
        # Scan data is stored per the ORIGIN's SIDE, so a cam with no side writes into a
        # slot nothing reads back and scans silently do not take. The GM and the OU Admiral
        # both assign one; this used not to.
        ship = to_id(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        sbs.assign_client_to_ship(CLIENT, ship)
        cam_id = dc.director_cam_ensure(CLIENT)
        from sbs_utils.procedural.query import to_object
        self.assertEqual(to_object(cam_id).side, "tsn")


class CrewNameIntegrationTests(unittest.TestCase):
    """`<<crew_name>>` against a REALLY seated client, not a stubbed one.

    WHY THIS EXISTS SEPARATELY from the token tests in test_director_overlays. Those stub
    `linked_to` and `get_inventory_value`, so they prove the resolver's LOGIC and nothing about
    whether it reads the same keys `common_console_select` writes. That is the actual risk: a
    key name is a string agreed between two files that never import each other, and getting it
    wrong fails silently - the lower third just says `unmanned` forever.

    So this seats a client the way the picker does, through the real link and inventory APIs,
    and asks the real resolver. `test_the_keys_match_the_picker` then pins the agreement to the
    picker's source, so a rename there fails here rather than on air.
    """

    PICKER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "consoles", "common_console_select.mast")

    def setUp(self):
        _fresh_client()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())

    def tearDown(self):
        SpaceObject.clear()
        FrameContext.context = None

    def _seat(self, ship_id, client_id, console, crew_name):
        """Exactly what show_console_selected does, in the same order."""
        from sbs_utils.procedural.links import link
        from sbs_utils.procedural.inventory import set_inventory_value
        Gui.clients[client_id] = GuiClient(client_id)
        link(ship_id, "consoles", client_id)
        set_inventory_value(client_id, "CONSOLE_TYPE", console)
        set_inventory_value(client_id, "CREW_NAME", crew_name)

    def test_the_token_names_the_person_at_that_station(self):
        import director_overlays as ov
        ship = to_id(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        self._seat(ship, 0x8080000000000010, "helm", "Viper")
        self._seat(ship, 0x8080000000000011, "weapons", "Maverick")

        item = {"kind": "con", "ship": ship, "console": "helm"}
        got = ov.director_overlay_resolve("<<name>> - <<console>> - <<crew_name>>", ship, item)
        self.assertEqual(got, "Artemis - Helm - Viper")

    def test_it_picks_the_BEATS_station_off_a_full_bridge(self):
        # A bridge has five people on it. Naming the wrong one on air is worse than naming
        # nobody, and a resolver that took the first linked client would do exactly that.
        import director_overlays as ov
        ship = to_id(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        seats = {"helm": "Viper", "weapons": "Maverick", "science": "Goose",
                 "comms": "Iceman", "engineering": "Jester"}
        for i, (console, who) in enumerate(sorted(seats.items())):
            self._seat(ship, 0x8080000000000020 + i, console, who)
        for console, who in seats.items():
            item = {"kind": "con", "ship": ship, "console": console}
            self.assertEqual(ov.director_overlay_resolve("<<crew_name>>", ship, item), who,
                             console)

    def test_an_empty_seat_falls_back(self):
        import director_overlays as ov
        ship = to_id(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        self._seat(ship, 0x8080000000000030, "helm", "Viper")
        item = {"kind": "con", "ship": ship, "console": "science"}
        self.assertEqual(
            ov.director_overlay_resolve("<<crew_name|unmanned>>", ship, item), "unmanned")

    def test_a_ship_with_nobody_aboard_falls_back(self):
        import director_overlays as ov
        ship = to_id(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        item = {"kind": "con", "ship": ship, "console": "helm"}
        self.assertEqual(
            ov.director_overlay_resolve("<<crew_name|unmanned>>", ship, item), "unmanned")

    def test_the_keys_match_the_picker(self):
        """The agreement, pinned to the picker's own source.

        Three strings shared between two files that never import each other. A rename in
        `common_console_select` would leave the lower third permanently reading `unmanned`,
        with nothing logged and nothing failing - so it fails HERE instead.
        """
        with io.open(self.PICKER, encoding="utf-8") as handle:
            picker = handle.read()
        for wrote in ('link(_ship_id, "consoles", client_id)',
                      'set_inventory_value(client_id, "CONSOLE_TYPE"',
                      'set_inventory_value(client_id, "CREW_NAME"'):
            self.assertIn(wrote, picker,
                          "the console picker no longer writes what <<crew_name>> reads")


class DirectorNameTests(unittest.TestCase):
    def setUp(self):
        _fresh_client()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())

    def tearDown(self):
        SpaceObject.clear()
        FrameContext.context = None

    def test_a_name_round_trips(self):
        dc.director_cam_name(CLIENT, "Wall Left")
        self.assertEqual(dc.director_cam_name(CLIENT), "Wall Left")

    def test_braces_are_stripped_from_a_name(self):
        # A MAST assignment re-runs an assigned STRING through f-string formatting, so a
        # brace typed into the name field would raise against the panel, not the typist.
        dc.director_cam_name(CLIENT, "Wall {Left}")
        self.assertNotIn("{", dc.director_cam_name(CLIENT))

    def test_a_default_name_beats_unnamed(self):
        dc.director_cam_ensure(CLIENT)
        self.assertEqual(dc.director_cam_default_name(CLIENT), "DIR01")

    def test_the_prefix_follows_the_mode(self):
        # A streamer with four windows open is reading tab titles: "Director 3" on a program
        # screen says the wrong thing about what that screen is.
        self.assertEqual(dc.director_cam_default_name(CLIENT, "program"), "PROG01")
        self.assertEqual(dc.director_cam_default_name(CLIENT, "preview"), "PRE01")

    def test_a_crew_name_does_not_survive_into_a_screen_name(self):
        # THE ONE THAT MATTERS since the Name field went. `common_console_select` writes
        # CREW_NAME from the crew-name flow, so a client that named itself before opening the
        # Director arrives with a person's name in that key - and a program screen called
        # "Doug" says nothing about what it is. The derivation ignores it.
        dc.director_cam_name(CLIENT, "Doug")
        self.assertEqual(dc.director_cam_default_name(CLIENT, "program"), "PROG01")

    def test_the_name_moves_when_the_mode_does(self):
        dc.director_cam_name(CLIENT, "PROG01")
        self.assertEqual(dc.director_cam_default_name(CLIENT, "preview"), "PRE01")

    def test_re_entering_the_same_mode_keeps_the_number(self):
        # suggest_name skips this client's own name, so asking again is stable rather than
        # climbing PROG01 -> PROG02 every time the entry screen is revisited.
        dc.director_cam_name(CLIENT, "PROG01")
        self.assertEqual(dc.director_cam_default_name(CLIENT, "program"), "PROG01")

    def test_the_number_auto_increments_past_names_in_use(self):
        other = 0x8080000000000002
        Gui.clients[other] = GuiClient(other)
        Gui.clients[other].add_role("console, director")
        dc.director_cam_name(other, "DIR01")
        self.assertEqual(dc.director_cam_default_name(CLIENT), "DIR02")

    def test_it_reuses_a_number_a_departed_console_freed(self):
        # Lowest free, not highest+1: a console that left should not cost the next one a
        # number forever, and a counted-cams version would keep climbing off leaked cams.
        a = 0x8080000000000002
        b = 0x8080000000000003
        for cid, name in ((a, "DIR01"), (b, "DIR03")):
            Gui.clients[cid] = GuiClient(cid)
            Gui.clients[cid].add_role("console, director")
            dc.director_cam_name(cid, name)
        self.assertEqual(dc.director_cam_default_name(CLIENT), "DIR02")

    def test_a_program_screen_still_holds_its_number(self):
        # A screen sent to program loses the `director` ROLE, so a role-only scan would hand
        # the next console a name that is already on a screen. Scanning every console covers it
        # - which is also why the earlier DIRECTOR_HOME back-pointer is no longer needed.
        other = 0x8080000000000002
        Gui.clients[other] = GuiClient(other)
        Gui.clients[other].add_role("console, cinematic")
        dc.director_cam_name(other, "PROG01")
        self.assertEqual(dc.director_cam_default_name(CLIENT, "program"), "PROG02")

    def test_numbering_is_per_prefix(self):
        other = 0x8080000000000002
        Gui.clients[other] = GuiClient(other)
        Gui.clients[other].add_role("console, director")
        dc.director_cam_name(other, "PROG01")
        self.assertEqual(dc.director_cam_default_name(CLIENT, "preview"), "PRE01")


class CameraPointTests(unittest.TestCase):
    """The cam used as a SUBJECT - "a shot of this place".

    A click on empty space pans the cam and selects it, so a bound item parked on the cam
    orbits wherever the operator dropped it. Two things follow, and neither is cosmetic: the
    cam is nameless by design, and it has no hull to size a shot off.
    """

    def setUp(self):
        _fresh_client()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())

    def tearDown(self):
        SpaceObject.clear()
        FrameContext.context = None

    def test_a_cam_is_a_camera_point(self):
        cam_id = dc.director_cam_ensure(CLIENT)
        self.assertTrue(dc.director_is_camera_point(cam_id))

    def test_an_ordinary_ship_is_not(self):
        ship = to_id(player_spawn(0, 0, 0, "Artemis", "tsn", "behav_playership"))
        self.assertFalse(dc.director_is_camera_point(ship))

    def test_nothing_is_not(self):
        # Every labeller and the framing call this before doing anything, so `None` and a dead
        # id have to be answers rather than raises.
        self.assertFalse(dc.director_is_camera_point(None))
        self.assertFalse(dc.director_is_camera_point(0))
        self.assertFalse(dc.director_is_camera_point(999999))

    def test_the_cam_is_nameless(self):
        # The premise of director_cam_point_name. If this ever stops being true the display
        # name should go with it - a name would put the cam in engine lists it is kept out of.
        cam = Agent.get(dc.director_cam_ensure(CLIENT))
        self.assertFalse(getattr(cam, "name", None))

    def test_a_point_is_named_after_its_console(self):
        # "camera point" alone does not say whose, with four windows open.
        dc.director_cam_name(CLIENT, "DIR01")
        cam_id = dc.director_cam_ensure(CLIENT)
        self.assertEqual(dc.director_cam_point_name(cam_id), "DIR01 point")

    def test_an_unnamed_console_still_gets_a_readable_point(self):
        cam_id = dc.director_cam_ensure(CLIENT)
        self.assertEqual(dc.director_cam_point_name(cam_id), "camera point")

    def test_a_ship_has_no_point_name(self):
        ship = to_id(player_spawn(0, 0, 0, "Artemis", "tsn", "behav_playership"))
        self.assertIsNone(dc.director_cam_point_name(ship))

    def test_a_point_is_framed_for_a_battle_not_a_hull(self):
        # THE ONE THAT MATTERS FOR THE SHOT. viewscreen_framing sizes off exclusion_radius, and
        # an invisible cam has none - so it falls to DEFAULT_RADIUS (90) and gives a 540/1440
        # shot, which frames one mid-sized ship. Parking the cam in the middle of a fight and
        # orbiting it at 540 units would be inside the engagement looking at nothing.
        import director_play as dp
        cam_id = dc.director_cam_ensure(CLIENT)
        near, far = dp._framing(cam_id)
        self.assertEqual((near, far), (dp.DIRECTOR_POINT_NEAR, dp.DIRECTOR_POINT_FAR))
        ship = to_id(player_spawn(0, 0, 0, "Artemis", "tsn", "behav_playership"))
        self.assertNotEqual(dp._framing(ship), (near, far))

    # What a probe measured off the siege map, sampling the densest knot of armed combatants
    # twice a second for 90s. These are the numbers the framing is sized against, and having
    # them here is what stops the next edit going back to round numbers that feel right.
    MEASURED_TYPICAL_RADIUS = 140.0     # median cluster radius
    MEASURED_WIDE_RADIUS = 3234.0       # the widest cluster seen
    # A camera at d with a ~60 degree vertical FOV holds a cluster of radius d * 0.577 / 1.3.
    FRAME_FACTOR = 2.25

    def test_the_framing_holds_a_real_engagement(self):
        """Sized against measured cluster radii, not against numbers that sound round.

        The first pass used 2500/7000, which held the WIDEST cluster ever seen and made the
        common one - four ships inside 140u - four dots. Both ends matter: NEAR is what a dolly
        pushes in to, FAR is the orbit radius and the shot most beats actually get.
        """
        import director_play as dp
        self.assertGreater(dp.DIRECTOR_POINT_FAR, dp.DIRECTOR_POINT_NEAR)
        # NEAR frames a TIGHT knot filling the frame - comfortably outside it, not inside.
        near_holds = dp.DIRECTOR_POINT_NEAR / self.FRAME_FACTOR
        self.assertGreater(near_holds, self.MEASURED_TYPICAL_RADIUS,
                           "NEAR is inside a typical engagement")
        self.assertLess(near_holds, self.MEASURED_WIDE_RADIUS,
                        "NEAR is so far out that the close end of a dolly is still a wide shot")
        # FAR holds a spread fight without making a typical one specks: it should cover well
        # over the median and stay under the widest, which is a rare outlier.
        far_holds = dp.DIRECTOR_POINT_FAR / self.FRAME_FACTOR
        self.assertGreater(far_holds, 4 * self.MEASURED_TYPICAL_RADIUS)
        self.assertLess(far_holds, self.MEASURED_WIDE_RADIUS)


if __name__ == "__main__":
    unittest.main()
