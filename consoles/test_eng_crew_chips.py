"""Engineering's crew chips (consoles/eng_crew_chips.py).

These replaced the `grid_object_list` engine widget, so the thing worth pinning is
that they are the SAME four objects and the SAME selection. The widget tabbed on a
grid object's engine `type` - the first role it was spawned with - and everything the
console must not list is spawned `#`. Get that filter wrong and the rail either loses
a `tools` object or fills with sixty rooms, and neither shows up as an error.

The selection half matters just as much: it lives on the HOST SHIP's blob
(`grid_selected_UID`), not per console, so a chip has to write there for the panel,
`grid_control` and every other engineering console on the bridge to follow.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_eng_crew_chips
"""
import os
import sys
import unittest
from contextlib import contextmanager

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes  # noqa: F401  (first, to break a circular import)
from cosmos_dev.mock import sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

from sbs_utils.consoledispatcher import ConsoleDispatcher
from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.inventory import set_inventory_value
from sbs_utils.procedural.query import get_grid_selection, to_id, to_object
from sbs_utils.procedural.roles import add_role, remove_role
from sbs_utils.procedural.spawn import grid_spawn, player_spawn
from sbs_utils.procedural import work_orders as W
from sbs_utils.spaceobject import SpaceObject

from consoles import eng_crew_chips as C

CID = 4321


class _FakeListBox:
    """Only what lm_eng_crew_pick / _refresh touch - in the SHAPES the real one uses.

    This stand-in used to answer `get_selected()` with a list whatever `multi` said,
    which is friendlier than `LayoutListbox` and therefore useless: the rail is
    single-select, the real widget hands back the bare item, and indexing it raised
    `'int' object is not subscriptable` on the first tap on a real bridge while every
    test here stayed green. A fake that is easier to satisfy than the thing it stands
    in for does not test anything.

    `multi` is a parameter so both contracts stay covered - `lm_eng_crew_pick` has to
    survive a rail that is later switched to multi-select.
    """

    def __init__(self, items=None, selected=None, multi=False):
        self.items = list(items or [])
        self.selected = list(selected or [])
        self.multi = multi
        self.dirty = 0

    def get_selected(self):
        # LayoutListbox.get_selected, verbatim.
        ret = list(self.selected)
        if self.multi:
            return ret
        if len(ret) == 1:
            return ret[0]
        return None

    def mark_visual_dirty(self):
        self.dirty += 1


class ChipBase(unittest.TestCase):
    def setUp(self):
        mock_sbs.create_new_sim()
        SpaceObject.clear()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(CID))
        self.page = StoryPage()
        self.page.pending_gui = False
        self.page.client_id = CID
        FrameContext.page = self.page
        self.ship = to_id(player_spawn(0, 0, 0, "Selene", "tsn", "cruiser"))
        mock_sbs.assign_client_to_ship(CID, self.ship)

    def tearDown(self):
        FrameContext.page = None
        FrameContext.context = None
        SpaceObject.clear()

    # --- fixtures ---------------------------------------------------------
    def damcon(self, x, name="DC1"):
        """A team, spawned exactly as grid_brains.mast spawns one."""
        go = grid_spawn(self.ship, name, name, x, 0, 80, "slateblue",
                        "crew,damcons,lifeform")
        dc_id = to_id(go)
        set_inventory_value(dc_id, "HP", 6)
        return dc_id

    def epad(self, x=9):
        """A `tools` grid object.

        The EPad - the only one the library ever spawned - was removed 2026-09-22, but
        the rail still accepts the type so a mod can add one, and these cases are what
        say so. Spawned exactly as internal_damage.py used to spawn it.
        """
        return to_id(grid_spawn(self.ship, "EPad", f"epad:{self.ship}", x, 0,
                                134, "#9994", "tools,epad"))

    def room(self, x, *roles):
        """A room or system node - spawned `#`, the do-not-list type."""
        return to_id(grid_spawn(self.ship, f"node{x}", f"node{x}", x, 0, 12,
                                "white", "#," + ",".join(roles or ("room",))))

    def broken(self, x):
        """A node there is actually something to do to.

        `work_orders_for` PURGES as it reads, so an order on a healthy node is gone
        by the time anything lists it - which is the point of it, and a fixture that
        forgets makes every status read "idle"."""
        return self.room(x, "system", "weapon", "__damaged__")

    def select(self, node_id):
        mock_sbs.sim.get_space_object(self.ship).data_set.set(
            "grid_selected_UID", node_id or 0, 0)


class TestTheChipsAreTheEngineList(ChipBase):
    def test_teams_come_first_then_tools_each_by_name(self):
        pad = self.epad()
        c = self.damcon(3, "DC3")
        a = self.damcon(1, "DC1")
        b = self.damcon(2, "DC2")
        self.assertEqual(C.lm_eng_crew_items(CID), [a, b, c, pad])

    def test_rooms_and_systems_are_not_chips(self):
        """Everything the engine list hid behind the `#` type stays hidden. A ship
        has dozens of these; one leaking in fills the rail."""
        dc = self.damcon(1)
        self.room(4, "room")
        self.room(5, "system")
        self.room(6, "hallway")
        self.assertEqual(C.lm_eng_crew_items(CID), [dc])

    def test_a_console_with_no_ship_has_no_chips(self):
        mock_sbs.assign_client_to_ship(CID, 0)
        self.assertEqual(C.lm_eng_crew_items(CID), [])

    def test_a_ship_with_no_interior_has_no_chips(self):
        self.assertEqual(C.lm_eng_crew_items(CID), [])


class TestWhatAChipSays(ChipBase):
    def test_an_idle_team_says_idle(self):
        dc = self.damcon(1)
        label, status, _name_color, _status_color = C.lm_eng_crew_state(dc)
        self.assertEqual((label, status), ("DC1", "idle"))

    def test_a_team_on_a_repair_says_repairing(self):
        dc = self.damcon(1)
        W.work_order_add(dc, self.broken(4))
        self.assertEqual(C.lm_eng_crew_state(dc)[1], "fixing")

    def test_a_second_job_is_counted_not_listed(self):
        dc = self.damcon(1)
        W.work_order_add(dc, self.broken(4))
        W.work_order_add(dc, self.broken(5))
        self.assertEqual(C.lm_eng_crew_state(dc)[1], "fixing +1")

    def test_a_hurt_team_is_colored_not_relabeled(self):
        """The status line still says what the team is DOING. Losing that to an HP
        word is what makes a rail stop being a rail."""
        dc = self.damcon(1)
        set_inventory_value(dc, "HP", 1)
        label, status, _name_color, status_color = C.lm_eng_crew_state(dc)
        self.assertEqual((label, status), ("DC1", "idle"))
        self.assertEqual(status_color, "Crimson")

    def test_the_epad_is_a_tool_not_a_team(self):
        self.assertEqual(C.lm_eng_crew_state(self.epad())[1], "tools")

    def test_every_chip_is_ascii(self):
        """These reach an engine-rendered surface."""
        dc = self.damcon(1)
        W.work_order_add(dc, self.broken(4))
        for item in (dc, self.epad()):
            for part in C.lm_eng_crew_state(item)[:2]:
                part.encode("ascii")


class TestTheChipsDriveTheShipsSelection(ChipBase):
    def test_tapping_a_chip_selects_that_team_on_the_ship(self):
        a = self.damcon(1, "DC1")
        b = self.damcon(2, "DC2")
        lb = _FakeListBox(C.lm_eng_crew_items(CID), [b])
        self.assertEqual(lb.get_selected(), b, "the fake must answer as the real one")
        with self._route_tap() as fired:
            self.assertEqual(C.lm_eng_crew_pick(CID, lb), b)
        self.assertEqual(get_grid_selection(self.ship), b)
        self.assertNotEqual(get_grid_selection(self.ship), a)
        # Writing the blob is half of it. grid_object_list ALSO fired the selection
        # route, which is what opens grid_control's button list for the new pick -
        # a chip that only wrote the blob would select a team and offer no orders.
        self.assertEqual(len(fired), 1)
        event = fired[0]
        self.assertEqual(event.sub_tag, "grid_selected_UID")
        self.assertEqual(event.value_tag, "grid_object_list")
        self.assertEqual(event.selected_id, b)

    def test_a_multi_select_rail_would_still_work(self):
        """get_selected answers with a LIST when multi - the other half of the
        contract, so switching the rail over cannot resurrect the crash."""
        a = self.damcon(1, "DC1")
        lb = _FakeListBox([a], [a], multi=True)
        self.assertEqual(lb.get_selected(), [a])
        with self._route_tap():
            self.assertEqual(C.lm_eng_crew_pick(CID, lb), a)
        self.assertEqual(get_grid_selection(self.ship), a)

    def test_an_empty_single_select_rail_answers_None_not_an_empty_list(self):
        dc = self.damcon(1)
        lb = _FakeListBox([dc], [])
        self.assertIsNone(lb.get_selected())
        with self._route_tap() as fired:
            self.assertIsNone(C.lm_eng_crew_pick(CID, lb))
        self.assertEqual(fired, [])

    def test_re_selecting_what_is_already_selected_does_not_re_fire(self):
        """The refresh path writes lb.selected to follow the ship, and that fires
        the same `on change` a tap does. Re-firing the route re-enters the
        //comms/grid tree, which sends grid_control back to its root - so an
        engineer three levels into a submenu gets bounced out whenever a team picks
        up a job somewhere else on the ship."""
        dc = self.damcon(1)
        self.select(dc)
        lb = _FakeListBox([dc], [dc])
        with self._route_tap() as fired:
            self.assertEqual(C.lm_eng_crew_pick(CID, lb), dc)
        self.assertEqual(fired, [], "re-fired the selection route on a no-op")
        self.assertEqual(get_grid_selection(self.ship), dc)

    def test_a_refresh_that_changes_nothing_fires_nothing(self):
        dc = self.damcon(1)
        self.select(dc)
        lb = _FakeListBox([], [])
        C.lm_eng_crew_refresh(CID, lb)
        with self._route_tap() as fired:
            C.lm_eng_crew_pick(CID, lb)
        self.assertEqual(fired, [])

    @contextmanager
    def _route_tap(self):
        """Record the selection events lm_eng_crew_pick dispatches.

        Tapped rather than let through: the real handler is the grid-comms one, and
        it needs a live MAST task to start the //comms/grid tree on. That belongs in
        the console harness, not here - what this file owns is that the route goes
        out, correctly addressed.
        """
        fired = []
        orig = ConsoleDispatcher.dispatch_select
        ConsoleDispatcher.dispatch_select = staticmethod(fired.append)
        try:
            yield fired
        finally:
            ConsoleDispatcher.dispatch_select = orig

    def test_the_rail_shows_the_ships_selection_whoever_made_it(self):
        """Selection is per SHIP, so a team picked on the interior view - or by the
        other engineer - lights the chip here."""
        dc = self.damcon(1)
        self.select(dc)
        self.assertEqual(C.lm_eng_crew_selected(CID), [dc])

    def test_a_selected_ROOM_lights_no_chip(self):
        """A room is a real selection and the panel shows it - but it is not one of
        these four, so the rail must not leave the last team lit."""
        self.damcon(1)
        self.select(self.room(4))
        self.assertEqual(C.lm_eng_crew_selected(CID), [])

    def test_tapping_nothing_changes_nothing(self):
        dc = self.damcon(1)
        self.select(dc)
        self.assertIsNone(C.lm_eng_crew_pick(CID, _FakeListBox([dc], [])))
        self.assertEqual(get_grid_selection(self.ship), dc)


class TestTheChipsRedrawOnlyWhenSomethingMoved(ChipBase):
    def test_a_settled_rail_reports_the_same_revision(self):
        self.damcon(1)
        self.epad()
        self.assertEqual(C.lm_eng_crew_revision(CID), C.lm_eng_crew_revision(CID))

    def test_a_new_job_moves_the_revision(self):
        dc = self.damcon(1)
        before = C.lm_eng_crew_revision(CID)
        W.work_order_add(dc, self.broken(4))
        self.assertNotEqual(C.lm_eng_crew_revision(CID), before)

    def test_a_new_team_moves_the_revision(self):
        self.damcon(1)
        before = C.lm_eng_crew_revision(CID)
        self.damcon(2, "DC2")
        self.assertNotEqual(C.lm_eng_crew_revision(CID), before)

    def test_refresh_reloads_the_items_and_the_selection(self):
        dc = self.damcon(1)
        self.select(dc)
        lb = _FakeListBox([], [])
        C.lm_eng_crew_refresh(CID, lb)
        self.assertEqual(lb.items, [dc])
        self.assertEqual(lb.selected, [dc])
        self.assertEqual(lb.dirty, 1)


class TestTheNameSurvivesAnEngineBuiltInterior(ChipBase):
    """THE FIELD REPORT, twice: "the chips all say unnamed".

    `unnamed` is the ENGINE's placeholder for an object nothing named - a literal in
    Artemis3-x64-release.exe. Two separate mistakes produced it, both invisible on
    the mock:

    * the rail filtered on the sbs_utils ROLE `damcons` while `grid_object_list`
      tabbed on the grid object's engine `type`, so it listed different objects; and
    * the name came from `GridObject.name`, a python-side cache only this process
      fills, rather than from the live grid object.

    The rail now makes one pass over the hull map and takes the type AND the name
    from the same place the widget did.
    """

    def test_the_rail_is_the_engine_type_not_the_role(self):
        """A team whose Agent lost the `damcons` role is still crew to the hull map,
        and is still what the engineer needs to command."""
        dc = self.damcon(1, "DC1")
        remove_role(dc, "damcons")
        self.assertEqual(C.lm_eng_crew_items(CID), [dc])
        self.assertEqual(C.lm_eng_crew_state(dc, CID)[0], "DC1")

    def test_a_room_wearing_the_damcons_role_is_still_not_on_the_rail(self):
        """The other direction: the `#` type is the do-not-list type, whatever roles
        an agent happens to carry."""
        dc = self.damcon(1)
        stray = self.room(4, "room")
        add_role(stray, "damcons")
        self.assertEqual(C.lm_eng_crew_items(CID), [dc])

    def test_the_engines_placeholder_is_never_printed(self):
        """An engine-built interior answers `unnamed`. LM sets a team's tag to its
        name, so the tag is the better answer."""
        dc = self.damcon(1, "DC1")
        to_object(dc).grid_object().name = "unnamed"
        self.assertEqual(C.lm_eng_crew_state(dc, CID)[0], "DC1")

    def test_the_placeholder_is_matched_whatever_its_case(self):
        dc = self.damcon(1, "DC1")
        to_object(dc).grid_object().name = "Unnamed"
        self.assertEqual(C.lm_eng_crew_state(dc, CID)[0], "DC1")

    def test_an_empty_cache_no_longer_matters(self):
        """The old lookup read this and nothing else."""
        dc = self.damcon(1, "DC1")
        to_object(dc)._name = ""
        self.assertEqual(C.lm_eng_crew_state(dc, CID)[0], "DC1")

    def test_a_chip_is_never_blank(self):
        """A chip with no text is an invisible button."""
        dc = self.damcon(1, "DC1")
        go = to_object(dc).grid_object()
        go.name = "unnamed"
        go.tag = ""
        self.assertTrue(C.lm_eng_crew_state(dc, CID)[0].strip())


class TestTheChipWearsTheTeamsColor(ChipBase):
    """A chip and the figure it selects are one team, so they are one color.

    The team color is the same inventory value `eng_grid_panel`'s header glyph and the
    figure on the interior view read, so the three cannot disagree.
    """

    def test_the_name_is_the_teams_own_color(self):
        dc = self.damcon(1, "DC1")
        set_inventory_value(dc, "color", "slateblue")
        self.assertEqual(C.lm_eng_crew_state(dc, CID)[2], "slateblue")

    def test_two_teams_wear_their_own_colors(self):
        a = self.damcon(1, "DC1")
        b = self.damcon(2, "DC2")
        set_inventory_value(a, "color", "slateblue")
        set_inventory_value(b, "color", "orange")
        self.assertEqual(C.lm_eng_crew_state(a, CID)[2], "slateblue")
        self.assertEqual(C.lm_eng_crew_state(b, CID)[2], "orange")

    def test_a_team_with_no_color_still_draws(self):
        """A missing color must not emit `color:None;` into a style string."""
        dc = self.damcon(1, "DC1")
        set_inventory_value(dc, "color", None)
        name_color = C.lm_eng_crew_state(dc, CID)[2]
        self.assertTrue(name_color)
        self.assertNotIn("None", str(name_color))

    def test_hurt_colors_the_STATUS_not_the_name(self):
        """The name is identity and must not change meaning when a team takes a hit -
        otherwise a hurt team stops being findable by color."""
        dc = self.damcon(1, "DC1")
        set_inventory_value(dc, "color", "slateblue")
        set_inventory_value(dc, "HP", 1)
        _label, _status, name_color, status_color = C.lm_eng_crew_state(dc, CID)
        self.assertEqual(name_color, "slateblue")
        self.assertEqual(status_color, "Crimson")

    def test_a_working_team_still_wears_its_color(self):
        dc = self.damcon(1, "DC1")
        set_inventory_value(dc, "color", "slateblue")
        W.work_order_add(dc, self.broken(4))
        _label, status, name_color, _sc = C.lm_eng_crew_state(dc, CID)
        self.assertEqual(status, "fixing")
        self.assertEqual(name_color, "slateblue")


if __name__ == "__main__":
    unittest.main()
