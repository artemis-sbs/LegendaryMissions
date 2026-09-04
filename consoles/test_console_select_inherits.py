"""`select_console` must not read a variable only `client_main` sets.

MAST variables are TASK-scoped. `client_main` is the client's own label; the picker
label `select_console` is reached from there normally, but also from the server (client
0, which never runs client_main), from a console cycle, and from the Director's
pre-game reroute. Every variable client_main leaves behind is undefined on those paths,
and a failing expression ENDS THE COMMAND - so the picker stops building half way and
the screen is dead, with one NameError in mast.runtime.log to show for it.

Reported from the engine as:

    NameError: name 'client_select_ship_id' is not defined
    crew_choices_for(client_select_ship_id, None, client_id)   line 406, client_id 0

That was the SECOND one found this way: guarding `console_select_item` alone simply
moved the error down the label. So this checks the whole class at once - anything
client_main sets and select_console reads before setting has to carry a `default`.

Static on purpose: it is a property of the file, and needs no engine, page or client.

    PYTHONPATH=../sbs_utils python -m unittest consoles.test_console_select_inherits
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PICKER = os.path.join(HERE, "common_console_select.mast")

LABEL = re.compile(r"^(?:={2,}\s*(\w+)|---+\s*(\w+))")
# `x = ...`, with or without a scope keyword, but never `==`.
ASSIGN = re.compile(r"^\s*(?:default\s+|shared\s+|assigned\s+|temp\s+|client\s+)*"
                    r"([a-zA-Z_]\w*)\s*=(?!=)")
DEFAULT = re.compile(r"^\s*default\s+(?:shared\s+)?([a-zA-Z_]\w*)\s*=")
SHARED = re.compile(r"^\s*(?:default\s+)?shared\s+([a-zA-Z_]\w*)\s*=")
NAME = re.compile(r"[a-zA-Z_]\w*")
STRING = re.compile(r"""("[^"]*"|'[^']*'|`[^`]*`)""")


def _lines():
    with open(PICKER, encoding="utf-8") as handle:
        return handle.read().split("\n")


def _spans(lines):
    """label name -> (start, end) line indexes, top-level labels only."""
    marks = [(i, m.group(1) or m.group(2))
             for i, l in enumerate(lines) for m in (LABEL.match(l),) if m]
    out = {}
    for k, (i, name) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        out.setdefault(name, (i, end))
    return out


def _code(line):
    """The line with its comment and every quoted string removed.

    Strings matter: `gui_input(var="crew_name")` names a variable it does not READ,
    and counting that as a read is how a check like this cries wolf."""
    line = line.split("#")[0]
    return STRING.sub(" ", line)


class TestSelectConsoleGuardsWhatItInherits(unittest.TestCase):
    def setUp(self):
        self.lines = _lines()
        spans = _spans(self.lines)
        self.assertIn("client_main", spans)
        self.assertIn("select_console", spans)
        self.cm = spans["client_main"]
        self.sc = spans["select_console"]

    def _set_in_client_main(self):
        """Names client_main assigns, EXCEPT the shared ones - those live on the story
        and survive whichever task ran first."""
        names, shared = set(), set()
        for line in self.lines[self.cm[0]:self.cm[1]]:
            line = _code(line)
            m = SHARED.match(line)
            if m:
                shared.add(m.group(1))
                continue
            m = ASSIGN.match(line)
            if m:
                names.add(m.group(1))
        return names - shared

    def test_every_inherited_variable_is_defaulted_before_it_is_read(self):
        inherited = self._set_in_client_main()
        first_read, first_write, guarded = {}, {}, set()
        for offset, raw in enumerate(self.lines[self.sc[0]:self.sc[1]]):
            line = _code(raw)
            m = DEFAULT.match(line)
            if m:
                guarded.add(m.group(1))
            m = ASSIGN.match(line)
            lhs = m.group(1) if m else None
            if lhs is not None:
                first_write.setdefault(lhs, offset)
            for name in NAME.findall(line[m.end():] if m else line):
                first_read.setdefault(name, offset)

        unguarded = []
        for name in sorted(inherited):
            if name in guarded or name not in first_read:
                continue
            read, write = first_read[name], first_write.get(name)
            if write is None or read < write:
                unguarded.append(f"{name} (read at line {self.sc[0] + read + 1})")

        self.assertEqual(
            unguarded, [],
            "select_console reads these without a `default`, and they are only set in "
            "client_main - so on the server, a console cycle or a pre-game reroute the "
            "page dies at the first one with a NameError:\n  " + "\n  ".join(unguarded))


if __name__ == "__main__":
    unittest.main()
