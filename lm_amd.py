"""LegendaryMissions' own AMD vocabulary.

Every tool - the linter, the VS Code Inspector, the fence reader's coercion - learns what
a field IS from the schema registry. A word nobody declares is kept and reported as
unknown, which is right for a typo and wrong for a word the mission means: fifty-one of
LM's lint warnings were correct lines nobody had ever declared.

Named `*_amd.py` on purpose - that is what `sbs lint` and the LSP scan for when loading a
mission's vocabulary, the same convention Open Universe's universe_amd.py follows.

Registration is LOUD on a clash with a core field (it raises at startup rather than
silently shadowing), so a future sbs_utils field called `Named` or `Hook` fails here
instead of quietly changing what LM's files mean.
"""
from sbs_utils.procedural.amd_schema import (amd_register_fields, text, integer, pct,
                                             csv, makeup, multiline)


def _declare_lm_vocabulary():
    # A BOSS record - the root of maps/bosses/*.amd. `Boss` resolves to the map archetype
    # (a file's root record names the whole document), so these hang off map.
    amd_register_fields("map", {
        "trigger": text(hint="what summons the boss, e.g. enemies_low"),
        "low": pct(hint="30% - the enemy count that counts as thinned out"),
        "flies": makeup(hint="pirate, or 60% Kralien, 20% Torgoth, 20% Arvonian"),
        "fleets": integer(hint="how many escort fleets arrive with it"),
        "difficulty": text(hint="+2 - a modifier ON the map's difficulty, not a level"),
        "named": csv(hint="Ragnarok tsn_juggernaut, XORN tsn_light_cruiser"),
        "wave": integer(hint="which wave this boss belongs to"),
        "hook": text(hint="the label/signal that stages the encounter"),
    }, domain="LegendaryMissions")

    # How close counts as "at" a landmark. A landmark that names a ZONE rather than a
    # spot - a picket, a patrol box, a no-fly area - needs its size where its position
    # is. A radius kept in the mast instead would be a second place to edit one fact,
    # and the two would drift the first time somebody moved the zone.
    amd_register_fields("landmark", {
        "radius": integer(hint="2500 - how close to Loc counts as inside the zone"),
    }, domain="LegendaryMissions")

    # `Call sign:` and `Intel:` are NOT here. They belong to the casino, which is the
    # only place either word appears (casino/bar.amd), and which ships as an addon a
    # mission can take WITHOUT this file. Declaring them in both places is what made
    # `AMD field 'call sign' is already declared ... with a different meaning` a live
    # startup error the day anything loaded both - the hints had drifted apart.
    # ONE OWNER PER CONCEPT: see casino/casino_amd.py.
    amd_register_fields("dialogue", {
        "lines": text(hint="a named set of barks this scene draws from"),
    }, domain="LegendaryMissions")


_declare_lm_vocabulary()
