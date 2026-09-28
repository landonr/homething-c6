"""The two shells and their joint features: the front skirt, the end catch
windows, the back lap, and the detents.
"""

import functools
import math

from build123d import (
    Box,
    GeomType,
    Plane,
    Pos,
    Polygon,
    Rectangle,
    RectangleRounded,
    Shell,
    Solid,
    Compound,
    chamfer,
    extrude,
    fillet,
    loft,
)

import board
import cache
import params

from .backform import back_form
from .caps import _key_prism, cap_counterbore, cap_face_hole, cap_outline
from .hardware import (
    end_screw_block,
    end_screw_cuts,
    end_screw_pilot,
    end_screw_wall_chamfer,
    legacy_retention_pilot,
    legacy_retention_post,
    mount_points,
)
from .support import front_support_cuts, support_runs
from .ir import emitter_bore, ir_window_opening, ir_window_rebate
from .keypad import face_depth_at, keypad_outline_groove, keypad_recess
from .mic import mic_bore, mic_duct
from .shape import (
    _cut,
    _chamfered_post,
    _fuse,
    _hole,
    _isect,
    _offset_face,
    _profiles,
    _ring,
    _slab,
)
from .stack import (
    BOARD_TOP,
    CAVITY_FRONT,
    COUNTERBORE_TOP,
    front_face,
    LAP_IN,
    LAP_OUT,
    MERGE,
    SHELL_SEAM,
    SHELL_BACK,
    SHELL_FRONT,
    SKIRT_BOTTOM,
    SKIRT_OUT,
    STIFFENED_WALL,
    SUPPORT_TOP,
)
from .usb import usb_pocket, usb_slot
from .wheel_ring import led_ring_channel, wheel_opening


def front_edge_round(fdm=False):
    """Top-edge size: FDM chamfer leg or recessed-front fillet radius.

    Here rather than read at the edge operation so checks/fdm.py can ask for the
    number it is about to measure on the built shell without restating the
    choice."""
    return params.EDGE_R_FRONT_FDM if fdm else params.EDGE_R_FRONT


def skirt_relief():
    """What the back gives up so its lap can close over the skirt: everything its
    wall has inboard of the lap, over the skirt's height and a fit below it."""
    return [
        _ring(
            params.BOARD_FIT - 6,
            LAP_IN,
            SKIRT_BOTTOM - params.SKIRT_FIT,
            SHELL_SEAM + 1,
        )
    ]


def skirt_cuts():
    """What turns the front's wall below the parting plane into the skirt: the
    cavity carried down past it, and everything outboard of the skirt, which is
    the space the back's lap closes into."""
    return [
        _slab(_offset_face(params.BOARD_FIT), SKIRT_BOTTOM - 1, SHELL_SEAM),
        _ring(SKIRT_OUT, LAP_OUT + 6, SKIRT_BOTTOM - 1, SHELL_SEAM),
    ]


def corner_tangent_y():
    """(min, max) Y of the board profile's straight long sides, where the four
    corner arcs meet them."""
    sides = [
        edge.bounding_box()
        for edge in board.board_profile().outer_wire().edges()
        if edge.geom_type == GeomType.LINE and edge.bounding_box().size.X < 1e-6
    ]
    return min(b.min.Y for b in sides), max(b.max.Y for b in sides)


def _side_strip(stations, back, z0, z1):
    """One prism per long side, as [-x, +x], between a face through `stations`
    and a constant `back` offset, extruded over z0..z1.

    `stations` is a list of (y, offset) pairs in y order. Each offset, like
    `back`, runs outward from that side's straight board edge. A profile-offset
    band on a straight side is a rectangle, so this matches one exactly there,
    and the strip cannot reach into a corner arc the way a clipped ring does.
    """
    if any(offset >= back for _, offset in stations):
        raise ValueError("a side strip's face reaches its back")
    box = board.board_profile().bounding_box()
    y0, y1 = stations[0][0], stations[-1][0]
    out = []
    for side, edge in ((-1, box.min.X), (1, box.max.X)):
        plan = Polygon(
            *((edge + side * offset, y) for y, offset in stations),
            (edge + side * back, y1),
            (edge + side * back, y0),
            align=None,
        )
        out.append(_slab(plan, z0, z1))
    return out


def skirt_stiffener_taper_span():
    """The y span over which each side of the stiffener tapers out from its
    full thickness to the plain board fit at the IR corner tangent."""
    run = params.SIDE_SKIRT_THICKEN_RUN
    yt0, yt1 = corner_tangent_y()
    if not 0 < run < yt1 - yt0:
        raise ValueError(
            f"SIDE_SKIRT_THICKEN_RUN {run} must be above zero and below the "
            f"{yt1 - yt0:.2f} straight side"
        )
    return yt1 - run, yt1


def skirt_stiffener():
    """Inward wall material clear of the board's edge, round the grip end and
    up both long sides, as one solid.

    A constant offset band, so the grip corners carry it without a step. Short
    of the IR corner tangents it tapers to the plain board fit, so the IR corner
    arcs and the IR end skirt keep that fit. The clip lies on the straight
    sides, where the band is a rectangle, so it leaves no slice.

    It runs from the skirt bottom to the cavity ceiling, so the inner wall has
    no step at the seam."""
    fit, thick = params.BOARD_FIT, STIFFENED_WALL
    ya, yt1 = skirt_stiffener_taper_span()
    box = board.board_profile().bounding_box()
    reach = fit + MERGE + 1
    clip_y0 = box.min.Y - reach
    clip = Pos(
        box.center().X, (clip_y0 + ya) / 2, (SKIRT_BOTTOM + CAVITY_FRONT) / 2
    ) * Box(box.size.X + 2 * reach, ya - clip_y0, CAVITY_FRONT - SKIRT_BOTTOM + 2)
    band = _ring(thick, fit + MERGE, SKIRT_BOTTOM, CAVITY_FRONT)
    tapers = _side_strip(
        [(ya, thick), (yt1, fit)], fit + MERGE, SKIRT_BOTTOM, CAVITY_FRONT
    )
    return _fuse(_isect(band, clip), *tapers)


def side_catch_y():
    """Catch station near the lengthwise centre of the board."""
    box = board.board_profile().bounding_box()
    y = box.center().Y + params.SIDE_CATCH_CENTER_OFFSET
    if not box.min.Y < y - params.SIDE_CATCH_W / 2 < y + params.SIDE_CATCH_W / 2 < box.max.Y:
        raise ValueError("side catch pocket reaches a board end")
    return y


@functools.cache
def side_catch_relief_top():
    """Top of the front skirt's support relief under either side catch.

    Read off the built cuts, not SUPPORT_TOP, so a support change that lifts the
    relief into a pocket or a detent fails here."""
    y = side_catch_y()
    y0, y1 = y - params.SIDE_CATCH_W / 2, y + params.SIDE_CATCH_W / 2
    tops = [
        cut.bounding_box().max.Z
        for cut in front_support_cuts()
        if cut.bounding_box().min.Y < y1 and cut.bounding_box().max.Y > y0
    ]
    return max(tops, default=SUPPORT_TOP)


def side_catch_bottom():
    """Pocket bottom, SIDE_CATCH_LOWER_LAND above the built support relief.

    The pocket sits as low as that lower lip allows, so the skirt land above it
    stays long."""
    z0 = side_catch_relief_top() + params.SIDE_CATCH_LOWER_LAND
    land = SHELL_SEAM - (z0 + params.SIDE_CATCH_H)
    if land < params.SIDE_CATCH_UPPER_LAND_MIN:
        raise ValueError(
            f"side catch pocket leaves {land:.3f} of skirt above it, below "
            f"SIDE_CATCH_UPPER_LAND_MIN {params.SIDE_CATCH_UPPER_LAND_MIN}"
        )
    return z0


def _side_catch_clear_of_relief(z, what):
    floor = max(side_catch_relief_top(), SUPPORT_TOP)
    if z <= floor:
        raise ValueError(
            f"side catch {what} at z {z:.3f} is not above the support relief "
            f"top {floor:.3f}"
        )


def side_catch_pockets():
    """Blind rounded pockets with a bevel all around each exterior mouth."""
    box = board.board_profile().bounding_box()
    z0 = side_catch_bottom()
    if z0 + params.SIDE_CATCH_H >= SHELL_SEAM:
        raise ValueError("side catch pocket reaches the top of the skirt")
    _side_catch_clear_of_relief(z0, "pocket bottom")
    bevel = params.SIDE_CATCH_POCKET_CHAMFER
    if not 0 < bevel < min(params.SIDE_CATCH_R, params.SIDE_CATCH_H / 2):
        raise ValueError("side catch pocket chamfer does not fit its rounded profile")
    out = []
    for side, edge in ((-1, box.min.X), (1, box.max.X)):
        def profile(radial, inset):
            plane = Plane(
                origin=(edge + side * radial, side_catch_y(), z0 + params.SIDE_CATCH_H / 2),
                x_dir=(0, 1, 0), z_dir=(side, 0, 0),
            )
            return plane * RectangleRounded(
                params.SIDE_CATCH_W - 2 * inset,
                params.SIDE_CATCH_H - 2 * inset,
                params.SIDE_CATCH_R - inset,
            )

        out.append(loft(
            [
                profile(SKIRT_OUT + MERGE, 0),
                profile(SKIRT_OUT + 0.02, 0),
                profile(SKIRT_OUT - params.SIDE_CATCH_POCKET_DEPTH, bevel),
            ],
            ruled=True,
        ))
    return out


DETENT_EDGE = 0.1
"""Radial width a side detent keeps at its bottom and top edges, so the ruled
loft of its wedge has no zero-width section."""


def side_catch_detent_z():
    """Bottom, tip-land bottom, tip-land top and top of each side detent.

    The lower flank crosses the pocket's lower mouth edge SIDE_CATCH_PRELOAD
    inside the skirt face, which sets every height here. The height itself
    comes from the flank angle, not from the pocket."""
    angle = params.SIDE_CATCH_FLANK_ANGLE
    if not 0 < angle < 90:
        raise ValueError("SIDE_CATCH_FLANK_ANGLE must be between 0 and 90 degrees")
    slope = math.tan(math.radians(angle))
    depth = params.SIDE_CATCH_D
    land = params.SIDE_CATCH_LAND_H
    preload = params.SIDE_CATCH_PRELOAD
    engage = depth - params.SKIRT_FIT
    if not DETENT_EDGE < depth:
        raise ValueError("SIDE_CATCH_D leaves the side detent no flank")
    if land <= 0:
        raise ValueError("SIDE_CATCH_LAND_H must be above zero")
    if not 0 < preload < engage:
        raise ValueError(
            f"SIDE_CATCH_PRELOAD {preload} must be above zero and below the "
            f"detent's {engage:.2f} reach past the skirt face"
        )
    if not engage < params.SIDE_CATCH_POCKET_DEPTH:
        raise ValueError("side catch detent tip reaches the pocket floor")
    pocket0 = side_catch_bottom()
    pocket1 = pocket0 + params.SIDE_CATCH_H
    land0 = pocket0 + (engage - preload) / slope
    land1 = land0 + land
    rise = (depth - DETENT_EDGE) / slope
    crossing = land1 + engage / slope
    if crossing > pocket1 - params.SIDE_CATCH_FIT:
        raise ValueError(
            f"side detent's upper flank meets the skirt face at z {crossing:.3f}, "
            f"within SIDE_CATCH_FIT of the pocket top {pocket1:.3f}"
        )
    return land0 - rise, land0, land1, land1 + rise


def side_catch_detent_centre():
    """Height of each side detent's tip land, where it stands deepest."""
    _, land0, land1, _ = side_catch_detent_z()
    return (land0 + land1) / 2


def side_catch_detents():
    """Back-lap detents that ramp at SIDE_CATCH_FLANK_ANGLE on the insertion
    and release sides. The release flank bears on the pocket's lower lip under
    a light preload, so the catch holds the seam closed."""
    box = board.board_profile().bounding_box()
    z0, land0, land1, z1 = side_catch_detent_z()
    _side_catch_clear_of_relief(z0, "detent bottom edge")
    depth = params.SIDE_CATCH_D
    fit = params.SIDE_CATCH_FIT
    # Stop FIT short of the pocket's rounded ends. The release flank must bear
    # on the straight lower lip only: past it the lip curls up and buries the
    # tip, which is the hard stop FIT exists to prevent.
    length = params.SIDE_CATCH_W - 2 * (params.SIDE_CATCH_R + fit)
    radius = max(params.SIDE_CATCH_R - fit, 0.1)
    if not radius < min(length, z1 - z0) / 2:
        raise ValueError("side detent corner radius does not fit its profile")
    y = side_catch_y()
    out = []
    for side, edge in ((-1, box.min.X), (1, box.max.X)):
        base = edge + side * LAP_IN
        tip = base - side * depth
        plane = Plane(
            origin=((base + tip) / 2, y, (z0 + z1) / 2),
            x_dir=(0, 1, 0), z_dir=(-side, 0, 0),
        )
        profile = plane * RectangleRounded(length, z1 - z0, radius)
        prism = extrude(profile, amount=depth / 2 + MERGE, both=True)
        rim = base - side * DETENT_EDGE / 2
        wedge = loft(
            [
                Pos(rim, y, z0) * Rectangle(DETENT_EDGE, params.SIDE_CATCH_W + 2),
                Pos((base + tip) / 2, y, land0)
                * Rectangle(depth, params.SIDE_CATCH_W + 2),
                Pos((base + tip) / 2, y, land1)
                * Rectangle(depth, params.SIDE_CATCH_W + 2),
                Pos(rim, y, z1) * Rectangle(DETENT_EDGE, params.SIDE_CATCH_W + 2),
            ],
            ruled=True,
        )
        out.append(_isect(prism, wedge))
    return out


def grip_skirt_relief():
    """Shave the hidden skirt around the grip end for closing clearance.

    The shave follows the corner arcs to where the long sides start, then fades
    out along each side over GRIP_SKIRT_RELIEF_RUN, so it ends without a -Y
    facing step in the skirt face."""
    run = params.GRIP_SKIRT_RELIEF_RUN
    if run <= 0:
        raise ValueError("GRIP_SKIRT_RELIEF_RUN must be above zero")
    box = board.board_profile().bounding_box()
    side_y, _ = corner_tangent_y()
    z0, z1 = SKIRT_BOTTOM - 0.1, SHELL_SEAM
    relieved = SKIRT_OUT - params.GRIP_SKIRT_RELIEF
    band = _ring(relieved, SKIRT_OUT + MERGE, z0, z1)
    clip_y0 = box.min.Y - 2 * (params.WALL + MERGE)
    clip = Pos(
        box.center().X,
        (clip_y0 + side_y) / 2,
        (SKIRT_BOTTOM + SHELL_SEAM) / 2,
    ) * Box(
        box.size.X + 2 * (params.WALL + MERGE),
        side_y - clip_y0,
        SHELL_SEAM - SKIRT_BOTTOM + 0.2,
    )
    tapers = _side_strip(
        [(side_y, relieved), (side_y + run, SKIRT_OUT)], SKIRT_OUT + MERGE, z0, z1
    )
    return _fuse(_isect(band, clip), *tapers)


CATCH_Z0 = SKIRT_BOTTOM + params.CATCH_RISE
"""Bottom of each window, and so the top of the skirt that catches under a detent."""


def catch_x():
    """Where the two windows sit across the IR end wall.

    The -x one is CATCH_SPACING off the centreline as it always was. The +x one
    cannot be: D1's bore is in this same face, and the mirrored position lands
    on it, so that window is placed off the bore instead and takes whichever of
    the two is further -x.
    """
    cx = board.board_profile().bounding_box().center().X
    clear = (
        emitter_bore().bounding_box().min.X
        - params.CATCH_EMITTER_CLEAR
        - params.CATCH_W / 2
    )
    return [
        cx - params.CATCH_SPACING / 2,
        min(cx + params.CATCH_SPACING / 2, clear),
    ]


@cache.solid
def skirt_lead_in_cuts():
    """Return material removed from the skirt for the folding lead-ins."""
    if params.SKIRT_TRANSITION_CHAMFER <= 0:
        return Compound([])
    skirt = _fuse(
        _ring(params.BOARD_FIT, SKIRT_OUT, SKIRT_BOTTOM, SHELL_SEAM),
        skirt_stiffener(),
    )
    cuts = front_support_cuts()
    skirt = _cut(skirt, *cuts)
    original = skirt
    tolerance = 1e-5
    profiles = []
    for cut in cuts:
        box = cut.bounding_box()
        height = box.max.Z - SKIRT_BOTTOM
        profiles.extend(
            ((box.min.Y, SKIRT_BOTTOM, height, -1),
             (box.max.Y, SKIRT_BOTTOM, height, 1))
        )
    if not 0 < params.SKIRT_LEAD_ANGLE < 90:
        raise ValueError("SKIRT_LEAD_ANGLE must be between 0 and 90 degrees")
    slope = math.tan(math.radians(params.SKIRT_LEAD_ANGLE))
    wedges = []
    for edge_y, bottom, height, direction in profiles:
        run = height / slope
        for edge in original.edges():
            box = edge.bounding_box()
            if not (
                box.size.X > tolerance
                and box.size.Y < tolerance
                and box.size.Z < tolerance
                and abs(box.min.Z - bottom) < tolerance
                and abs(edge.center().Y - edge_y) < tolerance
            ):
                continue
            plane = Plane(
                origin=(box.min.X - MERGE, edge_y, bottom),
                x_dir=(0, 1, 0), z_dir=(1, 0, 0),
            )
            # Start the ramp slightly into the skirt, with a short flat cut back
            # to the support break. The same Y relief applies in each direction.
            fit = params.SKIRT_LEAD_FIT
            points = [
                (0, 0),
                (direction * (run + fit), 0),
                (direction * fit, height),
                (0, height),
            ]
            wedge = plane * Polygon(*points, align=None)
            wedges.append(extrude(wedge, amount=box.size.X + 2 * MERGE, dir=(1, 0, 0)))
    y0, y1 = skirt_stiffener_taper_span()
    for wedge in wedges:
        box = wedge.bounding_box()
        if box.min.Y < y1 and box.max.Y > y0:
            raise ValueError(
                f"a skirt lead-in at y {box.min.Y:.3f} to {box.max.Y:.3f} "
                f"reaches the stiffener's IR-end taper at y {y0:.3f} to {y1:.3f}, "
                "so SIDE_SKIRT_THICKEN_RUN is too long"
            )
    skirt = _cut(skirt, *wedges)
    # A lead-in removes material only. Keep the catch lands outside this operation.
    return _cut(original, skirt)


def catch_windows():
    """Two rounded rectangles through the plain skirt at the IR end."""
    edge = board.board_profile().bounding_box().max.Y
    y = edge + (params.BOARD_FIT + SKIRT_OUT) / 2
    reach = (SKIRT_OUT - params.BOARD_FIT) / 2 + 0.3
    out = []
    for x in catch_x():
        plane = Plane(
            origin=(x, y, CATCH_Z0 + params.CATCH_H / 2),
            x_dir=(1, 0, 0),
            z_dir=(0, 1, 0),
        )
        sketch = plane * RectangleRounded(params.CATCH_W, params.CATCH_H, params.CATCH_R)
        out.append(extrude(sketch, amount=reach, both=True))
    return out


def catch_detents():
    """A wedge on the inside of the lap behind each window, thickest at its base.

    Built as the window's own profile, inset by the fit, intersected with the
    wedge. A plain rectangle lofted to a sliver is simpler and is what this was
    first: it fouled all four rounded corners and stood proud of the window's top,
    which is what the shells-mate pass reported.
    """
    edge = board.board_profile().bounding_box().max.Y
    base, tip = edge + LAP_IN + MERGE, edge + LAP_IN - params.CATCH_D
    f = params.CATCH_FIT
    z0, z1 = CATCH_Z0 + f, CATCH_Z0 + params.CATCH_H - f
    # The detent stands in along -Y at this end, so tip is below base in y and
    # every span below is taken as a magnitude with the direction carried by
    # copysign. Rectangle and extrude both refuse a negative one.
    reach = abs(tip - base)
    out = []
    for x in catch_x():
        plane = Plane(
            origin=(x, (base + tip) / 2, (z0 + z1) / 2), x_dir=(1, 0, 0), z_dir=(0, -1, 0)
        )
        profile = plane * RectangleRounded(
            params.CATCH_W - 2 * f, params.CATCH_H - 2 * f, max(params.CATCH_R - f, 0.2)
        )
        prism = extrude(profile, amount=reach / 2 + 1, both=True)
        wedge = loft(
            [
                Pos(x, (base + tip) / 2, z0) * Rectangle(params.CATCH_W + 2, reach),
                Pos(x, base + math.copysign(0.05, tip - base), z1)
                * Rectangle(params.CATCH_W + 2, 0.1),
            ],
            ruled=True,
        )
        out.append(_isect(prism, wedge))
    return out


def shared_cuts():
    """D1 and USB end-wall cuts shared by both shells, unchanged for U2's move."""
    return [usb_slot(), emitter_bore()]


@cache.solid
def back_shell():
    inner, outer = _profiles()
    form = back_form(0, 0)
    # Inset by the wall and lifted by the floor, so the shell keeps its thickness
    # around the rounded corner instead of thinning into it.
    cavity = back_form(params.WALL, params.FLOOR, params.FLOOR)

    shell = _isect(_slab(outer, SHELL_BACK, SHELL_SEAM), form)
    shell = _cut(
        shell,
        _isect(_slab(inner, SHELL_BACK, SHELL_SEAM + 1), cavity),
        *skirt_relief(),
    )

    # U2 receives through this shell's floor. Its opening and inside flange
    # rebate stay back-only; D1 and USB retain their shared end-wall cuts.
    shell = _fuse(
        shell,
        legacy_retention_post(),
        *support_runs(),
        *catch_detents(),
        *side_catch_detents(),
    )
    return _cut(
        shell,
        *shared_cuts(),
        ir_window_opening(),
        ir_window_rebate(),
        *end_screw_cuts(),
        end_screw_wall_chamfer(),
        legacy_retention_pilot(),
    )


OCC_CHAMFER_GAP = 1e-3
"""One micron, under print resolution: see _chamfer_usb_pocket_lip()."""


def _chamfer_usb_pocket_lip(shell):
    """Chamfer the pocket's inboard lip, where the USB connector catches.

    usb_pocket() leaves a square convex corner where its inboard wall meets
    the cavity ceiling at CAVITY_FRONT. The chamfer must come off the shell
    after the cut, not off the cut box: chamfering the box shrinks the void
    and adds material, which makes the catch worse. At the full wall height
    the cut consumes that face completely and leaves one 45 degree ramp with
    no square arris on top of it.

    The wall is measured off the built pocket, not off CAVITY_FRONT_USB: the
    pocket roof stands MERGE above that plane, and a chamfer sized from the
    plane alone leaves exactly the MERGE-tall arris this exists to remove.

    Where that wall stands is read off the same solid, and for the same reason.
    usb_pocket() reaches USB_POCKET_INBOARD_REACH past the connector's envelope
    and its clearance on this side alone, so the envelope plus USB_CLEARANCE is
    no longer where the wall is; reading the pocket is what makes the ramp
    follow the wall wherever the pocket puts it rather than having to be told
    twice. Its span across the pocket comes off the same box.

    Selected by position, as _uncut_support() selects its own edges: the one
    edge lying in the CAVITY_FRONT plane on the pocket's inboard wall that
    spans the pocket's width. Call this directly after the pocket cut, while
    the corner is still the only edge that matches. The count assertion makes
    a later geometry change fail here instead of cutting some other edge.
    """
    pocket = usb_pocket().bounding_box()
    wall = pocket.max.Z - CAVITY_FRONT
    if params.USB_POCKET_LIP_CHAMFER > wall + OCC_CHAMFER_GAP:
        raise ValueError(
            f"USB_POCKET_LIP_CHAMFER {params.USB_POCKET_LIP_CHAMFER} is past the "
            f"pocket wall's own {wall:.2f} height"
        )
    # OCCT refuses a chamfer that consumes its face exactly, and the full-height
    # value asks for exactly that, so stop one micron short of the pocket roof.
    length = min(params.USB_POCKET_LIP_CHAMFER, wall - OCC_CHAMFER_GAP)
    wall_y = pocket.max.Y
    span = pocket.size.X
    tol = 1e-4
    lip = [
        edge
        for edge in shell.edges()
        if abs(edge.bounding_box().min.Z - CAVITY_FRONT) < tol
        and abs(edge.bounding_box().max.Z - CAVITY_FRONT) < tol
        and abs(edge.center().Y - wall_y) < tol
        and edge.bounding_box().size.X > span / 2
    ]
    if len(lip) != 1:
        raise ValueError(f"expected one USB pocket lip edge, found {len(lip)}")
    return chamfer(lip, length)


def _cap_face_hole_cut(ref, fdm=False):
    """Face-hole prism plus a tapered mouth following this front's height.

    The recessed front meets a key hole at different Z around its perimeter,
    so a post-boolean edge chamfer is a fragmented non-planar loop that OCCT
    cannot chamfer reliably. Build a triangulated taper from the face depth at
    each outline point instead. The straight prism beneath it preserves the
    guide and the counterbore shoulder preserves the cap's retention.
    """
    x, y = board.components()[ref][:2]
    size = cap_face_hole(ref)
    amount = params.CAP_FACE_HOLE_CHAMFER
    depth = amount * math.tan(math.radians(params.CAP_FACE_HOLE_CHAMFER_ANGLE))
    inner_xy = cap_outline(size, x, y)
    outer_xy = cap_outline(size + 2 * amount, x, y)

    def surface_z(px, py):
        return front_face(True) if fdm else SHELL_FRONT - face_depth_at(px, py)

    inner_low = [(px, py, surface_z(px, py) - depth) for px, py in inner_xy]
    inner_high = [(px, py, surface_z(px, py) + MERGE) for px, py in inner_xy]
    outer_high = [(px, py, surface_z(px, py) + MERGE) for px, py in outer_xy]

    # A triangular tube around the opening: its sloped A-B wall is the visible
    # chamfer, while the other two walls merely close the cutter for OCCT. Each
    # quad is split into triangles because the dish makes its four corners
    # non-coplanar. This follows the face locally instead of introducing the
    # shelf a single planar loft made in an X/Y bisect.
    faces = []
    count = len(inner_xy)
    for index in range(count):
        following = (index + 1) % count
        for a, b, c, d in (
            (
                inner_low[index],
                inner_low[following],
                inner_high[following],
                inner_high[index],
            ),
            (
                inner_high[index],
                inner_high[following],
                outer_high[following],
                outer_high[index],
            ),
            (
                inner_low[index],
                inner_low[following],
                outer_high[following],
                outer_high[index],
            ),
        ):
            faces.append(Polygon(a, b, c))
            faces.append(Polygon(a, c, d))
    taper = Solid(Shell(faces))
    return _fuse(
        _key_prism(x, y, size, CAVITY_FRONT - 1, SHELL_FRONT + 1), taper
    )


@cache.solid
def front_shell(fdm=False):
    """The front shell. `fdm` swaps the one cut the face is finished with.

    Everything under the face is identical between the two, and deliberately
    so: the same bosses, ceiling, holes, counterbores, ducts and skirt, so a
    cap, a pad and a back shell fit either one. Two things differ, both on the
    outer plane. The recessed front takes keypad_recess(), the dish the keys sit
    in; the FDM front takes keypad_outline_groove(), that same recess's plan
    outline as a shallow slot, and stays flat everywhere else, because a dish
    that shallow over a span that wide cannot be printed face down and face down
    is the only way to print this part without support on its one cosmetic
    surface. And that face is built at front_face(fdm) rather than at
    SHELL_FRONT: flattening the dish at the raised level would keep every bit of
    material the dish removed, so the FDM face lands at the sunken level instead
    and the part comes out as slim as the one it stands in for. Its top edge
    carries a 45 degree chamfer where the recessed front has a round, leaving
    flat face outside the finer groove. See
    params.FDM_FACE_DROP, params.FDM_OUTLINE_W and params.EDGE_R_FRONT_FDM.
    """
    # The body is built to its own face and finished there before any key or
    # wheel hole is cut into it: the only top edge loop is the outer perimeter,
    # so its chamfer or fillet cannot land on an aperture's own edge.
    face = front_face(fdm)
    inner, outer = _profiles()
    body = _slab(outer, SKIRT_BOTTOM, face)
    top_edges = [e for e in body.edges() if e.bounding_box().min.Z > face - 0.01]
    body = (
        chamfer(top_edges, front_edge_round(True))
        if fdm
        else fillet(top_edges, front_edge_round(False))
    )
    shell = _cut(body, _slab(inner, SHELL_SEAM - 0.01, CAVITY_FRONT), *skirt_cuts())

    # The mic hears through the board, so the inlet is on the front. A duct down
    # to the board keeps it coupled to the board's own port hole instead of to
    # the whole cavity, and mic_bore() drills the funnel through it as one solid,
    # opening in the keypad recess's own curved floor rather than SHELL_FRONT.
    # The duct goes in solid: see mic_duct() for why it cannot be the tube it was.
    # Bosses reach the face, not CAVITY_FRONT: the keypad region's own
    # ceiling is too thin now to hold BOSS_PILOT_DEPTH under it, so each
    # boss carries its own material the rest of the way to the flat face,
    # the "local pad" the USB pocket has on the void side instead. No
    # overshoot past the face: the fuse already overlaps real volume
    # over the whole keypad ceiling's own depth, and going further would
    # poke the boss through the one outer face plane.
    bosses = [
        _chamfered_post(
            x,
            y,
            params.BOSS_OD,
            BOARD_TOP,
            face,
            params.STANDOFF_CHAMFER,
            "upper",
            CAVITY_FRONT,
        )
        for x, y in mount_points()
    ]
    shell = _fuse(
        shell,
        mic_duct(face),
        skirt_stiffener(),
        end_screw_block(),
        *bosses,
    )
    # No local pocket for D1 any more. It sat on the front of the board once,
    # its dome standing taller than the keypad region's own ceiling; on the
    # back it clears the front shell entirely except for the leads bent up
    # through the board, which stop well under CAVITY_FRONT.
    # The support ledges cross the skirt plane to reach the back lap. Match their
    # derived breaks in the skirt so the shells can close around them.
    shell = _cut(shell, usb_pocket())
    shell = _chamfer_usb_pocket_lip(shell)
    shell = _cut(
        shell,
        *front_support_cuts(),
        *skirt_lead_in_cuts().solids(),
        grip_skirt_relief(),
    )

    parts = board.components()
    # No collar cut around the bosses. key_size() sizes each key to clear them, so
    # subtracting the collar from the hole as well only shaves a sliver off the two
    # keys that sit at the limit, and it shows as ceiling overhanging a cap.
    #
    # Every key takes two holes now: the counterbore its cap's flange rides in,
    # and the narrower hole through the face land above that. The face hole runs
    # the full depth rather than stopping at the shoulder, which is harmless
    # because it is strictly inside the counterbore.
    keys = []
    for ref in board.refs("SW"):
        x, y = parts[ref][:2]
        keys.append(
            _key_prism(x, y, cap_counterbore(ref), CAVITY_FRONT - 1, COUNTERBORE_TOP)
        )
        keys.append(_cap_face_hole_cut(ref, fdm))
    pilots = [
        _hole(x, y, params.BOSS_PILOT_D, BOARD_TOP - 0.1, BOARD_TOP + params.BOSS_PILOT_DEPTH)
        for x, y in mount_points()
    ]
    return _cut(
        shell,
        *pilots,
        end_screw_pilot(),
        *catch_windows(),
        *side_catch_pockets(),
        wheel_opening(CAVITY_FRONT - 1, SHELL_FRONT + 1, fdm),
        led_ring_channel(fdm),
        mic_bore(),
        *keys,
        keypad_outline_groove() if fdm else keypad_recess(),
        *shared_cuts(),
    )
