"""Board deflection stops fused to the back shell side walls."""

import math

from build123d import Box, Cylinder, Face, Pos, fillet, loft

import board
import params

from .hardware import closure_point, mount_points
from .backform import back_form
from .shape import _cut, _fuse, _isect, _offset_face, _slab
from .stack import BOARD_TOP, LAP_IN, MERGE, SHELL_BACK, SKIRT_OUT, SUPPORT_TOP


def support_top():
    return SUPPORT_TOP


def support_case_envelope(inset=0.0):
    """Return the back case envelope with an optional uniform inside offset."""
    plan = _offset_face(params.BOARD_FIT + params.WALL - inset)
    return _isect(
        _slab(plan, SHELL_BACK, BOARD_TOP),
        back_form(inset, inset, inset),
    )


def support_obstacles(clearance=params.SUPPORT_CLEARANCE):
    """Clearance volumes for bottom courtyards and board screw heads."""
    reach = LAP_IN + MERGE + params.SUPPORT_BEARING
    z0 = support_top() - reach * math.tan(
        math.radians(params.SUPPORT_UNDER_ANGLE)
    ) - MERGE
    z1 = 0.1
    out = []
    board_box = board.board_profile().bounding_box()
    def through_wall(name, solid, x0, y0, x1, y1, wall_side=None):
        cuts = [solid]
        if wall_side in ("-x", "both") or x0 < board_box.min.X + params.SUPPORT_BEARING:
            outer = board_box.min.X - LAP_IN - 2 * MERGE
            x1 = max(
                x1,
                board_box.min.X
                + params.SUPPORT_BEARING
                + MERGE,
            )
            cuts.append(
                Pos((outer + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
                * Box(x1 - outer, y1 - y0, z1 - z0)
            )
        if wall_side in ("+x", "both") or x1 > board_box.max.X - params.SUPPORT_BEARING:
            outer = board_box.max.X + LAP_IN + 2 * MERGE
            x0 = min(
                x0,
                board_box.max.X
                - params.SUPPORT_BEARING
                - MERGE,
            )
            cuts.append(
                Pos((x0 + outer) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
                * Box(outer - x0, y1 - y0, z1 - z0)
            )
        out.append((name, _fuse(*cuts)))

    for ref, (x0, y0, x1, y1, side) in board.courtyards().items():
        if side != "bottom":
            continue
        solid = Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(
            x1 - x0 + 2 * clearance, y1 - y0 + 2 * clearance, z1 - z0
        )
        through_wall(
            ref,
            solid,
            x0 - clearance,
            y0 - clearance,
            x1 + clearance,
            y1 + clearance,
            "both" if ref == "D1" else None,
        )
    assembly_obstacles = []
    for index, solid in enumerate(board.assembly_solids(), 1):
        box = solid.bounding_box()
        if box.min.Z >= support_top():
            continue
        x0 = box.min.X - clearance
        y0 = box.min.Y - clearance
        x1 = box.max.X + clearance
        y1 = box.max.Y + clearance
        assembly_obstacles.append((index, x0, y0, x1, y1))

    for index, x0, y0, x1, y1 in assembly_obstacles:
        reaches_wall = (
            x0 < board_box.min.X + params.SUPPORT_BEARING
            or x1 > board_box.max.X - params.SUPPORT_BEARING
        )
        if reaches_wall:
            middle = (y0 + y1) / 2
            matching_break = params.SCREW_HEAD_D + 2 * clearance
            half = max((y1 - y0) / 2, matching_break / 2)
            y0, y1 = middle - half, middle + half
        obstacle = Pos(
            (x0 + x1) / 2,
            (y0 + y1) / 2,
            (z0 + z1) / 2,
        ) * Box(x1 - x0, y1 - y0, z1 - z0)
        through_wall(f"through-board solid {index}", obstacle, x0, y0, x1, y1)
    closure = closure_point()
    # By refdes, not by loop index, so a check message and a feature id both
    # name the hole a reader can find on the board.
    refs = board.mounting_hole_refs()
    for x, y in mount_points():
        if (x, y) == closure:
            continue
        solid = Pos(x, y, (z0 + z1) / 2) * Cylinder(
            params.SCREW_HEAD_D / 2 + clearance, z1 - z0
        )
        radius = params.SCREW_HEAD_D / 2 + clearance
        through_wall(
            f"mount {refs[(x, y)]}", solid, x - radius, y - radius, x + radius, y + radius
        )
    return out


def _uncut_support():
    """Flat board ledge with a filleted inboard edge and printable underside."""
    top = support_top()
    inner = -params.SUPPORT_BEARING
    outer = LAP_IN + MERGE
    depth = (outer - inner) * math.tan(
        math.radians(params.SUPPORT_UNDER_ANGLE)
    )
    underside_void = loft(
        [
            Pos(0, 0, top - depth - MERGE)
            * Face(_offset_face(outer + MERGE).outer_wire()),
            Pos(0, 0, top + MERGE) * Face(_offset_face(inner).outer_wire()),
        ],
        ruled=True,
    )
    support = _cut(
        _slab(_offset_face(outer), top - depth, top),
        underside_void,
    )
    board_box = board.board_profile().bounding_box()
    inner_edges = [
        edge
        for edge in support.edges()
        if edge.bounding_box().min.Z > top - MERGE
        and edge.bounding_box().size.Y > board_box.size.Y / 2
        and board_box.min.X < edge.center().X < board_box.max.X
    ]
    if len(inner_edges) != 2:
        raise ValueError(f"expected two support inner edges, found {len(inner_edges)}")
    return fillet(inner_edges, params.SUPPORT_INNER_R)


def support_fragments():
    """Surviving obstacle-cut runs, including short fragments for checks."""
    cut = _cut(_uncut_support(), *(solid for _, solid in support_obstacles()))
    box = board.board_profile().bounding_box()
    outer_reach = LAP_IN + MERGE
    clip_bearing = params.SUPPORT_BEARING
    z0 = support_top() - (outer_reach + params.SUPPORT_BEARING) * math.tan(
        math.radians(params.SUPPORT_UNDER_ANGLE)
    )
    z1 = support_top() + MERGE
    y0 = box.min.Y - params.BOARD_FIT - params.WALL + params.CATCH_SPAN
    clips = []
    for x in (
        box.min.X + (clip_bearing - outer_reach) / 2,
        box.max.X - (clip_bearing - outer_reach) / 2,
    ):
        clips.append(
            Pos(x, (y0 + box.max.Y) / 2, (z0 + z1) / 2)
            * Box(
                clip_bearing + outer_reach,
                box.max.Y - y0,
                z1 - z0,
            )
        )
    out = []
    for clip in clips:
        out.extend(cut.intersect(clip).solids())
    return out


def support_runs(wall_offset=LAP_IN):
    runs = [
        solid
        for solid in support_fragments()
        if solid.bounding_box().size.Y >= params.SUPPORT_MIN_RUN
    ]
    box = board.board_profile().bounding_box()
    middle = box.center().X
    envelope = support_case_envelope(params.SUPPORT_SHELL_SKIN)
    out = []
    for solid in runs:
        left = solid.bounding_box().center().X < middle
        boundary = (box.min.X - wall_offset) if left else (box.max.X + wall_offset)
        x0, x1 = (boundary, middle) if left else (middle, boundary)
        clip = Pos((x0 + x1) / 2, box.center().Y, 0) * Box(
            x1 - x0, box.size.Y + 20, 100
        )
        for clipped in solid.intersect(clip).solids():
            out.extend(clipped.intersect(envelope).solids())
    return out


def front_support_cuts():
    return support_runs(SKIRT_OUT)


def support_run_lengths():
    return sorted((solid.bounding_box().size.Y for solid in support_runs()), reverse=True)


def support_bearing_widths(ledge=None):
    """Measure the flat top bearing on each side of the built ledges."""
    ledge = support_ledges() if ledge is None else ledge
    board_box = board.board_profile().bounding_box()
    top = support_top()
    widths = {"-X": [], "+X": []}
    for solid in ledge.solids():
        top_faces = [
            face
            for face in solid.faces()
            if abs(face.bounding_box().min.Z - top) < 1e-6
            and abs(face.bounding_box().max.Z - top) < 1e-6
        ]
        left = solid.bounding_box().center().X < board_box.center().X
        if not top_faces:
            widths["-X" if left else "+X"].append(0.0)
            continue
        if left:
            width = max(face.bounding_box().max.X for face in top_faces) - board_box.min.X
            widths["-X"].append(width)
        else:
            width = board_box.max.X - min(
                face.bounding_box().min.X for face in top_faces
            )
            widths["+X"].append(width)
    return {side: min(values, default=0.0) for side, values in widths.items()}


def support_bearing_margins():
    box = board.board_profile().bounding_box()
    available = {-1: [], 1: []}
    for _, (x0, _, x1, _, side) in board.courtyards().items():
        if side != "bottom":
            continue
        if x0 > box.min.X:
            available[-1].append(x0 - box.min.X)
        if x1 < box.max.X:
            available[1].append(box.max.X - x1)
    return {
        "-X": min(v for v in available[-1] if v >= params.SUPPORT_BEARING)
        - params.SUPPORT_BEARING,
        "+X": min(v for v in available[1] if v >= params.SUPPORT_BEARING)
        - params.SUPPORT_BEARING,
    }


def support_ledges():
    runs = support_runs()
    if not runs:
        raise ValueError("no board support run meets SUPPORT_MIN_RUN")
    return _fuse(*runs)
