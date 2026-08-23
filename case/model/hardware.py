"""The board's own mounting holes, and the single screw that closes the two
shells through the back's floor."""

import functools
import math

import board
import params

from .backform import contour_depth
from .cell import cell_axis
from .shape import _hole
from .stack import MERGE


def mount_points():
    """The board holes the front plate screws into: every one of them, which is
    three since the board went to H1-H3, a pair at the grip end and a single one
    on the centreline at the IR end. Read rather than counted here, so a fourth
    coming back needs no edit."""
    return [(x, y) for x, y, _ in board.mounting_holes()]


@functools.cache
def closure_point():
    """The mounting hole the back screws up through.

    Wants a clear run from the back's floor to the board, so it is the hole away
    from the cell with the most room under it. The pair at the grip end are over
    the cell bay, and of the two at the IR end the other has U2 4.5 away against
    this one's 7.16 to R3.
    """
    _, _, y0, y1 = cell_axis()
    clear = [p for p in mount_points() if not y0 - 10 < p[1] < y1 + 10]

    def room(point):
        return min(
            math.hypot(
                max(x0 - point[0], point[0] - x1, 0),
                max(cy0 - point[1], point[1] - cy1, 0),
            )
            for _, (x0, cy0, x1, cy1, side) in board.courtyards().items()
            if side == "bottom"
        )

    return max(clear, key=room)


def closure_floors():
    """(outer, cavity) z of the back's floor under the closure screw."""
    _, y = closure_point()
    outer = -contour_depth(y)
    return outer, outer + params.FLOOR


def shell_standoff():
    """Post from the back's floor up to the board's underside, so the one screw
    clamps back, board and front together instead of only the two shells."""
    x, y = closure_point()
    _, cavity = closure_floors()
    return _hole(x, y, params.SHELL_SCREW_OD, cavity - MERGE, 0.0)


def closure_cuts():
    x, y = closure_point()
    outer, _ = closure_floors()
    return [
        _hole(x, y, params.SHELL_SCREW_CLEAR_D, outer - 1, 0.1),
        _hole(x, y, params.SHELL_SCREW_HEAD_D, outer - 1, outer + params.SHELL_SCREW_HEAD_H),
    ]
