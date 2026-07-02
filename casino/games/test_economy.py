"""Tests for casino_economy: pure helpers + procedural wrappers (mock sbs).

Run from the LegendaryMissions folder with the sbs_utils lib on the path:
    PYTHONPATH=../sbs_utils python -m unittest casino.games.test_economy
(the casino folder needs an __init__.py-free path; we import by file location).
"""
import os, sys, unittest

# make the casino folder importable (casino_economy.py lives one level up)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cosmos_dev.mock import sbs as sbs
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.agent import Agent, get_story_id
from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.fs import test_set_exe_dir

import casino_economy as ce

test_set_exe_dir()


class TestPureHelpers(unittest.TestCase):
    def test_clamp_buy(self):
        self.assertEqual(ce.clamp_buy(0, 40, 100), 40)
        self.assertEqual(ce.clamp_buy(80, 40, 100), 20)     # only room for 20
        self.assertEqual(ce.clamp_buy(100, 10, 100), 0)     # at cap
        self.assertEqual(ce.clamp_buy(0, -5, 100), 0)       # negative
        self.assertEqual(ce.clamp_buy(0, 500, 100), 100)    # capped
    def test_chips_after_delta(self):
        self.assertEqual(ce.chips_after_delta(50, 20), 70)
        self.assertEqual(ce.chips_after_delta(50, -50), 0)
        self.assertEqual(ce.chips_after_delta(50, -80), 0)  # no debt


def make_side(key, credits):
    side = Agent(); side.id = get_story_id(); side.add()
    side.add_role("__side__")
    side.set_inventory_value("side_key", key)
    side.set_inventory_value("side_name", key.upper())
    side.set_inventory_value("credits", credits)
    return side

def make_ship(side_key):
    ship = Agent(); ship.id = get_story_id(); ship.add()
    ship.side = side_key
    return ship

def make_client():
    c = Agent(); c.id = get_story_id(); c.add()
    return c


class TestCage(unittest.TestCase):
    def setUp(self):
        SpaceObject.clear()
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        self.side = make_side("tsn", 1000)
        self.ship = make_ship("tsn")
        self.client = make_client()

    def credits(self):
        from sbs_utils.procedural.inventory import get_inventory_value
        return get_inventory_value(self.side.id, "credits", 0)

    def test_buy_deducts_credits_adds_chips(self):
        got = ce.casino_chips_buy(self.client.id, self.side.id, 40)
        self.assertEqual(got, 40)
        self.assertEqual(ce.casino_chips_get(self.client.id), 40)
        self.assertEqual(self.credits(), 960)

    def test_buy_respects_cap(self):
        ce.casino_chips_buy(self.client.id, self.side.id, 80)
        got = ce.casino_chips_buy(self.client.id, self.side.id, 40)  # only 20 room
        self.assertEqual(got, 20)
        self.assertEqual(ce.casino_chips_get(self.client.id), 100)

    def test_buy_limited_by_wallet(self):
        poor = make_side("poor", 25)
        got = ce.casino_chips_buy(self.client.id, poor.id, 100)  # wallet only 25
        self.assertEqual(got, 25)
        self.assertEqual(ce.casino_chips_get(self.client.id), 25)

    def test_buy_house_comp_no_wallet(self):
        # side_id None -> house stakes you so you never get locked out
        got = ce.casino_chips_buy(self.client.id, None, 30)
        self.assertEqual(got, 30)
        self.assertEqual(ce.casino_chips_get(self.client.id), 30)

    def test_cash_out_all(self):
        ce.casino_chips_buy(self.client.id, self.side.id, 60)
        paid = ce.casino_chips_cash_out(self.client.id, self.side.id)
        self.assertEqual(paid, 60)
        self.assertEqual(ce.casino_chips_get(self.client.id), 0)
        self.assertEqual(self.credits(), 1000)   # back to start

    def test_welcome_stake_once(self):
        got = ce.casino_ensure_stake(self.client.id, 50)
        self.assertEqual(got, 50)
        self.assertEqual(ce.casino_chips_get(self.client.id), 50)
        # second call is a no-op (already granted)
        self.assertEqual(ce.casino_ensure_stake(self.client.id, 50), 0)
        self.assertEqual(ce.casino_chips_get(self.client.id), 50)

    def test_side_of_client_fallback(self):
        # No ship assigned -> falls back to a stashed "side" key on the client.
        from sbs_utils.procedural.inventory import set_inventory_value
        set_inventory_value(self.client.id, "side", "tsn")
        self.assertEqual(ce.casino_side_of_client(self.client.id), self.side.id)

    def test_bet_apply_win_and_loss_and_net(self):
        ce.casino_chips_buy(self.client.id, self.side.id, 50)
        ce.casino_bet_apply(self.client.id, +30)
        self.assertEqual(ce.casino_chips_get(self.client.id), 80)
        ce.casino_bet_apply(self.client.id, -100)   # clamps at 0
        self.assertEqual(ce.casino_chips_get(self.client.id), 0)
        # net = +30 then -80 (only lost what was there) = -50
        self.assertEqual(ce.casino_net(self.client.id), -50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
