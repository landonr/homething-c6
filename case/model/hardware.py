"""The board's own mounting holes, the single screw that closes the two shells
through the back's floor, and the one post the back offers a V2 board."""

import functools
import math

import board
import params

from .backform import contour_depth
from .cell import cell_axis
from .shape import _chamfered_post, _hole
from .stack import MERGE, SUPPORT_TOP


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
    return _chamfered_post(
        x,
        y,
        params.SHELL_SCREW_OD,
        cavity - MERGE,
        0.0,
        params.STANDOFF_CHAMFER,
        "lower",
        cavity,
    )


def closure_cuts():
    x, y = closure_point()
    outer, _ = closure_floors()
    return [
        _hole(x, y, params.SHELL_SCREW_CLEAR_D, outer - 1, 0.1),
        _hole(x, y, params.SHELL_SCREW_HEAD_D, outer - 1, outer + params.SHELL_SCREW_HEAD_H),
    ]


def legacy_retention_floors():
    """(outer, cavity) z of the back's floor under the V2 retention post."""
    _, y = board.legacy_retention_point()
    outer = -contour_depth(y)
    return outer, outer + params.FLOOR


def legacy_retention_post():
    """Post from the back's floor to just under the board, tapped for one
    optional M2 that retains a V2 board.

    V2 and V3 share an outline but no mounting hole, so a V2 board drops into
    this case with nothing to fasten it to. This is the one V2 hole that has a
    clear column under it in the V3 cavity (see board.legacy_retention_point),
    so it is the whole of the offer: retention, not compatibility. V2's IR
    parts and its upper keys still land in the wrong place, and no post fixes
    that.

    It stops at SUPPORT_TOP, the plane the support ledges stop at, so with a V3
    board fitted it is one more ledge under the board rather than something the
    board rests on: the V3 board is still carried by the front shell's bosses
    and is still SUPPORT_GAP clear of everything below it.

    A 5.5 mm post leaves extra printed wall around the same 1.7 mm pilot and
    4.4 mm engagement as the front bosses. The V2 screw is the same M2 x 6
    that the V3 board already takes.
    """
    x, y = board.legacy_retention_point()
    _, cavity = legacy_retention_floors()
    return _chamfered_post(
        x,
        y,
        params.LEGACY_RETENTION_OD,
        cavity - MERGE,
        SUPPORT_TOP,
        params.STANDOFF_CHAMFER,
        "lower",
        cavity,
    )


def legacy_retention_pilot():
    """The post's blind self-tapping pilot, drilled down from its top.

    Blind by a wide margin: the post is taller than BOSS_PILOT_DEPTH by more
    than the floor is thick, so the hole ends in the post and never reaches the
    exterior surface. legacy_pilot_blind() in checks/legacy.py holds that.
    """
    x, y = board.legacy_retention_point()
    return _hole(
        x,
        y,
        params.BOSS_PILOT_D,
        SUPPORT_TOP - params.BOSS_PILOT_DEPTH,
        SUPPORT_TOP + 0.1,
    )


def legacy_screw_length():
    """What the optional V2 screw has to be: V2's own board plus the pilot's
    engagement. The V2 board is 0.09 thinner than BOARD_THICKNESS, which the
    same M2 x 6 absorbs."""
    return params.BOARD_THICKNESS + params.BOSS_PILOT_DEPTH
