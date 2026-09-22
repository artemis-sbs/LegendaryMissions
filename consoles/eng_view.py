"""Engineering's View tab - how the interior view draws rooms and systems.

These four settings used to belong to the EPad: a grid object spawned at
`icon_scale 0.01`, all but invisible, that existed only to carry them as comms
buttons. Reaching them meant finding that object on the interior view and drilling
two menus - three taps to a preference, and the object sat in the grid item list
beside the actual damage-control teams. The EPad is gone (sbs_utils
`internal_damage.py`); the settings are here, in a tab BESIDE the view they change,
so the engineer sees the effect as they make it.

Two independent two-state choices, one cycle button each - press to change:

    Rooms
    [        icons        >      ]
    Systems
    [      diamonds       >      ]

The style is per SHIP, in inventory, so both engineers on a bridge see one answer and
it survives a console switch. `icon_index` / `icon_scale` are written to each node's
blob exactly as the old `epad_*` labels wrote them - this is a new front end on
unchanged behavior, not a new look.

Prefixed `lm_eng_view_` because every top-level function here becomes a MAST global in
one flat, mission-wide namespace.
"""
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui import gui_row, gui_text
from sbs_utils.procedural.grid import grid_objects
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import to_object_list
from sbs_utils.procedural.roles import role

#: Inventory keys on the SHIP. Per ship, not per console: two engineers looking at one
#: interior must not see it drawn two ways.
ROOM_STYLE_KEY = "lm_eng_view_rooms"
SYSTEM_STYLE_KEY = "lm_eng_view_systems"

#: label -> (blob icon key, scale divisor). The divisors are the old epad_* values.
ROOM_STYLES = {"icons": ("icon_index", 2.0), "circles": ("simple_icon_index", 4.0)}
SYSTEM_STYLES = {"icons": ("icon_index", 2.0), "diamonds": ("simple_icon_index", 4.0)}

#: The icon each pool falls back to when a node declares none - 97 rooms, 12 systems,
#: straight from the epad_* labels.
_ROOM_FALLBACK = 97
_SYSTEM_FALLBACK = 12

ROOM_DEFAULT = "icons"
SYSTEM_DEFAULT = "icons"


def lm_eng_view_room_style(ship_id):
    """The room draw style this ship is using."""
    value = get_inventory_value(ship_id, ROOM_STYLE_KEY, ROOM_DEFAULT)
    return value if value in ROOM_STYLES else ROOM_DEFAULT


def lm_eng_view_system_style(ship_id):
    """The system draw style this ship is using."""
    value = get_inventory_value(ship_id, SYSTEM_STYLE_KEY, SYSTEM_DEFAULT)
    return value if value in SYSTEM_STYLES else SYSTEM_DEFAULT


def _apply(ship_id, role_name, styles, style, fallback):
    """Write one pool's icon and scale, the way the epad_* labels did."""
    key, divisor = styles[style]
    for node in to_object_list(grid_objects(ship_id) & role(role_name)):
        node.data_set.set("icon_index", get_inventory_value(node, key, fallback), 0)
        node.data_set.set("icon_scale",
                          get_inventory_value(node, "icon_scale", 1) / divisor, 0)


def lm_eng_view_apply_rooms(ship_id, style=None):
    """Draw this ship's rooms in `style` (or the one it already has). Returns it."""
    style = style if style in ROOM_STYLES else lm_eng_view_room_style(ship_id)
    set_inventory_value(ship_id, ROOM_STYLE_KEY, style)
    _apply(ship_id, "room", ROOM_STYLES, style, _ROOM_FALLBACK)
    return style


def lm_eng_view_apply_systems(ship_id, style=None):
    """Draw this ship's systems in `style` (or the one it already has). Returns it."""
    style = style if style in SYSTEM_STYLES else lm_eng_view_system_style(ship_id)
    set_inventory_value(ship_id, SYSTEM_STYLE_KEY, style)
    _apply(ship_id, "system", SYSTEM_STYLES, style, _SYSTEM_FALLBACK)
    return style


def lm_eng_view_signature(ship_id):
    """What an `on change` watches: the two styles in force."""
    if not ship_id:
        return ("", "")
    return (lm_eng_view_room_style(ship_id), lm_eng_view_system_style(ship_id))


def _eng_view_label(text):
    """The name above a setting's button.

    Prefixed, though it no longer has to be. This was `_label` and drew NOTHING on a
    real bridge for four rounds: `director/director_overlays.py` also defines
    `_label` - a string sanitizer - and loads later (story.json: consoles 12,
    director 40). Every .py of a mission was exec'd into one shared namespace,
    underscores included, and a function's `__globals__` IS that dict, so the call
    resolved at call time to whichever file loaded last. No error, wrong function.

    MAST now honors the underscore (MastGlobals.PrivateFileNamespace), so this name
    is safe as `_label` again. Left prefixed anyway: it costs nothing, and it reads
    as intentional to anyone who finds this comment.
    """
    gui_row("row-height: 1.2em;")
    gui_text(f"$text:{text};font:gui-1;color:#8B85A8;")


# --- the tab ------------------------------------------------------------------
def lm_eng_view_show(cid, left, top, width, height):
    """The View tab: one cycle button per pool.

    THE THIRD CONTROL THIS TAB HAS WORN, and the reasoning is worth keeping so it is
    not walked back:

    * `gui_radio` renders each option as `send_gui_checkbox` - a checkbox glyph per
      option. Wrong semantic for an exclusive choice, wrong affordance for a finger.
    * Chips - a horizontal single-select listbox - spend one touch target per option,
      which is a poor trade in a 230px column.

    A setting with two states is not a "which of these" question, it is a "change it"
    question, so it gets ONE target showing the current state, advancing on each press.

    **The chips were ALSO reported as not toggling, and that was not the chips.** It
    was `lm_eng_view_tick` returning TICK_REDRAW whenever a style moved - and a press
    moves a style, so every press rebuilt this tab underneath the control that had
    just been touched. The same defect then showed on the cycle button as "two
    buttons after a press, and then back to one", because a rebuild takes fresh tags
    from `page.get_tag()`. The tick no longer redraws at all; see it below. Recorded
    because the first two controls were each replaced partly on evidence that
    belonged to this bug, not to them.

    Chips remain right for the crew rail above: those ARE peers you pick between.
    """
    ship_id = _view_ship(cid)
    gui_row("row-height: 1.5em;")
    gui_text("$text:View;font:gui-3;overflow:ellipsis;")
    if not ship_id:
        gui_row()
        gui_text("$text:(no ship on this console);color:#888;")
        return

    _eng_view_label("Rooms")
    _style_button(ship_id, ROOM_STYLES, lm_eng_view_room_style(ship_id),
                  lm_eng_view_apply_rooms)
    _eng_view_label("Systems")
    _style_button(ship_id, SYSTEM_STYLES, lm_eng_view_system_style(ship_id),
                  lm_eng_view_apply_systems)

    gui_row()
    gui_text("$text:(how the interior view draws each pool);font:gui-1;color:#888;")


def _style_button(ship_id, styles, current, apply_fn):
    """One pool's control: a cycle button showing the style in force.

    The button is the VALUE only; `_label` above it says which setting it is. Keeping
    the name out of the button is what lets the control stay one word wide in a
    230px column.
    """
    from sbs_utils.procedural.gui.cycle_button import gui_cycle_button
    from sbs_utils.procedural.gui.message import gui_message_callback

    gui_row("row-height: 2.2em;")
    button = gui_cycle_button(list(styles), value=current,
                              style="justify:center;font:gui-2;")
    if button is None:
        return None

    # gui_message_callback, NOT on_press=. An on_press CALLABLE is called with
    # nothing unless it declares a REQUIRED parameter (see gui_button's docstring),
    # and the house idiom - a closure with bound defaults - declares none. So a
    # handler written `def _p(event=None, sender=None, ...)` gets sender=None and
    # silently applies nothing. This form is handed (event, sender) every time.
    #
    # `.state`, never `.value`: value is Button's props string. They are named apart
    # precisely so this cannot be got wrong.
    gui_message_callback(button, lambda event, sender, _s=ship_id, _f=apply_fn:
                         _f(_s, sender.state))
    return button


def _view_ship(cid):
    ctx = FrameContext.context
    if ctx is None or ctx.sbs is None:
        return None
    try:
        ship = ctx.sbs.get_ship_of_client(cid)
    except Exception:                                   # noqa: BLE001
        return None
    from sbs_utils.procedural.query import to_id
    return to_id(ship) or None


def lm_eng_view_tick(info_panel):
    """Repaint the tab when a style moved. THIS is how the buttons update.

    A cycle button inside a tabbed panel cannot repaint itself - a widget re-sent
    into a region out of band paints wrong, drawing the new label over the old one
    (see CycleButton.mark_value_dirty). Returning 2 here runs
    `TabbedPanel.represent` -> `present`, which brackets the rebuild with
    `send_gui_clear` / `send_gui_complete`, and that is the only update a region
    accepts. Every other control in this panel already updates this way, which is
    why they behave.

    Never 0 - that sends the panel back to its default tab once a second.
    """
    sig = lm_eng_view_signature(_view_ship(info_panel.client_id))
    if sig != getattr(info_panel, "_eng_sig_view", None):
        info_panel._eng_sig_view = sig
        return 2                                        # TICK_REDRAW
    return 1                                            # TICK_STAY
