"""Auto-follow picks a ship, holds it, and lets go when it should.

These are decision tests: they feed a ranked candidate list straight in rather than
booting a sim, so they stay sub-second and cannot be defeated by a mission that happens
not to load an addon. What talks to the sim (`director_follow_candidates`) is one function
and is stubbed here; what DECIDES (`director_follow_pick`) is what breaks in front of an
audience.

Two of these guard bugs that would only ever appear on screen, never in a log:

  * `test_all_equal_does_not_flip` - `role("__player__")` is a SET, so with every ship
    equally exciting (a quiet moment, or headless where nothing populates `exciting` at
    all) "the best one" is whichever the set happened to yield first. Without a stable
    tie-break the program screen cuts between identical-looking ships on every poll.
  * `test_a_challenger_within_the_margin_is_ignored` - two ships trading a fractionally
    higher score would cut back and forth several times a minute, which reads as a fault
    rather than as direction.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_follow
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import director_follow as df

M = df.DIRECTOR_FOLLOW_MARGIN


class FollowPickTests(unittest.TestCase):
    def setUp(self):
        self._real = df.director_follow_candidates

    def tearDown(self):
        df.director_follow_candidates = self._real

    def _pick(self, ranked, current=None):
        df.director_follow_candidates = lambda: list(ranked)
        return df.director_follow_pick(current)

    def test_no_players_is_none_not_a_crash(self):
        # Between crews, and for the whole of a headless run.
        self.assertIsNone(self._pick([]))

    def test_no_players_forgets_what_it_was_following(self):
        self.assertIsNone(self._pick([], current=7))

    def test_first_pick_takes_the_best(self):
        self.assertEqual(self._pick([(0.9, 9), (0.1, 5)]), 9)

    def test_all_equal_does_not_flip(self):
        # The ORDER of the list is deliberately hostile here: the "other" ship is first.
        # A stable tie-break means the screen holds what it has.
        self.assertEqual(self._pick([(0.0, 9), (0.0, 5)], current=5), 5)

    def test_all_equal_first_pick_is_deterministic(self):
        # Same set, two different iteration orders, same answer - lowest id on a tie.
        self.assertEqual(self._pick([(0.0, 9), (0.0, 5)]), 5)
        self.assertEqual(self._pick([(0.0, 5), (0.0, 9)]), 5)

    def test_a_challenger_within_the_margin_is_ignored(self):
        self.assertEqual(self._pick([(0.5 + M * 0.5, 9), (0.5, 5)], current=5), 5)

    def test_a_challenger_beyond_the_margin_takes_the_shot(self):
        self.assertEqual(self._pick([(0.5 + M * 2, 9), (0.5, 5)], current=5), 9)

    def test_a_destroyed_subject_is_released(self):
        # THE ONE THAT WILL HAPPEN. Losing the ship is an ordinary ending, and holding a
        # dead subject is how a camera ends up on the engine's default top-down.
        self.assertEqual(self._pick([(0.0, 9)], current=5), 9)


if __name__ == "__main__":
    unittest.main()
