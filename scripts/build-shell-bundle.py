#!/usr/bin/env python3
"""Writes the interface bundle that the website serves, and signs it.

The firmware builds the shell itself. The shell pins the loader, and the loader
checks the signature of this bundle. So a change to the page needs a new bundle
and a new signature, but no firmware build.

The secret key lives outside the repository. Run this once for each clone:

    node scripts/ui-signing.mjs keygen

Usage: python3 scripts/build-shell-bundle.py [--check] [--no-sign]
"""

from __future__ import annotations

import argparse
import gzip
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "components" / "button_config"))

from shell_build import (  # noqa: E402
    APP, SIGNATURE, VERSION_FILE, bundle_body, bundle_js, loader_name, page,
    shell_html, sri_hash, ui_version,
)


def published_body() -> str | None:
    """Returns the published bundle without its version line."""
    if not APP.exists():
        return None
    text = APP.read_text()
    return text.split("\n", 1)[1] if text.startswith("//v=") else text


SECRET_KEY = Path.home() / ".config" / "homething-c6" / "ui-signing-key.pem"


def sign() -> bool:
    try:
        subprocess.run(["node", str(ROOT / "scripts" / "ui-signing.mjs"), "sign", str(APP)],
                       check=True)
        return True
    except (OSError, subprocess.SubprocessError) as err:
        print(f"cannot sign the bundle: {err}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail when the published bundle is not the current one")
    parser.add_argument("--no-sign", action="store_true",
                        help="write the bundle but leave the signature alone")
    args = parser.parse_args()

    body = bundle_body()
    if args.check:
        if published_body() != body:
            print("site/app/app.js is not the current bundle", file=sys.stderr)
            return 1
        if not SIGNATURE.exists():
            print("site/app/app.js.sig is missing", file=sys.stderr)
            return 1
        print("ok site/app/app.js")
        return 0

    # Without the key the bundle cannot be signed, and an unsigned rewrite
    # would leave the bundle and the signature disagreeing, which every loader
    # then refuses. So leave both files as they are. Only the project that
    # holds the key publishes the hosted interface, and a fork builds the
    # firmware with `page: embedded`, which needs no website and no key.
    if not args.no_sign and not SECRET_KEY.exists():
        print(f"no secret key at {SECRET_KEY}, so site/app/ stays as it is.\n"
              "Build the firmware with `page: embedded` to put the interface in flash.",
              file=sys.stderr)
        return 0

    # The version rises only on a real change, so an unrelated commit leaves
    # the bundle and its signature alone.
    if published_body() != body:
        VERSION_FILE.write_text(f"{ui_version() + 1}\n")
    bundle = bundle_js()
    APP.parent.mkdir(parents=True, exist_ok=True)
    APP.write_text(bundle)
    if not args.no_sign and not sign():
        return 1

    shell = shell_html()
    before = len(gzip.compress(page().encode(), 9))
    after = len(gzip.compress(shell.encode(), 9))
    print(f"bundle   site/app/app.js  {len(bundle)} bytes, version {ui_version()}")
    print(f"loader   site/app/{loader_name()}")
    print(f"pin      {sri_hash(Path(APP.parent / loader_name()).read_text())}")
    print(f"flash    {after} bytes gzip, was {before}, saves {before - after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
