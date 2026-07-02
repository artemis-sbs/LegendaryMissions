"""Discoverable casino-game route: //casino/game/<key> "Display Name".

Mirrors the engine's own discoverable decorator labels (//gui/tab, @console,
@map, //web). A game declares itself with a route; the lobby enumerates
CasinoGameDecoratorLabel.all - no registry list, no lobby edits. Adding a game
is just:

    //casino/game/nibble "Nibble"
        jump show_nibble

The @mast_node(append=False) registration must load before any .mast that uses
the syntax, so __init__.mast imports this .py before the game .mast files.
"""
import re
from sbs_utils.mast.mast_node import IF_EXP_REGEX, STRING_REGEX_NAMED, mast_node
from sbs_utils.mast.core_nodes.decorator_label import DecoratorLabel
from sbs_utils.procedural.execution import labels_get_type


@mast_node(append=False)
class CasinoGameDecoratorLabel(DecoratorLabel):
    rule = re.compile(
        r'(@|//)casino/game/(?P<path>([\w]+))[ \t]+'
        + STRING_REGEX_NAMED("display_name") + IF_EXP_REGEX)

    all = {}

    @classmethod
    def clear(cls):
        """Drop registered casino-game labels (fresh mission / recompile)."""
        cls.all = {}

    def __init__(self, path, display_name, if_exp=None, loc=None,
                 compile_info=None, q=None):
        id = DecoratorLabel.next_label_id()
        self.label_weight = id
        name = f"casino/game/{path}/{id}"
        super().__init__(name, loc)

        self.game_key = path
        self.display_name = display_name
        self.if_exp = if_exp
        # Leave `path` unset so labels_get_type() matches these by their route
        # NAME ("casino/game/<key>/<id>"). Discovery reads the shared story
        # label table (works in engine AND the separate-module mock), not this
        # class's `all` dict - see casino_games_list().
        self.path = None

        CasinoGameDecoratorLabel.all[path] = self

        self.code = None
        if if_exp is not None:
            if_exp = if_exp.strip()
            try:
                self.code = compile(if_exp, "<string>", "eval")
            except Exception:
                raise Exception(f"Syntax error '{if_exp}'")

        self.next = None
        self.loc = loc
        self.replace = None
        self.cmds = []

    def can_fallthrough(self, parent):
        return False

    def generate_label_end_cmds(self, compile_info=None):
        # Allow following into === / --- labels
        pass

    def test(self, task):
        if self.code is None:
            return True
        return task.eval_code(self.code)


def casino_games_list():
    """Discovered games as [{key, name, label}], sorted by display name.
    ``label`` is the route's label name (gui_task_jump target).

    Reads the shared story label table via labels_get_type - robust across the
    engine (one shared namespace) and the dev mock (separate modules), unlike a
    class-level `all` dict which the mock's per-file import would split."""
    out = []
    for lbl in labels_get_type("casino/game/"):
        out.append({
            "key": getattr(lbl, "game_key", ""),
            "name": getattr(lbl, "display_name", None) or lbl.name,
            "label": lbl.name,
        })
    return sorted(out, key=lambda g: g["name"])
