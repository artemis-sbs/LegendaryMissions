"""Two feeds: what PROGRAM is showing, and what PREVIEW is showing.

Not a wall. Every console in Program mode shows the SAME item, every console in Preview mode
shows the same item, and the two are different items. That is broadcast, and it is what replaced
a per-screen distribution nobody wanted: a director previews a shot and then takes it.

  PREVIEW   what the editor is building, live - or, when nothing is staged, the item the rundown
            will advance to next, so a preview screen is never blank.
  PROGRAM   what was taken, or what the rundown has advanced to.

THE ONE DOOR. Every screen transition ends in `gui_reroute_client(screen, <label>, ...)` and
there are exactly four targets - `cv_show`, `cv_show_2d`, `cv_screen_program`,
`cv_screen_preview`. All four call `director_screen_enter` first, and that is the whole of the
overlay-leak fix. Six separate leaks were found by tracing, every one a transition with no clear
on it, and fixing them one at a time just grew a seventh. One door is cheaper to keep true.

Every public name is prefixed `director_`; a leading underscore is private.
"""

# Sibling imports are LAZY, inside each function. Every .py of an addon is exec'd into ONE shared
# namespace and `sys.modules["director_rundowns"]` is bound to it as that file loads, so a
# top-level import would depend on `__init__.mast` importing the sibling first. It does, but a
# load-order dependency that fails silently is not worth the saved lines - and the lazy form is
# what lets the unit tests import this module on its own.

# How much more exciting a challenger must be before the auto-director cuts to it. Small enough
# that a real fight takes the shot promptly, large enough that noise does not.
DIRECTOR_AUTO_MARGIN = 0.15

# Where a chase sits relative to the subject, in multiples of the framing near-distance.
DIRECTOR_CHASE_BACK = 3.0
DIRECTOR_CHASE_UP = 0.5

# client_id -> the item key that screen is currently showing.
# client_id -> the set of overlay slots it currently has up.
# client_id -> {"mode","subject","prom","yaw","leg"} for a running camera shot.
#
# ALL PER MISSION: cosmos_dev reuses one interpreter across run_next_mission, so a module dict
# nothing clears is the classic "works on run 1, stale on run 2".
_LAST = {}
_SLOTS = {}
_SHOTS = {}

# What the editor is staging, for PREVIEW screens to follow.
_STAGED = [None]
# The auto-director's memory: the item key it settled on, so it can hold through noise.
_AUTO_HELD = [None]


def director_screen_enter(client_id):
    """A screen is arriving somewhere. Drop whatever it was carrying.

    THE INVARIANT: a screen cannot arrive anywhere with its previous furniture or camera still
    running. Called first by every reroute target, so there is no transition without a clear -
    cam to console item, cam to tactical, preview going idle, and the three more that were found
    one at a time.

    `overlay_clear`, not just dropping the bookkeeping: it is the only call that also does
    `_live_drop`, and without that the 1-second `_live_catchup` ticker re-shows the card onto any
    page in the audience whose slot is empty. An overlay with an audience and no `seconds` is a
    PERMANENT live record - "it comes back a second later" is that ticker.
    """
    _director_clear_overlays(client_id)
    _SHOTS.pop(client_id, None)


def _director_clear_overlays(client_id):
    from sbs_utils.procedural.gui.overlay import overlay_clear
    for slot in _SLOTS.pop(client_id, ()):
        overlay_clear(slot, to=[client_id])


def director_play_reset():
    """Forget everything - per mission, and on Stop.

    IT RELEASES FIRST, and that is not tidiness. `_SLOTS` is the only record of which overlay
    slots are up; dropping it while cards are on screen orphans them PERMANENTLY, because
    `overlay_clear` needs the slot name and nothing else will ever name them again. That is
    exactly what `Send` used to do - and it beat Stop, because Stop's release then found an empty
    `_SLOTS` and cleared nothing.
    """
    for client_id in set(list(_SLOTS) + list(_SHOTS)):
        director_screen_enter(client_id)
    _LAST.clear()
    _SLOTS.clear()
    _SHOTS.clear()
    _STAGED[0] = None
    _AUTO_HELD[0] = None


def _exciting(subject_id):
    from sbs_utils.procedural.query import get_data_set_value
    try:
        return float(get_data_set_value(subject_id, "exciting", 0) or 0.0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def director_play_rank(items):
    """`items` best first: most exciting, then by the order the rundowns gave them.

    The secondary key is the ORIGINAL INDEX, not the id, so a quiet moment - or a headless run
    where nothing populates `exciting` and everything reads 0.0 - leaves the operator's own
    ordering intact instead of replacing it with an arbitrary one.
    """
    from director_rundowns import director_item_subject
    decorated = []
    for index, item in enumerate(items or []):
        decorated.append((-_exciting(director_item_subject(item)), index, item))
    decorated.sort(key=lambda t: (t[0], t[1]))
    return [item for _v, _i, item in decorated]


def director_play_auto_order(items):
    """The order the auto-director wants, holding its choice through noise.

    It only re-leads when a challenger beats the held item by DIRECTOR_AUTO_MARGIN. Without that,
    two contacts trading a fractionally higher score would swap the feed several times a minute,
    which reads as a fault rather than as direction.
    """
    from director_rundowns import director_item_key, director_item_subject
    if not items:
        _AUTO_HELD[0] = None
        return []
    ranked = director_play_rank(items)
    held_key = _AUTO_HELD[0]
    if held_key is not None:
        held = None
        for item in items:
            if director_item_key(item) == held_key:
                held = item
                break
        if held is not None:
            leader = ranked[0]
            if director_item_key(leader) != held_key:
                gain = (_exciting(director_item_subject(leader))
                        - _exciting(director_item_subject(held)))
                if gain <= DIRECTOR_AUTO_MARGIN:
                    ranked = [held] + [i for i in ranked
                                       if director_item_key(i) != held_key]
    _AUTO_HELD[0] = director_item_key(ranked[0])
    return ranked


# --- what each feed is showing ---------------------------------------------------------------

def director_play_stage(item=None, clear=False):
    """Read or set what the editor is staging - what PREVIEW screens follow."""
    if clear:
        _STAGED[0] = None
    elif item is not None:
        _STAGED[0] = item
    return _STAGED[0]


def director_play_program_item(items, index=0, auto=False, punch=None):
    """The ONE item every program screen shows.

    `punch` is what "Send to Program" took, and it wins outright until cleared - on a six-second
    dwell a punch that did not hold would be overwritten on the next advance and read as a button
    that does nothing.
    """
    if punch is not None:
        return punch
    items = list(items or [])
    if not items:
        return None
    if auto:
        return director_play_auto_order(items)[0]
    return items[index % len(items)]


def director_play_preview_item(items, index=0):
    """The ONE item every preview screen shows: staged, else the next one up.

    The fallback matters. A preview screen that goes blank whenever the operator is not actively
    staging something reads as broken rather than as idle, and "next up" - what the rundown will
    hand to program on its next advance - is the other thing a director wants to see coming.
    """
    if _STAGED[0] is not None:
        return _STAGED[0]
    items = list(items or [])
    if not items:
        return None
    return items[(index + 1) % len(items)]


def _overlay_key(item):
    """A fingerprint of an item's FURNITURE, separate from its shot.

    Separate because they want different treatments: a new shot needs a reroute, while new
    text on the same shot must not get one. Preview restages on every keystroke, and a reroute
    per keystroke would rebuild the page and restart the camera each time.
    """
    parts = []
    for entry in ((item or {}).get("overlays") or ()):
        for key in sorted(entry):
            parts.append(str(key) + "=" + str(entry[key]))
        parts.append("/")
    return ";".join(parts)


def director_play_plan(item, screens):
    """Put ONE item on every screen. Returns [{screen, item, changed}].

    `changed` is what keeps this cheap: a console item is a full page rebuild on the target
    screen, and re-issuing one that is already correct several times a minute would flicker every
    screen for nothing. A furniture-only change is handled HERE rather than reported, because it
    needs no reroute at all - the cards are simply re-shown.
    """
    from director_rundowns import director_item_key
    screens = list(screens or [])
    key = director_item_key(item)
    ovkey = _overlay_key(item)
    plan = []
    for screen in screens:
        was = _LAST.get(screen)
        changed = was is None or was[0] != key
        if not changed and was[1] != ovkey and item is not None:
            director_play_overlays(screen, item)
        _LAST[screen] = (key, ovkey)
        plan.append({"screen": screen, "item": item, "changed": changed})
    return plan


def director_play_forget_absent(screens):
    """Stop tracking screens that are no longer in either feed.

    ONCE PER TICK, over BOTH feeds together - not inside `director_play_plan`, which is called
    twice with different screen lists. Pruning there would have the program pass forget every
    preview screen and the preview pass forget every program one, so every screen would read as
    changed on every tick and the whole wall would rebuild continuously.

    A screen that dropped out and comes back then counts as changed and is re-applied, rather
    than being assumed still correct.
    """
    keep = set(screens or ())
    for screen in [s for s in _LAST if s not in keep]:
        _LAST.pop(screen, None)


# --- applying one item to one screen ---------------------------------------------------------
#
# Modes, not geometry. `viewscreen_framing` sizes every shot off the subject's own hull radius,
# which is why a starbase and a fighter both fill the frame; the timings and angles are the
# library's, so a Director shot and a bridge "On Screen" shot of the same ship look identical.

def _framing(subject):
    from sbs_utils.procedural.gui.viewscreen import viewscreen_framing
    return viewscreen_framing(subject)


def _forward(subject):
    """The subject's forward vector, or None.

    GUARDED, because it is not on every object - the grav-tether harness hit exactly this and had
    to wrap it. A chase with no heading is still a shot (it falls back to a fixed rear offset); a
    chase that raises is a dead screen.
    """
    from sbs_utils.procedural.query import to_object
    obj = to_object(subject)
    if obj is None:
        return None
    for get in (getattr(obj, "space_object", None),
                lambda: getattr(obj, "engine_object", None)):
        try:
            eo = get() if get is not None else None
            if eo is None:
                continue
            fwd = eo.forward_vector()
            if fwd is None:
                continue
            from sbs_utils.vec import Vec3
            return Vec3(fwd.x, fwd.y, fwd.z)
        except Exception:
            continue
    return None


def _chase_lens(subject):
    """A world-space lens offset sitting BEHIND the subject, along its heading.

    Recomputed every tick, and that is the whole point: the engine does not rotate offsets into
    the dolly frame, so a fixed offset trails the ship only until it turns and then swings out to
    the side. Re-aiming is what makes a chase a chase.
    """
    from sbs_utils.vec import Vec3
    near, _far = _framing(subject)
    back = near * DIRECTOR_CHASE_BACK
    up = near * DIRECTOR_CHASE_UP
    fwd = _forward(subject)
    if fwd is None:
        return Vec3(0.0, up, -back)
    return Vec3(-fwd.x * back, up - fwd.y * back, -fwd.z * back)


def director_play_overlays(client_id, item):
    """Show an item's overlays on one screen, clearing whatever it had first.

    TEMPLATES ARE RESOLVED HERE, one line before `overlay_kind`, because `banner` and
    `lower_third` are cycle kinds: their text is word-wrapped and split into timed segments, so
    an unresolved `<<class>>` could be split across two of them.
    """
    from sbs_utils.procedural.gui.overlay import overlay_kind, _KIND_DEFAULT_SLOT
    from director_overlays import director_overlay_resolve_fields
    from director_rundowns import director_item_subject
    _director_clear_overlays(client_id)
    subject = director_item_subject(item)
    used = set()
    for entry in ((item or {}).get("overlays") or ()):
        fields = director_overlay_resolve_fields(entry, subject)
        kind = fields.pop("kind", None)
        if not kind:
            continue
        slot = _KIND_DEFAULT_SLOT.get(kind, "center_hero")
        overlay_kind(kind, to=[client_id], slot=slot, **fields)
        used.add(slot)
    if used:
        _SLOTS[client_id] = used
    return used


def director_play_apply_shot(client_id, item):
    """Put a camera item on ONE screen and start its first leg. True when it applied."""
    if item is None or item.get("kind") != "cam":
        return False
    subject = item.get("subject")
    if not subject:
        return False
    mode = item.get("mode") or "orbit"
    _SHOTS[client_id] = {"mode": mode, "subject": subject, "prom": None, "yaw": 0.0, "leg": 0}
    if mode != "tactical":
        director_play_next_leg(client_id)
    director_play_overlays(client_id, item)
    return True


def director_play_next_leg(client_id):
    """One leg of a running shot: a push, a turn, or a re-aimed chase.

    LEGS, not one endless move, and they must be RE-ISSUED when they finish - a 22-second dolly
    on a screen that is not changing item would otherwise run once and freeze on its last frame.
    Finite legs also recover by themselves: if one is cut short because the subject died or
    another console stole the camera, the next tick starts the next one.
    """
    from sbs_utils.procedural.gui.camera import camera_dolly, camera_orbit, camera_track
    from sbs_utils.procedural.gui.viewscreen import (DOLLY_SECONDS, ORBIT_SECONDS,
                                                     ORBIT_PITCH, DOLLY_YAW)
    from sbs_utils.procedural.query import to_object
    record = _SHOTS.get(client_id)
    if record is None:
        return False
    subject = record["subject"]
    if to_object(subject) is None:
        _SHOTS.pop(client_id, None)
        return False
    near, far = _framing(subject)
    cids = [client_id]
    mode = record["mode"]
    if mode == "orbit":
        yaw = record["yaw"]
        record["prom"] = camera_orbit(cids, subject, far, from_yaw=yaw, to_yaw=yaw + 360.0,
                                      seconds=ORBIT_SECONDS, pitch=ORBIT_PITCH)
        # Carry the angle over: a loop restarting at 0 would whip back round every lap.
        record["yaw"] = (yaw + 360.0) % 360.0
    elif mode == "chase":
        camera_track(cids, subject, lens=_chase_lens(subject))
        record["prom"] = None
    else:
        # Ping-pong: in, then out. A push that cut back to wide each time would read as a jump
        # cut every 22 seconds.
        a, b = (far, near) if record["leg"] % 2 == 0 else (near, far)
        record["prom"] = camera_dolly(cids, subject, a, b, yaw=DOLLY_YAW,
                                      pitch=ORBIT_PITCH, seconds=DOLLY_SECONDS)
    record["leg"] += 1
    return True


def director_play_tick_shots():
    """Advance every running shot. Called each player tick, independent of the dwell.

    Independent DELIBERATELY: `changed` says whether a screen should be handed a new ITEM, which
    is a different question from whether the shot it already has needs its next leg.
    """
    for client_id in list(_SHOTS):
        record = _SHOTS.get(client_id)
        if record is None:
            continue
        if record["mode"] == "chase":
            director_play_next_leg(client_id)      # re-aim every tick
            continue
        prom = record.get("prom")
        if prom is None or prom.done():
            director_play_next_leg(client_id)


def director_play_release(client_id):
    """Hand one screen back to the engine's own camera and take its furniture down.

    IT DOES NOT FORGET WHAT THE SCREEN WAS SHOWING. `_LAST` is what stops a plan re-issuing a
    screen that is already correct, and an idle screen's entry is `(None, "")` - a real state,
    not an absence. Popping it here would make the very next tick read the screen as changed,
    release it again, and reroute it again, twice a second, forever.
    """
    from sbs_utils.procedural.gui.camera import camera_auto
    director_screen_enter(client_id)
    camera_auto([client_id])


def director_play_status(program_item, program_n, preview_n, auto, punched):
    """One line for the main page: what is going out, and why nothing is when nothing is.

    Says the unhelpful cases out loud - "nothing happened" is the commonest confusion and the
    reason is never visible on screen otherwise.
    """
    if program_n == 0 and preview_n == 0:
        return "no program or preview screens - open one and pick its mode"
    if program_item is None:
        return "select a rundown - nothing is going out"
    line = ("ON AIR " + str(program_item.get("label") or "")
            + " on " + str(program_n) + " program")
    if preview_n:
        line = line + ", " + str(preview_n) + " preview"
    if punched:
        line = line + " - held"
    elif auto:
        line = line + " - auto-director"
    return line
