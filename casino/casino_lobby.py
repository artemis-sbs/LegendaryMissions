"""Lobby helpers: a games listbox (item/title templates) and per-game help
text shown in the details panel. Games are still discovered via
casino_games_list(); help comes from a `help` metadata value on the game's
//casino/game route when present, else this built-in table."""
from sbs_utils.procedural.gui import gui_row, gui_text
from sbs_utils.procedural.execution import labels_get_type


CASINO_GAME_HELP = {
    "bar": "The bar. Grab a drink, toast the room, and chat with the "
           "patrons. Rumors and side jobs, later.",
    "nibble": "Nibble (Arvonian). Beat the dealer with a hand of 20 or less - "
              "Hit to draw, Stand to hold. Castles on later cards score big, "
              "so pressing your luck is dangerous. Dealer wins ties. "
              "A very tough table.",
    "blackjack": "Blackjack. Classic 21 on a standard deck. Hit or Stand to "
                 "beat the dealer without going over 21. A natural blackjack "
                 "pays 3:2. Dealer stands on 17.",
    "gates": "Gates (Arvonian, baccarat-style). Bet on which hand - Player or "
             "Banker - scores higher. Each hand folds bit cards through "
             "logic-gate opcodes (AND/OR/NOR/NAND/XOR). Banker wins ties.",
    "choga": "Choga - Soul Tickle (Arvonian stud). Ante, then see your five "
             "cards and the Understander's up-card and choose Raise (2x) or "
             "Fold. Best poker hand wins; the dealer plays with a pair or "
             "better. A clean checksum pays a bonus.",
    "poker": "Video Poker (Jacks or Better). You're dealt five cards - Hold "
             "the ones you want and Draw the rest. Paid by the paytable: a "
             "pair of Jacks or better returns your bet, up to a Royal Flush "
             "at 250x. No dealer - just you and the odds.",
    "parity": "Parity (Arvonian). The house's fast game: three cards XOR into "
              "a register (0-15) and you bet on it. Even/Odd and High/Low pay "
              "even money. Quick, casual, and a fair shake.",
    # KoraTa declares its own help via `help` metadata on its //casino/game
    # route (korata.mast) - it no longer needs an entry here.
    "market": "Pilot Market. Spend your winnings: buy and sell craft upgrades "
              "and gear (chips first, then the crew's side credits). Earn a "
              "patron's trust at the bar and the grey market opens up.",
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
    gui_text(f"$text:{item.get('name', '?')};justify:left;")

def casino_game_list_title():
    gui_row("row-height: 1.4em; padding:8px; background:#1578;")
    gui_text("$text:Games;justify:center;")
