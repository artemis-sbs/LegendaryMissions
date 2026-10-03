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


def _boss_facts():
    """The shared quest vocabulary + the siege boss spawn labels (Trigger / Low /
    Flies / Fleets / Difficulty / Named). Flies reuses OU's makeup convention."""
    quest = amd_quest_facts()
    def handler(data, label, value):
        if quest(data, label, value):
            return True
        if label == "trigger":
            data["trigger"] = str(value).strip().lower()
        elif label == "low":
            data["low"] = amd_pct(value)                 # "25%" -> 0.25
        elif label == "wave":
            data["wave"] = int(amd_num(value))           # seconds between waves (continuous)
        elif label == "flies":
            data["makeup"] = amd_makeup(value)           # "50% Kralien, 50% Torgoth"
        elif label == "fleets":
            data["fleets"] = int(amd_num(value))
        elif label == "difficulty":
            data["difficulty"] = str(value).strip()      # "+2" | "-1" | "7"
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


def siege_boss_hook(sel):
    """A MAST label the boss runs (via prefab_spawn) for bespoke behavior beyond the
    config spawn - e.g. biomech_infestation (the LM biomech addon). '' if none."""
    return _bdata(sel).get("hook", "")
