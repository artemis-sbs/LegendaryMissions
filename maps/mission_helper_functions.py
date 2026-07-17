
import copy
import sbs
from sbs_utils.procedural.query import to_object_list
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.comms import comms_message
from sbs_utils.procedural.amd_doc import amd_fill


#**************************************************************************
def send_general_message(nName, textLine, face, srcID):

    sbs.send_story_dialog(0, nName, textLine, face, "#444")

    main_screen_client_list = to_object_list(role("mainscreen") & role("console"))

#    print(f"main screen client count = {len(main_screen_client_list)}")
    for c in main_screen_client_list:
        print(c.client_id)
        sbs.send_story_dialog(c.client_id, nName, textLine, face, "#444")

    # send it to all comms players as well
    my_players = to_object_list(role("__player__"))
    for player in my_players:
        comms_message(textLine, srcID, player.id, face=face, from_name=nName)
#        COMMS_ORIGIN_ID=player.id
#        COMMS_SELECTED_ID=phoenix_id
#        << "{nName}"     
#            "{textLine}



class Hold:
    """One cargo hold: a container code + the goods stored in it. `goods` is normally a whimsical
    trade good ("Albatross Soup"); in the kidnapper's ambassador hold it is the clue0 container
    name (Ambassador Florbin, riding disguised as innocuous freight)."""
    def __init__(self, code, goods):
        self.code = code
        self.goods = goods


class FbCargo:
    """A Florbin suspect's cargo manifest as a NAMED record instead of a 13-slot positional list,
    so florbin_case.mast reads `cargo.ship` / `cargo.holds[n].goods` / `cargo.amb_hold` instead of
    decoding cargo[0] / cargo[2] / cargo[6]... The generator builds these; the MAST labels only read.

      ship      : display name at THIS snapshot (a renamed kidnapper differs from orig_name)
      captain   : captain name (shown by the declarative science scan)
      stops     : [stop1, stop2, stop3] DS numbers (2..5) - the itinerary / destinations
      dep_time  : departure/arrival time on this snapshot's manifest ("08:34"); pure flavor
      holds     : four Hold objects (holds 1-4, what a manifest / bio-scan reads)
      reserve   : spare Holds a stop-transfer swaps in, so the manifest changes station to station
      amb_hold  : index 0-3 of the hold hiding Ambassador Florbin, or None (decoys / pre-abduction)
    """
    def __init__(self, ship, captain, stops, holds, reserve, dep_time=""):
        self.ship = ship
        self.captain = captain
        self.stops = list(stops)
        self.dep_time = dep_time
        self.holds = holds
        self.reserve = reserve
        self.amb_hold = None

    def manifest_text(self):
        """The 4-hold manifest block: 'Hold 1 - Container ABC: Albatross Soup^Hold 2 - ...'
        (^ = the engine newline). One formatter instead of the manifest f-string repeated a dozen
        times, and the only place a hold's shape is spelled out."""
        return "^".join(
            "Hold " + str(i + 1) + " - Container " + str(h.code) + ": " + str(h.goods)
            for i, h in enumerate(self.holds))


def fb_holds(cargo):
    """Back-compat / MAST-friendly alias for cargo.manifest_text() (the 4-hold manifest block)."""
    return cargo.manifest_text()


def fb_hold_scan(cargo, n):
    """Bio-scan of hold `n` (0-3) for the Florbin science route. Returns (is_ambassador, line):
    a True flag when this hold hides the ambassador (so MAST schedules fb_kidnapper_discovered) and
    the scan-result line to render. Replaces four near-identical MAST branches full of cargo[5..12]
    indices with one call - the hold identity lives in cargo.amb_hold, not in a magic index."""
    h = cargo.holds[n]
    if cargo.amb_hold == n:
        return (True, "Container " + str(h.code)
                + ": !!!ALERT!!! Bio-scan matches Ambassador Florbin.")
    return (False, "Container " + str(h.code) + ": " + str(h.goods) + ". Contents verified.")


def fb_host_contact(contact, clue_role, report):
    """Host an interview contact (a lifeform) on the station where its ship first stopped (the
    station carrying clue_role, e.g. 'clue1A'), so it shows as a comms badge there, and store
    that ship's interview report on it for the //comms/fb_interview badge route to deliver."""
    if contact is None:
        return
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.query import to_list
    from sbs_utils.procedural.lifeform import lifeform_transfer
    from sbs_utils.procedural.inventory import set_inventory_value
    stations = to_list(role(clue_role))
    if stations:
        lifeform_transfer(contact.id, stations[0])
    set_inventory_value(contact, "fb_report", report)


# ---------------------------------------------------------------------------------------------------
# Florbin suspect-trail GENERATOR (pure Python, engine-free, deterministic under a seeded rng).
#
# florbin_case.mast used to hand-build the whole suspect trail with ~450 lines of repeated,
# per-scenario, per-ship blocks. This is that generator factored into a testable data core: the MAST
# label seeds the pools, calls fb_generate_case(), then just APPLIES the returned specs to the engine
# (npc_spawn / add_role / set_inventory_value / host contacts). No mystery logic lives in MAST now.
#
# The mystery invariants this core guarantees (asserted by tests/test_florbin_case.py over 20 seeds):
#   1. Exactly ONE tracked suspect is the kidnapper.
#   2. That kidnapper hides the ambassador container (clue0) in exactly one cargo3 hold
#      (cargo3.holds[cargo3.amb_hold].goods == clue0); no other suspect's holds contain clue0 ->
#      the bio hold-scan matches on exactly that ship.
#   3. clue0 is a real container name (passed from clue_list[0:20], never "Empty").
#   4. The kidnapper's interview report carries the paired narrative clue (clue1); the other two
#      tracked reports carry clue2 / clue3, never clue1.
#   5. Each tracked suspect gets two distinct DS-2..5 stops tagged clue{N}A / clue{N}B.
#   6. Each tracked suspect has a non-empty interview report (hosted on its clue{N}A station).

# Contact (## Cast key) that informs on each tracked suspect: ship 1 -> Deck Chief, etc.
FB_CONTACTS = ["deck_chief", "maint_chief", "cargo_master"]
# Departure/arrival times shown on each tracked ship's three snapshots (DS1 manifest, stop A, stop B).
# Pure flavor - no rng, so adding them never perturbs the mystery draws. Attached to FbCargo.dep_time,
# which retires the old FB_TIMES map + the colon-in-a-data-dict workaround it existed to avoid.
FB_TIMES_BY_SHIP = [
    ("08:34", "11:41", "12:28"),
    ("09:18", "11:33", "12:44"),
    ("10:22", "11:22", "12:35"),
]


def fb_pools(ship_name_data):
    """Assemble the name/goods pools for the generator from SHIP_NAME_DATA. Returns COPIES so
    generation never permanently shrinks the shared SHIP_NAME_DATA lists (the old inline code
    popped from them in place, leaking names for the rest of the session)."""
    return {
        "alpha": ["B", "C", "F", "G", "H", "J", "R", "S", "U", "V", "Y", "Z"],
        "peacetime": list(ship_name_data.get("peacetime", [])),
        "civilian": list(ship_name_data.get("civilian", [])),
        "captain": list(ship_name_data.get("captain", [])),
        "tradegoods": list(ship_name_data.get("tradegoods", [])),
    }


def _pop_rand(lst, rng, fallback):
    return lst.pop(rng.randint(0, len(lst) - 1)) if lst else fallback


def fb_make_name(pools, kind, rng):
    """A cargo-ship display name: '<letter><NN> <word>', word popped from the given pool."""
    return (rng.choice(pools["alpha"]) + str(rng.randint(1, 99)).zfill(2)
            + " " + _pop_rand(pools[kind], rng, "Freighter"))


def _make_hold(pools, rng):
    """One Hold: a random 3-letter container code + a good popped from the trade-goods pool."""
    letters = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "M", "N",
               "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
    code = "".join(letters.pop(rng.randint(0, len(letters) - 1)) for _ in range(3))
    return Hold(code, _pop_rand(pools["tradegoods"], rng, "Cargo"))


def fb_make_cargo(name, captain, stops, pools, rng, dep_time=""):
    """Build a fresh FbCargo: four active holds + four reserve holds (spares a stop-transfer swaps
    in). Draw order (4 holds, then 4 reserve) matches the old flat build, so seeds are unchanged."""
    holds = [_make_hold(pools, rng) for _ in range(4)]
    reserve = [_make_hold(pools, rng) for _ in range(4)]
    return FbCargo(name, captain, stops, holds, reserve, dep_time)


def fb_transfer_hold(cargo, rng):
    """Transfer ONE hold at a stop: swap a hold for a reserve hold (pulled off the end), so the
    manifest genuinely changes station to station. Never touches cargo.amb_hold (the hold hiding
    the ambassador). Mutates cargo; returns (unloaded, loaded) strings for the interview report."""
    candidates = [i for i in range(len(cargo.holds)) if i != cargo.amb_hold]
    if not candidates or not cargo.reserve:
        return ("", "")
    i = candidates[rng.randint(0, len(candidates) - 1)]
    old = cargo.holds[i]
    new = cargo.reserve.pop()
    cargo.holds[i] = new
    return ("Container " + str(old.code) + ": " + str(old.goods),
            "Container " + str(new.code) + ": " + str(new.goods))


def fb_generate_case(pools, clue0, clues, templates, rng,
                     n_tracked=3, n_decoy=2, rename_chance=0.5):
    """Generate the whole Florbin suspect trail as pure data.

    pools    : fb_pools(SHIP_NAME_DATA) - name/captain/goods pools (mutated via pop; use copies)
    clue0    : the ambassador container name (a REAL container from clue_list[0:20])
    clues    : [clue1, clue2, clue3] narrative clues - clue1 pairs with clue0 (goes to the kidnapper)
    templates: FB_TEXT {key: template} (report_stop / report_stop_clue / report_rename)
    rng      : a random.Random (or the seeded `random` module) - determinism comes from the caller
    Returns {"kidnapper_index": k, "investigate_message": "n1^n2^n3", "suspects": [spec, ...]}.
    Each spec carries orig_name/cur_name/captain, tracked/kidnapper flags, the three DS stops, the
    clue{N}A/B role names, cargo1/2/3, kclue, the interview report, and its contact key."""
    n_total = n_tracked + n_decoy
    kidnapper_index = rng.randint(0, n_tracked - 1)
    decoy_clues = list(clues[1:])          # [clue2, clue3, ...] for the non-kidnapper tracked ships
    suspects = []
    for i in range(n_total):
        tracked = i < n_tracked
        is_kidnapper = tracked and i == kidnapper_index
        orig_name = fb_make_name(pools, "peacetime" if tracked else "civilian", rng)
        captain = _pop_rand(pools["captain"], rng, "Unknown")

        # Three distinct DS stops from 2..5: stop1/stop2 are the visited stops (tagged A/B), stop3
        # is the "heading to" destination shown on the itinerary.
        avail = [2, 3, 4, 5]
        stops = [avail.pop(rng.randint(0, len(avail) - 1)) for _ in range(3)]

        times = FB_TIMES_BY_SHIP[i] if tracked and i < len(FB_TIMES_BY_SHIP) else ("", "", "")

        cargo1 = fb_make_cargo(orig_name, captain, stops, pools, rng, times[0])
        if is_kidnapper:
            cargo1.amb_hold = rng.randint(0, 3)                     # which hold hides the ambassador
            cargo1.holds[cargo1.amb_hold].goods = clue0            # ...riding as innocuous "goods"
        cargo2 = copy.deepcopy(cargo1)                              # amb_hold rides along on the copy
        cargo2.dep_time = times[1]

        cur_name, report, clueA, clueB, contact = orig_name, None, None, None, None
        if tracked:
            clueA = "clue" + str(i + 1) + "A"
            clueB = "clue" + str(i + 1) + "B"
            contact = FB_CONTACTS[i]
            my_clue = clues[0] if is_kidnapper else (decoy_clues.pop(0) if decoy_clues else "")
            unl1, load1 = fb_transfer_hold(cargo2, rng)             # first stop (state = cargo2)
            cargo3 = copy.deepcopy(cargo2)
            cargo3.dep_time = times[2]
            unl2, load2 = fb_transfer_hold(cargo3, rng)             # second stop (state = cargo3)
            c_part = amd_fill(templates.get("report_stop_clue"), {
                "ship": orig_name, "unloaded": unl1, "loaded": load1,
                "holds": fb_holds(cargo2), "clue": my_clue})
            if is_kidnapper and rng.random() < rename_chance:
                cur_name = fb_make_name(pools, "civilian", rng)     # the "changed registry" twist
                cargo3.ship = cur_name
                d_part = amd_fill(templates.get("report_rename"), {
                    "ship": orig_name, "unloaded": unl2, "loaded": load2,
                    "holds": fb_holds(cargo3), "newname": cur_name})
            else:
                d_part = amd_fill(templates.get("report_stop"), {
                    "ship": orig_name, "unloaded": unl2, "loaded": load2,
                    "holds": fb_holds(cargo3)})
            report = c_part + "^^" + d_part
        else:
            cargo3 = copy.deepcopy(cargo2)                          # decoy: static red-herring holds

        suspects.append({
            "orig_name": orig_name, "cur_name": cur_name, "captain": captain,
            "tracked": tracked, "kidnapper": is_kidnapper,
            "stops": stops, "clueA": clueA, "clueB": clueB,
            "cargo1": cargo1, "cargo2": cargo2, "cargo3": cargo3,
            "kclue": clue0, "report": report, "contact": contact,
        })

    # DS1 briefing: the three tracked ships' DS1 (original) names, shuffled so the kidnapper is not
    # obviously listed first.
    briefed = [s["orig_name"] for s in suspects if s["tracked"]]
    rng.shuffle(briefed)
    return {"kidnapper_index": kidnapper_index,
            "investigate_message": "^".join(briefed),
            "suspects": suspects}


# ---------------------------------------------------------------------------------------------------
# Peacetime job board - spawn-on-accept helpers (peacetime_remastered.mast).

def pr_job_active(key):
    """True if any player ship has the named job quest ACTIVE - i.e. a player has ACCEPTED it from
    the quest tab. Drives spawn-on-accept: pr_job_dispatch spawns a job's targets the first tick
    this turns True, so targets never sit in space (spoilable / stale) before the job is taken on."""
    from sbs_utils.procedural.quest import quest_get_state, QuestState
    from sbs_utils.procedural.roles import role
    from sbs_utils.procedural.query import to_object_list
    for p in to_object_list(role("__player__")):
        if quest_get_state(p.id, key) == QuestState.ACTIVE:
            return True
    return False


def pr_landmark_by_key(records, key):
    """The landmark record with this key from a landmarks_from_section list (None if absent).
    Lets the mission spawn one fixed job object (the poacher / the shuttle) on accept instead of
    landmarks_spawn'ing the whole section at shift start."""
    for r in (records or []):
        if r.get("key") == key:
            return r
    return None
