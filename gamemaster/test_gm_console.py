"""The Game Master console builds, and its buttons do what they say.

`--test` never opens a console and `--exercise` reaches this one only by luck, so the
sidebar menus (spawn, sides, time limit, selection details) had no coverage at all. This
compiles the real addon files, opens the real `@console/gamemaster` label on a client
page, and presses the real buttons.

    PYTHONPATH=../sbs_utils python -m unittest gamemaster.test_gm_console
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

GM = os.path.dirname(os.path.abspath(__file__))
LM = os.path.dirname(GM)
# map_common.py does `from fleet import ...`: its siblings have to be importable.
for _d in ("fleets", "turrets"):
    sys.path.insert(0, os.path.join(LM, _d))

from sbs_utils.agent import Agent, clear_shared
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers gui/route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural import ship_data
from sbs_utils.procedural.fleet_tables import fleet_table_register
from sbs_utils.procedural.gui.navigation import gui_reroute_client
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.prefab import prefab_spawn
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.signal import signal_emit
from sbs_utils.procedural.sides import (side_are_enemies, side_create,
                                        side_keys_set, side_set_relations)
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.procedural.timers import is_timer_set
from sbs_utils.spaceobject import SpaceObject

# A console id carries the console bit; a bare small int takes the not-a-console branch.
CID = 0x8080000000000001

# Imports first so every route's signal_register lands in main; the park goes last.
# The prefab and fleet files are the ones the spawn menus enumerate by `type:`.
HARNESS_STORY = "\n".join([
    "shared SETTINGS = {}",
    # LM's server console publishes this from the picker; the terrain prefabs read it.
    'shared TERRAIN_SELECT = "few"',
    "import ../fleets/fleet.py",
    "import ../fleets/map_common.py",
    "import ../turrets/turrets.py",
    "import ../prefabs/basic_enemy.mast",
    "import ../prefabs/terrain_prefabs.mast",
    "import ../prefabs/station_prefabs.mast",
    "import ../prefabs/monster.mast",
    "import ../fleets/fleet.mast",
    "import ../turrets/turrets.mast",
    "import gamemaster.mast",
    "import gamemaster_spawn.mast",
    "import gamemaster_selection_details.mast",
    "import gamemaster_controls.py",
    "import gamemaster_info_panel.py",
    "import gamemaster.py",
    "import move_to_lib.py",
    "gui_text('$text:harness;')",
    "await gui()",
    "",
])


class GmPage(StoryPage):
    story = None


class _Emitted:
    """Every widget the page sent, as (send function, tag, props)."""

    SENDS = ("send_gui_text", "send_gui_button", "send_gui_icon", "send_gui_iconbutton",
             "send_gui_clickregion")

    def __init__(self):
        self.sent = []

    def install(self):
        self._orig = {}
        for name in self.SENDS:
            self._orig[name] = getattr(mock_sbs, name)
            setattr(mock_sbs, name, self._rec(name, self._orig[name]))

    def remove(self):
        for name, fn in self._orig.items():
            setattr(mock_sbs, name, fn)

    def _rec(self, name, orig):
        def _fn(client_id, parent, tag, props, *rest):
            if client_id == CID:
                self.sent.append((name, tag, props or ""))
            return orig(client_id, parent, tag, props, *rest)
        return _fn

    def clear(self):
        self.sent.clear()

    def tags(self, send, needle):
        """Tags of the widgets of one kind whose props hold `needle`, in draw order."""
        found = []
        for name, tag, props in self.sent:
            if name == send and needle in props and tag not in found:
                found.append(tag)
        return found

    def button_named(self, needle):
        return self.tags("send_gui_button", needle)

    def text_with(self, needle):
        return [p for n, _t, p in self.sent if n == "send_gui_text" and needle in p]


class _Base(unittest.TestCase):
    # LM's server console emits this when the map starts; the console's clock rides it.
    game_started = True

    def setUp(self):
        from sbs_utils.handlerhooks import reset_mission_state
        reset_mission_state()
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        DeleteQueue.clear()
        SpaceObject.clear()
        clear_shared()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)

        self.emitted = _Emitted()
        self.emitted.install()

        story = MastStory()
        story.basedir = GM
        errors = story.compile(HARNESS_STORY, "gmharness", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        GmPage.story = story
        FrameContext.mast = story
        self.story = story

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append

        self.server = GmPage()
        Gui.push(0, self.server)
        self.page = GmPage()
        Gui.push(CID, self.page)
        self.present()

        # Starting the story resets shared data, so the world is built after it.
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)
        for key, name in (("tsn", "TSN"), ("raider", "Raider"), ("civ", "Civilian")):
            side_create(key, name, "")
        side_set_relations("tsn", "raider", mock_sbs.DIPLOMACY.HOSTILE)
        # What the races addon and the turret hull file supply in a real mission.
        fleet_table_register("kralien", [[["kralien_cruiser", "kralien_cruiser"]]] * 11)
        ship_data._extra_ship_data_loaded.append(
            ("extraShipData_turrets", "", True, "turrets/extraShipData_turrets"))
        self.ship = player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser")
        self.foe = npc_spawn(2000, 0, 2000, "K01", "raider", "kralien_cruiser",
                             "behav_npcship")

        if self.game_started:
            self.emit("game_started")
        self.console = [k for k in story.labels if k.startswith("console/gamemaster")][0]
        self.open_console()

    def tearDown(self):
        self.emitted.remove()
        ship_data.extra_reset()
        MastScheduler.on_runtime_error = self._orig_rte
        Gui.clients = {}
        Gui.widget_list_sent = {}
        GmPage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        FrameContext.context = None
        SpaceObject.clear()

    def present(self, n=2):
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                           FakeEvent(0, "gui_present"))
            self.server.gui_state = "repaint"
            self.server.present(FakeEvent(0, "gui_present"))
            # The frame's event names the console: gui_sub_task_schedule hosts on
            # FrameContext.client_task, so a server event here would build every menu
            # panel into the SERVER page and leave this one empty.
            FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                           FakeEvent(CID, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(CID, "gui_present"))
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def emit(self, name, data=None):
        """Emit as the server, the way the mission's own flow does."""
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        FrameContext.page = self.server
        FrameContext.task = self.server.story_scheduler.tasks[0]
        signal_emit(name, data or {})
        self.present()

    def open_console(self):
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(CID, "gui_present"))
        gui_reroute_client(CID, self.console)
        self.emitted.clear()
        # The console waits a sim-second before it builds the sidebar.
        self.present(4)
        self.gm = get_inventory_value(CID, "GAMEMASTER_COMBOT", None)

    def click(self, tag):
        """One press, then one tick - the way the engine delivers them."""
        FrameContext.context = Context(mock_sbs.sim, mock_sbs,
                                       FakeEvent(CID, "gui_message"))
        Gui.on_message(FakeEvent(client_id=CID, tag="gui_message", sub_tag=tag))
        self.emitted.clear()
        self.present()

    def press(self, needle, index=0):
        tags = self.emitted.button_named(needle)
        self.assertTrue(tags, f"no '{needle}' button on screen; have "
                              f"{sorted({p for n, _t, p in self.emitted.sent if n == 'send_gui_button'})}")
        self.click(tags[index])

    def open_menu(self, icon_index):
        """Pick a main menu by the icon on its sidebar row."""
        rows = self.emitted.tags("send_gui_icon", f"icon_index: {icon_index};")
        self.assertTrue(rows, f"no sidebar row with icon {icon_index}")
        listbox, row, _ = rows[0].split(":")
        self.click(f"{listbox}:{row}:__click")

    def open_submenu(self, icon_index):
        tabs = self.emitted.tags("send_gui_iconbutton", f"icon_index: {icon_index};")
        self.assertTrue(tabs, f"no submenu tab with icon {icon_index}")
        self.click(tabs[0])

    def open_console_buttons(self):
        """Redraw, so the recorder holds the buttons again after a click cleared it."""
        self.emitted.clear()
        self.present()

    def npcs(self):
        return set(role("__npc__"))

    def terrain(self):
        return set(role("__terrain__"))


# Sidebar icons, from each menu label's `icon_index:`.
SELECTED, SHIPS, FLEETS, STATIONS, COMMS, TERRAIN, MONSTERS, SIDES, SETTINGS = (
    118, 140, 105, 114, 11, 30, 78, 23, 0)
TURRET, NEBULA, PLANET, BLACK_HOLE = 93, 44, 13, 7


class TestConsoleBuilds(_Base):
    def test_the_console_builds(self):
        self.assertIsNotNone(self.gm, "the console never made its camera")
        self.assertTrue(to_object(self.gm).has_role("gamemaster"))
        self.assertTrue(self.emitted.tags("send_gui_icon", f"icon_index: {SHIPS};"))

class TestConsoleBeforeTheGameStarts(_Base):
    game_started = False

    def test_the_console_builds_with_no_mission_clock(self):
        """Nothing starts Mission_Elapsed_Time until game_started is emitted."""
        self.assertIsNotNone(self.gm)


class TestSpawnShips(_Base):
    def test_spawn_with_no_ship_picked_is_not_an_error(self):
        before = self.npcs()
        self.press("`Spawn`")
        self.assertEqual(self.npcs(), before)

    def test_spawn_places_the_picked_ship(self):
        rows = self.emitted.tags("send_gui_text", "$text:Roles: ")
        self.assertTrue(rows, "the ship list drew no rows")
        listbox = rows[0].split(":")[0]
        self.click(f"{listbox}:0:__click")
        before = self.npcs()
        self.open_console_buttons()
        self.press("`Spawn`")
        self.assertEqual(len(self.npcs() - before), 1)


class TestSpawnMenus(_Base):
    def _spawns(self, button, pool):
        before = pool()
        self.press(button)
        self.present(3)
        made = pool() - before
        self.assertTrue(made, f"'{button}' spawned nothing")
        return made

    def test_fleet(self):
        self._spawns("Spawn Fleet", self.npcs)

    def test_station(self):
        made = self._spawns("Spawn Station", self.npcs)
        self.assertTrue(any(to_object(i).has_role("station") for i in made))

    def test_monster(self):
        self._spawns("Spawn Monster", self.npcs)

    def test_asteroids(self):
        self._spawns("Spawn Asteroid", self.terrain)

    def test_nebula(self):
        self._spawns("Spawn Nebula", self.terrain)

    def test_planet(self):
        self._spawns("Spawn Planet", self.terrain)

    def test_black_hole(self):
        self._spawns("Spawn Black Hole", self.terrain)

    def test_turret(self):
        made = self._spawns("Spawn Turret", self.npcs)
        self.assertTrue(any(to_object(i).has_role("turret") for i in made))


class TestTimeLimit(_Base):
    def test_set_extend_and_remove(self):
        self.assertFalse(is_timer_set(Agent.SHARED_ID, "time_limit"))
        self.press("`Time limit`")
        self.assertTrue(is_timer_set(Agent.SHARED_ID, "time_limit"))
        self.press("`+5 min`")
        self.press("`-1 min`")
        self.press("`Remove Time Limit`")
        self.assertFalse(is_timer_set(Agent.SHARED_ID, "time_limit"))


class TestSides(_Base):
    def test_same_side_twice_changes_nothing(self):
        self.press("`Set as Allies`")
        self.assertTrue(side_are_enemies("tsn", "raider"))

    def test_create_side_with_no_key_makes_no_side(self):
        before = set(side_keys_set())
        self.press("`Create Side`")
        self.assertEqual(set(side_keys_set()), before)


class TestComms(_Base):
    def test_send_with_no_origin_is_not_an_error(self):
        self.press("Send to All Ships")
        self.press("`Send to Selected`")


class TestSelectionDetails(_Base):
    def test_details_follow_the_selection(self):
        set_inventory_value(self.gm, "gamemaster_prev_selection", self.foe.id)
        self.emitted.clear()
        self.present()
        self.emit("gui_update_interval_signal")
        self.assertTrue(self.emitted.text_with("K01"),
                        "the details panel never named the selected ship")


class TestMenusKeepTheirOwnSettings(_Base):
    def _settings(self, label):
        return self.story.labels[label].get_inventory_value("settings")["Main"]

    def test_the_asteroid_menu_is_not_the_nebula_menu(self):
        """A menu label with no body falls through into the next one."""
        self.assertNotIn("Color", self._settings("gm_menu_terrain"))
        self.assertIn("Color", self._settings("gm_menu_terrain_nebulae"))

    def test_a_new_side_keeps_each_menu_on_its_own_variable(self):
        side_create("pirate", "Pirate", "")
        self.present(3)
        self.assertIn("pirate", self._settings("gm_menu_spawn_stations")["Side"])
        self.assertIn("STATION_SIDE", self._settings("gm_menu_spawn_stations")["Side"])
        self.assertIn("FLEET_SIDE", self._settings("gm_menu_spawn_fleets")["Side"])


class TestPrefabsOutsideTheConsole(_Base):
    def test_a_planetoid_spawned_the_old_way_is_the_old_size(self):
        """Maps spawn prefab_planetoid with no radius; it has always been 400 across."""
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        FrameContext.page = self.server
        FrameContext.task = self.server.story_scheduler.tasks[0]
        before = self.terrain()
        prefab_spawn(self.story.labels["prefab_planetoid"],
                     {"START_X": 9000, "START_Y": 0, "START_Z": 9000})
        self.present()
        made = [to_object(i) for i in self.terrain() - before]
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0].engine_object.exclusion_radius, 400)


if __name__ == "__main__":
    unittest.main()
