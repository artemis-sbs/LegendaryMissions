import unittest
from engines import (
    NibbleCard, nibble_score, nibble_is_natural, nibble_settle, nibble_deck,
    GatesHand, gates_apply, gates_score, gates_banker_draws, gates_settle,
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
        self.assertEqual(nibble_settle(p, d, 10), -10)
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
    def test_score_fold(self):
        h = GatesHand(bits=[5, 7], ops=[OP_AND])
        self.assertEqual(gates_score(h), 5)
        h2 = GatesHand(bits=[5, 7, 3], ops=[OP_AND, OP_OR])  # (5&7)|3 = 5|3 = 7
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
        self.assertGreaterEqual(len(p.bits), 2)
        self.assertEqual(gates_op_name(OP_XOR), "XOR")
        self.assertEqual(gates_bit_key(5), "card_arv_0_5")
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

if __name__ == "__main__":
    unittest.main(verbosity=2)
