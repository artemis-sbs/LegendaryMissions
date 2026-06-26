import datetime


def game_results_timestamp():
    """Wall-clock timestamp ("YYYY-MM-DD HH:MM:SS") for a game-results record.

    Computed in Python on purpose: MAST inline (~~ ~~) runs with a restricted
    __builtins__ (the mast_globals allow-list, no __import__), and datetime's
    now()/strftime() trigger an internal import that fails there. A normal module
    function runs with real builtins, so calling it from MAST is safe.
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def game_results_map(world_select):
    """Best-effort readable scenario/map name for a game-results record.

    LM's WORLD_SELECT may be a map object (with .display_name / .path), a plain
    string, or None. (getattr isn't in MAST's eval globals, so do this in Python.)
    """
    if world_select is None:
        return ""
    name = getattr(world_select, "display_name", None) or getattr(world_select, "path", None)
    return str(name) if name else str(world_select)
