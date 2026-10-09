"""Siege boss loader + config (folder-scan, config-driven).

Each boss is a self-contained .amd file in maps/bosses/ - the same idea as an Open
Universe universe .amd. A boss file has one `# [Display](key)` heading carrying the
spawn config (Trigger / Low / Flies / Fleets / Difficulty / Named) and `##`
objective sub-quests authored in the SHARED AMD quest vocabulary (with
`Parent: siege_mission`). The siege BOSS dropdown lists the files by their heading;
siege.mast spawns the selected boss's forces on `siege_enemies_low` and grants its
objectives onto the siege_mission tree.

Drop a new .amd in maps/bosses/ and it appears in the dropdown with no code change.

TWO FOLDERS. `maps/bosses/` is this mission's own, and it is replaced whenever the
mission is updated - `sbs fetch` deletes and re-extracts a mission folder - so a boss an
author dropped there was lost on the next update. The second folder is theirs:
`<missions>/common_data/bosses/`, beside the saves, which no update touches. A boss in
either appears in the list. An author's boss is a .amd file only: per-boss MAST lives in
the mission and cannot be loaded from outside it, though `Hook:` can still name any
label the mission has.

A BOSS HAS A VOICE OF HER OWN. Beside her objectives the file may hold a
`## [Characters](characters)` and a `## [Dialogue](dialogue)` section, written exactly as
a mission file writes them. Siege spawns the selected boss's people and registers her
scenes as she arrives (`siege_boss_voice`), and grants only her objectives as quests
(`siege_boss_quests`) - see the end of this file.
"""
import os
import random
from sbs_utils.fs import get_mission_dir_filename
from sbs_utils.procedural.amd import amd_parse_facts, amd_makeup, amd_pct, amd_num
from sbs_utils.procedural.amd_quest import amd_quest_facts
from sbs_utils.procedural.quest import document_get_amd_file

_BOSS_DIR = "maps/bosses"
_SHARED_BOSS_DIR = "bosses"          # under common_data: the author's own, kept on update
_bosses = None   # cache: Display -> boss node


_TRIGGERS = ("enemies_low", "continuous")


def _problem(data, label, value, why):
    """Note a line the game cannot read. The boss is then LEFT OUT of the list and the
    log says which line (`siege_boss_scan`).

    Each of these used to do something else, and none of them said so: `Trigger:
    enemy_low` was a boss that never arrived; `Low: forty percent` and `Difficulty: +two`
    stopped the game on the runtime-error page seconds in; `Fleets: three` made the whole
    file unreadable, and the Boss list offered an entry called "Could not read this
    document" in its place. Defaulting instead would play a boss the author did not
    write - so it is not offered at all, with one line that names the file and the value.
    """
    data.setdefault("problems", []).append(
        "`%s: %s` %s" % (label.capitalize(), str(value).strip(), why))


def _whole(data, key, label, value):
    """A whole number from 0 up, else a problem."""
    n = amd_num(value)
    if isinstance(n, (int, float)) and float(n) == int(n) and n >= 0:
        data[key] = int(n)
    else:
        _problem(data, label, value, "is not a whole number from 0 up")


def _boss_facts():
    """The shared quest vocabulary + the siege boss spawn labels (Trigger / Low /
    Flies / Fleets / Difficulty / Named). Flies reuses OU's makeup convention."""
    quest = amd_quest_facts()
    def handler(data, label, value):
        if quest(data, label, value):
            return True
        if label == "trigger":
            data["trigger"] = str(value).strip().lower()
            if data["trigger"] not in _TRIGGERS:
                _problem(data, label, value, "is not `enemies_low` or `continuous`")
        elif label == "low":
            low = amd_pct(value)                         # "25%" -> 0.25
            if not isinstance(low, float) or low < 0:
                _problem(data, label, value, "is not a share of the raiders - write `Low: 40%`")
            else:
                # `Low: 40`, the sign left off, is 40% - not forty times the raiders,
                # which meant "arrive at once".
                if "%" not in str(value) and low > 1.0:
                    low = low / 100.0
                data["low"] = min(low, 1.0)
        elif label == "wave":
            _whole(data, "wave", label, value)           # seconds between waves (continuous)
        elif label == "flies":
            data["makeup"] = amd_makeup(value)           # "50% Kralien, 50% Torgoth"
        elif label == "fleets":
            _whole(data, "fleets", label, value)
        elif label == "difficulty":
            text = str(value).strip()                    # "+2" | "-1" | "7"
            data["difficulty"] = text
            body = text[1:] if text[:1] in "+-" else text
            if not body.isdigit() or (text[:1] not in "+-" and not 1 <= int(body) <= 11):
                _problem(data, label, value,
                         "is not a level from 1 to 11, or a step such as `+2` or `-1`")
        elif label == "named":
            named = []
            for item in str(value).split(","):           # "Name art, Name art"
                toks = item.split()
                if len(toks) >= 2:
                    named.append((toks[0], toks[1]))
            data["named"] = named
        else:
            return None
        return True
    return handler


def _boss_data(text):
    return amd_parse_facts(text, _boss_facts())


def siege_boss_shared_folder():
    """The author's own boss folder: `<missions>/common_data/bosses`. Made on demand, so
    there is somewhere to put a file the first time anybody looks for it."""
    from sbs_utils.fs import get_common_data_dir
    folder = os.path.join(get_common_data_dir(), _SHARED_BOSS_DIR)
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        pass                     # a read-only install simply has no shared bosses
    return folder


def siege_boss_folders():
    """Every folder bosses are read from, in order: the mission's own, then the author's."""
    return [get_mission_dir_filename(_BOSS_DIR), siege_boss_shared_folder()]


def _say(message):
    """Where an author will see it: `mast.runtime.log`, the log everybody reads."""
    import logging
    logging.getLogger("mast.runtime").warning("Siege boss: " + message)


def siege_boss_scan(force=False):
    """Scan the boss folders -> {Display: boss node}. Cached (force=True to rescan).

    THE AUTHOR'S BOSS WINS A NAME. The shared folder is read second, so a boss there with
    a name the mission already uses replaces it in the list - and says so. The other
    rule would make an author's own file silently absent, which is the worse surprise:
    the usual way to get here is copying a shipped boss and forgetting to rename the
    heading, and "my boss is not in the list" gives nothing to go on.
    """
    global _bosses
    if _bosses is not None and not force:
        return _bosses
    _bosses = {}
    shared = siege_boss_shared_folder()
    for folder in siege_boss_folders():
        try:
            files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".amd"))
        except OSError:
            files = []
        for fn in files:
            try:
                doc = document_get_amd_file(os.path.join(folder, fn), data_parser=_boss_data)
            except Exception as e:                       # noqa: BLE001
                # One unreadable file must not take the whole boss list with it.
                _say("%s could not be read (%s: %s) - it is left out of the list"
                     % (fn, type(e).__name__, e))
                continue
            for node in doc.get("children", []):         # one boss per file (first heading)
                d = node.get("data") or {}
                if node.get("key") == "__amd_error__":
                    # The reader does not raise on a file it cannot parse: it hands back
                    # a stand-in record, which this list then OFFERED as a boss called
                    # "Could not read this document".
                    _say("%s could not be read (%s) - it is left out of the list"
                         % (fn, str(node.get("description") or "").strip()[:160]))
                    break
                if d.get("problems"):
                    _say("%s is left out of the Boss list: %s. Fix the line and start "
                         "the mission again." % (fn, "; ".join(d["problems"])))
                    break
                display = str(d.get("display") or node.get("display_text") or node.get("key"))
                if folder == shared and display in _bosses:
                    _say("%s in common_data/bosses is named '%s', which this mission "
                         "already has - yours is the one in the list. Rename the "
                         "heading to keep both." % (fn, display))
                _bosses[display] = node
                break
    return _bosses


def siege_boss_list():
    """Dropdown options string: 'None, <Display>, ...'. None = today's behavior."""
    return ", ".join(["None"] + list(siege_boss_scan().keys()))


def siege_boss_get(sel):
    """The boss node for a selected Display (None for 'None' / unknown)."""
    if not sel or str(sel).strip().lower() == "none":
        return None
    return siege_boss_scan().get(str(sel))


def _bdata(sel):
    node = siege_boss_get(sel)
    return (node.get("data") or {}) if node else {}


def siege_boss_trigger(sel):
    """How the boss arrives: 'enemies_low' (spawn once when raiders thin - default)
    or 'continuous' (respawn waves until the clock runs out)."""
    return _bdata(sel).get("trigger", "enemies_low") if siege_boss_get(sel) else "none"


def siege_boss_wave(sel):
    """Seconds between waves for a continuous boss (default 45)."""
    return int(_bdata(sel).get("wave", 45))


def siege_boss_low_pct(sel):
    """Fraction of the peak enemy count below which the boss triggers (default .25)."""
    return float(_bdata(sel).get("low", 0.25))


def siege_boss_fleet_count(sel):
    return int(_bdata(sel).get("fleets", 0))


def siege_boss_difficulty(sel, base):
    """Resolve the boss difficulty: '+2'/'-1' relative to base, or an absolute int."""
    d = _bdata(sel).get("difficulty")
    base = int(base)
    if d is None:
        return base
    d = str(d).strip()
    if d.startswith("+"):
        return base + int(d[1:] or 0)
    if d.startswith("-"):
        return max(1, base - int(d[1:] or 0))
    try:
        return int(d)
    except ValueError:
        return base


def siege_boss_race(sel):
    """Pick a race from the boss's Flies makeup (weighted dict / list / string)."""
    m = _bdata(sel).get("makeup")
    if isinstance(m, dict) and m:
        return random.choices(list(m.keys()), weights=list(m.values()))[0]
    if isinstance(m, list) and m:
        return random.choice(m)
    if isinstance(m, str) and m:
        return m
    return "kralien"


def siege_boss_named(sel):
    """List of (name, art) named flagship hulls for the boss (may be empty)."""
    return list(_bdata(sel).get("named", []))


def siege_boss_hook_ready(sel):
    """The boss's `Hook:` label when the story HAS a label by that name, else ''.

    A hook is MAST, and a boss file is not: the label lives in some addon, or in a folder
    the author added to the mission. When it is not there - a typo, or the folder went
    with an update - `prefab_spawn` of the name was "Calling undefined label" on the
    runtime-error page at the moment the boss arrived, with her ships and objectives
    already in the game. Now the boss arrives without her hook, and the log says why.
    """
    name = str(siege_boss_hook(sel) or "").strip()
    if not name:
        return ""
    try:
        from sbs_utils.helpers import FrameContext
        mast = FrameContext.mast
        labels = getattr(mast, "labels", None)
        if labels is not None and name not in labels:
            _say("the boss '%s' says `Hook: %s`, and no label in this mission has that "
                 "name, so she arrives without it. A hook is a MAST label: check the "
                 "spelling, and that its file is still in the mission" % (sel, name))
            return ""
    except Exception:                                    # noqa: BLE001
        pass
    return name


def siege_boss_hook(sel):
    """A MAST label the boss runs (via prefab_spawn) for bespoke behavior beyond the
    config spawn - e.g. biomech_infestation (the LM biomech addon). '' if none."""
    return _bdata(sel).get("hook", "")


# --- a boss with a voice: her own Characters and Dialogue ------------------------------
#
# A boss file used to be read for two things only: the boss's own lines and QUESTS. Every
# record under the boss was granted as a quest, whatever it said - so an author who typed
# the two sections they already knew from a mission file,
#
#     ## [Characters](characters)        ## [Dialogue](dialogue)
#
# got no cast and no call, and six jobs on the board named "Characters", "The Corsair
# Queen", "Dialogue" and so on. A boss could have objectives and a sentence for winning,
# and no person and no scene; anything she said had to live in a second file inside the
# mission, read by a hook the author wrote in MAST.
#
# Now the two sections are read as what they are, the way a mission's own are
# (`lifeforms_spawn` / `dialogue_register_scenes`, the two lines the `amd` template's
# story.mast has), and they are NOT granted as quests. The words are the ones a mission
# file already uses - nothing here is new vocabulary.
#
# ONLY THE SELECTED BOSS, and only when she arrives: `siege_boss_voice(sel)` is called by
# siege.mast as it loads her. KEYED, NOT LATCHED: a character is found by its key before
# it is made, and a scene is registered under its key, so loading twice makes nothing
# twice - and there is no module-level "already loaded" flag for a mission restart in a
# reused interpreter to inherit.

_VOICE_SECTIONS = ("characters", "dialogue")


def _siege_boss_is_section(node, key):
    """Whether a record under the boss is the `key` SECTION rather than a quest that
    happens to be keyed the same. A section heading says nothing about what it is (no
    fence), or says its own name; a quest says `Quest`, `Beat`, `Arc`..."""
    if str(node.get("key") or "").strip().lower() != key:
        return False
    kind = str((node.get("data") or {}).get("__kind__") or "").strip().lower()
    return kind in ("", key, key.rstrip("s"))


def siege_boss_section(sel, key):
    """The boss file's own `## [..](key)` section node - `characters` or `dialogue` - or
    None when the selected boss has none (the three shipped ones have neither)."""
    node = siege_boss_get(sel)
    if node is None:
        return None
    key = str(key).strip().lower()
    for child in node.get("children") or []:
        if _siege_boss_is_section(child, key):
            return child
    return None


def siege_boss_quests(sel):
    """The boss node to hand `quest_grant_amd`: her objectives, WITHOUT her cast and her
    scenes.

    A boss with neither section gets the very node the scan read, untouched - so the
    shipped bosses are granted exactly as they always were. None for 'None' / unknown.
    """
    node = siege_boss_get(sel)
    if node is None:
        return None
    kids = node.get("children") or []
    keep = [c for c in kids
            if not any(_siege_boss_is_section(c, k) for k in _VOICE_SECTIONS)]
    if len(keep) == len(kids):
        return node
    quests = dict(node)
    quests["children"] = keep
    return quests


def siege_boss_voice(sel):
    """Bring the selected boss's own people and scenes into the game.

    Her `## [Characters](characters)` are spawned the way a mission's are, and her
    `## [Dialogue](dialogue)` scenes are registered, so a hail or a comms scene written
    in the boss file works - including one whose answer `; completes` a quest in the same
    file, or a Beat there whose `Action:` places her call.

    Call it BEFORE granting her quests: a Beat's `Action:` runs as it starts, and
    `queen hails queen_calls` needs both the person and the scene to be there.

    Safe to call again, and for a boss with no voice (it does nothing).

    Returns:
        tuple: ``(characters, scenes)`` - how many of each the file holds.
    """
    cast = siege_boss_section(sel, "characters")
    scenes = siege_boss_section(sel, "dialogue")
    if cast is None and scenes is None:
        return (0, 0)
    from sbs_utils.procedural.amd_lifeforms import lifeforms_spawn
    from sbs_utils.procedural.amd_dialogue import dialogue_register_scenes
    people = lifeforms_spawn(cast) if cast is not None else {}
    said = dialogue_register_scenes(scenes) if scenes is not None else {}
    return (len(people), len(said))
