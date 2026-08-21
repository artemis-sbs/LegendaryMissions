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
# The Console sub-tab's block is TALLER than the item one: a subject line, a button row AND the
# status line. It shared `itembtn_up` while it had two rows to itembtn's one, so the status
# line - the only thing that says "added 3 console items" or "make a rundown first" - was drawn
# off the bottom of its own section. That is a fair part of why "Add console items" read as
# doing nothing.
#
# The subject line is READ-ONLY and comes from the bench: the tab's own Ships list was deleted
# when a console item learned to bind its ship, because the Stage's Subject/Bind row already
# answers "which ship" and two controls that can disagree about it is the duplicate the screen
# picker was deleted for.
_ROWS_CONBTN = [(2.0, "gui-2"), (2.2, "gui-2"), (1.8, "gui-2")]
# The Stage's control block: what the ITEM is, stacked and full width under the 2D view.
#
# IT USED TO CARRY THE OVERLAY ROWS TOO - one hand-unrolled row per overlay kind, four of them,
# because an `on gui_message` registered in a loop captures the loop variable at its last value.
# That put the vocabulary in the layout: a fifth kind was a fifth row here, a fifth block of
# MAST, and 24 more pixels off the 2D view. The overlays are a kind picker and ONE field editor
# now (`ovkinds` / `ovedit`), so this block is a fixed height whatever the vocabulary grows to.
#
# THE 2D VIEW IS WHAT PAYS FOR ROWS HERE, and it is the tight thing on this page: at 720p it is
# down to about 230px, which is usable for picking a contact off a radar but not generous. At
# 1080p it is nearly 600px and none of this matters. A fourth row wants measuring before it is
# added, not guessing - which is what this whole module exists for.
_ROWS_CTRL = [
    (2.0, "gui-2"),         # subject + clear + the BIND picker + the shot-mode radio
    (2.2, "gui-2"),         # add to rundown + send to program + hold
    (2.0, "gui-2"),         # distance + dolly-to + auto
]

# The overlay editor: which kind is being written, its fields, and the preset controls.
#
# DIRECTOR_OVERLAY_MAX_FIELDS field rows, unrolled and hidden past the end of the edited kind's
# field list. Declared as a fixed count here because the layout has to reserve room for the
# WIDEST kind - a section sized for the kind currently showing would resize under the operator
# every time they changed the dropdown.
_ROWS_OVEDIT = [
    (1.8, "gui-2"),         # "Editing" + the kind dropdown + the preset dropdown
    (1.9, "gui-2"),         # field 1
    (1.9, "gui-2"),         # field 2
    (1.9, "gui-2"),         # field 3
    (1.8, "gui-2"),         # preset name + save + status
]

# The MAIN PANEL's bottom stack, which used to be the literal `cv_ctrl_px = 219` in panel.mast
# with the arithmetic spelled out in a comment beside it. Same reason the editor's budget is
# here: the tab-strip pages are the ones the headless layout audit cannot reach, so a number
# nothing measures is a number that goes wrong quietly.
_ROWS_PANEL_CTRL = [
    (2.4, "gui-2"),         # send / stop / resume / refresh / pick mode
    (2.4, "gui-2"),         # dwell slider + auto-director checkbox
    (2.0, "gui-2"),         # ON AIR - written by the player
    (2.0, "gui-2"),         # status - written by the operator's own actions
]

# The panel's header: the cam name, the screen summary, and the live SELECTION.
_ROWS_PANEL_HEAD = [(1.5, "gui-3")]

_SECTION_ROWS = {
    "subtab": _ROWS_SUBTAB,
    "rundown": _ROWS_RUNDOWN,
    "itembtn": _ROWS_ITEMBTN,
    "conbtn": _ROWS_CONBTN,
    "ctrl": _ROWS_CTRL,
    "ovedit": _ROWS_OVEDIT,
    "panel_head": _ROWS_PANEL_HEAD,
    "panel_ctrl": _ROWS_PANEL_CTRL,
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
    ovedit_h = director_rows_px(_ROWS_OVEDIT) + DIRECTOR_SECTION_PAD + 2
    bottom = 6
    # The Stage's bottom stack, outside in: the overlay editor sits under the control block,
    # and the kind picker beside it shares its top edge - so `ovedit_up` is what the 2D view
    # and the kind picker both back off from.
    ovedit_up = ovedit_h + bottom
    stage_ctrl_up = ovedit_up + ctrl_h + 2

    # The MAIN PANEL. Its header, its tree and its control block are one column; the 2D view
    # and its zoom control are the other.
    panel_head_h = director_rows_px(_ROWS_PANEL_HEAD) + DIRECTOR_SECTION_PAD
    panel_tree_top = top + panel_head_h + 4
    panel_ctrl_h = director_rows_px(_ROWS_PANEL_CTRL) + DIRECTOR_SECTION_PAD + 2
    # The radar zoom strip is an ENGINE widget with its own fixed height, not a MAST row - it
    # is given pixels rather than em for the same reason it gets its own section.
    panel_zoom_h = 34
    panel_view_top = top + panel_zoom_h + 4
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
        "ctrl_up": stage_ctrl_up,
        "ovedit_h": ovedit_h,
        "ovedit_up": ovedit_up,
        "panel_head_h": panel_head_h,
        "panel_tree_top": panel_tree_top,
        "panel_ctrl_h": panel_ctrl_h,
        "panel_ctrl_up": panel_ctrl_h + bottom,
        "panel_zoom_h": panel_zoom_h,
        "panel_view_top": panel_view_top,
        "bottom": bottom,
    }


# name -> (left%, top_expr, right%, bottom_expr). The exprs are resolved against the metrics.
_AREAS = {
    "subtab":   (2, "top", 98, "top+subtab_h"),
    "rundown":  (2, "content_top", 30, "content_top+rundown_h"),
    "items":    (2, "items_top", 30, "-itembtn_up"),
    "itembtn":  (2, "-itembtn_up", 30, "-bottom"),
    # Stage: the 2D view with the science object list beside it, then the control block full
    # width under both. The split is FOUR FIFTHS to the view: the list is a column of names and
    # wants no more than that, while picking a subject off the radar wants every pixel it can
    # get. 32..85 is 53 of the 66 available (80.3%), 85..98 is 13 (19.7%).
    "view2d":   (32, "content_top", 85, "-ctrl_up"),
    "scilist":  (85, "content_top", 98, "-ctrl_up"),
    "ctrl":     (32, "-ctrl_up", 98, "-ovedit_up"),
    # The overlay editor, along the bottom: which kinds this item carries on the left, and the
    # text of the ONE being written on the right. The picker is narrow on purpose - it is a
    # column of six short labels, and every pixel it does not take is a template box wide
    # enough to read `<<class|ship>> - <<side>>` in.
    "ovkinds":  (32, "-ovedit_up", 48, "-bottom"),
    "ovedit":   (49, "-ovedit_up", 98, "-bottom"),
    # Console sub-tab: ONE list now - which stations - with the bench's subject, the Add button
    # and the status line under it. The Ships list that used to sit beside it went when a console
    # item learned to bind its ship; `consoles` took the whole width rather than being left
    # narrow beside a gap.
    "consoles": (32, "content_top", 98, "-conbtn_up"),
    "conbtn":   (32, "-conbtn_up", 98, "-bottom"),
    # --- the MAIN PANEL -------------------------------------------------------------------
    # Two columns. Left: who this is, the rundown tree, and the transport controls. Right: the
    # 2D view, which is a SELECTION SURFACE, not a monitor - clicking a contact re-points every
    # bound item in the play set. See panel.mast for the console-name rule that makes that work.
    #
    # 60/39 rather than an even split: the tree is the thing being read continuously and it
    # holds long labels ("Chase - Selection > weapons target  7s  [lower third]"), while the
    # radar only has to be big enough to hit a contact with a mouse.
    "panel_head":   (2, "top", 60, "top+panel_head_h"),
    "panel_tree":   (2, "panel_tree_top", 60, "-panel_ctrl_up"),
    "panel_ctrl":   (2, "-panel_ctrl_up", 60, "-bottom"),
    "panel_zoom":   (61, "top", 99, "top+panel_zoom_h"),
    "panel_view2d": (61, "panel_view_top", 99, "-bottom"),
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
