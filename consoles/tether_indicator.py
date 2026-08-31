"""The grav-tether readout on Weapons - the same square the called-shot panel uses.

A tether is a state the bridge can be in for minutes at a time, and until now nothing on
Weapons said so. The cockpit button turns cyan, which is fine for the pilot who pressed
it and invisible to everyone else; on a capital ship the beam is opened from a hold-menu
that closes immediately afterwards, so the only evidence a tow existed was the ship
handling badly.

This draws the LOAD - its own flat art, the same `<artfileroot>1024.png` the called-shot
panel draws - in the same 156px square, with the mode word over it and the name and range
under it. Silhouette first: "what have I got hold of" is a shape question, and a line of
text in a scrollback is the easiest thing on a bridge to miss.

TWO REGIONS, ONE RECT, exactly as `manual_beams_helpers` sets it up - the geometry is
IMPORTED from there rather than restated, so the scrims and the words cannot drift apart
and neither can drift from the called-shot panel that shares the rect.

The square has one occupant at a time: the called-shot panel wins while Manual is on and
a target is in range (it is the thing the gunner is actively working), and the tether
takes it the rest of the time. So that a tow is never left completely unsaid, the strip
along the bottom carries `manual_tether_suffix` in BOTH states.

Depends on the LIBRARY primitive (`sbs_utils.procedural.grav_tether`), NOT on LM's
grav_tether addon - a console must not require an addon to draw itself. With no tether
open every function here returns "nothing" and the panel simply does not appear.
"""

import sbs
from sbs_utils.procedural.grav_tether import grav_tether_status
from sbs_utils.procedural.gui import gui_blank, gui_row, gui_sub_section, gui_text
from sbs_utils.procedural.query import to_id, to_object
from sbs_utils.procedural.ship_data import ship_art_image

from manual_beams_helpers import MB_CELL_PX, MB_LABEL_LAYER, MB_SQ_PX

#: The tether's color everywhere it appears. The same cyan the cockpit's tether button
#: turns, so the two readouts are recognizably the same fact.
MT_COLOR = "#0ff"

#: Scrim behind the two text bands. The art has to read THROUGH it - that is the whole
#: point of the square - but white-on-hull is unreadable without something behind it.
MT_SCRIM = "#000a"

#: No art for this hull (a cargo pod, an upgrade canister). Dark enough that the mode
#: word carries the square on its own rather than sitting on a bright empty panel.
MT_NO_ART = "background: #0008;"

#: How much of a name fits across the square at gui-1 before it starts pushing the range
#: off the right edge.
MT_NAME_CHARS = 13

#: What the mode is CALLED, per end of the beam. Towing and being towed are one registry
#: entry and opposite experiences, so the pulled end never reads "TOW".
_MT_WORDS = {
    ("lock", "source"): "LOCK",
    ("tow", "source"): "TOW",
    ("reel", "source"): "REEL",
    ("swing", "source"): "ANCHOR",
    ("lock", "target"): "HELD",
    ("tow", "target"): "TOWED",
    ("reel", "target"): "REELED",
    ("swing", "target"): "SWING",
}


def _mt_state(ship):
    """The tether this ship is in, plus the partner object, or None."""
    sid = to_id(ship)
    if sid is None or sid == 0:
        return None
    st = grav_tether_status(sid)
    if st is None:
        return None
    st = dict(st)
    st["object"] = to_object(st["partner"])
    return st


def manual_tether_partner(ship):
    """The id on the other end of this ship's tether, or 0. The panel's one gate."""
    st = _mt_state(ship)
    return 0 if st is None else st["partner"]


def manual_tether_word(ship):
    """TOW / REEL / LOCK / ANCHOR, or the pulled end's TOWED / SWING. "" when free.

    A shared haul gets its crew size appended - "TOW x4". That is the legible team signal:
    the strain BAND barely moves across a four-ship span, while the count changes the
    instant a hull joins or lets go, which is the thing the gunner acted on.
    """
    st = _mt_state(ship)
    if st is None:
        return ""
    word = _MT_WORDS.get((st.get("mode"), st.get("role")), "TETHER")
    crew = st.get("pullers") or 1
    return f"{word} x{crew}" if crew > 1 else word


def manual_tether_name(ship):
    """A short name for the load. Braces stripped, because this lands in an f-string.

    A MAST assignment re-formats any string it is given, so a brace arriving from data
    the author never sees is a SyntaxError reported against the line that displays it.
    """
    st = _mt_state(ship)
    if st is None:
        return ""
    so = st["object"]
    name = (getattr(so, "name", None) or "") if so is not None else ""
    if not name:
        name = "contact"
    name = name.replace("{", "").replace("}", "")
    if len(name) > MT_NAME_CHARS:
        name = name[:MT_NAME_CHARS - 1] + "."
    return name


def manual_tether_range(ship):
    """How far off the load is, as a whole number of units. "" when there is no tether."""
    st = _mt_state(ship)
    if st is None or st["object"] is None:
        return ""
    try:
        return str(int(round(sbs.distance_id(to_id(ship), st["partner"]))))
    except Exception:
        return ""


def manual_tether_signature(ship):
    """A cheap value that changes when the READOUT would change, and not otherwise.

    Deliberately excludes range: distance changes every tick, and repainting the panel
    every tick would tear it down under the gunner's hands. The panel's existing 3 second
    ticker refreshes the number; this is what makes grabbing and letting go show at once.

    Strain and crew size ARE in it, because both change only when someone attaches or
    releases - about once a haul - and both change what the square says.
    """
    st = _mt_state(ship)
    if st is None:
        return ""
    # Strain BAND and crew count, never the ratio. The ratio is a float that moves with
    # the fleet, and a float in a repaint key is the same mistake as putting range in it.
    return (f"{st['partner']}:{st.get('mode')}:{st.get('role')}"
            f":{st.get('strain')}:{st.get('pullers')}")


def manual_tether_suffix(ship):
    """The one-line form for the bottom strip, e.g. ``"  |  TOW Ore Hauler"``.

    Shown in BOTH panel states, so a tow is still stated while the called-shot panel owns
    the square. Empty string when there is no tether, so the caller can concatenate it
    unconditionally.
    """
    st = _mt_state(ship)
    if st is None:
        return ""
    return f"  |  {manual_tether_word(ship)} {manual_tether_name(ship)}"


# --- the square -------------------------------------------------------------
def manual_tether_bars(ship):
    """Fill `manual_beams_area()`: the load's art, scrimmed where the words go.

    Same three-band grid as the called-shot panel, and for the same reason - the label
    region declares the identical rect, so a band here and a band there are the same
    strip of screen. The MIDDLE band is left clear: that is the widest part of a
    top-down hull sprite, and covering it would defeat the point of drawing one.
    """
    art = ship_art_image(manual_tether_partner(ship))
    backdrop = f"background-image: {art}; background: white;" if art else MT_NO_ART
    gui_row(f"row-height: {MB_SQ_PX}px;")
    with gui_sub_section(backdrop):
        gui_row(f"row-height: {MB_CELL_PX}px;")
        gui_blank(1, f"background: {MT_SCRIM};")
        gui_row(f"row-height: {MB_CELL_PX}px;")
        gui_blank()
        gui_row(f"row-height: {MB_CELL_PX}px;")
        gui_blank(1, f"background: {MT_SCRIM};")


def manual_tether_labels(ship):
    """Fill `manual_beams_label_area()`: the mode word, the name and the range.

    One line per band, because the engine centers a single line in its rect and there is
    no vertical-align to reach for - which band a line is in IS its vertical position.
    """
    gui_row(f"row-height: {MB_CELL_PX}px;")
    gui_text(f"$text:{manual_tether_word(ship)};justify:center;font:gui-2;"
             f"color:{MT_COLOR}", f"layer: {MB_LABEL_LAYER};")
    gui_row(f"row-height: {MB_CELL_PX}px;")
    gui_blank()
    gui_row(f"row-height: {MB_CELL_PX}px;")
    gui_text(f"$text:{manual_tether_name(ship)};font:gui-1;color:#fff",
             f"padding: 6px, 0, 0, 0;layer: {MB_LABEL_LAYER};")
    gui_text(f"$text:{manual_tether_range(ship)};justify:right;font:gui-1;color:#fff",
             f"col-width: 62px;padding: 0, 0, 6px, 0;layer: {MB_LABEL_LAYER};")
