"""Overlay text templates, and the presets that fill them in.

WHY TEMPLATES AT ALL. The generated rundowns make one item per ship - "Player ships" is four
items on a four-ship bridge - so there is nowhere to type "Artemis". A template resolved against
each item's OWN subject is the only way one rundown item can name whatever it is pointed at.

WHY `<<token>>` AND NOT `{token}`. This is not a style choice; braces are fatal on this path:

  * MAST re-runs any string containing `{` through f-string formatting at ASSIGNMENT
    (mast/core_nodes/assign.py), and `gui_text` does it AGAIN at render
    (procedural/gui/text.py). A failed format does not raise - it silently returns "" - so a
    lower third with a bad token would not error, it would just VANISH.
  * A backtick is deleted twice over: by `gui_text_escape` on the way out, and by
    `TextInput._sanitize` on the way in, so the operator cannot even type one.
  * `$` is the style-key sigil (`_STYLE_KEY_RE`), and leads a per-line style in a text area.
  * `[` is a link reference in `gui_text_area` markdown, which eats the rest of the line.

`<` and `>` appear in NO parser on the path - typed input, dict, `overlay_kind`, `send_gui_text`
- and doubling them means a stray `<` in "<5%" can never match. They also pass through the
`_plain()` brace-stripping the addon already does, so none of that had to change.

Every public name is prefixed `director_`: an addon's `def`s become MAST globals in one flat
mission-wide namespace, last loaded wins, silently. A leading underscore is private.
"""
import re

# <<token>> or <<token|fallback when it will not resolve>>.
_TOKEN = re.compile(r"<<\s*(?P<tok>[A-Za-z_][A-Za-z_0-9]*)\s*(?:\|(?P<alt>[^>]*?))?\s*>>")

# What each overlay kind's fields are called, so a preset knows what it is filling.
DIRECTOR_OVERLAY_FIELDS = {
    "lower_third": ("name", "line"),
    "hero": ("title", "subtitle"),
    "banner": ("text",),
    "letterbox": ("line",),
}

# kind -> ((key, label, {field: template}), ...). Built-ins; user saves land beside these.
_BUILTIN = {
    "lower_third": (
        ("ship_id", "Ship ID", {"name": "<<name>>", "line": "<<class>>"}),
        ("ship_side", "Ship and side", {"name": "<<name>>", "line": "<<class|ship>> - <<side>>"}),
        ("condition", "Condition", {"name": "<<name>>", "line": "hull <<hull|--%>>"}),
        ("contact", "Contact", {"name": "<<comms_id>>", "line": "<<role|contact>>"}),
    ),
    "hero": (
        ("ship_id", "Ship ID", {"title": "<<name>>", "subtitle": "<<class>>"}),
        ("contact", "Contact", {"title": "<<comms_id>>", "subtitle": "<<role|contact>>"}),
    ),
    "banner": (
        ("ship_id", "Ship ID", {"text": "<<name>> - <<class|ship>>"}),
        ("condition", "Condition", {"text": "<<name>>  hull <<hull|--%>>  shields <<shields|--%>>"}),
    ),
    "letterbox": (
        ("ship_id", "Ship ID", {"line": "<<name>>"}),
        ("ship_side", "Ship and side", {"line": "<<name>> - <<side>>"}),
    ),
}

# kind -> {key: {"label", "fields"}} for what a person saved. PER MISSION: cosmos_dev reuses one
# interpreter across run_next_mission, so a module dict nothing clears is the classic "works on
# run 1, broken on run 2". Cleared from the addon top level.
_PRESETS = {}


def director_overlay_presets_reset():
    """Drop every saved preset. Called from the addon top level, per mission."""
    _PRESETS.clear()


def _plain(text):
    """Display text with no braces and no backticks. `<` and `>` deliberately survive."""
    return str(text).replace("{", "(").replace("}", ")").replace("`", "'").strip()


def _label(text):
    """A preset NAME safe to sit in a `list:` property.

    A preset name reaches the wire as one entry of `list: a,b,c;`, so a comma in it silently
    becomes two entries and a semicolon ends the property early - and the picker then holds a
    name that matches no preset. The overlay TEXT keeps its punctuation; only the name is
    flattened, because only the name is spliced into a style string.
    """
    out = _plain(text)
    for char in (",", ";", ":"):
        out = out.replace(char, " ")
    return " ".join(out.split())


# --- token resolution ---------------------------------------------------------------------

def _obj(subject_id):
    from sbs_utils.procedural.query import to_object
    return to_object(subject_id) if subject_id else None


def _tok_name(obj, sid):
    return getattr(obj, "name", None) or ""


def _tok_class(obj, sid):
    """The hull's display name - "Light Cruiser" for `tsn_light_cruiser`.

    The per-object `hull_name` blob value wins: that is the override a science scan shows, and a
    mission that bothered to set it meant it. shipData is the fallback everything else uses.
    """
    try:
        override = obj.data_set.get("hull_name", 0)
        if override:
            return str(override)
    except Exception:
        pass
    try:
        from sbs_utils.procedural.ship_data import get_ship_name
        return get_ship_name(getattr(obj, "ship_data_key", None)) or ""
    except Exception:
        return ""


def _tok_side(obj, sid):
    return getattr(obj, "side_display", None) or getattr(obj, "side", None) or ""


def _tok_role(obj, sid):
    """The first MEANINGFUL role - raider, station, monster.

    The engine's own bookkeeping roles are `__player__`, `__npc__`, `__terrain__` and friends;
    showing one of those on air would be worse than showing nothing.
    """
    from sbs_utils.procedural.roles import get_role_list
    try:
        for role in (get_role_list(sid) or []):
            r = str(role)
            if r.startswith("__") or r == "#":
                continue
            return r
    except Exception:
        pass
    return ""


def _tok_race(obj, sid):
    race = getattr(obj, "race", None) or ""
    # `race` falls back to the literal "no origin" rather than to empty, which reads as a bug on
    # air. Treat it as unresolved so the |fallback can do its job.
    return "" if race == "no origin" else race


def _tok_comms_id(obj, sid):
    return getattr(obj, "comms_id", None) or getattr(obj, "name", None) or ""


def _tok_hull(obj, sid):
    from sbs_utils.procedural.gui.viewscreen_pages import viewscreen_hull_percent
    try:
        pct = viewscreen_hull_percent(sid)
    except Exception:
        return ""
    return "" if pct is None else str(int(pct)) + "%"


def _pct(cur, mx):
    try:
        cur = float(cur or 0)
        mx = float(mx or 0)
    except (TypeError, ValueError):
        return None
    if mx <= 0:
        return None
    return int(round(100.0 * cur / mx))


def _tok_shields(obj, sid):
    try:
        blob = obj.data_set
        front = _pct(blob.get("shield_val", 0), blob.get("shield_max_val", 0))
        rear = _pct(blob.get("shield_val", 1), blob.get("shield_max_val", 1))
    except Exception:
        return ""
    if front is None and rear is None:
        return ""
    if rear is None:
        return str(front) + "%"
    if front is None:
        return str(rear) + "%"
    return str(front) + "% / " + str(rear) + "%"


_TOKENS = {
    "name": _tok_name,
    "class": _tok_class,
    "side": _tok_side,
    "role": _tok_role,
    "race": _tok_race,
    "comms_id": _tok_comms_id,
    "hull": _tok_hull,
    "shields": _tok_shields,
}


def director_overlay_tokens():
    """The token names, for a help line on the editor."""
    return sorted(_TOKENS)


def director_overlay_token_help():
    """One ASCII line naming what an operator can type."""
    return "<<" + ">>  <<".join(director_overlay_tokens()) + ">>   (<<class|ship>> for a fallback)"


def director_overlay_resolve(text, subject_id):
    """Fill a template against one subject.

    An UNKNOWN token is left literal rather than raising - the same missing-key-safe contract
    `amd_fill` settled on, so a typo shows up on screen as `<<shpi>>` and is obvious, instead of
    blanking the card. A KNOWN token that cannot resolve (no hull class on a rock) becomes its
    `|fallback`, or empty.
    """
    if not text:
        return ""
    text = str(text)
    if "<<" not in text:
        return _plain(text)
    obj = _obj(subject_id)

    def swap(m):
        tok = m.group("tok").lower()
        alt = m.group("alt")
        fn = _TOKENS.get(tok)
        if fn is None:
            return m.group(0)          # unknown: leave it visible
        if obj is None:
            return alt if alt is not None else ""
        try:
            value = fn(obj, subject_id)
        except Exception:
            value = ""
        if value:
            return str(value)
        return alt if alt is not None else ""

    # _plain AFTER substitution too: a ship literally named `Foo{bar}` would otherwise reach
    # gui_text and be f-string evaluated there.
    return _plain(_TOKEN.sub(swap, text))


def director_overlay_resolve_fields(fields, subject_id):
    """Resolve every value in one overlay's field dict. `kind` is passed through untouched."""
    out = {}
    for key, value in (fields or {}).items():
        out[key] = value if key == "kind" else director_overlay_resolve(value, subject_id)
    return out


# --- presets ------------------------------------------------------------------------------

def _user(kind):
    return _PRESETS.setdefault(kind, {})


def director_overlay_preset_rows(kind):
    """(labels, keys) for one kind's preset dropdown - built-ins then saved ones.

    Labels are made unique: a dropdown and a listbox both resolve a selection by comparing the
    display text, so two identical entries are indistinguishable.
    """
    labels = []
    keys = []
    seen = {}
    for key, label, _fields in _BUILTIN.get(kind, ()):
        labels.append(label)
        keys.append(key)
        seen[label] = 1
    for key in _user(kind):
        label = _user(kind)[key]["label"]
        n = seen.get(label, 0) + 1
        seen[label] = n
        if n > 1:
            label = label + " (" + str(n) + ")"
        labels.append(label)
        keys.append(key)
    return labels, keys


def director_overlay_preset_list(kind):
    """The comma-separated labels, for `gui_drop_down`'s `list:`."""
    return ",".join(director_overlay_preset_rows(kind)[0])


def director_overlay_preset_fields(kind, label):
    """The templates a preset holds, by its DISPLAY label. {} when there is no such preset."""
    want = _label(label)
    for _key, name, fields in _BUILTIN.get(kind, ()):
        if name == want:
            return dict(fields)
    for key in _user(kind):
        if _user(kind)[key]["label"] == want:
            return dict(_user(kind)[key]["fields"])
    return {}


def director_overlay_preset_save(kind, name, fields):
    """Save the templates currently typed into a row. Returns the stored LABEL, or None.

    The label rather than the key, because the label is what the caller has to put back in the
    dropdown - and it is not always the string that was passed in, since `_label` flattens the
    punctuation a `list:` property cannot carry.

    Saving over a name replaces it - an operator tweaking a preset means to change it, not to
    accumulate "Ship ID (2)".
    """
    label = _label(name)
    if not label or kind not in DIRECTOR_OVERLAY_FIELDS:
        return None
    keep = {}
    for field in DIRECTOR_OVERLAY_FIELDS[kind]:
        keep[field] = str((fields or {}).get(field) or "")
    key = "u:" + label.lower()
    _user(kind)[key] = {"key": key, "label": label, "fields": keep}
    return label


def director_overlay_preset_delete(kind, label):
    want = _label(label)
    for key in list(_user(kind)):
        if _user(kind)[key]["label"] == want:
            _user(kind).pop(key)
            return True
    return False
