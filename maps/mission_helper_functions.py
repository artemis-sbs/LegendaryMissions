
import sbs
from sbs_utils.procedural.query import to_object_list
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.comms import comms_message


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


def fb_text_load(section):
    """{key: template} from a parsed AMD section's children (florbin_case.mast ## Florbin Text).
    Built in Python (not a MAST loop) so the template strings - which carry {ship}/{suspects}/...
    slots - are NOT interpolated at load time; comms_receive fills them per message instead."""
    out = {}
    if section is not None:
        for n in section.get("children", []):
            out[n.get("key")] = (n.get("description") or "").strip()
    return out
