"""Lobby helpers: a games listbox (item/title templates) and per-game help
text shown in the details panel. Games are still discovered via
casino_games_list(); help comes from a `help` metadata value on the game's
//casino/game route when present, else this built-in table."""
from sbs_utils.procedural.gui import gui_row, gui_text, gui_text_escape
from sbs_utils.procedural.execution import labels_get_type


# Every casino game now declares its own `help` (and min_bet) via a metadata
# block on its //casino/game route - see casino_game_help() below. This dict is
# just the fallback for any game that predates metadata (currently none).
CASINO_GAME_HELP = {
}

def casino_game_meta(key, name, default=None):
    """A metadata value declared on a game's //casino/game/<key> route (stored in
    the route label's inventory via its metadata block), or `default`."""
    for lbl in labels_get_type("casino/game/"):
        if getattr(lbl, "game_key", None) == key:
            return lbl.get_inventory_value(name, default)
    return default

def casino_game_help(key):
    # Prefer a `help` metadata value on the game's route; fall back to the
    # built-in table for games that haven't migrated to metadata yet.
    meta = casino_game_meta(key, "help", None)
    if meta:
        return meta
    return CASINO_GAME_HELP.get(key, "Select a game to see how to play.")


def casino_game_list_template(item):
    gui_row("row-height: 1.4em; padding:8px;")
    gui_text(f"$text:{gui_text_escape(item.get('name', '?'))};justify:left;")

def casino_game_list_title():
    gui_row("row-height: 1.4em; padding:8px; background:#1578;")
    gui_text("$text:Games;justify:center;")
