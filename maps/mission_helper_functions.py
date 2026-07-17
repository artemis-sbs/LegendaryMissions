
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
