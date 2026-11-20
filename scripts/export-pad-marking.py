#!/usr/bin/env python3
"""Write the key legend artwork of the one-piece TPU pad, for silkscreen or
laser marking on the blank pad.

PCBWay marks a part from an Ai or SVG artwork file and a 2D drawing (DWG or
DXF) that gives the size and placement. This script writes three files:

- pad-legends.svg: the legends alone, at true scale, for the printer.
- pad-marking.dxf: the lobe and key top outlines, the legends and a centre
  mark for each key, in mm, with the origin at the pad's lower left corner.
- pad-marking-drawing.svg: the same plan with labels, the key centres and the
  key top heights, for a person to read.

Every shape and position comes from the case model at run time, so the files
match the legends that `c6remote-case-pad-tpu.stl` debosses."""

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))

from face_plan import ROOT, fmt  # noqa: E402

sys.path.insert(0, str(ROOT / "case"))

from build123d import ExportDXF, ExportSVG, Polyline, Pos, Unit  # noqa: E402

import board  # noqa: E402
import params  # noqa: E402
from model.caps import cap_body, cap_outline  # noqa: E402
from model.keypad import pad_lobe_face, pad_lobes  # noqa: E402
from model.legends import _legend_faces, legend_entry  # noqa: E402
from model.stack import cap_top  # noqa: E402

OUT_DIR = ROOT / "case" / "export" / "pad-marking"
KEYS = tuple(f"SW{i}" for i in range(1, 12))
CENTER_MARK = 1.0

# Drawing sheet, px per mm and margins in px. Nothing here describes the part.
SCALE = 6.0
MARGIN = 40.0
TABLE_W = 360.0


def plan():
    """Everything the three files draw, in the case frame."""
    parts = board.components()
    # The built outline, tabs included, and not pad_lobe_box(), which stops
    # inside the tabs.
    lobes = {}
    for name, *_ in pad_lobes():
        box = pad_lobe_face(name).bounding_box()
        lobes[name] = (box.min.X, box.min.Y, box.max.X, box.max.Y)
    tops = {ref: cap_top(ref) for ref in KEYS}
    low = min(tops.values())
    keys = []
    for ref in KEYS:
        x, y = parts[ref][:2]
        spec, size = legend_entry(ref)
        keys.append({
            "ref": ref,
            "x": x,
            "y": y,
            "size": size,
            "rise": tops[ref] - low,
            "legend": [Pos(x, y) * face for face in _legend_faces(spec, size)],
            "outline": cap_outline(cap_body(ref), x, y),
        })
    x0 = min(box[0] for box in lobes.values())
    y0 = min(box[1] for box in lobes.values())
    return lobes, keys, (x0, y0)


def shifted(shape, origin):
    return Pos(-origin[0], -origin[1]) * shape


def sample(wire, n=240):
    """A wire as points, so curved glyph edges stay curved in the drawing."""
    return [(p.X, p.Y) for p in (wire.position_at(i / n) for i in range(n))]


def write_svg(lobes, keys, origin, path):
    svg = ExportSVG(unit=Unit.MM, line_weight=0)
    # An unpainted frame at the pad's bounding box, so the SVG canvas starts at
    # the same corner as the DXF and the artwork keeps its placement.
    svg.add_layer("frame", fill_color=None, line_color=None)
    x1 = max(box[2] for box in lobes.values()) - origin[0]
    y1 = max(box[3] for box in lobes.values()) - origin[1]
    svg.add_shape(Polyline((0, 0), (x1, 0), (x1, y1), (0, y1), close=True), layer="frame")
    svg.add_layer("legend", fill_color=(0, 0, 0), line_color=None)
    for key in keys:
        svg.add_shape([shifted(face, origin) for face in key["legend"]], layer="legend")
    svg.write(path)


def write_dxf(lobes, keys, origin, path):
    dxf = ExportDXF(unit=Unit.MM)
    for layer in ("outline", "keytop", "legend", "center"):
        dxf.add_layer(layer)
    for name in lobes:
        dxf.add_shape(shifted(pad_lobe_face(name).outer_wire(), origin), layer="outline")
    for key in keys:
        dxf.add_shape(shifted(Polyline(*key["outline"], close=True), origin), layer="keytop")
        for face in key["legend"]:
            dxf.add_shape([shifted(w, origin) for w in face.wires()], layer="legend")
        x, y, h = key["x"], key["y"], CENTER_MARK
        for a, b in (((x - h, y), (x + h, y)), ((x, y - h), (x, y + h))):
            dxf.add_shape(shifted(Polyline(a, b), origin), layer="center")
    dxf.write(path)


def write_drawing(lobes, keys, origin, path):
    """A plan a person reads: outlines, legends, refs, centres and heights."""
    x0, y0 = origin
    x1 = max(box[2] for box in lobes.values())
    y1 = max(box[3] for box in lobes.values())
    plan_w, plan_h = (x1 - x0) * SCALE, (y1 - y0) * SCALE
    sheet_w = plan_w + 2 * MARGIN + TABLE_W
    sheet_h = plan_h + 2 * MARGIN

    def P(x, y):
        return MARGIN + (x - x0) * SCALE, MARGIN + (y1 - y) * SCALE

    def path_of(points):
        pts = [P(*p) for p in points]
        return "M" + " L".join(f"{fmt(a, 2)} {fmt(b, 2)}" for a, b in pts) + " Z"

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(sheet_w)} {fmt(sheet_h)}" '
        f'width="{fmt(sheet_w)}" height="{fmt(sheet_h)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        "<style>.o{fill:none;stroke:#555;stroke-width:1.2}.k{fill:none;stroke:#999;stroke-width:0.8}"
        ".l{fill:#000;stroke:none}.c{stroke:#d24a12;stroke-width:0.8}"
        "text{font-family:'DejaVu Sans',Verdana,sans-serif;fill:#222}"
        ".r{font-size:11px;font-weight:700}.t{font-size:11px}.h{font-size:12px;font-weight:700}"
        ".m{font-size:11px;font-family:'DejaVu Sans Mono',Menlo,monospace}</style>",
    ]
    for name in lobes:
        out.append(f'<path class="o" d="{path_of(sample(pad_lobe_face(name).outer_wire(), 600))}"/>')
    for key in keys:
        out.append(f'<path class="k" d="{path_of(key["outline"])}"/>')
        for face in key["legend"]:
            d = " ".join(path_of(sample(wire)) for wire in face.wires())
            out.append(f'<path class="l" fill-rule="evenodd" d="{d}"/>')
        cx, cy = P(key["x"], key["y"])
        h = CENTER_MARK * SCALE
        out.append(f'<path class="c" d="M{fmt(cx - h, 1)} {fmt(cy, 1)} H{fmt(cx + h, 1)} '
                   f'M{fmt(cx, 1)} {fmt(cy - h, 1)} V{fmt(cy + h, 1)}"/>')
        out.append(f'<text class="r" x="{fmt(cx, 1)}" y="{fmt(cy - 5.6 * SCALE, 1)}" '
                   f'text-anchor="middle">{key["ref"]}</text>')

    tx = plan_w + 2 * MARGIN
    lines = [
        ("h", "Key legend placement, one-piece TPU pad"),
        ("t", "Units: mm. Origin: lower left corner of the pad."),
        ("t", "Print or engrave on the blank pad, top view."),
        ("t", ""),
        ("m", "Key   centre x  centre y  size   top"),
    ]
    for key in keys:
        lines.append(("m", f"{key['ref']:<5} {key['x'] - x0:9.2f} {key['y'] - y0:9.2f} "
                           f"{key['size']:5.1f}  +{key['rise']:.2f}"))
    step = max(k["rise"] for k in keys)
    lines.append(("t", ""))
    if step < 0.01:
        lines.append(("t", "Every key top is flat and at one level."))
    else:
        raised = ", ".join(k["ref"] for k in keys if k["rise"] > step / 2)
        lines += [
            ("t", f"Each key top is flat. {raised}"),
            ("t", f"stand {step:.2f} mm higher than the other keys."),
        ]
    lines.append(("t", f"Legend line width {params.LEGEND_STROKE_W} mm."))
    for i, (klass, text) in enumerate(lines):
        out.append(f'<text class="{klass}" x="{fmt(tx, 1)}" y="{fmt(MARGIN + 16 * (i + 1), 1)}" '
                   f'xml:space="preserve">{escape(text)}</text>')
    out.append("</svg>\n")
    Path(path).write_text("\n".join(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out-dir", help="where to write the files")
    args = ap.parse_args()
    out_dir = Path(args.out_dir or OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    lobes, keys, origin = plan()
    write_svg(lobes, keys, origin, out_dir / "pad-legends.svg")
    write_dxf(lobes, keys, origin, out_dir / "pad-marking.dxf")
    write_drawing(lobes, keys, origin, out_dir / "pad-marking-drawing.svg")
    for name in ("pad-legends.svg", "pad-marking.dxf", "pad-marking-drawing.svg"):
        print(f"wrote {out_dir / name}")


if __name__ == "__main__":
    main()
