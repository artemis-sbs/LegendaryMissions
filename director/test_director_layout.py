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
SIZED = ("subtab", "rundown", "itembtn", "conbtn", "ctrl")
FLEX = ("items", "view2d", "scilist", "ships", "consoles")

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

    def test_nothing_starts_under_the_tab_strip(self):
        # The console tab strip owns Layout(tag, None, 20, 0, 100, 3) - a 35px row. Content
        # starting above that is drawn underneath the tabs.
        m = dl.director_layout_metrics()
        self.assertGreaterEqual(m["top"], dl.DIRECTOR_TAB_STRIP_PX)

    def test_sections_in_a_column_do_not_overlap(self):
        # rundown -> items -> itembtn share the left column and are stacked; ships -> conbtn
        # do the same on the Console sub-tab, and that pair is what went wrong: conbtn held two
        # rows while it was sized from the ONE-row itembtn metric, so its status line drew
        # outside it.
        for screen in SCREENS:
            for stack in (("rundown", "items", "itembtn"), ("ships", "conbtn")):
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
