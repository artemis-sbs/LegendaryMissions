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

    def test_a_typed_name_is_not_overwritten_by_the_default(self):
        dc.director_cam_name(CLIENT, "Stream Out")
        self.assertEqual(dc.director_cam_default_name(CLIENT), "Stream Out")
        self.assertEqual(dc.director_cam_default_name(CLIENT, "program"), "Stream Out")

    def test_a_suggested_name_IS_replaced_when_the_mode_moves(self):
        # The entry screen re-suggests on every move of the mode radio. A name that still looks
        # like ours is ours to change; anything typed is not.
        dc.director_cam_name(CLIENT, "PROG01")
        self.assertEqual(dc.director_cam_default_name(CLIENT, "preview"), "PRE01")

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


if __name__ == "__main__":
    unittest.main()
