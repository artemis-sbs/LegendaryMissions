"""AMD-authored recipe registry for the Fabricator (LegendaryMissions).

Recipes come from two sources, both surfaced through this registry:
  * AMD recipe files (primary, mission-authorable) -> fabrication_load_recipes_amd()
  * item-def metadata (craft_cost/craft_time on item/... prefabs) -> back-compat; the
    fabrication tab still lists those directly, and a mission can also mirror them in
    here via fabrication_add_recipe if it wants multi-input costs.

The fence is read by the SHARED AMD reader (no bespoke parser); this module is just the
loader (fabrication_load_recipes_amd) that reads each heading's fence data + body into
the registry.

AMD form (one heading per recipe):

    # [Bio Beacon](recipe_beacon_bio)
    ---
    Output: Beacon
    Inputs: bio_sample x1, salvage x5
    Time: 30
    Build at: engineering
    Program: kind=bio
    Properties:              # map-format: {label: 'gui_control_expr'}, fed to gui_properties_set
      Monster: 'gui_drop_down("list: shark, dragon, any", var="monster")'
      Mode: 'gui_drop_down("list: attract, repel", var="mode")'
    Defaults:                # {var: value} seed values (like a map's Defaults block)
      monster: shark
      mode: attract
    ---
    A distress-beacon hull rewired to broadcast to xeno-organisms.

Fields: Output (produced cargo/torpedo key), Inputs ("key xN, key xM" -> {key:count}),
Time (build seconds), Build at (console/station gate, optional), Program (k=v,k=v -> dict of
extra data stamped on the output, e.g. a beacon's kind). Optional Properties + Defaults blocks
use the SAME format a map's Properties panel uses (a {label: 'gui_control_expr'} dict + a
{var: value} defaults dict), rendered by gui_property_list_box / gui_properties_set. The body
is the description.
"""
import re
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.gui import gui_row, gui_text

# key -> {key, name, output, inputs{key:count}, time, build_at, program{}, properties{},
#         defaults{}, desc}
_RECIPES = {}


# `amd_recipe_data` used to live here: a data_parser that called load_yaml_string
# directly, because the friendly reader could not do the nested Properties/Defaults
# blocks a recipe needs. That made recipes a THIRD fence dialect - the game read a
# nested dict while amd_core (the linter and the Inspector) read `properties: ''`
# plus two keys that collided with Defaults. The shared reader does block nesting
# natively now, and the mission never passed the parser anyway, so it is gone.
#
# `_parse_inputs` / `_parse_program` went with it: they are the `counted` and `kv`
# value types in sbs_utils.procedural.amd, declared rather than hand-rolled.
from sbs_utils.procedural.amd import amd_counted as _parse_inputs, amd_kv as _parse_program


def _declare_recipe_vocabulary():
    """Tell the shared registry what a recipe fence looks like, so the linter checks
    these values and the VS Code Inspector renders a real widget for each - the same
    treatment core fields get. Raises on a clash with a core field."""
    from sbs_utils.procedural.amd_schema import (
        amd_register_fields, amd_register_section_names,
        text, integer, counted, kv, enum)
    amd_register_fields("recipe", {
        "output": text(hint="the cargo/torpedo key this produces"),
        "inputs": counted(hint="salvage x5, bio_sample x1"),
        "time": integer(hint="build seconds"),
        "build at": enum("engineering", "science", "weapons", "comms", "helm", open=True),
        # Program keys can end up bound as MAST variables (the Properties grid binds
        # var= names through set_variable), so keep them off MAST's globals table -
        # `beacon_range`, never `range`. See the ns-amd-var-shadows-builtin lint rule.
        "program": kv(hint="kind=bio, beacon_range=medium"),
        # Blocks, not scalars: a {label: 'gui_control_expr'} property grid and a
        # {var: value} seed map. Their INNER names belong to the recipe, so they are
        # declared as text and the linter does not look inside them.
        "properties": text(hint="a nested block of gui control expressions"),
        "defaults": text(hint="a nested block of {var: value} seeds"),
    }, domain="fabrication")
    amd_register_section_names(("recipes",), "recipe", domain="fabrication")


try:
    _declare_recipe_vocabulary()
except Exception as _e:      # a vocabulary clash must not stop the mission loading
    print(f"recipes: vocabulary not declared - {_e}")


def recipe_property_grid(recipe):
    """The recipe's Properties -- a map-style {section/label: 'gui_control_expr'} dict, passed
    straight to gui_properties_set (no bespoke generation). {} when the recipe declares none."""
    return recipe.get("properties") or {}


_VAR_RE = re.compile(r'var\s*=\s*"([^"]+)"')


def recipe_property_names(recipe):
    """The control var names a recipe's Properties bind, in order -- walk the dict tree and pull
    every var="..." out of the control strings (like maps._map_property_vars), so Build can read
    each back with get_variable."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            for m in _VAR_RE.finditer(node):
                if m.group(1) not in found:
                    found.append(m.group(1))

    walk(recipe.get("properties") or {})
    return found


def recipe_property_defaults(recipe):
    """{var: default} from the recipe's Defaults block (seeds the property vars before render)."""
    return recipe.get("defaults") or {}


def fabrication_add_recipe(key, output, inputs=None, time=30, build_at="", program=None, name=None, desc="", properties=None, defaults=None):
    """Register (or replace) a recipe by key. Returns the key. `properties` is a map-style
    Properties dict ({label: 'gui_control_expr'}); `defaults` a {var: value} seed dict."""
    _RECIPES[key] = {
        "key": key, "name": name or key, "output": output,
        "inputs": inputs or {}, "time": int(time or 30),
        "build_at": str(build_at or ""), "program": program or {},
        "properties": properties or {}, "defaults": defaults or {}, "desc": desc or "",
    }
    return key


def fabrication_recipes():
    """Every recipe the Fabricate panel should list - AMD recipes AND item craftables.

    ONE PANEL, TWO SOURCES. There used to be two: this registry behind `//gui/app/fabricate`,
    and a second screen behind `//gui/app/fabrication` that read item-def `craft_cost`
    metadata directly. Both appeared on the ePADD, so a mission got two Fabrication tiles -
    and in LegendaryMissions and the TNG missions the second one was EMPTY, because nothing
    there declares craft_cost. StormsBeacon does, which is why the path cannot simply be
    deleted.

    So the item craftables are folded in here instead, and the second screen is no longer
    offered. `craft_cost: 8` says exactly what `Inputs: salvage x8` says, which is what
    makes this a translation rather than a reinterpretation.

    MERGED AT READ TIME, not at load. Items are registered by a MISSION's top level, which
    may run after this addon's, so a one-shot import at load would see nothing. An AMD
    recipe of the same key wins - a mission that has written a real recipe has said more
    about it than its item def can.
    """
    out = list(_RECIPES.values())
    have = {r.get("key") for r in out}
    for extra in _item_craftables():
        if extra["key"] not in have:
            out.append(extra)
    return out


def _item_craftables():
    """Item defs carrying `craft_cost`, as recipes. Empty when the item system is absent."""
    try:
        from sbs_utils.procedural.items import items_get_list
    except Exception:                                   # noqa: BLE001
        return []
    out = []
    try:
        labels = list(items_get_list() or [])
    except Exception:                                   # noqa: BLE001
        # No story loaded (a unit test, or a panel asking before the labels exist), or
        # something that is not a list came back. `list()` is INSIDE the guard for the
        # second case: the iteration used to sit outside it, so a non-iterable answer
        # raised past this and took the panel down with it.
        return []
    for lbl in labels:
        try:
            key = lbl.get_inventory_value("key")
            cost = int(lbl.get_inventory_value("craft_cost", 0) or 0)
        except Exception:                               # noqa: BLE001
            continue
        if not key or cost <= 0:
            continue
        out.append({
            "key": key,
            "name": lbl.get_inventory_value("display_text", key),
            # The item IS the output - that was the whole shape of the old screen:
            # "THE RECIPES ARE THE ITEM DEFS".
            "output": key,
            "inputs": {"salvage": cost},
            "time": int(lbl.get_inventory_value("craft_time", 30) or 30),
            "build_at": "", "program": {}, "properties": {}, "defaults": {},
            "desc": lbl.get_inventory_value("description", "") or "",
        })
    return out


def fabrication_get_recipe(key):
    """One recipe dict by key, or None."""
    return _RECIPES.get(key)


def _iter_nodes(node):
    """Depth-first walk of every heading node under `node` (recipes are ## children of the
    # root, so we descend the whole tree rather than only the top level)."""
    for n in (node.get("children") or []):
        yield n
        for c in _iter_nodes(n):
            yield c


def fabrication_load_recipes_amd(doc):
    """Register every recipe heading in a parsed AMD doc (from document_get_amd_file with
    the shared reader, or a mission's amd_mission_data + amd_section). A heading is
    a recipe if its fence has an Output; the root/section headings without one are skipped."""
    if doc is None:
        return
    for n in _iter_nodes(doc):
        data = {str(k).lower(): v for k, v in (n.get("data") or {}).items()}
        key = n.get("key") or data.get("key")
        output = data.get("output")
        if not key or not output:
            continue
        fabrication_add_recipe(
            key=key, output=output,
            inputs=_parse_inputs(data.get("inputs")),
            time=data.get("time", 30),
            build_at=(data.get("build at") or data.get("build_at") or ""),
            program=_parse_program(data.get("program")),
            properties=data.get("properties") or {},
            defaults=data.get("defaults") or {},
            name=n.get("display_text") or data.get("name") or key,
            desc=n.get("description") or "",
        )


def fabrication_recipe_affordable(ship_id, key):
    """True if the ship holds every input for recipe `key`."""
    r = _RECIPES.get(key)
    if r is None:
        return False
    for ik, need in r["inputs"].items():
        if (get_inventory_value(ship_id, ik, 0) or 0) < need:
            return False
    return True


def fabrication_recipe_consume(ship_id, key):
    """Spend a recipe's inputs if the ship can afford them. Returns True on success, else
    False (nothing spent)."""
    if not fabrication_recipe_affordable(ship_id, key):
        return False
    r = _RECIPES[key]
    for ik, need in r["inputs"].items():
        set_inventory_value(ship_id, ik, (get_inventory_value(ship_id, ik, 0) or 0) - need)
    return True


def recipe_inputs_text(recipe):
    """'bio_sample x1, salvage x5' summary of a recipe's inputs (for a detail panel)."""
    return ", ".join(f"{k} x{v}" for k, v in (recipe.get("inputs") or {}).items())


# --- list-box templates (item_gui.mast style: item_template=row, title_template=title) ---
def recipe_row(item):
    """One recipe row in the Fabricate list box."""
    gui_row("row-height: 1.1em; padding:8px;")
    gui_text(f"$text:{item.get('name', '?')};justify:left;")


def recipe_title():
    gui_row("row-height: 1.1em; padding:8px; background:#1578;")
    gui_text("$text:Recipes;justify:center;")


def cargo_list(ship_id):
    """A general cargo manifest for the Cargo tab: built beacons + held registry items + held
    non-beacon recipe outputs (materials). Each entry: {ckind, name, count, ...}. Beacons carry
    their program (kind/monster/mode/beacon_range) and a cidx into beacon_built; items/materials
    carry a key. Deliver and Eject act on the cidx, not on the program values -- two Sensor
    Beacons differing only in range would otherwise be indistinguishable to a match.
    So the Cargo tab isn't beacon-only -- it lists everything the ship is carrying."""
    out = []
    # built beacons (one row each, so a single one can be delivered / ejected)
    built = get_inventory_value(ship_id, "beacon_built", []) or []
    idx = 0
    for b in built:
        # A Sensor Beacon carries no monster/mode; name it by its range rather than "? / ?".
        b_name = fabrication_beacon_name(b)
        out.append({
            "ckind": "beacon", "cidx": idx, "count": 1, "cid": f"b{idx}",
            "name": b_name,
            "kind": b.get("kind"), "monster": b.get("monster"), "mode": b.get("mode"),
        })
        idx += 1
    seen = set()
    # held tangible items from the items registry
    try:
        from sbs_utils.procedural.items import items_get_list
        for lbl in items_get_list():
            k = lbl.get_inventory_value("key")
            if not k or k in seen:
                continue
            n = get_inventory_value(ship_id, k, 0) or 0
            if n > 0:
                out.append({"ckind": "item", "key": k, "count": n, "cid": f"i{k}",
                            "name": lbl.get_inventory_value("display_text", k)})
                seen.add(k)
    except Exception:
        pass
    # held non-beacon recipe outputs (fabricated materials)
    for r in _RECIPES.values():
        ok = r.get("output")
        if not ok or ok == "Beacon" or ok in seen:
            continue
        n = get_inventory_value(ship_id, ok, 0) or 0
        if n > 0:
            out.append({"ckind": "material", "key": ok, "count": n, "cid": f"m{ok}", "name": ok})
            seen.add(ok)
    return out


def cargo_row(item):
    """One cargo row in the Cargo list box (name + count for stacks)."""
    gui_row("row-height: 1.1em; padding:8px;")
    cnt = item.get("count", 1)
    suffix = f"  x{cnt}" if cnt and cnt > 1 else ""
    gui_text(f"$text:{item.get('name', '?')}{suffix};justify:left;")


def cargo_title():
    gui_row("row-height: 1.1em; padding:8px; background:#1578;")
    gui_text("$text:Cargo;justify:center;")


# --- "what just came out of the fabricator" ---------------------------------
#
# The Fabricate panel's only feedback used to be the countdown, and even that was
# unreachable (the page never repainted after Build). When a build FINISHED the panel
# said nothing at all - the sole indication was an overlay_toast, which is a log line
# now: it lands in the ambient strip and the Log tab, i.e. everywhere except the panel
# the engineer is looking at. So a build looked like nothing happened, twice over.
#
# A toast needs a durable twin. This is the twin: the completion routes stamp what came
# out, the panel shows it until the next build starts, and it survives a repaint, a tab
# switch and a reconnect because it lives on the ship.

def fabrication_last_built_set(ship_id, name):
    """Record what the fabricator just produced (None clears it)."""
    if name is None:
        set_inventory_value(ship_id, "fab_last_built", None)
        return
    # Braces out. MAST re-runs every assigned STRING through f-string formatting, so a
    # `{` in a name the panel assigns would be a SyntaxError reported against the
    # panel's line rather than against whatever produced the name.
    set_inventory_value(ship_id, "fab_last_built",
                        str(name).replace("{", "(").replace("}", ")"))


def fabrication_last_built(ship_id):
    """What the fabricator last produced, or "" if nothing since the last build."""
    return get_inventory_value(ship_id, "fab_last_built", None) or ""


def fabrication_beacon_name(entry):
    """Display name for a built beacon - the same naming the Cargo tab uses.

    Shared so the "Built: X" line and the cargo row cannot drift apart; they are the
    two halves of one claim ("it is done, and it is over there").
    """
    if entry.get("kind") == "sensor":
        return ("Sensor Beacon (Long Range)" if entry.get("beacon_range") == "long"
                else "Sensor Beacon")
    return f"Beacon: {entry.get('mode', '?')} / {entry.get('monster', '?')}"
