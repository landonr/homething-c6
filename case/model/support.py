"""Board deflection stops fused to the back shell side walls."""

import math

from build123d import Box, Face, Pos, fillet, loft

import board
import params

from .backform import back_form
from .hardware import end_screw_block
from .shape import _cut, _fuse, _isect, _offset_face, _slab
from .stack import BOARD_TOP, LAP_IN, MERGE, SHELL_BACK, SHELL_SEAM, SKIRT_OUT, SUPPORT_TOP


def support_top():
    return SUPPORT_TOP


def support_case_envelope(inset=0.0):
    """Return the back case envelope with an optional uniform inside offset."""
    plan = _offset_face(params.BOARD_FIT + params.WALL - inset)
    return _isect(
        _slab(plan, SHELL_BACK, SHELL_SEAM),
        back_form(inset, inset, inset),
    )


def _break_box(x0, y0, x1, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(
        x1 - x0, y1 - y0, z1 - z0
    )


def ledge_breaks(items, wall, z0, z1, clearance=params.SUPPORT_CLEARANCE):
    """[(name, solid)] keepout prisms over z0..z1 for plan rectangles.

    `items` is [(name, x0, y0, x1, y1, wall_side)], each rectangle as the part
    occupies it. Every prism stands `clearance` outside its rectangle. A prism
    that comes within SUPPORT_BEARING of a long side edge, or names that side in
    `wall_side`, is carried out through that side's wall to `wall` past the board
    edge, so the break opens the whole ledge and leaves no sliver in front of
    the wall. The back ledges and the front ledges share this."""
    board_box = board.board_profile().bounding_box()
    out = []
    for name, x0, y0, x1, y1, wall_side in items:
        x0, y0, x1, y1 = x0 - clearance, y0 - clearance, x1 + clearance, y1 + clearance
        cuts = [_break_box(x0, y0, x1, y1, z0, z1)]
        if wall_side in ("-x", "both") or x0 < board_box.min.X + params.SUPPORT_BEARING:
            outer = board_box.min.X - wall - 2 * MERGE
            edge = max(x1, board_box.min.X + params.SUPPORT_BEARING + MERGE)
            cuts.append(_break_box(outer, y0, edge, y1, z0, z1))
        if wall_side in ("+x", "both") or x1 > board_box.max.X - params.SUPPORT_BEARING:
            outer = board_box.max.X + wall + 2 * MERGE
            edge = min(x0, board_box.max.X - params.SUPPORT_BEARING - MERGE)
            cuts.append(_break_box(edge, y0, outer, y1, z0, z1))
        out.append((name, _fuse(*cuts)))
    return out


def support_obstacles(clearance=params.SUPPORT_CLEARANCE):
    """Clearance volumes for the board's bottom courtyards and the assembly
    solids that reach below the ledge top, each opening a break in the runs."""
    reach = LAP_IN + MERGE + params.SUPPORT_BEARING
    z0 = support_top() - reach * math.tan(
        math.radians(params.SUPPORT_UNDER_ANGLE)
    ) - MERGE
    z1 = 0.1
    items = []
    for ref, (x0, y0, x1, y1, side) in board.courtyards().items():
        if side == "bottom":
            items.append((ref, x0, y0, x1, y1, "both" if ref == "D1" else None))
    for index, solid in enumerate(board.assembly_solids(), 1):
        box = solid.bounding_box()
        if box.min.Z >= support_top():
            continue
        y0, y1 = box.min.Y, box.max.Y
        board_box = board.board_profile().bounding_box()
        if (
            box.min.X - clearance < board_box.min.X + params.SUPPORT_BEARING
            or box.max.X + clearance > board_box.max.X - params.SUPPORT_BEARING
        ):
            middle = (y0 + y1) / 2
            half = max((y1 - y0) / 2, params.SUPPORT_MIN_BREAK / 2 - clearance)
            y0, y1 = middle - half, middle + half
        items.append(
            (f"through-board solid {index}", box.min.X, y0, box.max.X, y1, None)
        )
    # The front's end-screw block and its side tie hang in the back's cavity at
    # the grip end. A ledge round that corner would cross the tie, and the
    # relief cut for it would cut the tie off the skirt.
    block = end_screw_block().bounding_box()
    items.append(
        ("end screw block", block.min.X, block.min.Y, block.max.X, block.max.Y, None)
    )
    return ledge_breaks(items, LAP_IN, z0, z1, clearance)


def _ledge_blank(outer):
    """Flat board ledge at z 0 with a filleted inboard edge and a printable
    underside, reaching `outer` past the board edge. Built with its top face at
    z 0 so the back lifts it and the front mirrors it."""
    top = 0.0
    inner = -params.SUPPORT_BEARING
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


def _uncut_support():
    """The back's ledge blank, lifted to the support plane."""
    return Pos(0, 0, support_top()) * _ledge_blank(LAP_IN + MERGE)


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
    y0 = box.min.Y
    y1 = box.max.Y
    clips = []
    for x in (
        box.min.X + (clip_bearing - outer_reach) / 2,
        box.max.X - (clip_bearing - outer_reach) / 2,
    ):
        clips.append(
            Pos(x, (y0 + y1) / 2, (z0 + z1) / 2)
            * Box(
                clip_bearing + outer_reach,
                y1 - y0,
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
    if not params.SUPPORT_SOUTH_RUNS:
        for left in (True, False):
            side = [
                solid
                for solid in runs
                if (solid.bounding_box().center().X < middle) == left
            ]
            if side:
                runs.remove(min(side, key=lambda solid: solid.bounding_box().center().Y))
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
    """The front skirt relief over each run, SUPPORT_SKIRT_FIT above its top.

    Each run is fused with a copy of itself lifted by the fit. The run is far
    taller than the fit at the skirt, so the fuse is a clean upward sweep with
    the same ends and underside."""
    fit = params.SUPPORT_SKIRT_FIT
    if fit <= 0:
        raise ValueError("SUPPORT_SKIRT_FIT must be above zero")
    out = []
    for run in support_runs(SKIRT_OUT):
        swept = _fuse(run, Pos(0, 0, fit) * run).solids()
        if len(swept) != 1:
            raise ValueError(f"front support relief swept to {len(swept)} solids")
        out.append(swept[0])
    return out


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
