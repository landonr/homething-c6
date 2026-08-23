"""The AA cell's bay under the board, and the two saddle ribs that hold it.

Split out from hardware.py because the back's contour is sized off the
cradle's own span: backform.py reads cradle_span() from here, and hardware.py
reads contour_depth() from backform, so the cell has to sit below both of them
rather than beside the screws it otherwise belongs with.
"""

import functools

from build123d import Box, Cylinder, Pos, Rot

import board
import params

from .stack import CAVITY_BACK, MERGE


@functools.cache
def cell_obstacles(top, x0, x1):
    """(y_min, y_max) of everything under the board reaching below the cell's top
    face, within the cell's width. Only two do: U2's leads and J1."""
    spans = []
    for solid in board.assembly_solids():
        box = solid.bounding_box()
        if box.min.Z >= top or box.max.X <= x0 or box.min.X >= x1:
            continue
        spans.append((box.min.Y, box.max.Y))

    # Courtyards carry no height, so only use them for parts the STEP is missing.
    for ref, (cx0, cy0, cx1, cy1, side) in board.courtyards().items():
        if side != "bottom" or cx1 <= x0 or cx0 >= x1:
            continue
        try:
            board.part_envelope(ref)
            continue
        except ValueError:
            pass
        if -params.UNMODELLED_DEPTH < top:
            spans.append((cy0, cy1))
    return sorted(spans)


@functools.cache
def cell_bay():
    """(y_min, y_max) of the longest run of board with nothing hanging into it.

    The cell's top face is one CELL_TOP_GAP below the board, not below whatever
    happens to be in the way, so anything reaching lower than that counts as an
    obstacle and the cell goes where there are none. That is worth more than the
    length it costs: it lets the cell sit right up under the board.
    """
    x = board.board_profile().bounding_box().center().X
    top = -params.CELL_TOP_GAP
    half = (params.CELL_D + params.CELL_FIT) / 2

    edges = [board.board_profile().bounding_box().min.Y]
    for lo, hi in cell_obstacles(top, x - half, x + half):
        edges += [lo, hi]
    edges.append(board.board_profile().bounding_box().max.Y)
    gaps = [
        (edges[i + 1] - edges[i], edges[i], edges[i + 1])
        for i in range(0, len(edges) - 1, 2)
    ]
    _, lo, hi = max(gaps)
    return lo, hi


@functools.cache
def cell_axis():
    """(x, z, y_min, y_max) of the cell envelope, cradle excluded.

    Pushed to the -Y end of its bay rather than centred in it, so the deep part of
    the case is the end the hand holds.
    """
    x = board.board_profile().bounding_box().center().X
    z = -(params.CELL_TOP_GAP + params.CELL_D / 2)
    lo, hi = cell_bay()
    length = params.CELL_L + params.CELL_END_FIT
    y0 = min(lo + params.CRADLE_T + params.CELL_END_MARGIN, hi - params.CRADLE_T - length)
    return x, z, y0, y0 + length


def cell_envelope():
    x, z, y0, y1 = cell_axis()
    radius = (params.CELL_D + params.CELL_FIT) / 2
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(radius, y1 - y0)


@functools.cache
def cradle_footprints():
    """2D (name, x0, y0, x1, y1) of the two saddle ribs, for the clearance check."""
    x, _, y0, y1 = cell_axis()
    half = (params.CELL_D + params.CELL_FIT) / 2 + params.TUBE_WALL
    return [
        ("cradle -y", x - half, y0 - params.CRADLE_T, x + half, y0),
        ("cradle +y", x - half, y1, x + half, y1 + params.CRADLE_T),
    ]


def cradle_span():
    ribs = cradle_footprints()
    return min(r[2] for r in ribs), max(r[4] for r in ribs)


def cradle_z():
    """(z0, z1) the saddle ribs occupy, for the clearance check."""
    _, z, _, _ = cell_axis()
    return CAVITY_BACK - MERGE, z


def cradle():
    """Two saddle ribs. The notch cradles the cell, the face stops it sliding."""
    base, z = cradle_z()
    ribs = None
    for _, x0, y0, x1, y1 in cradle_footprints():
        rib = Pos((x0 + x1) / 2, (y0 + y1) / 2, (base + z) / 2) * Box(
            x1 - x0, y1 - y0, z - base
        )
        ribs = rib if ribs is None else ribs + rib
    return ribs - cell_envelope()
