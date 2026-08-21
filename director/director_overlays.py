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

# THE OVERLAY VOCABULARY. (kind, editor label, field names), in picker order.
#
# ONE TABLE. The editor used to carry its own copy - four kinds, hand-unrolled into four MAST
# rows - and this file carried the field names again beside the presets. Two tables that have
# to agree are two tables that will not, and adding a kind meant editing both plus eighty lines
# of MAST. The editor now reads THIS and builds its picker from it, so a new kind is one line.
#
# The fields are the ones each builder in overlay.py ACTUALLY reads. A field a builder ignores
# is a text box that silently does nothing, which is worse than not offering it at all.
DIRECTOR_OVERLAY_KINDS = (
    ("lower_third",          "Lower third", ("name", "line")),
    ("lower_third_portrait", "Speaker",     ("name", "line", "ship")),
    ("hero",                 "Hero",        ("title", "subtitle")),
    ("banner",               "Top status",  ("text",)),
    ("letterbox",            "Letterbox",   ("line",)),
    ("credits",              "Credits",     ("title", "entries")),
)

# The most fields any one kind has - how many field rows the editor unrolls.
DIRECTOR_OVERLAY_MAX_FIELDS = max(len(f) for _k, _l, f in DIRECTOR_OVERLAY_KINDS)

# kind -> field names, derived so it cannot drift from the table above.
DIRECTOR_OVERLAY_FIELDS = {kind: fields for kind, _label, fields in DIRECTOR_OVERLAY_KINDS}

# kind -> ((key, label, {field: template}), ...). Built-ins; user saves land beside these.
_BUILTIN = {
    "lower_third": (
        ("ship_id", "Ship ID", {"name": "<<name>>", "line": "<<class>>"}),
        ("ship_side", "Ship and side", {"name": "<<name>>", "line": "<<class|ship>> - <<side>>"}),
        ("condition", "Condition", {"name": "<<name>>", "line": "hull <<hull|--%>>"}),
        ("contact", "Contact", {"name": "<<comms_id>>", "line": "<<role|contact>>"}),
        # "Artemis - Helm" over "Viper". The one worth having on a CONSOLE beat, and the reason
        # console items learned to carry furniture at all.
        ("station", "Station and crew",
         {"name": "<<name>> - <<console>>", "line": "<<crew_name|unmanned>>"}),
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
    # A SPEAKER CARD. `ship` takes an id, not text - overlay_lower_third_portrait draws a
    # `ship://` square from it - so the preset fills it with the subject's own id and a
    # speaker card of whatever is on screen needs no typing at all. See _tok_subject_id.
    "lower_third_portrait": (
        ("speaker", "Speaker", {"name": "<<name>>", "line": "", "ship": "<<subject_id>>"}),
        ("speaker_side", "Speaker and side",
         {"name": "<<name>>", "line": "<<side>>", "ship": "<<subject_id>>"}),
        # SUBJECT-FREE, for an overlay-only beat: a named narrator over whatever is on air.
        ("narrator", "Narrator", {"name": "Narrator", "line": "", "ship": ""}),
    ),
    "credits": (
        ("roll", "Roll", {"title": "", "entries": ""}),
        ("titled_roll", "Titled roll", {"title": "Artemis Cosmos", "entries": ""}),
    ),
}

# Kinds whose built-ins are the ones an OVERLAY-ONLY item wants - a title, an intro, an outro.
# A subject-free preset per kind is not a nicety: the first thing a director does with an ovl
# item is tick Hero and expect a card, and every other preset there resolves to empty.
_BUILTIN_FREE = {
    "hero": ("title", "Title card", {"title": "", "subtitle": ""}),
    "banner": ("plain", "Plain text", {"text": ""}),
    "letterbox": ("plain", "Plain text", {"line": ""}),
    "lower_third": ("plain", "Plain text", {"name": "", "line": ""}),
}
for _kind, _row in _BUILTIN_FREE.items():
    _BUILTIN[_kind] = _BUILTIN[_kind] + (_row,)

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


def _tok_subject_id(obj, sid):
    """The subject's own id, as text.

    NOT display text - it is for a field that takes an ID, `lower_third_portrait`'s `ship=`.
    A token rather than a special case in the builder, so a speaker card can be pointed at
    the subject by a PRESET and the operator can still override it by typing.

    Empty on an overlay-only item, where there is no subject. The portrait builder then draws
    the card without a square, which is the right answer for a narrator card.
    """
    return str(sid) if sid else ""


_TOKENS = {
    "subject_id": _tok_subject_id,
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
    names = director_overlay_tokens() + director_overlay_item_tokens()
    return "<<" + ">>  <<".join(sorted(names)) + ">>   (<<class|ship>> for a fallback)"


def director_overlay_resolve(text, subject_id, item=None):
    """Fill a template against one subject, and optionally against the BEAT showing it.

    An UNKNOWN token is left literal rather than raising - the same missing-key-safe contract
    `amd_fill` settled on, so a typo shows up on screen as `<<shpi>>` and is obvious, instead of
    blanking the card. A KNOWN token that cannot resolve (no hull class on a rock) becomes its
    `|fallback`, or empty.

    `item` is what lets `<<name>> - <<console>> - <<crew_name>>` read as
    "Artemis - Helm - Viper": two of those three are properties of the beat and the person at
    that station, not of the ship. Absent, those tokens resolve to their fallback like any other
    that cannot answer - so an old caller that does not pass it degrades rather than raising.
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
        # ITEM TOKENS FIRST, and they are asked even when the subject is gone: `<<console>>` is
        # a property of the beat, so a console beat pointed at a ship that just blew up should
        # still say which station it was.
        item_fn = _ITEM_TOKENS.get(tok)
        if item_fn is not None:
            try:
                value = item_fn(item, obj, subject_id)
            except Exception:
                value = ""
            if value:
                return str(value)
            return alt if alt is not None else ""
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


# --- tokens that come off the ITEM rather than the subject --------------------------------
#
# A console beat is "Artemis - Helm - Viper", and only one third of that is a property of the
# ship. `<<console>>` is a property of the BEAT, and `<<crew_name>>` is a property of the person
# sitting at that console on that ship - which needs both.
#
# A separate table rather than more entries in `_TOKENS`, because the signatures genuinely
# differ: a subject token is answered from the object alone, and these cannot be.


def _tok_console(item, obj, sid):
    """The beat's console, title-cased for display: "Helm", "Weapons".

    Empty on a camera beat, which has no console - and empty is right rather than a fallback,
    because `<<name>> - <<console>>` on a camera item should read as the ship's name and not as
    the ship's name followed by a dash and a lie.
    """
    console = str((item or {}).get("console") or "").strip()
    return console.capitalize() if console else ""


def _tok_crew_name(item, obj, sid):
    """Who is sitting at this beat's console on this ship, or "".

    The ship's own consoles are its `consoles` LINK - that is what common_console_select writes
    when a client picks a station, and what the Director's own cam takes with it when it moves.
    A client carries CONSOLE_TYPE and CREW_NAME as inventory, both set in show_console_selected.

    NOT the first client on the ship: a bridge has five, and naming the wrong one on air is
    worse than naming nobody. It matches the beat's console, so a camera beat - which has no
    console - correctly resolves to nothing.
    """
    console = str((item or {}).get("console") or "").strip().lower()
    if not console or not sid:
        return ""
    from sbs_utils.procedural.links import linked_to
    from sbs_utils.procedural.inventory import get_inventory_value
    try:
        clients = linked_to(sid, "consoles")
    except Exception:
        return ""
    for client_id in sorted(clients or ()):
        seat = get_inventory_value(client_id, "CONSOLE_TYPE", None)
        if str(seat or "").strip().lower() != console:
            continue
        name = get_inventory_value(client_id, "CREW_NAME", None)
        if name:
            return _plain(name)
    return ""


_ITEM_TOKENS = {
    "console": _tok_console,
    "crew_name": _tok_crew_name,
}


def director_overlay_item_tokens():
    """The token names that need the item rather than just the subject."""
    return sorted(_ITEM_TOKENS)


def director_overlay_resolve_fields(fields, subject_id, item=None):
    """Resolve every value in one overlay's field dict. `kind` is passed through untouched."""
    out = {}
    for key, value in (fields or {}).items():
        out[key] = value if key == "kind" else director_overlay_resolve(value, subject_id, item)
    return out


# Fields that are NOT text by the time overlay.py sees them. The editor can only offer a text
# box, so the conversion has to happen on the way out - once, here, rather than at the call
# site, which is MAST and cannot do either of these.
#
#   entries   overlay_credits takes a LIST of lines. Split on `;` - not a newline, because a
#             single-line gui_input cannot produce one.
#   ship      overlay_lower_third_portrait takes an object ID for its `ship://` square. The
#             `<<subject_id>>` token resolves to the id as TEXT, and a str id would be built
#             into a `ship://` path that names nothing and draw a blank square.
_LIST_FIELDS = ("entries",)
_ID_FIELDS = ("ship",)


def director_overlay_build_fields(entry, subject_id, item=None):
    """One overlay's fields, resolved AND in the shapes overlay.py's builders expect.

    TEXT FIELDS ARE PASSED THROUGH EVEN WHEN EMPTY. Several builders take their primary field
    positionally (`overlay_lower_third(name, line)`), so dropping a blank one would raise
    rather than draw a card with a blank line - and a blank line is a legitimate thing to want.

    An unusable `ship` is the one exception, because its default is `None` and not `""`: an
    empty or zero id has to be OMITTED so the builder draws no square, rather than being sent
    a `ship://` path that names nothing.
    """
    out = {}
    for key, value in director_overlay_resolve_fields(entry, subject_id, item).items():
        if key in _LIST_FIELDS:
            lines = [part.strip() for part in str(value or "").split(";")]
            out[key] = [line for line in lines if line]
        elif key in _ID_FIELDS:
            try:
                oid = int(str(value).strip())
            except (TypeError, ValueError):
                oid = 0
            if oid:
                out[key] = oid
        else:
            out[key] = value
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
