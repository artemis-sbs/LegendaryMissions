"""AMD-authored recipe registry for the Fabricator (LegendaryMissions).

Recipes come from two sources, both surfaced through this registry:
  * AMD recipe files (primary, mission-authorable) -> fabrication_load_recipes_amd()
  * item-def metadata (craft_cost/craft_time on item/... prefabs) -> back-compat; the
    fabrication tab still lists those directly, and a mission can also mirror them in
    here via fabrication_add_recipe if it wants multi-input costs.

Mirrors the amd_science / amd_quest layering: a data_parser (amd_recipe_data) + a loader
(fabrication_load_recipes_amd) that reads each heading's fence data + body into the registry.

AMD form (one heading per recipe):

    # [Bio Beacon](recipe_beacon_bio)
    ---
    Output: Beacon
    Inputs: bio_sample x1, salvage x5
    Time: 30
    Build at: engineering
    Program: kind=bio
    ---
    A distress-beacon hull rewired to broadcast to xeno-organisms.

Fields: Output (produced cargo/torpedo key), Inputs ("key xN, key xM" -> {key:count}),
Time (build seconds), Build at (console/station gate, optional), Program (k=v,k=v -> dict of
extra data stamped on the output, e.g. a beacon's kind). The body is the description.
"""
from sbs_utils.procedural.amd import amd_parse_facts
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.procedural.gui import gui_row, gui_text

# key -> {key, name, output, inputs{key:count}, time, build_at, program{}, desc}
_RECIPES = {}


def amd_recipe_data(text):
    """data_parser for a recipe .amd file (parses one heading's --- fence into a dict)."""
    return amd_parse_facts(text)


def _parse_inputs(s):
    """'bio_sample x1, salvage x5' -> {'bio_sample': 1, 'salvage': 5}. Bare key -> count 1."""
    out = {}
    for part in str(s or "").split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split()
        key = bits[0]
        count = 1
        if len(bits) > 1:
            c = bits[-1].lstrip("xX")
            if c.isdigit():
                count = int(c)
        out[key] = count
    return out


def _parse_program(s):
    """'kind=bio, mode=attract' -> {'kind': 'bio', 'mode': 'attract'}."""
    out = {}
    for part in str(s or "").split(","):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _parse_properties(s):
    """Parse a recipe's Properties into build-time option specs. Grammar (';'-separated):
        name:type=opt1,opt2,...     e.g. 'monster:list=shark,dragon,any; mode:radio=attract,repel'
    type in {list (drop-down), radio, toggle, int, text}. Default value = first option. These
    render as a property grid (like a map's Properties) in the Fabricate detail panel."""
    out = []
    for part in str(s or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        left, right = part.split("=", 1)
        if ":" not in left:
            continue
        name, typ = left.split(":", 1)
        opts = [o.strip() for o in right.split(",") if o.strip()]
        out.append({"name": name.strip(), "type": typ.strip().lower(),
                    "options": opts, "default": opts[0] if opts else ""})
    return out


def _prop_control_expr(prop):
    """A property spec -> the gui control-expression string the property grid evaluates
    (mirrors how a map's Properties YAML holds 'gui_drop_down(...)' strings). Each binds to a
    shared var named for the property, so Build can read it back with get_shared_variable."""
    name = prop["name"]
    typ = prop["type"]
    opts = ", ".join(prop["options"])
    if typ == "radio":
        return f'gui_radio("{opts}", var="{name}")'
    if typ == "toggle":
        return 'gui_checkbox("$text: {' + name + '};", var="' + name + '")'
    if typ in ("int", "text"):
        return f'gui_input("desc: {typ};", var="{name}")'
    # default: a list -> drop-down. No "$text:{var}" (that interpolation crashes before the
    # var is seeded) -- the drop-down shows its own bound selection; its open list inherits the
    # control height.
    return f'gui_drop_down("list: {opts}", var="{name}")'


def recipe_property_grid(recipe):
    """A recipe -> the {section: {label: control_expr}} dict for gui_properties_set, or {} when
    the recipe declares no Properties."""
    props = recipe.get("properties") or []
    if not props:
        return {}
    inner = {}
    for p in props:
        inner[p["name"].capitalize()] = _prop_control_expr(p)
    return {"Program": inner}


def recipe_property_names(recipe):
    """The property (shared-var) names a recipe declares, in order."""
    return [p["name"] for p in (recipe.get("properties") or [])]


def recipe_property_defaults(recipe):
    """{name: default} for a recipe's properties (used to seed the shared vars)."""
    return {p["name"]: p["default"] for p in (recipe.get("properties") or [])}


def fabrication_add_recipe(key, output, inputs=None, time=30, build_at="", program=None, name=None, desc="", properties=None):
    """Register (or replace) a recipe by key. Returns the key."""
    _RECIPES[key] = {
        "key": key, "name": name or key, "output": output,
        "inputs": inputs or {}, "time": int(time or 30),
        "build_at": str(build_at or ""), "program": program or {},
        "properties": properties or [], "desc": desc or "",
    }
    return key


def fabrication_recipes():
    """Every registered recipe (list of dicts)."""
    return list(_RECIPES.values())


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
    data_parser=amd_recipe_data, or a mission's amd_mission_data + amd_section). A heading is
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
            properties=_parse_properties(data.get("properties")),
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
    their program (kind/monster/mode) and a cidx into beacon_built; items/materials carry a key.
    So the Cargo tab isn't beacon-only -- it lists everything the ship is carrying."""
    out = []
    # built beacons (one row each, so a single one can be delivered / ejected)
    built = get_inventory_value(ship_id, "beacon_built", []) or []
    idx = 0
    for b in built:
        out.append({
            "ckind": "beacon", "cidx": idx, "count": 1, "cid": f"b{idx}",
            "name": f"Beacon: {b.get('mode', '?')} / {b.get('monster', '?')}",
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
