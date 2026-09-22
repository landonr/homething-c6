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
import params

from build123d import Box, Pos

from model import shells
from model.stack import LAP_IN, SHELL_SEAM, SKIRT_BOTTOM, SKIRT_OUT
from model.support import front_support_cuts

from .common import TOLERANCE, Problem, _Crop, _volume


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


def side_seam_retention(front, back):
    """Read the printed skirt, catch and grip relief from the built shells."""
    problems = []
    board_box = board.board_profile().bounding_box()
    y = shells.side_catch_y()
    z0 = shells.side_catch_bottom()
    z = z0 + params.SIDE_CATCH_H / 2

    def probe(crop, label, centre, size, material):
        solid = Pos(*centre) * Box(*size)
        fraction = crop.fill_fraction(solid)
        if (material and fraction < 0.9) or (not material and fraction > 0.1):
            problems.append(Problem(
                f"{label} is {fraction:.0%} material, expected "
                f"{'solid' if material else 'open'}",
                box=solid,
            ))

    for side, edge, name in (
        (-1, board_box.min.X, "-X"),
        (1, board_box.max.X, "+X"),
    ):
        # Fixed sites inside the newly claimed material and interlock. Reading
        # the tunable itself here would let a weakened feature move its probe
        # along with it and give a vacuous pass.
        inner = edge + side * (params.BOARD_FIT - 0.1)
        board_gap = edge + side * 0.1
        pocket_x = edge + side * (SKIRT_OUT - 0.12)
        pocket_floor_x = edge + side * (
            params.BOARD_FIT - params.SIDE_SKIRT_THICKEN
            + params.SIDE_CATCH_WALL_MIN - 0.05
        )
        lap_face = edge + side * LAP_IN
        engaged = edge + side * (SKIRT_OUT - 0.08)
        lo_x = min(edge, lap_face) - params.WALL
        hi_x = max(edge, lap_face) + params.WALL
        lo_y = y - params.SIDE_CATCH_W / 2 - 2
        hi_y = y + params.SIDE_CATCH_W / 2 + 2
        front_crop = _Crop(front, (lo_x, lo_y, SKIRT_BOTTOM - 0.1),
                           (hi_x, hi_y, SHELL_SEAM + 0.1))
        back_crop = _Crop(back, (lo_x, lo_y, SKIRT_BOTTOM - 0.1),
                          (hi_x, hi_y, SHELL_SEAM + 0.1))
        probe(front_crop, f"{name} skirt stiffener", (inner, y - params.SIDE_CATCH_W / 2 - 0.7, z),
              (0.1, 0.2, 0.2), True)
        probe(front_crop, f"{name} board edge gap", (board_gap, y - params.SIDE_CATCH_W / 2 - 0.7, z),
              (0.1, 0.2, 0.2), False)
        probe(front_crop, f"{name} catch pocket mouth", (pocket_x, y, z),
              (0.2, 0.2, 0.2), False)
        probe(front_crop, f"{name} continuous pocket floor", (pocket_floor_x, y, z),
              (0.1, 0.2, 0.2), True)
        mouth_x = edge + side * (SKIRT_OUT - 0.05)
        floor_edge_x = edge + side * (
            SKIRT_OUT - params.SIDE_CATCH_POCKET_DEPTH + 0.05
        )
        for lip, lip_z in (
            ("lower", z0 + 0.06),
            ("upper", z0 + params.SIDE_CATCH_H - 0.06),
        ):
            probe(front_crop, f"{name} {lip} pocket bevel mouth", (mouth_x, y, lip_z),
                  (0.04, 0.12, 0.04), False)
            probe(front_crop, f"{name} {lip} pocket bevel floor", (floor_edge_x, y, lip_z),
                  (0.04, 0.12, 0.04), True)
        probe(front_crop, f"{name} interlock opening", (engaged, y, z),
              (0.08, 0.2, 0.08), False)
        probe(front_crop, f"{name} skirt beside pocket", (pocket_x, y - params.SIDE_CATCH_W / 2 - 0.7, z),
              (0.2, 0.2, 0.2), True)
        probe(back_crop, f"{name} engaged detent", (engaged, y, z),
              (0.08, 0.2, 0.08), True)
        probe(back_crop, f"{name} lower release ramp", (engaged, y, z0 + params.SIDE_CATCH_FIT + 0.08),
              (0.08, 0.2, 0.08), False)
        probe(back_crop, f"{name} upper insertion ramp", (engaged, y, z0 + params.SIDE_CATCH_H - params.SIDE_CATCH_FIT - 0.08),
              (0.08, 0.2, 0.08), False)
        land_z = z0 + params.SIDE_CATCH_H + params.SIDE_CATCH_UPPER_LAND_MIN
        lap_x = edge + side * (LAP_IN + params.SKIRT_T / 2)
        probe(front_crop, f"{name} upper skirt land", (pocket_x, y, land_z),
              (0.2, 0.2, 0.08), True)
        probe(back_crop, f"{name} raised back lap", (lap_x, y, land_z),
              (0.2, 0.2, 0.08), True)

    end_x = board_box.center().X
    end_y = board_box.min.Y - SKIRT_OUT
    # Keep this below the USB opening; moving the side pocket upward does not
    # move the grip-end wall site whose relief this probes.
    end_z = SKIRT_BOTTOM + 1.7
    end_crop = _Crop(
        front,
        (end_x - 1, end_y - 0.5, SKIRT_BOTTOM - 0.1),
        (end_x + 1, end_y + 1, SHELL_SEAM + 0.1),
    )
    probe(end_crop, "grip-end skirt relief", (end_x, end_y + params.GRIP_SKIRT_RELIEF / 2, end_z),
          (0.2, 0.08, 0.2), False)
    probe(end_crop, "grip-end skirt behind relief", (end_x, end_y + params.GRIP_SKIRT_RELIEF + 0.18, end_z),
          (0.2, 0.08, 0.2), True)
    return problems


def side_skirt_lead_ins(front):
    """The support-break ramps remove the complete reinforced skirt width."""
    problems = []
    board_box = board.board_profile().bounding_box()
    middle_y = board_box.center().Y
    runs = front_support_cuts()
    for side, edge, name in (
        (-1, board_box.min.X, "-X"),
        (1, board_box.max.X, "+X"),
    ):
        crossing = [
            run for run in runs
            if (run.bounding_box().center().X < board_box.center().X) == (side < 0)
            and run.bounding_box().min.Y < middle_y < run.bounding_box().max.Y
        ]
        if len(crossing) != 1:
            problems.append(Problem(
                f"{name} has {len(crossing)} support runs at the board midpoint, "
                "so its lead-in has no unambiguous edge"
            ))
            continue
        edge_y = crossing[0].bounding_box().max.Y
        height = crossing[0].bounding_box().max.Z - SKIRT_BOTTOM
        run_length = height / math.tan(math.radians(params.SKIRT_LEAD_ANGLE))
        z = SKIRT_BOTTOM + 0.35
        cropped = _Crop(
            front,
            (edge - params.WALL - 1, edge_y - 0.1, SKIRT_BOTTOM - 0.1),
            (edge + params.WALL + 1, edge_y + run_length + 0.7, SHELL_SEAM + 0.1),
        )
        for position, radial in (
            ("outer", SKIRT_OUT - 0.15),
            ("reinforced inner", params.BOARD_FIT - 0.1),
        ):
            x = edge + side * radial
            for label, y, should_be_material in (
                ("ramp", edge_y + run_length / 2, False),
                ("skirt after ramp", edge_y + run_length + 0.35, True),
            ):
                probe = Pos(x, y, z) * Box(0.12, 0.12, 0.12)
                filled = cropped.fill_fraction(probe)
                if (should_be_material and filled < 0.9) or (
                    not should_be_material and filled > 0.1
                ):
                    problems.append(Problem(
                        f"{name} {position} {label} is {filled:.0%} material, "
                        f"expected {'solid' if should_be_material else 'open'}",
                        box=probe,
                    ))
    return problems


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
