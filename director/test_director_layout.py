"""Every editor section is big enough for the rows it holds.

WHY THIS IS THE IMPORTANT TEST IN THIS ADDON. The editor page is reachable only by clicking a
tab-strip button, and `--exercise-click` cannot press those - they are built into
`pending_layouts`, never into the page tag map. So `--audit-layout` has never seen that page and
never will until the harness changes. It is the one screen nothing measures.

The first version of it shipped with a section 64px tall holding two 53px rows: the item list
bled up into the rundown buttons, and the control block was given 226px to hold 415px of stacked
rows, so **Add to rundown** fell off the bottom of the screen. Neither was a mock-versus-engine
metrics question - the arithmetic was simply wrong, and nothing checked it.

The control block is stacked again now, and full width - the 3D preview pane that forced it into
two columns is gone, because every Preview screen shows the real thing at full size. That is a
row budget that grew by four rows in one edit, which is precisely the change this test exists to
catch.

So the geometry is declared as data and checked here. A section that cannot fit its own rows
fails a test rather than looking wrong in a screenshot.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_layout
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import director_layout as dl

# The two ends of the range this console is expected to work at. 720p is the tight one: the
# bottom stack is anchored in pixels, so it costs the same there as at 1080p while the content
# above it has a third of the room.
SCREENS = (720, 1080)

# Sections that must hold declared rows. The others are lists and engine views, which scroll or
# size themselves - what matters for those is that they are not left with nothing.
SIZED = ("subtab", "rundown", "itembtn", "conbtn", "ctrl", "entry")
FLEX = ("items", "view2d", "scilist", "consoles")

# A list with less than this is not a list. Four rows at 1.7em gui-2 plus a title.
MIN_LIST_PX = 180


class SectionFitTests(unittest.TestCase):
    def test_every_sized_section_fits_its_rows(self):
        for screen in SCREENS:
            for name in SIZED:
                need = dl.director_rows_px(dl.director_section_rows(name))
                have = dl.director_section_height(name, screen)
                self.assertGreaterEqual(
                    have, need,
                    f"{name} at {screen}p has {have}px for {need}px of rows - "
                    f"its content will overdraw whatever is under it")

    def test_flex_sections_keep_usable_room(self):
        # The engine does not clip, so a section squeezed to nothing does not disappear - it
        # draws on top of its neighbour, which is exactly how the item list ended up over the
        # rundown buttons.
        for screen in SCREENS:
            for name in FLEX:
                have = dl.director_section_height(name, screen)
                self.assertGreaterEqual(
                    have, MIN_LIST_PX,
                    f"{name} at {screen}p is only {have}px tall")

    def test_the_bottom_stack_fits_the_smallest_screen(self):
        m = dl.director_layout_metrics()
        used = m["content_top"] + m["ctrl_up"]
        self.assertLess(used, 720,
                        "the fixed top and bottom bands leave nothing for the views at 720p")

    def test_a_row_over_wrapping_text_is_declared_for_more_than_one_line(self):
        """THE BUG THAT PUT THE ENTRY SCREEN IN THIS MODULE, as a test.

        Its help sentence wraps to two lines at the card's width and the row was declared
        `1.4em` - one line. The engine does not clip, so the second line drew straight through
        the pin row underneath it, and the input and button drew over each other from there.

        The MAST row is `row-height: content` so it takes what it measures, but the section has
        to have the space to give it, and that is what `_ROWS_ENTRY` reserves. A future edit
        trimming this back to one line would put the overlap straight back.
        """
        help_row = dl.director_section_rows("entry")[4]
        self.assertEqual(help_row[1], "gui-1")
        self.assertGreaterEqual(
            help_row[0], 2.0,
            "the entry screen's help text wraps - a one-line row spills into the pin row")

    def test_the_entry_card_pads_rather_than_growing_its_rows(self):
        """Height is for the line of text; PADDING is for the air around it.

        This test replaced one asserting the opposite, and the one it replaced was the bug.
        A widget FILLS the cell it is given, so making a row taller to stop things overlapping
        makes a taller BUTTON - the first fix for this screen cleared the overlap and left 62px
        slabs behind. Every row here is ONE line plus an explicit pad.
        """
        for i, row in enumerate(dl.director_section_rows("entry")):
            em, font = row[0], row[1]
            # The help row is the one legitimate multi-line row - its text genuinely wraps.
            limit = 2.0 if i == 4 else 1.0
            self.assertLessEqual(
                em, limit,
                f"entry row {i} is {em} lines of {font} - put the air in `padding:`, "
                f"not in `row-height:`, or the control grows with the row")

    def test_the_entry_cards_controls_get_air(self):
        # The radio and the pin/start row hold widgets that FILL their cell - a
        # RadioButtonGroup declines measurement entirely - so without vertical padding they
        # are exactly as tall as the row, whatever the row is.
        rows = dl.director_section_rows("entry")
        for i, what in ((2, "the mode radio"), (5, "the pin and start row")):
            pad = rows[i][2] if len(rows[i]) > 2 else 0
            self.assertGreaterEqual(
                pad, 12,
                f"{what} needs vertical padding - its controls fill the row without it")

    def test_the_entry_card_is_not_a_stack_of_slabs(self):
        # The whole card, as the reviewer sees it. Seven rows of one line each should not add
        # up to much more than seven lines and their gaps.
        need = dl.director_rows_px(dl.director_section_rows("entry"))
        self.assertLessEqual(need, 340, f"the entry card is {need}px of rows - too tall for "
                                        "seven lines of text")

    def test_the_entry_card_is_wide_enough_for_its_radio(self):
        # Three gui-3 labels side by side in ONE content item. At 50% of the screen they
        # wrapped mid-word - "Direct/r", "Progr/am", "Previe/w".
        left, _top, right, _bottom = dl._AREAS["entry"]
        self.assertGreaterEqual(right - left, 55,
                                "the mode radio needs room for three labels in a row")

    def test_nothing_starts_under_the_tab_strip(self):
        # The console tab strip owns Layout(tag, None, 20, 0, 100, 3) - a 35px row. Content
        # starting above that is drawn underneath the tabs.
        m = dl.director_layout_metrics()
        self.assertGreaterEqual(m["top"], dl.DIRECTOR_TAB_STRIP_PX)

    def test_sections_in_a_column_do_not_overlap(self):
        # rundown -> items -> itembtn share the left column and are stacked; consoles -> conbtn
        # do the same on the Console sub-tab, and that pair is what went wrong: conbtn held two
        # rows while it was sized from the ONE-row itembtn metric, so its status line drew
        # outside it.
        for screen in SCREENS:
            for stack in (("rundown", "items", "itembtn"), ("consoles", "conbtn")):
                self._assert_stacked(stack, screen)

    def _assert_stacked(self, names, screen):
        if True:
            bounds = []
            for name in names:
                left, top, right, bottom = dl._AREAS[name]
                bounds.append((self._px(top, screen), self._px(bottom, screen), name))
            for i in range(len(bounds) - 1):
                self.assertLessEqual(
                    bounds[i][1], bounds[i + 1][0],
                    f"{bounds[i][2]} ends at {bounds[i][1]} but "
                    f"{bounds[i + 1][2]} starts at {bounds[i + 1][0]} ({screen}p)")

    @staticmethod
    def _px(expr, screen):
        m = dl.director_layout_metrics()
        if expr.startswith("-"):
            return screen - m[expr[1:]]
        return sum(m[p] for p in expr.split("+"))


class AreaStringTests(unittest.TestCase):
    def test_every_area_is_a_well_formed_style_string(self):
        for name in dl._AREAS:
            area = dl.director_area(name)
            self.assertTrue(area.startswith("area: "), area)
            self.assertTrue(area.endswith(";"), area)
            self.assertEqual(area.count(","), 3, area)

    def test_lengths_are_px_or_percent_never_bare(self):
        # A bare number in an area is percent-of-SCREEN, which is exactly the unit confusion
        # this module exists to keep out of the MAST. Every vertical edge here is explicit px.
        for name in dl._AREAS:
            parts = [p.strip() for p in dl.director_area(name)[6:-1].split(",")]
            for vertical in (parts[1], parts[3]):
                self.assertIn("px", vertical, f"{name}: {vertical}")


class RowMathTests(unittest.TestCase):
    def test_an_em_is_one_line_of_the_rows_font(self):
        self.assertEqual(dl.director_row_px(1.0, "gui-2"), 24)
        self.assertEqual(dl.director_row_px(2.0, "gui-2"), 48)
        self.assertEqual(dl.director_row_px(1.5, "gui-3"), 42)

    def test_an_unknown_font_falls_back_to_gui_2(self):
        # An unfonted row IS gui-2 in the layout engine; matching that here keeps the budget
        # honest rather than optimistic.
        self.assertEqual(dl.director_row_px(1.0, "not-a-font"), 24)


if __name__ == "__main__":
    unittest.main()
