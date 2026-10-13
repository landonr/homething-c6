"""The pouch cell's bay under the board.

Nothing in the shell holds the pouch: adhesive strips hold it to the board.
Split out from hardware.py because the back's contour is sized off the cell's
own span: backform.py reads cell_span() from here, and hardware.py reads
contour_depth() from backform, so the cell has to sit below both of them
rather than beside the screws it otherwise belongs with.
"""

import functools

from build123d import Box, Pos

import board
import params


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
    half = (params.CELL_W + params.CELL_FIT) / 2

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
    """(x, z, y_min, y_max) of the cell envelope.

    Pushed to the -Y end of its bay rather than centred in it, so the deep part of
    the case is the end the hand holds.
    """
    x = board.board_profile().bounding_box().center().X
    z = -(params.CELL_TOP_GAP + params.CELL_T / 2)
    lo, hi = cell_bay()
    length = params.CELL_L + params.CELL_END_FIT
    y0 = min(lo + params.CELL_END_MARGIN, hi - length)
    return x, z, y0, y0 + length


def cell_envelope():
    x, z, y0, y1 = cell_axis()
    return Pos(x, (y0 + y1) / 2, z) * Box(
        params.CELL_W + params.CELL_FIT, y1 - y0, params.CELL_T
    )


def cell_span():
    """(y_min, y_max) of the cell envelope."""
    _, _, y0, y1 = cell_axis()
    return y0, y1
