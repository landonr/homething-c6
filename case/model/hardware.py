"""The board's own mounting holes, the single screw that closes the two shells
through the back's -Y end wall, and the one post the back offers a V2 board."""

import functools

from build123d import Box, Cylinder, Pos, Rot

import board
import params

from .backform import contour_depth
from .shape import _chamfered_post, _fuse, _hole, _rounded_prism
from .stack import LAP_OUT, MERGE, SKIRT_BOTTOM, SUPPORT_TOP


def mount_points():
    """The board holes the front plate screws into: every one of them, which is
    three since the board went to H1-H3, a pair at the grip end and a single one
    on the centreline at the IR end. Read rather than counted here, so a fourth
    coming back needs no edit."""
    return [(x, y) for x, y, _ in board.mounting_holes()]


def end_wall_edge():
    """The board edge the closure screw enters through: the -Y one."""
    return board.board_profile().bounding_box().min.Y


@functools.cache
def end_screw_axis():
    """(x, z) of the end screw's axis, in the -Y end wall.

    Off the board's own centre rather than off a mounting hole, because this
    screw passes through no board hole: it closes the two shells to each other
    behind the board's end, and END_SCREW_X_OFFSET is what puts it in the clear
    column between R8 and the cradle on one side and J1 on the other.
    """
    x = board.board_profile().bounding_box().center().X + params.END_SCREW_X_OFFSET
    return x, params.END_SCREW_Z


def end_screw_block():
    """The front's own boss for that screw, hanging behind the skirt.

    Two solids rather than one. The block proper stands off the back's inner
    wall by SKIRT_FIT, so the two shells never rub over the whole depth it
    hangs down; a block built flush to that wall would bind the fold closed.
    That leaves it with nothing to grow from, so a web at the skirt's own
    height ties it into the skirt's inner face, which is the only front
    material within reach this far down.

    It carries END_SCREW_BLOCK_BOTTOM under the axis and runs up to
    SUPPORT_TOP, so it stops clear of the board like everything else the
    cavity holds.

    The block's vertical edges carry END_SCREW_BLOCK_R in plan. The web stays
    the block's full width and reaches past the two wall-side rounds by that
    radius plus MERGE, so what bridges to the skirt is the block's whole
    section and not the narrowed waist a round would otherwise leave.
    """
    x, z = end_screw_axis()
    edge = end_wall_edge()
    face = edge - params.BOARD_FIT + params.SKIRT_FIT
    back = face + params.END_SCREW_BLOCK_D
    bottom = z - params.END_SCREW_BLOCK_BOTTOM
    block = _rounded_prism(
        x,
        (face + back) / 2,
        (params.END_SCREW_BLOCK_W, back - face),
        params.END_SCREW_BLOCK_R,
        bottom,
        SUPPORT_TOP,
    )
    web_y0 = edge - params.BOARD_FIT - MERGE
    web_y1 = face + params.END_SCREW_BLOCK_R + MERGE
    web = Pos(x, (web_y0 + web_y1) / 2, (SKIRT_BOTTOM + SUPPORT_TOP) / 2) * Box(
        params.END_SCREW_BLOCK_W, web_y1 - web_y0, SUPPORT_TOP - SKIRT_BOTTOM
    )
    return _fuse(block, web)


def end_screw_pilot():
    """The block's blind self-tapping pilot, drilled in along -Y.

    END_SCREW_BLOCK_D is BOSS_PILOT_DEPTH plus half a millimetre, so this stops
    inside the block rather than opening out of the back of it.
    """
    x, z = end_screw_axis()
    face = end_wall_edge() - params.BOARD_FIT + params.SKIRT_FIT
    y0, y1 = face - 0.1, face + params.BOSS_PILOT_DEPTH
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(
        radius=params.BOSS_PILOT_D / 2, height=y1 - y0
    )


def end_screw_cuts():
    """(clearance, head recess) through the back's -Y end wall.

    The clearance stops at the cavity face rather than running on into the
    cavity, so the only thing it opens is the wall itself; the block behind it
    is the front's and takes the thread.
    """
    x, z = end_screw_axis()
    edge = end_wall_edge()
    outer = edge - LAP_OUT
    y0 = outer - 1
    return [
        _y_hole(x, z, params.SHELL_SCREW_CLEAR_D, y0, edge - params.BOARD_FIT + 0.1),
        _y_hole(x, z, params.SHELL_SCREW_HEAD_D, y0, outer + params.SHELL_SCREW_HEAD_H),
    ]


def end_screw_length():
    """What the end screw has to be: the wall left under its head, the fit the
    block stands off that wall by, and the engagement it then takes. Comes out
    at the same M2 x 6 as the three board screws, so the case takes one
    fastener in one length."""
    return (
        (LAP_OUT - params.BOARD_FIT - params.SHELL_SCREW_HEAD_H)
        + params.SKIRT_FIT
        + params.BOSS_PILOT_DEPTH
    )


def _y_hole(x, z, diameter, y0, y1):
    """A Y-axis bore, the way ir.emitter_bore builds one. _hole is Z-only."""
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(
        radius=diameter / 2, height=y1 - y0
    )


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
