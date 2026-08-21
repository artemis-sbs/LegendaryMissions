"""Rundowns: named, ordered lists of things a screen can show.

WHY THE DIRECTOR OWNS THIS INSTEAD OF USING `sbs_utils.procedural.gui.rundown`. That module
is a broadcast vision mixer and it is the right shape for ONE feed: `_SHOTS` is a single flat
table, `_DESK["program"]` is one audience and `_DESK["live"]` is one shot. The Director needs
neither of those things:

  * several rundowns SELECTED AT ONCE (unselected is off), whose items play as one set - one
    flat table cannot say which shot came from which rundown;
  * a DIFFERENT item on each screen (the wall) - one live shot cannot express that.

So the desks are not used. What IS reused is everything that fits: `shot_apply` /
`shot_furniture` take a client-id LIST and no desk, so they stay the camera vocabulary;
`camera_orbit_lens` stays the framing maths; the engine's own `exciting` value stays the
auto-director's ranking. Do not "fix" this back to `rundown_program()`.

AN ITEM is one thing a screen can show, and there are two kinds because the engine has two
unrelated mechanisms:

    {"kind": "cam", "mode": "dolly"|"orbit"|"chase"|"tactical", "subject": id,
     "label": ..., "overlays": [ {...}, ... ]}

    {"kind": "con", "label": ..., "ship": id, "console": "helm"}
                                    -> gui_reroute_client(screen, cv_show, {...})

A camera item carries a MODE, not geometry. The modes are the ones a bridge already offers -
`viewscreen.SHOT_LABELS`, the science and weapons "On Screen" list - so a Director shot and a
bridge shot are the same shot, and the framing comes from `viewscreen_framing()`, which sizes
it off the subject's own hull radius. An earlier version carried a hand-built lens offset and a
fixed distance, which framed a starbase and a fighter equally badly.

A camera item and a console item cannot be unified: one is a camera, the other is
`assign_client_to_ship` + `gui_console` + roles. Pretending otherwise is what would break.

Every public name is prefixed `director_`: an addon's `def`s become MAST globals in one flat
mission-wide namespace, last loaded wins, silently. A leading underscore is private.
"""

# --- shot modes -------------------------------------------------------------------------
# The bridge vocabulary, verbatim: these are viewscreen.MODES minus "off" (which is not a
# shot, it is handing the screen back), plus "chase". Framing is NOT a constant here - it
# comes from viewscreen_framing(subject), which scales off the hull radius so a starbase and
# a fighter both fill the frame.
DIRECTOR_MODES = ("dolly", "orbit", "chase", "tactical")
DIRECTOR_MODE_LABELS = {"dolly": "Dolly", "orbit": "Orbit",
                        "chase": "Chase", "tactical": "Tactical"}

# How many items the dynamic generators produce. "The action" is a shortlist by design - a
# rundown of forty contacts is not a rundown, it is the radar.
DIRECTOR_ACTION_COUNT = 6
DIRECTOR_SCENERY_COUNT = 8

# The bridge wall's console types. Kept in step with CV_CONSOLES by a setter rather than
# duplicated, so the Shot tab's picker and this generator cannot drift.
_BRIDGE_CONSOLES = ["helm", "weapons", "science", "engineering", "comms", "mainscreen"]

# key -> {"key", "label", "items": [...]} for the rundowns a person built.
# PER MISSION. `director_rundowns_reset()` is called from the addon's top level, which runs
# on every story load - cosmos_dev reuses one interpreter across run_next_mission, so a
# module-level dict that nothing clears is the classic "works on run 1, broken on run 2".
_RUNDOWNS = {}


def director_bridge_consoles_set(consoles):
    """Point the bridge-wall generator at the mission's console list (CV_CONSOLES)."""
    global _BRIDGE_CONSOLES
    if consoles:
        _BRIDGE_CONSOLES = [str(c).strip() for c in consoles if str(c).strip()]
    return list(_BRIDGE_CONSOLES)


def director_rundowns_reset():
    """Drop every user-built rundown. Called from the addon top level, per mission."""
    _RUNDOWNS.clear()


def _plain(text):
    """Display text with no braces and no backticks.

    A `{` would be re-run as an f-string by the MAST assignment that receives it, and a
    backtick is the `$text:` quoting delimiter and would end the quote early.
    """
    return str(text).replace("{", "(").replace("}", ")").replace("`", "'").strip()


def _name_of(obj, fallback="unnamed"):
    return _plain(getattr(obj, "name", None) or fallback)


def _exciting(obj):
    """One object's `exciting` value as a float, 0.0 when it has none. Never raises.

    The ENGINE's own notion - the value its automatic cinematic camera follows - so a
    Director shortlist agrees with what the engine would have picked rather than being a
    second opinion invented here. Unscored is boring, not an error: headless nothing
    populates this at all and every object reads 0.0, which is why the callers also sort by
    id (a total, stable order).
    """
    from sbs_utils.procedural.query import get_data_set_value
    try:
        return float(get_data_set_value(obj.id, "exciting", 0) or 0.0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


# --- item constructors ------------------------------------------------------------------

def _hold(seconds):
    """A per-item hold in whole seconds, or None for "use the operator's dwell".

    0 and negatives mean None rather than "cut instantly": the control that sets this is a
    slider whose bottom stop has to mean something, and "no opinion" is the useful thing for it
    to mean. A hold of half a second would be unwatchable anyway.
    """
    try:
        seconds = int(float(seconds))
    except (TypeError, ValueError):
        return None
    return seconds if seconds > 0 else None


def director_item_cam(subject_id, mode="orbit", label=None, overlays=None, hold=None):
    """A camera item: a subject, one of DIRECTOR_MODES, and optionally how long it holds.

    Geometry is resolved at play time from `viewscreen_framing`, so the same item frames
    correctly whatever it ends up pointed at - and a subject that grows a bigger hull between
    builds does not need the item rewritten.

    `hold` is seconds on air, overriding the operator's dwell for this item alone - an
    establishing shot that wants ten seconds next to action beats that want three. Absent means
    the dwell decides. It IS part of the item's identity (director_item_ident), so the same
    shot held for three seconds and for ten are two different beats and a rundown can hold
    both - but it is NOT part of the SHOT key, so cutting between them keeps the camera
    running.
    """
    from sbs_utils.procedural.query import to_object
    mode = str(mode).strip().lower()
    if mode not in DIRECTOR_MODES:
        mode = "orbit"
    if label is None:
        label = DIRECTOR_MODE_LABELS[mode] + " - " + _name_of(to_object(subject_id))
    return {"kind": "cam", "mode": mode, "subject": subject_id,
            "label": _plain(label), "overlays": list(overlays or ()),
            "hold": _hold(hold)}


def director_item_con(ship_id, console, label=None, hold=None):
    """A console item: show `console` for `ship_id` on whichever screen gets this."""
    console = str(console).strip()
    if label is None:
        from sbs_utils.procedural.query import to_object
        label = console.capitalize() + " - " + _name_of(to_object(ship_id), "no ship")
    return {"kind": "con", "label": _plain(label), "ship": ship_id, "console": console,
            "hold": _hold(hold)}


def director_item_key(item):
    """Which SHOT this is: subject + mode. NOT what makes two items different.

    Not the label: two rundowns can name the same shot differently and it is still one shot,
    and a label that changes with the subject's name would break any comparison built on it.

    Use this only where "is the camera pointed at the same thing the same way" is the actual
    question - which is one place, the player's re-route tracking. For "are these the same
    item", use director_item_ident.
    """
    if item is None:
        return None
    if item.get("kind") == "con":
        return ("con", item.get("ship"), item.get("console"))
    return ("cam", item.get("subject"), item.get("mode"))


def director_item_overlay_ident(item):
    """A hashable fingerprint of an item's FURNITURE."""
    out = []
    for entry in ((item or {}).get("overlays") or ()):
        out.append(tuple(sorted((str(k), str(v)) for k, v in entry.items())))
    return tuple(out)


def director_item_ident(item):
    """Which ITEM this is - the whole beat: shot, furniture and hold.

    THE SHOT IS NOT THE ITEM, and conflating them cost a whole feature. A rundown legitimately
    holds "wide on the station with a lower third, seven seconds" followed by "the same shot,
    clean" - two beats of one shot, and that is ordinary direction, not a mistake. Keyed on
    subject + mode alone, the second Add answered "already in that rundown" and did nothing,
    and the play set would have dropped it even if it had gone in.

    Two items are the same only when everything about them matches, so a double-click still
    collapses and a generated orbit of Artemis appearing in two rundowns still collapses.
    """
    if item is None:
        return None
    return (director_item_key(item), director_item_overlay_ident(item), item.get("hold"))


def director_item_subject(item):
    """The object an item needs alive - the subject for a camera, the ship for a console."""
    if item is None:
        return None
    return item.get("ship") if item.get("kind") == "con" else item.get("subject")


def _shot(subject_id, mode):
    return director_item_cam(subject_id, mode)


# --- the generators ---------------------------------------------------------------------
#
# Functions, not stored lists, and re-evaluated every time the play set is computed - so a
# rundown tracks ships that spawn and die instead of going stale the moment it was chosen.
# Each sorts by id, because `role()` returns a SET: without a total order the wall would
# reshuffle on every dwell and read as a fault rather than as direction.


def _player_ships():
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.query import to_object
    out = []
    for sid in sorted(role("__player__") - role("director_cam")):
        obj = to_object(sid)
        if obj is not None:
            out.append(obj)
    return out


def director_rundown_gen_bridge():
    """A console item per console type per player ship - the classic Director multiview."""
    items = []
    for ship in _player_ships():
        for console in _BRIDGE_CONSOLES:
            items.append(director_item_con(ship.id, console,
                                           console.capitalize() + " - " + _name_of(ship)))
    return items


def director_rundown_gen_players():
    """A slow orbit of each player ship."""
    return [_shot(ship.id, "orbit") for ship in _player_ships()]


def director_rundown_gen_action():
    """Chase shots on the most exciting objects right now, best first.

    A shortlist, not the radar. Ties break on the lowest id so a quiet moment - or a headless
    run, where nothing populates `exciting` at all and everything reads 0.0 - produces a
    steady order rather than a different one every evaluation.
    """
    from sbs_utils.procedural.roles import any_role, role
    from sbs_utils.procedural.query import to_object
    ranked = []
    for oid in (any_role("__player__,__npc__") - role("director_cam")):
        obj = to_object(oid)
        if obj is None:
            continue
        ranked.append((-_exciting(obj), oid, obj))
    ranked.sort(key=lambda t: (t[0], t[1]))
    # CHASE for the action: these are moving ships in a fight, and a chase holds them in
    # frame where an orbit would swing away from what is happening.
    return [_shot(obj.id, "chase") for _v, _i, obj in ranked[:DIRECTOR_ACTION_COUNT]]


def director_rundown_gen_scenery():
    """Orbits of stations and NAMED terrain - the establishing shots between fights.

    Named terrain only, and capped. A map carries well over a thousand terrain objects; an
    uncapped generator would turn a rundown into a scrollbar, and the unnamed ones are
    asteroids nobody wants a shot of.
    """
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.query import to_object
    items = []
    for sid in sorted(role("station")):
        obj = to_object(sid)
        if obj is not None:
            items.append(_shot(sid, "orbit"))
    for tid in sorted(role("__terrain__")):
        if len(items) >= DIRECTOR_SCENERY_COUNT:
            break
        obj = to_object(tid)
        if obj is None or not getattr(obj, "name", None):
            continue
        items.append(_shot(tid, "orbit"))
    return items[:DIRECTOR_SCENERY_COUNT]


# key -> (label, generator). Order here is the order in the picker.
_GENERATORS = (
    ("bridge", "Bridge wall", director_rundown_gen_bridge),
    ("players", "Player ships", director_rundown_gen_players),
    ("action", "The action", director_rundown_gen_action),
    ("scenery", "Stations & terrain", director_rundown_gen_scenery),
)


# --- the registry -----------------------------------------------------------------------

def director_rundown_new(name):
    """Create an empty user rundown. Returns its key; an existing one is returned as is."""
    label = _plain(name)
    if not label:
        return None
    key = "u:" + label.lower()
    if key not in _RUNDOWNS:
        _RUNDOWNS[key] = {"key": key, "label": label, "items": []}
    return key


def director_rundown_delete(key):
    return _RUNDOWNS.pop(key, None) is not None


def director_rundown_rename(key, name):
    label = _plain(name)
    record = _RUNDOWNS.get(key)
    if record is None or not label:
        return False
    record["label"] = label
    return True


def director_rundown_add_item(key, item):
    """Append an item to a user rundown, skipping one it already holds.

    "Already holds" means the same BEAT - see director_item_ident. The same shot with different
    furniture or a different hold is a different beat and goes in.
    """
    record = _RUNDOWNS.get(key)
    if record is None or item is None:
        return False
    ident = director_item_ident(item)
    for existing in record["items"]:
        if director_item_ident(existing) == ident:
            return False
    record["items"].append(item)
    return True


def director_rundown_item_remove(key, index):
    record = _RUNDOWNS.get(key)
    if record is None or index is None or not (0 <= index < len(record["items"])):
        return False
    record["items"].pop(index)
    return True


def director_rundown_item_move(key, index, delta):
    """Move an item up or down. A rundown is ORDERED, so this is not a nicety."""
    record = _RUNDOWNS.get(key)
    if record is None or index is None:
        return None
    items = record["items"]
    target = index + delta
    if not (0 <= index < len(items)) or not (0 <= target < len(items)):
        return None
    items[index], items[target] = items[target], items[index]
    return target


def director_rundown_items_of(key):
    """One rundown's items - generated fresh for a generator, stored for a user one."""
    for gen_key, _label, fn in _GENERATORS:
        if key == gen_key:
            return fn()
    record = _RUNDOWNS.get(key)
    return list(record["items"]) if record else []


def director_rundown_user_keys():
    """(keys, labels) of the user-built rundowns - for the Shot tab's "Add to" dropdown."""
    keys = list(_RUNDOWNS)
    return keys, [_RUNDOWNS[k]["label"] for k in keys]


def director_rundown_key_for(label):
    """The user rundown whose display name is `label`, or None.

    A dropdown carries display TEXT, not keys, so the selection has to be mapped back. Two
    rundowns can be renamed to the same thing; the first match is the honest answer and the
    rename UI is where a person notices the clash.
    """
    want = _plain(label)
    if not want:
        return None
    for key in _RUNDOWNS:
        if _RUNDOWNS[key]["label"] == want:
            return key
    return None


def director_rundown_rows():
    """(labels, keys) for the main page's multi-select rundown list.

    Each row carries its live item count, because "Bridge wall 12" tells an operator what
    Send is about to do and a bare name does not.
    """
    labels = []
    keys = []
    seen = {}
    for key, label, fn in _GENERATORS:
        labels.append(label + "   " + str(len(fn())))
        keys.append(key)
    for key in _RUNDOWNS:
        record = _RUNDOWNS[key]
        label = record["label"] + "   " + str(len(record["items"]))
        # Unique labels are load-bearing: a listbox decides what is selected by comparing
        # ITEMS with ==, so two identical rows select and deselect together.
        n = seen.get(label, 0) + 1
        seen[label] = n
        if n > 1:
            label = label + " (" + str(n) + ")"
        labels.append(label)
        keys.append(key)
    return labels, keys


def director_rundown_play_set(keys):
    """The ordered, de-duplicated, still-alive union of the selected rundowns' items.

    Multi-select means unselected is OFF, so this is the whole of what plays. Dead subjects
    are dropped HERE rather than by a destroy hook: a delete is tombstoned immediately, so
    `to_object()` reports gone on the same frame, and filtering at play time also covers
    objects that were removed without ever being destroyed.
    """
    from sbs_utils.procedural.query import to_object
    out = []
    seen = set()
    for key in (keys or []):
        for item in director_rundown_items_of(key):
            subject = director_item_subject(item)
            if subject is None or to_object(subject) is None:
                continue
            ident = director_item_ident(item)
            if ident in seen:
                continue
            seen.add(ident)
            out.append(item)
    return out


def director_rundown_play_labels(keys):
    """Just the labels of the play set - for a status line or a preview list."""
    return [item["label"] for item in director_rundown_play_set(keys)]
