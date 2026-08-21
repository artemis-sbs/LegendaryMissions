"""The editor's vertical budget, as data - so it can be CHECKED.

WHY THIS EXISTS. The editor page is only reachable by clicking a tab-strip button, and the
headless clicker cannot press those (they are built into `pending_layouts`, never into the tag
map). So `--audit-layout` never saw this page: it was the one screen nothing measured, and the
first version shipped with a section 64px tall holding two 53px rows. The item list bled up
into the rundown buttons and the Add button fell off the bottom.

Guessing again would be the same mistake. The sections are declared here with the ROWS they
have to hold, `director_area()` computes the geometry, and `test_director_layout.py` asserts
every section is big enough for its own rows. A section that cannot fit fails a test instead of
looking wrong in a screenshot.

THE LINE HEIGHTS ARE THE ENGINE'S OCCUPIED HEIGHTS, not ink extents - the same table the
layout engine uses to resolve `em`. An `em` is one line of the ROW's font, and a row that
declares no font is gui-2, which is the trap these constants exist to keep out of the MAST.

Every public name is prefixed `director_`: an addon's `def`s become MAST globals in one flat
mission-wide namespace, last loaded wins, silently.
"""

# Occupied line height per font tag. smallest 18, gui-1 22, gui-2 24, gui-3 28, gui-4 32,
# gui-5 36, gui-6 52.
DIRECTOR_FONT_PX = {"smallest": 18, "gui-1": 22, "gui-2": 24, "gui-3": 28,
                    "gui-4": 32, "gui-5": 36, "gui-6": 52}

# The engine console tab strip owns the top of the screen (Layout(tag, None, 20, 0, 100, 3),
# a 35px row). Content starts below it or it is drawn under the tabs.
DIRECTOR_TAB_STRIP_PX = 35

# Breathing room added to each section beyond the sum of its rows. Without it a section is
# exactly its content and the last row sits hard against the edge.
DIRECTOR_SECTION_PAD = 6


def director_row_px(em, font="gui-2"):
    """One row's height in pixels. `em` is a multiple of the ROW's font line height."""
    return int(round(float(em) * DIRECTOR_FONT_PX.get(font, 24)))


def director_rows_px(rows):
    """Total height of `[(em, font), ...]`."""
    return sum(director_row_px(em, font) for em, font in rows)


# Each section: the rows it must hold, and its horizontal extent in screen percent.
# `stack` is how the vertical budget is built - see director_layout_metrics.
_ROWS_SUBTAB = [(1.5, "gui-3")]
_ROWS_RUNDOWN = [(2.2, "gui-2"), (2.2, "gui-2")]        # picker row, then the button row
_ROWS_ITEMBTN = [(2.2, "gui-2")]
# The Console sub-tab's block is TALLER than the item one: a button row AND the status line.
# It shared `itembtn_up` while it had two rows to itembtn's one, so the status line - the only
# thing that says "added 3 console items" or "make a rundown first" - was drawn off the bottom
# of its own section. That is a fair part of why "Add console items" read as doing nothing.
_ROWS_CONBTN = [(2.2, "gui-2"), (1.8, "gui-2")]
# The control block, stacked and FULL WIDTH under the 2D view.
#
# It was two columns while the Stage carried a 3D preview pane beside the radar, which left the
# overlay rows about 400px to hold a checkbox, a preset picker, two template boxes and a Save.
# Dropping that pane (preview screens show the real thing, at full size, live) gave the whole
# width back, and a full-width row is the difference between a readable template box and one
# that shows six characters of `<<class|ship>> - <<side>>`.
_ROWS_CTRL = [
    (2.0, "gui-2"),         # subject + clear + the shot-mode radio
    (2.2, "gui-2"),         # add to rundown + send to program
    (1.9, "gui-2"),         # lower third
    (1.9, "gui-2"),         # hero
    (1.9, "gui-2"),         # top status
    (1.9, "gui-2"),         # letterbox
    (1.8, "gui-2"),         # preset name + save + status
]

_SECTION_ROWS = {
    "subtab": _ROWS_SUBTAB,
    "rundown": _ROWS_RUNDOWN,
    "itembtn": _ROWS_ITEMBTN,
    "conbtn": _ROWS_CONBTN,
    "ctrl": _ROWS_CTRL,
}


def director_layout_metrics():
    """Every vertical boundary the editor uses, in pixels.

    `*_top` are measured from the TOP; `*_up` are measured from the BOTTOM and are what a
    `100-Npx` coordinate wants. Anchoring the bottom stack in pixels is what keeps the page
    honest at 720p and 1080p alike - a percent section full of `em` rows is only correct at
    the resolution it was tuned at.
    """
    top = DIRECTOR_TAB_STRIP_PX + 5
    subtab_h = director_rows_px(_ROWS_SUBTAB) + DIRECTOR_SECTION_PAD
    content_top = top + subtab_h + 4
    rundown_h = director_rows_px(_ROWS_RUNDOWN) + DIRECTOR_SECTION_PAD + 2
    items_top = content_top + rundown_h + 4
    itembtn_h = director_rows_px(_ROWS_ITEMBTN) + DIRECTOR_SECTION_PAD
    conbtn_h = director_rows_px(_ROWS_CONBTN) + DIRECTOR_SECTION_PAD
    ctrl_h = director_rows_px(_ROWS_CTRL) + DIRECTOR_SECTION_PAD + 2
    bottom = 6
    return {
        "top": top,
        "subtab_h": subtab_h,
        "content_top": content_top,
        "rundown_h": rundown_h,
        "items_top": items_top,
        "itembtn_h": itembtn_h,
        "itembtn_up": itembtn_h + bottom,
        "conbtn_h": conbtn_h,
        "conbtn_up": conbtn_h + bottom,
        "ctrl_h": ctrl_h,
        "ctrl_up": ctrl_h + bottom,
        "bottom": bottom,
    }


# name -> (left%, top_expr, right%, bottom_expr). The exprs are resolved against the metrics.
_AREAS = {
    "subtab":   (2, "top", 98, "top+subtab_h"),
    "rundown":  (2, "content_top", 30, "content_top+rundown_h"),
    "items":    (2, "items_top", 30, "-itembtn_up"),
    "itembtn":  (2, "-itembtn_up", 30, "-bottom"),
    # Stage: the 2D view across the top, the control block full width under it.
    "view2d":   (32, "content_top", 98, "-ctrl_up"),
    "ctrl":     (32, "-ctrl_up", 98, "-bottom"),
    # Console sub-tab: two lists, and a button row plus a status line under them.
    "ships":    (32, "content_top", 64, "-conbtn_up"),
    "consoles": (66, "content_top", 98, "-conbtn_up"),
    "conbtn":   (32, "-conbtn_up", 98, "-bottom"),
}


def _edge(expr, m):
    """Resolve `top+subtab_h` or `-ctrl_up` into an area coordinate string."""
    if expr.startswith("-"):
        return "100-" + str(m[expr[1:]]) + "px"
    total = 0
    for part in expr.split("+"):
        total += m[part]
    return str(total) + "px"


def director_area(name):
    """The `area:` style string for one editor section.

    MAST asks for a NAME, not an arithmetic expression, so the geometry lives in one place
    that a test can check rather than being spelled out at nine call sites.
    """
    m = director_layout_metrics()
    left, top, right, bottom = _AREAS[name]
    return ("area: " + str(left) + ", " + _edge(top, m) + ", "
            + str(right) + ", " + _edge(bottom, m) + ";")


def director_section_rows(name):
    """The rows a section declares it must hold - what the fit test measures against."""
    return list(_SECTION_ROWS.get(name, ()))


def director_section_height(name, screen_px=720):
    """A section's height in pixels at a given screen height, for the fit test."""
    m = director_layout_metrics()
    left, top, right, bottom = _AREAS[name]

    def px(expr):
        if expr.startswith("-"):
            return screen_px - m[expr[1:]]
        return sum(m[p] for p in expr.split("+"))

    return px(bottom) - px(top)
