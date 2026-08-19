"""Which ship the program screens should be showing, chosen automatically.

WHY. The Director panel's Ships list is built once when the console opens, and the
operator picks from it by hand. That is fine for a streamer choosing a shot; it is
friction for anything with a ROTATING CAST - a party with a queue of crews, a long
campaign, a demo running all day - where the ship worth watching changes without anyone
touching the console, and the picker is stale the moment a new crew is seated.

WHAT IT WATCHES. The `exciting` value on each player ship, which is the ENGINE's own
notion, not a second opinion invented here: it is what the engine's automatic cinematic
camera follows, and what `sbs_utils.procedural.gui.rundown.rundown_excitement` reads. So
an auto-followed program screen agrees with what the engine would have chosen.

TWO THINGS THAT KEEP IT WATCHABLE, both learned the hard way from cameras that twitch:

  * STABLE ORDER. `role("__player__")` is a SET, so iterating it is not ordered. With
    every ship equally exciting - a quiet moment, or a headless run where nothing
    populates `exciting` at all - "the first one" is whichever the set happened to yield,
    and the screen would flip between identical-looking ships on every poll. Ties break on
    the lowest id instead, which is arbitrary but CONSTANT.
  * HYSTERESIS. A challenger has to beat the ship on screen by a MARGIN, not by a hair.
    Two ships trading a fractionally higher score would otherwise cut back and forth
    several times a minute, which reads as a fault rather than as direction.

Every public name is prefixed `director_`: an addon's `def`s become MAST globals in one
flat mission-wide namespace and `register_mission_functions` assigns into it
unconditionally - last loaded wins, silently, in a non-deterministic order.
"""

# How much more exciting a challenger must be before the screen cuts to it. Small enough
# that a real fight takes the shot promptly, large enough that noise does not.
DIRECTOR_FOLLOW_MARGIN = 0.15


def _director_excitement(obj):
    """One ship's `exciting` value as a float, 0.0 when it has none.

    Never raises: an unscored ship is a boring ship, not an error. That matters headless,
    where nothing populates the key at all and every ship reads 0.0 - the caller then
    falls through to the stable-order tie-break rather than to an empty screen.
    """
    from sbs_utils.procedural.query import get_data_set_value
    try:
        return float(get_data_set_value(obj.id, "exciting", 0) or 0.0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def director_follow_candidates():
    """[(excitement, ship_id), ...] for every live player ship, best first.

    Sorted by excitement descending then id ascending, so the order is total and stable
    across polls even when every score is identical.
    """
    from sbs_utils.procedural.query import to_object_list
    from sbs_utils.procedural.roles import role
    out = []
    for p in to_object_list(role("__player__")):
        if p is None:
            continue
        out.append((_director_excitement(p), p.id))
    out.sort(key=lambda pair: (-pair[0], pair[1]))
    return out


def director_follow_pick(current=None):
    """The ship the program screens should be on, or None when there are no players.

    `current` is what is on screen now. It is KEPT unless it has gone or something beats
    it by `DIRECTOR_FOLLOW_MARGIN` - so a screen holds its shot through the ordinary
    wobble of two ships being about equally interesting, and cuts when something actually
    happens.

    Returning the current ship unchanged is the normal case; the caller compares and only
    re-applies on a change.
    """
    ranked = director_follow_candidates()
    if not ranked:
        return None

    # Pick the best HERE rather than trusting `ranked[0]`. The ordering is the whole
    # stability guarantee, and a decision that depends on its caller having sorted first
    # is one refactor away from flipping between identical ships again. Same key as
    # `director_follow_candidates`: most exciting, then lowest id.
    best_v, best_id = min(ranked, key=lambda pair: (-pair[0], pair[1]))
    if current is None:
        return best_id

    # Is the ship on screen still there? A destroyed one drops out of the list, and
    # holding a dead subject is how a camera ends up on the engine's default top-down.
    current_v = None
    for v, sid in ranked:
        if sid == current:
            current_v = v
            break
    if current_v is None:
        return best_id

    if best_id != current and best_v > current_v + DIRECTOR_FOLLOW_MARGIN:
        return best_id
    return current


def director_follow_status(current=None):
    """One short line for the panel: what is being followed and how close it was.

    Plain ASCII, no braces - a returned `{` is re-run as an f-string by the MAST
    assignment that receives it, and the SyntaxError is blamed on the caller.
    """
    ranked = director_follow_candidates()
    if not ranked:
        return "auto-follow: no player ships"
    from sbs_utils.procedural.query import to_object
    obj = to_object(current if current is not None else ranked[0][1])
    name = getattr(obj, "name", None) or "ship"
    # BRACES OUT. The caller assigns this to a MAST variable, and MAST re-runs an assigned
    # STRING through f-string formatting - so a `{` arriving in a ship's name would raise
    # a SyntaxError reported against the panel rather than against whoever named the ship.
    # Nothing names a ship with a brace today; this costs one replace and removes the
    # class of failure.
    name = str(name).replace("{", "(").replace("}", ")")
    return "auto-follow: " + name + " of " + str(len(ranked))
