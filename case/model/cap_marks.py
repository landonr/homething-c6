"""Shared cap and pad legend geometry for the deboss and marking artwork."""

from functools import partial
import math

from build123d import Kind, Pos, RegularPolygon, extrude, offset

import board
import params

from .legends import _legend_faces, legend_entry
from .stack import MERGE, cap_top

DIRECTION_ANGLES = {"SW4": 180, "SW6": 90, "SW8": 270, "SW10": 0}


def rounded_mark(radius, sides, angle):
    """Make a centered polygon outline with rounded outer and inner corners."""
    corner_radius = params.CAP_GRID_MARK_CORNER_R
    stroke = params.LEGEND_STROKE_W
    inner_radius = radius - stroke / math.cos(math.pi / sides)
    outer = RegularPolygon(radius, sides, rotation=angle, align=None).faces()[0]
    inner = RegularPolygon(inner_radius, sides, rotation=angle, align=None).faces()[0]
    outer = outer.fillet_2d(corner_radius, outer.vertices())
    inner = inner.fillet_2d(corner_radius - stroke, inner.vertices())
    center = outer.bounding_box().center()
    return [Pos(*(-center)) * face for face in outer.cut(inner).faces()]


def _mark_design(ref, spare):
    """Return a shape builder, its starting size, and its font glyph if any."""
    if spare:
        return partial(rounded_mark, sides=4, angle=0), params.CAP_GRID_MARK_DIAMOND_R, None
    if ref == "SW5":
        radius = params.CAP_GRID_MARK_SQUARE_W / math.sqrt(2)
        return partial(rounded_mark, sides=4, angle=45), radius, None
    if ref in DIRECTION_ANGLES:
        return (
            partial(rounded_mark, sides=3, angle=DIRECTION_ANGLES[ref]),
            params.CAP_GRID_MARK_TRIANGLE_R,
            None,
        )
    spec, size = legend_entry(ref)
    if ref == "SW2":
        spec = ("svg", "glyphs/mic-engraving.svg")
    if ref == "SW7":
        size = params.CAP_GRID_MARK_CIRCLE_SIZE
    elif ref in ("SW1", "SW2", "SW9", "SW11"):
        size = params.CAP_GRID_MARK_CONTROL_SIZE
    return (
        partial(_legend_faces, spec, stroke_width=mark_stroke_width(ref)),
        size,
        spec if isinstance(spec, str) else None,
    )


def mark_stroke_width(ref):
    return params.CAP_GRID_MARK_CONTROL_W if ref in ("SW9", "SW11") else params.LEGEND_STROKE_W


def mark_font_glyph(ref):
    return _mark_design(ref, spare=False)[2]


def flat_faces_at(part, z):
    """Return the faces and bounds on the specified horizontal plane."""
    faces = []
    for face in part.faces():
        box = face.bounding_box()
        if abs(box.min.Z - z) < 1e-6 and abs(box.max.Z - z) < 1e-6:
            faces.append((face, box))
    return faces


def flat_face_at(flat_faces, x, y, ref):
    """Find the unbroken flat face at this key position."""
    matches = []
    for face, box in flat_faces:
        center = box.center()
        if math.hypot(center.X - x, center.Y - y) < 1e-5 and not face.inner_wires():
            matches.append(face)
    if len(matches) != 1:
        raise ValueError(f"Expected one flat cap face for {ref}, found {len(matches)}")
    return matches[0]


def safe_area(flat_faces, x, y, ref):
    """Inset the actual flat face at this slot's center."""
    face = flat_face_at(flat_faces, x, y, ref)
    areas = offset(face, -params.CAP_GRID_MARK_CLEARANCE, kind=Kind.INTERSECTION).faces()
    if len(areas) != 1 or not areas[0].is_valid:
        raise ValueError(f"Could not inset the flat cap face for {ref}")
    return areas[0]


def fitted_mark(ref, spare, center, area):
    """Reduce the mark size if necessary and keep its stroke width."""
    build_mark, size, _ = _mark_design(ref, spare)
    for step in range(1 if ref == "SW3" else 12):
        marks = [center * face for face in build_mark(size * 0.98**step)]
        if marks and all(
            sum(part.area for part in mark.cut(area).faces()) < 1e-7 for mark in marks
        ):
            return marks
    raise ValueError(f"Engraving for {ref} does not fit its {params.CAP_GRID_MARK_CLEARANCE:g} mm inset")


def keytop_mark_faces(ref, blank):
    """Fit the artwork to the built keytop and project the marks to XY."""
    x, y = board.components()[ref][:2]
    top = cap_top(ref)
    area = safe_area(flat_faces_at(blank, top), x, y, ref)
    return fitted_mark(ref, False, Pos(x, y), Pos(0, 0, -top) * area)


def mark_cutters(ref, faces):
    """Extrude planar marks into cutters with the specified deboss depth."""
    top = cap_top(ref)
    return [
        extrude(Pos(0, 0, top + MERGE) * face, amount=MERGE + params.LEGEND_DEPTH,
                dir=(0, 0, -1))
        for face in faces
    ]
