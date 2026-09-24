"""The two shells and their joint features: the front skirt, the deep catch
section, the back lap, and the detents.
"""

import math

from build123d import (
    Box,
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


def side_skirt_stiffeners():
    """Inward material along both side skirts, clear of the board's edge."""
    box = board.board_profile().bounding_box()
    band = _ring(
        params.BOARD_FIT - params.SIDE_SKIRT_THICKEN,
        params.BOARD_FIT + MERGE,
        SKIRT_BOTTOM,
        SHELL_SEAM,
    )
    reach = params.BOARD_FIT + params.WALL + MERGE
    clips = [
        Pos(x, box.center().Y, (SKIRT_BOTTOM + SHELL_SEAM) / 2)
        * Box(2 * reach, box.size.Y + 2 * reach, SHELL_SEAM - SKIRT_BOTTOM)
        for x in (box.min.X - reach, box.max.X + reach)
    ]
    return [_isect(band, clip) for clip in clips]


def side_catch_y():
    """Catch station near the lengthwise centre of the board."""
    box = board.board_profile().bounding_box()
    y = box.center().Y + params.SIDE_CATCH_CENTER_OFFSET
    if not box.min.Y < y - params.SIDE_CATCH_W / 2 < y + params.SIDE_CATCH_W / 2 < box.max.Y:
        raise ValueError("side catch pocket reaches a board end")
    return y


def side_catch_bottom():
    """Centre the pocket in the ledge-free height up to the raised seam."""
    return (SUPPORT_TOP + SHELL_SEAM - params.SIDE_CATCH_H) / 2


def side_catch_pockets():
    """Blind rounded pockets with a bevel all around each exterior mouth."""
    box = board.board_profile().bounding_box()
    z0 = side_catch_bottom()
    if z0 + params.SIDE_CATCH_H >= SHELL_SEAM:
        raise ValueError("side catch pocket reaches the top of the skirt")
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


def side_catch_detents():
    """Back-lap detents chamfered on both insertion and release sides."""
    box = board.board_profile().bounding_box()
    z0 = side_catch_bottom() + params.SIDE_CATCH_FIT
    z1 = z0 + params.SIDE_CATCH_H - 2 * params.SIDE_CATCH_FIT
    depth = params.SIDE_CATCH_D
    fit = params.SIDE_CATCH_FIT
    land = params.SIDE_CATCH_LAND_H
    if not 0 < land < z1 - z0:
        raise ValueError("side catch land must fit inside the detent height")
    middle = (z0 + z1) / 2
    out = []
    for side, edge in ((-1, box.min.X), (1, box.max.X)):
        base = edge + side * LAP_IN
        tip = base - side * depth
        plane = Plane(
            origin=((base + tip) / 2, side_catch_y(), (z0 + z1) / 2),
            x_dir=(0, 1, 0), z_dir=(-side, 0, 0),
        )
        profile = plane * RectangleRounded(
            params.SIDE_CATCH_W - 2 * fit,
            params.SIDE_CATCH_H - 2 * fit,
            max(params.SIDE_CATCH_R - fit, 0.1),
        )
        prism = extrude(profile, amount=depth / 2 + MERGE, both=True)
        wedge = loft(
            [
                Pos(base - side * 0.05, side_catch_y(), z0)
                * Rectangle(0.1, params.SIDE_CATCH_W + 2),
                Pos((base + tip) / 2, side_catch_y(), middle - land / 2)
                * Rectangle(depth, params.SIDE_CATCH_W + 2),
                Pos((base + tip) / 2, side_catch_y(), middle + land / 2)
                * Rectangle(depth, params.SIDE_CATCH_W + 2),
                Pos(base - side * 0.05, side_catch_y(), z1)
                * Rectangle(0.1, params.SIDE_CATCH_W + 2),
            ],
            ruled=True,
        )
        out.append(_isect(prism, wedge))
    return out


def grip_skirt_relief():
    """Shave the hidden skirt around the grip end for closing clearance."""
    box = board.board_profile().bounding_box()
    band = _ring(
        SKIRT_OUT - params.GRIP_SKIRT_RELIEF,
        SKIRT_OUT + MERGE,
        SKIRT_BOTTOM - 0.1,
        SHELL_SEAM,
    )
    clip = Pos(
        box.center().X,
        box.min.Y + (params.WALL - 2 * (params.WALL + MERGE)) / 2,
        (SKIRT_BOTTOM + SHELL_SEAM) / 2,
    ) * Box(
        box.size.X + 2 * (params.WALL + MERGE),
        params.WALL + 2 * (params.WALL + MERGE),
        SHELL_SEAM - SKIRT_BOTTOM + 0.2,
    )
    return _isect(band, clip)


DEEP_BOTTOM = BOARD_TOP - params.CATCH_SKIRT_H
"""How far the skirt reaches at the IR end."""

CATCH_Z0 = DEEP_BOTTOM + params.CATCH_RISE
"""Bottom of each window, and so the top of the skirt that catches under a detent."""


def catch_region():
    """Limits the deepened skirt to the IR end."""
    box = board.board_profile().bounding_box()
    y0 = box.max.Y + params.BOARD_FIT + params.WALL
    return Pos(box.center().X, y0 - params.CATCH_SPAN / 2, 0) * Box(
        300, params.CATCH_SPAN, 300
    )


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


def deep_skirt():
    """The skirt carried further down, at the IR end only."""
    return _isect(
        _ring(params.BOARD_FIT, SKIRT_OUT, DEEP_BOTTOM, SKIRT_BOTTOM + MERGE),
        catch_region(),
    )


@cache.solid
def skirt_lead_in_cuts():
    """Return material removed from the skirt for the folding lead-ins."""
    if params.SKIRT_TRANSITION_CHAMFER <= 0:
        return Compound([])
    skirt = _fuse(
        _ring(params.BOARD_FIT, SKIRT_OUT, SKIRT_BOTTOM, SHELL_SEAM),
        deep_skirt(),
        *side_skirt_stiffeners(),
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
            ((box.min.Y, box.min.Y, SKIRT_BOTTOM, height, -1),
             (box.max.Y, box.max.Y, SKIRT_BOTTOM, height, 1))
        )
    # +1: the deepened region lies on the +Y side of this edge, and a wedge's
    # own local x runs +Y, so the lead-in has to ramp into the deep skirt.
    catch_y = catch_region().bounding_box().min.Y
    profiles.append(
        (catch_y, catch_y, DEEP_BOTTOM, params.SKIRT_TRANSITION_CHAMFER, 1)
    )
    if not 0 < params.SKIRT_LEAD_ANGLE < 90:
        raise ValueError("SKIRT_LEAD_ANGLE must be between 0 and 90 degrees")
    slope = math.tan(math.radians(params.SKIRT_LEAD_ANGLE))

    # The two IR-end support lead-ins and the deep-skirt lead-in are the same
    # angle. Put them on the same plane as well, so each wall reads as one
    # straight ramp instead of two parallel facets with a small step between.
    # Its foot has to land where the deep lead-in's head is, which is short of
    # the support cut's own face, so the wedge carries a flat back to that face:
    # a bare triangle there leaves the skirt between the two as a loose block.
    deep_top = DEEP_BOTTOM + params.SKIRT_TRANSITION_CHAMFER
    ir_support_y = max(
        edge_y
        for edge_y, _, _, _, direction in profiles
        if direction > 0 and edge_y < catch_y
    )
    profiles = [
        (
            edge_y,
            catch_y - (bottom + height - deep_top) / slope
            if direction > 0 and abs(edge_y - ir_support_y) < tolerance
            else wedge_y,
            bottom,
            height,
            direction,
        )
        for edge_y, wedge_y, bottom, height, direction in profiles
    ]
    wedges = []
    for edge_y, wedge_y, bottom, height, direction in profiles:
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
                origin=(box.min.X - MERGE, wedge_y, bottom),
                x_dir=(0, 1, 0), z_dir=(1, 0, 0),
            )
            back = min(edge_y - wedge_y, 0.0)
            # Start the same-angle ramp slightly into the skirt, with a short
            # flat cut back to the support break. The same Y relief applies at
            # either direction and keeps the IR-end ramps on their shared plane.
            fit = params.SKIRT_LEAD_FIT
            points = [
                (back, 0),
                (direction * (run + fit), 0),
                (direction * fit, height),
                (back, height),
            ]
            wedge = plane * Polygon(*points, align=None)
            wedges.append(extrude(wedge, amount=box.size.X + 2 * MERGE, dir=(1, 0, 0)))
    skirt = _cut(skirt, *wedges)
    # A lead-in removes material only. Keep the catch lands outside this operation.
    return _cut(original, skirt)


def catch_windows():
    """Two rounded rectangles through the deepened skirt."""
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


def catch_relief():
    """The back's lap is hollowed out this much further down over the deepened
    section, so the longer skirt has somewhere to go. Carry the cut back to the
    IR-end support faces so the relief and ledges meet at one flush edge rather
    than leaving a narrow strip of lap between them."""
    region = catch_region()
    runs = support_runs()
    if not runs:
        raise ValueError("catch relief needs at least one board support run")
    box = region.bounding_box()
    support_end = max(run.bounding_box().max.Y for run in runs)
    y0 = min(box.min.Y, support_end)
    region = Pos(box.center().X, (y0 + box.max.Y) / 2, 0) * Box(
        box.size.X, box.max.Y - y0, box.size.Z
    )
    return _isect(
        _ring(
            params.BOARD_FIT - 6,
            LAP_IN,
            DEEP_BOTTOM - params.SKIRT_FIT,
            SKIRT_BOTTOM,
        ),
        region,
    )


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
    shell = _cut(shell, catch_relief())
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
        deep_skirt(),
        *side_skirt_stiffeners(),
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
