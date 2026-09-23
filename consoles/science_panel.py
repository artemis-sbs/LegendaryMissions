"""Science's read-out - what replaces the `science_data` and `science_data_freq` widgets.

`science_data` is 200px doing five jobs: an identity card, live shields, system health,
whatever prose five different mission tabs wrote, and the only affordance in the game that
starts a scan. `science_data_freq` is a further 40px of band readout that means nothing
until a contact has been scanned for frequencies and sits there regardless.

The console owns that rectangle now. It shows ONE tab - whichever `science_tabs` says is
current - so each gets the whole height instead of five things sharing it badly.

ONE `gui_text_area`, UPDATED IN PLACE. Not a region and not a refilled sub-section. A
region has to be pinned to an absolute `area:`, which this pane is not - it is a flex row
in a column - and a plain sub-section refilled out of band allocates new tags and leaves
every earlier fill painted underneath. A text area is a Control that owns its own region,
so assigning `.value` genuinely replaces what it drew. Engineering's Systems tab builds
its efficiency block exactly this way.

THE READOUT IS LIVE. A science tab is normally a STORED STRING - the scan writes it once
and re-selecting the contact never runs that block again, which is why `science_status.py`
has to run a ticker and push corrections per side to stop the status tab lying. Nothing
here reads that string for the numbers: they are read off the contact's blob every time
the value is rebuilt, so the readout cannot go stale.

IT SPEAKS ENGINEERING'S LANGUAGE. The efficiency coefficients below are the same eight the
damage grid derives and Engineering's Systems tab shows, read the same way and colored by
the same tiers - so "engines at 62%" means one thing across both consoles.

UNVERIFIED, and guarded accordingly: Engineering reads those coefficients off its OWN ship.
Whether the engine replicates a TARGET's coefficients to a client that has scanned it is not
something we have confirmed, and there is a good reason it might not - handing every client
every NPC's damage model is the leak the scan gate exists to prevent. Every read is coalesced
and the block is skipped entirely when nothing comes back, so this degrades to the shield and
system lines rather than drawing zeros that look like damage.

Prefixed `lm_sci_` because every top-level function here becomes a MAST global in one flat,
mission-wide namespace. A leading underscore is private to this file.
"""
from sbs_utils.helpers import FrameContext, gui_text_escape
from sbs_utils.procedural.query import to_object, to_blob
from sbs_utils.procedural.science import science_get_scan_data
from sbs_utils.procedural.sides import (side_are_enemies, side_are_allies,
                                        side_get_side_color)
from sbs_utils.procedural.gui import viewscreen_relative_bearing

from science_queue import (lm_sci_queue_list, lm_sci_queue_side,
                           lm_sci_queue_is_scanned)
from science_tabs import lm_sci_tabs_current, lm_sci_tabs_pair, LM_SCI_QUEUE_TAB

_DIM = "#8B85A8"
_LABEL = "#5B6D7F"
_GOOD = "springgreen"
_WORN = "#F2B32C"
_BAD = "Crimson"
_TUNED = "#45D3E6"
_HOSTILE = "#FF6B6B"

#: The eight coefficients the grid derives, exactly as Engineering's Systems tab lists
#: them - same keys, same order, same labels, so the two consoles cannot drift.
LM_SCI_COEFFICIENTS = (
    ("beam", "all_beam_damage_coeff", 0),
    ("tube", "all_tube_damage_coeff", 0),
    ("impulse", "impulse_damage_coeff", 0),
    ("warp", "warp_damage_coeff", 0),
    ("turn", "turn_damage_coeff", 0),
    ("sensor", "sensor_damage_coeff", 0),
    ("shield fwd", "shield_damage_coeff", 0),
    ("shield aft", "shield_damage_coeff", 1),
)

#: Engineering's four system pools, in `sbs.SHPSYS` index order.
LM_SCI_SYSTEMS = ("WEAP", "ENGN", "SENS", "SHLD")


def _blob_get(blob, key, index=0, default=None):
    """A coalesced blob read. The engine answers None for a field nothing has set, and the
    index argument is a SLOT, not a default - so it does not save you."""
    if blob is None:
        return default
    value = blob.get(key, index)
    return default if value is None else value


def _safe(text):
    """A dynamic value about to sit on a `$$`-styled markdown line.

    NOT `gui_text_escape`: that wraps a value in BACKTICKS so a `:` or `;` reads as
    literal text inside a `$text:` PROPERTY. These lines are not a property - they are
    markdown - so backticks would render as backticks. What actually has to go is a `;`,
    which closes the line's own style block early, and a newline, which splits one line
    into two.
    """
    out = str(text).replace(chr(59), chr(44))
    for ch in (chr(13), chr(10)):
        out = out.replace(ch, chr(32))
    return out


def _line(text, color=None, font="gui-1"):
    """One styled line: `$$<style-block><SPACE><text>`.

    THE SPACE IS THE SYNTAX. `TextArea.get_line_style` does `some_lines.split(" ", 1)`
    and parses everything before the first space as the style block - so a line written
    `$$color:X;font:Y;TSN Beijing` hands `color:X;font:Y;TSN` to the style parser and the
    widget draws "Document syntax issue line number 0". One space after the final `;` is
    the whole fix. Engineering's efficiency lines have it (two, in fact, because their
    body starts with an indented dash).

    It also means the style block itself must contain NO space - an authored
    `justify: left` would end the block early - which is why the values here are bare.

    Bypassing the markdown pass is the point: a scan line that happens to start with `-`
    or a digit must not silently become a bullet or a numbered list item.
    """
    if color is None:
        return _safe(text)
    return f"$$color:{color};font:{font}; {_safe(text)}"


def lm_sci_coefficients(target_id):
    """The derived efficiency coefficients for a contact, as (label, percent) pairs.

    Empty when the engine does not replicate them for this object, which is the expected
    outcome for a contact rather than the ship you are flying - see the module note.
    """
    blob = to_blob(target_id) if target_id else None
    if blob is None:
        return []
    out = []
    for label, key, index in LM_SCI_COEFFICIENTS:
        value = blob.get(key, index)
        if value is None:
            continue
        out.append((label, int(round(float(value) * 100))))
    # ALL ZEROES MEANS "NEVER POPULATED", not "every system destroyed". The engine
    # answers a typed default for a field nothing set, and the mock answers 0.0 for all
    # eight - which drew a healthy raider as a wreck with beam 0%, tube 0%, warp 0%. A
    # missing readout and a dead ship are the two things this tab must never confuse.
    if not any(pct for _label, pct in out):
        return []
    return out


def lm_sci_coefficient_color(pct):
    """What tier a coefficient reads as - the same four tiers Engineering uses, so a
    number and the grid it came from cannot disagree."""
    if pct > 100:
        return _TUNED
    if pct >= 100:
        return _GOOD
    if pct >= 75:
        return _WORN
    return _BAD


def lm_sci_system_health(target_id):
    """(label, percent) per system pool, from damage against capacity.

    Empty when the object carries no damage model at all, so a terrain object or a probe
    does not read as a healthy warship.
    """
    blob = to_blob(target_id) if target_id else None
    if blob is None:
        return []
    out = []
    for i, label in enumerate(LM_SCI_SYSTEMS):
        max_dmg = _blob_get(blob, "system_max_damage", i, 0.0) or 0.0
        if max_dmg <= 0:
            continue
        dmg = _blob_get(blob, "system_damage", i, 0.0) or 0.0
        pct = max(0, min(100, int(round((1.0 - dmg / max_dmg) * 100))))
        out.append((label, pct))
    return out


#: The five shield frequency bands, in the order the engine's own readout shows them.
LM_SCI_FREQ_BANDS = ("A", "B", "C", "D", "E")

#: `shield_freq_strength`'s scale is DETECTED, not assumed.
#:
#: It was read as a 0..1 coefficient first (every band came out at 100% or more), then
#: hard-coded to 10000 - and that second guess is what silently LOST the readout: values
#: smaller than the assumed scale all round to 0, and the all-zero guard then drops the
#: whole block. A wrong constant here does not look wrong, it looks like missing data.
#:
#: So the scale comes from the values themselves. The bands are one reading on one ship,
#: so the biggest of them says which scale they are on, and every band is divided by the
#: same number - which is what keeps them comparable and the WEAK marker honest.
LM_SCI_FREQ_SCALES = (1.0, 100.0, 10000.0)

#: Tier edges as PERCENT of that scale, matching how the engine's own bars read.
LM_SCI_FREQ_HIGH = 75
LM_SCI_FREQ_MID = 50
LM_SCI_FREQ_LOW = 25


def lm_sci_shield_frequencies(target_id):
    """(band, percent) per shield frequency, or [] when the contact does not report them.

    This is what the `science_data_freq` widget drew: how well the target's shields hold
    against each band, so weapons can tune to the one they hold WORST. It is the single
    most actionable thing science can hand a gunner, and it is why this tab exists.

    THESE ARE THE REAL BLOB VALUES, not invented ones: `blob.get("shield_freq_strength", i)`
    for each of the five bands. (The MOCK fabricates its own bands from the contact's id
    to feed its `science_data_freq` widget - that is the mock's display, and nothing here
    reads it.)

    WHAT IS UNVERIFIED is the key's SHAPE. `shield_freq_strength` is in the engine field
    table the mock mirrors, so the name is real, but nothing in the tree reads or writes
    it - so "indexed 0-4, one per band, 0.0-1.0" is inference from how the sibling shield
    keys work, not something measured. If the bands come back empty on a bridge, that
    assumption is what to check first.

    Guarded accordingly: every read is coalesced and the whole block is dropped when
    nothing comes back, so the worst case is a status tab without frequencies rather than
    one showing five zeroes that read as "no shields at all".
    """
    blob = to_blob(target_id) if target_id else None
    if blob is None:
        return []
    raw = []
    for i, band in enumerate(LM_SCI_FREQ_BANDS):
        value = blob.get("shield_freq_strength", i)
        if value is None:
            continue
        raw.append((band, float(value)))
    if not raw:
        return []
    scale = lm_sci_frequency_scale(max(v for _b, v in raw))
    return [(band, int(round(value / scale * 100.0))) for band, value in raw]


def lm_sci_frequency_scale(peak):
    """The scale these readings are on, from the largest of them.

    Smallest scale the peak fits in, so a 0..1 coefficient, a percentage and a 0..10000
    level all read correctly and none of them is rounded away to nothing.
    """
    for scale in LM_SCI_FREQ_SCALES:
        if peak <= scale:
            return scale
    return LM_SCI_FREQ_SCALES[-1]


def lm_sci_has_band_readings(bands):
    """True when the bands carry an actual reading.

    All zeroes means "never populated", not "shields down on every band" - the engine
    answers a typed default for a field nothing wrote. Kept SEPARATE from reading the
    bands so the tab can tell the difference on screen: a block that silently vanishes
    is indistinguishable from a block that was never coded, which is exactly how long
    this took to notice.
    """
    return any(pct for _band, pct in bands)


def lm_sci_frequency_color(pct):
    """What tier a band's strength reads as - quartered at 25 / 50 / 75 percent, which is
    how the engine's own bars read.

    Coloured by MAGNITUDE, not by desirability, and deliberately: a low band is good news
    for the gunner but it is still a low reading, and flipping the colour scale over
    would put this tab at odds with every other readout on the bridge. Which band to
    shoot is said in words instead - see the WEAK marker.
    """
    if pct >= LM_SCI_FREQ_HIGH:
        return _GOOD
    if pct >= LM_SCI_FREQ_MID:
        return "#8A9A24"
    if pct >= LM_SCI_FREQ_LOW:
        return _WORN
    return "#B4711E"


def lm_sci_weakest_band(bands):
    """The band to tune to: the one the target holds worst. None for an empty readout."""
    if not bands:
        return None
    return min(bands, key=lambda pair: pair[1])[0]


def _contact_color(ship_id, target_id):
    if side_are_enemies(ship_id, target_id):
        return _HOSTILE
    if side_are_allies(ship_id, target_id):
        return _GOOD
    return "white"


# --- the header and the statline ------------------------------------------------------
#
# TWO WIDGETS, NOT TWO LINES OF THE BODY, because they change on completely different
# clocks. The title moves only when the selection does; the STATLINE moves every tick a
# contact is under way. Folding them into the text area's value would mean rebuilding the
# whole readout - eight coefficients, four system lines, whatever prose the mission wrote -
# every frame to keep one range figure honest. Two `gui_text` widgets updated in place cost
# one string assignment each.


def lm_sci_header_name_text(client_id):
    """The contact's NAME, colored by DIPLOMATIC RELATION - hostile, allied or neutral.

    `overflow:shrink` rather than wrap: a long name - "TSN Warramunga" - wrapped to a
    second line that the engine then drew OVER the statline, because it does not clip.
    Shrinking walks down the font ladder (gui-3, gui-2, ...) until the name fits on one
    line, which keeps the title one line tall whatever the contact is called. This is the
    first production use of the policy, so it is worth a look on a real bridge.

    Two widgets rather than one string, because the two halves of this line answer
    different questions and a `gui_text` carries one colour. What a contact IS to us
    (relation) and who it BELONGS to (side) are not the same fact: a neutral ship of a
    side we are at war with elsewhere must not read as hostile because of its flag.
    """
    ship_id, target_id = lm_sci_tabs_pair(client_id)
    target = to_object(target_id) if target_id else None
    if target is None:
        return f"$text:{gui_text_escape('(no contact selected)')};color:{_DIM};font:gui-3;"
    # AN UNSCANNED CONTACT IS "unknown" - name AND colour. The relation colour is itself
    # information: a red title tells the crew this is hostile before anyone has earned
    # that, which is the whole thing the scan gate exists to withhold.
    if lm_sci_queue_is_scanned(ship_id, target_id, "scan"):
        name = getattr(target, "name", None) or "unknown"
        color = _contact_color(ship_id, target_id)
    else:
        name, color = "unknown", _DIM
    return (f"$text:{gui_text_escape(str(name))};color:{color};font:gui-3;"
            f"overflow:shrink;")


def lm_sci_header_side_text(client_id):
    """The contact's SIDE, in that side's OWN colour - the same one its icon uses on the
    2D map, so the word and the blip agree."""
    _ship_id, target_id = lm_sci_tabs_pair(client_id)
    target = to_object(target_id) if target_id else None
    if target is None:
        return "$text:;"
    # The SIDE is scan data too - a flag identifies a contact as surely as a name does.
    ship_id, _t = lm_sci_tabs_pair(client_id)
    if not lm_sci_queue_is_scanned(ship_id, target_id, "scan"):
        return "$text:;"
    side = getattr(target, "side", None) or ""
    if not side:
        return "$text:;"
    color = side_get_side_color(side, _DIM)
    return (f"$text:{gui_text_escape(str(side))};color:{color};font:gui-3;"
            f"justify:right;overflow:shrink;")


def lm_sci_header_revision(client_id):
    """What an `on change` watches for the title: both halves at once, so a side change
    repaints even when the name has not moved."""
    return (lm_sci_header_name_text(client_id), lm_sci_header_side_text(client_id))


def lm_sci_statline(client_id):
    """`rng:  nnnnnn  ber: nnn alt: nnn` - the numbers that move.

    BEARING is RELATIVE to the ship's heading, 0 dead ahead, clockwise:
    `viewscreen_relative_bearing` takes it from the engine's own forward/right vectors
    rather than assuming an axis, which is the documented way to avoid a bearing that is
    quietly 90 degrees out. ALTITUDE is signed - above is positive - so the sign carries
    the information the stock readout spends the words "Above You" on.

    A part that cannot be computed is left out rather than shown as zero: a missing
    reading and a reading of zero mean very different things to a science officer.
    """
    ship_id, target_id = lm_sci_tabs_pair(client_id)
    if not ship_id or not target_id:
        return ""
    origin, target = to_object(ship_id), to_object(target_id)
    if origin is None or target is None:
        return ""
    parts = []
    ctx = FrameContext.context
    if ctx is not None and ctx.sbs is not None:
        try:
            parts.append("rng: " + str(int(ctx.sbs.distance_id(ship_id, target_id))))
        except Exception:                               # noqa: BLE001
            pass
    bearing = viewscreen_relative_bearing(target_id, ship_id)
    if bearing is not None:
        parts.append("ber: " + str(int(bearing)))
    try:
        parts.append("alt: " + str(int(round(target.pos.y - origin.pos.y))))
    except Exception:                                   # noqa: BLE001
        pass
    return "  ".join(parts)


def lm_sci_statline_text(client_id):
    """The statline as props for its own `gui_text`."""
    return (f"$text:{gui_text_escape(lm_sci_statline(client_id))};color:{_LABEL};"
            f"font:gui-1;overflow:shrink;")


def lm_sci_shield_lines(target_id):
    """Front and rear shields, coloured by how much is left.

    On BOTH tabs, deliberately. Shields are the fastest-moving thing a science officer
    reports and the one a gunner asks for by name, so making somebody switch tabs to see
    them during a fight is the wrong trade - and status is the tab they will be on, since
    it is where the systems and the bands are.

    The VALUE is absolute, matching the stock readout, and only the colour is a ratio:
    "front shields 90" is what gets said out loud, not "front shields 75 percent".
    """
    blob = to_blob(target_id) if target_id else None
    if blob is None:
        return []
    lines = []
    for i, label in enumerate(("FRNT SHLD", "REAR SHLD")):
        value = _blob_get(blob, "shield_val", i, None)
        if value is None:
            continue
        max_value = _blob_get(blob, "shield_max_val", i, 0.0) or 0.0
        color = _GOOD
        if max_value > 0:
            ratio = float(value) / max_value
            color = _GOOD if ratio >= 0.75 else (_WORN if ratio >= 0.25 else _BAD)
        lines.append(_line(f"{label}  {int(value)}", color))
    return lines


def lm_sci_panel_scan_lines(ship_id, target_id):
    """What the identity card adds BELOW the header and statline: how hard it would be
    to hurt, and whatever the mission wrote."""
    if target_id is None:
        return []
    lines = lm_sci_shield_lines(target_id)
    text = science_get_scan_data(ship_id, target_id, "scan")
    if text:
        lines += ["", _line(text, _DIM)]
    return lines


def lm_sci_panel_status_lines(ship_id, target_id):
    """Engineering's readout, pointed at somebody else's ship."""
    if target_id is None:
        return []
    # SHIELDS FIRST, before the systems. They move fastest and they are what a gunner
    # asks for by name, so they should not be below a block that rarely changes.
    lines = lm_sci_shield_lines(target_id)
    if lines:
        lines.append("")
    health = lm_sci_system_health(target_id)
    if health:
        lines.append(_line("SYSTEMS", _LABEL))
        for label, pct in health:
            lines.append(_line(f"  {label}  {pct}%", lm_sci_coefficient_color(pct)))
    # SHIELD FREQUENCIES, drawn HERE rather than by the engine's own widget.
    #
    # `science_data_freq` could not be made to draw from a console that replaces
    # `science_data_tabs` - the engine appears to have no way to be told which tab is
    # active. Engine-confirmed; the note in science_tabs.py lists what was tried. So the
    # bands are drawn as text until that ask lands.
    #
    # Hostiles only: nobody tunes a beam to a ship they are not shooting, and the space
    # is better spent on what is left of a friendly.
    if side_are_enemies(ship_id, target_id):
        bands = lm_sci_shield_frequencies(target_id)
        lines += ["", _line("SHIELD FREQUENCY", _LABEL)]
        if not lm_sci_has_band_readings(bands):
            # SAY SO rather than draw nothing. Zeroes must not be shown as real - five
            # of them read as "no shields at all", a lie in the dangerous direction -
            # but a heading with a reason under it tells a science officer the console
            # is working and the data is not there, which an empty tab does not.
            lines.append(_line("  (no band readings from this contact)", _DIM))
        else:
            weak = lm_sci_weakest_band(bands)
            for band, pct in bands:
                color = lm_sci_frequency_color(pct)
                if band == weak:
                    # Named in WORDS as well as tiered: the tier colour says how strong
                    # the band is, the word says which one to shoot, and a gunner reads
                    # this aloud over comms. Both facts are wanted.
                    lines.append(_line(f"  {band}  {pct}%   WEAK", color))
                else:
                    lines.append(_line(f"  {band}  {pct}%", color))

    # NO EFFICIENCY BLOCK ON A CONTACT.
    #
    # The eight `*_damage_coeff` values are DERIVED FROM A SHIP'S OWN DAMAGE GRID, and a
    # console only has a grid for the ship it is flying. Read off somebody else's hull
    # they are not a weaker signal, they are the wrong number - reported as inaccurate on
    # NPCs from a real bridge, which is exactly where this would show first.
    #
    # SYSTEM HEALTH above is different and stays: `system_damage` / `system_max_damage`
    # is the model the engine uses to kill an NPC, so it is true about any ship. The
    # readings a science officer can legitimately have are what this tab shows.
    #
    # `lm_sci_coefficients` is kept - it is correct about the ship you are ON, which is
    # what Engineering's own Systems tab uses it for.

    text = science_get_scan_data(ship_id, target_id, "status")
    if text:
        lines += ["", _line(text, _WORN)]
    return lines


def lm_sci_panel_prose_lines(ship_id, target_id, tab):
    """A prose tab - intel, bio, mat, or anything a mission invented."""
    if target_id is None:
        return []
    lines = []
    text = science_get_scan_data(ship_id, target_id, tab)
    if not text or text == "no data":
        lines.append(_line("(nothing on this band)", _DIM))
    else:
        lines.append(_safe(text))
    return lines


def lm_sci_panel_queue_lines(ship_id):
    """The side's queue: contact and tab, who asked, and how far along."""
    side = lm_sci_queue_side(ship_id)
    entries = lm_sci_queue_list(side) if side else []
    lines = [_line(f"SCAN QUEUE  {side or 'no side'}", _TUNED, "gui-2")]
    if not entries:
        lines.append(_line("(nothing queued)", _DIM))
        return lines
    for i, entry in enumerate(entries):
        target = to_object(entry["target"])
        name = getattr(target, "name", None) or "unknown"
        origin = to_object(entry["origin"])
        asked = getattr(origin, "name", None) or "?"
        color = _TUNED if i == 0 else _DIM
        detail = f"{int(entry['pct'])}%" if i == 0 else "waiting"
        lines.append(_line(f"{name}  {entry['tab']}  {detail}", color))
        lines.append(_line(f"    {asked}", _LABEL))
    return lines


def lm_sci_panel_effective_tab(client_id):
    """Which tab the READOUT actually shows, which is not always the one selected.

    A tab with no data for this contact shows the QUEUE instead. Two reasons, and the
    first is the important one:

    * NOTHING A SCAN HAS NOT EARNED. Shields, system health and the efficiency
      coefficients are all scan results, and drawing them off the contact's blob before
      the scan lands hands the crew exactly what the scan was for. The old panel did
      this - it read the blob whether or not the side had scanned anything.
    * An empty pane is a dead end. The queue is the useful thing to be looking at while
      a scan runs, and it is where the scan you just asked for appears.
    """
    tab = lm_sci_tabs_current(client_id)
    if tab == LM_SCI_QUEUE_TAB:
        return tab
    ship_id, target_id = lm_sci_tabs_pair(client_id)
    if not ship_id or not target_id:
        return LM_SCI_QUEUE_TAB
    if not lm_sci_queue_is_scanned(ship_id, target_id, tab):
        return LM_SCI_QUEUE_TAB
    return tab


def lm_sci_panel_value(client_id):
    """The whole read-out for this console, as a text-area value."""
    ship_id, target_id = lm_sci_tabs_pair(client_id)
    tab = lm_sci_panel_effective_tab(client_id)
    if tab == LM_SCI_QUEUE_TAB:
        lines = lm_sci_panel_queue_lines(ship_id)
    elif not ship_id:
        lines = [_line("(this console is not on a ship)", _DIM)]
    elif tab == "scan":
        lines = lm_sci_panel_scan_lines(ship_id, target_id)
    elif tab == "status":
        lines = lm_sci_panel_status_lines(ship_id, target_id)
    else:
        lines = lm_sci_panel_prose_lines(ship_id, target_id, tab)
    # THE JOINED MARKDOWN, RAW. Not wrapped in a text property - that was a crash, not
    # a cosmetic slip: every styled line starts with its own style block ending in a
    # semicolon, and that semicolon closed the text property, so the engine was handed
    # malformed props and raised IndexError: invalid string position out of
    # send_gui_text. Engineering joins its efficiency block the same way.
    return chr(10).join(lines)


def lm_sci_panel_revision(client_id):
    """What an `on change` watches: THE RENDERED VALUE ITSELF.

    It used to be a hand-picked tuple - tab, target, system health, frequencies,
    coefficients - and that is a bug waiting to happen, because anything drawn but not
    listed never triggers a repaint. It happened: the SHIELD numbers and the mission's
    own scan TEXT were both drawn and neither was watched, so the scan tab sat on stale
    figures while a contact took fire, and a status line pushed by `science_status.py`
    never appeared.

    Comparing the value cannot drift from what is on screen, because it IS what goes on
    screen. It costs one build of the string per poll - a handful of blob reads, the same
    order as the tuple it replaces, which was already reading system health, frequencies
    and every coefficient.
    """
    return lm_sci_panel_value(client_id)
