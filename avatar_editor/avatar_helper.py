"""Helpers for the avatar editor's named-choice controls.

The redrawn face sheets turned several features into real CHOICES rather than a numeric
range - Terran eyes run Angry / Open / Worried / Closed / Green / Amber / Blue, Ximni's
masks are Respirator / Breather / Armored / Warmask - and `faces.FACE_FEATURES` now
carries those names. A dropdown needs them as a style string going out and as an index
coming back, which is the whole job here.

Every function is prefixed `avatar_editor_`: an addon's top-level defs land in ONE flat
mission-wide MAST namespace, last loaded wins, with no warning. A bare `choice_index`
here would be a runtime signature error in whichever addon lost, on a line that looks
correct.
"""


def avatar_editor_choice_style(names, index):
    """A `gui_drop_down` style string showing `index` and offering `names`.

    Contains no braces on purpose. MAST re-runs an assigned string through f-string
    formatting, so a '{' in text handed back from Python is a SyntaxError reported
    against the caller's line rather than against this function.
    """
    names = [str(n).replace(",", " ") for n in (names or [])]
    if not names:
        return "text: ;list: "
    try:
        current = names[int(index) % len(names)]
    except (TypeError, ValueError):
        current = names[0]
    return "text: " + current + ";list: " + ", ".join(names)


#: Above this many options a dropdown stops being usable in the engine. The owner's call:
#: "anything over 15 gets ugly - even 10". 8 sits under that with room to spare, and it
#: lands where the content does: it keeps the short, genuinely enumerable lists as
#: dropdowns (body 2, rank pips 3, masks 4, alien eyes 4-5, Kralien mouths 6) and sends
#: the long ones to a slider - eyes 14, mouths 14, hair tone 12, and the 39-tone skin
#: palette that prompted this.
AVATAR_EDITOR_DROPDOWN_MAX = 8


def avatar_editor_use_slider(names):
    """True when a named feature should be a slider-with-a-name rather than a dropdown."""
    return len(names or []) > AVATAR_EDITOR_DROPDOWN_MAX


def avatar_editor_choice_label(label, names, index):
    """`"<Feature>: <name>"` as a text prop, for the label beside a named slider.

    One widget carrying both, rather than a third control on the row: the editor's
    controls live in a 400px column and a label, a name and a slider do not fit across it.

    Escaped and de-braced. The name comes from a table, but a ':' or ';' in it would
    inject style properties into the widget, and a '{' would be re-run as an f-string by
    MAST and reported as a SyntaxError against the caller.
    """
    names = list(names or [])
    if not names:
        return "text: " + _avatar_clean(label)
    try:
        current = names[int(index) % len(names)]
    except (TypeError, ValueError):
        current = names[0]
    return "text: " + _avatar_clean(label) + ": " + _avatar_clean(current)


def _avatar_clean(text):
    out = str(text or "")
    for bad in ("{", "}", ":", ";", "`"):
        out = out.replace(bad, " ")
    return out.strip()


def avatar_editor_defaults(features, race):
    """Starting values for a race with no face to resume from.

    Every control starts at its minimum EXCEPT the eyes and mouth, which start on the
    race's neutral expression. Index 0 of the Terran eye row is "Angry" and index 0 of the
    mouth row is a particular resting shape - so a brand new avatar used to open scowling
    at you, which reads as the editor being broken rather than as a choice.
    """
    from sbs_utils import faces

    values = [f.get("min", 0) for f in features]
    neutral = faces.FACE_EXPRESSIONS.get(str(race).lower(), {}).get("neutral")
    if neutral is None:
        return values
    for i, f in enumerate(features):
        if f.get("key") == "eyes" and neutral[0] is not None:
            values[i] = neutral[0]
        elif f.get("key") == "mouth" and neutral[1] is not None:
            values[i] = neutral[1]
    return values


def avatar_editor_randomize(features, race, required=None):
    """(values, enables) for a fresh random face of the SAME race.

    Built by rolling a real `random_face` and reading it back through `parse_face`, not by
    picking a number per control. That is the whole point: the randomizer already knows
    not to hand somebody closed eyes or a mid-word mouth as a resting portrait, not to
    give a human green skin, and roughly how often a face should have a hat - and none of
    that would survive being reimplemented here.

    `required` is the caller's not-optional list. Marking Clothes required has to mean
    more than "the checkbox is gone": one roll in five is a civilian, so without this a
    press of Randomize puts the bridge officer in a suit and tie - which is the exact
    thing the required flag exists to prevent.

    Falls back to the defaults if the roll cannot be read back, which is what happens for
    a race whose atlas is whole drawn busts: there are no features to take apart.
    """
    from sbs_utils import faces

    wanted = {str(x).strip().lower() for x in (required or [])}
    civilian = False if "clothes" in wanted else None
    parsed = faces.parse_face(faces.random_face(race, civilian=civilian))
    if parsed is None or parsed.get("race") != str(race).lower():
        return avatar_editor_defaults(features, race), [True] * len(features)
    values = list(parsed["values"])
    enables = list(parsed["enables"])
    # parse_face returns one entry per FACE_FEATURES slot for that race, but pad anyway -
    # a short list here would leave the tail of the controls reading somebody else's face.
    values += [0] * (len(features) - len(values))
    enables += [True] * (len(features) - len(enables))
    return values[:len(features)], enables[:len(features)]


def avatar_editor_choice_index(names, value):
    """The index `value` picked, or 0 when the dropdown answered something unexpected.

    0 rather than raising: an unknown label means the control and the table disagree,
    and a face built from feature 0 is a face. Failing here would take down the whole
    editor page instead.
    """
    names = [str(n).replace(",", " ") for n in (names or [])]
    try:
        return names.index(str(value))
    except ValueError:
        return 0
