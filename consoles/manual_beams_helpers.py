"""The Manual Beams called-shot panel - the target's own art, with its systems on it.

The gunner picks a system to aim at. That used to be three plain buttons under a
`3dview`, which cost the bottom fifth of the console and told nobody which system was
worth shooting. This draws the target's flat sprite (`<artfileroot>1024.png`) and lays
the three targetable systems over it as bars that fill from the bottom in proportion to
how much of that system is left. The bars ARE the buttons.

TWO REGIONS, ONE RECT. The layout engine has no overlapping siblings - a row's margin
shrinks its children along with its backdrop, and a clickregion's text/background is a
HOVER affordance (it is how a listbox row is selected), not a paint surface. So a label
cannot sit on top of a fill inside one layout. Instead the caller declares two absolute
regions with the SAME `area:` string - `manual_beams_area()` for the art and the bars,
`manual_beams_label_area()` for the text, raised with `layer:` - and every rect lines up
because it is literally the same string. The areas are all-px so no font is in the path.

Row order is engines / sensors / weapons top to bottom, which is SHPSYS 1, 2, 0 and NOT
enum order. IT MATCHES THE ART: the sprite is drawn with the ship's BACK at the top of
the square and its NOSE at the bottom, so the engines band sits over the engines and the
weapons band sits over the bow. Aiming at a system means clicking the part of the ship it
is in, which is the whole reason this replaced three plain buttons. Reversing these two
puts every click on the wrong end of the hull while still looking plausible.

Sensors is deliberately the middle band: it is where the HIT flash lands, so the word
reads as vertically centered in the square.
"""

import random

import sbs
from sbs_utils.procedural.comms import comms_broadcast
from sbs_utils.procedural.execution import get_shared_variable, set_shared_variable
from sbs_utils.procedural.gui import (
    gui_blank, gui_message_callback, gui_row, gui_sub_section, gui_text)
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import get_weapons_selection, to_id, to_object
from sbs_utils.procedural.ship_data import ship_art_image


# --- Geometry ---------------------------------------------------------------
# One square, three equal bands. Everything below is derived from these, so the bars and
# the labels cannot drift apart.
MB_SQ_PX = 156          # the square's side (~6.5em at gui-2)
MB_CELL_PX = 52         # MB_SQ_PX // 3
MB_X_PX = 130           # left edge, clear of the Manual checkbox
MB_PCT_PX = 46          # the percent column
MB_LABEL_LAYER = 1500   # over the bars (backdrops paint at 1000)

# (display name, SHPSYS index, click tag). Order is the ROW order - see the module note.
MB_SYSTEMS = (
    ("engines", sbs.SHPSYS.ENGINES, "mb_engines"),
    ("sensors", sbs.SHPSYS.SENSORS, "mb_sensors"),
    ("weapons", sbs.SHPSYS.WEAPONS, "mb_weapons"),
)

# Which band the HIT flash writes into: the MIDDLE one, so the word reads as vertically
# centered in the square. Derived from the table rather than named, so re-ordering the
# bands moves the word with them instead of leaving it off-center.
MB_HIT_BAND = MB_SYSTEMS[len(MB_SYSTEMS) // 2][1]

# Fill colors, 4-digit RGBA (the `#1578` spelling used across the repo). The alpha is the
# point: the hull has to read THROUGH the bar, or the panel stops saying which ship it is
# about.
MB_FILL_GOOD = "#2f88"
MB_FILL_HURT = "#fc38"
MB_FILL_BAD = "#f338"
MB_HIT_COLOR = "#f22c"
MB_HOVER = "#fff3"

MB_TEXT = "#fff"
MB_TEXT_ARMED = "#ff0"      # the system currently loaded for a called shot
MB_DIVIDER = "#fff6"


def manual_beams_area():
    """The absolute `area:` for the square. Bottom-aligned with the Manual checkbox."""
    return f"area: {MB_X_PX}px, 96-{MB_SQ_PX}px, {MB_X_PX + MB_SQ_PX}px, 96;"


def manual_beams_label_area():
    """The SAME rect as `manual_beams_area`, raised over it. Same string on purpose."""
    return manual_beams_area() + f"layer: {MB_LABEL_LAYER};"


# --- Reading the target -----------------------------------------------------
def manual_beams_health(id_or_obj, system):
    """How much of one system is left, 0..100.

    `1 - system_damage / system_max_damage`, the same sum the mock's systems readout
    takes. Two guards that are not optional:

    * The ENGINE answers `None` for a data_set field nothing has written, where the mock
      hands back a typed default - so an unguarded read is fine headless and raises
      `NoneType / int` on a real bridge. And a failing expression STOPS the command, so
      the panel would simply stop drawing.
    * `system_damage` OVERSHOOTS its max here. The called-shot route grows it
      geometrically (`cur * 1.35`) and only then compares, so a dying system reports more
      damage than it has capacity for. Clamp, or the bar goes negative.
    """
    so = to_object(id_or_obj)
    if so is None:
        return 0
    blob = getattr(so, "data_set", None)
    if blob is None:
        return 0
    mx = blob.get("system_max_damage", system) or 0
    if mx <= 0:
        # Nothing has declared a capacity for this hull - full rather than empty, so an
        # unknown target does not read as a wreck.
        return 100
    dmg = blob.get("system_damage", system) or 0
    return max(0, min(100, int(round((1.0 - float(dmg) / float(mx)) * 100))))


def _mb_fill_color(pct):
    if pct > 66:
        return MB_FILL_GOOD
    if pct > 33:
        return MB_FILL_HURT
    return MB_FILL_BAD


# --- The bars (lower region) ------------------------------------------------
def manual_beams_bars(id_or_obj, hit=False):
    """Fill `manual_beams_area()`: the target's art, with a bottom-up bar per system.

    `hit` swaps in the flash: one tinted pane over the whole square. The branch is here
    rather than in the caller because MAST reads better without an if/else nested inside
    a `with gui_rebuild(...)` block, and there is exactly one right answer either way.

    The art is the sub-section's background-image, which paints at BACKDROP_LAYER (1000)
    - under every bar and every label without anyone having to say so. `background:
    white` is the tint, i.e. untinted; the backdrop is only drawn at all when a color is
    set, so the pair is required, not decorative.
    """
    if hit:
        gui_row(f"row-height: {MB_SQ_PX}px;")
        gui_blank(1, f"background: {MB_HIT_COLOR};")
        return
    art = ship_art_image(id_or_obj)
    backdrop = f"background-image: {art}; background: white;" if art else "background: #0008;"
    gui_row(f"row-height: {MB_SQ_PX}px;")
    with gui_sub_section(backdrop):
        _mb_bar_cells(id_or_obj)


def _mb_bar_cells(id_or_obj):
    for _name, system, _tag in MB_SYSTEMS:
        pct = manual_beams_health(id_or_obj, system)
        fill = int(round(MB_CELL_PX * pct / 100.0))
        spacer = MB_CELL_PX - fill
        gui_row(f"row-height: {MB_CELL_PX}px;")
        with gui_sub_section():
            # Only the rows that have height are emitted. A full bar wants no spacer and
            # an empty one wants no fill; asking for a `0px` row is a way of finding out
            # what the layout does with one, which is not a question worth asking.
            if spacer > 0:
                gui_row(f"row-height: {spacer}px;")
                gui_blank()
            if fill > 0:
                gui_row(f"row-height: {fill}px;")
                gui_blank(1, f"background: {_mb_fill_color(pct)};")


# --- The labels (upper region) ----------------------------------------------
def manual_beams_labels(id_or_obj, armed=None, hit=False, hit_text="HIT"):
    """Fill `manual_beams_label_area()`: the name, the percent, and the click targets.

    `hit` swaps what the bands SAY - one word in the MIDDLE band, nothing in the other
    two - and changes nothing about where they are or what they answer to. Centered in
    the sensors band rather than in the square, because that is the band a single line
    lands vertically centered in: the engine centers one line in its rect and there is no
    vertical-align to reach for, so which band the word is in IS the vertical position.

    THE BANDS ARE BUILT IN EVERY STATE, and that is not cosmetic. A band is the only
    thing absorbing a click over this part of the screen; the engine's `weapon_2d_view`
    runs underneath the whole panel. Drawing the flash as three plain rows instead left
    the square with no click regions for two seconds, so a click during the flash reached
    the 2d view, selected empty space, and dropped the weapons lock - which took
    `target_id` to 0 and sent the panel to minimize. The panel's hit-target geometry must
    not depend on what it is currently showing.

    The name is left-justified and the percent right-justified in a fixed column, so
    neither moves as the number changes width. The whole band is the hit target - the
    click tag goes on the band's sub-section, and a sub-section only emits its
    clickregion when `click_text` is set, so it is set to empty, which is exactly what a
    listbox row does to make itself selectable.
    """
    first = True
    for name, system, tag in MB_SYSTEMS:
        cell = MB_CELL_PX
        if not first:
            # A 1px rule between bands, paid for out of the band below it so every band
            # still starts where its bar does.
            gui_row("row-height: 1px;")
            # Explicit layer, not "it happens to be drawn later": a background is a
            # backdrop at 1000, the same band the bars paint in, and a tie between two
            # images is settled by emission order across two independent regions - which
            # is not a thing to rely on. Text needs no such help; on a tie text wins.
            gui_blank(1, f"background: {MB_DIVIDER};layer: {MB_LABEL_LAYER};")
            cell -= 1
        first = False
        pct = manual_beams_health(id_or_obj, system)
        color = MB_TEXT_ARMED if armed == system else MB_TEXT
        gui_row(f"row-height: {cell}px;")
        band = gui_sub_section(f"click_tag: {tag};click_text:;click_background: {MB_HOVER};")
        with band:
            gui_row(f"row-height: {cell}px;")
            if hit:
                if system == MB_HIT_BAND:
                    gui_text(f"$text:{hit_text};justify:center;font:gui-4;color:#fff",
                             f"layer: {MB_LABEL_LAYER};")
                else:
                    gui_blank()
            else:
                gui_text(f"$text:{name};font:gui-1;color:{color}",
                         f"padding: 6px, 0, 0, 0;layer: {MB_LABEL_LAYER};")
                gui_text(f"$text:{pct}%;justify:right;font:gui-1;color:{color}",
                         f"col-width: {MB_PCT_PX}px;padding: 0, 0, 6px, 0;"
                         f"layer: {MB_LABEL_LAYER};")
        gui_message_callback(band, _mb_band_handler(system, tag))


# --- Arming a called shot ---------------------------------------------------
def _mb_repaint():
    """Bump the shared version every manual-beams console watches.

    The panel's own MAST ticker owns this variable; writing it from here is how a click
    handled in Python gets the band it just armed to light up, without the handler
    needing a task of its own.
    """
    set_shared_variable("manual_beams_version",
                        (get_shared_variable("manual_beams_version", 0) or 0) + 1)


def _mb_band_handler(system, tag):
    """One click handler per band, built by a factory so the closure cannot capture a
    loop variable at its last value - the standard trap for handlers made in a loop.

    A callback, not an `on gui_click` block, and that is not a style choice. A trigger
    registered inside a region rebuild is APPENDED to the page's click list and nothing
    prunes it, so a panel that rebuilds every three seconds would stack up handlers for
    the life of the mission - and the next full page repaint would throw all of them
    away at once. A callback lives on the widget, so it is rebuilt with the widget and
    dies with it.

    `Layout.on_message` invokes a section's callback for EVERY message the client sends,
    not only the ones carrying this section's tag (`Column.on_message` does gate; a
    section does not). Hence the filter - without it, ticking the Manual checkbox would
    arm all three systems.
    """
    def _handler(event, _item):
        if getattr(event, "sub_tag", None) != tag:
            return
        manual_beams_arm(sbs.get_ship_of_client(event.client_id), system, event.client_id)
    return _handler


def manual_beams_arm(id_or_obj, system, client_id=None):
    """Load a called shot on `system`, and roll for whether it lands as a critical.

    Straight out of the old `manual_weapons_shoot` label, unchanged in behavior: picking
    a different system throws away a critical you had already won, and a critical that is
    already armed is not re-rolled. It moved to Python because the bands are now handled
    by a callback, and none of it was ever GUI work.

    The one thing that IS new: the selected system is recorded every time, not only when
    it changes. Nothing depended on the old gap - the damage route needs
    MANUAL_CRITICAL_HIT as well - and the band cannot light up as "loaded" if the state
    it reads is only written on a switch.
    """
    ship_id = to_id(id_or_obj)
    if not ship_id:
        return
    critical = get_inventory_value(ship_id, "MANUAL_CRITICAL_HIT", False)
    last = get_inventory_value(ship_id, "MANUAL_LAST_PICK", None)
    if system != last:
        set_inventory_value(ship_id, "MANUAL_CRITICAL_HIT", None)
        if critical:
            comms_broadcast(client_id, "Lost Critical hit, chance", "cyan")
        critical = None
    set_inventory_value(ship_id, "MANUAL_SYSTEM", system)
    set_inventory_value(ship_id, "MANUAL_LAST_PICK", system)
    _mb_repaint()

    #
    # If critical don't do it again
    #
    if critical:
        return

    t = to_object(get_weapons_selection(ship_id))
    if t is None:
        return
    if random.randint(1, 20) == 20:
        set_inventory_value(ship_id, "MANUAL_CRITICAL_HIT", t.id)
        comms_broadcast(client_id, f"Potential Critical hit {t.name}", "yellow")


def manual_beams_signature(id_or_obj):
    """A cheap value that changes when any bar would move.

    The panel is torn down and rebuilt on a 3 second ticker, which is fine for a panel
    and far too slow for a gauge. An `on change` on this repaints the moment the target
    actually takes damage, without shortening the ticker - which would keep destroying
    the panel under the gunner's hands.
    """
    if to_object(id_or_obj) is None:
        return ""
    return ",".join(str(manual_beams_health(id_or_obj, s)) for _n, s, _t in MB_SYSTEMS)
