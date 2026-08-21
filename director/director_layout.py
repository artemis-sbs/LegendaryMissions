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


def director_row_px(em, font="gui-2", pad=0):
    """One row's height in pixels: `em` lines of the ROW's font, plus `pad` pixels.

    `pad` is the row's VERTICAL PADDING, and it is a separate term because it is a separate
    thing. Padding is what puts air around a control; making the row taller instead just makes
    the CONTROL taller, because a widget fills the cell it is given. That is not a nicety - it
    is the difference between a 28px button with room to breathe and a 62px slab.
    """
    return int(round(float(em) * DIRECTOR_FONT_PX.get(font, 24))) + int(pad)


def director_rows_px(rows):
    """Total height of `[(em, font), ...]` or `[(em, font, pad), ...]`.

    Both shapes, because most sections declare no padding and should not have to say `0`.
    """
    total = 0
    for row in rows:
        em, font = row[0], row[1]
        pad = row[2] if len(row) > 2 else 0
        total += director_row_px(em, font, pad)
    return total


# --- the row idiom -------------------------------------------------------------------------
#
# A WIDGET FILLS THE CELL IT IS GIVEN. That one fact is why every control on this console used
# to be a slab: the rows were declared 1.8em to 2.4em - 43 to 58 pixels - so the buttons, the
# typeins and the dropdowns in them were 43 to 58 pixels tall. Reaching for more height to stop
# things overlapping makes the overlap go away and leaves the slabs behind.
#
#   `row-height` is for the LINE OF TEXT.  `padding:` is for the AIR around it.
#
# Padding comes OUT of the row (layout.py shrinks the row's area by it) rather than adding to
# it, so a one-line row plus 16px of padding is a 40px row holding a 24px control with room to
# breathe - against a 53px row holding a 53px control with none.
#
# More below than above on purpose: the gap UNDER a row is what a reader perceives as separating
# it from the next one, and an even split wastes half of it on a gap nobody reads.
DIRECTOR_PAD_TOP = 4
DIRECTOR_PAD_BOTTOM = 12
DIRECTOR_CONTROL_PAD = DIRECTOR_PAD_TOP + DIRECTOR_PAD_BOTTOM

# HORIZONTAL AIR, and it is TWO different gaps. BOTH IN PIXELS.
#
# Pixels and not percent, which is worth stating because a bare number in a style string IS
# percent - LayoutAreaParser returns `digits` as-is and converts `px` and `em` into it. A 2%
# inset is 26px at 1280 and 38px at 1920: a margin that grows with the screen, when what is
# wanted is a hairline that does not.
#
# `DIRECTOR_PAD_SIDE` insets a row's content from the edges of its section, so text and controls
# do not start hard against the panel border.
#
# `DIRECTOR_COL_GAP` is the gap BETWEEN two controls in the same row. Columns are laid out edge
# to edge with no gap of their own - there is no `col-gap`, and `item-gap` belongs to a listbox -
# so without this a label sits welded to the box it labels: `Pin` and `Enter pin` with nothing
# at all between them. It is the one to raise if the row still reads as one run-on control.
DIRECTOR_PAD_SIDE = 5
DIRECTOR_COL_GAP = 5


def director_row_control(font="gui-2", extra=0):
    """The `gui_row` style for a row of CONTROLS - buttons, typeins, dropdowns, sliders.

    One line of `font` tall, with the standard air around it. `extra` adds height for a widget
    that needs more than its text - a radio group is the one here, because it DECLINES
    measurement (RadioButtonGroup inherits the base Column.measure, which returns None) and so
    it has nothing to size itself from.
    """
    height = DIRECTOR_PAD_TOP + DIRECTOR_PAD_BOTTOM + int(extra)
    return ("row-height: 1em+%dpx; font: %s; padding: %dpx,%dpx,%dpx,%dpx;"
            % (height, font, DIRECTOR_PAD_SIDE, DIRECTOR_PAD_TOP + int(extra),
               DIRECTOR_PAD_SIDE, DIRECTOR_PAD_BOTTOM))


def director_row_text(font="gui-2", gap=6):
    """The `gui_row` style for a row of TEXT - one line, with a gap under it.

    No top padding: text has no chrome to clear, so air above it only pushes it away from the
    thing it usually labels.
    """
    return ("row-height: 1em+%dpx; font: %s; padding: %dpx,0,%dpx,%dpx;"
            % (gap, font, DIRECTOR_PAD_SIDE, DIRECTOR_PAD_SIDE, gap))


def director_col(width=None, gap=None):
    """A control's style: how wide it is, and the gap to whatever sits beside it.

    COLUMNS ARE LAID OUT EDGE TO EDGE. There is no `col-gap` and `item-gap` belongs to a
    listbox, so two controls in one row touch unless one of them says otherwise - which is why
    the pin label sat welded to the box it labels. The gap goes on the RIGHT, so a row reads as
    a series of things each followed by a space; the last one's gap is absorbed by the
    `gui_blank()` that takes the slack.

    `width` is passed through verbatim - "160px", "content", "1fr" - because the vocabulary is
    the layout's, not this function's.
    """
    gap = DIRECTOR_COL_GAP if gap is None else int(gap)
    style = "col-width: %s; " % width if width else ""
    return style + "padding: 0,0,%dpx,0;" % gap


def director_row_control_budget(font="gui-2", extra=0):
    """The `_ROWS_*` entry matching `director_row_control` - so the two cannot drift."""
    return (1.0, font, DIRECTOR_PAD_TOP + DIRECTOR_PAD_BOTTOM + int(extra))


def director_row_text_budget(font="gui-2", gap=6):
    """The `_ROWS_*` entry matching `director_row_text`."""
    return (1.0, font, gap)


# Each section: the rows it must hold, and its horizontal extent in screen percent.
# `stack` is how the vertical budget is built - see director_layout_metrics.
_ROWS_SUBTAB = [director_row_control_budget("gui-3")]
_ROWS_RUNDOWN = [director_row_control_budget(),         # the rundown picker
                 director_row_control_budget()]        # new / rename / delete
_ROWS_ITEMBTN = [director_row_control_budget()]
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
_ROWS_CONBTN = [director_row_control_budget(),          # the bench subject, read-only
                director_row_control_budget(),          # add console items
                director_row_control_budget()]          # the status line
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
    director_row_control_budget(),      # subject + clear + the BIND picker + the shot-mode radio
    director_row_control_budget(),      # add to rundown + send to program + hold
    director_row_control_budget(),      # distance + dolly-to + auto
]

# The overlay editor: which kind is being written, its fields, and the preset controls.
#
# DIRECTOR_OVERLAY_MAX_FIELDS field rows, unrolled and hidden past the end of the edited kind's
# field list. Declared as a fixed count here because the layout has to reserve room for the
# WIDEST kind - a section sized for the kind currently showing would resize under the operator
# every time they changed the dropdown.
_ROWS_OVEDIT = [
    director_row_control_budget(),      # "Editing" + the kind dropdown + the preset dropdown
    director_row_control_budget(),      # field 1
    director_row_control_budget(),      # field 2
    director_row_control_budget(),      # field 3
    director_row_control_budget(),      # preset name + save + status
]

# The MAIN PANEL's bottom stack, which used to be the literal `cv_ctrl_px = 219` in panel.mast
# with the arithmetic spelled out in a comment beside it. Same reason the editor's budget is
# here: the tab-strip pages are the ones the headless layout audit cannot reach, so a number
# nothing measures is a number that goes wrong quietly.
_ROWS_PANEL_CTRL = [
    director_row_control_budget(),      # send / stop / resume / refresh / pick mode
    director_row_control_budget(),      # dwell slider + auto-director checkbox
    director_row_text_budget(),         # ON AIR - written by the player
    director_row_text_budget(),         # status - written by the operator's own actions
]

# The panel's header: the cam name, the screen summary, and the live SELECTION.
_ROWS_PANEL_HEAD = [director_row_text_budget("gui-3", 10)]

# THE ENTRY SCREEN - the pin / mode card every console lands on.
#
# IT WAS THE PAGE NOTHING MEASURED, and it drifted exactly the way this module's docstring says
# the editor did: a hand-written `area:` with hand-written `em` rows, and it shipped rendering
# with the radio labels wrapped mid-word, the help sentence overlapping the pin row, and the
# input drawn on top of the button. The engine does not clip, so a row declared one size and
# rendered another spills into whatever sits under it.
#
# THE FIRST FIX MADE THE ROWS TALLER, AND THAT WAS THE WRONG INSTINCT. A widget FILLS the cell
# it is given, so a taller row is a taller BUTTON - the overlap went away and left 62px slabs
# behind. Height is for the line of text; PADDING is for the air around it. Every row here is
# therefore ONE line plus an explicit pad, and the pad is the third term so it cannot be
# mistaken for content.
#
# The pad is mostly on the BOTTOM: that is the gap to the next row, which is the spacing a
# reader actually perceives. Where a control needs air on both sides - the radio, the pin row -
# it is split, and the MAST puts the same numbers on the row's `padding:`.
_ROWS_ENTRY = [
    director_row_text_budget("gui-4", 12),      # title
    director_row_text_budget("gui-2", 6),       # "This console is a"
    # THE RADIO IS THE ONE THAT CANNOT BE MEASURED. RadioButtonGroup inherits the base
    # Column.measure, which returns None - so `row-height: content` would fall back to FLEX and
    # it would fill whatever was left. It gets an explicit line plus its padding, and the
    # padding is what stops the buttons being as tall as the row.
    director_row_control_budget("gui-3", 8),    # the mode radio
    director_row_text_budget("gui-3", 12),      # "This screen will be called DIR01"
    (2.0, "gui-1", 14),                         # the help text - TWO lines at this width
    director_row_control_budget(),              # pin + input + start, one action on one row
    director_row_text_budget("gui-2", 0),       # the error line
]

_SECTION_ROWS = {
    "subtab": _ROWS_SUBTAB,
    "rundown": _ROWS_RUNDOWN,
    "itembtn": _ROWS_ITEMBTN,
    "conbtn": _ROWS_CONBTN,
    "ctrl": _ROWS_CTRL,
    "ovedit": _ROWS_OVEDIT,
    "panel_head": _ROWS_PANEL_HEAD,
    "panel_ctrl": _ROWS_PANEL_CTRL,
    "entry": _ROWS_ENTRY,
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

    # THE ENTRY CARD, anchored from the TOP in pixels rather than centred. The metrics here
    # are deliberately resolution-independent - `_edge` resolves `top`-relative and
    # `-bottom`-relative expressions and knows no screen height at all - so there is nothing
    # to centre against. Top-anchored is what every other section does, and it is what keeps
    # the card in the same place at 720p and 1080p instead of drifting between them.
    entry_h = director_rows_px(_ROWS_ENTRY) + DIRECTOR_SECTION_PAD + 2
    entry_top = top + 60
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
        "entry_h": entry_h,
        "entry_top": entry_top,
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
    # --- the ENTRY CARD -------------------------------------------------------------------
    # 60% wide, up from the 50% it shipped with. The radio needs room for three gui-3 labels
    # side by side and 50% is what left them wrapping mid-word; this is the width that fits
    # them. Narrower than the working pages on purpose - it is a card on an otherwise empty
    # screen, not a console.
    "entry":        (20, "entry_top", 80, "entry_top+entry_h"),
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
