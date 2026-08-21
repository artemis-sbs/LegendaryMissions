"""The staging bench: the item the editor is currently building, and the shot vocabulary.

WHAT THIS NO LONGER DOES. It used to compute lens offsets - a hand-built orbit vector at a
hand-picked distance, with sliders for both. That is gone. The shot modes here are the ones a
bridge already offers (`viewscreen.SHOT_LABELS`, the science and weapons "On Screen" list), and
the framing comes from `viewscreen_framing()`, which scales off the subject's own hull radius so
"a starbase and a fighter both fill the frame". A fixed distance framed neither well, and having
a second framing vocabulary meant a Director shot and a bridge shot of the same ship looked
different for no reason.

WHY THE BENCH IS HERE AND NOT IN MAST VARIABLES. Every control on the editor restages LIVE - a
tick, a preset, a keystroke - and a repaint would throw away whatever is half-typed in the next
box, so the handlers cannot rebuild the page. Keeping the bench in Python makes each handler one
short call that mutates it and restages, instead of a twelve-argument line repeated at ten call
sites and ten `shared` variables to keep in step with it.

ONE BENCH, not one per console. A show has one director; two people editing the same staged shot
from two consoles would be fighting over the preview feed anyway, and per-console state would
only make that failure quieter.

WHY `tactical` IS IN THE SAME LIST AS THE CAMERA MODES. It is not a cinematic camera - it is a
2D view - and `MAIN_SCREEN_VIEW` really does live on the SHIP rather than the client. But that
only rules out doing it through the main-screen keys. A Director screen showing a full-page
`2dview` focused on the subject is per-client, so two screens can hold different modes for the
same ship. To the operator it is one vocabulary; where the mechanisms differ is the player's
problem, not the picker's.

Every public name is prefixed `director_`: an addon's `def`s become MAST globals in one flat
mission-wide namespace, last loaded wins, silently. A leading underscore is private.
"""

def director_overlay_kinds():
    """The overlay vocabulary: ((kind, label, field names), ...), in picker order.

    THE TABLE LIVES IN director_overlays, which already owns the field names and the presets.
    It used to live here as well, and two tables that have to agree are two tables that will
    not - adding a kind meant editing both and unrolling another MAST row.

    A function, not a top-level import: every .py of an addon is exec'd into ONE shared
    namespace in a load order nothing here controls, so a top-level sibling import is a
    load-order dependency that fails silently. It is also what lets the unit tests import each
    module on its own.
    """
    from director_overlays import DIRECTOR_OVERLAY_KINDS
    return DIRECTOR_OVERLAY_KINDS


def director_overlay_kind_labels():
    """Just the editor labels, in order - the rows of the kind picker."""
    return [label for _kind, label, _fields in director_overlay_kinds()]


def director_overlay_kind_for(label):
    """The kind a picker label names, or None."""
    want = _plain(label)
    for kind, name, _fields in director_overlay_kinds():
        if name == want:
            return kind
    return None


# The bench. PER MISSION: cosmos_dev reuses one interpreter across run_next_mission, so a
# module-level dict nothing clears is the classic "works on run 1, stale on run 2". Cleared from
# the addon top level.
# How long the Stage's "Dolly to" move takes. Short - it is a check on the framing, not a
# shot, and the operator is waiting to see the end of it.
DIRECTOR_DOLLY_SECONDS = 2.5

_STAGE = {}


def _plain(text):
    """Display text with no braces and no backticks - see director_rundowns._plain.

    `<` and `>` deliberately SURVIVE: they are the overlay template delimiters, chosen because
    every other candidate is eaten somewhere on the path. See director_overlays.py.
    """
    return str(text).replace("{", "(").replace("}", ")").replace("`", "'").strip()


def director_stage_reset():
    """Empty the bench and seed each overlay kind with its first built-in preset.

    Seeded rather than blank so a director who ticks Lower third and takes the shot gets the
    ship's name on air, instead of an empty card that reads as a broken overlay.

    `bind` starts FIXED - the item takes the object that was clicked. That is what every
    existing rundown means, and a bench that defaulted to a binding would silently change what
    the Add button had always done.
    """
    from director_overlays import director_overlay_preset_rows, director_overlay_preset_fields
    from director_bind import DIRECTOR_BIND_FIXED
    _STAGE.clear()
    _STAGE.update({"subject": None, "mode_label": "Orbit", "hold": 0, "on": set(),
                   "fields": {}, "preset": {},
                   "bind": DIRECTOR_BIND_FIXED, "edit": None,
                   # 0 = frame it automatically. See director_stage_distance.
                   "distance": 0,
                   # The Console sub-tab's ticked stations. ON THE BENCH rather than living in
                   # the widget, because the tab now shares this bench with the Stage: recall
                   # has to be able to restore a console item, and Replace has to rebuild one.
                   "consoles": set()})
    for kind, _label, _fields in director_overlay_kinds():
        labels, _keys = director_overlay_preset_rows(kind)
        if not labels:
            continue
        _STAGE["preset"][kind] = labels[0]
        _STAGE["fields"][kind] = director_overlay_preset_fields(kind, labels[0])


def _bench():
    if not _STAGE:
        director_stage_reset()
    return _STAGE


# --- the shot vocabulary -----------------------------------------------------------------

def director_subject_label(subject_id):
    """What the editor calls the current subject."""
    from sbs_utils.procedural.query import to_object
    from director_cam import director_cam_point_name
    if not subject_id:
        return "none picked"
    obj = to_object(subject_id)
    if obj is None:
        return "gone"
    # A click on empty space selects the CAM - a PLACE, not a ship - and the cam is nameless
    # by design, so ask what to call a point before falling through to "unnamed".
    point = director_cam_point_name(subject_id)
    if point:
        return _plain(point)
    return _plain(getattr(obj, "name", None) or "unnamed")


def director_shot_mode_list():
    """The comma-separated labels for the shot-mode radio, in DIRECTOR_MODES order."""
    from director_rundowns import DIRECTOR_MODES, DIRECTOR_MODE_LABELS
    return ",".join(DIRECTOR_MODE_LABELS[m] for m in DIRECTOR_MODES)


def director_shot_mode_for(label):
    """The mode a radio label means. Anything unknown reads as `orbit`."""
    from director_rundowns import DIRECTOR_MODES, DIRECTOR_MODE_LABELS
    want = str(label or "").strip().lower()
    for mode in DIRECTOR_MODES:
        if DIRECTOR_MODE_LABELS[mode].lower() == want or mode == want:
            return mode
    return "orbit"


def director_shot_mode_label(mode):
    from director_rundowns import DIRECTOR_MODE_LABELS
    return DIRECTOR_MODE_LABELS.get(str(mode or "").strip().lower(), "Orbit")


# --- the bench ----------------------------------------------------------------------------
#
# Every setter restages, so an editor handler is one call. That is the whole live-preview
# contract: change anything, and every console in Preview mode is showing it within a tick.

def director_stage_subject(subject_id=None, clear=False):
    """Read or set what is being staged."""
    bench = _bench()
    if clear:
        bench["subject"] = None
        director_stage_restage()
    elif subject_id is not None:
        bench["subject"] = subject_id
        director_stage_restage()
    return bench["subject"]


def director_stage_bind(chain=None, set_it=False):
    """Read or set the staged item's SUBJECT BINDING.

    Three states, and the third is why this cannot just be a string:

        ""                       FIXED   - the item takes the object that was clicked
        "<<selected_id>>..."     BOUND   - resolved at play time against the selection
        None                     NONE    - no subject; the item is overlays only

    `None` is a VALUE here, not "no argument given", so setting it needs `set_it=True`. The
    editor's dropdown always passes it; the flag exists so a plain `director_stage_bind()`
    stays a read, which is what every status line wants.
    """
    bench = _bench()
    if set_it or chain is not None:
        bench["bind"] = chain if chain is None else str(chain)
        director_stage_restage()
    return bench.get("bind", "")


def director_stage_bind_label():
    """The picker label for the current binding."""
    from director_bind import director_bind_label_of
    return director_bind_label_of(director_stage_bind())


def director_stage_bind_set_label(label):
    """Set the binding from the dropdown's DISPLAY text. Returns the stored binding."""
    from director_bind import director_bind_for
    return director_stage_bind(director_bind_for(label), set_it=True)


def director_stage_is_overlay_only():
    """Is the bench building a furniture-only beat?"""
    return director_stage_bind() is None


def director_stage_mode_label(label=None):
    bench = _bench()
    if label is not None:
        bench["mode_label"] = director_shot_mode_label(director_shot_mode_for(label))
        director_stage_restage()
    return bench["mode_label"]


def director_stage_hold(seconds=None):
    """Read or set how long the staged item holds on air. 0 means "use the dwell".

    Zero rather than None as the bottom stop, because the control is a slider and its low end
    has to mean something: "no opinion" is the useful thing for it to mean, and a half-second
    shot would be unwatchable anyway.
    """
    bench = _bench()
    if seconds is not None:
        try:
            bench["hold"] = max(0, int(float(seconds)))
        except (TypeError, ValueError):
            bench["hold"] = 0
        director_stage_restage()
    return bench.get("hold", 0)


def director_stage_distance(units=None):
    """Read or set the staged item's explicit lens distance. 0 = frame it automatically.

    THE AUTOMATIC FRAMING IS STILL THE DEFAULT, and that matters: the hand-built distance
    sliders of the first version were deleted because a FIXED distance framed a starbase and a
    fighter equally badly. This is not those sliders - it is a per-item override, and an item
    that never touches it behaves exactly as it always did.

    IT DOES NOT RESTAGE, alone among the setters on this bench. Every other control pushes to
    Preview live, which is right for a tick or a keystroke; re-issuing the SHOT on each step of
    a slider is a cut per step. `director_stage_dolly_to` is what applies this, and being able
    to see the move rather than a cut is the whole reason there is a button.
    """
    bench = _bench()
    if units is not None:
        try:
            bench["distance"] = max(0, int(float(units)))
        except (TypeError, ValueError):
            bench["distance"] = 0
    return bench.get("distance", 0)


def director_stage_distance_auto():
    """The distance the AUTOMATIC framing would use for what is staged, or 0.

    What the slider is seeded with, so staging a fighter starts it near 1400 and a starbase
    near 4800 - a sensible number for THAT hull to nudge from, rather than a bare 0 the
    operator has to discover the scale of.

    Through director_play._framing rather than viewscreen_framing directly: that is the one
    that already knows a camera POINT is framed for a region and not for a hull.
    """
    subject = director_stage_subject_id()
    if not subject:
        return 0
    try:
        from director_play import _framing
        _near, far = _framing(subject)
        return int(far)
    except Exception:
        return 0


def director_stage_distance_display():
    """What the slider shows: the committed distance, else the automatic one."""
    return director_stage_distance() or director_stage_distance_auto()


def director_stage_distance_label():
    """One short line for the editor: what the distance control currently means."""
    units = director_stage_distance()
    if not units:
        auto = director_stage_distance_auto()
        if auto:
            return "automatic - " + str(auto) + "u"
        return "automatic"
    return "holds at " + str(units) + "u"


def director_stage_subject_id():
    """The LIVE object the bench is pointed at, resolving a binding. None when nothing is."""
    bench = _bench()
    bind = bench.get("bind", "")
    if bind is None:
        return None
    if bind:
        from director_bind import director_bind_resolve
        return director_bind_resolve(bind)
    return bench.get("subject")


def director_stage_dolly_to():
    """Move every Preview screen to the staged distance, and commit it. What the button does.

    A MOVE RATHER THAN A CUT, which is the point: the slider has already been dragged, and
    what the operator wants to judge is the framing at the end of it. `camera_dolly` is the
    library's own eased move, so this looks like the dolly the item will play.

    It deliberately does NOT restage. The running shot picks the new distance up on its next
    leg (director_play_next_leg reads it off the record), so restaging here would cut to the
    new distance a beat after this move arrived at it.
    """
    subject = director_stage_subject_id()
    if not subject:
        return False
    target = director_stage_distance_display()
    if not target:
        return False
    # Committed BEFORE the move, so an item added while the dolly is still running carries the
    # distance the operator asked for rather than the one it happens to be passing through.
    director_stage_distance(target)
    from director_modes import director_preview_screens
    screens = director_preview_screens()
    if not screens:
        return True
    start = director_stage_distance_auto() or target
    from sbs_utils.procedural.gui.camera import camera_dolly
    from sbs_utils.procedural.gui.viewscreen import ORBIT_PITCH, DOLLY_YAW
    camera_dolly(screens, subject, start, target, yaw=DOLLY_YAW, pitch=ORBIT_PITCH,
                 seconds=DIRECTOR_DOLLY_SECONDS)
    return True


def director_stage_distance_auto_set():
    """Hand the framing back to the automatic path. What the Auto button does."""
    director_stage_distance(0)
    return True


def director_stage_hold_label():
    """One short line for the editor: what the hold slider currently means."""
    seconds = director_stage_hold()
    if not seconds:
        return "holds for the dwell"
    return "holds " + str(seconds) + "s"


def director_stage_on(kind):
    """Is this overlay row ticked?"""
    return kind in _bench()["on"]


def director_stage_toggle(kind):
    """Tick or untick one overlay row. Returns the new state."""
    bench = _bench()
    if kind in bench["on"]:
        bench["on"].discard(kind)
    else:
        bench["on"].add(kind)
    director_stage_restage()
    return kind in bench["on"]


def director_stage_set_kinds(labels):
    """Replace the ticked set from the kind picker's SELECTION.

    The listbox's selection IS the enabled set, so this is a replace rather than a toggle -
    an untick is a row leaving the selection and has no event of its own.

    Labels, not kinds, because that is what a listbox of display strings hands back. An
    unrecognized one is dropped rather than stored: a kind nothing can build is an overlay
    that silently never appears.
    """
    bench = _bench()
    chosen = set()
    for label in (labels or ()):
        kind = director_overlay_kind_for(label)
        if kind is not None:
            chosen.add(kind)
    bench["on"] = chosen
    director_stage_restage()
    return sorted(chosen)


def director_stage_on_labels():
    """The picker labels of the ticked kinds - what a repaint restores the selection from."""
    return [label for kind, label, _fields in director_overlay_kinds()
            if kind in _bench()["on"]]


def director_stage_edit_kind(kind=None):
    """Read or set WHICH kind the single field editor is showing.

    Separate from the ticked set on purpose. Ticking is "does this item carry a lower third";
    editing is "whose text am I typing" - and wanting to write the hero card before ticking it
    is ordinary. One listbox meaning both would make every tick jump the boxes.

    Falls back to the first ticked kind, then to the first kind in the table, so the editor
    always has something to show and never renders an empty column.
    """
    bench = _bench()
    if kind is not None:
        bench["edit"] = kind
    current = bench.get("edit")
    known = [k for k, _l, _f in director_overlay_kinds()]
    if current in known:
        return current
    for k in known:
        if k in bench["on"]:
            return k
    return known[0] if known else None


def director_stage_edit_kind_label():
    """The picker label of the kind being edited."""
    want = director_stage_edit_kind()
    for kind, label, _fields in director_overlay_kinds():
        if kind == want:
            return label
    return ""


def director_stage_edit_set_label(label):
    """Set the edited kind from the dropdown's DISPLAY text."""
    kind = director_overlay_kind_for(label)
    if kind is not None:
        director_stage_edit_kind(kind)
    return director_stage_edit_kind()


def director_stage_edit_fields():
    """The field names of the kind being edited, in order. [] when there is no kind."""
    want = director_stage_edit_kind()
    for kind, _label, fields in director_overlay_kinds():
        if kind == want:
            return list(fields)
    return []


def director_stage_edit_field_name(index):
    """The `index`-th field name of the edited kind, or "" past the end.

    The editor unrolls DIRECTOR_OVERLAY_MAX_FIELDS rows and hides the spare ones - unrolled
    because an `on gui_message` registered in a loop captures the loop variable at its LAST
    value - so it asks positionally and needs a defined answer past the end.
    """
    fields = director_stage_edit_fields()
    return fields[index] if 0 <= index < len(fields) else ""


def director_stage_edit_field(index):
    """What is currently typed into the `index`-th field of the edited kind."""
    field = director_stage_edit_field_name(index)
    return director_stage_field(director_stage_edit_kind(), field) if field else ""


def director_stage_edit_set_field(index, text):
    """Store what was typed into the `index`-th field of the edited kind, and restage."""
    field = director_stage_edit_field_name(index)
    if not field:
        return False
    return director_stage_set_field(director_stage_edit_kind(), field, text)


def director_stage_field(kind, field):
    """The template currently typed into one field."""
    return str(_bench()["fields"].get(kind, {}).get(field, "") or "")


def director_stage_set_field(kind, field, text):
    """Store what was typed and restage. Called on every keystroke."""
    bench = _bench()
    bench["fields"].setdefault(kind, {})[field] = _plain(text)
    director_stage_restage()
    return True


def director_stage_preset(kind):
    """The preset label showing in one row's dropdown."""
    return str(_bench()["preset"].get(kind, "") or "")


def director_stage_apply_preset(kind, label):
    """Fill one row's fields from a preset. Returns True when it matched one."""
    from director_overlays import director_overlay_preset_fields
    bench = _bench()
    fields = director_overlay_preset_fields(kind, label)
    bench["preset"][kind] = _plain(label)
    if not fields:
        return False
    bench["fields"][kind] = dict(fields)
    director_stage_restage()
    return True


def director_stage_save_preset(kind, name):
    """Save one row's typed templates as a preset. Returns the stored label, or None.

    The STORED label is what goes back in the dropdown, not the string that was typed: a name
    carrying a comma cannot survive a `list:` property and comes back flattened.
    """
    from director_overlays import director_overlay_preset_save
    bench = _bench()
    label = director_overlay_preset_save(kind, name, bench["fields"].get(kind, {}))
    if not label:
        return None
    bench["preset"][kind] = label
    return label


def director_stage_overlays():
    """The overlay records for the ticked rows, templates unresolved.

    UNRESOLVED deliberately: an item is stored in a rundown and replayed against whatever it is
    pointed at, so a template baked down to "Artemis" at add time would name the wrong ship for
    every other item a generated rundown makes. Resolution happens one line before
    `overlay_kind`, in director_play.
    """
    bench = _bench()
    out = []
    for kind, _label, fields in director_overlay_kinds():
        if kind not in bench["on"]:
            continue
        entry = {"kind": kind}
        for field in fields:
            entry[field] = director_stage_field(kind, field)
        out.append(entry)
    return out


def director_stage_item():
    """The item the bench currently describes, or None when nothing is staged.

    THE BINDING DECIDES WHAT KIND OF ITEM THIS IS, which is why it is read before anything
    else. Overlay-only means there is no subject and no shot to build - the mode radio and the
    clicked object are simply not part of that item, and a bench holding both is not a
    contradiction, it is a director who has already picked a shot and is now writing a title.
    """
    bench = _bench()
    bind = bench.get("bind", "")
    if bind is None:
        from director_rundowns import director_item_overlay
        overlays = director_stage_overlays()
        if not overlays:
            return None                 # an ovl item with no furniture shows nothing at all
        return director_item_overlay(overlays=overlays, hold=bench.get("hold", 0))
    return director_shot_build(bind or bench["subject"],
                               director_shot_mode_for(bench["mode_label"]),
                               director_stage_overlays(), hold=bench.get("hold", 0),
                               distance=bench.get("distance", 0))


def director_stage_load(item):
    """Load an existing item back onto the bench - the inverse of director_stage_item.

    WHY THIS EXISTS. Without it an item already in a rundown is a dead end: to fix a typo in a
    lower third you rebuild the whole beat from scratch, and the beat is a subject, a binding, a
    mode, a hold, a distance and up to six overlays with their templates. The bench already
    holds every one of those; nothing loaded one back.

    TEMPLATES COME BACK AS TEMPLATES. An item stores `<<name>>`, not "Artemis" - that is the
    whole point of them - so the fields are copied verbatim. Resolving on the way in would bake
    the currently selected ship's name into a beat written to follow whatever it is pointed at,
    and the operator would not see the difference until it went to air naming the wrong ship.

    ALL THREE KINDS LOAD. A `con` item ticks its station in the bench's console set, which is
    why that set lives on the bench at all.
    """
    from director_bind import director_bind_is, DIRECTOR_BIND_FIXED, DIRECTOR_BIND_NONE
    if not item:
        return False
    bench = _bench()
    kind = item.get("kind")

    # The subject, and whether it is a binding. `bind` and `subject` are separate slots on the
    # bench - a bound item keeps whatever object was last clicked in `subject`, so switching the
    # picker back to Fixed does not lose it.
    declared = item.get("ship") if kind == "con" else item.get("subject")
    if kind == "ovl":
        bench["bind"] = DIRECTOR_BIND_NONE
    elif director_bind_is(declared):
        bench["bind"] = declared
    else:
        bench["bind"] = DIRECTOR_BIND_FIXED
        if declared:
            bench["subject"] = declared

    if kind == "cam":
        bench["mode_label"] = director_shot_mode_label(item.get("mode"))
        bench["distance"] = int(item.get("distance") or 0)
    if kind == "con":
        # ONE station, not a replace of the whole set: recalling three console beats one after
        # another should build the set back up rather than each one clearing the last.
        console = str(item.get("console") or "").strip()
        if console:
            bench.setdefault("consoles", set()).add(console)

    bench["hold"] = int(item.get("hold") or 0)

    # The furniture. The ticked set is REPLACED, not merged - the item is the answer to "what
    # does this beat carry", so a kind it does not carry has to come off.
    on = set()
    for entry in (item.get("overlays") or ()):
        entry_kind = entry.get("kind")
        if entry_kind is None:
            continue
        on.add(entry_kind)
        fields = {}
        for field, value in entry.items():
            if field != "kind":
                fields[field] = value
        bench.setdefault("fields", {})[entry_kind] = fields
    bench["on"] = on
    # Open the field editor on the FIRST ticked kind in picker order, so recalling a beat shows
    # the operator something they can edit rather than whichever kind the dict happened to
    # yield first. Untouched when the beat carries no furniture: whatever they were editing
    # before is a better guess than an arbitrary reset.
    for kind_name, _label, _fields in director_overlay_kinds():
        if kind_name in on:
            bench["edit"] = kind_name
            break

    director_stage_restage()
    return True


def director_stage_load_summary(item):
    """One line naming what was just recalled, for the status."""
    if not item:
        return "nothing to recall"
    return "recalled " + _plain(item.get("label"))


def director_stage_restage():
    """Push the bench to every Preview screen. Returns the item, or None.

    THE LIVE PREVIEW. Called by every setter above rather than by the editor, so there is no
    way to change a control and forget to push - which is the same "one door" reasoning
    `director_screen_enter` uses for the clear.
    """
    from director_play import director_play_stage
    item = director_stage_item()
    director_play_stage(item, clear=item is None)
    return item


def director_stage_summary():
    """One line naming what is staged - the editor's status when nothing else happened.

    FOUR CASES NOW, and "click something in the 2D view" is only right for one of them. A
    bound item does not want a click, an overlay-only item has no subject to click, and a
    bound item that cannot resolve YET is not an error - it is the ordinary state between
    writing the item and selecting something.

    THE CLASH NOTE IS APPENDED TO EVERY CASE, including "nothing staged". Ticking two overlays
    that share a slot is something an operator does BEFORE picking a subject as often as after,
    and a warning that only appears once the shot is otherwise complete is a warning that
    arrives after the mistake has been made.
    """
    from director_bind import director_bind_label, director_bind_resolve
    bench = _bench()
    bind = bench.get("bind", "")
    overlays = director_stage_overlays()
    extra = director_overlay_summary(overlays)
    note = _clash_note(overlays)

    if bind is None:
        if not overlays:
            return "overlays only - tick at least one overlay"
        return "staged overlays only [" + extra + "]" + note

    if bind:
        subject = director_bind_resolve(bind)
        where = director_subject_label(subject) if subject else "nothing selected yet"
        line = ("staged " + director_shot_mode_label(bench["mode_label"]) + " - "
                + director_bind_label(bind) + " (" + where + ")")
    else:
        if bench["subject"] is None:
            return "nothing staged - click something in the 2D view" + note
        line = ("staged " + director_shot_mode_label(bench["mode_label"]) + " - "
                + director_subject_label(bench["subject"]))

    if bench.get("hold"):
        line = line + " " + str(bench["hold"]) + "s"
    if extra:
        line = line + " [" + extra + "]"
    return line + note


def _clash_note(overlays):
    """The tail the summary carries when two ticked overlays share one slot."""
    clashes = director_overlay_slot_clash(overlays)
    if not clashes:
        return ""
    return "  - hidden behind another card: " + ", ".join(clashes)


# --- overlays -----------------------------------------------------------------------------

def director_overlay_summary(overlays):
    """One short line naming what an item carries, for a row or a status line."""
    names = []
    for entry in (overlays or ()):
        for kind, label, _fields in director_overlay_kinds():
            if entry.get("kind") == kind:
                names.append(label)
                break
    return ", ".join(names)


def director_overlay_row_label(kind):
    for row_kind, label, _fields in director_overlay_kinds():
        if row_kind == kind:
            return label
    return kind


def director_overlay_slot_clash(overlays):
    """The kinds in `overlays` that would land in a slot another one already has.

    A SLOT HOLDS ONE CARD. `lower_third` and `lower_third_portrait` (the speaker card) both
    default to the `lower_third` slot, so ticking both silently draws one over the other and
    the operator sees an overlay that "did not appear". It is an authoring mistake rather than
    a bug, but it is one nothing on screen would otherwise explain - and it only became
    possible when the picker started offering more than four kinds.

    The library's own map, not a copy: a kind that changes slot upstream must not go on being
    checked against a stale table here.
    """
    from sbs_utils.procedural.gui.overlay import _KIND_DEFAULT_SLOT
    seen = {}
    clashes = []
    for entry in (overlays or ()):
        kind = entry.get("kind")
        slot = _KIND_DEFAULT_SLOT.get(kind, "center_hero")
        if slot in seen:
            clashes.append(director_overlay_row_label(kind))
        else:
            seen[slot] = kind
    return clashes


# --- item builders ----------------------------------------------------------------------

def director_shot_build(subject_id, mode, overlays=None, hold=None, distance=None):
    """One camera item. None with no subject.

    A BINDING COUNTS AS A SUBJECT even though nothing is selected yet - it is a truthy string,
    so the `not subject_id` guard already lets it through, and that is the intended reading:
    "orbit whatever I click" is a complete item the moment it is written. Whether it can be
    SHOWN is a separate question, asked every tick by director_rundown_play_set.
    """
    if not subject_id:
        return None
    from director_rundowns import director_item_cam
    return director_item_cam(subject_id, mode, overlays=overlays, hold=hold,
                             distance=distance)


def director_stage_consoles(labels=None):
    """Read or set the Console tab's ticked stations. The selection IS the set.

    A replace rather than a toggle, for the same reason the overlay kind picker is: an untick
    is a row leaving a multi-select and has no event of its own.
    """
    bench = _bench()
    if labels is not None:
        bench["consoles"] = set(str(c).strip() for c in labels if str(c).strip())
    return sorted(bench.get("consoles") or ())


def director_stage_console_items():
    """The console items the bench currently describes - one per ticked station.

    THE SHIP COMES FROM THE BENCH, which is the whole point of the Console tab losing its own
    Ships list: the Stage's Subject/Bind row is the one place that answers "which ship", so the
    two views cannot disagree about it. A binding is passed through AS AUTHORED, so the items
    follow the selection rather than baking whatever is selected right now.
    """
    from director_rundowns import director_item_con
    bench = _bench()
    bind = bench.get("bind", "")
    if bind is None:
        return []                       # overlay-only: there is no ship to show a console of
    ship = bind or bench.get("subject")
    consoles = director_stage_consoles()
    if not ship or not consoles:
        return []
    # THE TICKED OVERLAYS COME TOO. A console beat carries furniture now, and the field it most
    # wants is `<<name>> - <<console>> - <<crew_name>>` - "Artemis - Helm - Viper". Each item
    # gets its OWN copy of each record: they are separate beats and an edit to one must not
    # reach into the others.
    overlays = director_stage_overlays()
    return [director_item_con(ship, console,
                              overlays=[dict(o) for o in overlays])
            for console in consoles]


def director_stage_console_problem():
    """Why Add would produce nothing on the Console tab, or "" when it would work.

    AUTHORING-TIME GUARD. The play set already skips a console beat that cannot be shown, so
    nothing breaks without this - but items that can never play are a mystery when they simply
    sit in the list doing nothing. This is what the status line says instead.
    """
    bench = _bench()
    if bench.get("bind", "") is None:
        return "this item is overlays only - pick a subject or a binding first"
    if not director_stage_consoles():
        return "tick at least one console"
    ship = bench.get("bind") or bench.get("subject")
    if not ship:
        return "click a ship in the 2D view, or bind to the selection"
    live = director_stage_subject_id()
    if live is None:
        # A binding with nothing selected yet. Not an error - the items are perfectly good and
        # will play the moment something is selected.
        return ""
    from sbs_utils.procedural.roles import role
    if live not in role("__player__"):
        return "that is not a player ship - a console beat needs a crewable one"
    return ""


def director_shot_console_items(ship_id, consoles):
    """One console item per selected console type, for one ship.

    Kept for a caller that has an explicit ship. `director_stage_console_items` is what the
    editor uses now, because the ship it wants is the bench's.
    """
    from director_rundowns import director_item_con
    if not ship_id or not consoles:
        return []
    return [director_item_con(ship_id, console) for console in consoles]


def director_shot_item_rows(key):
    """(labels, indexes) for the editor's list of one rundown's items.

    The MODE leads each row, because a camera item and a console item behave completely
    differently on a screen and the subject name alone does not say which is which. Labels are
    made unique: a listbox decides what is selected by comparing ITEMS with `==`, so two
    identical rows select and deselect together.
    """
    from director_rundowns import director_rundown_items_of, director_item_row_tag
    labels = []
    indexes = []
    seen = {}
    for index, item in enumerate(director_rundown_items_of(key)):
        label = director_item_row_tag(item) + " " + _plain(item.get("label"))
        if item.get("hold"):
            label = label + "  " + str(item["hold"]) + "s"
        extra = director_overlay_summary(item.get("overlays"))
        if extra:
            label = label + "  [" + extra + "]"
        n = seen.get(label, 0) + 1
        seen[label] = n
        if n > 1:
            label = label + " (" + str(n) + ")"
        labels.append(label)
        indexes.append(index)
    return labels, indexes
