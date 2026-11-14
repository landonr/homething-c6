#!/usr/bin/env python3
"""Regenerates the minified web page script with esbuild.

The firmware build must not need Node.js, because a Device Builder adoption
build has no checkout. So this script runs at development time and commits the
result. Run it after every change to `button_config_page.h`.

Usage:
  python3 scripts/minify-page.py            # write the minified script
  python3 scripts/minify-page.py --check    # fail if the committed file is stale
"""

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "components" / "button_config" / "page_build.py"

_SPEC = importlib.util.spec_from_file_location("page_build", MODULE)
page_build = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(page_build)

# esbuild keeps every top-level name, because a plain script shares the global
# scope. Only local names change, so the page keeps its entry points.
ESBUILD_ARGS = ["--minify", "--loader=js"]
# Another version emits different bytes, so the committed file would read as
# stale. design-checks.yml installs this version.
ESBUILD_VERSION = "0.28.1"


def minify(script: str) -> str:
    """Returns the minified script, or raises SystemExit with the esbuild error."""
    if shutil.which("esbuild") is None:
        raise SystemExit(
            f"esbuild is not on PATH. Install it with `npm i -g esbuild@{ESBUILD_VERSION}`.")
    found = subprocess.run(["esbuild", "--version"], capture_output=True,
                           text=True, timeout=60).stdout.strip()
    if found != ESBUILD_VERSION:
        print(f"warning: esbuild {found} is not the pinned {ESBUILD_VERSION}, "
              "so the output can differ", file=sys.stderr)
    result = subprocess.run(
        ["esbuild", *ESBUILD_ARGS], input=script,
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise SystemExit(f"esbuild failed:\n{result.stderr}")
    return result.stdout.strip("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="compare only, and fail if the committed file is stale")
    args = parser.parse_args()

    wanted = minify(page_build.source_script())
    target = page_build.MINIFIED
    current = target.read_text().strip("\n") if target.exists() else None

    if current == wanted:
        print(f"{target.name} is current ({len(wanted)} bytes)")
        return 0
    if args.check:
        print(f"{target.name} is stale. Run `python3 scripts/minify-page.py`.", file=sys.stderr)
        return 1
    target.write_text(wanted + "\n")
    print(f"wrote {target.name} ({len(wanted)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
