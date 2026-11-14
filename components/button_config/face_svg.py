"""Packs case-front-face.svg into the data: URL of the web page.

The page puts the result after "data:image/svg+xml," in a double-quoted img src.
No esphome import, so scripts/preview-buttons-page.py loads this file too.
"""

from decimal import Decimal
import re

_TOKEN = re.compile(r"[MLZ]|-?(?:\d+\.?\d*|\.\d+)")
# Only absolute M, L and Z with plain numbers. Other path data stays as it is.
_SIMPLE_PATH = re.compile(r"[MLZ0-9.\s,-]*")


def _number(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    sign = "-" if text.startswith("-") else ""
    text = text.lstrip("-")
    if text.startswith("0."):
        text = text[1:]
    if text in ("", "0"):
        return "0"
    return sign + text


def _join(parts: list[str]) -> str:
    out = []
    last = ""
    for part in parts:
        if part.isalpha():
            last = ""
        else:
            # "1.5.5" is 1.5 then .5, and "1-2" is 1 then -2.
            if last and not part.startswith("-") and not (part.startswith(".") and "." in last):
                out.append(" ")
            last = part
        out.append(part)
    return "".join(out)


def relative_path(d: str) -> str:
    """Rewrites absolute M/L/Z path data as relative moves and lines.

    Decimal keeps each delta exact, so the points do not move. Small deltas
    are shorter and repeat more, which gzip rewards.
    """
    if _SIMPLE_PATH.fullmatch(d) is None:
        return d
    tokens = _TOKEN.findall(d)
    parts: list[str] = []
    x = y = start_x = start_y = None
    command = None
    # The command that a bare pair continues: "M" continues as an absolute line.
    implicit = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "Z":
            parts.append("z")
            x, y = start_x, start_y
            implicit = None
            i += 1
            continue
        if token in ("M", "L"):
            command = token
            i += 1
            continue
        if command is None or (command == "L" and x is None) or i + 1 >= len(tokens) or tokens[i + 1] in "MLZ":
            raise ValueError(f"path data that does not start with M or has an unpaired coordinate: {d[:40]}")
        nx, ny = Decimal(token), Decimal(tokens[i + 1])
        i += 2
        if command == "M":
            if x is None:
                parts += ["M", _number(nx), _number(ny)]
                implicit = "M"
            else:
                parts += ["m", _number(nx - x), _number(ny - y)]
                implicit = "l"
            start_x, start_y = nx, ny
            command = "L"
        else:
            if implicit != "l":
                parts.append("l")
                implicit = "l"
            parts += [_number(nx - x), _number(ny - y)]
        x, y = nx, ny
    return _join(parts)


def minify(svg: str) -> str:
    svg = re.sub(r"<\?xml.*?\?>", "", svg, flags=re.DOTALL)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.DOTALL)
    # A URL parser drops newlines, which would join two numbers.
    svg = re.sub(r"\s+", " ", svg).strip()
    if "<text" not in svg:
        svg = re.sub(r">\s+<", "><", svg)
    # Single quotes need no escape in the double-quoted src.
    svg = re.sub(r"=\"([^\"']*)\"", r"='\1'", svg)
    return re.sub(r"(\sd=')([^']*)(')", lambda m: m.group(1) + relative_path(m.group(2)) + m.group(3), svg)


def escape(svg: str) -> str:
    """Escapes only what the data: URL or the attribute would misread.

    % starts an escape, # starts a fragment, " ends the attribute, and & starts
    an HTML character reference. Controls and non-ASCII go as UTF-8 escapes.
    """
    out = []
    for char in svg:
        code = ord(char)
        if char in '%#"&' or code < 0x20 or code >= 0x7F:
            out.append("".join(f"%{byte:02X}" for byte in char.encode()))
        else:
            out.append(char)
    return "".join(out)


def data_url_body(svg: str) -> str:
    return escape(minify(svg))
