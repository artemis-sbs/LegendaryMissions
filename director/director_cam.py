"""The camera each Director console rides, and keeping the console seated on it.

WHY THIS IS A FUNCTION AND NOT A BLOCK OF MAST IN ONE LABEL. Every tab has to do this, not
just the one that spawns the cam:

  Staging a shot calls `shot_apply` -> `camera_track`, and `camera_track` does
  `sbs.assign_client_to_ship(cid, dolly)` - it MUST, because the engine only honors a camera
  change when the console and the lens ride the same object. So a Director console that has
  previewed anything is no longer on its own cam.

  Everything the Stage tab does is gated on `has_roles(SCIENCE_ORIGIN_ID, "director_cam")`,
  and `SCIENCE_ORIGIN_ID` is exactly `sbs.get_ship_of_client(client_id)`. So after one visit
  to the Shot tab, `//focus/science` and `//enable/science` silently stop matching, clicking
  the 2D view selects nothing, and nothing is logged anywhere. That is the whole of the
  "selecting a subject eventually gets broken" report: it broke the first time the operator
  opened Shot, and only a trip back through the program tab (the one label that re-seated)
  ever fixed it.

`director_cam_ensure` is therefore called at the TOP OF EVERY TAB. It is idempotent, so
calling it on every repaint costs a lookup and an assign.

Every public name is prefixed `director_`: an addon's `def`s become MAST globals in one flat
mission-wide namespace, last loaded wins, silently. A leading underscore is private.
"""

# How far the cam can see. The Game Master uses 15000; a Director is picking shots across a
# whole system rather than managing one fight, so it gets the Admiral's reach instead.
DIRECTOR_CAM_SCAN_RANGE = 40000

# Spawn height. Above the plane, so the first pan does not drop the cam into the middle of a
# hull and the 2D view keeps a plan-like view of the system.
DIRECTOR_CAM_HEIGHT = 1000


def _sbs():
    from sbs_utils.helpers import FrameContext
    context = FrameContext.context
    return getattr(context, "sbs", None) if context is not None else None


# Inventory key for a PROGRAM SCREEN own camera. A screen needs one for the same reason the
# console does - somewhere neutral to sit - but for different moments: a TACTICAL item (a 2D
# view has no dolly/target constraint, so the screen can stay on its own cam instead of being
# assigned to an enemy hull and inheriting its side and scan view), and parking when the screen
# is idle or released rather than being left riding whatever it last filmed.
#
# It cannot help a 3D shot: cinematic_control renders a BLACK FRAME when the dolly and target
# ids differ, and camera_track folds a separate dolly away and assigns the console to the
# target. While a Dolly/Orbit/Chase shot is live the screen rides the subject, by engine rule.
DIRECTOR_SCREEN_CAM_KEY = "DIRECTOR_SCREEN_CAM"


def director_screen_cam(client_id, seat=False):
    """A program screen own camera, spawned on demand. Returns its id, or None.

    `seat=True` also assigns the client to it - for parking an idle or released screen, and
    for a tactical item. Left False the cam merely exists, which is all a lookup needs.
    """
    return _cam_ensure(client_id, DIRECTOR_SCREEN_CAM_KEY, roles="director_screen_cam",
                       seat=seat, move_console_link=False)


def director_cam_of(client_id):
    """This console's OWN camera id, or None. Never `sbs.get_ship_of_client`.

    While a shot is previewing, the client is assigned to the SUBJECT, so
    `get_ship_of_client` answers with whatever is being filmed. This is the same hazard
    `viewscreen_home_ship` exists to solve for the main screen.
    """
    from sbs_utils.procedural.inventory import get_inventory_value
    return get_inventory_value(client_id, "DIRECTOR_CAM", None)


def director_cam_ensure(client_id):
    """This CONSOLE own camera, spawned if needed, with the client seated on it.

    Call at the top of EVERY Director tab - see the module docstring for why. Returns the cam
    id, or None if the spawn failed.
    """
    return _cam_ensure(client_id, "DIRECTOR_CAM", roles="director_cam",
                       seat=True, move_console_link=True)


def _cam_ensure(client_id, key, roles="director_cam", seat=True, move_console_link=False):
    """One camera, remembered against `client_id` under `key`.

    The console own cam and a program screen cam are the same object with different jobs, so
    they are the same function with different flags rather than two near-copies that drift.

    `move_console_link` is the difference that matters: a Director console SHOULD take its
    `consoles` link with it (otherwise every overlay aimed at the ship it left paints over the
    panel), but a program screen must NOT - its console link belongs to its home bridge, and
    Stop puts the screen back there.
    """
    from sbs_utils.procedural.query import to_object, to_id
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    from sbs_utils.procedural.roles import remove_role, any_role
    from sbs_utils.procedural.links import link, unlink
    from sbs_utils.procedural.spawn import player_spawn

    sbs = _sbs()
    if sbs is None:
        return None

    prev_ship = sbs.get_ship_of_client(client_id)
    cam_id = get_inventory_value(client_id, key, None)
    cam = to_object(cam_id)

    # `to_object(...) is None` ALONGSIDE the None check is the RESTART GUARD: the inventory
    # value survives a sim_create() that took the object with it, so testing the id alone
    # would seat the client on a hull that no longer exists.
    if cam_id is None or cam is None:
        # has_science_scan gives friendly-eyes processing without being a player.
        # NO `gamemaster` role - that is what //comms/gamemaster routes gate on, and adding
        # it would open every GM menu on a console that is not a Game Master.
        cam = to_object(player_spawn(0, DIRECTOR_CAM_HEIGHT, 0, "",
                                     "#," + roles + ",has_science_scan", "invisible"))
        if cam is None:
            return None
        # The ONE thing keeping the cam out of every role("__player__") query - the ship
        # pickers, the rundown generators, scoring, end-game checks, NPC targeting.
        remove_role(cam, "__player__")
        cam_id = to_id(cam)
        set_inventory_value(client_id, key, cam_id)
        link(cam_id, "extra_scan_source", any_role("__npc__,__player__"))
        cam.data_set.set("ship_base_scan_range", DIRECTOR_CAM_SCAN_RANGE, 0)

    # THE CAM NEEDS A SIDE. `player_spawn(..., "#,...")` means "roles only, do not set a
    # side", and scan data is stored per the ORIGIN SIDE (science_set_scan_data writes
    # target_blob.set(tab, msg, origin.side)). With an empty side every write lands in a slot
    # nothing reads back, so scans silently do not take. The Game Master and the OU Admiral
    # both assign one right after spawning; this used not to, which is why the Director scans
    # behaved differently from the GM on identical code.
    if not getattr(cam, "side", None):
        prev = to_object(prev_ship) if prev_ship else None
        side = getattr(prev, "side", None) if prev is not None else None
        if side:
            cam.side = side

    if not seat:
        return cam_id

    # SEAT THE CLIENT. Unconditional for a console, because that is the whole point of the
    # function: the client may currently be on a shot subject rather than on its cam.
    if prev_ship != cam_id:
        sbs.assign_client_to_ship(client_id, cam_id)
        if move_console_link:
            # common_console_select linked this client to the ship it picked. Left there,
            # every overlay, banner and announce() aimed at that ship paints over the Director
            # panel - and because get_ship_of_client now answers with the cam, the operator
            # next console change unlinks the cam and orphans the old link for good.
            # server_console.mast re-links for the same reason; the GM and the Admiral do not,
            # and both leak it.
            #
            # Only unlink what this client was actually on, and only when it was not already
            # the cam - so a preview-subject reseat does not unlink a real player ship own
            # consoles.
            if prev_ship and prev_ship != cam_id:
                unlink(prev_ship, "consoles", client_id)
            link(cam_id, "consoles", client_id)

    # Back-pointer: //comms and //focus routes run server-side (their client_id is 0), so a
    # route that needs to reach this console own client reads it back off the cam.
    set_inventory_value(cam_id, "cam_client", client_id)
    return cam_id


def director_screen_park(client_id):
    """Park a program screen on its own cam - idle, released, or between shots.

    Without this a stopped screen is left riding whatever it last filmed, which means it keeps
    that hull side and scan view and shows its motion.
    """
    return director_screen_cam(client_id, seat=True)


def director_is_camera_point(object_id):
    """Is this subject a Director cam - that is, a PLACE rather than a hull?

    A click on empty space pans the cam and selects it, so the cam is a legitimate subject:
    park it in the middle of a fight and orbit it, and the shot is of the fight. Everything
    that treats a subject as a ship has to ask this first.
    """
    from sbs_utils.procedural.roles import has_roles
    if not object_id:
        return False
    try:
        return bool(has_roles(object_id, "director_cam"))
    except Exception:
        return False


def director_cam_point_name(object_id):
    """What to call a camera point on screen, or None if `object_id` is not one.

    The cam is spawned NAMELESS on purpose - `player_spawn(..., "", ...)`, because a name would
    put it in engine lists it is deliberately kept out of - so every labeller reads it back as
    `unnamed`, which says nothing about what the operator just did.

    NAMED AT THE DISPLAY LAYER instead, and named after the CONSOLE it belongs to: with four
    windows open, "camera point" alone does not say whose. The `cam_client` back-pointer is
    already there for the //focus routes, which run server-side and have no client of their own.
    """
    from sbs_utils.procedural.inventory import get_inventory_value
    if not director_is_camera_point(object_id):
        return None
    client_id = get_inventory_value(object_id, "cam_client", None)
    who = director_cam_name(client_id) if client_id else ""
    return (who + " point") if who else "camera point"


def director_cam_name(client_id, name=None):
    """Read or set the name this Director console is known by.

    Stored as CREW_NAME on the client, which is the key `director_screen_name` also reads - so
    a named screen says so on its own holding page and in the operator's summary. The only
    caller that sets one is the entry screen, and it passes `director_cam_default_name`; a
    console that never went through it reads as `unnamed`, which is not an error.
    """
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    if name is not None:
        name = str(name).replace("{", "(").replace("}", ")").replace("`", "'").strip()
        set_inventory_value(client_id, "CREW_NAME", name)
        sbs = _sbs()
        if sbs is not None:
            try:
                sbs.set_client_string(client_id, "crew_name", name)
            except Exception:
                # Older engines and the mock may not carry the client string; the inventory
                # value is the one the picker reads, so this is a nice-to-have.
                pass
    return get_inventory_value(client_id, "CREW_NAME", None) or ""


def director_cam_default_name(client_id, mode=None):
    """This console's name: `DIR01`, `PROG01`, `PRE01`. DERIVED, never typed.

    THE MODE PICKS THE PREFIX, because that is what a streamer is reading when four windows
    are open - "Director 3" on a program screen says the wrong thing about what it is. The
    numbering rule (lowest free per prefix, so a screen that leaves frees its number) lives in
    director_modes.py beside the modes themselves.

    IT IGNORES WHATEVER `CREW_NAME` ALREADY HOLDS, and that is the point rather than an
    oversight. `common_console_select` writes that key from the crew-name flow, so a client
    that named itself before opening the Director arrives with a person's name in it - and a
    program screen called "Doug" says nothing about what it is. There is no name field on the
    entry screen any more, so there is no typed name to protect, and the derivation is the
    only source.

    Stable under re-entry: `director_screen_suggest_name` skips this client's own name, so a
    console already called PROG01 asking again for a program name gets PROG01 back.
    """
    from director_modes import director_mode_of, director_screen_suggest_name
    if mode is None:
        mode = director_mode_of(client_id)
    return director_screen_suggest_name(client_id, mode)
