"""Engineering's crew chips - what replaced the `grid_object_list` engine widget.

`grid_object_list` spent a 200px box on four rows (DC1, DC2, DC3, EPad) and left
roughly 60% of it empty, in the column where `grid_control` - the only surface on this
console that DOES anything - was squeezed to 33px per button. Measured, at every
resolution from 1280x720 to 2560x1440.

So the list moves to a chip row above the interior view, the pattern the comms filter
bar already uses (`comms_chips.py`), and the column it vacates goes to `grid_control`.
A chip also carries each team's live state, which the engine list could not: the widget
knew only a name.

The engine list and these chips are the same four objects, and the rail asks the hull
map for them exactly as the widget did. `grid_object_list` tabs on a grid object's
engine `type`, which is the FIRST role it was spawned with (`gridobject.py` `spawn`):
`crew` for the damage-control teams (`grid_brains.mast`); `tools` had one member, the
EPad, which was REMOVED 2026-09-22 (see `eng_view.py`). Everything else is spawned
`#`, the "do not list me" type. `tools` is still accepted here - a mod is free to add
one, and a rail of crew is what a stock hull now shows.

DO NOT reach for `role("damcons")` here, however natural it looks. The role set and
the hull map are separate bookkeeping and they DO disagree on a real bridge - that,
plus reading the Agent's cached name, is what shipped a rail of chips all reading
`unnamed`. Both are invisible on the mock, which spawns every node in-process.

NO MODULE-LEVEL CACHE ON PURPOSE. There are four chips and the reads are cheap, so
there is nothing to hold between missions and nothing to register with
`register_reset_state` - the second-run trap this console does not need to be in.

Prefixed `lm_eng_crew_` because every top-level function here becomes a MAST global in
one flat, mission-wide namespace.
"""
from sbs_utils.helpers import FrameContext, gui_text_escape
from sbs_utils.procedural.gui import gui_row, gui_text
from sbs_utils.procedural.inventory import get_inventory_value
from sbs_utils.procedural.internal_damage import (grid_get_max_hp,
                                                  GRID_TUNED_COLOR_DEFAULT)
from sbs_utils.procedural.query import (to_id, get_grid_selection,
                                        set_grid_selection)
from sbs_utils.procedural.routes import follow_route_select_grid
from sbs_utils.procedural.work_orders import (work_orders_for, work_order_kind,
                                              work_order_priority, KIND_REPAIR)

#: What a chip says a team is doing. Same words the Selected tab uses, so a chip and
#: the panel beside it cannot describe one team two ways.
_WORK_WORDS = {KIND_REPAIR: "fixing"}
_WORK_DEFAULT = "tuning"

_DIM = "#8B85A8"
_BAD = "Crimson"

#: What the ENGINE calls an object nothing ever named - a literal in
#: Artemis3-x64-release.exe. A placeholder, never something to print.
LM_ENG_CREW_NO_NAME = "unnamed"

#: One chip's width AND pitch, in em. It lives here, beside the template that has to
#: fit inside it, because the two are one decision: a horizontal listbox that
#: overflows draws a slider along its bottom and takes that height OUT of the item
#: area, so a rail that scrolls squeezes its own chips. Sized so a rail of four never
#: scrolls in the narrowest rail the console has (576px at 1280x720): 4.5em is 108px,
#: which fits five.
LM_ENG_CREW_CHIP_EM = 4.5


def lm_eng_crew_chip_style():
    """The rail listbox's style. A function, not a constant - only top-level defs
    become MAST globals, so a `.mast` file cannot read a module-level value.

    The background must stay SEE-THROUGH: the selection bar is drawn on the same
    layer, and an opaque background hides which chip is selected.
    """
    return f"col-width:{LM_ENG_CREW_CHIP_EM}em;background:#0E151D80;"


def lm_eng_crew_ship(client_id):
    """The ship this console is wired to, or None.

    Same lookup `eng_grid_panel` makes - the console's OWN ship, not the viewscreen's
    home ship, because the grid selection these chips write lives on that ship's blob.
    """
    ctx = FrameContext.context
    if ctx is None or ctx.sbs is None:
        return None
    try:
        ship = ctx.sbs.get_ship_of_client(client_id)
    except Exception:                                   # noqa: BLE001
        return None
    # to_id, not `ship.id`: the engine hands back a Pybind space object, whose id is
    # `unique_ID`. Reading `.id` came back None and the rail was simply always empty.
    return to_id(ship) or None


#: The two engine `type` values `grid_object_list` tabbed on, in rail order. A grid
#: object's type is the FIRST role it was spawned with (`gridobject.py` `spawn`):
#: `crew` for the damage-control teams; `tools` is kept for a mod that adds one (its
#: only stock member, the EPad, is gone). Everything the console must not list is
#: spawned `#`, the do-not-list type.
LM_ENG_CREW_TYPES = ("crew", "tools")


def lm_eng_crew_rows(client_id):
    """[(id, name, kind)] for this ship's crew and tools, straight off the hull map.

    WALKS THE HULL MAP AND READS THE ENGINE'S OWN `type` AND `name`, because that is
    literally what `grid_object_list` did, and this rail exists to replace it.

    The first version filtered `grid_objects(ship) & role("damcons")` and took the
    name from the Agent. Both halves were wrong on a real bridge and right on the
    mock, so the tests could not see it: the role set and the hull map are separate
    bookkeeping, and `GridObject.name` is a python-side CACHE only filled when THIS
    process called `set_name`. Every chip came up reading `unnamed`, which is the
    ENGINE's own placeholder for an object nothing named. One pass over the hull map
    gets the right objects and their real names from the same source.
    """
    ship_id = lm_eng_crew_ship(client_id)
    if not ship_id:
        return []
    ctx = FrameContext.context
    hull_map = ctx.sbs.get_hull_map(ship_id) if ctx is not None and ctx.sbs else None
    if hull_map is None:
        return []
    found = {kind: [] for kind in LM_ENG_CREW_TYPES}
    for i in range(hull_map.get_grid_object_count()):
        go = hull_map.get_grid_object_by_index(i)
        if go is None:
            continue
        kind = str(getattr(go, "type", "") or "").strip().lower()
        if kind not in found:
            continue
        found[kind].append((go.unique_ID, _display_name(go), kind))
    rows = []
    for kind in LM_ENG_CREW_TYPES:
        rows.extend(sorted(found[kind], key=lambda r: r[1]))
    return rows


def _display_name(go):
    """What to print on a chip for one grid object.

    `unnamed` is the engine's placeholder, not a name - verified as a literal in
    Artemis3-x64-release.exe. LM sets a team's tag to its name, so the tag is the
    better answer when the name is missing, and a marker is better than a blank chip:
    a chip with no text is an invisible button.
    """
    name = str(getattr(go, "name", "") or "").strip()
    if name and name.lower() != LM_ENG_CREW_NO_NAME:
        return name
    tag = str(getattr(go, "tag", "") or "").strip()
    return tag or "?"


def lm_eng_crew_items(client_id):
    """The chips' items - grid object ids, teams first then tools."""
    return [node_id for node_id, _name, _kind in lm_eng_crew_rows(client_id)]


def lm_eng_crew_name(client_id, node_id):
    """One node's chip label, from the same hull-map pass the rail was built from."""
    return _row_for(client_id, node_id)[0]


def _row_for(client_id, node_id):
    """(name, kind) for one node, or ("?", "") if it is not on the rail."""
    for other_id, name, kind in lm_eng_crew_rows(client_id):
        if other_id == node_id:
            return name, kind
    return "?", ""


def lm_eng_crew_state(node_id, client_id=None):
    """(label, status, name_color, status_color) for one chip.

    TWO colors, because the chip says two things. The NAME is drawn in the team's own
    color - the same color its figure is drawn in on the interior view, so a chip and
    the thing it selects are recognisably one team without reading either. The STATUS
    line carries the state: crimson when the team is hurt, the tuned color while it is
    working, dim when idle.

    `client_id` defaults to the frame's, which is what the item template has.
    """
    if client_id is None:
        client_id = FrameContext.client_id
    # Crew vs tools is the ENGINE's `type`, the same thing that put the node on the
    # rail - not `has_role(node_id, "damcons")`. Asking the role set here would let
    # a node the hull map calls crew be described as a tool, which is exactly the
    # kind of split-bookkeeping disagreement that made the rail read `unnamed`.
    name, kind = _row_for(client_id, node_id)
    if kind != "crew":
        return name, "tools", _DIM, _DIM

    # The team's own color, the same read eng_grid_panel's header glyph makes, so the
    # chip, the glyph and the figure on the map cannot disagree.
    team_color = get_inventory_value(node_id, "color", "white") or "white"

    max_hp = grid_get_max_hp()
    hp = get_inventory_value(node_id, "HP", max_hp)
    hurt = hp < max_hp

    # work_orders_for, not linked_to: it purges as it reads, so a job somebody else
    # already finished stops being counted instead of sitting on the chip forever.
    orders = list(work_orders_for(node_id))
    if not orders:
        return name, "idle", team_color, (_BAD if hurt else _DIM)
    top = max(orders, key=work_order_priority)
    word = _WORK_WORDS.get(work_order_kind(top) or KIND_REPAIR, _WORK_DEFAULT)
    if len(orders) > 1:
        word = f"{word} +{len(orders) - 1}"
    return name, word, team_color, (_BAD if hurt else GRID_TUNED_COLOR_DEFAULT)


def lm_eng_crew_template(item):
    """One chip: the team's name over what it is doing.

    Two rows rather than comms's one - a name alone is what the engine list already
    gave, and the status is the reason to replace it. The chip's WIDTH is the
    listbox's `col-width`; these rows just fill its height.
    """
    label, status, name_color, status_color = lm_eng_crew_state(item)
    # 1.2 + 0.9em = 51px of the rail's 56px row. A horizontal listbox that overflows
    # draws a slider along its bottom and takes that height OUT of the item area, so
    # a template sized to the full row has nowhere to put it - the chips are kept
    # narrow enough (layout_widgets) that a rail of four never overflows.
    gui_row("row-height: 1.2em;")
    gui_text(f"$text:{gui_text_escape(label)};justify:center;font:gui-2;"
             f"color:{name_color};overflow:ellipsis;")
    gui_row("row-height: 0.9em;")
    gui_text(f"$text:{gui_text_escape(status)};justify:center;font:gui-1;"
             f"color:{status_color};overflow:ellipsis;")


def lm_eng_crew_selected(client_id):
    """The chip to show selected: the ship's grid selection, when it is one of ours.

    Selecting a ROOM on the interior view is not one of these, so the rail correctly
    shows nothing selected rather than leaving the last team lit.
    """
    ship_id = lm_eng_crew_ship(client_id)
    if not ship_id:
        return []
    sel = get_grid_selection(ship_id)
    return [sel] if sel and sel in lm_eng_crew_items(client_id) else []


def lm_eng_chip_one(picked):
    """The one item a selection means, whichever shape the listbox answers in.

    Public and shared: every single-select chip rail on this console goes through it
    (the crew rail here, the View tab's two rails in eng_view.py).

    `LayoutListbox.get_selected` returns a LIST when the box is `multi`, and the bare
    item - or None - when it is single-select, which this rail is. Indexing that
    answer raised `'int' object is not subscriptable` on a real bridge the first time
    anyone tapped a chip, and the unit test missed it because the stand-in listbox
    answered in the friendlier shape. Accept both and the rail cannot care again.
    """
    if picked is None:
        return None
    if isinstance(picked, (list, tuple, set)):
        picked = list(picked)
        return picked[0] if picked else None
    return picked or None


def lm_eng_crew_pick(client_id, lb):
    """A chip was tapped: make it the ship's grid selection and fire the route.

    Exactly what tapping a row of `grid_object_list` did - the selection lives on the
    HOST SHIP's blob, so every engineering console on the bridge follows.
    """
    node_id = lm_eng_chip_one(lb.get_selected())
    ship_id = lm_eng_crew_ship(client_id)
    if not ship_id or not node_id:
        return None
    # ALREADY SELECTED IS NOT A TAP. `lm_eng_crew_refresh` writes `lb.selected` to
    # follow the ship, which moves `get_selected()`, which fires the same
    # `on change` a real tap does - and refresh runs whenever ANY team's status
    # moves. Re-firing the route from there re-enters the //comms/grid tree and
    # sends grid_control back to its root, so an engineer reading a submenu would
    # be bounced out of it every time a team picked up a job. Nothing would look
    # broken; the menu would just never stay put.
    if get_grid_selection(ship_id) == node_id:
        return node_id
    set_grid_selection(ship_id, node_id)
    follow_route_select_grid(ship_id, node_id)
    return node_id


def lm_eng_crew_revision(client_id):
    """What an `on change` watches: which chips there are and what each one says.

    Redraws when a team starts or finishes a job or takes a hit - not every tick.
    """
    return tuple((i,) + lm_eng_crew_state(i) for i in lm_eng_crew_items(client_id))


def lm_eng_crew_refresh(client_id, lb):
    """State moved: redraw the chips' own rows, never the page."""
    lb.items = lm_eng_crew_items(client_id)
    lb.selected = lm_eng_crew_selected(client_id)
    lb.mark_visual_dirty()
