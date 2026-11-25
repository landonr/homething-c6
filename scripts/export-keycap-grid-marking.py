#!/usr/bin/env python3
"""Export 1:1 legend artwork and a placement guide for the breakaway cap grid."""

import argparse
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "case"))

from build123d import ExportSVG, Pos, Rot, Unit  # noqa: E402

from model.cap_grid import keycap_grid, keycap_grid_layout  # noqa: E402
from model.cap_marks import fitted_mark, flat_faces_at, safe_area  # noqa: E402

OUT_DIR = ROOT / "case" / "export" / "keycap-grid-marking"
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def svg_document(exporter, width, height, margin=0):
    """Set the canvas from the part envelope without adding any geometry."""
    stream = BytesIO()
    exporter.write(stream)
    svg = ET.fromstring(stream.getvalue())
    page_width = width + 2 * margin
    page_height = height + 2 * margin
    svg.set("width", f"{page_width:.6f}mm")
    svg.set("height", f"{page_height:.6f}mm")
    svg.set("viewBox", f"{-margin:g} {-margin:g} {page_width:.6f} {page_height:.6f}")
    return ET.ElementTree(svg)


def marking_files(out_dir, converter):
    grid = keycap_grid()
    bounds = grid.bounding_box()
    _, slots = keycap_grid_layout()
    marks = ExportSVG(unit=Unit.MM)
    guide = ExportSVG(unit=Unit.MM)
    guide.add_layer("placement", line_color=(92, 106, 123), line_weight=0.12)
    guide.add_layer("marking-safe-area", line_color=(20, 125, 112), line_weight=0.07)

    # The marking view flips the printed part about X, then uses SVG's Y-down axis.
    face_up = Pos(-bounds.min.X, bounds.min.Y) * Rot(180, 0, 0)
    flat_faces = flat_faces_at(grid, 0)
    for face, _ in flat_faces:
        guide.add_shape([face_up * wire for wire in face.wires()], layer="placement")

    labels = []
    seen = set()
    for index, (ref, x, y) in enumerate(slots, 1):
        area = face_up * safe_area(flat_faces, x, y, ref)
        guide.add_shape(area.outer_wire(), layer="marking-safe-area")
        x -= bounds.min.X
        y -= bounds.min.Y
        spare = ref in seen
        layer = f"slot-{index}-{ref}"
        for exporter in (marks, guide):
            exporter.add_layer(layer, fill_color=(0, 0, 0), line_color=None)
        faces = fitted_mark(ref, spare, Pos(x, -y), area)
        marks.add_shape(faces, layer=layer)
        guide.add_shape(faces, layer=layer)
        labels.append((x, y, f"{ref} spare" if spare else ref))
        seen.add(ref)

    width, height = bounds.size.X, bounds.size.Y
    svg = svg_document(marks, width, height)
    margin = 0.3
    placement = svg_document(guide, width, height, margin=margin)
    placement.getroot().insert(0, ET.Element(f"{{{SVG_NS}}}rect", {
        "x": f"{-margin:g}",
        "y": f"{-margin:g}",
        "width": f"{width + 2 * margin:.6f}",
        "height": f"{height + 2 * margin:.6f}",
        "fill": "#fff",
    }))
    for x, y, label in labels:
        text = ET.SubElement(placement.getroot(), f"{{{SVG_NS}}}text", {
            "x": f"{x:.6f}",
            "y": f"{y + 4.3:.6f}",
            "text-anchor": "middle",
            "font-family": "sans-serif",
            "font-size": "0.9",
            "fill": "#46566b",
        })
        text.text = label

    with TemporaryDirectory(dir=out_dir) as tmp:
        tmp = Path(tmp)
        legend_svg = tmp / "keycap-grid-legends.svg"
        legend_pdf = tmp / "keycap-grid-legends.pdf"
        guide_svg = tmp / "keycap-grid-placement.svg"
        svg.write(legend_svg, encoding="utf-8", xml_declaration=True)
        placement.write(guide_svg, encoding="utf-8", xml_declaration=True)
        subprocess.run(
            [converter, "--format=pdf", "--output", str(legend_pdf), str(legend_svg)],
            check=True,
        )
        for artifact in (legend_svg, legend_pdf, guide_svg):
            path = out_dir / artifact.name
            artifact.replace(path)
            print(f"wrote {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    converter = shutil.which("rsvg-convert")
    if converter is None:
        parser.error("rsvg-convert from librsvg is required to export the PDF")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    marking_files(args.out_dir, converter)


if __name__ == "__main__":
    main()
