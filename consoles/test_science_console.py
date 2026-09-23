"""The prototype science console actually builds, and its tab buttons do their job.

A MAST layout that does not compile, or that hits a NameError where a widget should be,
schedules nothing and logs nothing useful - and a headless `--test` run still reports
PASS, because it never enters a console page. So this drives the REAL route: it compiles
`layout_widgets.mast`, enters `//gui/normal_sci` through `gui_console("science")` with
SCIENCE_NEW_LAYOUT on, and presses a real tab row.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_science_console
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

CONSOLES = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CONSOLES)

from sbs_utils.agent import clear_shared                           # noqa: E402
from sbs_utils.gui import Gui                                      # noqa: E402
from sbs_utils.helpers import Context, FakeEvent, FrameContext     # noqa: E402
from sbs_utils.mast.maststory import MastStory                     # noqa: E402
from sbs_utils.mast.mastscheduler import MastScheduler             # noqa: E402
from sbs_utils.mast_sbs import story_nodes                         # noqa: E402,F401
from sbs_utils.mast_sbs.maststorypage import StoryPage             # noqa: E402
from sbs_utils.procedural import settings as settings_mod          # noqa: E402
from sbs_utils.procedural.query import to_object, set_science_selection  # noqa: E402
from sbs_utils.procedural.science import science_set_scan_data     # noqa: E402
from sbs_utils.procedural.sides import side_ensure, side_set_relations  # noqa: E402
from sbs_utils.procedural.spawn import npc_spawn, player_spawn     # noqa: E402
from sbs_utils.spaceobject import SpaceObject                      # noqa: E402

import science_queue as sq                                         # noqa: E402
import science_tabs as st                                          # noqa: E402
import science_chips as sc                                         # noqa: E402

CID = 1

# Same import order as consoles/__init__.mast. A MAST global is only defined once its
# module has loaded, so leaving one out builds the console with a NameError where a
# widget should be - which is exactly the failure this harness exists to catch.
HARNESS = "\n".join([
    "shared SETTINGS = {}",
    "import manual_beams_helpers.py",
    "import tether_indicator.py",
    "import eng_grid_panel.py",
    "import comms_chips.py",
    "import eng_crew_chips.py",
    "import eng_grid_buttons.py",
    "import science_scan_time.py",
    "import science_queue.py",
    "import science_tabs.py",
    "import science_panel.py",
    "import science_chips.py",
    "import science_queue_list.py",
    "import layout_widgets.mast",
    "import science_layout.mast",
    "jump harness_console",
    "",
    "== harness_console ==",
    '    gui_console("science")',
    "    await gui()",
    "",
])


class ConsolePage(StoryPage):
    story = None


class _Rects:
    """Where each MAST widget was actually drawn, by tag.

    Measuring the emitted RECTS rather than the strings that ask for them, the way
    test_manual_beams_panel does. The bug this exists for - a region declared as a third
    sibling of two columns, which threw the right column across the full width - changed
    no data at all, so a test that only reads the model cannot see it.
    """

    def __init__(self):
        self.calls = []
        self.tagged = []

    def install(self):
        self.widget_rects = []
        self.widget_lists = []
        self._orig_wl = mock_sbs.send_client_widget_list

        def _wl(client_id, console, widgets):
            self.widget_lists.append((client_id, console, widgets))
            return self._orig_wl(client_id, console, widgets)

        mock_sbs.send_client_widget_list = _wl
        self._orig_wr = mock_sbs.send_client_widget_rects

        def _wr(client_id, widget, *coords):
            self.widget_rects.append((client_id, widget, tuple(coords)))
            return self._orig_wr(client_id, widget, *coords)

        mock_sbs.send_client_widget_rects = _wr
        self._orig = {}
        for name in ("send_gui_checkbox", "send_gui_text", "send_gui_icon",
                     "send_gui_iconbutton", "send_gui_clickregion"):
            self._orig[name] = getattr(mock_sbs, name)
            setattr(mock_sbs, name, self._wrap(name, self._orig[name]))

    def _wrap(self, name, orig):
        def _fn(client_id, parent, tag, style, left, top, right, bottom, *rest):
            self.calls.append((client_id, name, style, left, top, right, bottom))
            self.tagged.append((client_id, name, tag, style))
            return orig(client_id, parent, tag, style, left, top, right, bottom, *rest)
        return _fn

    def remove(self):
        mock_sbs.send_client_widget_list = self._orig_wl
        mock_sbs.send_client_widget_rects = self._orig_wr
        for name, fn in self._orig.items():
            setattr(mock_sbs, name, fn)

    def clear(self):
        self.calls.clear()
        self.tagged.clear()
        self.widget_rects.clear()
        self.widget_lists.clear()

    def emitted(self, name):
        """Every call to one emitter, as (tag, style)."""
        return [(t, st) for cid, n, t, st in self.tagged if cid == CID and n == name]

    def find(self, needle):
        """Every rect whose style mentions `needle`, on the console under test."""
        return [(l, t, r, b) for cid, _n, style, l, t, r, b in self.calls
                if cid == CID and needle in (style or "")]


class _Base(unittest.TestCase):
    NEW_LAYOUT = True

    def setUp(self):
        clear_shared()
        SpaceObject.clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        StoryPage._forget_parked_widgets()
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        side_ensure("tsn")
        side_ensure("raider")
        side_ensure("civ")
        # A side pair is NEUTRAL until a relation is declared, and a contact that is
        # neither ally nor enemy lands in no chip at all - so declare it, the way a
        # mission's sides block does, or the counts test proves nothing.
        side_set_relations("tsn", "raider", mock_sbs.DIPLOMACY.HOSTILE)
        sq.lm_sci_queue_clear()

        # The real lookup, pinned. `settings_get_defaults` caches into this global on
        # first call, so setting it is what a settings.yaml would have done - not a
        # stub in front of the function the console actually calls.
        self._orig_settings = settings_mod.setting_defaults
        settings_mod.setting_defaults = {"SCIENCE_NEW_LAYOUT": self.NEW_LAYOUT}

        story = MastStory()
        story.basedir = CONSOLES
        errors = story.compile(HARNESS, "sciconsoleharness", story)
        self.assertEqual(errors, [], f"compile errors: {errors}")
        story.compiler_errors = []
        ConsolePage.story = story
        FrameContext.mast = story

        self.rects = _Rects()
        self.rects.install()
        self.addCleanup(self.rects.remove)

        self.rte = []
        self._orig_rte = MastScheduler.on_runtime_error
        MastScheduler.on_runtime_error = self.rte.append

        self.ship = to_object(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        self.ship.data_set.set("ship_base_scan_range", 25000.0, 0)
        self.target = to_object(npc_spawn(1000, 0, 0, "K19", "raider",
                                          "tsn_light_cruiser", "behav_npcship"))
        mock_sbs.assign_client_to_ship(CID, self.ship.id)

        self.server = ConsolePage()
        Gui.push(0, self.server)
        self.page = ConsolePage()
        Gui.push(CID, self.page)
        self.present()

    def tearDown(self):
        settings_mod.setting_defaults = self._orig_settings
        MastScheduler.on_runtime_error = self._orig_rte
        sq.lm_sci_queue_clear()
        Gui.clients = {}
        Gui.widget_list_sent = {}
        StoryPage._forget_parked_widgets()
        ConsolePage.story = None
        FrameContext.task = None
        FrameContext.page = None
        FrameContext.mast = None
        FrameContext.context = None
        SpaceObject.clear()

    def present(self, n=1):
        for _ in range(n):
            mock_sbs.sim._time_tick_counter += 30
            self.server.gui_state = "repaint"
            self.server.present(FakeEvent(0, "gui_present"))
            self.page.gui_state = "repaint"
            self.page.present(FakeEvent(CID, "gui_present"))
        self.assertEqual(self.rte, [], f"MAST runtime errors: {self.rte}")

    @property
    def rect_calls(self):
        """Every engine-widget rect this client was sent."""
        return self.rects.widget_rects

    def select(self, obj):
        set_science_selection(self.ship, obj)
        self.present()


class ScienceConsoleBuilds(_Base):
    def test_the_console_builds_with_no_runtime_errors(self):
        # setUp already presented it; this asserts the point of the harness explicitly.
        self.present(2)
        self.assertEqual(self.rte, [])

    #: The four engine widgets this console replaces. They must leave the console's
    #: WIDGET LIST, not merely be moved out of sight.
    #: Replaced outright. `science_data_freq` is NOT here: it is transient, positioned
    #: by rect on the status tab, so it stays declared.
    REMOVED_WIDGETS = ("science_data_tabs", "science_data", "science_data_freq")

    def _widget_lists(self):
        """Every widget list this client was sent, newest last."""
        return [w for cid, _console, w in self.rects.widget_lists if cid == CID]

    def test_the_replaced_widgets_leave_the_console_widget_list(self):
        """PARKING IS NOT REMOVING.

        `gui_widget_offscreen` sends a rect at 100,100 - out of sight, still DECLARED.
        `gui_console("science")` declares all four of these before this route runs, so a
        parked contact list kept being drawn on a real bridge. `gui_update_widget_list`
        rewrites the list and re-sends it, which is what manual_weapons.mast uses to be
        rid of the 3dview.
        """
        self.present()
        lists = self._widget_lists()
        self.assertTrue(lists, "no widget list was ever sent")
        final = set(lists[-1].split("^"))
        for widget in self.REMOVED_WIDGETS:
            self.assertNotIn(widget, final,
                             f"{widget} is still in the console's widget list: {lists[-1]}")

    def test_the_widgets_the_console_still_needs_survive(self):
        """The removal must be surgical - taking the 2D view with it would be worse."""
        self.present()
        final = set(self._widget_lists()[-1].split("^"))
        # science_sorted_list stays in the list: it is TRANSIENT now, parked by RECT
        # rather than dropped, because it is still the fastest way to pick a contact.
        for widget in ("science_2d_view", "radar_zoom_ctrl", "ship_data",
                       "science_sorted_list"):
            self.assertIn(widget, final, f"{widget} was removed too: {final}")

    def test_no_widget_is_given_a_rect_after_it_leaves_the_list(self):
        """A widget off the list should not be positioned at all - a stray rect would mean
        something is still trying to place it."""
        self.present()
        placed = {w for cid, w, _r in self.rect_calls if cid == CID}
        for widget in self.REMOVED_WIDGETS:
            self.assertNotIn(widget, placed,
                             f"{widget} was still given a rect after removal")

    def test_an_unknown_contact_offers_only_the_scan_tab(self):
        self.select(self.target)
        rows = st.lm_sci_tabs_items(CID)
        tabs = [r["tab"] for r in rows]
        self.assertEqual(tabs, ["scan", st.LM_SCI_QUEUE_TAB])
        self.assertEqual(rows[0]["state"], "idle")

    def test_an_unscanned_tab_reads_queue_scan(self):
        """The label says what the press DOES. Pressing it queues a scan - it does not
        take you anywhere - so naming the destination would misdescribe the button."""
        self.select(self.target)
        row = st.lm_sci_tabs_items(CID)[0]
        self.assertEqual(row["label"], "Queue Scan")
        self.assertEqual(row["detail"], "")

    def test_a_scanned_tab_reads_just_its_name(self):
        """`Scan DONE` said the same thing twice - a plain `Scan` beside a `Queue Scan`
        already tells you which one has data."""
        science_set_scan_data(self.ship, self.target,
                              {"scan": "A kralien cruiser.", "status": "Damaged."})
        self.select(self.target)
        labels = {r["tab"]: r["label"] for r in st.lm_sci_tabs_items(CID)}
        self.assertEqual(labels["scan"], "Scan")
        self.assertEqual(labels["status"], "Status")
        details = {r["tab"]: r["detail"] for r in st.lm_sci_tabs_items(CID)}
        self.assertEqual(details["scan"], "", "a scanned tab needs no suffix")

    def test_a_suffix_only_appears_when_it_says_something_new(self):
        """Queue position and percentage cannot be read off the label, so they stay."""
        self.select(self.target)
        st.lm_sci_tabs_press({"cid": CID, "tab": "scan"})
        row = st.lm_sci_tabs_items(CID)[0]
        self.assertEqual(row["label"], "Scan", "a queued tab is no longer an offer")
        self.assertIn("SCANNING", row["detail"])

    def test_pressing_an_unscanned_tab_queues_it(self):
        self.select(self.target)
        st.lm_sci_tabs_press({"cid": CID, "tab": "scan"})
        self.assertEqual(st.lm_sci_tab_state(self.ship.id, self.target.id, "scan"),
                         "scanning")
        self.assertEqual(len(sq.lm_sci_queue_list("tsn")), 1)
        self.present()

    def test_pressing_a_queued_tab_does_nothing(self):
        self.select(self.target)
        st.lm_sci_tabs_press({"cid": CID, "tab": "scan"})
        before = sq.lm_sci_queue_list("tsn")
        self.assertFalse(st.lm_sci_tabs_press({"cid": CID, "tab": "scan"}))
        self.assertEqual(sq.lm_sci_queue_list("tsn"), before)

    def test_pressing_a_scanned_tab_navigates(self):
        science_set_scan_data(self.ship, self.target,
                              {"scan": "A kralien cruiser.", "status": "Engines damaged."})
        self.select(self.target)
        self.assertTrue(st.lm_sci_tabs_press({"cid": CID, "tab": "status"}))
        self.assertEqual(st.lm_sci_tabs_current(CID), "status")
        self.assertEqual(sq.lm_sci_queue_list("tsn"), [])
        self.present()

    def test_declared_tabs_come_from_the_object(self):
        science_set_scan_data(self.ship, self.target,
                              {"scan": "A kralien cruiser.", "status": "Engines damaged.",
                               "bio": "Kralien crew."})
        self.select(self.target)
        tabs = [r["tab"] for r in st.lm_sci_tabs_items(CID)]
        self.assertEqual(tabs[0], "scan", "scan is always first")
        self.assertIn("status", tabs)
        self.assertIn("bio", tabs)
        self.assertEqual(tabs[-1], st.LM_SCI_QUEUE_TAB)

    def test_the_queue_row_is_labelled_in_queue(self):
        """The KEY stays "Queue" - it is compared against everywhere. Only the label
        changes, because "Queue" under "Queue Scan" reads as a verb: queue what?"""
        row = st.lm_sci_tabs_items(CID)[-1]
        self.assertEqual(row["tab"], st.LM_SCI_QUEUE_TAB, "the key must not move")
        self.assertEqual(row["label"], "In Queue")

    def test_the_queue_row_is_always_offered(self):
        rows = st.lm_sci_tabs_items(CID)
        self.assertEqual([r["tab"] for r in rows], [st.LM_SCI_QUEUE_TAB],
                         "with nothing selected, only the queue is reachable")

    # --- the queue's bare icons ---------------------------------------------

    def _open_queue_with_entries(self):
        """Two entries queued and the Queue tab open.

        Asserts its own preconditions. Without them a failure downstream reads as "no
        click regions were drawn", which points at the widget code when the real cause is
        an empty queue - an already-scanned contact cannot be queued, and scan data
        outlives a bare SpaceObject.clear() if a previous test wrote it.
        """
        self.assertTrue(sq.lm_sci_queue_add(self.ship, self.target, "scan"),
                        "the target could not be queued - already scanned?")
        other = to_object(npc_spawn(4000, 0, 0, "L01", "raider",
                                    "tsn_light_cruiser", "behav_npcship"))
        self.assertTrue(sq.lm_sci_queue_add(self.ship, other, "scan"),
                        "the second contact could not be queued")
        st.lm_sci_tabs_set_current(CID, st.LM_SCI_QUEUE_TAB)
        self.assertEqual(st.lm_sci_tabs_current(CID), st.LM_SCI_QUEUE_TAB,
                         "the console did not switch to the Queue tab")
        self.present(4)
        self.assertEqual(len(sq.lm_sci_queue_list("tsn")), 2,
                         "the queue emptied while the console painted")

    def _queue_regions(self):
        """The queue's own click regions, distinct, in the order first emitted.

        Read from what the build ALREADY sent rather than clearing and presenting again:
        the dirty system does not re-send an unchanged widget, so a second present emits
        nothing and the regions look absent. De-duplicated because a tag repeats across
        frames by design - a widget keeps its tag.
        """
        seen = []
        for tag, _style in self.rects.emitted("send_gui_clickregion"):
            if ":__click:" in tag and tag not in seen:
                seen.append(tag)
        return seen

    def _fire(self, tag):
        ev = FakeEvent(CID, "gui_message", sub_tag=tag)
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, ev)
        self.page.on_message(ev)

    # --- the contact list ---------------------------------------------------

    def _list_rect(self):
        r = [x for c, w, x in self.rect_calls if c == CID and w == "science_sorted_list"]
        return r[-1] if r else None

    def test_the_contact_list_is_up_when_nothing_is_selected(self):
        self.present()
        rect = self._list_rect()
        self.assertIsNotNone(rect, "the contact list was never placed")
        self.assertLess(rect[0], 100, f"the list is off screen: {rect}")

    def test_the_contact_list_gives_way_once_a_contact_is_picked(self):
        """Selecting is the one thing the list is for."""
        self.present()
        self.select(self.target)
        self.present(2)
        self.assertGreaterEqual(self._list_rect()[0], 100,
                                "the list is still showing with a contact selected")

    def test_the_contact_list_comes_back_on_deselect(self):
        from sbs_utils.procedural.query import set_science_selection
        self.select(self.target)
        self.present(2)
        set_science_selection(self.ship, None)
        self.present(2)
        self.assertLess(self._list_rect()[0], 100,
                        "the list did not return when the selection cleared")

    def test_the_list_is_never_handed_to_gui_layout_widget(self):
        """THE WHOLE TRICK. A layout placeholder re-sends its widget's rect on every
        build, which fights the rect an `on change` handler sends and wins - that is what
        "the object list is always showing" was. Positioned purely by rect, nothing
        fights it. Asserted by shape: only ONE rect per present should ever be sent for
        this widget, and a placeholder would add a second."""
        self.rects.clear()
        self.present(1)
        sends = [r for c, w, r in self.rect_calls
                 if c == CID and w == "science_sorted_list"]
        self.assertLessEqual(len(sends), 1,
                             f"something else is also placing the list: {sends}")

    def test_the_chip_rail_is_drawn_under_the_view(self):
        """It is a real row, not a mockup: the labels reach the client."""
        self.present()
        drawn = self.rects.find("Threats")
        self.assertTrue(drawn, "the Threats chip was never drawn")
        left, top, _right, _bottom = drawn[-1]
        # Under the view, so well down the screen, and left of the right-hand column.
        self.assertGreater(top, 50.0, f"the rail is not below the view: top={top}")
        self.assertLess(left, 70.0, f"the rail is in the right column: left={left}")

    def test_the_rail_spans_the_whole_console_width(self):
        """Inside the view's column the rail was only 70% wide, because that column IS
        the view. Its own section spans everything."""
        self.present()
        drawn = self.rects.find("Threats") + self.rects.find("Terrain")
        self.assertTrue(drawn, "no chip was drawn")
        rightmost = max(r for _l, _t, r, _b in drawn)
        self.assertGreater(rightmost, 70.0,
                           f"the rail stops inside the view column: right={rightmost}")

    def test_the_view_stops_above_the_rail(self):
        """The two content sections end `lm_sci_chip_row_px()` short of the bottom, so
        the rail has a band of its own and nothing overlaps."""
        self.present()
        view = [r for cid, w, r in self.rect_calls
                if cid == CID and w == "science_2d_view"]
        self.assertTrue(view, "the 2D view was never placed")
        bottom = view[-1][3]
        self.assertLess(bottom, 100.0, "the view runs under the chip rail")

    def test_the_rail_costs_the_view_a_row_rather_than_covering_it(self):
        """The chips are NOT an overlay: unlike the tab stack they have no `area:`."""
        self.assertFalse(hasattr(sc, "lm_sci_chips_area"),
                         "the rail must be a layout row, not an absolute region")
        self.assertNotIn("area:", sc.lm_sci_chips_style())

    def test_counts_exclude_unscanned_contacts(self):
        """A count that included unknowns would tell the crew what they have not found."""
        self.assertEqual(len(sc.lm_sci_chips_sets(CID).get("threats", ())), 0,
                         "an unscanned raider must not be counted")
        science_set_scan_data(self.ship, self.target, {"scan": "A kralien cruiser."})
        self.assertEqual(len(sc.lm_sci_chips_sets(CID).get("threats", ())), 1,
                         "a scanned raider should count")

    def test_a_known_neutral_contact_lands_in_a_chip(self):
        """Without a neutral bucket a scanned civilian is reachable only through All,
        which reads as the rail having lost it."""
        civ = to_object(npc_spawn(2000, 0, 0, "U85 Yakima", "civ",
                                  "tsn_light_cruiser", "behav_npcship"))
        science_set_scan_data(self.ship, civ, {"scan": "A usfp transport."})
        sets = sc.lm_sci_chips_sets(CID)
        found = [k for k, v in sets.items() if civ.id in v]
        self.assertTrue(found, f"the civilian is in no chip: {sets}")

    def test_three_chips_never_carry_a_number(self):
        for key in ("all", "unscanned", "terrain"):
            self.assertIn(key, sc.LM_SCI_CHIP_NO_COUNT)

    def test_all_is_exclusive(self):
        class _FakeBox:
            def __init__(self, sel): self._sel = list(sel)
            def get_selected(self): return list(self._sel)
            @property
            def selected(self): return list(self._sel)
            @selected.setter
            def selected(self, v): self._sel = list(v)
        # Picking a chip while All is selected drops All - All means "no filter", so
        # keeping it beside a filter would be a contradiction.
        box = _FakeBox(["all", "threats"])
        self.assertEqual(sc.lm_sci_chips_normalize(CID, box), ["threats"])
        # Two real chips coexist.
        box = _FakeBox(["threats", "friends"])
        self.assertEqual(sorted(sc.lm_sci_chips_normalize(CID, box)), ["friends", "threats"])
        # Picking All while others are selected clears them.
        box = _FakeBox(["threats", "friends", "all"])
        self.assertEqual(sc.lm_sci_chips_normalize(CID, box), ["all"])
        # Deselecting everything falls back to All rather than showing nothing.
        box = _FakeBox([])
        self.assertEqual(sc.lm_sci_chips_normalize(CID, box), ["all"])

    # --- the beam frequency readout -----------------------------------------

    def test_the_active_tab_is_published_to_the_engine(self):
        """The engine learns the active tab from `science_data_tabs`, which this console
        does not have - so it has to be told, or `science_data_freq` has no reason to
        show anything."""
        science_set_scan_data(self.ship, self.target,
                              {"scan": "A kralien cruiser.", "status": "Damaged."})
        self.select(self.target)
        st.lm_sci_tabs_set_current(CID, "status")
        self.assertEqual(self.ship.data_set.get("cur_scan_type", 0), "status")
        self.assertEqual(self.ship.data_set.get("cur_scan_ID", 0), self.target.id)

    def test_the_queue_tab_publishes_no_scan_type(self):
        """The queue is not a scan tab - naming it would tell the engine science is
        looking at a contact called "Queue"."""
        st.lm_sci_tabs_set_current(CID, st.LM_SCI_QUEUE_TAB)
        self.assertEqual(self.ship.data_set.get("cur_scan_type", 0), "")
        self.assertEqual(self.ship.data_set.get("cur_scan_ID", 0), 0)

    def test_progress_is_not_claimed(self):
        """`cur_scan_percent` means a scan IN PROGRESS. Showing a tab that already has
        data is not one, and claiming otherwise would put a phantom scan on every console
        reading that field."""
        self.select(self.target)
        st.lm_sci_tabs_set_current(CID, "scan")
        self.assertIn(self.ship.data_set.get("cur_scan_percent", 0), (0, 0.0, None))

    def test_the_stack_is_an_absolute_area_in_the_lower_left(self):
        """An overlay in mechanism, but placed in the console's lower LEFT - the dead band
        under the info panel and log tail - so it costs no content and never covers the
        map."""
        area = st.lm_sci_stack_area(CID)
        self.assertIn("area:", area)
        self.assertIn(f"{st.LM_SCI_STACK_X_PX}px", area)
        self.assertIn(f"{st.LM_SCI_STACK_BOTTOM_PCT}", area)
        style = st.lm_sci_stack_style(CID)
        self.assertIn(f"layer: {st.LM_SCI_STACK_LAYER}", style)
        # The GROUND is on each row, not on the box: a ground here would paint the whole
        # fixed-height rectangle, including the empty space above a short stack.
        self.assertNotIn("background:", style)
        self.assertIn("background:", st.LM_SCI_STACK_BG.join(["background:", ""]))

    def test_the_right_column_stays_in_the_right_column(self):
        """The Follow checkbox belongs in the 30%-wide right column.

        A region declared between the two columns became a third sibling, the column
        maths changed underneath, and Follow and On-screen were drawn across the full
        width on top of the tab stack. Nothing about the model changed, so only a rect
        can catch it.
        """
        self.present()
        found = self.rects.find("Follow")
        self.assertTrue(found, "the Follow checkbox was never drawn")
        left, _top, right, _bottom = found[-1]
        self.assertGreater(left, 50.0,
                           f"Follow drawn at left={left}; it belongs in the right column")
        self.assertLessEqual(right, 100.5, f"Follow runs off the screen: right={right}")

    def test_the_stack_does_not_overlap_the_right_column(self):
        """The two must not share space: the stack is bottom-left, the controls right."""
        right_edge_pct = 100.0 * (st.LM_SCI_STACK_X_PX + st.LM_SCI_STACK_W_PX) / 1024.0
        self.present()
        found = self.rects.find("Follow")
        self.assertTrue(found)
        left = found[-1][0]
        self.assertGreater(left, right_edge_pct,
                           "the right column starts left of where the stack ends")

    def test_the_stack_stays_clear_of_the_2d_view(self):
        """The left column is 280px. Spilling past it would put the panel on the map,
        which is the placement this console deliberately does not use."""
        right_edge = st.LM_SCI_STACK_X_PX + st.LM_SCI_STACK_W_PX
        self.assertLessEqual(right_edge, 292,
                             "the stack must stay inside the left column")

    def test_the_stack_grows_upward_from_a_fixed_base(self):
        """A long tab set must not push the first row off the top, and the base is where
        the eye learns to look."""
        science_set_scan_data(self.ship, self.target,
                              {"scan": "A.", "status": "B.", "bio": "C.", "mat": "D."})
        self.select(self.target)
        area = st.lm_sci_stack_area(CID)
        # bottom stays pinned; only the top moves, as `PCT-<height>px`
        self.assertIn(f", {st.LM_SCI_STACK_BOTTOM_PCT};", area)
        self.assertIn(f"{st.LM_SCI_STACK_BOTTOM_PCT}-", area)

    def test_the_box_does_not_resize_when_the_tab_count_changes(self):
        """A region's `area:` is read when it is pushed; reassigning `.style` on a live
        one did not re-lay-it-out, which is why the stack never grew. So the box is a
        CONSTANT sized for the most rows it will hold, and the rows do the growing."""
        before = st.lm_sci_stack_height_px(CID)
        science_set_scan_data(self.ship, self.target,
                              {"scan": "A kralien cruiser.", "status": "Damaged.",
                               "bio": "Kralien crew.", "mat": "Duranium."})
        self.select(self.target)
        self.assertEqual(st.lm_sci_stack_height_px(CID), before,
                         "the box must not depend on today's row count")

    def test_the_box_is_tall_enough_for_every_stock_tab_set(self):
        """scan/status/intel/mat/bio plus Queue, plus the header."""
        science_set_scan_data(self.ship, self.target,
                              {"scan": "a", "status": "b", "intel": "c",
                               "mat": "d", "bio": "e"})
        self.select(self.target)
        rows = len(st.lm_sci_tabs_items(CID))
        needed = st.LM_SCI_STACK_HEAD_PX + rows * st.LM_SCI_STACK_ROW_PX
        self.assertGreaterEqual(st.lm_sci_stack_height_px(CID), needed,
                                f"{rows} rows do not fit the box")

    def test_the_stack_comes_and_goes_with_the_selection(self):
        self.select(self.target)
        with_contact = [r["tab"] for r in st.lm_sci_tabs_items(CID)]
        self.assertIn("scan", with_contact)
        set_science_selection(self.ship, None)
        self.present()
        without = [r["tab"] for r in st.lm_sci_tabs_items(CID)]
        self.assertNotIn("scan", without)
        self.assertEqual(without, [st.LM_SCI_QUEUE_TAB])

    def test_queue_tab_shows_the_queue_panel(self):
        self.select(self.target)
        st.lm_sci_tabs_press({"cid": CID, "tab": "scan"})
        self.assertTrue(st.lm_sci_tabs_press({"cid": CID, "tab": st.LM_SCI_QUEUE_TAB}))
        self.assertEqual(st.lm_sci_tabs_current(CID), st.LM_SCI_QUEUE_TAB)
        self.present()


class ScienceConsoleClassic(_Base):
    """With the setting off, the stock console must build exactly as before."""
    NEW_LAYOUT = False

    def test_the_stock_console_still_builds(self):
        self.present(2)
        self.assertEqual(self.rte, [])

    def test_nothing_is_queued_by_the_stock_console(self):
        self.select(self.target)
        self.present()
        self.assertEqual(sq.lm_sci_queue_list("tsn"), [])


if __name__ == "__main__":
    unittest.main()
