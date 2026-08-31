"""LM's answers to "what does this weigh" and "how hard does this ship pull".

The library ships the mechanism and refuses to guess the numbers, so everything the mass
rules do in LM comes out of this module. Two of these tests pin live bugs rather than new
behavior: a pickup weighed as much as a corvette, which cost a cruiser a third of its
throttle for collecting a canister and made a FIGHTER's reel run backwards.
"""
from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import os
import sys
import unittest

import cosmos_dev.mock.sbs as mock_sbs

sys.modules.setdefault("sbs", mock_sbs)

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.procedural import grav_tether as gt
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.items import item_spawn
from sbs_utils.procedural.query import to_id
from sbs_utils.procedural.roles import add_role
from sbs_utils.procedural.spawn import npc_spawn, player_spawn
from sbs_utils.procedural.timers import set_timer
from sbs_utils.spaceobject import SpaceObject

import tether_mass
import tether_salvage

MASS_YAML = os.path.join(HERE, "tether_mass.yaml")

#: Where LM declares its collectibles. Scanned as text - see the collision test.
ITEM_DEF_FILES = ("items/item_defs.mast", "items/trade_goods.mast",
                  "fabrication/salvage.mast", "turrets/turret_deploy.mast")


def _declared_items():
    """Every `type: item/...` metadata block, from SOURCE, as {key: {field: value}}.

    Read out of the .mast text rather than through the label registry on purpose: nothing
    compiles `item/` labels in this process, so `item_keys()` answers `[]` and every
    registry-based assertion below would pass against any name anyone could choose.
    """
    import re
    root = os.path.dirname(HERE)
    items = {}
    for rel in ITEM_DEF_FILES:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for block in re.split(r"^metadata:", text, flags=re.M)[1:]:
            head = block.split("```", 2)[1] if "```" in block else ""
            if "type: item/" not in head:
                continue
            fields = dict(re.findall(r"^(\w+):\s*(\S.*?)\s*$", head, flags=re.M))
            if fields.get("key"):
                items[fields["key"]] = fields
    return items


def _declared_item_keys():
    """Every `key:` declared in a `type: item/...` metadata block, from source."""
    return set(_declared_items())


class _SourceLabel:
    """An `item/` metadata block, shaped like the label object the library reads."""

    def __init__(self, fields):
        self._f = fields

    def get_inventory_value(self, key, defa=None):
        return self._f.get(key, defa)


def _scatter_pool():
    """The keys `terrain_spawn_pickups` would actually scatter, from the REAL library.

    Calls sbs_utils' own `_item_spawn_pool` with the declared items standing in for the
    label registry, rather than re-implementing its rule here. A local copy of the filter
    is the trap this whole test class exists to catch: it would keep answering the way the
    author expected long after the library stopped agreeing with it.
    """
    import sbs_utils.procedural.items as CORE
    labels = [_SourceLabel(f) for f in _declared_items().values()]
    real, CORE.labels_get_type = CORE.labels_get_type, lambda prefix: list(labels)
    try:
        keys, _weights = CORE._item_spawn_pool(["upgrade", "resource"])
    finally:
        CORE.labels_get_type = real
    return set(keys)


#: Sim ticks per second - the clock is_timer_finished reads.
TICKS_PER_SECOND = 30


def _advance_sim(seconds):
    """Move sim time forward without sleeping. `time_tick_counter` is a read-only
    property; `_time_tick_counter` is the writable field behind it."""
    mock_sbs.sim._time_tick_counter += int(seconds * TICKS_PER_SECOND)


def _install_masses():
    """Load the table and install the providers, WITHOUT media_read_relative_file.

    `lm_tether_load_masses` reads the yaml relative to the running .mast, and there is no
    .mast here - it would silently install an EMPTY table and every assertion below would
    read the unlisted-hull default instead. Same file, plain IO, so what is under test is
    the rules rather than media resolution.
    """
    from sbs_utils.fs import load_yaml_string
    with open(MASS_YAML, encoding="utf-8") as handle:
        data = load_yaml_string(handle.read()) or {}
    tether_mass._LM_MASSES = {str(k): float(v)
                              for k, v in (data.get("masses") or {}).items()}
    gt.grav_tether_set_mass_fn(tether_mass.lm_tether_mass)
    gt.grav_tether_set_pull_bonus_fn(tether_mass.lm_tether_pull_bonus)


class TestTetherMass(unittest.TestCase):
    def setUp(self):
        SpaceObject.clear()
        gt.grav_tether_clear_all()
        mock_sbs.create_new_sim()
        mock_sbs.resume_sim()
        FrameContext.context = Context(mock_sbs.sim, mock_sbs, FakeEvent(0, "test"))
        _install_masses()

    def tearDown(self):
        gt.grav_tether_clear_all()
        gt.grav_tether_set_mass_fn(None)
        gt.grav_tether_set_pull_bonus_fn(None)

    # --- the table -----------------------------------------------------------

    def test_the_table_loaded_at_all(self):
        self.assertGreater(tether_mass.lm_tether_mass_count(), 50)

    def test_a_hull_weighs_what_the_table_says(self):
        base = npc_spawn(0, 0, 0, "Base", "tsn", "starbase_command", "behav_station")
        self.assertEqual(tether_mass.lm_tether_mass(base), 200.0)

    def test_the_turret_crate_is_light_enough_to_reposition(self):
        """It exists to be towed into position, and it was falling to the corvette
        default - heavy enough that a light cruiser's beam flipped and dragged the
        CRUISER to the crate."""
        crate = npc_spawn(0, 0, 0, "Crate", "tsn", "lm_turret_crate", "behav_station")
        tug = player_spawn(500, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        self.assertEqual(tether_mass.lm_tether_mass(crate), 2.0)
        self.assertLess(gt.grav_tether_mass_ratio(tug, crate), gt.MASS_REVERSE_RATIO)

    # --- pickups -------------------------------------------------------------

    def test_a_pickup_weighs_almost_nothing(self):
        pod = item_spawn("salvage", 0, 0, 0)
        self.assertEqual(tether_mass.lm_tether_mass(pod), tether_mass.LM_TETHER_PICKUP_MASS)

    def test_a_fighter_can_reel_a_pickup_the_right_way_round(self):
        """THE BUG. A tsn_fighter is mass 1 and a pickup used to default to 3, which is
        over MASS_REVERSE_RATIO - so grav_tether_attach built the connection backwards and
        reeled the FIGHTER onto the canister, capped to impulse the whole way."""
        pod = item_spawn("salvage", 800, 0, 0)
        fighter = player_spawn(0, 0, 0, "Scout", "tsn", "tsn_fighter")
        gt.grav_tether_reel(fighter, pod)
        self.assertFalse(gt._TETHERS[(to_id(fighter), to_id(pod))]["reversed"])
        self.assertIsNotNone(
            mock_sbs.sim.GetTractorConnection(to_id(fighter), to_id(pod)))

    def test_reeling_a_canister_no_longer_brakes_the_ship(self):
        pod = item_spawn("salvage", 800, 0, 0)
        cruiser = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        self.assertLess(gt._drag_amount(gt.grav_tether_mass_ratio(cruiser, pod)), 0.05)

    def test_the_rule_is_keyed_on_the_stamp_not_on_a_role(self):
        """`item_spawn` puts the item KEY into the role string as well, so an item
        someone names "hulk" would answer a role test meant for salvage. `item_key` is
        stamped by item_spawn and by nothing else."""
        pod = item_spawn("salvage", 0, 0, 0)
        self.assertIsNotNone(get_inventory_value(to_id(pod), "item_key", None))

    # --- and it cannot reach the salvage payout -------------------------------

    def test_a_hulk_still_weighs_and_pays_what_it_did(self):
        hulk = npc_spawn(0, 0, 0, "Wreck", "tsn", "cargo_ship", "behav_npcship")
        add_role(hulk, "hulk")
        self.assertEqual(tether_mass.lm_tether_mass(hulk), 12.0)
        self.assertEqual(tether_salvage.lm_tether_salvage_value(hulk),
                         max(1, int(12.0 * tether_salvage.LM_SALVAGE_PER_MASS + 0.5)))

    def test_no_item_key_collides_with_a_salvage_role(self):
        """Silent when it breaks: `item_spawn` puts the item KEY into the pickup's role
        string, so an item named `wreck` would make every one of them deliverable at a
        station for salvage.

        Read out of the .mast SOURCE, not from `item_keys()`. That accessor walks the
        compiled `item/` labels, and nothing compiles them here - it answers `[]`, which
        would make this assertion pass against every name anyone could ever choose.
        """
        salvage_roles = set(tether_salvage.LM_SALVAGE_ROLES.split(","))
        keys = _declared_item_keys()
        self.assertGreater(len(keys), 10, "found no item keys - the scan is broken")
        self.assertEqual(keys & salvage_roles, set())

    # --- the Heavy rig: bought, permanent ------------------------------------

    def _fit_heavy(self, tug):
        set_inventory_value(to_id(tug), "grav_tug_rig_fitted", 1)

    def _fit_mk1(self, tug, seconds=600):
        set_timer(to_id(tug), "tug_rig_mk1", seconds=seconds)

    def test_the_rig_multiplies_what_you_pull_with(self):
        tug = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        self.assertEqual(tether_mass.lm_tether_pull_bonus(tug), 1.0)
        self._fit_heavy(tug)
        self.assertEqual(tether_mass.lm_tether_pull_bonus(tug),
                         tether_mass.LM_TETHER_TUG_BONUS)

    def test_carrying_the_crate_is_not_wearing_the_rig(self):
        """THE BUG the separate flag name exists for. `market_buy` credits a purchase as
        set_inventory_value(ship, "grav_tug_rig", n), so a fitted-flag sharing the item
        key would be raised by CARRYING the crate: the rig would work before anyone
        activated it, and selling the crate would rip it back out of a fitted hull."""
        tug = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        set_inventory_value(to_id(tug), "grav_tug_rig", 1)      # bought, not yet fitted
        self.assertEqual(tether_mass.lm_tether_pull_bonus(tug), 1.0)

    def test_the_rig_does_not_change_what_the_ship_weighs(self):
        """Why it is its own hook and not a line in the mass table. Mass also decides
        whether a Grav Lock reverses onto you and what your own wreck pays as salvage -
        better towing gear must not quietly raise the price of your hulk."""
        tug = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        before = tether_mass.lm_tether_mass(tug)
        self._fit_heavy(tug)
        self.assertEqual(tether_mass.lm_tether_mass(tug), before)
        self.assertEqual(tether_salvage.lm_tether_salvage_value(tug),
                         max(1, int(before * tether_salvage.LM_SALVAGE_PER_MASS + 0.5)))

    def test_a_rigged_tug_hauls_like_four_ships(self):
        base = npc_spawn(3000, 0, 0, "Base", "tsn", "starbase_command", "behav_station")
        tug = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        gt.grav_tether_tow(tug, base, 500)
        plain = gt.grav_tether_pull_mass(base)
        self._fit_heavy(tug)
        self.assertEqual(gt.grav_tether_pull_mass(base),
                         plain * tether_mass.LM_TETHER_TUG_BONUS)

    # --- the Mk I: found, weaker, expiring -----------------------------------

    def test_the_mk1_is_weaker_than_the_rig(self):
        tug = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        self._fit_mk1(tug)
        self.assertEqual(tether_mass.lm_tether_pull_bonus(tug),
                         tether_mass.LM_TETHER_TUG_MK1_BONUS)
        self.assertLess(tether_mass.LM_TETHER_TUG_MK1_BONUS,
                        tether_mass.LM_TETHER_TUG_BONUS)

    def test_the_mk1_burns_out(self):
        tug = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        self._fit_mk1(tug, seconds=600)
        self.assertGreater(tether_mass.lm_tether_pull_bonus(tug), 1.0)
        _advance_sim(601)
        self.assertEqual(tether_mass.lm_tether_pull_bonus(tug), 1.0)

    def test_a_ship_that_never_fitted_one_reads_no_bonus(self):
        """The whole design rests on is_timer_finished answering True for a timer that
        was never set, so the guard fails CLOSED. Pin it rather than trust it."""
        tug = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        self.assertEqual(tether_mass.lm_tether_pull_bonus(tug), 1.0)

    def test_the_two_rigs_stack(self):
        """Not generosity - a fix. item_activate decrements a consumable BEFORE running
        the effect, so under best-one-wins a crew that owns the permanent rig destroys
        any Mk I they activate for nothing, and neither the GUI nor the server route can
        refuse the press. Every scattered Mk I would be trash for exactly the crews most
        likely to want a tug."""
        tug = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        self._fit_heavy(tug)
        self._fit_mk1(tug)
        self.assertEqual(tether_mass.lm_tether_pull_bonus(tug),
                         tether_mass.LM_TETHER_TUG_BONUS
                         + tether_mass.LM_TETHER_TUG_MK1_BONUS - 1.0)

    def test_the_mk1_lifts_a_liner_off_the_drag_floor(self):
        """Why the Mk I is 2.5 and not the obvious 2.0. Tow drag saturates at ratio 2.14,
        so on the standard haul - a mass-3 cruiser dragging a mass-16 liner - a 2x rig
        moves the drag penalty not at all, and the crew pays for an item that changes
        nothing they can feel."""
        liner = npc_spawn(3000, 0, 0, "Liner", "tsn", "luxury_liner", "behav_npcship")
        tug = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        gt.grav_tether_tow(tug, liner, 500)
        floor_ratio = (1.0 - gt.DRAG_FLOOR) / gt.DRAG_AT_EQUAL_MASS
        self.assertGreater(gt.grav_tether_load_ratio(tug, liner), floor_ratio)
        self._fit_mk1(tug)
        self.assertLess(gt.grav_tether_load_ratio(tug, liner), floor_ratio)

    def test_the_bonus_never_raises_without_a_sim(self):
        """Called from the tether tick for every puller, so a raise here takes the whole
        tick down. It must go through the LIBRARY wrapper - that is what catches."""
        tug = player_spawn(0, 0, 0, "Tug", "tsn", "tsn_light_cruiser")
        tid = to_id(tug)
        self._fit_mk1(tug)
        saved, FrameContext.context = FrameContext.context, None
        try:
            self.assertEqual(gt.grav_tether_pull_bonus(tid), 1.0)
        finally:
            FrameContext.context = saved

    # --- which of the two is loot, and which is stock ------------------------

    def test_the_permanent_rig_is_bought_and_never_found(self):
        """THE original mistake, pinned. `type: item/upgrade/...` is what the random
        scatter samples, so this shipped a permanent 4x hauling multiplier into the loot
        table of every map that calls terrain_spawn_pickups."""
        rig = _declared_items()["grav_tug_rig"]
        self.assertNotIn("grav_tug_rig", _scatter_pool(),
                         "a permanent fitting must not be loot")
        self.assertEqual(rig.get("mode"), "install")
        self.assertGreater(int(rig.get("price", 0)), 0, "it has to be buyable instead")

    def test_the_mk1_is_found_and_never_sold(self):
        mk1 = _declared_items()["tug_rig_mk1"]
        self.assertIn("tug_rig_mk1", _scatter_pool(), "the aged one is the pickup")
        self.assertEqual(mk1.get("mode"), "consumable")
        self.assertNotIn("price", mk1, "found, not bought - the mirror of the Heavy rig")
        self.assertGreater(int(mk1.get("duration", 0)), 0, "it has to expire")

    def test_the_rig_stays_in_the_debug_console_skip_set(self):
        """consoles/debug.py builds its Test Items skip set from
        items_of_category("upgrade") and drops everything ELSE as a floating pickup. So
        retyping the rig to dodge the scatter would have the debug console spawning it -
        in the one place you stand while testing that it does not spawn."""
        rig = _declared_items()["grav_tug_rig"]
        self.assertIn("upgrade", (rig.get("type") or "").split("/"))


if __name__ == "__main__":
    unittest.main()
