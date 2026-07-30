"""Zip a folder's CONTENTS at the archive root - the layout a .mastlib must have.

    python .github/zip_flat.py <folder> <archive>

MAST opens a .mastlib and reads ``__init__.mast`` at the ZIP ROOT
(``Mast.import_content`` -> ``content_from_lib_or_file`` -> ``ZipFile(lib).open(...)``).
An archive that nests the addon folder holds ``<addon>/__init__.mast`` instead, that open
raises, and the addon silently never loads: the mission compiles to zero labels and the
headless test still reports PASS. Every published mastlib had that shape until this
script replaced a `zip-release` step whose `path:` includes the folder.

Mirrors ``file_help.zipdir`` (what ``sbs lib`` writes into ``__lib__``), because both feed
the same folder and a mission cannot tell which one produced its copy: contents at the
root, ``__pycache__`` skipped, deflate level 8. Paths are normalised to ``/`` - zip
entries must use forward slashes to be readable everywhere.

Kept as a file rather than an inline `run:` so it can be executed locally, unchanged, to
verify what a release will contain.
"""
import os
import sys
import zipfile


def zip_flat(src, archive):
    """Write `archive` containing everything under `src`, relative to `src`."""
    count = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        for root, _dirs, files in os.walk(src):
            if "__pycache__" in root:
                continue
            for name in files:
                path = os.path.join(root, name)
                zf.write(path, os.path.relpath(path, src).replace("\\", "/"))
                count += 1
    return count


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, archive = sys.argv[1], sys.argv[2]
    n = zip_flat(src, archive)
    print(f"{archive}: {n} files from {src}/ (flat)")
