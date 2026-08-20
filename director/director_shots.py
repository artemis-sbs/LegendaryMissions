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

# The overlay rows the editor offers, in order: (kind, label, field names).
# The fields are the ones each builder ACTUALLY reads (overlay.py) - a field the builder does
# not read is a text box that silently does nothing, which is worse than not offering it.
DIRECTOR_OVERLAY_ROWS = (
    ("lower_third", "Lower third", ("name", "line")),
    ("hero", "Hero", ("title", "subtitle")),
    ("banner", "Top status", ("text",)),
    ("letterbox", "Letterbox", ("line",)),
)

# The bench. PER MISSION: cosmos_dev reuses one interpreter across run_next_mission, so a
# module-level dict nothing clears is the classic "works on run 1, stale on run 2". Cleared from
# the addon top level.
_STAGE = {}


def _plain(text):
    """Display text with no braces and no backticks - see director_rundowns._plain.

    `<` and `>` deliberately SURVIVE: they are the overlay template delimiters, chosen because
    every other candidate is eaten somewhere on the path. See director_overlays.py.
    """
    return str(text).replace("{", "(").replace("}", ")").replace("`", "'").strip()


def director_stage_reset():
    """Empty the bench and seed each overlay row with its first built-in preset.

    Seeded rather than blank so a director who ticks Lower third and takes the shot gets the
    ship's name on air, instead of an empty card that reads as a broken overlay.
    """
    from director_overlays import director_overlay_preset_rows, director_overlay_preset_fields
    _STAGE.clear()
    _STAGE.update({"subject": None, "mode_label": "Orbit", "on": set(),
                   "fields": {}, "preset": {}})
    for kind, _label, _fields in DIRECTOR_OVERLAY_ROWS:
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
    if not subject_id:
        return "none picked"
    obj = to_object(subject_id)
    if obj is None:
        return "gone"
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


def director_stage_mode_label(label=None):
    bench = _bench()
    if label is not None:
        bench["mode_label"] = director_shot_mode_label(director_shot_mode_for(label))
        director_stage_restage()
    return bench["mode_label"]


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
    for kind, _label, fields in DIRECTOR_OVERLAY_ROWS:
        if kind not in bench["on"]:
            continue
        entry = {"kind": kind}
        for field in fields:
            entry[field] = director_stage_field(kind, field)
        out.append(entry)
    return out


def director_stage_item():
    """The item the bench currently describes, or None when nothing is staged."""
    bench = _bench()
    return director_shot_build(bench["subject"], director_shot_mode_for(bench["mode_label"]),
                               director_stage_overlays())


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
    """One line naming what is staged - the editor's status when nothing else happened."""
    bench = _bench()
    if bench["subject"] is None:
        return "nothing staged - click something in the 2D view"
    line = "staged " + director_shot_mode_label(bench["mode_label"]) + " - " \
        + director_subject_label(bench["subject"])
    extra = director_overlay_summary(director_stage_overlays())
    if extra:
        line = line + " [" + extra + "]"
    return line


# --- overlays -----------------------------------------------------------------------------

def director_overlay_summary(overlays):
    """One short line naming what an item carries, for a row or a status line."""
    names = []
    for entry in (overlays or ()):
        for kind, label, _fields in DIRECTOR_OVERLAY_ROWS:
            if entry.get("kind") == kind:
                names.append(label)
                break
    return ", ".join(names)


def director_overlay_row_label(kind):
    for row_kind, label, _fields in DIRECTOR_OVERLAY_ROWS:
        if row_kind == kind:
            return label
    return kind


# --- item builders ----------------------------------------------------------------------

def director_shot_build(subject_id, mode, overlays=None):
    """One camera item. None with no subject."""
    if not subject_id:
        return None
    from director_rundowns import director_item_cam
    return director_item_cam(subject_id, mode, overlays=overlays)


def director_shot_console_items(ship_id, consoles):
    """One console item per selected console type, for one ship."""
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
    from director_rundowns import director_rundown_items_of
    labels = []
    indexes = []
    seen = {}
    for index, item in enumerate(director_rundown_items_of(key)):
        if item.get("kind") == "con":
            tag = "con  "
        else:
            tag = (item.get("mode") or "orbit")[:5].ljust(5)
        label = tag + " " + _plain(item.get("label"))
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
