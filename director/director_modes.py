"""What a Director console opened AS: program, preview, or the control console.

The Director is a STREAMING TOOL. It does not commandeer mainscreens or crew seats - Cosmos has
plenty of other ways to put something on a bridge screen, and taking a crew console away
mid-game is a way to ruin somebody's game. Instead a streamer opens extra clients and declares
what each one is:

    program    an output screen; this is what the streamer captures
    preview    the same, showing the shot BEFORE it goes out
    director   the control console - main page, rundown editor, capture

That simplification deleted a whole layer. There is no "home console" to remember and no
restore-to-your-old-bridge path on Stop, because a director screen never had a bridge: Stop just
releases its camera and parks it on its own cam.

A MODE IS A SELECTION, AND THAT IS ALL THE SELECTION THERE IS. There was a picker here once -
`director_screen_rows`, a pre-tick that had to be one-shot so an un-tick could stick, and a set
remembering which ids had been offered. It answered a question nobody had: a console that opened
as Program had already said what it was, and the list only restated that one repaint behind.
Send now goes to every program screen and preview follows the editor, so what is left is the
declaration and the two sets it produces.

Every public name is prefixed `director_`: an addon's `def`s become MAST globals in one flat
mission-wide namespace, last loaded wins, silently. A leading underscore is private.
"""

DIRECTOR_MODES_ALL = ("director", "program", "preview")
DIRECTOR_MODE_LABELS_ALL = {"director": "Director", "program": "Program", "preview": "Preview"}

# The name prefix each mode suggests on the entry screen. PROG01 / PRE01 / DIR01 rather than
# "Director 1" for all three: a streamer with four windows open is reading tab titles, and
# "Director 3" on a program screen says the wrong thing about what it is.
DIRECTOR_MODE_PREFIX = {"director": "DIR", "program": "PROG", "preview": "PRE"}


def director_modes_reset():
    """Kept as the per-mission hook even though there is no state left to clear.

    The addon top level calls it beside the other resets, and a module that grows state later
    should not have to remember to add the call back. Removing it is how a run-2 bug gets in.
    """
    return True


def director_mode_list():
    """The comma-separated labels for the entry screen's mode radio."""
    return ",".join(DIRECTOR_MODE_LABELS_ALL[m] for m in DIRECTOR_MODES_ALL)


def director_mode_for(label):
    """The mode a radio label means. Anything unknown reads as `director`."""
    want = str(label or "").strip().lower()
    for mode in DIRECTOR_MODES_ALL:
        if DIRECTOR_MODE_LABELS_ALL[mode].lower() == want or mode == want:
            return mode
    return "director"


def director_mode_label(mode):
    return DIRECTOR_MODE_LABELS_ALL.get(str(mode or "").strip().lower(), "Director")


def director_mode_set(client_id, mode):
    """Declare what this console is. Returns the stored mode."""
    mode = director_mode_for(mode)
    from sbs_utils.procedural.inventory import set_inventory_value
    set_inventory_value(client_id, "DIRECTOR_SCREEN_MODE", mode)
    return mode


def director_mode_of(client_id):
    """This console's declared mode, defaulting to `director`."""
    from sbs_utils.procedural.inventory import get_inventory_value
    return director_mode_for(get_inventory_value(client_id, "DIRECTOR_SCREEN_MODE", None))


def director_mode_declared(client_id):
    """Has this console COMMITTED a mode, as opposed to defaulting to one?

    `director_mode_of` cannot answer this: it defaults to `director`, so a console that has
    never seen the entry screen is indistinguishable from one that chose the control console.
    That distinction only started to matter when the entry screen became reachable BEFORE the
    game starts - see director_mode_resume_take.
    """
    from sbs_utils.procedural.inventory import get_inventory_value
    return get_inventory_value(client_id, "DIRECTOR_SCREEN_MODE", None) is not None


def director_mode_clear(client_id):
    """Forget the declaration: this console has not said what it is.

    What Cancel does. A console that backs out of the entry screen has to become genuinely
    undeclared, or the next visit would skip the screen it just cancelled out of.
    """
    from sbs_utils.procedural.inventory import set_inventory_value
    set_inventory_value(client_id, "DIRECTOR_SCREEN_MODE", None)
    director_mode_resume_take(client_id)
    return True


# --- surviving the start of the game ------------------------------------------------------
#
# THE PROBLEM THIS SOLVES. A console set up before the mission starts is rerouted through
# `game_started_console` the moment the server presses Start, and that walks it into its
# console the ordinary way - `jump(console.label)`, which for this addon is `director_entry`.
# So a screen the streamer had already declared as PROG01 lands back on the pin screen, and
# with four windows open somebody has to walk round and press Start in all of them. The whole
# point of setting up early is not having to.
#
# A ONE-SHOT flag rather than "skip whenever a mode is declared", because the picker path and the
# start reroute arrive at the same label by the same jump and are otherwise indistinguishable.
# Armed at the moment a mode is committed and CONSUMED by the next entry: the start reroute
# spends it, and an operator who later re-picks Director from the console list finds it spent
# and gets the screen - which is the only way to change a mode.


def director_mode_resume_arm(client_id):
    """Say that the next entry to the pin screen should be skipped. Consumed once."""
    from sbs_utils.procedural.inventory import set_inventory_value
    set_inventory_value(client_id, "DIRECTOR_RESUME", True)
    return True


def director_mode_resume_take(client_id):
    """Spend the resume flag. True when it was armed - meaning: go straight to the mode."""
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    armed = bool(get_inventory_value(client_id, "DIRECTOR_RESUME", False))
    set_inventory_value(client_id, "DIRECTOR_RESUME", False)
    return armed


def _clients_in_mode(mode):
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.inventory import get_inventory_value
    out = []
    for cid in sorted(role("console")):
        if get_inventory_value(cid, "DIRECTOR_SCREEN_MODE", None) == mode:
            out.append(cid)
    return out


def director_program_screens():
    """Every console that declared itself a program output."""
    return _clients_in_mode("program")


def director_preview_screens():
    """Every console that declared itself a preview monitor."""
    return _clients_in_mode("preview")


def director_screen_name(client_id):
    """What a screen calls itself, plus what it is currently showing."""
    from sbs_utils.procedural.inventory import get_inventory_value
    name = get_inventory_value(client_id, "CREW_NAME", None) or "unnamed"
    showing = get_inventory_value(client_id, "CONSOLE_TYPE", None) or ""
    name = str(name).replace("{", "(").replace("}", ")").replace("`", "'").strip()
    if showing and showing != "director":
        return name + " - " + str(showing)
    return name


def director_screen_summary():
    """"2 program, 1 preview" - what the header says instead of a picker.

    The unhelpful case is said out loud. "Nothing happened" is the commonest confusion on this
    console and the reason is invisible otherwise: with no screen declared there is nowhere for
    the show to go, and Send is a button that appears to do nothing.
    """
    program = len(director_program_screens())
    preview = len(director_preview_screens())
    if not program and not preview:
        return "no screens - open a client and declare it Program or Preview"
    return str(program) + " program, " + str(preview) + " preview"


def director_screen_suggest_name(client_id, mode):
    """`PROG01`, `PRE02`, `DIR01` - the LOWEST free number for that mode's prefix.

    Lowest free rather than a count, twice over: a leaked console inflates a count, and a
    number freed by a screen that left should be reusable. Scanning the names actually in use
    and taking the first gap is stable under both.

    Numbered PER PREFIX, so a program screen and a preview screen can both be 01 - they read
    as PROG01 and PRE01 and nobody confuses them.
    """
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.inventory import get_inventory_value
    prefix = DIRECTOR_MODE_PREFIX.get(director_mode_for(mode), "DIR")
    taken = set()
    for cid in role("console"):
        if cid == client_id:
            continue
        name = str(get_inventory_value(cid, "CREW_NAME", "") or "")
        if name.startswith(prefix):
            tail = name[len(prefix):].strip()
            if tail.isdigit():
                taken.add(int(tail))
    n = 1
    while n in taken:
        n += 1
    return prefix + str(n).zfill(2)


def director_mode_fingerprint():
    """Changes when the declared screens or their names do - drives the live refresh.

    Deliberately does NOT include what each screen is currently showing: the player rewrites
    CONSOLE_TYPE every time it changes a screen's item, and watching that would repaint the
    operator's page every dwell, under their hands.
    """
    from sbs_utils.procedural.inventory import get_inventory_value
    parts = []
    for mode in ("program", "preview"):
        for cid in _clients_in_mode(mode):
            parts.append(str(cid) + ":" + mode + ":"
                         + str(get_inventory_value(cid, "CREW_NAME", "?")))
    return "|".join(parts)
