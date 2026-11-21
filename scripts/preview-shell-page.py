#!/usr/bin/env python3
"""Serves the shell and the website files from two origins, as the split is.

The device server answers on one port with the shell and the fake remote of
scripts/preview-buttons-page.py. The website server answers on another port
with the loader, the bundle, and the signature. A different port is a different
origin, so the browser treats the website as cross-origin and enforces the
integrity pin, as it does for GitHub Pages.

Usage: python3 scripts/preview-shell-page.py [--port 8123] [--site-port 8131]

Open http://127.0.0.1:8123/ to use the page.

  --tamper-app     change one byte of the bundle. The loader must refuse it.
  --tamper-loader  change one byte of the loader. The browser must refuse it.
  --downgrade      serve an older signed bundle. The loader must refuse it.

Open http://127.0.0.1:8123/preview/offline to drop the fake remote API.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_SPEC = importlib.util.spec_from_file_location(
    "preview_buttons_page", ROOT / "scripts" / "preview-buttons-page.py")
preview = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(preview)

sys.path.insert(0, str(ROOT / "components" / "button_config"))
import shell_build as build  # noqa: E402

FILES: dict[str, tuple[bytes, str]] = {}


class SiteHandler(BaseHTTPRequestHandler):
    """Stands in for GitHub Pages, which sends the same CORS header."""

    def log_message(self, fmt: str, *args) -> None:
        print("site:", fmt % args)

    def do_GET(self) -> None:
        entry = FILES.get(self.path)
        if entry is None:
            self.send_error(404)
            return
        body, kind = entry
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def signed(text: str) -> bytes:
    """Returns the signature of the text, made with the local secret key."""
    with tempfile.TemporaryDirectory() as hold:
        path = Path(hold) / "app.js"
        path.write_text(text)
        subprocess.run(["node", str(ROOT / "scripts" / "ui-signing.mjs"), "sign", str(path)],
                       check=True, capture_output=True)
        return path.with_suffix(".js.sig").read_bytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--site-port", type=int, default=8131)
    parser.add_argument("--tamper-app", action="store_true")
    parser.add_argument("--tamper-loader", action="store_true")
    parser.add_argument("--downgrade", action="store_true")
    args = parser.parse_args()

    base = f"http://127.0.0.1:{args.site_port}/app/"
    name = build.loader_name()
    loader = build.loader_text().replace(build.BUNDLE_BASE, base)
    shell = build.shell_html(loader, base, name)

    app = build.bundle_js()
    if args.downgrade:
        app = app.replace(f"//v={build.ui_version()}\n", "//v=1\n", 1)
    signature = signed(app)
    if args.tamper_app:
        app += "\n"
    served_loader = loader + "\n" if args.tamper_loader else loader

    FILES[f"/app/{name}"] = (served_loader.encode(), "text/javascript; charset=utf-8")
    FILES["/app/app.js"] = (app.encode(), "text/javascript; charset=utf-8")
    FILES["/app/app.js.sig"] = (signature, "text/plain; charset=utf-8")
    preview.page_html = lambda: shell.encode()

    site = ThreadingHTTPServer(("127.0.0.1", args.site_port), SiteHandler)
    threading.Thread(target=site.serve_forever, daemon=True).start()
    device = ThreadingHTTPServer(("127.0.0.1", args.port), preview.Handler)
    print(f"device   http://127.0.0.1:{args.port}/   shell {len(shell)} bytes")
    print(f"website  {base}   loader {len(loader)} bytes, bundle {len(app)} bytes")
    print(f"pin      {build.sri_hash(loader)}")
    for flag in ("tamper_app", "tamper_loader", "downgrade"):
        if getattr(args, flag):
            print(f"TEST     {flag} is on")
    device.serve_forever()


if __name__ == "__main__":
    main()
