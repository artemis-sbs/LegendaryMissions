
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



def fb_holds(cargo):
    """The 4-hold cargo manifest block for a Florbin suspect's cargo array (florbin_case.mast).
    Holds live at indices 5..12: (container-code, goods) pairs for holds 1-4. Returns
    "Hold 1 - Container <code>: <goods>^..." (^ = the engine newline). One formatter instead of
    the manifest f-string repeated a dozen times."""
    return "^".join(
        "Hold " + str(i + 1) + " - Container " + str(cargo[5 + 2 * i]) + ": " + str(cargo[6 + 2 * i])
        for i in range(4))


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


def fb_times_map():
    """Docking-time strings for the Florbin A/B station previews (florbin_case.mast fb_preview),
    keyed by ship+cargo snapshot. Built in Python (NOT a MAST dict literal) so the colon inside a
    time value ('11:41') never reaches the MAST compiler as a data-dict literal - a literal string
    value with a colon in a comms-button data dict is an untested idiom that can desync the parser.
    fb_preview looks the time up by ckey instead of carrying it in the button's data dict."""
    return {
        "ship1_cargo2": "11:41",
        "ship1_cargo3": "12:28",
        "ship2_cargo2": "11:33",
        "ship2_cargo3": "12:44",
        "ship3_cargo2": "11:22",
        "ship3_cargo3": "12:35",
    }


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
#   2. That kidnapper carries the ambassador container (clue0) in one cargo3 hold-goods slot
#      (index 6/8/10/12) == kclue; no other suspect's holds contain clue0 -> the bio hold-scan
#      matches on exactly that ship.
#   3. clue0 is a real container name (passed from clue_list[0:20], never "Empty").
#   4. The kidnapper's interview report carries the paired narrative clue (clue1); the other two
#      tracked reports carry clue2 / clue3, never clue1.
#   5. Each tracked suspect gets two distinct DS-2..5 stops tagged clue{N}A / clue{N}B.
#   6. Each tracked suspect has a non-empty interview report (hosted on its clue{N}A station).

# Hold-goods indices for holds 1-4 in a cargo array (container code lives at idx-1).
FB_HOLD_GOODS_IDX = [6, 8, 10, 12]
# Contact (## Cast key) that informs on each tracked suspect: ship 1 -> Deck Chief, etc.
FB_CONTACTS = ["deck_chief", "maint_chief", "cargo_master"]


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


def fb_make_cargo(name, captain, stops, pools, rng):
    """Build a fresh cargo array: [name, captain, stop1, stop2, stop3, (container,good) x8].
    Holds 1-4 are pairs 0-3 (indices 5..12); pairs 4-7 are the 'reserve' fb_transfer_hold draws
    from to simulate loading new containers at a stop."""
    cargo = [name, captain, stops[0], stops[1], stops[2]]
    for _ in range(8):
        letters = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "M", "N",
                   "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
        code = "".join(letters.pop(rng.randint(0, len(letters) - 1)) for _ in range(3))
        cargo.append(code)
        cargo.append(_pop_rand(pools["tradegoods"], rng, "Cargo"))
    return cargo


def fb_transfer_hold(cargo, avoid_idx, rng):
    """Transfer ONE hold at a stop: swap a hold's (container,good) for a reserve pair pulled off
    the end of the array, so the manifest genuinely changes station to station. Never touches
    avoid_idx (the hold hiding the ambassador). Mutates cargo; returns (unloaded, loaded) strings."""
    candidates = [gi for gi in FB_HOLD_GOODS_IDX if gi != avoid_idx and gi < len(cargo)]
    if not candidates or len(cargo) < 7:
        return ("", "")
    gi = candidates[rng.randint(0, len(candidates) - 1)]
    old_cont, old_good = cargo[gi - 1], cargo[gi]
    new_good = cargo.pop()
    new_cont = cargo.pop()
    cargo[gi - 1] = new_cont
    cargo[gi] = new_good
    return ("Container " + str(old_cont) + ": " + str(old_good),
            "Container " + str(new_cont) + ": " + str(new_good))


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

        cargo1 = fb_make_cargo(orig_name, captain, stops, pools, rng)
        rand1 = None
        if is_kidnapper:
            rand1 = FB_HOLD_GOODS_IDX[rng.randint(0, len(FB_HOLD_GOODS_IDX) - 1)]
            cargo1[rand1] = clue0          # the ambassador rides in this hold, as innocuous "goods"
        cargo2 = copy.deepcopy(cargo1)

        cur_name, report, clueA, clueB, contact = orig_name, None, None, None, None
        if tracked:
            clueA = "clue" + str(i + 1) + "A"
            clueB = "clue" + str(i + 1) + "B"
            contact = FB_CONTACTS[i]
            my_clue = clues[0] if is_kidnapper else (decoy_clues.pop(0) if decoy_clues else "")
            unl1, load1 = fb_transfer_hold(cargo2, rand1, rng)      # first stop (state = cargo2)
            cargo3 = copy.deepcopy(cargo2)
            unl2, load2 = fb_transfer_hold(cargo3, rand1, rng)      # second stop (state = cargo3)
            c_part = amd_fill(templates.get("report_stop_clue"), {
                "ship": orig_name, "unloaded": unl1, "loaded": load1,
                "holds": fb_holds(cargo2), "clue": my_clue})
            if is_kidnapper and rng.random() < rename_chance:
                cur_name = fb_make_name(pools, "civilian", rng)     # the "changed registry" twist
                cargo3[0] = cur_name
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
