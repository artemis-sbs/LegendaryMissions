"""The Director's SELECTION, and subjects that name it instead of an object.

WHY. A rundown item used to bake a concrete object id at the moment it was added, so a
rundown was a list of specific ships and a show had to be re-authored whenever the
interesting ship changed. A BOUND subject is a string of `<<token>>` hops resolved at play
time, so one item means "orbit whatever I have clicked" - and the operator re-points the
whole show by clicking a contact on the 2D view, mid-show, without touching the rundown.

ONE SELECTION, not one per console, for the same reason there is one staging bench
(director_shots.py): a show has one director, and two people re-pointing the same feed from
two consoles would be fighting over it anyway.

THE DELIMITER IS THE OVERLAY DELIMITER, deliberately. `director_overlays` already teaches
the operator `<<name>>` and `<<class|ship>>`; a subject written `<<selected_id>>` costs them
no new vocabulary. See that module for why braces are fatal on this path.

A HOP THAT LEADS NOWHERE FALLS BACK TO THE SHIP IT WAS ASKED ABOUT, rather than failing: a
weapons officer with no target gives a shot of the SHIP, not a hole in the rotation. See
`director_bind_resolve` for the whole rule and the two things that still resolve to nothing.

WHERE THIS DIFFERS FROM THE OVERLAY RESOLVER, and it matters: an unknown token there is left
LITERAL, so a typo shows up on air as `<<shpi>>` and is obvious. Here an unknown token kills
the chain - it is the one failure that does NOT fall back. A visible typo on a card is
informative; a subject that quietly resolved to the selection would point the camera somewhere
plausible and look deliberate.

Every public name is prefixed `director_`: an addon's `def`s become MAST globals in one flat
mission-wide namespace, last loaded wins, silently. A leading underscore is private.
"""
import re

# One hop. No `|fallback` form: a subject either resolves or it does not - see the module
# docstring, and director_rundown_play_set, which skips what will not resolve.
_HOP = re.compile(r"<<\s*(?P<tok>[A-Za-z_][A-Za-z_0-9]*)\s*>>")

# The show's current selection. A LIST so it is rebindable from a nested scope, and PER
# MISSION: cosmos_dev reuses one interpreter across run_next_mission, so a module-level
# container nothing clears is the classic "works on run 1, stale on run 2". Cleared from the
# addon top level.
_SELECTION = [None]


def director_selection_reset():
    """Forget what is selected. Called from the addon top level, per mission."""
    _SELECTION[0] = None


def director_selection(object_id=None, clear=False):
    """Read or set the Director's selection. Returns the id, or None.

    Set from `//focus/science` in stage.mast, which fires for the main panel and the editor
    alike because it is gated on the client riding its own `director_cam` - not on a tab.
    """
    if clear:
        _SELECTION[0] = None
    elif object_id:
        _SELECTION[0] = object_id
    return _SELECTION[0]


def _plain(text):
    """Display text with no braces and no backticks - see director_rundowns._plain."""
    return str(text).replace("{", "(").replace("}", ")").replace("`", "'").strip()


def director_selection_label():
    """What the panel calls the current selection."""
    from sbs_utils.procedural.query import to_object
    from director_cam import director_cam_point_name
    sid = _SELECTION[0]
    if not sid:
        return "nothing selected"
    obj = to_object(sid)
    if obj is None:
        return "gone"
    # A click on empty space selects the CAM, which is nameless by design - so ask what to
    # call a place before falling through to "unnamed".
    point = director_cam_point_name(sid)
    if point:
        return _plain(point)
    return _plain(getattr(obj, "name", None) or "unnamed")


# --- the hops -----------------------------------------------------------------------------
#
# Each takes the id resolved so far and returns the next one. A CONSOLE SELECTION READS 0
# WHEN IT IS UNSET - `get_weapons_selection` pulls `weapon_target_UID` straight out of the
# blob and the engine's "no target" value is 0, not None - so every one of these can hand
# back a falsy value that is not an id, and `_resolve` treats falsy as end of chain.


def _hop_selected(current):
    """The seed hop. Identity: the chain already starts at the selection."""
    return current


def _hop_weapons(current):
    from sbs_utils.procedural.query import get_weapons_selection
    return get_weapons_selection(current)


def _hop_science(current):
    from sbs_utils.procedural.query import get_science_selection
    return get_science_selection(current)


def _hop_comms(current):
    from sbs_utils.procedural.query import get_comms_selection
    return get_comms_selection(current)


# NO GRID HOP. `grid_selected_UID` names a room or a system on a ship's INTERNAL grid, not a
# space object - there is nothing out there for a camera to point at, and the ids come from a
# different space entirely. It was offered in the first version of this table purely because
# `get_grid_selection` sits beside the other three in query.py.
_HOPS = {
    "selected_id": _hop_selected,
    "weapons_selection": _hop_weapons,
    "science_selection": _hop_science,
    "comms_selection": _hop_comms,
}

# token -> what a row or a picker calls that hop.
_HOP_LABELS = {
    "selected_id": "Selection",
    "weapons_selection": "weapons target",
    "science_selection": "science target",
    "comms_selection": "comms target",
}


def director_bind_tokens():
    """The hop names, for a help line on the editor."""
    return sorted(_HOPS)


def director_bind_token_help():
    """One ASCII line naming what an operator can type into a subject."""
    return "<<" + ">>  <<".join(director_bind_tokens()) + ">>   (chained left to right)"


def director_bind_is(subject):
    """Is this subject a binding rather than an object id?"""
    return isinstance(subject, str) and "<<" in subject


def _hops_of(subject):
    """The token list a binding spells, in order. [] when it spells none."""
    return [m.group("tok").lower() for m in _HOP.finditer(str(subject or ""))]


def director_bind_resolve(subject):
    """The live id a binding currently names, or None.

    THE CHAIN SEEDS FROM THE SELECTION, so `<<weapons_selection>>` and
    `<<selected_id>><<weapons_selection>>` are the same thing and `<<selected_id>>` is just
    the identity hop. That is not a shortcut for the parser's benefit - it is what makes the
    picker's labels read as one sentence ("Selection > weapons target") instead of forcing a
    prefix nobody would ever omit deliberately.

    A HOP THAT LEADS NOWHERE FALLS BACK TO THE SHIP IT WAS ASKED ABOUT. "Chase what the
    selected ship is shooting at" is a shot of that ship when it is shooting at nothing, and
    that is the answer a director wants: a fight is full of moments with no target, and a gap
    in the rotation every time the weapons officer drops theirs is worse direction than the
    ship itself. So each hop is TRIED, and the last live object stands if it leads nowhere.

    Three ways a hop leads nowhere, all the same thing here:

      * the console has no target - `weapon_target_UID` reads 0, which is the engine's "unset"
        and NOT object zero;
      * it is still holding an id that has since been destroyed;
      * the blob read raises, which a tombstoned object can do from inside the engine.

    WHAT STILL RESOLVES TO None, and is therefore skipped by director_rundown_play_set:

      * nothing selected, or the selection itself is gone. There is no ship to fall back TO,
        so there is nothing to show.
      * an unknown token. That is an authoring error rather than a runtime state, and falling
        back would quietly point the camera at the selection and look deliberate. A binding
        that never shows at all is the visible failure.
    """
    from sbs_utils.procedural.query import to_object
    current = _SELECTION[0]
    # THE SEED IS VALIDATED TOO. Every later hop falls back to it, so a dead selection would
    # otherwise be what the whole chain settled on.
    if not current or to_object(current) is None:
        return None
    hops = _hops_of(subject)
    if not hops:
        return None
    for tok in hops:
        fn = _HOPS.get(tok)
        if fn is None:
            return None                 # unknown token: the chain is dead, not literal
        try:
            nxt = fn(current)
        except Exception:
            nxt = None
        if not nxt or to_object(nxt) is None:
            break                       # nothing live down there - hold what we have
        current = nxt
    return current


def director_bind_label(subject):
    """What a row calls a binding: "Selection > weapons target"."""
    hops = _hops_of(subject)
    if not hops:
        return "unbound"
    names = [_HOP_LABELS.get(tok, tok) for tok in hops]
    if names[0] != _HOP_LABELS["selected_id"]:
        # The seed is implicit in the string; it is not implicit in the label.
        names = [_HOP_LABELS["selected_id"]] + names
    return " > ".join(names)


# --- what the editor offers ----------------------------------------------------------------
#
# A fixed table of the USEFUL chains. A hand-typed chain still resolves - this is the picker,
# not the grammar - but the picker is how anybody actually gets one, so it holds the ones a
# director wants and no combinatorial expansion of the hop table.

# The two ends are not chains: "" means the item keeps the object that was clicked, and None
# means the item has no subject at all and is pure furniture.
DIRECTOR_BIND_FIXED = ""
DIRECTOR_BIND_NONE = None

_CHOICES = (
    (DIRECTOR_BIND_FIXED, "Fixed - the object clicked"),
    ("<<selected_id>>", "Selection"),
    ("<<selected_id>><<weapons_selection>>", "Selection > weapons target"),
    ("<<selected_id>><<science_selection>>", "Selection > science target"),
    ("<<selected_id>><<comms_selection>>", "Selection > comms target"),
    (DIRECTOR_BIND_NONE, "None - overlays only"),
)


def director_bind_choices():
    """(values, labels) for the editor's Bind dropdown, in picker order."""
    return [c[0] for c in _CHOICES], [c[1] for c in _CHOICES]


def director_bind_list():
    """The comma-separated labels, for `gui_drop_down`'s `list:`."""
    return ",".join(director_bind_choices()[1])


def director_bind_for(label):
    """The binding a picker label means: a chain, "" for fixed, or None for overlay-only.

    A dropdown carries display TEXT, not values, so the selection has to be mapped back -
    and the two ends of this table are `""` and `None`, which a caller cannot tell apart
    from "no match". `director_bind_label_of` is the inverse and never guesses.
    """
    want = _plain(label)
    for value, name in _CHOICES:
        if name == want:
            return value
    return DIRECTOR_BIND_FIXED


def director_bind_label_of(value):
    """The picker label for a stored binding. The inverse of director_bind_for."""
    for choice, name in _CHOICES:
        if choice == value:
            return name
    # A hand-typed chain that is not in the table still deserves a readable row.
    return director_bind_label(value) if director_bind_is(value) else _CHOICES[0][1]
