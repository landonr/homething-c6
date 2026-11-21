"""The back shell's paper clip guide to U1 RESET."""

import math

from build123d import Box, Cone, Plane, Pos

import board
import params

from .backform import back_form, contour_depth
from .shape import _fuse, _hole, _isect
from .stack import MERGE, SHELL_BACK, SKIRT_BOTTOM


def reset_guide():
    """Return the guide blank with a flat tie to the grip end wall."""
    x, y, z = board.reset_actuator()
    diameter = params.RESET_BORE_D + 2 * params.RESET_GUIDE_WALL
    start = SHELL_BACK
    stop = min(
        z - params.RESET_GUIDE_GAP,
        SKIRT_BOTTOM - params.SKIRT_FIT - params.RESET_GUIDE_TOP_DROP,
    )
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


def reset_chamfer():
    """Return the countersink at the outer end of the bore.

    Its apex is on the bore axis, at the height that puts the -Y mouth
    RESET_CHAMFER_W out from the bore on the floor's roll into the end wall.
    Its axis leans RESET_CHAMFER_TILT toward -Y. The cone starts inside the
    bore, so its surface crosses the bore wall instead of sharing an edge with
    it. Its wide end is wholly below SHELL_BACK.
    """
    x, y, _ = board.reset_actuator()
    radius = params.RESET_BORE_D / 2
    width = params.RESET_CHAMFER_W
    half = math.radians(params.RESET_CHAMFER_ANGLE)
    tilt = math.radians(params.RESET_CHAMFER_TILT)
    spread = math.tan(half)
    # The -Y generator leans half + tilt from -Z and passes through the mouth.
    apex = -contour_depth(y - radius - width) + (radius + width) / math.tan(half + tilt)
    near = radius / (2 * (spread + math.sin(tilt)))
    # The wide end's highest point is its -Y rim.
    far = (apex - SHELL_BACK + MERGE) / (math.cos(tilt) - spread * math.sin(tilt))
    axis = Plane(
        origin=(x, y, apex), z_dir=(0, -math.sin(tilt), -math.cos(tilt))
    )
    return axis * Pos(0, 0, (near + far) / 2) * Cone(
        near * spread, far * spread, far - near
    )
