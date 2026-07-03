import os, sys, unittest

# engines.py lives alongside this file; ensure it's importable regardless of
# the discovery start dir / cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engines import (
    NibbleCard, nibble_score, nibble_is_natural, nibble_settle, nibble_deck,
    GatesHand, gates_apply, gates_score, gates_banker_draws, gates_settle,
    arv_opcode, gates_card_key,
    OP_AND, OP_OR, OP_NOR, OP_NAND, OP_XOR,
    bj_hand_value, bj_is_blackjack, bj_settle, bj_deck,
    choga_rank, choga_checksum, choga_settle, choga_deck,
)

class TestNibble(unittest.TestCase):
    def test_score_face_only(self):
        # type 0 -> no castle; total == face sum
        cards = [NibbleCard(3,0), NibbleCard(5,0)]
        self.assertEqual(nibble_score(cards), (8, 8))
    def test_castle_positional(self):
        # popcount(type)=1 each; multipliers 1,2 -> castle 3; num 0 -> total 3
        cards = [NibbleCard(0,1), NibbleCard(0,2)]
        self.assertEqual(nibble_score(cards)[0], 1*1 + 1*2)
    def test_castle_type3_popcount2(self):
        cards = [NibbleCard(0,3)]     # popcount 2 * multi 1
        self.assertEqual(nibble_score(cards)[0], 2)
    def test_natural_zero_and_14(self):
        self.assertTrue(nibble_is_natural([NibbleCard(0,0), NibbleCard(0,0)]))
        self.assertTrue(nibble_is_natural([NibbleCard(7,0), NibbleCard(7,0)]))  # 14
        self.assertFalse(nibble_is_natural([NibbleCard(3,0), NibbleCard(4,0)]))
    def test_settle_player_natural(self):
        p = [NibbleCard(7,0), NibbleCard(7,0)]     # natural
        d = [NibbleCard(5,0), NibbleCard(5,0)]
        self.assertEqual(nibble_settle(p, d, 10), 20)
    def test_settle_player_bust(self):
        p = [NibbleCard(15,0), NibbleCard(15,0)]   # 30 > 20
        d = [NibbleCard(5,0), NibbleCard(5,0)]
        self.assertEqual(nibble_settle(p, d, 10), -10)   # cost = bet (2 dealer cards)
    def test_settle_win_reward_scales(self):
        p = [NibbleCard(9,0), NibbleCard(9,0), NibbleCard(1,0)]  # 3 cards, total 19
        d = [NibbleCard(5,0), NibbleCard(5,0)]                   # 10
        self.assertEqual(nibble_settle(p, d, 10), 10 * 2**(3-2))  # 20
    def test_tie_dealer_wins(self):
        p = [NibbleCard(9,0), NibbleCard(9,0)]   # 18
        d = [NibbleCard(9,0), NibbleCard(9,0)]   # 18
        self.assertEqual(nibble_settle(p, d, 10), -10)          # default: dealer
        self.assertEqual(nibble_settle(p, d, 10, player_wins_ties=True), 10)  # softened
    def test_deck_size(self):
        self.assertEqual(len(nibble_deck(16)), 64)
        self.assertEqual(len(nibble_deck(8)), 32)
    def test_deal_and_dealer_deck(self):
        from engines import nibble_deal, nibble_play_dealer_deck, nibble_card_key
        deck = nibble_deck(16)
        n0 = len(deck)
        hand = nibble_deal(deck, 2)
        self.assertEqual(len(hand), 2)
        self.assertEqual(len(deck), n0 - 2)
        dealer = nibble_play_dealer_deck([NibbleCard(3,0)], deck, must=15)
        self.assertGreaterEqual(nibble_score(dealer)[0], 15)
        self.assertEqual(nibble_card_key(NibbleCard(5, 2)), "card_arv_2_5")

class TestGates(unittest.TestCase):
    def test_truth_examples(self):
        # from info page: 5 AND 7 = 5, 5 OR 7 = 7, 5 NAND 7 = 2, 5 NOR 7 = 0, 5 XOR 7 = 2
        self.assertEqual(gates_apply(OP_AND, 5, 7), 5)
        self.assertEqual(gates_apply(OP_OR, 5, 7), 7)
        self.assertEqual(gates_apply(OP_NAND, 5, 7), 2)
        self.assertEqual(gates_apply(OP_NOR, 5, 7), 0)
        self.assertEqual(gates_apply(OP_XOR, 5, 7), 2)
    def test_arv_opcode_from_art(self):
        # op = (value + castle) % 4 over [OR, AND, NOR, NAND], no XOR.
        # Verified against arvonian_deck.png across all four castle rows.
        expected = {
            0: [OP_OR, OP_AND, OP_NOR, OP_NAND],    # castle 0 (red)
            1: [OP_AND, OP_NOR, OP_NAND, OP_OR],    # castle 1 (purple)
            2: [OP_NOR, OP_NAND, OP_OR, OP_AND],    # castle 2 (blue)
            3: [OP_NAND, OP_OR, OP_AND, OP_NOR],    # castle 3 (green)
        }
        for castle, gates in expected.items():
            for value in range(8):
                self.assertEqual(arv_opcode(value, castle), gates[value % 4])
        # the mapping never produces XOR
        for castle in range(4):
            for value in range(16):
                self.assertIn(arv_opcode(value, castle),
                              (OP_OR, OP_AND, OP_NOR, OP_NAND))

    def test_score_fold(self):
        # Operators are now the cards' own corner opcodes (arv_opcode).
        # (5,0)->op OR unused (first card); (7,2)->op AND: 5 AND 7 = 5
        h = GatesHand(cards=[(5, 0), (7, 2)])
        self.assertEqual(h.ops, [OP_AND])
        self.assertEqual(gates_score(h), 5)
        # add (3,1)->op OR: (5 AND 7) OR 3 = 5 | 3 = 7
        h2 = GatesHand(cards=[(5, 0), (7, 2), (3, 1)])
        self.assertEqual(h2.ops, [OP_AND, OP_OR])
        self.assertEqual(gates_score(h2), 7)
    def test_banker_tableau(self):
        self.assertTrue(gates_banker_draws(0, 4))
        self.assertTrue(gates_banker_draws(2, 5))
        self.assertFalse(gates_banker_draws(2, 6))
        self.assertTrue(gates_banker_draws(3, 2))
        self.assertFalse(gates_banker_draws(3, 6))
        self.assertTrue(gates_banker_draws(4, 5))
        self.assertFalse(gates_banker_draws(4, 3))
        self.assertFalse(gates_banker_draws(5, 4))
    def test_settle_banker_ties(self):
        # equal totals -> banker wins; bet on player loses, bet on banker wins
        self.assertEqual(gates_settle(10, True, 5, 5), -10)
        self.assertEqual(gates_settle(10, False, 5, 5), 10)
        self.assertEqual(gates_settle(10, True, 6, 4), 10)
    def test_play_round_and_helpers(self):
        import random
        from engines import gates_play_round, gates_op_name, gates_bit_key, gates_ops_str
        r = random.Random(3)
        p, b, pt, bt = gates_play_round(True, r)
        self.assertTrue(0 <= pt <= 7 and 0 <= bt <= 7)
        self.assertGreaterEqual(len(p.cards), 2)
        # dealt cards carry only the four deck gates - never XOR
        for hand in (p, b):
            for op in hand.ops:
                self.assertIn(op, (OP_OR, OP_AND, OP_NOR, OP_NAND))
        self.assertEqual(gates_op_name(OP_XOR), "XOR")
        self.assertEqual(gates_bit_key(5), "card_arv_0_5")
        self.assertEqual(gates_card_key((5, 2)), "card_arv_2_5")
        self.assertIsInstance(gates_ops_str(p), str)

class TestBlackjack(unittest.TestCase):
    def test_values_and_soft_ace(self):
        self.assertEqual(bj_hand_value([("A",0),("9",0)]), 20)      # soft 20
        self.assertEqual(bj_hand_value([("A",0),("9",0),("5",0)]), 15)  # ace hard
        self.assertEqual(bj_hand_value([("K",0),("Q",0)]), 20)
    def test_blackjack(self):
        self.assertTrue(bj_is_blackjack([("A",0),("K",0)]))
        self.assertFalse(bj_is_blackjack([("A",0),("5",0),("5",0)]))
    def test_settle(self):
        self.assertEqual(bj_settle([("A",0),("K",0)], [("10",0),("9",0)], 10), 15)  # bj 3:2
        self.assertEqual(bj_settle([("10",0),("9",0)], [("10",0),("8",0)], 10), 10)
        self.assertEqual(bj_settle([("10",0),("5",0),("K",0)], [("10",0),("9",0)], 10), -10)  # bust
        self.assertEqual(bj_settle([("10",0),("9",0)], [("10",0),("9",0)], 10), 0)   # push
    def test_deck(self):
        self.assertEqual(len(bj_deck()), 52)
    def test_deck_drivers_and_key(self):
        from engines import bj_deal, bj_play_dealer_deck, bj_card_key
        deck = bj_deck(); n0 = len(deck)
        hand = bj_deal(deck, 2)
        self.assertEqual(len(hand), 2)
        self.assertEqual(len(deck), n0 - 2)
        dealer = bj_play_dealer_deck([("6",0),("9",1)], deck)  # 15 -> must draw
        self.assertGreaterEqual(bj_hand_value(dealer), 17)
        self.assertEqual(bj_card_key(("K", 2)), "card_ter_diamonds_K")

class TestChoga(unittest.TestCase):
    def test_ranks(self):
        pair = [(3,0),(3,1),(7,0),(9,0),(1,0)]
        two_pair = [(3,0),(3,1),(7,0),(7,1),(1,0)]
        trips = [(3,0),(3,1),(3,2),(7,0),(1,0)]
        flush = [(1,2),(4,2),(7,2),(9,2),(11,2)]
        straight = [(4,0),(5,1),(6,2),(7,3),(8,0)]
        full = [(3,0),(3,1),(3,2),(7,0),(7,1)]
        quads = [(3,0),(3,1),(3,2),(3,3),(7,0)]
        sflush = [(4,2),(5,2),(6,2),(7,2),(8,2)]
        r = choga_rank
        self.assertTrue(r(pair) < r(two_pair) < r(trips))
        self.assertTrue(r(trips) < r(flush) < r(straight))   # straight > flush (deck quirk)
        self.assertTrue(r(straight) < r(full) < r(quads) < r(sflush))
    def test_checksum(self):
        self.assertTrue(choga_checksum([(3,0),(3,1),(5,0),(5,1),(0,0)]))  # 3^3^5^5^0=0
        self.assertFalse(choga_checksum([(1,0),(2,0),(3,0),(4,0),(5,0)]))
    def test_checksum_bonus(self):
        from engines import choga_checksum_bonus, CHOGA_CHECKSUM_PAY
        clean = [(3,0),(3,1),(5,0),(5,1),(0,0)]      # XOR 0
        dirty = [(1,0),(2,0),(3,0),(4,0),(5,0)]      # XOR != 0
        self.assertEqual(choga_checksum_bonus(clean, 10), 10 * CHOGA_CHECKSUM_PAY)
        self.assertEqual(choga_checksum_bonus(dirty, 10), 0)
    def test_settle_fold_and_qualify(self):
        strong = [(9,0),(9,1),(9,2),(2,0),(3,0)]   # trips
        weak_nonqual = [(1,0),(4,1),(7,2),(9,0),(11,0)]  # high card -> dealer no qualify
        self.assertEqual(choga_settle(strong, weak_nonqual, 10, False), -10)  # folded
        # dealer doesn't qualify -> ante pays 1:1
        self.assertEqual(choga_settle(strong, weak_nonqual, 10, True), 10)
    def test_deck(self):
        self.assertEqual(len(choga_deck()), 64)
    def test_helpers(self):
        from engines import choga_deal, choga_card_key, choga_rank_name
        deck = choga_deck(); n0 = len(deck)
        hand = choga_deal(deck, 5)
        self.assertEqual(len(hand), 5)
        self.assertEqual(len(deck), n0 - 5)
        self.assertEqual(choga_card_key((5, 2)), "card_arv_2_5")
        self.assertEqual(choga_rank_name([(3,0),(3,1),(7,0),(9,0),(1,0)]), "Pair")

class TestVideoPoker(unittest.TestCase):
    def test_categories(self):
        from engines import poker_hand_category
        self.assertEqual(poker_hand_category([("10",0),("J",0),("Q",0),("K",0),("A",0)]), "royal_flush")
        self.assertEqual(poker_hand_category([("2",1),("3",1),("4",1),("5",1),("6",1)]), "straight_flush")
        self.assertEqual(poker_hand_category([("J",0),("J",1),("J",2),("J",3),("3",0)]), "four_kind")
        self.assertEqual(poker_hand_category([("J",0),("J",1),("J",2),("3",0),("3",1)]), "full_house")
        self.assertEqual(poker_hand_category([("2",1),("5",1),("7",1),("9",1),("J",1)]), "flush")
        self.assertEqual(poker_hand_category([("A",0),("2",1),("3",2),("4",3),("5",0)]), "straight")  # wheel
        self.assertEqual(poker_hand_category([("J",0),("J",1),("3",0),("7",0),("9",0)]), "jacks_or_better")
        self.assertEqual(poker_hand_category([("4",0),("4",1),("3",0),("7",0),("9",0)]), "nothing")  # low pair
    def test_payout(self):
        from engines import video_poker_payout
        self.assertEqual(video_poker_payout([("10",0),("J",0),("Q",0),("K",0),("A",0)], 5), 1250)
        self.assertEqual(video_poker_payout([("J",0),("J",1),("3",0),("7",0),("9",0)], 5), 5)   # jacks 1x
        self.assertEqual(video_poker_payout([("4",0),("4",1),("3",0),("7",0),("9",0)], 5), 0)   # nothing
    def test_draw_holds(self):
        from engines import bj_deck, poker_deal, poker_draw, poker_card_key
        deck = bj_deck(); hand = poker_deal(deck, 5); n = len(deck)
        new = poker_draw(deck, hand, [True, False, True, False, False])
        self.assertEqual(new[0], hand[0]); self.assertEqual(new[2], hand[2])
        self.assertEqual(len(deck), n - 3)
        self.assertEqual(poker_card_key(("K", 2)), "card_ter_diamonds_K")


class TestParity(unittest.TestCase):
    def test_roll(self):
        from engines import parity_roll
        import random
        cards, reg = parity_roll(random.Random(4))
        self.assertEqual(len(cards), 3)
        self.assertTrue(0 <= reg <= 15)
        # register is the XOR of the three values
        x = 0
        for v, c in cards:
            x ^= v
        self.assertEqual(reg, x)
    def test_wins_and_settle(self):
        from engines import parity_wins, parity_settle
        self.assertTrue(parity_wins("even", 0, 6))
        self.assertFalse(parity_wins("even", 0, 7))
        self.assertTrue(parity_wins("odd", 0, 7))
        self.assertTrue(parity_wins("high", 0, 12))
        self.assertTrue(parity_wins("low", 0, 3))
        self.assertTrue(parity_wins("exact", 9, 9))
        self.assertFalse(parity_wins("exact", 9, 8))
        self.assertEqual(parity_settle(10, "even", 0, 6), 10)
        self.assertEqual(parity_settle(10, "even", 0, 7), -10)
        self.assertEqual(parity_settle(10, "exact", 9, 9), 150)   # 15:1


class TestKoraTa(unittest.TestCase):
    def test_deck_and_keys(self):
        from engines import korata_deck, korata_card_key, korata_op_of_card
        self.assertEqual(len(korata_deck(3)), 32)   # values 0-7 x 4 castles
        self.assertEqual(len(korata_deck(4)), 64)   # full Arvonian deck
        self.assertEqual(korata_card_key((5, 2)), "card_arv_2_5")
        self.assertEqual(korata_op_of_card((0, 0)), OP_OR)    # (0+0)%4
        self.assertEqual(korata_op_of_card((0, 2)), OP_NOR)   # (0+2)%4

    def test_run_score_fold_and_width(self):
        from engines import korata_run_score
        # 3-bit: (5 AND 7) OR 3 = 5 | 3 = 7
        self.assertEqual(korata_run_score([5, 7, 3], [OP_AND, OP_OR], 7), 7)
        # NAND width matters: ~(5&7) masked
        self.assertEqual(korata_run_score([5, 7], [OP_NAND], 7), 2)    # ~5 & 7
        self.assertEqual(korata_run_score([5, 7], [OP_NAND], 15), 10)  # ~5 & 15
        # 4-bit example: ~(9 & 14) & 15 = ~8 & 15 = 7
        self.assertEqual(korata_run_score([9, 14], [OP_NAND], 15), 7)
        # partial runs mid-hand
        self.assertEqual(korata_run_score([5], [], 7), 5)
        self.assertEqual(korata_run_score([5], [OP_AND], 7), 5)   # trailing op ignored
        self.assertEqual(korata_run_score([], [], 7), 0)

    def test_apply(self):
        from engines import korata_apply
        self.assertEqual(korata_apply(OP_OR, 5, 7, 7), 7)
        self.assertEqual(korata_apply(OP_NOR, 5, 7, 7), 0)
        self.assertEqual(korata_apply(OP_NAND, 5, 7, 15), 10)

    def test_ai_pick_value_uses_fold(self):
        from engines import korata_ai_pick_value
        # empty run -> just the largest value
        self.assertEqual(korata_ai_pick_value([(2,0),(6,0),(4,0)], [], [], 7), 1)
        # with a pending AND gate, the card that folds highest wins (7 AND 7 = 7)
        self.assertEqual(
            korata_ai_pick_value([(1,0),(7,0)], [7], [OP_AND], 7), 1)

    def test_ai_pick_opcode_minimizes_you(self):
        from engines import korata_ai_pick_opcode, korata_op_of_card
        # your_score 7: NOR drives every next fold to 0, the strongest sabotage.
        hand = [(0,0), (0,2), (1,0)]        # ops: OR, NOR, AND
        self.assertEqual(korata_op_of_card((0,2)), OP_NOR)
        self.assertEqual(korata_ai_pick_opcode(hand, 7, 7), 1)

    def test_ai_bet(self):
        from engines import korata_ai_bet, KORATA_RAISE
        self.assertEqual(korata_ai_bet(7, 2, 10, 20, 7), ("raise", 10 + KORATA_RAISE))
        self.assertEqual(korata_ai_bet(2, 7, 10, 20, 7), ("fold", 0))
        self.assertEqual(korata_ai_bet(4, 4, 10, 20, 7), ("call", 10))
        self.assertEqual(korata_ai_bet(7, 2, 0, 20, 7), ("raise", KORATA_RAISE))

    def test_showdown_and_pot_settle(self):
        from engines import korata_showdown, korata_pot_settle
        self.assertEqual(korata_showdown(5, 3), "player")
        self.assertEqual(korata_showdown(3, 5), "ai")
        self.assertEqual(korata_showdown(4, 4), "tie")
        self.assertEqual(korata_pot_settle(20, 40, "player"), 40)   # take AI's stake
        self.assertEqual(korata_pot_settle(20, 40, "ai"), -20)      # lose own stake
        self.assertEqual(korata_pot_settle(30, 30, "tie"), 0)

    def test_card_list_helpers(self):
        from engines import (korata_cards_score, korata_cards_run_str,
                             korata_ai_value_index)
        cards = [(5, 0), (7, 2), (3, 1)]     # values 5,7,3
        self.assertEqual(korata_cards_score(cards, [OP_AND, OP_OR], 7), 7)
        self.assertEqual(korata_cards_run_str(cards, [OP_AND, OP_OR]),
                         "5 AND 7 OR 3")
        # picks the card that folds highest onto an empty run (largest value)
        self.assertEqual(
            korata_ai_value_index([(2,0),(6,0),(4,0)], [], [], 7), 1)

    def test_greedy_beats_random(self):
        import random
        from engines import korata_simulate_hand, korata_showdown
        rng = random.Random(1234)
        p_wins = a_wins = ties = 0
        for _ in range(400):
            ps, as_ = korata_simulate_hand(rng, 4, "greedy", "random")
            self.assertTrue(0 <= ps <= 15 and 0 <= as_ <= 15)
            w = korata_showdown(ps, as_)
            if w == "player": p_wins += 1
            elif w == "ai":   a_wins += 1
            else:             ties += 1
        # the greedy seat (player) should clearly beat the random seat (ai)
        self.assertGreater(p_wins, a_wins)


if __name__ == "__main__":
    unittest.main(verbosity=2)
