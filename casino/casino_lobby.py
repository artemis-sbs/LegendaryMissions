"""Lobby helpers: a games listbox (item/title templates) and per-game help
text shown in the details panel. Games are still discovered via
casino_games_list(); help is keyed by the game's key."""
from sbs_utils.procedural.gui import gui_row, gui_text


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
    "korata3": "KoraTa - Ghost-Writing (3-bit). Duel the Understander's "
               "apprentice over five rounds: play your cards as VALUES to build "
               "your run, or as OPCODES (the gate on the card) to corrupt "
               "theirs. Bet across two streets; high score takes the pot. "
               "Tighter 0-7 values - more ties.",
    "korata4": "KoraTa - Ghost-Writing (4-bit). The wide table: same duel, but "
               "values run 0-15 for bigger scores and fewer ties. Build your "
               "run, sabotage the apprentice's with your cards' gates, and bet "
               "across two streets. High score wins.",
    "market": "Pilot Market. Spend your winnings: buy and sell craft upgrades "
              "and gear (chips first, then the crew's side credits). Earn a "
              "patron's trust at the bar and the grey market opens up.",
}

def casino_game_help(key):
    return CASINO_GAME_HELP.get(key, "Select a game to see how to play.")


def casino_game_list_template(item):
    gui_row("row-height: 1.4em; padding:8px;")
    gui_text(f"$text:{item.get('name', '?')};justify:left;")

def casino_game_list_title():
    gui_row("row-height: 1.4em; padding:8px; background:#1578;")
    gui_text("$text:Games;justify:center;")
