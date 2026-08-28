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
#
# HALVED, both of them, and halving BOTH is what keeps it a chase. At 3.0 back the ship was a
# speck - `near` is already 6 hull radii, so a light cruiser was being chased from about 1600
# units out, which reads as a wide shot that happens to follow something.
#
# The height matters as much as the distance here, because what makes a shot read as BEHIND is
# the elevation ANGLE, not the height itself. Back and up are both multiples of the same
# `near`, so the ratio between them IS the angle - 0.5/3.0 is about 9.5 degrees above the
# subject's own line, which is over its shoulder. Halving the distance alone would have left
# that at 18.4 degrees and tipped the shot toward looking DOWN on the ship, which is exactly
# what it should not be. Halved together, the angle is unchanged and the shot is simply closer.
DIRECTOR_CHASE_BACK = 1.5
DIRECTOR_CHASE_UP = 0.25
# How long one chase leg runs before it is re-issued. Long, because unlike a dolly or an orbit
# a chase has no shape to complete - the leg exists only so a dead subject or a stolen camera
# recovers, which `_drive` already handles at the end of one.
DIRECTOR_CHASE_SECONDS = 30.0

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
# The ident of the item the RUNDOWN is holding. Identity, deliberately, not an index - see
# director_play_feeds.
_PROGRAM_HELD = [None]
# The ident of what is ACTUALLY going out, which is the take when there is one. Separate from
# _PROGRAM_HELD because a take does not disturb the rundown's place - so the two differ for as
# long as the take is up, and the operator's list has to mark the one on screen.
_ON_AIR = [None]


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
    """Everything on this screen, not just what the Director put there.

    The invariant is "a screen cannot arrive anywhere with its previous furniture
    still running", and iterating _SLOTS only ever made that true of the Director's
    OWN furniture. A program screen carries console roles - it explicitly adds
    them - so it can be holding a hail band or the science data column raised by
    the bridge it is watching, and those survived every transition here.

    _SLOTS is still emptied: it is the record of what WE raised, and leaving stale
    names in it would have a later clear reach for slots that are already gone.
    """
    from sbs_utils.procedural.gui.overlay import overlay_clear_console
    _SLOTS.pop(client_id, None)
    overlay_clear_console(client_id)


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
    _PROGRAM_HELD[0] = None
    _ON_AIR[0] = None


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
    from director_rundowns import director_item_subject_id
    decorated = []
    for index, item in enumerate(items or []):
        # The RESOLVED subject: a bound item's excitement is whatever it is pointed at now,
        # and an overlay-only item resolves to None and scores 0.0 - it is furniture, so it
        # has no action of its own to rank and keeps the operator's own ordering.
        decorated.append((-_exciting(director_item_subject_id(item)), index, item))
    decorated.sort(key=lambda t: (t[0], t[1]))
    return [item for _v, _i, item in decorated]


def director_play_auto_order(items):
    """The order the auto-director wants, holding its choice through noise.

    It only re-leads when a challenger beats the held item by DIRECTOR_AUTO_MARGIN. Without that,
    two contacts trading a fractionally higher score would swap the feed several times a minute,
    which reads as a fault rather than as direction.
    """
    from director_rundowns import director_item_ident, director_item_subject_id
    if not items:
        _AUTO_HELD[0] = None
        return []
    ranked = director_play_rank(items)
    held_key = _AUTO_HELD[0]
    if held_key is not None:
        held = None
        for item in items:
            if director_item_ident(item) == held_key:
                held = item
                break
        if held is not None:
            leader = ranked[0]
            if director_item_ident(leader) != held_key:
                gain = (_exciting(director_item_subject_id(leader))
                        - _exciting(director_item_subject_id(held)))
                if gain <= DIRECTOR_AUTO_MARGIN:
                    ranked = [held] + [i for i in ranked
                                       if director_item_ident(i) != held_key]
    _AUTO_HELD[0] = director_item_ident(ranked[0])
    return ranked


# --- what each feed is showing ---------------------------------------------------------------

def director_play_on_air_ident():
    """The ident of the item actually on PROGRAM right now, or None.

    NOT `_PROGRAM_HELD`, which is where the RUNDOWN is - a take overrides the feed without
    disturbing that, so the two differ for as long as the take is up. The operator's list marks
    what is on screen, so it needs this one; using the rundown's place would put the green on a
    row that is not going out.

    The ident rather than the item, because that is what each row is compared against.
    """
    return _ON_AIR[0]


def director_play_stage(item=None, clear=False):
    """Read or set what the editor is staging - what PREVIEW screens follow."""
    if clear:
        _STAGED[0] = None
    elif item is not None:
        _STAGED[0] = item
    return _STAGED[0]


def _index_of(order, ident):
    """Where `ident` sits in `order`, or None if it is not there any more.

    The full IDENT, not the shot key: a rundown can hold the same shot twice with different
    furniture, and matching on the shot would find the first of them - so advancing from the
    titled beat to the clean one would snap straight back to the titled one.
    """
    if ident is None:
        return None
    from director_rundowns import director_item_ident
    for index, item in enumerate(order):
        if director_item_ident(item) == ident:
            return index
    return None


def _next_after(order, ident, auto):
    """The item that should follow `ident` when the clock runs out."""
    from director_rundowns import director_item_ident
    at = _index_of(order, ident)
    if at is None:
        return order[0]
    if auto:
        # Auto means "follow the action", so an advance goes to the LEADER - unless the leader
        # is already what is on air, in which case sitting on it forever is not direction
        # either and it steps on.
        if director_item_ident(order[0]) != ident:
            return order[0]
    return order[(at + 1) % len(order)]


def director_play_hold(item, dwell):
    """How long `item` stays on air: its own hold, else the operator's dwell.

    An establishing shot of a starbase wants ten seconds; a chase in a firefight wants three.
    The hold is per item so a rundown can say that, and the dwell stays the answer for
    everything that has no opinion - including every generated item.
    """
    try:
        dwell = float(dwell)
    except (TypeError, ValueError):
        dwell = 6.0
    own = (item or {}).get("hold")
    if own is None:
        return dwell
    try:
        return float(own)
    except (TypeError, ValueError):
        return dwell


def director_play_feeds(items, elapsed=None, dwell=6.0, auto=False, punch=None):
    """Both feeds and the dwell clock, from one evaluation.

    Returns `{"program": item, "preview": item, "elapsed": seconds}`. Hand `elapsed` back to
    the player each tick; it comes back reset to 0.0 on an advance.

    ONE CALL, so preview's "next up" is computed against the same ordering program just used.
    Two calls could disagree, and a preview screen showing something the next advance will not
    actually take is worse than no preview at all. THE CLOCK IS HERE TOO, because whether to
    advance depends on the HELD item's own hold - so a caller that decided first would have to
    know what is held before asking what is held.

    THE PROGRAM ITEM IS HELD BY IDENTITY, AND THAT IS THE WHOLE POINT OF THIS FUNCTION. The
    play set is rebuilt every tick - twelve times per dwell - so that generated rundowns track
    ships that spawn and die. "The action" then re-sorts it by live `exciting` values every
    time, and its top-N membership churns in a fight. Indexing that list POSITIONALLY meant the
    on-air item moved whenever the sort moved, with no advance having happened: the reported
    flicker. Holding the KEY makes the item immune to the list reordering underneath it, and
    the clock is the only thing that can change what is on air.

    `elapsed=None` means "do not consider advancing" - a pure read of the two feeds.

    `punch` is what "Send to Program" took. It wins outright AND FREEZES THE CLOCK, so Resume
    hands the feed back exactly where it was rather than cutting immediately because the dwell
    expired while the take was up.
    """
    from director_rundowns import director_item_ident
    items = list(items or [])
    if not items:
        _PROGRAM_HELD[0] = None
        _ON_AIR[0] = director_item_ident(punch)
        return {"program": punch, "preview": _STAGED[0], "elapsed": 0.0}

    order = director_play_auto_order(items) if auto else items
    at = _index_of(order, _PROGRAM_HELD[0])
    if at is None:
        # Nothing held, or what was held has died or left the play set. Take the front rather
        # than the old position: a stale index into a re-sorted list is what this exists to
        # avoid.
        program = order[0]
        elapsed = 0.0 if elapsed is not None else None
    else:
        program = order[at]
        if punch is None and elapsed is not None:
            if elapsed >= director_play_hold(program, dwell):
                program = _next_after(order, _PROGRAM_HELD[0], auto)
                elapsed = 0.0
    _PROGRAM_HELD[0] = director_item_ident(program)

    # Preview follows the editor when something is staged; otherwise it shows what the NEXT
    # advance will take. A preview screen that goes blank whenever the operator is not staging
    # reads as broken rather than as idle.
    preview = _STAGED[0]
    if preview is None:
        preview = _next_after(order, _PROGRAM_HELD[0], auto)
    on_air = punch if punch is not None else program
    _ON_AIR[0] = director_item_ident(on_air)
    return {"program": on_air,
            "preview": preview,
            "elapsed": 0.0 if elapsed is None else elapsed}


def _overlay_key(item):
    """A fingerprint of an item's FURNITURE, separate from its shot.

    Separate because they want different treatments: a new shot needs a reroute, while new
    text on the same shot must not get one. Preview restages on every keystroke, and a reroute
    per keystroke would rebuild the page and restart the camera each time.

    This is also what makes "the station with a lower third, then the same shot clean" look
    right on air: the SHOT key is unchanged across those two beats, so the camera keeps
    running and only the cards swap.
    """
    from director_rundowns import director_item_overlay_ident
    return director_item_overlay_ident(item)


def director_play_plan(item, screens):
    """Put ONE item on every screen. Returns [{screen, item, changed}].

    `changed` is what keeps this cheap: a console item is a full page rebuild on the target
    screen, and re-issuing one that is already correct several times a minute would flicker every
    screen for nothing. A furniture-only change is handled HERE rather than reported, because it
    needs no reroute at all - the cards are simply re-shown.

    TWO DIFFERENT KEYS, AND THE DIFFERENCE IS THE WHOLE OF SELECTION BINDING.

    The FEED holds its place by `director_item_ident`, built from the item AS AUTHORED - see
    director_play_feeds. A bound item is the same item in the rundown however the selection
    moves; if its ident moved on every click, `_index_of` would lose `_PROGRAM_HELD`, the
    program would snap to `order[0]` and the dwell clock would reset - the exact flicker that
    identity-holding was written to prevent.

    A SCREEN, though, must re-aim when the resolved subject moves: the camera is pointed at an
    id, not at a binding. So the key compared here carries the RESOLVED subject alongside the
    authored one. A bound item whose selection changed then reports `changed`, gets a fresh
    reroute and a fresh camera, and the rundown keeps its place through all of it.
    """
    from director_rundowns import director_item_key, director_item_subject_id
    screens = list(screens or [])
    ovkey = _overlay_key(item)
    overlay_only = item is not None and item.get("kind") == "ovl"
    # `None` for no item at all is a REAL STATE, not an absence - an idle screen's entry is
    # `(None, "")` and director_play_release depends on it staying that way. Keep it a bare
    # None rather than a one-tuple, so nothing downstream has to know the difference.
    key = None
    if item is not None and not overlay_only:
        key = director_item_key(item) + (director_item_subject_id(item),)
    plan = []
    for screen in screens:
        was = _LAST.get(screen)
        if overlay_only:
            # A TITLE BELONGS OVER THE SHOT THAT IS RUNNING, not instead of it. So an overlay
            # item INHERITS the screen's current shot key and never reports changed: no
            # reroute, no page rebuild, the camera keeps stepping its legs, and only the cards
            # swap. That also makes two ovl beats in a row a straight card change.
            #
            # Its overlays are applied unconditionally rather than on an ovkey difference,
            # because the beat before it may have been a camera item that left its own
            # furniture up - and `changed` being False means nothing else will clear it.
            director_play_overlays(screen, item)
            _LAST[screen] = (was[0] if was else None, ovkey)
            plan.append({"screen": screen, "item": item, "changed": False})
            continue
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

# A CAMERA POINT IS NOT FRAMED LIKE A HULL. `viewscreen_framing` sizes a shot off the
# subject's `exclusion_radius`, and the cam is invisible with none - so it falls to
# DEFAULT_RADIUS (90) and gives a 540/1440 shot, which frames one mid-sized ship. The point of
# parking the cam is to orbit a FIGHT, and a fight is not a ship.
#
# MEASURED, not guessed - and the guess was wrong. A probe sampled the siege map twice a second
# for 90s, taking the densest knot of armed combatants within 6000u of each other (the whole
# map's spread is 60,000u, which is the size of the SYSTEM and not of a battle - a camera at
# that centroid is in deep space):
#
#     cluster size    median 4 ships
#     cluster radius  median 140u, p90 151u, max 3234u
#     nearest pair    median 100u
#     player->enemy   803u to 3500u across runs
#
# So an engagement is USUALLY a tight knot a few hundred units across, and occasionally spreads
# to a few thousand. The first pass at these numbers - 2500 and 7000 - was sized for the widest
# case alone, which made the common one a speck: at 7000u a 140u knot is four dots.
#
# A camera at distance d with a ~60 degree vertical FOV sees a half-height of about 0.577d, so
# it holds a cluster of radius R at d ~= 2.25R with a little margin. FAR holds ~1400u (most of
# the measured range); NEAR holds ~520u, which is a tight knot filling the frame. The dolly
# ping-pongs between them, so one item covers both looks.
#
# CAVEAT, because it decides how much these are worth: the headless run never produced a proper
# brawl - the player ended 3500u from its nearest enemy - so the upper end comes from cluster
# GEOMETRY rather than from watching a fight. Worth re-checking on a real bridge.
DIRECTOR_POINT_NEAR = 900.0
DIRECTOR_POINT_FAR = 2500.0


def _framing(subject):
    from sbs_utils.procedural.gui.viewscreen import viewscreen_framing
    from director_cam import director_is_camera_point
    if director_is_camera_point(subject):
        return DIRECTOR_POINT_NEAR, DIRECTOR_POINT_FAR
    return viewscreen_framing(subject)


def director_play_overlays(client_id, item):
    """Show an item's overlays on one screen, clearing whatever it had first.

    TEMPLATES ARE RESOLVED HERE, one line before `overlay_kind`, because `banner` and
    `lower_third` are cycle kinds: their text is word-wrapped and split into timed segments, so
    an unresolved `<<class>>` could be split across two of them.
    """
    from sbs_utils.procedural.gui.overlay import overlay_kind, _KIND_DEFAULT_SLOT
    from director_overlays import director_overlay_build_fields
    from director_rundowns import director_item_subject_id
    _director_clear_overlays(client_id)
    # RESOLVED, so `<<name>>` on a bound item names whatever it is pointed at THIS time round
    # rather than whatever it was pointed at when the item was written. None on an
    # overlay-only item, where every subject token correctly resolves to its fallback.
    subject = director_item_subject_id(item)
    used = set()
    for entry in ((item or {}).get("overlays") or ()):
        fields = director_overlay_build_fields(entry, subject, item)
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
    from director_rundowns import director_item_subject_id
    if item is None or item.get("kind") != "cam":
        return False
    # THE RESOLVED id, never the authored field: a binding is a string and the camera takes an
    # object. It can come back None between the play set being built and this running - the
    # operator deselected in that half-second - so this is a real branch, not a formality.
    subject = director_item_subject_id(item)
    if not subject:
        return False
    mode = item.get("mode") or "orbit"
    # THE DISTANCE RIDES ON THE RECORD, not looked up per leg: the item can be replaced
    # under a running shot (Replace on the editor), and a leg re-issued half a second
    # later should still be the shot that was applied until the feed says otherwise.
    _SHOTS[client_id] = {"mode": mode, "subject": subject, "prom": None, "yaw": 0.0,
                         "leg": 0, "distance": item.get("distance")}
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
    from sbs_utils.procedural.gui.camera import camera_chase, camera_dolly, camera_orbit
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
    # AN EXPLICIT DISTANCE IS WHERE THE CAMERA SITS - the orbit radius, the chase back, the
    # dolly's wide end. Absent (the usual case) leaves the hull-derived framing alone, which is
    # why this is an override rather than the return of the sliders that were deleted: those
    # were the ONLY way to size a shot, and a fixed number framed a starbase and a fighter
    # equally badly.
    #
    # The dolly still pushes: half the distance and back out, so "3500" is a shot that lives at
    # 3500 rather than a static hold there.
    want = record.get("distance")
    cids = [client_id]
    mode = record["mode"]
    if mode == "orbit":
        yaw = record["yaw"]
        radius = want if want else far
        record["prom"] = camera_orbit(cids, subject, radius, from_yaw=yaw, to_yaw=yaw + 360.0,
                                      seconds=ORBIT_SECONDS, pitch=ORBIT_PITCH)
        # Carry the angle over: a loop restarting at 0 would whip back round every lap.
        record["yaw"] = (yaw + 360.0) % 360.0
    elif mode == "chase":
        # THIRD PERSON, DRIVEN ON THE TICK. This used to re-issue `camera_track` from the
        # player's own 0.5s loop with a lens recomputed here, and that is what flickered: the
        # engine has no interpolation, so the driver IS the animation and a few hertz reads as
        # a stutter. `camera_chase` rebuilds the offset from the subject's live heading every
        # dispatcher tick, which is how camera_dolly and camera_orbit already work - and they
        # were the two modes that never flickered.
        #
        # THE HEIGHT STAYS TIED TO THE FRAMING, not to the explicit distance. What makes a
        # chase read as behind is the elevation ANGLE, and scaling the height with a distance
        # the operator is dragging would tip the shot overhead as they came closer - the exact
        # thing halving DIRECTOR_CHASE_UP alongside DIRECTOR_CHASE_BACK was done to avoid.
        back = want if want else near * DIRECTOR_CHASE_BACK
        record["prom"] = camera_chase(cids, subject, back,
                                      height=near * DIRECTOR_CHASE_UP,
                                      seconds=DIRECTOR_CHASE_SECONDS)
    else:
        # Ping-pong: in, then out. A push that cut back to wide each time would read as a jump
        # cut every 22 seconds.
        wide, close = (want, want * 0.5) if want else (far, near)
        a, b = (wide, close) if record["leg"] % 2 == 0 else (close, wide)
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
        # NO SPECIAL CASE FOR CHASE any more. It used to be re-aimed here on every player
        # tick; it is a tick-driven library move now, so like every other mode it only needs
        # its next leg when the current one ends.
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
