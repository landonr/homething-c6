"""Shells mate: the front and the back do not occupy the same space. Nothing else
covers it, because every other pass measures a shell against the board.

Interference: components the shells and the plate actually hit in 3D, each
one either a missing aperture or a keepout parameter set too tight.

Parts are sound: every part that gets exported is a valid solid and meshes to a
closed manifold. This is the only pass in the suite that looks at a mesh, and it
exists because everything else looks at the BRep instead. A shell can be torn
open in the STL, which is the artifact that ships and the only thing anyone ever
renders, while every probe in every other module reads the solid behind it and
reports clean.
"""

import math
from collections import Counter

import board

from .common import TOLERANCE, Problem, _volume


EXPORT_STEMS = {
    "front shell": "case-front",
    "back shell": "case-back",
    "button pad": "case-pad",
    "IR window": "ir-window",
}


def _stem(name):
    """The export file's stem for a part's display name. A failure that belongs to
    a whole part has no place on it to point at, so the part itself is what a
    viewer has to be handed, and the file it exports to is the one name both
    sides already agree on."""
    if name in EXPORT_STEMS:
        return EXPORT_STEMS[name]
    ref, _, kind = name.partition(" ")
    return f"cap-{ref.lower()}" if kind == "cap" else None


def shells_mate(front, back):
    """The two shells must not occupy the same space anywhere.

    Nothing else covers this. Every other pass measures a shell against the board,
    so a mating feature cut on the wrong side, or a fit that went negative, passes
    all of them and only shows up when the parts will not close.
    """
    overlap = front.intersect(back)
    fouled = _volume(overlap)
    if fouled <= TOLERANCE:
        return []
    return [Problem(f"front and back overlap by {fouled:.2f} mm3", box=overlap)]


MESH_TOLERANCE = 0.05
"""Linear deflection the soundness pass tessellates at. Finer than the STL
export's own default, so a mesh that closes here closes there too."""

VERTEX_PLACES = 5
"""Decimals a mesh vertex is rounded to before edges are matched up. The
tessellator emits the shared vertices of adjacent faces at the same coordinates,
so this only has to absorb the last bit or two of float noise; a sound part
reads exactly zero open edges at this rounding, which is what makes the count
worth asserting on."""


def _open_edges(shape):
    """How many edges of `shape`'s own mesh are not shared by exactly two
    triangles. Zero for a closed manifold, and anything else is a hole in it or
    a self-overlap.

    Raises whatever the tessellator raises. A solid malformed enough that it
    cannot be meshed at all throws out of here rather than returning a count,
    and parts_are_sound() reports that as its own kind of failure: a part that
    will not mesh is a part that will not export.
    """
    vertices, triangles = shape.tessellate(MESH_TOLERANCE)
    points = [
        tuple(round(c, VERTEX_PLACES) for c in (v.X, v.Y, v.Z)) for v in vertices
    ]
    counts = Counter()
    for tri in triangles:
        pts = [points[i] for i in tri]
        for a, b in ((pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])):
            if a != b:
                counts[frozenset((a, b))] += 1
    return sum(1 for shared in counts.values() if shared != 2)


def parts_are_sound(parts):
    """Every exported part is a valid solid and meshes to a closed manifold.

    The only pass here that reads a mesh rather than the BRep behind it, and the
    reason it exists is that the two can disagree in exactly the direction that
    matters. A keypad recess lofted through an unstable spline once came back as
    a single solid that BRepCheck called valid, that filled a plausible bounding
    box, and that every local probe in checks/keypad.py agreed with; the STL cut
    from it was torn wide open across the front face and was the only place the
    damage was visible. Nobody renders a BRep.

    Three readings per part. `is_valid` is BRepCheck and is the cheap one,
    catching a solid that is already malformed. The mesh count is the one that
    would have caught that recess: it walks the triangles and requires every
    edge to be shared by exactly two of them, which is the definition of the
    closed surface a printed part has to be. And the meshing is done inside a
    try, because a solid can be broken past the point of tessellating at all;
    that throws rather than returning a torn mesh, and an exception escaping
    here would take the whole pass down instead of reporting the part.
    """
    problems = []
    for name, shape in parts.items():
        part = _stem(name)
        if not shape.is_valid:
            problems.append(Problem(f"{name} is not a valid solid", part=part))
        if len(shape.solids()) < 1:
            problems.append(Problem(f"{name} has no solid in it at all", part=part))
        if shape.volume <= 0:
            problems.append(Problem(
                f"{name} has a volume of {shape.volume:.2f}", part=part
            ))
        try:
            loose = _open_edges(shape)
        except Exception as exc:
            problems.append(Problem(
                f"{name} will not mesh at all ({type(exc).__name__}): it cannot "
                "be exported, whatever the solid behind it says",
                part=part,
            ))
            continue
        if loose:
            problems.append(Problem(
                f"{name} meshes to {loose} open or non-manifold edges: the "
                "exported surface is torn, whatever the solid behind it says",
                part=part,
            ))
    return problems


def interference(shells):
    shells_box = shells.bounding_box()
    placements = [(ref, x, y) for ref, (x, y, _, _) in board.components().items()]
    placements.append(("ENC1", *board.wheel_center()))

    hits = []
    for solid in board.assembly_solids():
        box = solid.bounding_box()
        if box.min.Z >= shells_box.max.Z or box.max.Z <= shells_box.min.Z:
            continue
        overlap = shells.intersect(solid)
        volume = _volume(overlap)
        if volume <= TOLERANCE:
            continue
        center = box.center()
        ref = min(
            placements, key=lambda p: math.hypot(p[1] - center.X, p[2] - center.Y)
        )[0]
        hits.append((ref, volume, box.min.Z, box.max.Z))
    return hits
