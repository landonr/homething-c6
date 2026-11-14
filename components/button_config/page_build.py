"""Composes the web page from its source header and its minified script.

The firmware build cannot run a JavaScript minifier, because an adopted build
has no checkout and no Node.js. So the minified script is a committed file, and
`scripts/minify-page.py` regenerates it. `test_page_js.py` proves that the
committed file still matches the source.
"""

from pathlib import Path
import re

HERE = Path(__file__).parent
PAGE = HERE / "button_config_page.h"
MINIFIED = HERE / "button_config_page.min.js"
SCRIPT_OPEN = "<script>\n"
SCRIPT_CLOSE = "\n</script>"
SVG_PLACEHOLDER = "__CASE_FRONT_FACE_SVG__"


def page_html() -> str:
    """Returns the PAGE_HTML raw string of the header."""
    match = re.search(r'R"=====\((.*)\)=====";', PAGE.read_text(), re.DOTALL)
    if match is None:
        raise ValueError("button_config_page.h has no PAGE_HTML value")
    return match.group(1)


def script_bounds(html: str) -> tuple[int, int]:
    """Returns the start and the end of the script body. The extraction is
    positional, so a second script block would hide code from both of them."""
    start = html.index(SCRIPT_OPEN) + len(SCRIPT_OPEN)
    return start, html.index(SCRIPT_CLOSE, start)


def source_script() -> str:
    html = page_html()
    start, end = script_bounds(html)
    return html[start:end]


def compose(svg: str, minified: bool = True) -> str:
    """Returns the page. The firmware embeds the minified script. The preview
    keeps the source script, so it stays readable and cannot show a stale copy."""
    html = page_html()
    if minified:
        start, end = script_bounds(html)
        html = html[:start] + MINIFIED.read_text().strip("\n") + html[end:]
    return html.replace(SVG_PLACEHOLDER, svg)
