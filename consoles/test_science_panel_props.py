"""The readout's value has to be something the ENGINE can parse.

THE FIELD REPORT: `IndexError: invalid string position` out of `send_gui_text`, on a real
bridge, with the console otherwise working.

The cause was one wrapper. Every styled line is `$$color:X;font:Y;body` - a markdown
line-style block - and the whole lot was being wrapped in `$text:...;`. The first `;`
inside `$$color:X;` closed the `$text:` property, so the engine was handed props that ran
off the end of the string. Engineering never hits it because it passes the joined markdown
straight to `gui_text_area`.

The mock's `send_gui_text` takes whatever it is given, so 342 tests stayed green while the
engine crashed. These assert the SHAPE of the value instead: no property wrapper, and no
dynamic value carrying a `;` that would close a style block early.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_science_panel_props
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

from sbs_utils.helpers import Context, FakeEvent, FrameContext     # noqa: E402
from sbs_utils.procedural.query import to_object                   # noqa: E402
from sbs_utils.procedural.science import science_set_scan_data     # noqa: E402
from sbs_utils.procedural.sides import side_ensure, side_set_relations  # noqa: E402
from sbs_utils.procedural.spawn import npc_spawn, player_spawn     # noqa: E402
from sbs_utils.spaceobject import SpaceObject                      # noqa: E402

import science_panel as sp                                         # noqa: E402
import science_queue as sq                                         # noqa: E402
import science_tabs as st                                          # noqa: E402

CID = 1


class PanelPropsTest(unittest.TestCase):
    def setUp(self):
        SpaceObject.clear()
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        side_ensure("tsn")
        side_ensure("raider")
        # A side pair is NEUTRAL until a relation is declared. Without this the frequency
        # block - which is hostiles-only - is simply never reached.
        side_set_relations("tsn", "raider", mock_sbs.DIPLOMACY.HOSTILE)
        sq.lm_sci_queue_clear()
        self.ship = to_object(player_spawn(0, 0, 0, "Artemis", "tsn", "tsn_light_cruiser"))
        self.target = to_object(npc_spawn(1000, 0, 0, "K19", "raider",
                                          "tsn_light_cruiser", "behav_npcship"))
        mock_sbs.assign_client_to_ship(CID, self.ship.id)

    def tearDown(self):
        sq.lm_sci_queue_clear()
        FrameContext.context = None
        SpaceObject.clear()

    def _values(self):
        """The readout value on every tab, so one bad tab cannot hide behind a good one."""
        out = {}
        for tab in ("scan", "status", "intel", st.LM_SCI_QUEUE_TAB):
            st.lm_sci_tabs_set_current(CID, tab)
            out[tab] = sp.lm_sci_panel_value(CID)
        return out

    # --- nothing a scan has not earned --------------------------------------

    def _select(self, obj):
        from sbs_utils.procedural.query import set_science_selection
        set_science_selection(self.ship, obj)

    def test_an_unscanned_contact_is_unknown_in_the_header(self):
        """The NAME is scan data."""
        self._select(self.target)
        self.assertIn("unknown", sp.lm_sci_header_name_text(CID))
        self.assertNotIn("K19", sp.lm_sci_header_name_text(CID))

    def test_an_unscanned_contact_does_not_wear_its_relation_colour(self):
        """A red title says 'hostile' before anyone has earned it."""
        self._select(self.target)
        self.assertNotIn(sp._HOSTILE, sp.lm_sci_header_name_text(CID))

    def test_an_unscanned_contact_shows_no_side(self):
        """A flag identifies a contact as surely as a name does."""
        self._select(self.target)
        self.assertEqual(sp.lm_sci_header_side_text(CID), "$text:;")

    def test_the_readout_shows_the_queue_until_the_scan_lands(self):
        self._select(self.target)
        st.lm_sci_tabs_set_current(CID, "scan")
        self.assertEqual(sp.lm_sci_panel_effective_tab(CID), st.LM_SCI_QUEUE_TAB)
        self.assertIn("SCAN QUEUE", sp.lm_sci_panel_value(CID))

    def test_no_shield_or_system_reading_leaks_before_the_scan(self):
        """These come straight off the contact's blob, which is readable whether or not
        the side has scanned anything - so the gate has to be ours."""
        self._select(self.target)
        st.lm_sci_tabs_set_current(CID, "scan")
        value = sp.lm_sci_panel_value(CID)
        for leak in ("FRNT SHLD", "REAR SHLD", "SYSTEMS", "EFFICIENCY"):
            self.assertNotIn(leak, value, f"{leak} shown before the scan completed")

    def test_the_readout_opens_up_once_the_scan_lands(self):
        self._select(self.target)
        st.lm_sci_tabs_set_current(CID, "scan")
        science_set_scan_data(self.ship, self.target, {"scan": "A kralien cruiser."})
        self.assertEqual(sp.lm_sci_panel_effective_tab(CID), "scan")
        self.assertIn("K19", sp.lm_sci_header_name_text(CID))
        self.assertIn("raider", sp.lm_sci_header_side_text(CID))

    def test_a_scanned_scan_tab_does_not_unlock_the_status_tab(self):
        """Each tab is earned separately.

        Asserts the GATE directly rather than through the remembered tab: the current
        tab is per-client inventory, and this harness has no client agent to hold it -
        `lm_sci_tabs_set_current` silently does nothing here. The console harness, which
        pushes real pages, covers the remembered-tab path.
        """
        self._select(self.target)
        science_set_scan_data(self.ship, self.target, {"scan": "A kralien cruiser."})
        self.assertTrue(sq.lm_sci_queue_is_scanned(self.ship, self.target, "scan"))
        self.assertFalse(sq.lm_sci_queue_is_scanned(self.ship, self.target, "status"))

    def test_the_overflow_policy_is_shrink_not_wrap(self):
        """A wrapped title is drawn over the statline - the engine does not clip."""
        self._select(self.target)
        science_set_scan_data(self.ship, self.target, {"scan": "A kralien cruiser."})
        for props in (sp.lm_sci_header_name_text(CID),
                      sp.lm_sci_header_side_text(CID),
                      sp.lm_sci_statline_text(CID)):
            self.assertIn("overflow:shrink;", props, props)

    # --- shield frequencies -------------------------------------------------

    def _arm_bands(self, obj, strengths):
        for i, v in enumerate(strengths):
            obj.data_set.set("shield_freq_strength", v, i)

    def _status_of(self, obj):
        from sbs_utils.procedural.query import set_science_selection
        set_science_selection(self.ship, obj)
        science_set_scan_data(self.ship, obj, {"scan": "seen", "status": "hurt"})
        st.lm_sci_tabs_set_current(CID, "status")
        return chr(10).join(sp.lm_sci_panel_status_lines(self.ship.id, obj.id))

    def test_an_enemy_shows_its_shield_frequencies(self):
        """Drawn as text because the engine's own widget cannot be driven from a console
        that replaces science_data_tabs - see the note in science_tabs.py."""
        self._arm_bands(self.target, [9000, 3500, 8000, 9500, 7000])
        body = self._status_of(self.target)
        self.assertIn("SHIELD FREQUENCY", body)
        for band in sp.LM_SCI_FREQ_BANDS:
            # One gauge per band; the weak one's label also says WEAK.
            self.assertRegex(body, rf"\[{band}( - WEAK)?\]\(gauge://", f"band {band} missing")

    def test_the_weakest_band_is_called_out_in_words(self):
        """The tier colour says how strong a band is; the word says which to shoot. A
        gunner reads this aloud over comms, so both facts are wanted."""
        self._arm_bands(self.target, [9000, 3500, 8000, 9500, 7000])
        self.assertEqual(sp.lm_sci_weakest_band(
            sp.lm_sci_shield_frequencies(self.target.id)), "B")
        self.assertIn("WEAK", self._status_of(self.target))

    def test_a_friendly_shows_no_frequencies(self):
        """Nobody tunes a beam to a ship they are not shooting."""
        from sbs_utils.procedural.spawn import npc_spawn as _spawn
        friend = to_object(_spawn(3000, 0, 0, "TSN Essex", "tsn",
                                  "tsn_light_cruiser", "behav_npcship"))
        self._arm_bands(friend, [9000, 3500, 8000, 9500, 7000])
        self.assertNotIn("SHIELD FREQUENCY", self._status_of(friend))

    def test_unpopulated_bands_say_so_instead_of_showing_zeroes(self):
        """Five zeroes would read as "no shields at all" - a lie in the dangerous
        direction. But drawing NOTHING is indistinguishable from the block not existing,
        which is how long this took to notice."""
        body = self._status_of(self.target)
        self.assertIn("SHIELD FREQUENCY", body, "the heading must still appear")
        self.assertIn("no band readings", body)
        self.assertFalse(sp.lm_sci_has_band_readings(
            sp.lm_sci_shield_frequencies(self.target.id)))

    def test_the_readout_repaints_when_a_band_moves(self):
        """Weapons tunes to whatever this says, so a stale band points the guns at the
        wrong frequency - worse than showing none."""
        from sbs_utils.procedural.query import set_science_selection
        set_science_selection(self.ship, self.target)
        science_set_scan_data(self.ship, self.target, {"scan": "seen", "status": "hurt"})
        # The STATUS lines directly: `lm_sci_tabs_set_current` needs a client agent to
        # hold the tab and this harness has none, so going through the console's current
        # tab would silently test the scan tab instead.
        self._arm_bands(self.target, [9000, 3500, 8000, 9500, 7000])
        before = sp.lm_sci_panel_status_lines(self.ship.id, self.target.id)
        # Band C takes a beating and becomes the weak one.
        self.target.data_set.set("shield_freq_strength", 1000, 2)
        self.assertNotEqual(before,
                            sp.lm_sci_panel_status_lines(self.ship.id, self.target.id),
                            "a band change must repaint the readout")
        self.assertEqual(sp.lm_sci_weakest_band(
            sp.lm_sci_shield_frequencies(self.target.id)), "C")

    def test_the_values_are_read_from_the_blob_not_invented(self):
        """Exactly what was written, as a percentage of 10000 - no fabrication anywhere.

        The scale matters: read as a 0..1 coefficient, every band came out at 100% or
        more and the readout was meaningless."""
        self._arm_bands(self.target, [2000, 4000, 6000, 8000, 10000])
        self.assertEqual(sp.lm_sci_shield_frequencies(self.target.id),
                         [("A", 20), ("B", 40), ("C", 60), ("D", 80), ("E", 100)])
        self._arm_bands(self.target, [0.2, 0.4, 0.6, 0.8, 1.0])
        self.assertEqual(sp.lm_sci_shield_frequencies(self.target.id),
                         [("A", 20), ("B", 40), ("C", 60), ("D", 80), ("E", 100)])

    def test_the_scale_is_detected_not_assumed(self):
        """A hard-coded 10000 silently LOST the readout when the real values were
        smaller: everything rounded to 0 and the all-zero guard dropped the block. A
        wrong constant here does not look wrong, it looks like missing data."""
        self._arm_bands(self.target, [0.9, 0.35, 0.8, 0.95, 0.7])
        pcts = dict(sp.lm_sci_shield_frequencies(self.target.id))
        self.assertEqual(pcts["A"], 90, f"0..1 scale misread: {pcts}")
        self.assertEqual(pcts["B"], 35)

        self._arm_bands(self.target, [90, 35, 80, 95, 70])
        self.assertEqual(dict(sp.lm_sci_shield_frequencies(self.target.id))["A"], 90,
                         "percent scale misread")

        self._arm_bands(self.target, [9000, 3500, 8000, 9500, 7000])
        self.assertEqual(dict(sp.lm_sci_shield_frequencies(self.target.id))["A"], 90,
                         "10000 scale misread")

    def test_the_weak_band_is_the_same_whatever_the_scale(self):
        """Every band divides by the SAME number, which is what keeps them comparable."""
        for bands in ([0.9, 0.35, 0.8, 0.95, 0.7],
                      [90, 35, 80, 95, 70],
                      [9000, 3500, 8000, 9500, 7000]):
            self._arm_bands(self.target, bands)
            self.assertEqual(sp.lm_sci_weakest_band(
                sp.lm_sci_shield_frequencies(self.target.id)), "B", f"scale {bands[0]}")

    def test_the_tiers_are_quartered(self):
        """25 / 50 / 75, the way the engine's own bars read."""
        self.assertEqual(sp.lm_sci_frequency_color(80), sp.lm_sci_frequency_color(100))
        self.assertNotEqual(sp.lm_sci_frequency_color(74), sp.lm_sci_frequency_color(76))
        self.assertNotEqual(sp.lm_sci_frequency_color(49), sp.lm_sci_frequency_color(51))
        self.assertNotEqual(sp.lm_sci_frequency_color(24), sp.lm_sci_frequency_color(26))

    def test_the_lowest_band_is_the_weak_one(self):
        """Whatever the scale, WEAK is simply the smallest reading."""
        self._arm_bands(self.target, [9000, 3500, 8000, 9500, 7000])
        self.assertEqual(sp.lm_sci_weakest_band(
            sp.lm_sci_shield_frequencies(self.target.id)), "B")
        self._arm_bands(self.target, [9000, 8000, 8000, 500, 7000])
        self.assertEqual(sp.lm_sci_weakest_band(
            sp.lm_sci_shield_frequencies(self.target.id)), "D")

    def test_status_shows_the_shields_too(self):
        """Shields move fastest and are what a gunner asks for by name - status is the
        tab they will be on, so switching tabs to read them is the wrong trade."""
        self.target.data_set.set("shield_val", 90.0, 0)
        self.target.data_set.set("shield_val", 40.0, 1)
        self.target.data_set.set("shield_max_val", 120.0, 0)
        self.target.data_set.set("shield_max_val", 120.0, 1)
        body = self._status_of(self.target)
        self.assertIn("[FRNT SHLD](gauge://90?max=120&show=value", body)
        self.assertIn("[REAR SHLD](gauge://40?max=120&show=value", body)

    def test_the_readout_parses_into_gauges_and_a_systems_grid(self):
        """Parsed the way the widget parses it, so a malformed line cannot pass."""
        from sbs_utils.pages.layout.text_area import TextArea, GaugeLine, TableLine
        from sbs_utils.pages.layout.layout import Bounds
        self.target.data_set.set("shield_val", 90.0, 0)
        self.target.data_set.set("shield_max_val", 120.0, 0)
        for i in range(4):
            self.target.data_set.set("system_max_damage", 10.0, i)
        self._arm_bands(self.target, [9000, 8000, 8000, 500, 7000])
        area = TextArea("probe", self._status_of(self.target))
        area.bounds = Bounds(0, 0, 25, 95)
        area.calc_rich(CID)
        gauges = [ln for ln in area.lines if isinstance(ln, GaugeLine)]
        grids = [ln for ln in area.lines if isinstance(ln, TableLine)]
        self.assertEqual(len(grids), 1, "SYSTEMS is one grid")
        self.assertFalse(grids[0].has_header)
        self.assertEqual(len(grids[0].gauges), 4)
        labels = [g.spec["label"] for g in gauges]
        self.assertIn("FRNT SHLD", labels)
        self.assertIn("D - WEAK", labels)                 # the weakest band, in words
        self.assertEqual(len([l for l in labels if l[:1] in "ABCDE" and len(l) <= 8]), 5)

    def test_the_shield_value_is_absolute_and_only_the_colour_is_a_ratio(self):
        """"front shields 90" is what gets said out loud, not "75 percent"."""
        self.target.data_set.set("shield_val", 90.0, 0)
        self.target.data_set.set("shield_max_val", 120.0, 0)
        line = sp.lm_sci_shield_lines(self.target.id)[0]
        self.assertIn("90", line)
        self.assertNotIn("75", line)

    def test_both_tabs_draw_the_same_shield_lines(self):
        """One helper, so they cannot drift apart."""
        self.target.data_set.set("shield_val", 90.0, 0)
        self.target.data_set.set("shield_max_val", 120.0, 0)
        shields = sp.lm_sci_shield_lines(self.target.id)
        scan = sp.lm_sci_panel_scan_lines(self.ship.id, self.target.id)
        status = sp.lm_sci_panel_status_lines(self.ship.id, self.target.id)
        for line in shields:
            self.assertIn(line, scan)
            self.assertIn(line, status)

    def test_a_contact_never_shows_the_efficiency_block(self):
        """The eight `*_damage_coeff` values are derived from a ship's OWN damage grid,
        so read off somebody else's hull they are not a weaker signal - they are the
        wrong number. Reported as inaccurate on NPCs from a real bridge."""
        for key in ("all_beam_damage_coeff", "impulse_damage_coeff",
                    "warp_damage_coeff", "sensor_damage_coeff"):
            self.target.data_set.set(key, 0.5, 0)
        self.assertNotIn("EFFICIENCY", self._status_of(self.target))

    def test_system_health_still_shows_on_a_contact(self):
        """`system_damage` / `system_max_damage` is the model the engine uses to kill an
        NPC, so unlike the coefficients it is true about any ship."""
        for i in range(4):
            self.target.data_set.set("system_max_damage", 10.0, i)
        self.target.data_set.set("system_damage", 5.0, 1)
        body = self._status_of(self.target)
        self.assertIn("SYSTEMS", body)
        self.assertIn("ENGN", body)

    def test_unpopulated_coefficients_are_dropped_not_shown_as_zeroes(self):
        """Eight zeroes drew a healthy raider as a wreck - beam 0%, tube 0%, warp 0%.
        A missing readout and a dead ship must never look the same."""
        self.assertEqual(sp.lm_sci_coefficients(self.target.id), [])
        self.assertNotIn("EFFICIENCY", self._status_of(self.target))

    def test_real_coefficients_still_show(self):
        """The guard must not swallow a genuine readout that happens to contain a zero."""
        self.target.data_set.set("all_beam_damage_coeff", 1.0, 0)
        self.target.data_set.set("warp_damage_coeff", 0.0, 0)
        values = dict(sp.lm_sci_coefficients(self.target.id))
        self.assertEqual(values.get("beam"), 100)
        self.assertEqual(values.get("warp"), 0)

    def test_name_is_colored_by_relation_and_side_by_the_side(self):
        """Two facts, two colours. A neutral ship of a side we fight elsewhere must not
        read as hostile because of its flag."""
        from sbs_utils.procedural.query import set_science_selection
        from sbs_utils.procedural.sides import side_set_icon_color, side_get_side_color
        side_set_icon_color("raider", "#B03060")
        set_science_selection(self.ship, self.target)
        # The colour rules only apply once the contact is KNOWN - before that it is
        # "unknown" in grey, which its own test covers.
        science_set_scan_data(self.ship, self.target, {"scan": "A kralien cruiser."})
        name = sp.lm_sci_header_name_text(CID)
        side = sp.lm_sci_header_side_text(CID)
        self.assertIn("K19", name)
        self.assertIn("raider", side)
        self.assertIn(side_get_side_color("raider"), side,
                      "the side must wear its own icon colour")
        self.assertNotIn(side_get_side_color("raider"), name,
                         "the name must NOT take the side's colour")

    def test_the_title_is_gui_3(self):
        from sbs_utils.procedural.query import set_science_selection
        set_science_selection(self.ship, self.target)
        science_set_scan_data(self.ship, self.target, {"scan": "A kralien cruiser."})
        self.assertIn("font:gui-3;", sp.lm_sci_header_name_text(CID))
        self.assertIn("font:gui-3;", sp.lm_sci_header_side_text(CID))

    def test_the_statline_reads_rng_ber_alt(self):
        from sbs_utils.procedural.query import set_science_selection
        set_science_selection(self.ship, self.target)
        stat = sp.lm_sci_statline(CID)
        for key in ("rng:", "ber:", "alt:"):
            self.assertIn(key, stat, f"{key} missing from {stat!r}")
        self.assertIn("font:gui-1;", sp.lm_sci_statline_text(CID))

    def test_the_statline_changes_when_the_contact_moves(self):
        """It is watched by an `on change` on its own text, so it has to actually move."""
        from sbs_utils.procedural.query import set_science_selection
        set_science_selection(self.ship, self.target)
        before = sp.lm_sci_statline(CID)
        self.target.pos = mock_sbs.vec3(9000.0, 400.0, 0.0)
        self.assertNotEqual(before, sp.lm_sci_statline(CID))

    def test_a_missing_reading_is_omitted_not_zeroed(self):
        """A reading of zero and no reading at all mean very different things."""
        self.assertEqual(sp.lm_sci_statline(CID), "",
                         "with nothing selected the statline is empty, not 'rng: 0'")

    def test_the_value_is_never_wrapped_in_a_text_property(self):
        """This exact wrapper is what crashed the engine."""
        for tab, value in self._values().items():
            self.assertFalse(value.startswith("$text:"),
                             f"{tab} tab wrapped its markdown in a $text: property")

    def test_every_styled_line_separates_its_style_block_with_a_space(self):
        """THE SPACE IS THE SYNTAX.

        `TextArea.get_line_style` does `some_lines.split(" ", 1)` and parses everything
        before the FIRST space as the style block. Without a space after the final `;`,
        the first word of the text is parsed as a style property and the widget draws
        "Document syntax issue line number 0" - which is what a real bridge showed for
        `$$color:springgreen;font:gui-3;TSN Beijing`.
        """
        for tab, value in self._values().items():
            for line in value.split(chr(10)):
                if not line.startswith("$$"):
                    continue
                self.assertIn(" ", line, f"{tab}: no space to end the style block: {line!r}")
                block = line.split(" ", 1)[0][2:]
                self.assertTrue(block.endswith(";"),
                                f"{tab}: style block does not end in a semicolon: {line!r}")
                for pair in [p for p in block.split(";") if p]:
                    self.assertIn(":", pair,
                                  f"{tab}: {pair!r} is text parsed as a style property "
                                  f"in {line!r}")

    def test_the_style_block_itself_contains_no_space(self):
        """A space inside the block would end it early - so the values stay bare."""
        for tab, value in self._values().items():
            for line in value.split(chr(10)):
                if line.startswith("$$"):
                    block = line.split(" ", 1)[0]
                    self.assertNotIn(" ", block, f"{tab}: {line!r}")

    def test_every_styled_line_has_a_complete_style_block(self):
        """A `$$` line is `$$<props>;<body>`. If a dynamic value smuggled in a `;`, the
        body would be parsed as another property and the engine would run off the end."""
        for tab, value in self._values().items():
            for line in value.split(chr(10)):
                if not line.startswith("$$"):
                    continue
                props = line[2:]
                self.assertIn(";", props, f"{tab}: style block never closed: {line!r}")
                # color and font, then the body - exactly two semicolons before text.
                head, _, body = props.partition(";")
                self.assertTrue(head.startswith("color:"), f"{tab}: {line!r}")
                self.assertNotIn(";", body.partition(";")[2],
                                 f"{tab}: body carries a semicolon: {line!r}")

    def test_a_semicolon_in_mission_prose_cannot_break_a_line(self):
        """Scan text is author-written and can contain anything."""
        science_set_scan_data(self.ship, self.target,
                              {"scan": "Hull breach; venting atmosphere; adrift."})
        st.lm_sci_tabs_set_current(CID, "scan")
        from sbs_utils.procedural.query import set_science_selection
        set_science_selection(self.ship, self.target)
        value = sp.lm_sci_panel_value(CID)
        for line in value.split(chr(10)):
            if line.startswith("$$"):
                self.assertLessEqual(line.count(";"), 2,
                                     f"prose leaked a semicolon into a style block: {line!r}")

    def test_a_newline_in_mission_prose_cannot_split_a_styled_line(self):
        name_with_break = "K19" + chr(10) + "raider"
        self.assertNotIn(chr(10), sp._safe(name_with_break))

    def test_safe_is_not_backtick_escaping(self):
        """`gui_text_escape` wraps in backticks for a $text: PROPERTY. In a markdown body
        that renders as backticks, which is why this module has its own sanitizer."""
        self.assertNotIn("`", sp._safe("plain words"))


if __name__ == "__main__":
    unittest.main()
