"""Checks the packed front-face SVG that the web page shows from a data: URL."""

from decimal import Decimal
import importlib.util
from pathlib import Path
import re
import unittest
from urllib.parse import unquote
import xml.etree.ElementTree as ET


ROOT = Path(__file__).parents[2]
COMPONENT = ROOT / "components" / "button_config"
FACE_SVG = ROOT / "docs" / "readme-assets" / "case-front-face.svg"
INIT = (COMPONENT / "__init__.py").read_text()
PAGE = (COMPONENT / "button_config_page.h").read_text()
PREVIEW = (ROOT / "scripts" / "preview-buttons-page.py").read_text()

_SPEC = importlib.util.spec_from_file_location("face_svg", COMPONENT / "face_svg.py")
face_svg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(face_svg)

_TOKEN = re.compile(r"[MmLlZz]|-?(?:\d+\.?\d*|\.\d+)")


def absolute_points(d: str) -> list:
    """Returns the absolute points of M/m/L/l/Z/z path data, exact in Decimal."""
    points = []
    tokens = _TOKEN.findall(d)
    x = y = start_x = start_y = None
    command = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in "Zz":
            points.append("Z")
            x, y = start_x, start_y
            i += 1
            continue
        if token in "MmLl":
            command = token
            i += 1
            continue
        px, py = Decimal(tokens[i]), Decimal(tokens[i + 1])
        i += 2
        if command in "ml" and x is not None:
            px, py = x + px, y + py
        x, y = px, py
        if command in "Mm":
            start_x, start_y = x, y
            points.append(("M", x, y))
            # A bare pair after a move is a line of the same kind.
            command = "L" if command == "M" else "l"
        else:
            points.append(("L", x, y))
    return points


class FaceSvgEmbedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = FACE_SVG.read_text()
        self.embed = face_svg.data_url_body(self.source)

    def test_the_embed_escapes_only_what_the_url_or_attribute_would_misread(self) -> None:
        # Every % starts an escape, and nothing that ends the attribute or the URL is raw.
        self.assertIsNone(re.search(r"%(?![0-9A-F]{2})", self.embed))
        for char in '#"&\n\r\t':
            self.assertNotIn(char, self.embed)
        self.assertTrue(all(0x20 <= ord(char) < 0x7F for char in self.embed))
        # Plain text stays plain, which is what makes it small.
        self.assertIn(" ", self.embed)
        self.assertIn("<svg xmlns='http://www.w3.org/2000/svg'", self.embed)
        self.assertLess(len(self.embed), len(self.source))

    def test_the_embed_decodes_to_the_same_drawing(self) -> None:
        decoded = unquote(self.embed)
        root = ET.fromstring(decoded)
        source_root = ET.fromstring(self.source)
        for attribute in ("viewBox", "width", "height"):
            self.assertEqual(root.get(attribute), source_root.get(attribute))
        before = re.findall(r'\sd="([^"]*)"', self.source)
        after = re.findall(r"\sd='([^']*)'", decoded)
        self.assertEqual(len(after), len(before))
        for old, new in zip(before, after):
            # Relative data is a rewrite, not a rounding: each point is exact.
            self.assertEqual(absolute_points(new), absolute_points(old))
        self.assertLess(sum(map(len, after)), sum(map(len, before)))
        def styles(tree: ET.Element) -> list:
            return [re.sub(r"\s+", " ", el.text or "").strip() for el in tree.iter() if el.tag.endswith("style")]
        self.assertEqual(styles(root), styles(source_root))

    def test_the_minifier_drops_declarations_comments_and_tag_whitespace(self) -> None:
        text = ('<?xml version="1.0"?>\n<!-- generated -->\n<svg viewBox="0 0 10 10">\n'
                '  <path d="M1 0.5 L2 3 L-0.5 1.5Z M4 4 L5 5"/>\n</svg>\n')
        self.assertEqual(face_svg.minify(text), "<svg viewBox='0 0 10 10'><path d='M1 .5l1 2.5-2.5-1.5zm3 3.5 1 1'/></svg>")

    def test_unsupported_path_data_stays_as_it_is(self) -> None:
        self.assertEqual(face_svg.relative_path("M0 0 C1 1 2 2 3 3"), "M0 0 C1 1 2 2 3 3")
        self.assertEqual(face_svg.relative_path("m1 1 l2 2"), "m1 1 l2 2")

    def test_the_page_and_the_preview_share_the_encoder(self) -> None:
        self.assertIn('<img src="data:image/svg+xml,__CASE_FRONT_FACE_SVG__"', PAGE)
        self.assertIn("from .face_svg import data_url_body", INIT)
        self.assertIn('svg = data_url_body(svg_path.read_text(encoding="utf-8"))', INIT)
        self.assertIn('ROOT / "components" / "button_config" / "face_svg.py"', PREVIEW)
        self.assertIn('svg = face_svg.data_url_body(CASE_FRONT_FACE.read_text(encoding="utf-8"))', PREVIEW)
        for text in (INIT, PREVIEW):
            self.assertNotIn("quote_from_bytes", text)
        # The module must load without esphome, or the preview cannot use it.
        self.assertNotIn("esphome", (COMPONENT / "face_svg.py").read_text().split('"""', 2)[2])


if __name__ == "__main__":
    unittest.main()
