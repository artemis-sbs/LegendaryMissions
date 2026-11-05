"""The Follow checkbox on Comms and (stock) Science reaches the script.

THE FIELD REPORT: "the comms follow check box doesn't do anything - it is always in
follow mode". The console route ends after its build, taking the task that owns
`follow_tag` with it, so the checkbox's var write landed nowhere: the box flipped, the
`2d_follow` inventory flag never did, and `on change follow_tag` never fired.

    PYTHONPATH=../../sbs_utils python -m unittest consoles.test_follow_checkbox
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import unittest

from test_console_tab_widget_rects import (_Base, CID, FrameContext, Context, FakeEvent,
                                           mock_sbs)
from sbs_utils.pages.layout.checkbox import Checkbox
from sbs_utils.procedural.inventory import get_inventory_value
from sbs_utils.procedural.spawn import npc_spawn
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.routes import follow_route_select_comms


def _walk(item, seen=None):
    seen = seen if seen is not None else set()
    if id(item) in seen:
        return
    seen.add(id(item))
    yield item
    for attr in ("rows", "columns", "layouts"):
        for child in getattr(item, attr, []) or []:
            yield from _walk(child, seen)


class _FollowMixin:
    SELECT = None

    def _box(self):
        boxes = [i for s in self.page.layouts for i in _walk(s)
                 if isinstance(i, Checkbox) and "Follow" in str(i.message)]
        self.assertEqual(len(boxes), 1, "expected exactly one Follow checkbox")
        return boxes[0]

    def _click(self, box):
        ev = FakeEvent(CID, "gui_message", sub_tag=box.tag)
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, ev)
        self.page.on_message(ev)
        self.present(2)

    def test_the_checkbox_sets_the_flag_and_refocuses(self):
        calls = []
        orig = mock_sbs.assign_client_to_alt_ship

        def spy(cid, sid):
            calls.append((cid, sid))
            return orig(cid, sid)
        mock_sbs.assign_client_to_alt_ship = spy
        try:
            self.enter("harness_console")
            npc = to_object(npc_spawn(2000, 0, 0, "Target", "raider", "tsn_light_cruiser",
                                      "behav_npcship"))
            FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(CID, "gui_present"))
            if self.SELECT is not None:
                self.SELECT(self.ship.id, npc.id)
                self.present(2)
            box = self._box()
            start = bool(box.value)
            self._click(box)
            self.assertEqual(bool(get_inventory_value(CID, "2d_follow")), not start,
                             "clicking the box did not reach the 2d_follow flag")
            self._click(box)
            self.assertEqual(bool(get_inventory_value(CID, "2d_follow")), start)
            if self.SELECT is not None:
                self.assertTrue(any(c == (CID, npc.id) for c in calls) or not start,
                                f"turning Follow on never pointed the view at the contact: {calls}")
        finally:
            mock_sbs.assign_client_to_alt_ship = orig


class TestCommsFollow(_FollowMixin, _Base):
    CONSOLE = "comms"
    SELECT = staticmethod(follow_route_select_comms)


class TestScienceFollow(_FollowMixin, _Base):
    CONSOLE = "science"
    # No selection: this harness does not load the //focus/science route's own helpers, and
    # the flag is what is under test. The comms case covers the re-point.
    SELECT = None


if __name__ == "__main__":
    unittest.main()
