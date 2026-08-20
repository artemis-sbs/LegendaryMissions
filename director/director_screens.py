"""Ship rows, and carrying a listbox selection across a repaint.

WHAT LEFT THIS FILE. It used to work out who was on which screen: grouping mainscreens and crew
consoles, remembering what console a screen had been before the Director took it, and putting it
back on Stop. All of that went when the Director narrowed to a STREAMING TOOL - it drives
consoles that opened in program or preview mode (see director_modes.py) and does not reach out
and commandeer a bridge screen, so there is no home to remember and nothing to restore.

What is left is the two things that are still real: naming the player ships for a picker, and
the repaint contract at the bottom.

Every public name is prefixed `director_`: an addon's `def`s become MAST globals in one flat
mission-wide namespace and `register_mission_functions` assigns into it unconditionally - last
loaded wins, silently, in a non-deterministic order. A leading underscore is private.
"""


def _plain(text):
    """One safe line of display text: no braces, no backticks, stripped.

    `{` would be re-run as an f-string by the MAST assignment that receives it. A backtick
    is the `$text:` quoting delimiter and ends the quote early on the send path, which
    silently truncates the rest of the style string.
    """
    text = str(text)
    return text.replace("{", "(").replace("}", ")").replace("`", "'").strip()

def director_status_line(text):
    """The status line, always something. Safe to pass to `$text:` after `gui_text_escape`."""
    line = _plain(text or "")
    return line if line else "Ready."

def director_ship_rows():
    """(labels, ids) for the Ships listbox.

    Director cams are excluded twice over: they are stripped of `__player__` at spawn, and
    named here as well - so the exclusion is visible in the picker's own code rather than
    depending on a `remove_role` three files away staying put.
    """
    from sbs_utils.procedural.roles import role, any_role
    from sbs_utils.procedural.query import to_object
    labels = []
    ids = []
    seen = {}
    # Both cam kinds: a console's own cam and a program/preview screen's. Neither is a ship.
    for sid in sorted(role("__player__") - any_role("director_cam,director_screen_cam")):
        obj = to_object(sid)
        if obj is None:
            continue
        name = _plain(getattr(obj, "name", None) or "unnamed ship")
        n = seen.get(name, 0) + 1
        seen[name] = n
        if n > 1:
            name = name + " (" + str(n) + ")"
        labels.append(name)
        ids.append(sid)
    return labels, ids


# --- selection across a repaint ----------------------------------------------------------
#
# A repaint builds a NEW listbox whose items are new string objects, so nothing the old one held
# is still meaningful - except the ids in the parallel list, which are stable. These are the
# whole contract between one build and the next.


def director_selected_ids(lb, ids):
    """The ids behind a multi-select listbox's selection. Header slots are skipped."""
    if lb is None or ids is None:
        return []
    out = []
    for i in (lb.get_selected_index() or []):
        if 0 <= i < len(ids) and ids[i] is not None:
            out.append(ids[i])
    return out

def director_first_id(lb, ids, fallback=None):
    """The first selected id, or `fallback`. For a single-choice picker that may be empty."""
    chosen = director_selected_ids(lb, ids)
    return chosen[0] if chosen else fallback

def director_selected_items(lb):
    """The selected item objects, for a listbox whose items ARE the values."""
    if lb is None:
        return []
    return list(lb.get_selected() or [])

def director_selection_hint(lb):
    """The opaque view token to hand the next build, so the list does not jump to the top."""
    return lb.get_selection_hint() if lb is not None else None

def director_restore_ids(lb, ids, wanted):
    """Re-select every row whose parallel id is in `wanted`.

    THERE IS NO MULTI-SELECT RESTORE API. `set_selected_index` CLEARS the selection and
    takes one index; `apply_selection_hint` restores at most one, and only while nothing is
    selected; `select_all` is all-or-nothing; `set_value` takes a single value. So this
    assigns `.selected` directly - the same list `select_all()` writes - BEFORE the listbox
    is first presented, which is also what makes the hint yield to it: an explicit selection
    beats the hint's by contract, because the hint's job is the VIEW.

    The honest name for this is a library gap. `LayoutListbox.set_selected_indexes(indexes,
    set_cur=False)` is the fix; until it lands, this is the ONE place that knows about it.
    """
    if lb is None or not wanted or not ids:
        return
    want = set(wanted)
    sel = []
    for i, oid in enumerate(ids):
        if oid is not None and oid in want and i < len(lb.unfiltered_items):
            sel.append(lb.unfiltered_items[i])
    if sel:
        lb.selected = sel

def director_restore_items(lb, wanted):
    """Same, for a listbox whose items ARE the values (the Consoles list)."""
    if lb is None or not wanted:
        return
    sel = [item for item in lb.unfiltered_items if item in wanted]
    if sel:
        lb.selected = sel
