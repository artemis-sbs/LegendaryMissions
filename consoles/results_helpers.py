import datetime


def game_results_timestamp():
    """Wall-clock timestamp ("YYYY-MM-DD HH:MM:SS") for a game-results record.

    Computed in Python on purpose: MAST inline (~~ ~~) runs with a restricted
    __builtins__ (the mast_globals allow-list, no __import__), and datetime's
    now()/strftime() trigger an internal import that fails there. A normal module
    function runs with real builtins, so calling it from MAST is safe.
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
