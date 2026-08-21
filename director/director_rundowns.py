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

AN ITEM is one thing a screen can show, and there are three kinds:

    {"kind": "cam", "mode": "dolly"|"orbit"|"chase"|"tactical", "subject": id,
     "label": ..., "overlays": [ {...}, ... ], "distance": units|None}

    {"kind": "con", "label": ..., "ship": id, "console": "helm", "overlays": [ ... ]}
                                    -> gui_reroute_client(screen, cv_show, {...})

    {"kind": "ovl", "label": ..., "overlays": [ {...}, ... ]}

A camera item's SUBJECT may be an object id or a BINDING - a `<<selected_id>>` chain resolved
at play time against whatever the director has clicked (director_bind.py). The item model does
not care which: it stores what it was given and asks `director_item_subject_id` for a live id
at the point of use. That is what lets ONE authored item mean "orbit whatever I am pointing at"
and be re-pointed mid-show without touching the rundown.

THE THIRD KIND IS NOT A SHOT. An `ovl` item has no subject and no camera - it changes only what
is drawn OVER whatever is already on air, which is what a title, an intro, an outro or a
speaker card is. It is deliberately not a camera item with an empty subject: every liveness
test here asks "does this item name something that still exists", and an item that names
nothing ON PURPOSE has to be distinguishable from one whose ship blew up.

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

# The crew stations a GENERATED console beat is allowed to use.
#
# NOT `CV_CONSOLES`. That list is what the editor offers when a person is building a console
# item by hand, and it carries `mainscreen` and `cinematic` - neither of which is a crew view.
# `cinematic` is the worse of the two: `cv_show` gives it a full-screen `3dview` with
# `cv_shot=None`, so it is a 3D window with no camera applied to it. A generated rundown that
# cut to one would look like a fault.
DIRECTOR_CREW_CONSOLES = ("helm", "weapons", "science", "comms")

# key -> {"key", "label", "items": [...]} for the rundowns a person built.
# PER MISSION. `director_rundowns_reset()` is called from the addon's top level, which runs
# on every story load - cosmos_dev reuses one interpreter across run_next_mission, so a
# module-level dict that nothing clears is the classic "works on run 1, broken on run 2".
_RUNDOWNS = {}


def director_rundowns_reset():
    # The collapse memory goes with the rundowns it names.
    _TREE_COLLAPSE.clear()
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


def _distance(units):
    """An explicit lens distance in world units, or None for "frame it automatically".

    0 and negatives mean None rather than "sit on top of it": the control that sets this is a
    slider whose bottom stop has to mean something, and automatic is the useful thing for it to
    mean - a camera at zero units would be inside the hull.
    """
    try:
        units = float(units)
    except (TypeError, ValueError):
        return None
    return units if units > 0 else None


def director_item_cam(subject_id, mode="orbit", label=None, overlays=None, hold=None,
                      distance=None):
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

    `distance` is the same bargain for the LENS. Absent means the automatic framing above,
    which is the right answer almost always and is why the hand-built distance sliders of the
    first version were deleted - a FIXED distance framed a starbase and a fighter equally
    badly. This is not those sliders: it is a per-item override for the shot that wants a
    specific look, and the automatic path is untouched when it is absent.
    """
    from director_bind import director_bind_is, director_bind_label
    mode = str(mode).strip().lower()
    if mode not in DIRECTOR_MODES:
        mode = "orbit"
    if label is None:
        # A BOUND subject must never reach to_object, and must never bake a ship name into the
        # label either: the point of the binding is that it names a different ship whenever the
        # director clicks a different contact, so a row reading "Orbit - Artemis" would be a lie
        # the moment it was written.
        if director_bind_is(subject_id):
            label = DIRECTOR_MODE_LABELS[mode] + " - " + director_bind_label(subject_id)
        else:
            from sbs_utils.procedural.query import to_object
            label = DIRECTOR_MODE_LABELS[mode] + " - " + _name_of(to_object(subject_id))
    return {"kind": "cam", "mode": mode, "subject": subject_id,
            "label": _plain(label), "overlays": list(overlays or ()),
            "hold": _hold(hold), "distance": _distance(distance)}


def director_item_con(ship_id, console, label=None, hold=None, overlays=None):
    """A console item: show `console` for `ship_id` on whichever screen gets this.

    `ship_id` may be a BINDING, exactly like a camera item's subject - "the selected ship's
    weapons console" is one item that follows whoever the director clicks, against one item
    per console per ship that goes stale the moment the roster changes.

    The subject has to resolve to a PLAYER SHIP for the beat to play, and that is checked
    where every other skip lives - director_rundown_play_set. A console view of an asteroid
    would assign a screen to the asteroid and draw helm widgets for it.

    IT CARRIES FURNITURE NOW. It could not, which is why the stock bridge rundown went to air
    unlabelled: the field a lower third most wants on a console beat is
    `<<name>> - <<console>> - <<crew_name>>`, and two of those three are properties of the BEAT
    and the person at that station rather than of the ship. See director_overlays._ITEM_TOKENS.
    """
    from director_bind import director_bind_is, director_bind_label
    console = str(console).strip()
    if label is None:
        # The same rule as director_item_cam, and it was missing here: `to_object` on a
        # binding answers None, so every bound console item was labelled "Helm - no ship".
        if director_bind_is(ship_id):
            label = console.capitalize() + " - " + director_bind_label(ship_id)
        else:
            from sbs_utils.procedural.query import to_object
            label = console.capitalize() + " - " + _name_of(to_object(ship_id), "no ship")
    return {"kind": "con", "label": _plain(label), "ship": ship_id, "console": console,
            "overlays": list(overlays or ()), "hold": _hold(hold)}


def director_item_overlay(label=None, overlays=None, hold=None):
    """An overlay-only item: furniture, no shot.

    The camera is left exactly as it is - a title belongs OVER the shot that is running, not
    instead of it - so this never causes a reroute. `director_play_plan` is where that is
    actually enforced; there is nothing here that could.

    A default label rather than a blank one, because the row is the only thing that says what
    the beat carries and an empty row reads as a broken item.
    """
    overlays = list(overlays or ())
    if label is None:
        kinds = [str(entry.get("kind", "")).replace("_", " ") for entry in overlays]
        label = ", ".join(k for k in kinds if k) or "no overlays"
    return {"kind": "ovl", "label": _plain(label), "overlays": overlays,
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
    kind = item.get("kind")
    if kind == "con":
        return ("con", item.get("ship"), item.get("console"))
    if kind == "ovl":
        # No shot at all, so EVERY ovl item shares one key - none of them may ever read as a
        # new shot. director_play_plan inherits the running shot's key instead of using this.
        return ("ovl", None, None)
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

    THE DISTANCE IS IN HERE FOR THE SAME REASON THE HOLD IS. "Wide on the station, then push
    in on it" is two beats of one shot, and a rundown has to be able to hold both - but the
    SHOT key is unchanged across them, so cutting between them keeps the camera running and
    only the lens moves.
    """
    if item is None:
        return None
    return (director_item_key(item), director_item_overlay_ident(item),
            item.get("hold"), item.get("distance"))


def director_item_subject(item):
    """What an item DECLARES as its subject - an id, a binding string, or None.

    AS AUTHORED, not resolved: a binding comes back as the `<<selected_id>>` string it was
    written as. `None` means the item declares no subject at all, which is a different thing
    from a subject that has died - see director_rundown_play_set, which needs to tell them
    apart to know whether to skip the item.
    """
    if item is None:
        return None
    kind = item.get("kind")
    if kind == "ovl":
        return None
    return item.get("ship") if kind == "con" else item.get("subject")


def director_item_subject_id(item):
    """The LIVE object id an item is pointed at right now, or None.

    The resolved twin of director_item_subject, and the one every CONSUMER wants: the play
    set's liveness test, the excitement ranking, the camera, the overlay templates and the
    reroute all need an id the engine will accept.

    KEPT SEPARATE rather than folded in, and that separation is the whole reason a bound item
    works. The item's IDENTITY is built from the authored subject, so a bound item whose
    selection moves is still the same item in the rundown - only what it is pointed at
    changed. Resolving inside director_item_subject would move `director_item_ident` on every
    click, `_index_of` would lose `_PROGRAM_HELD`, and the feed would snap back to the top of
    the play set each time the operator selected something.

    IT DOES NOT CHECK LIVENESS, and deliberately: "what is this pointed at" and "is that still
    alive" are two questions, and the second one belongs in the one place that has always asked
    it - director_rundown_play_set. Folding it in here would put a `to_object` call behind the
    excitement ranking and every reroute as well, several times a second per screen, to answer
    a question those callers do not have.

    A BINDING is the exception, and it is not one really: resolution itself validates the last
    hop, because a chain that arrives at a corpse has genuinely failed to resolve rather than
    resolved to something dead.
    """
    declared = director_item_subject(item)
    if declared is None:
        return None
    from director_bind import director_bind_is, director_bind_resolve
    if director_bind_is(declared):
        return director_bind_resolve(declared)
    return declared


def _shot(subject_id, mode, overlays=None):
    return director_item_cam(subject_id, mode, overlays=overlays)


def _overlay(kind, **fields):
    """One overlay record for a generated beat.

    TEMPLATES, NOT TEXT, and that is the whole reason generated rundowns can carry furniture
    at all: a generator makes one item per ship, so there is nowhere to type "Artemis".
    `<<name>>` resolves against whatever the beat is pointed at, one line before `overlay_kind`
    - which for a BOUND beat is a different ship every time the director clicks.
    """
    entry = {"kind": kind}
    entry.update(fields)
    return entry


# The furniture the stock rundowns wear. Kept beside each other rather than inline so the
# generators read as one line per beat, and so what a new operator first sees on air is in one
# place to argue with. These mirror director_overlays._BUILTIN, which is what the editor's
# preset picker offers - a generated beat and a hand-built one should look the same on screen.
_OVL_SHIP_ID = {"kind": "lower_third", "name": "<<name>>", "line": "<<class>>"}
_OVL_CONDITION = {"kind": "banner",
                  "text": "<<name>>  hull <<hull|--%>>  shields <<shields|--%>>"}
_OVL_ESTABLISH = {"kind": "hero", "title": "<<name>>", "subtitle": "<<class|>>"}
# "Artemis - Helm" over "Viper". `<<console>>` and `<<crew_name>>` are ITEM tokens - the beat
# knows which station it is, and the person is found by matching that station against the
# ship's `consoles` link. `|unmanned` because an empty seat is the ordinary case on a small
# bridge and a blank second line reads as a broken card.
_OVL_STATION = {"kind": "lower_third", "name": "<<name>> - <<console>>",
                "line": "<<crew_name|unmanned>>"}


# --- the generators ---------------------------------------------------------------------
#
# Functions, not stored lists, and re-evaluated every time the play set is computed - so a
# rundown tracks ships that spawn and die instead of going stale the moment it was chosen.
# Each sorts by id, because `role()` returns a SET: without a total order the feed would
# reshuffle on every dwell and read as a fault rather than as direction.
#
# WHAT WENT, AND WHY. `director_rundown_gen_bridge` - "Bridge wall" - generated a console item
# per console per player ship, twelve rows for a two-ship roster. Its premise died with the
# screen-distribution model: every program screen shows the SAME item, so those twelve beats
# were never a wall, they were a twelve-beat rotation the one program feed cycled through on a
# dwell. Cutting to what the weapons officer is seeing is a real broadcast move; cycling all of
# them for every ship is noise. `director_rundown_gen_crew` is what a director actually wanted
# from it - the SELECTED ship's stations, four rows, following whoever they click.


def _player_ships():
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.query import to_object
    out = []
    for sid in sorted(role("__player__") - role("director_cam")):
        obj = to_object(sid)
        if obj is not None:
            out.append(obj)
    return out


def director_rundown_gen_follow():
    """Three beats that all follow whatever the director has clicked. No object is named.

    THE SHOWCASE FOR THE BINDING, and the one rundown that needs no setup: send it, then point
    at things. The middle beat is the one worth having - "chase what the selected ship is
    shooting at" - and it falls back to the ship itself when the weapons officer has no target,
    so it is a shot rather than a gap for most of a fight.

    With nothing selected all three fail to resolve and are skipped by the play set, so this
    shows three rows and plays none. That is the ordinary rule, not a special case.
    """
    return [
        _shot("<<selected_id>>", "orbit", [dict(_OVL_SHIP_ID)]),
        _shot("<<selected_id>><<weapons_selection>>", "chase", [dict(_OVL_SHIP_ID)]),
        _shot("<<selected_id>>", "tactical"),
    ]


def director_rundown_gen_crew():
    """The SELECTED ship's crew stations - what replaced the bridge wall.

    Four bound rows that follow whoever the director clicks, rather than one row per console
    per ship naming hulls that may not exist by the time the rundown is sent.

    DIRECTOR_CREW_CONSOLES, not CV_CONSOLES: `mainscreen` and `cinematic` are not crew views,
    and a `cinematic` console beat is a full-screen 3dview with no camera applied to it.

    A beat whose selection is not a player ship is skipped by the play set - see
    director_rundown_play_set. Clicking a rock ignores the console list rather than showing
    helm widgets for an asteroid.
    """
    return [director_item_con("<<selected_id>>", console, overlays=[dict(_OVL_STATION)])
            for console in DIRECTOR_CREW_CONSOLES]


def director_rundown_gen_players():
    """A slow orbit of each player ship, with its name and class on a lower third."""
    return [_shot(ship.id, "orbit", [dict(_OVL_SHIP_ID)]) for ship in _player_ships()]


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
    #
    # A CONDITION BANNER rather than a lower third, because this is the fight: hull and shields
    # are what a viewer wants off a ship that is being shot at, and the top strip is where a
    # broadcast puts a running score. `|--%` so a rock or an unscanned contact reads as unknown
    # instead of blank.
    return [_shot(obj.id, "chase", [dict(_OVL_CONDITION)])
            for _v, _i, obj in ranked[:DIRECTOR_ACTION_COUNT]]


def director_rundown_gen_scenery():
    """Orbits of stations and NAMED terrain - the establishing shots between fights.

    Named terrain only, and capped. A map carries well over a thousand terrain objects; an
    uncapped generator would turn a rundown into a scrollbar, and the unnamed ones are
    asteroids nobody wants a shot of.

    A HERO CARD, because these are the establishing shots: the beat between fights that says
    where you are. `<<class|>>` with an EMPTY fallback - a station has a hull class worth
    naming and a gas cloud does not, and a subtitle reading "--" under a title card looks
    broken where no subtitle at all looks deliberate.
    """
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.query import to_object
    items = []
    for sid in sorted(role("station")):
        obj = to_object(sid)
        if obj is not None:
            items.append(_shot(sid, "orbit", [dict(_OVL_ESTABLISH)]))
    for tid in sorted(role("__terrain__")):
        if len(items) >= DIRECTOR_SCENERY_COUNT:
            break
        obj = to_object(tid)
        if obj is None or not getattr(obj, "name", None):
            continue
        items.append(_shot(tid, "orbit", [dict(_OVL_ESTABLISH)]))
    return items[:DIRECTOR_SCENERY_COUNT]


# key -> (label, generator). Order here is the order in the picker.
#
# FOLLOW FIRST, because it is the only one that needs no setup at all: send it and point at
# things. "bridge" is gone - see the note above the generators.
_GENERATORS = (
    ("follow", "Follow the selection", director_rundown_gen_follow),
    ("crew", "Crew consoles", director_rundown_gen_crew),
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


def director_rundown_item_replace(key, index, item):
    """Overwrite one item in place. What Replace does after recalling a beat onto the bench.

    NO DEDUPE, deliberately, where `director_rundown_add_item` has one. Add is "put this beat
    in the rundown", so answering "you already have it" is right; Replace is "make row 4 be
    this", and refusing because row 7 already matches would leave the operator staring at a
    row that did not change with no way to see why. Replacing a beat with a copy of one two
    rows down is also an ordinary thing to do while working.
    """
    record = _RUNDOWNS.get(key)
    if record is None or item is None or index is None:
        return False
    if not (0 <= index < len(record["items"])):
        return False
    record["items"][index] = item
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


# Row labels that should render GREEN - the on-air item and the rundown holding it. A module
# set rather than something carried on the row, because a listbox decides what is SELECTED by
# comparing items with `==`: a label that changed as the feed advanced would drop the
# operator's selection every time the show moved on. The labels stay stable and the colour is
# looked up beside them. Rebuilt by director_rundown_tree_rows on every build.
_TREE_GREEN = set()

# rundown key -> is its branch shut. REMEMBERED ACROSS REBUILDS, because a rebuild makes NEW
# header objects and `on_collapse_header` toggles the OLD ones in place - so without this every
# repaint throws the operator's collapse away, and this page repaints whenever the feed
# advances. Per mission, like every other module container here.
_TREE_COLLAPSE = {}

# (tag, label, is_header, idents) for the rows of the CURRENT build. What lets the green move
# with `gui_update` instead of a repaint - see director_tree_recolor.
_TREE_ROWS = []


def director_tree_remember_collapse(lb, keys):
    """Record which branches are shut, read off the LIVE listbox before it is rebuilt.

    From the widget rather than from a click handler: collapse is handled inside the listbox
    (`on_collapse_header` flips `item.collapse` and re-presents), so there is no handler of ours
    it passes through and the widget is the only thing that knows.
    """
    if lb is None or not keys:
        return
    items = getattr(lb, "unfiltered_items", None) or []
    for item, key in zip(items, keys):
        if key and key[0] == "run" and hasattr(item, "collapse"):
            _TREE_COLLAPSE[key[1]] = bool(item.collapse)


def director_tree_collapse_reset():
    """Open every branch again - per mission, from the addon top level."""
    _TREE_COLLAPSE.clear()


class _TreeRow:
    """One item row under a rundown header. An OBJECT, not a string, and that is the point.

    LayoutListbox indents a row by `item.indent * indent_pixels`, reading the attribute off the
    ITEM - so a plain string row has no indent to read and draws flush against the header above
    it however deep it logically sits. Carrying `indent` is how the listbox's OWN indent
    applies, rather than faking one with row padding.

    `visual_indent` too, because the listbox checks that first and falls back to `indent`.
    """

    __slots__ = ("label", "indent", "visual_indent", "tag")

    def __init__(self, label, indent=1, tag=None):
        self.label = label
        self.indent = indent
        self.visual_indent = indent
        self.tag = tag

    def __str__(self):
        return self.label


def _row_props(label, is_header, green):
    """The props string for one tree row. ONE source of truth for the colour.

    The template and `director_tree_recolor` both go through here, so a row built green and a
    row recoloured green cannot disagree - and `gui_update` REPLACES the whole props string, so
    it has to carry the text and the font too, not just the colour.

    Not the column style: the header's background lives there and is left alone by an update.
    """
    from sbs_utils.helpers import gui_text_escape
    if green:
        color = "#8f8"
    elif is_header:
        color = "#8cf"
    else:
        color = "#cde"
    return "$text:" + gui_text_escape(label) + ";font:gui-2;color:" + color + ";"


def director_tree_recolor(active_ident=None):
    """Move the green to whatever is on air now, WITHOUT rebuilding the page.

    This is the whole reason the rows carry tags. Repainting to move a colour cost a black
    frame, a repaint loop, the operator's collapse and their scroll position - see panel.mast.
    An update touches only the rows whose colour actually changed, which is at most a handful.

    A row scrolled off screen reports False from `gui_update` and is skipped; that is the
    ordinary case, not an error, and the template paints it correctly when it scrolls back.

    Returns how many rows were updated on screen.
    """
    from sbs_utils.procedural.gui import gui_update
    changed = 0
    for tag, label, is_header, idents in _TREE_ROWS:
        green = active_ident is not None and active_ident in idents
        if green == (label in _TREE_GREEN):
            continue
        if green:
            _TREE_GREEN.add(label)
        else:
            _TREE_GREEN.discard(label)
        if tag and gui_update(tag, _row_props(label, is_header, green)):
            changed += 1
    return changed


def director_rundown_tree_rows(active_ident=None, with_items=True):
    """(items, keys) for the main page: every rundown a header, its items the children.

    COLLAPSIBLE IS A MODE OF THE HEADER, and it is the opposite of selectable. The listbox
    gives the header's whole section the collapse click ONLY when `selectable=False`; ask for
    both and it hands `collapse_tag` to the template instead and the section becomes the
    select, so a header that is selectable does not collapse on its own. That maps cleanly onto
    the two pick modes: picking RUNDOWNS wants selectable headers (and has no children to
    collapse anyway), picking ITEMS wants collapsible ones, because there the header is a
    branch to open and shut rather than a thing to choose.

    `with_items=False` returns the RUNDOWNS ALONE. Picking rundowns and picking an item are
    two different questions, and the items are not the unit of choice in the first one - sixty
    of them just bury the four names actually being chosen between. Not collapsed branches:
    ABSENT. A rundown still goes green when the item on air is inside it, so a headers-only
    list still says where the show is.

    `items` mixes `LayoutListBoxHeader` objects with row strings; `keys` is a PARALLEL list -
    `("run", key)` for a header and `("item", key, index)` for a row - because
    `get_selected_index()` walks `unfiltered_items`, so index i of a selection has to be index
    i of the keys.

    Headers are `selectable=True`: clicking one still collapses the branch, and it ALSO
    reports a selection, which is what lets "pick rundowns" and "pick one item" be two modes of
    one list instead of two lists.

    Labels are made unique. Two rows reading the same string select and DESELECT together and
    one selection reports two indices - and a tree makes duplicates likely, because the same
    shot can legitimately appear in two rundowns.
    """
    from sbs_utils.procedural.gui.listbox import gui_list_box_header
    _TREE_GREEN.clear()
    _TREE_ROWS.clear()
    items = []
    keys = []
    seen = {}

    def unique(label):
        count = seen.get(label, 0) + 1
        seen[label] = count
        return label if count == 1 else label + " (" + str(count) + ")"

    def tag_for(slot):
        # POSITIONAL, and deliberately free of `:` and `;` - a tag is spliced into a style
        # string, and a rundown key like `u:my show` would end the property early. Positional is
        # safe because `_alias_overrides` lives on the LayoutListbox instance, so a rebuild
        # starts with none and the template's own colour is correct on the fresh rows.
        return "rd" + str(slot)

    # GENERATORS FIRST, then the operator's own - the same order as the flat picker, so the
    # list does not reshuffle when this page grew a tree. The generated ones are re-evaluated
    # here like everywhere else, so their children track ships that spawn and die.
    for key in [g[0] for g in _GENERATORS] + list(_RUNDOWNS):
        label = director_rundown_label_for(key)
        rows = director_rundown_items_of(key)
        head = unique(_plain(label) + "  (" + str(len(rows)) + ")")
        head_tag = tag_for(len(items))
        head_idents = set()
        items.append(gui_list_box_header(head, _TREE_COLLAPSE.get(key, False), indent=0,
                                        selectable=not with_items, data=head_tag))
        keys.append(("run", key))
        # The header carries EVERY ident in its branch, so a recolour can tell whether the show
        # is inside it without walking the rundowns again - and a collapsed or headers-only
        # branch still goes green.
        _TREE_ROWS.append((head_tag, head, True, head_idents))
        for index, item in enumerate(rows):
            ident = director_item_ident(item)
            head_idents.add(ident)
            on_air = active_ident is not None and ident == active_ident
            if on_air:
                _TREE_GREEN.add(head)
            if not with_items:
                continue
            row = unique(_row_label(item))
            row_tag = tag_for(len(items))
            items.append(_TreeRow(row, tag=row_tag))
            keys.append(("item", key, index))
            _TREE_ROWS.append((row_tag, row, False, {ident}))
            if on_air:
                _TREE_GREEN.add(row)
    return items, keys


def director_rundown_label_for(key):
    """The display name of any rundown, generated or user-built."""
    for gen_key, label, _fn in _GENERATORS:
        if gen_key == key:
            return label
    record = _RUNDOWNS.get(key)
    return record["label"] if record else str(key)


def director_item_row_tag(item):
    """The five-character kind tag that leads every item row.

    ONE definition, because TWO list renderers draw these rows - the tree here and
    `director_shot_item_rows` in director_shots - and a tag that disagreed between them would
    make one item look like two different things depending on which list was being read.
    """
    kind = item.get("kind")
    if kind == "con":
        return "con  "
    if kind == "ovl":
        return "ovl  "
    return (item.get("mode") or "orbit")[:5].ljust(5)


def director_item_row_suffix(item):
    """Everything a row says AFTER the label: the hold, the distance, and the furniture.

    ONE definition, for the same reason `director_item_row_tag` is one: two list renderers draw
    these rows - the tree here and `director_shot_item_rows` in director_shots - and a suffix
    that disagreed between them would make one item look like two different beats depending on
    which list was being read. The distance was added here once rather than in both.
    """
    out = ""
    if item.get("hold"):
        out = out + "  " + str(item["hold"]) + "s"
    if item.get("distance"):
        out = out + "  " + str(int(item["distance"])) + "u"
    kinds = []
    for entry in (item.get("overlays") or ()):
        kinds.append(str(entry.get("kind", "")).replace("_", " "))
    if kinds:
        out = out + "  [" + ", ".join(kinds) + "]"
    return out


def _row_label(item):
    """One item's row text: the mode, the label, its hold and what furniture it carries."""
    return (director_item_row_tag(item) + " " + _plain(item.get("label"))
            + director_item_row_suffix(item))


def director_rundown_row_template(item, **kwargs):
    """Draw one tree row. GREEN is what is on air right now.

    A template rather than plain string rows, because a plain row cannot carry a colour - and
    "which one of these is actually going out" is the question the operator asks this list most
    often. The rundown holding it goes green too, so a collapsed branch still says the show is
    inside it.

    EVERY ROW IS TAGGED, so `director_tree_recolor` can move the green without a repaint. The
    tag goes in the STYLE, beside the header's background - it is a script-side name the page
    records alongside the engine's own tag, so naming a row does not disturb the tag the
    listbox and its click region depend on.
    """
    from sbs_utils.procedural.gui import gui_row, gui_text
    from sbs_utils.procedural.gui.listbox import gui_list_box_is_header
    # A header carries its tag in `data` (that is what the argument is for); a _TreeRow has its
    # own slot. Both carry `.label`, and nothing else reaches this template.
    label = getattr(item, "label", item)
    is_header = gui_list_box_is_header(item)
    tag = getattr(item, "data", None) if is_header else getattr(item, "tag", None)
    style = "tag:" + tag + ";" if tag else ""
    gui_row("row-height: 1.7em; font: gui-2;")
    if is_header:
        gui_text(_row_props(label, True, label in _TREE_GREEN), style + "background: #234;")
        return
    # NO PADDING HERE. The row's indent is the listbox's own - _TreeRow carries `.indent`, so
    # the widget is placed indented rather than the text being pushed across inside a
    # full-width row, which also keeps the click region where the row looks like it is.
    gui_text(_row_props(label, False, label in _TREE_GREEN), style)


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


def director_tree_selected_rundowns(selection):
    """The rundown keys a tree selection names - headers, plus the parents of picked items.

    Picking an item implies its rundown, so "select two items from two rundowns and Send" does
    what it looks like rather than sending nothing.
    """
    out = []
    for entry in (selection or ()):
        if not entry:
            continue
        key = entry[1]
        if key not in out:
            out.append(key)
    return out


def director_tree_keep_selectable(selection, with_items):
    """Drop selection entries the CURRENT mode cannot select.

    The two modes select different kinds of row - rundowns in one, items in the other - and a
    mode change repaints with the outgoing selection in hand. Restoring an item key onto a list
    that has no item rows, or a rundown key onto a header that is no longer selectable, marks a
    row the operator cannot see or unmark.
    """
    want = "item" if with_items else "run"
    return [e for e in (selection or ()) if e and e[0] == want]


def director_tree_selected_item(selection):
    """The one ITEM a tree selection names, or None. Headers do not count as items."""
    for entry in (selection or ()):
        if entry and entry[0] == "item":
            rows = director_rundown_items_of(entry[1])
            if 0 <= entry[2] < len(rows):
                return rows[entry[2]]
    return None


def director_rundown_play_set(keys):
    """The ordered, de-duplicated, still-alive union of the selected rundowns' items.

    Multi-select means unselected is OFF, so this is the whole of what plays. Dead subjects
    are dropped HERE rather than by a destroy hook: a delete is tombstoned immediately, so
    `to_object()` reports gone on the same frame, and filtering at play time also covers
    objects that were removed without ever being destroyed.
    """
    from sbs_utils.procedural.query import to_object
    from sbs_utils.procedural.roles import role
    players = None
    out = []
    seen = set()
    for key in (keys or []):
        for item in director_rundown_items_of(key):
            # DECLARES a subject but cannot resolve one right now -> skip. One rule covering
            # three cases that are the same thing to the feed: a destroyed ship, an object
            # removed without ever being destroyed, and a BINDING with nothing selected (or a
            # weapons officer with no target). This beat cannot be shown, so the rundown steps
            # past it and picks it up again the moment it can be.
            #
            # An item that declares NO subject - kind "ovl" - is kept. It is furniture; asking
            # it to name something alive is asking the wrong question.
            #
            # RESOLVE, THEN CHECK. Two steps because they can each fail on their own: a
            # binding fails to resolve (nothing selected), and a baked id resolves to itself
            # and then turns out to name a corpse.
            if director_item_subject(item) is not None:
                live = director_item_subject_id(item)
                if live is None or to_object(live) is None:
                    continue
                # A CONSOLE BEAT NEEDS A CREWABLE SHIP, and a bound one can easily point at
                # something that is not: the operator clicks a rock, or a monster, or their own
                # camera point. `cv_show` would assign a screen to it and draw helm widgets for
                # an asteroid. So the console list is simply ignored for that selection - the
                # beat is skipped like any other that cannot be shown right now.
                #
                # `role("__player__")` and not a hull check: director cams are stripped of it at
                # spawn (director_cam.py), so a cambot can never be mistaken for a ship. Read
                # once per play set - this runs twice a second.
                if item.get("kind") == "con":
                    if players is None:
                        players = role("__player__")
                    if live not in players:
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
