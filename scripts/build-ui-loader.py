#!/usr/bin/env python3
"""Bundles the interface loader that the device shell pins.

The loader verifies the signature of the interface bundle, so the website can
change the interface with no firmware build. The shell pins the loader by its
hash, so the loader itself changes only with a firmware build.

esbuild runs here, not in the firmware build: an adopted build has no checkout
and no Node.js. So the bundled loader is a committed file, as the minified page
script is.

Usage: python3 scripts/build-ui-loader.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "components" / "button_config"))

from shell_build import (  # noqa: E402
    BUNDLE_BASE, BUNDLE_DIR, DEFAULT_BUNDLE_BASE, ID_CHARS,
)

SOURCE = BUNDLE_DIR / "loader.src.js"
CURRENT = BUNDLE_DIR / "loader.current"
KEPT = BUNDLE_DIR / "loaders.kept"
PUBLIC_KEY = BUNDLE_DIR / "ui-signing-key.pub"
# Keep this equal to the version in .github/workflows/design-checks.yml.
ESBUILD_VERSION = "0.28.1"


def esbuild() -> str:
    found = shutil.which("esbuild")
    if found is None:
        raise SystemExit(
            f"esbuild is not on PATH. Install it with `npm i -g esbuild@{ESBUILD_VERSION}`.")
    version = subprocess.run([found, "--version"], capture_output=True, text=True,
                             check=True).stdout.strip()
    if version != ESBUILD_VERSION:
        print(f"warning: esbuild {version} is not the pinned {ESBUILD_VERSION}, "
              "so the bundle can differ", file=sys.stderr)
    return found


def build() -> str:
    """Returns the bundled loader, with the key and the base URL filled in."""
    out = subprocess.run(
        [esbuild(), str(SOURCE), "--bundle", "--format=iife", "--minify", "--target=es2020"],
        capture_output=True, text=True, check=True, cwd=ROOT,
    ).stdout
    key = PUBLIC_KEY.read_text().strip()
    for name, value in (("__PUBLIC_KEY__", key), ("__BASE__", BUNDLE_BASE)):
        if out.count(name) != 1:
            raise SystemExit(f"{name} appears {out.count(name)} times in the bundle, want 1")
        out = out.replace(name, value)
    return out


def loader_name(loader: str) -> str:
    return "loader-" + hashlib.sha384(loader.encode()).hexdigest()[:ID_CHARS] + ".js"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail when the committed loader is not the current one")
    args = parser.parse_args()

    loader = build()
    name = loader_name(loader)
    path = BUNDLE_DIR / name

    if args.check:
        if CURRENT.read_text().strip() != name or not path.exists():
            print(f"the committed loader is not {name}", file=sys.stderr)
            return 1
        print(f"ok {name}")
        return 0

    if not path.exists():
        path.write_text(loader)
    CURRENT.write_text(name + "\n")
    # A firmware pins one loader for the life of its release, so every loader
    # that was ever published must stay. The list is what a test checks. A
    # bench loader points at another server and is never published, so it stays
    # out of the list and out of git.
    if BUNDLE_BASE == DEFAULT_BUNDLE_BASE:
        kept = KEPT.read_text().split() if KEPT.exists() else []
        if name not in kept:
            kept.append(name)
        KEPT.write_text("\n".join(kept) + "\n")
    else:
        print(f"bench base {BUNDLE_BASE}, so {name} is not published", file=sys.stderr)
    print(f"loader   site/app/{name}  {len(loader)} bytes")
    print(f"key      {PUBLIC_KEY.read_text().strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
