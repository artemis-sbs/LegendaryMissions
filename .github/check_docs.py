"""Fail if the generated documentation has fallen behind the .amd files.

Run from the MISSIONS folder with sbs_utils and sbs_cli beside this repo, which is
how a developer's machine is laid out and what the CI workflow reproduces.

Two separate invocations, in two separate processes, and that is load-bearing:
`amd_register_fields` writes into a process-global table and is cumulative, so
documenting two missions in one interpreter lists the first one's fields in the
second one's tables. `sbs site` refuses it outright rather than emitting a wrong
table; this script satisfies the rule by only ever documenting one.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MISSION = os.path.dirname(HERE)
MISSIONS = os.path.dirname(MISSION)
SRC = os.path.join(MISSIONS, "sbs_cli", "src")

RUN = """\
import sys
sys.path.insert(0, sys.argv[1])
import main
from click.testing import CliRunner
from cli_cmd import cli
r = CliRunner().invoke(cli, ['site', sys.argv[2], '--emit', sys.argv[3], '--check'])
print(r.output)
sys.exit(r.exit_code)
"""


def main():
    failed = []
    for emit in ("includes", "records"):
        print(f"--- {os.path.basename(MISSION)}: {emit}")
        result = subprocess.run([sys.executable, "-c", RUN, SRC, MISSION, emit])
        if result.returncode != 0:
            failed.append(emit)
    if failed:
        print(f"\nOut of date: {', '.join(failed)}.")
        print(f"Run `sbs site {os.path.basename(MISSION)} --emit <what>` and commit "
              f"the result.")
        return 1
    print("\nGenerated documentation is current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
