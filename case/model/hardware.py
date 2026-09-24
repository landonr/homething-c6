"""The board's own mounting holes, the single screw that closes the two shells
through the back's -Y end wall, and the one post the back offers a V2 board."""

import functools

from build123d import (
    BuildLine,
    BuildSketch,
    Box,
    Cylinder,
    Plane,
    Polyline,
    Pos,
    Rot,
    extrude,
    make_face,
)

import board
import params

from .backform import contour_depth
from .shape import _chamfered_post, _cut, _fuse, _hole, _rounded_prism
from .stack import LAP_IN, LAP_OUT, MERGE, SKIRT_BOTTOM, SKIRT_OUT, SUPPORT_TOP


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


def _ramp_block_top(block, cavity):
    """Cut the top of the block and its web back to one 45 degree ramp.

    The front prints face down, so the top face of the block and web is a
    ceiling hung off the skirt in print, and a flat one needs a support tower
    in the cavity. The ramp leaves the skirt END_SCREW_BLOCK_RAMP_LEDGE
    inboard of the cavity face and falls one for one toward +Y, so every layer
    stands on the one before it. The same ramp is the board's lead-in: nothing
    square stands under the board's end for a tilted board to strike.

    A straight wedge cut across the whole width plus MERGE either side, never
    an edge chamfer. The top +Y arris is a tangent chain of the straight edge
    and the two END_SCREW_BLOCK_R plan rounds, and an edge chamfer on that
    chain exported a torn, non-manifold front while every geometric check was
    green. Do not put the edge chamfer back. See the STL discipline in
    AGENTS.md.

    The wedge's top edge stands MERGE above SUPPORT_TOP on the same line, so
    no face of it lies in the block's top face.
    """
    ledge = params.END_SCREW_BLOCK_RAMP_LEDGE
    if not 0 <= ledge < params.END_SCREW_BLOCK_GAP:
        raise ValueError(
            f"END_SCREW_BLOCK_RAMP_LEDGE {ledge} is not between the skirt and "
            f"the block's own face, {params.END_SCREW_BLOCK_GAP} inboard of it"
        )
    start = cavity + ledge
    far = block.bounding_box().max.Y + MERGE
    with BuildSketch(Plane.YZ) as section:
        with BuildLine():
            Polyline(
                (start - MERGE, SUPPORT_TOP + MERGE),
                (far, SUPPORT_TOP + MERGE),
                (far, SUPPORT_TOP - (far - start)),
                close=True,
            )
        make_face()
    reach = params.END_SCREW_BLOCK_W / 2 + MERGE
    x = block.bounding_box().center().X
    wedge = Pos(x, 0, 0) * extrude(section.sketch, amount=reach, both=True)
    return _cut(block, wedge)


def _chamfer_block_base(block, back, bottom):
    """Cut the block's bottom +Y arris back to a ramp, the corner the fold leads
    with. A wedge across the full width, for the same tangent-chain reason
    _ramp_block_top is one."""
    size = params.END_SCREW_BLOCK_BASE_CHAMFER
    if not 0 < size < params.END_SCREW_BLOCK_BOTTOM:
        raise ValueError(
            f"END_SCREW_BLOCK_BASE_CHAMFER {size} is not inside the "
            f"{params.END_SCREW_BLOCK_BOTTOM} the block carries under the screw"
        )
    if size >= params.END_SCREW_BLOCK_D:
        raise ValueError(
            f"END_SCREW_BLOCK_BASE_CHAMFER {size} is not inside the block's "
            f"own {params.END_SCREW_BLOCK_D} depth"
        )
    with BuildSketch(Plane.YZ) as section:
        with BuildLine():
            Polyline(
                (back - size, bottom),
                (back, bottom),
                (back, bottom + size),
                close=True,
            )
        make_face()
    reach = params.END_SCREW_BLOCK_W / 2 + MERGE
    x = block.bounding_box().center().X
    wedge = Pos(x, 0, 0) * extrude(section.sketch, amount=reach, both=True)
    return _cut(block, wedge)


def end_screw_fillet_start():
    """Y where the block's root fillet leaves SKIRT_BOTTOM: the skirt's outer
    face at the grip end, the plane grip_skirt_relief cuts it back to."""
    return end_wall_edge() - (SKIRT_OUT - params.GRIP_SKIRT_RELIEF)


def end_screw_root_legs():
    """(fillet, chamfer): the legs of the block's root fillet and of the back's
    end wall chamfer. Each runs corner to corner, so neither is a parameter.

    The fillet runs from end_screw_fillet_start to the block's -Y face. The
    chamfer runs from the lap's inner face at the relief floor to the cavity
    wall, which is the whole floor. A wider one would notch the lap.
    """
    face = end_wall_edge() - params.BOARD_FIT + params.END_SCREW_BLOCK_GAP
    return face - end_screw_fillet_start(), LAP_IN - params.BOARD_FIT


def _block_root_fillet(x, face):
    """The 45 degree fillet under the web, in the inside corner where the web's
    underside at SKIRT_BOTTOM meets the block's -Y face.

    The screw pulls the block toward the wall, so the web bends at its neck.
    The ramp limits the neck from above, so the fillet deepens it from below.

    Its hypotenuse starts on SKIRT_BOTTOM at the skirt's relieved outer face,
    end_screw_fillet_start, and falls at 45 degrees to the block's face. So it
    deepens the neck at the skirt root too, and leaves no flat strip of skirt
    underside beside it. The start lies in the plane of the relief cut, the way
    the back's chamfer starts on the lap's inner face. It reaches MERGE up into
    the skirt and web and MERGE into the block, both inside material, so it
    fuses as one solid.

    It points up as the front prints, so it needs no support. It runs the
    block's full width, because the block's -Y face is square. Bounded by the
    pilot below it.
    """
    start = end_screw_fillet_start()
    leg = face - start
    _, z = end_screw_axis()
    pilot_top = z + params.BOSS_PILOT_D / 2
    if SKIRT_BOTTOM - leg <= pilot_top:
        raise ValueError(
            f"the root fillet reaches down to {SKIRT_BOTTOM - leg:.2f}, not "
            f"above the pilot's top at {pilot_top:.2f}"
        )
    with BuildSketch(Plane.YZ) as section:
        with BuildLine():
            Polyline(
                (start, SKIRT_BOTTOM + MERGE),
                (start, SKIRT_BOTTOM),
                (face + MERGE, SKIRT_BOTTOM - leg - MERGE),
                (face + MERGE, SKIRT_BOTTOM + MERGE),
                close=True,
            )
        make_face()
    reach = params.END_SCREW_BLOCK_W / 2
    return Pos(x, 0, 0) * extrude(section.sketch, amount=reach, both=True)


def end_screw_block():
    """The front's own boss for that screw, hanging behind the skirt.

    Two solids rather than one. The block proper stands off the back's inner
    wall by END_SCREW_BLOCK_GAP, so the two shells never rub over the whole
    depth it hangs down; a block built flush to that wall would bind the fold
    closed, and one built to SKIRT_FIT alone bore on it and bowed the case.
    That leaves it with nothing to grow from, so a web at the skirt's own
    height ties it into the skirt's inner face, which is the only front
    material within reach this far down.

    It carries END_SCREW_BLOCK_BOTTOM under the axis and rises toward
    SUPPORT_TOP, so it stops clear of the board like everything else the
    cavity holds.

    The block's two +Y vertical edges carry END_SCREW_BLOCK_R in plan. The two
    wall-side edges stay square, so the web and the root fillet run the block's
    full width and nothing narrows the section that bridges to the skirt.

    Its bottom +Y arris is cut back by END_SCREW_BLOCK_BASE_CHAMFER, which is
    the corner the fold leads with.

    Its top is one 45 degree ramp off the skirt, cut after the web joins so the
    web is ramped too. The ramp is the underside the face down print builds
    without support, and the lead-in a board going in at a tilt slides down.
    See _ramp_block_top.

    The ramp limits the web's neck from above, so a 45 degree fillet under the
    web deepens it from below. The back's end wall takes a parallel chamfer.
    See _block_root_fillet and end_screw_wall_chamfer.
    """
    x, z = end_screw_axis()
    edge = end_wall_edge()
    face = edge - params.BOARD_FIT + params.END_SCREW_BLOCK_GAP
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
    square = params.END_SCREW_BLOCK_R + MERGE
    block = _fuse(
        block,
        Pos(x, face + square / 2, (bottom + SUPPORT_TOP) / 2)
        * Box(params.END_SCREW_BLOCK_W, square, SUPPORT_TOP - bottom),
    )
    block = _chamfer_block_base(block, back, bottom)
    cavity = edge - params.BOARD_FIT
    web_y0 = cavity - MERGE
    web_y1 = face + MERGE
    web = Pos(x, (web_y0 + web_y1) / 2, (SKIRT_BOTTOM + SUPPORT_TOP) / 2) * Box(
        params.END_SCREW_BLOCK_W, web_y1 - web_y0, SUPPORT_TOP - SKIRT_BOTTOM
    )
    fillet = _block_root_fillet(x, face)
    return _ramp_block_top(_fuse(block, web, fillet), cavity)


def end_screw_pilot():
    """The block's blind self-tapping pilot, drilled in along -Y.

    END_SCREW_BLOCK_D is END_SCREW_PILOT_DEPTH plus half a millimetre, so this
    stops inside the block rather than opening out of the back of it.
    """
    x, z = end_screw_axis()
    face = end_wall_edge() - params.BOARD_FIT + params.END_SCREW_BLOCK_GAP
    y0, y1 = face - 0.1, face + params.END_SCREW_PILOT_DEPTH
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


def end_screw_wall_chamfer():
    """The chamfer on the inner top arris of the back's -Y end wall, under the
    skirt relief, that makes room for the block's root fillet.

    The fillet goes below SKIRT_BOTTOM, where this wall is. A planar wedge cut
    at 45 degrees, so its face stays parallel to the fillet's. Its leg is the
    relief floor's own width, see end_screw_root_legs, so the chamfer starts at
    the lap's inner face and takes the whole floor. It cannot grow without
    notching the lap.

    The two legs differ. The horizontal gap between the faces is the skirt's
    own clearance to the lap at the grip end, LAP_IN - SKIRT_OUT +
    GRIP_SKIRT_RELIEF, plus SKIRT_FIT. Below the chamfer, the block's -Y face
    keeps END_SCREW_BLOCK_GAP to the wall.

    It points up as the back prints, so it needs no support. Bounded by the
    clearance bore below it. The wedge rises from the lap corner into the
    relief void and never cuts the lap. It runs over the block's full width
    plus MERGE either side.
    """
    _, c = end_screw_root_legs()
    x, z = end_screw_axis()
    floor = SKIRT_BOTTOM - params.SKIRT_FIT
    clear_top = z + params.SHELL_SCREW_CLEAR_D / 2
    if floor - c <= clear_top:
        raise ValueError(
            f"the end wall chamfer reaches down to {floor - c:.2f}, not above "
            f"the clearance bore's top at {clear_top:.2f}"
        )
    wall = end_wall_edge() - params.BOARD_FIT
    with BuildSketch(Plane.YZ) as section:
        with BuildLine():
            Polyline(
                (wall - c, floor),
                (wall + MERGE, floor - c - MERGE),
                (wall + MERGE, floor + MERGE),
                close=True,
            )
        make_face()
    reach = params.END_SCREW_BLOCK_W / 2 + MERGE
    return Pos(x, 0, 0) * extrude(section.sketch, amount=reach, both=True)


def end_screw_length():
    """What the end screw has to be: the wall left under its head, the fit the
    block stands off that wall by, and the engagement it then takes. Comes out
    at the same M2 x 6 as the three board screws, so the case takes one
    fastener in one length."""
    return (
        (LAP_OUT - params.BOARD_FIT - params.SHELL_SCREW_HEAD_H)
        + params.END_SCREW_BLOCK_GAP
        + params.END_SCREW_PILOT_DEPTH
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
