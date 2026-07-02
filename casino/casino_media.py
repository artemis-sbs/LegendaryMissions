"""Card-atlas registration. Call casino_register_decks() once at setup; then
draw any card with gui_image("card_arv_<castle>_<value>") /
"card_ter_<suit>_<rank>". See media/README.md for the sheet geometry.

NOTE (render-verify): the image path is relative to the mission dir. As a
packaged addon the media may need to live under the mission's media
resources; adjust CASINO_MEDIA if paths don't resolve in-engine.
"""
from sbs_utils.procedural.gui import gui_image_add_atlas

# Card sheets live in the LM media source (media/LegendaryMissions/casino/) so
# they resolve the same way as the hangar's media - the image atlas checks the
# path against the running mission's folder (<mission>/media/LegendaryMissions/
# casino/*.png), which the LM media resource populates.
CASINO_MEDIA = "media/LegendaryMissions/casino"
_ARV_CELL = 256                 # arvonian_deck.png cell size
_TER_W, _TER_H = 190, 280       # terran_deck.png cell size
RANKS = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
SUITS = ["spades","hearts","diamonds","clubs"]

_registered = False

def casino_register_decks(force=False):
    """Idempotent: register every card sub-rect as an atlas key."""
    global _registered
    if _registered and not force:
        return
    arv = CASINO_MEDIA + "/arvonian_deck"
    for castle in range(4):
        for value in range(16):
            x, y = value * _ARV_CELL, castle * _ARV_CELL
            gui_image_add_atlas("card_arv_%d_%d" % (castle, value), arv,
                                x, y, x + _ARV_CELL, y + _ARV_CELL)
    ter = CASINO_MEDIA + "/terran_deck"
    for s, _suit in enumerate(SUITS):
        for c, _rank in enumerate(RANKS):
            x, y = c * _TER_W, s * _TER_H
            gui_image_add_atlas("card_ter_%s_%s" % (_suit, _rank), ter,
                                x, y, x + _TER_W, y + _TER_H)
    # backs (full-image keys)
    gui_image_add_atlas("card_arv_back", CASINO_MEDIA + "/arvonian_back")
    gui_image_add_atlas("card_ter_back", CASINO_MEDIA + "/terran_back")
    _registered = True

def card_arv_key(castle, value):
    return "card_arv_%d_%d" % (castle, value)

def card_ter_key(suit, rank):
    return "card_ter_%s_%s" % (suit, rank)
