"""Drag to order, driven through the real MAST.

Drag a unit onto something on the comms console and comms opens //comms/orders for that
unit, with the orders that fit the target. This compiles the real drag_orders.mast and
friendly_give_orders.mast, fires the engine's `comms_drag_event`, reads the comms buttons
the engine would be sent, and presses them.

The mock has no drag gesture, so this is the only headless proof the chain holds.
The order labels are stand-ins with the same metadata as prefabs/defender.mast - that file
drags in the whole prefab system, and the menu only reads `type`, `valid_for` and
`display_name`.

    PYTHONPATH=../sbs_utils python -m unittest comms.test_drag_orders
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs
sys.modules.setdefault("sbs", mock_sbs)

COMMS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, COMMS)

from sbs_utils.agent import Agent, clear_shared
from sbs_utils.consoledispatcher import ConsoleDispatcher
from sbs_utils.delete_queue import DeleteQueue
from sbs_utils.dragdispatcher import DragDispatcher
from sbs_utils.gui import Gui
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.mast.mast_globals import MastGlobals
from sbs_utils.mast.maststory import MastStory
from sbs_utils.mast.mastscheduler import MastScheduler
from sbs_utils.mast_sbs import story_nodes  # noqa: F401  (registers route nodes)
from sbs_utils.mast_sbs.maststorypage import StoryPage
from sbs_utils.procedural.links import linked_to
from sbs_utils.procedural.query import to_object, get_comms_selection
from sbs_utils.procedural.science import science_set_scan_data
from sbs_utils.procedural.sides import side_ensure
from sbs_utils.procedural.space_objects import delete_object
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.spaceobject import SpaceObject

import orders

CID = 1

for _n in dir(orders):
    _f = getattr(orders, _n)
    if callable(_f) and not _n.startswith("_") and getattr(_f, "__module__", "") == "orders":
        MastGlobals.import_python_function(_f)

# Imports first so every route registers in main; the park last. The stand-in orders
# follow the park - labels, not main.
HARNESS_STORY = '''import friendly_give_orders.mast
import drag_orders.mast
gui_text("$text:harness;")
await gui()

=== t_order_goto
metadata: ``` yaml
display_name: Head to location
type: objective/orders/defender
valid_for: any
```
+++ test
    yield idle

=== t_order_attack
metadata: ``` yaml
display_name: Attack
type: objective/orders/defender
valid_for: hostile
```
+++ test
    yield idle

=== t_order_escort
metadata: ``` yaml
display_name: Escort
type: objective/orders/defender
valid_for: allies
```
+++ test
    yield idle

=== t_order_stop
metadata: ``` yaml
display_name: Full Stop
type: objective/orders/defender
valid_for: self
```
+++ test
    yield idle
'''


# The library's own console handlers (comms, science, popups) are registered once, at
# import. reset_mission_state() drops them along with the per-story routes, so keep the
# plain-function ones and put them back after each reset. Route handlers are bound
# methods of a Handle* object and are deliberately NOT kept - those are what leak.
def _library_defaults(table):
    return {k: [cb for cb in v if not hasattr(cb, "__self__")]
            for k, v in table.items() if k[0] == 0 and isinstance(v, list)}


import sbs_utils.procedural.comms, sbs_utils.procedural.science, sbs_utils.procedural.popup  # noqa: E401,F401
_SELECT_DEFAULTS = _library_defaults(ConsoleDispatcher._dispatch_select)
_MESSAGE_DEFAULTS = _library_defaults(ConsoleDispatcher._dispatch_messages)


class OrdersPage(StoryPage):
    story = None


class _Comms:
    """What the engine's comms console is sent."""

    def __init__(self):
        self.buttons = []     # (ship, text, tag)
        self.messages = []    # comms_receive text

    def install(self):
        self._orig_btn = mock_sbs.send_comms_button_info
        self._orig_clr = mock_sbs.send_comms_selection_info
        mock_sbs.send_comms_button_info = lambda ship, color, text, tag: self.buttons.append((ship, text, tag))
        # A selection send clears the console's buttons before the new set arrives
        mock_sbs.send_comms_selection_info = lambda ship, face, color, title: self.buttons.clear()

    def remove(self):
        mock_sbs.send_comms_button_info = self._orig_btn
        mock_sbs.send_comms_selection_info = self._orig_clr

    def texts(self):
        return [t for _s, t, _g in self.buttons]

    def tag_of(self, needle):
        for _s, text, tag in self.buttons:
            if needle in text:
                return tag
        raise AssertionError(f"no comms button containing {needle!r}: {self.texts()}")


class DragOrdersBase(unittest.TestCase):
    def setUp(self):
        # Every route a compile registers (//focus/comms, //drag/comms, ...) lives in a
        # dispatcher, not in the story - so the PREVIOUS test's routes still answer, and
        # jump into a story that no longer exists. A mission reload clears them; so do we.
        from sbs_utils.handlerhooks import reset_mission_state
        reset_mission_state()
        for k, v in _SELECT_DEFAULTS.items():
            ConsoleDispatcher._dispatch_select[k] = list(v)
        for k, v in _MESSAGE_DEFAULTS.items():
            ConsoleDispatcher._dispatch_messages[k] = list(v)
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        DeleteQueue.clear()
        clear_shared()
        SpaceObject.clear()
        DragDispatcher.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        Agent.SHARED.set_inventory_value("sim", mock_sbs.sim)
        side_ensure("tsn")
        side_ensure("klingon")

        self.comms = _Comms()
        self.comms.install()
        self.addCleanup(self.comms.remove)

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append

        story = MastStory()
        story.basedir = COMMS
        errors = story.compile(HARNESS_STORY, "dragharness", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        OrdersPage.story = story
        FrameContext.mast = story

        self.ship = to_object(player_spawn(0, 0, 0, "Hero", "tsn", "tsn_light_cruiser"))
        self.unit = to_object(npc_spawn(1000, 0, 0, "Unit", "tsn", "tsn_light_cruiser", "behav_npcship"))
        self.buddy = to_object(npc_spawn(2000, 0, 0, "Buddy", "tsn", "tsn_light_cruiser", "behav_npcship"))
        self.foe = to_object(npc_spawn(3000, 0, 0, "Foe", "klingon", "tsn_light_cruiser", "behav_npcship"))
        mock_sbs.assign_client_to_ship(CID, self.ship.id)
        # Comms sends NO buttons for a contact the side has not scanned ("unknown") - that
        # is comms, not the drag. A crew ordering a unit has identified it.
        for who in (self.unit, self.buddy, self.foe):
            science_set_scan_data(self.ship, who, "identified")

        self.server = OrdersPage()
        Gui.push(0, self.server)
        self.page = OrdersPage()
        Gui.push(CID, self.page)
        self.present()

    def tearDown(self):
        MastScheduler.on_runtime_error = self._orig_rte
        DragDispatcher.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        OrdersPage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        FrameContext.context = None
        SpaceObject.clear()

    def present(self, n=2):
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "gui_present"))
            self.server.gui_state = "repaint"
            self.server.present(FakeEvent(0, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(CID, "gui_present"))
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    def drag(self, source, target):
        ev = FakeEvent(client_id=CID, tag="comms_drag_event",
                       origin_id=source.id if source else 0,
                       selected_id=target.id if target else 0,
                       parent_id=self.ship.id)
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, ev)
        DragDispatcher.dispatch_comms(ev)
        self.present()

    def press(self, needle):
        tag = self.comms.tag_of(needle)
        ev = FakeEvent(client_id=CID, tag="press_comms_button", sub_tag=tag,
                       origin_id=self.ship.id, selected_id=self.unit.id)
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, ev)
        ConsoleDispatcher.dispatch_message(ev, "comms_target_UID")
        self.present()

    def objectives(self, who):
        return [to_object(o).label.name for o in linked_to(who.id, "OBJECTIVE")
                if to_object(o) is not None]


class TestTheMenu(DragOrdersBase):

    def test_A_DRAG_OPENS_ORDERS_ON_THE_UNIT(self):
        self.drag(self.unit, self.foe)
        self.assertEqual(self.unit.id, get_comms_selection(self.ship.id),
                         "comms did not select the unit being ordered")
        self.assertIn("Attack: Foe", self.comms.texts())
        self.assertIn("Back", self.comms.texts())

    def test_a_hostile_target_offers_hostile_orders_only(self):
        self.drag(self.unit, self.foe)
        texts = self.comms.texts()
        self.assertIn("Head to location: Foe", texts)
        self.assertNotIn("Escort: Foe", texts)
        self.assertFalse([t for t in texts if "Full Stop" in t])

    def test_a_friendly_target_offers_ally_orders(self):
        self.drag(self.unit, self.buddy)
        texts = self.comms.texts()
        self.assertIn("Escort: Buddy", texts)
        self.assertNotIn("Attack: Buddy", texts)

    def test_dropped_on_itself_offers_the_self_orders(self):
        self.drag(self.unit, self.unit)
        texts = self.comms.texts()
        self.assertIn("Full Stop", texts)
        self.assertFalse([t for t in texts if "Attack" in t or "Escort" in t])

    def test_a_unit_that_cannot_take_orders_opens_nothing(self):
        self.drag(self.foe, self.unit)
        self.assertNotEqual(self.foe.id, get_comms_selection(self.ship.id))
        self.assertEqual(0, orders.lm_drag_orders_target(self.ship.id, self.foe.id))

    def test_a_drop_on_empty_space_opens_nothing(self):
        self.drag(self.unit, None)
        self.assertEqual(0, orders.lm_drag_orders_target(self.ship.id, self.unit.id))
        self.assertFalse([t for t in self.comms.texts() if "Attack" in t])


class TestGivingTheOrder(DragOrdersBase):

    def test_THE_ORDER_IS_GIVEN_WITH_THE_TARGET(self):
        self.drag(self.unit, self.foe)
        self.press("Attack: Foe")
        self.assertEqual(["t_order_attack"], self.objectives(self.unit))
        obj = to_object(linked_to(self.unit.id, "OBJECTIVE").pop())
        self.assertEqual(self.foe.id, obj.data["objective_target"])

    def test_the_pending_record_is_spent(self):
        self.drag(self.unit, self.foe)
        self.press("Attack: Foe")
        self.assertEqual(0, orders.lm_drag_orders_target(self.ship.id, self.unit.id))

    def test_A_TARGET_GONE_BEFORE_THE_PRESS_GIVES_NO_ORDER(self):
        """The menu was built while the target lived; it died before the button was
        pressed. No order - the unit must not be sent after something that is not there."""
        self.drag(self.unit, self.foe)
        tag = self.comms.tag_of("Attack: Foe")
        delete_object(self.foe.id)
        ev = FakeEvent(client_id=CID, tag="press_comms_button", sub_tag=tag,
                       origin_id=self.ship.id, selected_id=self.unit.id)
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, ev)
        ConsoleDispatcher.dispatch_message(ev, "comms_target_UID")
        self.present()
        self.assertEqual([], self.objectives(self.unit))
        self.assertEqual(0, orders.lm_drag_orders_target(self.ship.id, self.unit.id))


if __name__ == "__main__":
    unittest.main()
