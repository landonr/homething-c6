"""Builds the device shell and the website bundle from the page source.

The firmware serves the shell, a small document with no interface in it. The
shell loads a loader from the project website over HTTPS, and the loader loads
the interface bundle. An insecure page can load a secure subresource, so the
device keeps plain HTTP and its `.local` name. The reverse does not work: a
page on the website cannot call the device, because the browser blocks a
request from HTTPS to HTTP.

The shell pins the loader with its sha384 hash, so the browser runs no other
loader. The loader holds the project public key and checks the signature of the
bundle, so the interface changes with no firmware build.

A pin cannot change without a firmware build, so each loader carries its hash
in its file name and stays in the repository. A unit on an old release then
still finds the loader that its own shell pins.

No esphome import, so the scripts and the tests load this file too.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

try:  # ESPHome imports this file as part of the component package.
    from .face_svg import data_url_body
except ImportError:  # The scripts and the tests load it by path.
    from face_svg import data_url_body

ROOT = Path(__file__).resolve().parents[2]
CASE_FRONT_FACE = ROOT / "docs" / "readme-assets" / "case-front-face.svg"
PAGE_FILE = Path(__file__).resolve().parent / "button_config_page.html"
SCRIPT_OPEN = "<script>\n"
SCRIPT_CLOSE = "\n</script>"
BUNDLE_DIR = ROOT / "site" / "app"
APP = BUNDLE_DIR / "app.js"
SIGNATURE = BUNDLE_DIR / "app.js.sig"
CURRENT_LOADER = BUNDLE_DIR / "loader.current"
VERSION_FILE = BUNDLE_DIR / "ui.version"
# A bench build can point the shell and the loader at another server. Set
# HOMETHING_UI_BASE to test on hardware before the website carries the files.
# Never commit a loader that a bench base built.
DEFAULT_BUNDLE_BASE = "https://landonr.github.io/homething-c6/app/"
BUNDLE_BASE = os.environ.get("HOMETHING_UI_BASE", DEFAULT_BUNDLE_BASE)
CACHE_KEY = "htc6-loader"
TITLE = "homeThing c6 config"
ID_CHARS = 16

SHELL = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<body>
<p id="boot" style="font:15px/1.45 system-ui,sans-serif;margin:2rem">Loading the
configuration page.</p>
<script>
(function(){var U="__URL__",H="__SRI__",K="__KEY__"+H;
function run(s){var e=document.createElement("script");e.textContent=s;
document.head.appendChild(e)}
function stop(){var b=document.getElementById("boot");if(b)b.textContent=
"This page needs the internet one time, to load the configuration interface."}
function cached(){try{return localStorage.getItem(K)}catch(e){return null}}
fetch(U,{integrity:H}).then(function(r){if(!r.ok)throw Error("loader answered "+r.status);
return r.text()}).then(function(s){try{localStorage.setItem(K,s)}catch(e){}run(s)})
.catch(function(e){console.error("homeThing c6 shell: "+((e&&e.message)||e));
var s=cached();if(s)run(s);else stop()})})()
</script>
"""


def ui_version() -> int:
    """Returns the stored bundle version, which never goes down.

    The loader refuses a bundle older than the one that it holds.
    `scripts/build-shell-bundle.py` raises it only when the bundle body
    changes, so an unrelated commit leaves the bundle and its signature alone.
    """
    try:
        return int(VERSION_FILE.read_text().strip())
    except (OSError, ValueError):
        return 1


def script_bounds(html: str) -> tuple[int, int]:
    """Returns the start and the end of the page script.

    The search is positional, so a second script block would hide code from
    both of them.
    """
    start = html.index(SCRIPT_OPEN) + len(SCRIPT_OPEN)
    return start, html.index(SCRIPT_CLOSE, start)


def page() -> str:
    """Returns the composed page, the document that `page: embedded` holds."""
    svg = data_url_body(CASE_FRONT_FACE.read_text(encoding="utf-8"))
    return PAGE_FILE.read_text().replace("__CASE_FRONT_FACE_SVG__", svg)


def bundle_js() -> str:
    """Returns the bundle that the website serves.

    The first line is the version, which the signature covers with the rest of
    the file.
    """
    return f"//v={ui_version()}\n" + bundle_body()


def bundle_body() -> str:
    """Returns the bundle without its version line.

    The page script stays at the top level, so its functions and its variables
    keep the global scope that they have in the page today.
    """
    html = page()
    start, end = script_bounds(html)
    style = html[html.index("<style>") + len("<style>") : html.index("</style>")]
    body_start = html.index(">", html.index("<body")) + 1
    markup = html[body_start : html.index("<script>")]
    icon = html[html.index('<link rel=icon href="') + len('<link rel=icon href="') :]
    icon = icon[: icon.index('">')]
    return (
        "document.head.insertAdjacentHTML('beforeend',"
        + json.dumps("<style>" + style + "</style>")
        + ");\n(function(){var l=document.createElement('link');l.rel='icon';l.href="
        + json.dumps(icon)
        + ";document.head.appendChild(l)})();\ndocument.body.innerHTML="
        + json.dumps(markup)
        + ";\n"
        + html[start:end]
    )


def sri_hash(text: str) -> str:
    """Returns the subresource integrity value of the text."""
    return "sha384-" + base64.b64encode(hashlib.sha384(text.encode()).digest()).decode()


def loader_name() -> str:
    """Returns the file name of the loader that the shell must pin."""
    return CURRENT_LOADER.read_text().strip()


def loader_text() -> str:
    return (BUNDLE_DIR / loader_name()).read_text()


def shell_html(loader: str | None = None, base: str = BUNDLE_BASE,
               name: str | None = None) -> str:
    """Returns the document that the firmware serves at / and /buttons.

    The cache key carries the pin, so a firmware with a new pin ignores the
    copy that the browser saved for the old one.
    """
    if loader is None:
        loader = loader_text()
    if name is None:
        name = loader_name()
    return (
        SHELL.replace("__TITLE__", TITLE)
        .replace("__URL__", base + name)
        .replace("__SRI__", sri_hash(loader))
        .replace("__KEY__", CACHE_KEY)
    )


def write_bundle() -> Path:
    """Writes the interface bundle. The caller signs it afterwards."""
    APP.parent.mkdir(parents=True, exist_ok=True)
    APP.write_text(bundle_js())
    return APP
