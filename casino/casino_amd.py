"""The casino addon's own AMD vocabulary.

Named `*_amd.py` on purpose: that is what `sbs lint`, the LSP and the headless
`--test` gate scan for when loading a mission's vocabulary - and they scan inside a
packaged mastlib too, so a mission that consumes the casino as an addon gets these
words without owning a copy of them.

WHY THIS FILE EXISTS AT ALL. `call sign` and `intel` used to be declared TWICE -
here (as `casino`) and again in LegendaryMissions' root `lm_amd.py` (as
`LegendaryMissions`) - with different hints. `amd_register_fields` raises on a
re-declaration that disagrees, by design, so the pair was a live
`AMD field 'call sign' is already declared by archetype 'lifeform' with a different
meaning` waiting for anything that loaded both. Nothing did, only because
`lm_amd.py` is not packaged and `bar_content.py` does not match the `*_amd.py`
scan - two accidents, not a design. The moment a pre-flight lint ran in the same
process as the mission, it fired.

The rule that prevents the next one: ONE OWNER PER CONCEPT. Both fields appear only
in `casino/bar.amd`, so the casino owns them and `lm_amd.py` no longer names them.
Same convention as prefixing an addon's functions - a shared flat namespace where
last-loaded wins silently is the problem in both cases.
"""


def _declare_casino_vocabulary():
    # Imported INSIDE the function, the same way bar_content.py and recipes.py do it,
    # and not as a style choice: MAST merges an imported .py into ONE global namespace
    # where every module name is a global, and sbs_utils ships three modules called
    # `text`. A module-level `from ... import text` is shadowed by one of them, and the
    # bare call fails at runtime with `'module' object is not callable` - pointing at
    # this file from bar.mast, which reads as a bug in the vocabulary rather than a
    # name clash. A local binding wins over the merged globals.
    from sbs_utils.procedural.amd_schema import (amd_register_fields,
                                                 amd_register_section_names,
                                                 text, multiline)

    # A patron is a CHARACTER - a person in the bar, which is what it will have to be
    # the day one of them gets a brain.
    amd_register_fields("lifeform", {
        "call sign": text(hint="Ghost, Bitters, NightSky - the handle the room uses"),
        # `Reliability:` is the shared `reputation` trait's - every person has one.
    }, domain="casino")

    # A rumor is DIALOGUE: the prose is what the patron SAYS (the tip); `intel` is the
    # payoff line shown once the tip proves true.
    amd_register_fields("dialogue", {
        "intel": multiline(hint="the payoff line, shown when the tip checks out"),
    }, domain="casino")

    amd_register_section_names(("patrons", "bar"), "lifeform", domain="casino")


# Registered at IMPORT, like lm_amd.py - so the tooling that imports this module by
# the `*_amd.py` convention gets the words without running any of the addon's MAST.
_declare_casino_vocabulary()
