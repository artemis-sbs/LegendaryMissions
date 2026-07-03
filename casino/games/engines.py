"""Pure-Python casino game engines. No MAST/GUI, no sbs imports.

Deterministic: every engine takes an injected random.Random so tests and
house-edge sims are reproducible. Rules confirmed against the original
bundle.js and info pages (see casino/CASINO_RULES.md, casino/rules_text.md).

Ready to drop into casino/games/ when coding starts.
"""
from dataclasses import dataclass, field


def popcount(n):
    return bin(n & 0b11).count("1")   # castle type is 2-bit


# =========================================================================
# NIBBLE  (Arvonian deck; confirmed from bundle.js module 8)
# =========================================================================
@dataclass
class NibbleCard:
    num: int      # face value (0..maxnum-1)
    type: int     # castle, 0-3 (2-bit); also the color-row of the art

def nibble_deck(maxnum=16):
    # value x castle(4).  (color axis not represented in our art)
    return [NibbleCard(num, t) for t in range(4) for num in range(maxnum)]

def nibble_score(cards):
    """Return (total, num). total = face-sum + positional castle score."""
    multi = 1
    castle = 0
    numscore = 0
    for c in cards:
        castle += popcount(c.type) * multi
        multi *= 2
        numscore += c.num
    return castle + numscore, numscore

def nibble_is_natural(cards):
    if len(cards) != 2:
        return False
    _, num = nibble_score(cards)
    return num == 0 or num == 14

def nibble_settle(player_cards, dealer_cards, bet, player_wins_ties=False):
    """Signed payout delta, replicating endHand(). ``player_wins_ties`` is a
    casino house-rule softener (the original has the dealer win ties); combined
    with a lower dealer hit target it makes the (very house-favored) table
    friendlier. dealer_cards must already be played out per policy."""
    player = nibble_score(player_cards)[0]
    dealer = nibble_score(dealer_cards)[0]
    is_nat = nibble_is_natural(player_cards)
    is_nat_dealer = nibble_is_natural(dealer_cards)
    rewards_cards = len(player_cards)
    cost_cards = len(dealer_cards)         # handId = DEALER for DEALER_MUST
    cost = bet * (cost_cards - 1)
    cost = cost if cost >= bet else bet
    reward = bet * (2 ** (rewards_cards - 2))
    if is_nat_dealer:
        cost = max(cost, bet * 2)
        return -cost
    if is_nat:
        return bet * 2
    if dealer > 20 and player <= 20:
        return reward
    if player > 20:
        return -cost
    if dealer > player:
        return -cost
    if dealer < player:
        return reward
    return reward if player_wins_ties else -cost   # tie

def nibble_play_dealer(dealer_cards, draw, must=15, player_busted=False,
                       player_natural=False):
    """Dealer draws while total < must, unless a natural is present or the
    player already busted (mirrors endHand's guard). Mutates/returns list."""
    cards = list(dealer_cards)
    if player_natural or nibble_is_natural(cards) or player_busted:
        return cards
    while nibble_score(cards)[0] < must:
        if nibble_is_natural(cards):
            break
        cards.append(draw())
    return cards


# --- MAST-friendly deck drivers (no lambdas needed in MAST) -----------------
def nibble_deal(deck, n):
    """Pop n cards off the end of a (shuffled) deck list. Returns the hand."""
    return [deck.pop() for _ in range(n)]

def nibble_play_dealer_deck(dealer_cards, deck, must=15,
                            player_busted=False, player_natural=False):
    """As nibble_play_dealer but draws from a deck list (pop) - MAST-callable."""
    return nibble_play_dealer(dealer_cards, deck.pop, must,
                              player_busted, player_natural)

def nibble_card_key(card):
    """Atlas key for a NibbleCard: card_arv_<castle>_<value>."""
    return "card_arv_%d_%d" % (card.type, card.num)


# =========================================================================
# GATES  (baccarat-style; confirmed from bundle.js module 12 + info page)
# =========================================================================
OP_OR, OP_AND, OP_NOR, OP_NAND, OP_XOR = 0, 1, 2, 3, 4
MASK = 0b111   # values are 3-bit (0-7)

# The Arvonian card's operator is PRINTED on the card (the corner logic-gate
# glyph), derived from its (value, castle):  op = (value + castle) % 4 over the
# gate order [OR, AND, NOR, NAND].  There is NO XOR on the deck (confirmed by
# reading arvonian_deck.png across all four castle rows).  Both Gates and OpCode
# read the operator off the card via this mapping instead of inventing one, so
# the folded gates always match the glyphs on screen.
def arv_opcode(value, castle):
    return (value + castle) % 4   # -> OP_OR / OP_AND / OP_NOR / OP_NAND

def gates_apply(op, a, b):
    if op == OP_AND:  r = a & b
    elif op == OP_OR: r = a | b
    elif op == OP_NOR: r = ~(a | b)
    elif op == OP_NAND: r = ~(a & b)
    elif op == OP_XOR: r = a ^ b
    else: raise ValueError(op)
    return r & MASK

@dataclass
class GatesHand:
    # Real Arvonian cards (value 0-7, castle 0-3). The gate folded in when a
    # card joins is that card's OWN printed corner opcode (arv_opcode), so the
    # operators the hand folds through are exactly the glyphs drawn on the cards.
    # bits/ops are derived so gates_score and the display helpers are unchanged.
    cards: list = field(default_factory=list)

    @property
    def bits(self):
        return [c[0] for c in self.cards]

    @property
    def ops(self):
        return [arv_opcode(v, castle) for (v, castle) in self.cards[1:]]

def gates_score(hand):
    score = hand.bits[0]
    for i, op in enumerate(hand.ops):
        score = gates_apply(op, score, hand.bits[i + 1])
    return score

def gates_banker_draws(banker_total, player_third):
    """Baccarat tableau. player_third is None if player stood."""
    if banker_total <= 1: return True
    if player_third is None:
        return banker_total <= 5           # banker draws if 5 or less when player stood
    if banker_total == 2: return player_third != 6
    if banker_total == 3: return player_third in (2, 3, 4, 5)
    if banker_total == 4: return player_third in (4, 5)
    return False                            # 5,6,7 stand

def gates_settle(bet, bet_on_player, player_total, banker_total):
    """bet_on_player: True=player hand, False=banker. Banker wins ties."""
    if player_total == banker_total:
        winner_is_player = False            # banker wins ties
    else:
        winner_is_player = player_total > banker_total
    won = (bet_on_player == winner_is_player)
    return bet if won else -bet

# --- MAST-friendly round driver + display helpers ---------------------------
import random as _random
GATES_OPS = [OP_OR, OP_AND, OP_NOR, OP_NAND]   # the four deck gates (no XOR)
OP_NAMES = {OP_OR: "OR", OP_AND: "AND", OP_NOR: "NOR", OP_NAND: "NAND", OP_XOR: "XOR"}

def gates_op_name(op):
    return OP_NAMES.get(op, "?")

def gates_bit_key(value):
    """Deprecated: castle-row-0 atlas key (value 0-7). Kept for back-compat;
    gates now draws real cards via gates_card_key so the corner opcode shows."""
    return "card_arv_0_%d" % value

def gates_card_key(card):
    """Atlas key for a real Arvonian gates card (value, castle) - renders the
    value AND its printed corner opcode."""
    value, castle = card
    return "card_arv_%d_%d" % (castle, value)

def gates_ops_str(hand):
    return " ".join(gates_op_name(o) for o in hand.ops)

def _gates_card(r):
    """Deal one Arvonian card (value 0-7, castle 0-3); its operator is the
    printed corner glyph arv_opcode(value, castle)."""
    return (r.randint(0, 7), r.randint(0, 3))

def _gates_new_hand(r):
    return GatesHand(cards=[_gates_card(r), _gates_card(r)])

def gates_play_round(hit_rule=True, rng=None):
    """Deal + apply the hit tableau. Returns (player, banker, p_total, b_total).
    Operators are read off the cards (arv_opcode), never invented - so the folded
    gates match the corner glyphs shown on screen."""
    r = rng or _random
    p = _gates_new_hand(r)
    b = _gates_new_hand(r)
    pt, bt = gates_score(p), gates_score(b)
    if hit_rule:
        p_third = None
        if pt <= 5 and bt not in (6, 7):
            p.cards.append(_gates_card(r)); p_third = p.cards[-1][0]; pt = gates_score(p)
        if gates_banker_draws(bt, p_third):
            b.cards.append(_gates_card(r)); bt = gates_score(b)
    return p, b, pt, bt


# =========================================================================
# BLACKJACK  (standard 52; Terran deck)
# =========================================================================
RANKS = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
def bj_card_value(rank):
    if rank == "A": return 11
    if rank in ("10","J","Q","K"): return 10
    return int(rank)

def bj_deck(shoes=1):
    return [(r, s) for _ in range(shoes) for s in range(4) for r in RANKS]

def bj_hand_value(cards):
    """Best total <=21 if possible; aces soften."""
    total = sum(bj_card_value(r) for r, _ in cards)
    aces = sum(1 for r, _ in cards if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def bj_is_blackjack(cards):
    return len(cards) == 2 and bj_hand_value(cards) == 21

def bj_play_dealer(cards, draw, hit_soft_17=False):
    cards = list(cards)
    while True:
        total = bj_hand_value(cards)
        soft = ("A" in [r for r, _ in cards]) and \
               (sum(bj_card_value(r) for r, _ in cards) != total)  # an ace counts as 11
        if total < 17 or (total == 17 and soft and hit_soft_17):
            cards.append(draw())
        else:
            return cards

def bj_settle(player_cards, dealer_cards, bet, blackjack_pays=1.5):
    p, d = bj_hand_value(player_cards), bj_hand_value(dealer_cards)
    pbj, dbj = bj_is_blackjack(player_cards), bj_is_blackjack(dealer_cards)
    if pbj and dbj: return 0
    if pbj: return bet * blackjack_pays
    if dbj: return -bet
    if p > 21: return -bet
    if d > 21: return bet
    if p > d: return bet
    if p < d: return -bet
    return 0                                # push

# --- MAST-friendly deck drivers ---------------------------------------------
_TER_SUITS = ["spades", "hearts", "diamonds", "clubs"]
def bj_deal(deck, n):
    return [deck.pop() for _ in range(n)]
def bj_play_dealer_deck(cards, deck, hit_soft_17=False):
    return bj_play_dealer(cards, deck.pop, hit_soft_17)
def bj_card_key(card):
    """Atlas key for a Terran card (rank, suit_index): card_ter_<suit>_<rank>."""
    rank, suit = card
    return "card_ter_%s_%s" % (_TER_SUITS[suit], rank)


# =========================================================================
# CHOGA  (house-banked stud; Arvonian 64-card; design + Monte-Carlo balanced)
# =========================================================================
# card = (value 0-15, castle 0-3).  "suit" for flush = castle.
CHOGA_CATS = ["high","pair","two_pair","trips","flush","straight",
              "full_house","quads","straight_flush"]  # index = strength

def choga_deck():
    return [(v, c) for c in range(4) for v in range(16)]

def choga_rank(cards):
    """Return a comparable tuple (category_index, *tiebreakers). Higher=better.
    NOTE deck quirk: straight (5) outranks flush (4)."""
    from collections import Counter
    vals = sorted((v for v, c in cards), reverse=True)
    suits = [c for v, c in cards]
    vc = Counter(v for v, c in cards)
    # sort values by (count, value) desc for tiebreak
    by_count = sorted(vc.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    counts = [n for v, n in by_count]
    tie = tuple(v for v, n in by_count)
    uniq = sorted(set(v for v, c in cards))
    is_flush = len(set(suits)) == 1
    is_straight = len(uniq) == 5 and (uniq[-1] - uniq[0] == 4)
    if is_straight and is_flush: cat = 8
    elif counts[0] == 4:         cat = 7
    elif counts[0] == 3 and counts[1] == 2: cat = 6
    elif is_straight:            cat = 5      # straight > flush in this deck
    elif is_flush:               cat = 4
    elif counts[0] == 3:         cat = 3
    elif counts[0] == 2 and counts[1] == 2:  cat = 2
    elif counts[0] == 2:         cat = 1
    else:                        cat = 0
    if is_straight:
        return (cat, uniq[-1])
    return (cat, tie)

def choga_checksum(cards):
    x = 0
    for v, c in cards:
        x ^= v
    return x == 0

# suggested pay ladders (x:1 on the raise), tuned toward ~3-5% house edge
CHOGA_RAISE_PAY = {1:1, 2:2, 3:3, 5:6, 4:5, 6:10, 7:50, 8:200}
CHOGA_CHECKSUM_PAY = 10   # side bet, ~1-in-16

def choga_dealer_qualifies(dealer_cards):
    return choga_rank(dealer_cards)[0] >= 1   # pair or better

def choga_settle(player_cards, dealer_cards, ante, raised):
    """Caribbean-Stud style. raised=True means player put up 2x ante and stays.
    Returns signed delta (excludes optional checksum side bet)."""
    if not raised:
        return -ante                          # folded
    pr = choga_rank(player_cards)
    dr = choga_rank(dealer_cards)
    raise_amt = ante * 2
    if not choga_dealer_qualifies(dealer_cards):
        return ante                           # ante pays 1:1, raise pushes
    if pr > dr:
        pay = CHOGA_RAISE_PAY.get(pr[0], 1)
        return ante + raise_amt * pay
    if pr < dr:
        return -(ante + raise_amt)
    return 0                                  # exact tie pushes

# --- MAST-friendly helpers --------------------------------------------------
CHOGA_NAMES = ["High card", "Pair", "Two pair", "Three of a kind", "Flush",
               "Straight", "Full house", "Four of a kind", "Straight flush"]
def choga_deal(deck, n):
    return [deck.pop() for _ in range(n)]
def choga_card_key(card):
    """Atlas key for a Choga card (value, castle): card_arv_<castle>_<value>."""
    value, castle = card
    return "card_arv_%d_%d" % (castle, value)
def choga_rank_name(cards):
    return CHOGA_NAMES[choga_rank(cards)[0]]
def choga_checksum_bonus(cards, ante):
    """Arvonian 'clean checksum' side bonus: if the 5 values XOR to 0 (~1-in-16),
    pay ante * CHOGA_CHECKSUM_PAY on top of the hand result. 0 otherwise."""
    return ante * CHOGA_CHECKSUM_PAY if choga_checksum(cards) else 0


# =========================================================================
# VIDEO POKER  (Jacks or Better; Terran 52-card deck - same as blackjack)
# =========================================================================
_POKER_VAL = {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,
              "J":11,"Q":12,"K":13,"A":14}

# 9/6 Jacks or Better, payout per 1 bet.
POKER_PAYTABLE = {"royal_flush":250, "straight_flush":50, "four_kind":25,
                  "full_house":9, "flush":6, "straight":4, "three_kind":3,
                  "two_pair":2, "jacks_or_better":1, "nothing":0}
POKER_NAMES = {"royal_flush":"Royal Flush","straight_flush":"Straight Flush",
               "four_kind":"Four of a Kind","full_house":"Full House",
               "flush":"Flush","straight":"Straight","three_kind":"Three of a Kind",
               "two_pair":"Two Pair","jacks_or_better":"Jacks or Better","nothing":"Nothing"}

def poker_hand_category(cards):
    """Category key for a 5-card Terran hand (Jacks or Better rules)."""
    from collections import Counter
    vals = sorted(_POKER_VAL[r] for r, s in cards)
    suits = [s for r, s in cards]
    vc = Counter(vals)
    counts = sorted(vc.values(), reverse=True)
    is_flush = len(set(suits)) == 1
    uniq = sorted(set(vals))
    is_straight = len(uniq) == 5 and (uniq[-1] - uniq[0] == 4)
    if set(vals) == {14, 2, 3, 4, 5}:          # wheel A-2-3-4-5
        is_straight = True
    is_royal = is_flush and set(vals) == {10, 11, 12, 13, 14}
    if is_royal:                       return "royal_flush"
    if is_straight and is_flush:       return "straight_flush"
    if counts[0] == 4:                 return "four_kind"
    if counts[0] == 3 and counts[1] == 2: return "full_house"
    if is_flush:                       return "flush"
    if is_straight:                    return "straight"
    if counts[0] == 3:                 return "three_kind"
    if counts[0] == 2 and counts[1] == 2: return "two_pair"
    if counts[0] == 2:
        pair_val = [v for v, c in vc.items() if c == 2][0]
        if pair_val >= 11:             return "jacks_or_better"  # J,Q,K,A
    return "nothing"

def video_poker_payout(cards, bet, paytable=None):
    pt = paytable or POKER_PAYTABLE
    return bet * pt.get(poker_hand_category(cards), 0)

def poker_hand_name(cards):
    return POKER_NAMES[poker_hand_category(cards)]

# card = (rank, suit_index) - Terran deck, same as blackjack.
def poker_card_key(card):
    return bj_card_key(card)

def poker_deal(deck, n):
    return [deck.pop() for _ in range(n)]

def poker_draw(deck, hand, held):
    """Replace non-held cards with fresh draws. held is a list of bools."""
    out = []
    for i, c in enumerate(hand):
        out.append(c if held[i] else deck.pop())
    return out

def poker_toggle_hold(held, i):
    """Flip hold state for card i (MAST-friendly - avoids in-script list-index
    assignment). Returns the same list."""
    held[i] = not held[i]
    return held


# =========================================================================
# PARITY  (original Arvonian chance game - a "register" you bet on)
# =========================================================================
# Three cards' values XOR into a 4-bit register (0-15). Bet on properties of
# it, roulette-style. Even/odd, high/low are exactly 50/50 and exact is 1/16
# paying 15:1 - a FAIR table by default (add a "house zero" later for an edge).
PARITY_PAYS = {"even": 1, "odd": 1, "high": 1, "low": 1, "exact": 15}
PARITY_LABELS = {"even": "Even", "odd": "Odd", "high": "High (>=8)",
                 "low": "Low (<8)", "exact": "Exact"}

def parity_roll(rng=None):
    """Deal 3 Arvonian cards; XOR their values into a register 0-15.
    Returns (cards, register)."""
    r = rng or _random
    deck = choga_deck()
    r.shuffle(deck)
    cards = [deck.pop() for _ in range(3)]
    reg = 0
    for v, c in cards:
        reg ^= v
    return cards, reg

def parity_wins(bet_type, bet_value, reg):
    if bet_type == "even":  return reg % 2 == 0
    if bet_type == "odd":   return reg % 2 == 1
    if bet_type == "high":  return reg >= 8
    if bet_type == "low":   return reg < 8
    if bet_type == "exact": return reg == bet_value
    return False

def parity_settle(bet, bet_type, bet_value, reg):
    if parity_wins(bet_type, bet_value, reg):
        return bet * PARITY_PAYS.get(bet_type, 0)
    return -bet

def parity_card_key(card):
    return choga_card_key(card)
