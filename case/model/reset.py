"""The back shell's paper clip guide to U1 RESET."""

from build123d import Box, Pos

import board
import params

from .backform import back_form
from .shape import _fuse, _hole, _isect
from .stack import MERGE, SHELL_BACK, SKIRT_BOTTOM


def reset_guide():
    """Return the guide blank with a flat tie to the grip end wall."""
    x, y, z = board.reset_actuator()
    diameter = params.RESET_BORE_D + 2 * params.RESET_GUIDE_WALL
    start = SHELL_BACK
    stop = min(z - params.RESET_GUIDE_GAP, SKIRT_BOTTOM - params.SKIRT_FIT)
    wall_y = board.board_profile().bounding_box().min.Y - params.BOARD_FIT - MERGE
    web = Pos(x, (wall_y + y) / 2, (start + stop) / 2) * Box(
        diameter, y - wall_y, stop - start
    )
    blank = _fuse(_hole(x, y, diameter, start, stop), web)
    root = Pos(0, 0, params.FLOOR / 2) * back_form(0, 0)
    return _isect(blank, root)


def reset_bore():
    """Return the straight bore through the guide and the back floor."""
    x, y, z = board.reset_actuator()
    return _hole(x, y, params.RESET_BORE_D, SHELL_BACK - MERGE, z)
