"""House-edge Monte-Carlo for each engine. Confirms the house profits by a
sane margin under simple player strategy. house_edge = -avg(player return)/bet.
"""
import random
from engines import *

def sim_blackjack(n, rng):
    net = 0
    for _ in range(n):
        deck = bj_deck(); rng.shuffle(deck)
        d = lambda: deck.pop()
        player = [d(), d()]; dealer = [d(), d()]
        # naive player: hit while < 17
        while bj_hand_value(player) < 17:
            player.append(d())
        dealer = bj_play_dealer(dealer, d)
        net += bj_settle(player, dealer, 1)
    return -net / n

def sim_nibble(n, rng, stand_at=16):
    net = 0
    for _ in range(n):
        deck = nibble_deck(16); rng.shuffle(deck)
        d = lambda: deck.pop()
        player = [d(), d()]; dealer = [d(), d()]
        # naive player: hit while total < stand_at and not bust
        while nibble_score(player)[0] < stand_at:
            player.append(d())
        busted = nibble_score(player)[0] > 20
        nat = nibble_is_natural(player)
        dealer = nibble_play_dealer(dealer, d, must=15,
                                    player_busted=busted, player_natural=nat)
        net += nibble_settle(player, dealer, 1)
    return -net / n

def sim_gates(n, rng, hit_rule=True):
    net = 0
    ops = [OP_OR, OP_AND, OP_NOR, OP_NAND, OP_XOR]
    for _ in range(n):
        bit = lambda: rng.randint(0, 7)
        op = lambda: rng.choice(ops)
        p = GatesHand(bits=[bit(), bit()], ops=[op()])
        b = GatesHand(bits=[bit(), bit()], ops=[op()])
        pt, bt = gates_score(p), gates_score(b)
        if hit_rule:
            p_third = None
            if pt <= 5 and bt not in (6, 7):
                p.bits.append(bit()); p.ops.append(op()); p_third = p.bits[-1]
                pt = gates_score(p)
            if gates_banker_draws(bt, p_third):
                b.bits.append(bit()); b.ops.append(op()); bt = gates_score(b)
        bet_on_player = rng.random() < 0.5
        net += gates_settle(1, bet_on_player, pt, bt)
    return -net / n

def sim_choga(n, rng, ante=1):
    net = 0
    for _ in range(n):
        deck = choga_deck(); rng.shuffle(deck)
        player = [deck.pop() for _ in range(5)]
        dealer = [deck.pop() for _ in range(5)]
        # strategy: raise with pair or better, else fold
        raised = choga_rank(player)[0] >= 1
        net += choga_settle(player, dealer, ante, raised)
    # edge relative to ante (total wagered varies; report vs ante for comparability)
    return -net / n

if __name__ == "__main__":
    rng = random.Random(2024)
    N = 500_000
    print(f"House edge (positive = house wins), N={N:,} per game, naive strategy")
    print(f"  blackjack : {sim_blackjack(N, rng)*100:+6.2f}%")
    print(f"  nibble    : {sim_nibble(N, rng)*100:+6.2f}%   (stand_at=16)")
    print(f"  gates     : {sim_gates(N, rng)*100:+6.2f}%   (hit rule on)")
    print(f"  choga     : {sim_choga(N, rng)*100:+6.2f}%   (raise on pair+, vs ante)")
