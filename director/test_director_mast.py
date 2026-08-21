"""Static checks on the addon's own .mast, for the shapes that fail SILENTLY at runtime.

WHY A TEXT SCAN AND NOT A TEST THAT RUNS SOMETHING. The editor tab is unreachable headless -
`--exercise-click` cannot press tab-strip buttons - and even the pages that ARE reachable report
PASS while showing a blank screen, because a black frame is a render outcome and no headless run
looks at pixels. Both black screens in this addon shipped under a green `--test`.

    PYTHONPATH=../sbs_utils python -m unittest director.test_director_mast
"""
import glob
import re
import io
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

# Anything that puts content on the page, or hands the page to an engine console. `gui_console`
# counts: `cv_show` for a console item legitimately builds nothing else, because the engine's
# own console widgets ARE the page there.
BUILDS = (
    "gui_section", "gui_row", "gui_text", "gui_button", "gui_list_box", "gui_layout_widget",
    "gui_console", "gui_checkbox", "gui_radio", "gui_input", "gui_drop_down", "gui_int_slider",
    "gui_blank", "gui_sub_section", "gui_face", "gui_icon", "gui_text_area", "gui_table",
    "gui_region", "gui_activate_console", "gui_reroute_client",
)


def _labels(path):
    """Walk one .mast, yielding (label, line_no, line) with comment lines dropped.

    A comment is dropped whole rather than trimmed off the end of a code line: a `#` inside a
    quoted style string is not a comment, and getting that wrong would make the scan lie in
    whichever direction the guess fell.
    """
    label = "<top level>"
    with io.open(path, encoding="utf-8") as handle:
        source = handle.readlines()
    for n, raw in enumerate(source, 1):
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if raw[:1] in ("=", "-", "/") and (raw.startswith("==") or raw.startswith("--")
                                           or raw.startswith("//")):
            label = stripped
            yield label, n, raw, True
            continue
        yield label, n, raw, False


class AwaitGuiNeedsABuildTests(unittest.TestCase):
    """`await gui()` in a label that builds nothing hands the client a BLANK PAGE.

    `await gui()` -> `GuiPromise.initial_poll` -> `page.set_button_layout` -> `swap_layout()`,
    which does `self.layouts = self.pending_layouts` - and the previous swap left
    `pending_layouts` as a fresh EMPTY section. So the await presents nothing at all.

    This cost two black screens in one session: a wrong pin, and then the label added to stop a
    repaint loop. A handler that only changes STATE needs no label and no `await` at all; a
    label that has something to show has to build it first.
    """

    def test_every_await_gui_follows_a_build(self):
        bad = []
        for path in sorted(glob.glob(os.path.join(HERE, "*.mast"))):
            built = False
            for label, n, line, is_label in _labels(path):
                if is_label:
                    built = False
                    continue
                if any(token + "(" in line for token in BUILDS):
                    built = True
                if "await gui(" in line and not built:
                    bad.append("%s:%d  %s  ->  %s"
                               % (os.path.basename(path), n, label, line.strip()))
        self.assertEqual(bad, [], "await gui() with nothing built:\n  " + "\n  ".join(bad))

    def test_the_scan_can_actually_see_a_violation(self):
        # A guard that cannot fail is not a guard. Prove the walker flags the exact shape both
        # black screens had, rather than passing because it matched nothing.
        import tempfile
        src = "=== fine\n    gui_text(\"hi\")\n    await gui()\n\n=== broken\n    await gui()\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sample.mast")
            with io.open(path, "w", encoding="utf-8") as handle:
                handle.write(src)
            found = []
            built = False
            for label, n, line, is_label in _labels(path):
                if is_label:
                    built = False
                    continue
                if any(token + "(" in line for token in BUILDS):
                    built = True
                if "await gui(" in line and not built:
                    found.append((label, n))
        self.assertEqual(found, [("=== broken", 6)])

    def test_a_comment_mentioning_it_is_not_a_violation(self):
        # The README and panel.mast both discuss `await gui()` in prose. An earlier ad-hoc scan
        # reported those as real, which is how a guard starts getting ignored.
        import tempfile
        src = "=== fine\n    # never await gui() here\n    gui_text(\"hi\")\n    await gui()\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sample.mast")
            with io.open(path, "w", encoding="utf-8") as handle:
                handle.write(src)
            built = False
            bad = []
            for label, n, line, is_label in _labels(path):
                if is_label:
                    built = False
                    continue
                if any(token + "(" in line for token in BUILDS):
                    built = True
                if "await gui(" in line and not built:
                    bad.append(n)
        self.assertEqual(bad, [])

class PropsTerminatorTests(unittest.TestCase):
    """Every widget props string ends in `;`.

    `gui_input` stores its props RAW and `_present` appends the cascaded styling straight onto
    the end, so `gui_input("desc: name")` goes on the wire as `desc: namefont:gui-2` and the
    widget draws that as its prompt. Fourteen calls in this addon were missing it.
    """

    WIDGETS = ("gui_input", "gui_checkbox", "gui_drop_down")

    @staticmethod
    def _unterminated(line, widget):
        """The props of a ONE-LITERAL call that does not end in `;`, or None.

        A concatenation is not judged. `gui_input("$text:" + x + ";desc: name;")` assembles to
        something ending in `;` while its FIRST literal ends in `:`, so a scan reading the first
        literal would report every one of them - and a guard that cries wolf gets switched off.
        The shape that actually bit was the plain one-literal call.
        """
        call = widget + '("'
        if call not in line:
            return None
        rest = line.split(call, 1)[1]
        props, _sep, after = rest.partition('"')
        if after[:1] not in (",", ")"):
            return None
        if props and not props.rstrip().endswith(";"):
            return props
        return None

    def test_props_strings_are_terminated(self):
        bad = []
        for path in sorted(glob.glob(os.path.join(HERE, "*.mast"))):
            for label, n, line, is_label in _labels(path):
                if is_label:
                    continue
                for widget in self.WIDGETS:
                    if self._unterminated(line, widget) is not None:
                        bad.append("%s:%d  %s" % (os.path.basename(path), n, line.strip()))
        self.assertEqual(bad, [], "props string with no terminator:\n  " + "\n  ".join(bad))

    def test_the_terminator_scan_can_fail(self):
        # A guard that cannot fail is not a guard.
        good = '    gui_input("desc: ok;", "col-width: 10px;")'
        bad = '    gui_input("desc: bad", "col-width: 10px;")'
        joined = '    gui_input("$text:" + v + ";desc: ok;", "col-width: 10px;")'
        self.assertIsNone(self._unterminated(good, "gui_input"))
        self.assertEqual(self._unterminated(bad, "gui_input"), "desc: bad")
        self.assertIsNone(self._unterminated(joined, "gui_input"))


class CallableNamesTests(unittest.TestCase):
    """Every `director_*` the MAST calls has to be a real def somewhere in the addon.

    A MISSPELLED NAME IS A NameError AT RUNTIME, and a failing MAST expression STOPS THE
    COMMAND - the assignment does not happen, the task ends, and the button reads as doing
    nothing with nothing on screen to say why. That is the same failure mode that made "Add
    console items" look broken, and neither the headless run nor `sbs lint` catches it: the
    editor's tabs are unreachable to `--exercise-click`, and the panel's own handlers only fire
    on a press.

    It also catches the reverse - a helper renamed in Python with a MAST call site left behind.

    A LEADING UNDERSCORE IS PRIVATE (2026-08-16): `_name` is skipped by
    register_mission_functions and is NOT a MAST global, so this deliberately only accepts
    public defs.
    """

    def _defs(self):
        names = set()
        for path in glob.glob(os.path.join(HERE, "*.py")):
            if os.path.basename(path).startswith("test_"):
                continue
            with io.open(path, encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("def director_"):
                        names.add(line[4:line.index("(")].strip())
        return names

    def _called(self):
        """`director_*(` occurrences in the .mast, with the label and line they are on.

        Comment lines are dropped by `_labels`, which is what keeps a name that only appears in
        a design note from being demanded as a def.
        """
        out = []
        for path in sorted(glob.glob(os.path.join(HERE, "*.mast"))):
            for label, n, raw, is_label in _labels(path):
                if is_label:
                    continue
                for match in re.finditer(r"\b(director_[A-Za-z_0-9]*)\s*\(", raw):
                    out.append((os.path.basename(path), n, match.group(1)))
        return out

    def test_every_call_resolves(self):
        defined = self._defs()
        missing = ["%s:%d %s" % (f, n, name)
                   for f, n, name in self._called() if name not in defined]
        self.assertEqual(missing, [], "MAST calls a director_* that no .py defines")

    def test_the_console_declares_pre_game_and_compiles(self):
        """The `@console/director` metadata block, compiled for real.

        TWO THINGS AT ONCE, because they fail together. The picker's Ready handler reads
        `pre_game` off this label, so a block that is absent silently turns the feature off -
        and a block in the WRONG PLACE fails to compile, which is far worse: a story that does
        not compile schedules no task at all, so the whole mission runs with 0 labels.

        `metadata:` and its closing fence sit at column 0, so putting them after ANY indented
        body line - the `"` description included - is an indentation drop mid-label and raises
        "Bad indentation". Measured on `@console`, `@map` and a plain `==` label alike. It is
        the sort of thing that gets "tidied" into the wrong order by someone matching the
        example in MAST_CLAUDE.md, which has it the other way round and does not compile.
        """
        from sbs_utils.fs import test_set_exe_dir
        test_set_exe_dir()
        from sbs_utils.mast_sbs import story_nodes  # noqa: F401 - registers story nodes
        from sbs_utils.mast.mast import Mast
        from sbs_utils.agent import clear_shared

        with io.open(os.path.join(HERE, "director_entry.mast"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith("@console/director"))
        end = next(i for i in range(start + 1, len(lines))
                   if lines[i].strip().startswith("jump "))
        # The real declaration, with its body replaced so nothing else has to resolve.
        code = "\n".join(lines[start:end]) + "\n    ->END\n"
        self.assertIn("metadata:", code, "the console no longer declares metadata")
        self.assertIn("pre_game", code, "the console no longer declares pre_game")

        mast = Mast()
        clear_shared()
        errors = mast.compile(code.replace(" if DIRECTOR_enabled", ""), "t", mast)
        self.assertEqual(errors, [], "the @console/director declaration does not compile")
        label = None
        for name, node in mast.labels.items():
            if "console" in name:
                label = node
        self.assertIsNotNone(label)
        self.assertTrue(label.get_inventory_value("pre_game"),
                        "pre_game did not reach the label's inventory")

    def test_metadata_after_the_description_really_does_not_compile(self):
        # The companion to the test above: prove the trap is real rather than trusting that a
        # passing compile means the order mattered. Same declaration, block moved below the
        # description line - which is the order MAST_CLAUDE.md's example uses.
        from sbs_utils.fs import test_set_exe_dir
        test_set_exe_dir()
        from sbs_utils.mast_sbs import story_nodes  # noqa: F401
        from sbs_utils.mast.mast import Mast
        from sbs_utils.agent import clear_shared

        bad = ('@console/director !0 ^94 "Director"\n'
               '    " Stream director\n'
               'metadata: ``` yaml\n'
               'pre_game: true\n'
               '```\n'
               '    ->END\n')
        mast = Mast()
        clear_shared()
        errors = mast.compile(bad, "t", mast)
        self.assertTrue(errors)
        self.assertIn("indentation", errors[0].lower())

    def test_the_scan_finds_the_calls_it_should(self):
        # A guard that matched nothing would pass forever. These are load-bearing call sites -
        # the selection, the resolved subject, and the bind picker.
        found = {name for _f, _n, name in self._called()}
        for name in ("director_selection", "director_item_subject_id", "director_bind_list",
                     "director_area", "director_cam_ensure"):
            self.assertIn(name, found)


if __name__ == "__main__":
    unittest.main()
