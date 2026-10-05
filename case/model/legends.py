"""What each keycap says: resolving params.LEGENDS' three forms, setting a
string in LEGEND_FONT or importing an SVG under glyphs/, and turning either
into the solids debossed out of a cap's top face."""

from pathlib import Path

from build123d import (
    Align, Compound, Kind, Pos, Side, Sketch, Text, extrude, import_svg, make_face, offset,
)

import board
import params

from .stack import CAP_TOP, HERE, MERGE


def _bounds(shapes):
    box = shapes[0].bounding_box()
    for shape in shapes[1:]:
        box = box.add(shape.bounding_box())
    return box


def legend_entry(ref):
    """(spec, size) for one cap, resolving LEGENDS' three forms.

    A two-tuple starting with "svg" is artwork; any other two-tuple is a spec
    paired with its own size. Anything else is a bare spec at LEGEND_SIZE. See
    params.LEGENDS for why a size ever differs from the default.
    """
    entry = params.LEGENDS[ref]
    if isinstance(entry, tuple) and len(entry) == 2 and entry[0] != "svg":
        return entry
    return entry, params.LEGEND_SIZE


def legend_size(ref):
    """The size one cap's legend is set or scaled at. What check.py measures
    the flat top against, rather than LEGEND_SIZE, now that a cap can carry
    its own."""
    return legend_entry(ref)[1]


def _outline_band(face, spec):
    """A glyph face's inward outline, one LEGEND_STROKE_W wide, as faces.

    The band's outer edge is the glyph's own ink edge. A glyph too thin to hold
    an interior offset raises or returns nothing in build123d's offset, which
    is turned into one clear error rather than a silent fill.
    """
    w = params.LEGEND_STROKE_W
    try:
        inner = offset(face, -w, kind=Kind.INTERSECTION).faces()
    except (ValueError, RuntimeError):
        # A circle's single-edge wire makes INTERSECTION return a null shape;
        # ARC is the same offset on a smooth outline.
        try:
            inner = [make_face(face.outer_wire().offset_2d(-w, kind=Kind.ARC))]
        except (ValueError, RuntimeError) as err:
            raise ValueError(
                f"legend {spec!r} is too thin to outline at LEGEND_STROKE_W={w}: "
                f"use a solid glyph or an SVG stroke ({err})"
            ) from err
    if not inner:
        raise ValueError(
            f"legend {spec!r} is too thin to outline at LEGEND_STROKE_W={w}: "
            "use a solid glyph or an SVG stroke"
        )
    return list((face - Sketch(obj=Compound(list(inner)))).faces())


def _stroke_faces(wires, size):
    """Centerline wires thickened to LEGEND_STROKE_W, as non-overlapping faces.

    Scaled first so the centerline's longest side is size less one stroke
    width, which makes the inked result about `size` on its longest side, then
    thickened in mm so the line weight does not depend on size. Open wires get
    round caps.
    """
    w = params.LEGEND_STROKE_W
    box = _bounds(wires)
    k = (size - w) / max(box.size.X, box.size.Y)
    faces = []
    for wire in wires:
        wire = wire.scale(k)
        if wire.is_closed:
            faces.append(
                make_face(wire.offset_2d(w / 2, kind=Kind.ARC))
                - make_face(wire.offset_2d(-w / 2, kind=Kind.ARC))
            )
        else:
            faces.append(
                make_face(wire.offset_2d(w / 2, kind=Kind.ARC, side=Side.BOTH, closed=True))
            )
    faces = [f for fs in faces for f in (fs.faces() if hasattr(fs, "faces") else [fs])]
    if len(faces) > 1:
        faces = faces[0].fuse(*faces[1:]).faces()
    return list(faces)


def _legend_faces(spec, size):
    """The legend as stroke faces on the XY plane, centred on its own ink.

    Every legend is a line of LEGEND_STROKE_W. A string is the inward outline
    of each font glyph, so the interior stays standing. An SVG is a set of
    centerline paths thickened to the same weight.

    Centred on the ink rather than left where either source puts it. Text
    centres on the font's own layout box, which carries the ascender and
    descender whether the glyph reaches them or not, so a geometric shape
    lands a few tenths low; import_svg centres on the document. Both are
    brought back onto the ink's own bounding box here, so a legend sits in
    the middle of the cap whichever branch built it.
    """
    if isinstance(spec, str):
        glyphs = Text(spec, font_size=size, font_path=str(params.LEGEND_FONT)).faces()
        faces = [band for glyph in glyphs for band in _outline_band(glyph, spec)]
    else:
        kind, name = spec
        if kind != "svg":
            raise ValueError(f"unknown legend spec {spec!r}")
        path = Path(name)
        art = import_svg(path if path.is_absolute() else HERE / path, align=Align.CENTER)
        wires = list(art.wires() if hasattr(art, "wires") else art)
        faces = _stroke_faces(wires, size) if wires else []

    if not faces:
        return []
    box = _bounds(faces)
    return [Pos(*(-v for v in box.center())) * face for face in faces]


def legend_solids(ref, x=None, y=None):
    """What is debossed into one cap's top face, as one solid per glyph.

    A list rather than a single shape: Text hands back a face per character and
    an SVG a face per closed path, and cutting with a compound of disjoint
    solids leaves the cut volumes behind.

    No rotation. The frame's +Y is away from the grip, so a legend built on the
    XY plane already reads the right way up with the grip end toward you.

    Public because check.py measures these rather than inferring a legend from
    the finished cap: an entry that resolves to no faces at all, a missing
    glyph or an empty string, builds a perfectly good blank cap and nothing
    else in the model would notice.
    """
    if x is None or y is None:
        x, y = board.components()[ref][:2]
    spec, size = legend_entry(ref)
    return [
        extrude(Pos(x, y, CAP_TOP + MERGE) * face, amount=MERGE + params.LEGEND_DEPTH,
                dir=(0, 0, -1))
        for face in _legend_faces(spec, size)
    ]
