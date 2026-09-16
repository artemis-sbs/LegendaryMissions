"""Row templates for the crew console's roster listbox.

Templates are PYTHON functions taking the item, not MAST labels - the listbox calls them
during its layout pass.

Named `boarding_ui_*`, not `boarding_*`. An addon's module-level functions land in one flat,
mission-wide MAST namespace, and `boarding_*` is the LIBRARY's
(`boarding_choices`, `boarding_answer`, `boarding_job_text`...). A helper called `boarding_row` here would
overwrite whichever the loader reached second, silently, with load order deciding which.
"""
from sbs_utils.procedural.boarding import boarding_job_text
from sbs_utils.procedural.gui import gui_row, gui_text, gui_text_escape


def boarding_ui_roster_row(item):
    """One character on the roster: who they are, and what they are for.

    The job line is not decoration - the scene's guards read exactly those words, so it
    is the answer to "why can she do that and I cannot".

    Sizes its ROWS and returns nothing. A listbox only calls `resize_to_content()` when
    the template returns None; returning a size leaves the item section degenerate, which
    takes the selection and the click region with it.
    """
    name = getattr(item, "name", None) or ""
    gui_row("row-height: 1.6em;")
    gui_text(f"$text:{gui_text_escape(name)};font:gui-3")
    gui_row("row-height: 1.4em;")
    gui_text(f"$text:{gui_text_escape(boarding_job_text(item, default='watching'))};font:gui-1;color:#8cf")


def boarding_ui_roster_title():
    """The list's own heading, so the box gets the whole section rather than sharing it
    with a label row above."""
    gui_row("row-height: 1.8em; background:#2348;")
    gui_text("$text:SPEAKING FOR;justify:center;font:gui-2;color:#fc8")
