"""The clearance band the pad keeps around the wheel, the shell's own wheel
opening, and the LED ring channel. The seat around that opening is the rotary
keypad recess's now, built in keypad.py as a dish centred on the wheel rather
than as a recess of its own here.

The fixed radii these are built from live in stack.py, since the keypad's
pockets and the checks read them too; the pad's own bore and the channel's
radii are derived here off the LED placements instead. There used to be a
moulded light-pipe ring here, a plug rising through a countersunk shell
window off a flange that reached out over the LEDs; the translucent case
material diffuses better than the silicone did, so the pad gets out of the
light's way entirely and the light pipe is now a void inside the shell: an
annular channel circling the wheel opening, open to the cavity below, roofed
by LED_RING_ROOF of translucent shell. Its inner wall stands plumb, so the web
to the wheel's bore is a full LED_RING_WALL at every height; its outer wall is
one 45 degree plane over the whole height, widest at the mouth, so the light
enters across a flare. The four LEDs fire up into it and the channel carries
their light around the wheel, so the face shows a ring rather than four dots.
"""

import math

from build123d import (
    Axis,
    BuildLine,
    BuildSketch,
    Plane,
    Polyline,
    Pos,
    make_face,
    revolve,
)

import board
import params

from .shape import _face_reach, _fuse, _hole, _isect, _offset_face, _slab
from .stack import (
    CAVITY_FRONT,
    FDM_FACE,
    LIP_CLEAR_R,
    MERGE,
    SHELL_FRONT,
    WHEEL_OPENING_R,
)

LED_RING_TOP = SHELL_FRONT - params.LED_RING_ROOF
"""Ceiling of the channel, and so the underside of the roof the ring glows
through."""


def led_ring_top(fdm=False):
    """Ceiling of the channel on either front.

    The recessed front uses the full channel. The FDM front shortens that wall
    from the cavity side, leaving a thicker roof under its lower flat face.
    """
    if not fdm:
        return LED_RING_TOP
    return CAVITY_FRONT + params.FDM_LED_RING_DEPTH_RATIO * (
        LED_RING_TOP - CAVITY_FRONT
    )


def led_y_reach():
    """Furthest any status LED's body edge sits from the wheel centre in y:
    the reach the pad's cut has to uncover."""
    _, wy = board.wheel_center()
    parts = board.components()
    return max(
        abs(parts[ref][1] - wy) + params.LED_BODY / 2 for ref in board.refs("D")[1:]
    )


def pad_clear_y():
    """Half-width of the band around the wheel the pad has to stay out of, in y
    off the wheel centre: whichever asks for more of the lip's own rotating
    clearance and led_y_reach() plus PAD_LED_CLEARANCE. The lip governs at the
    present layout, so the LEDs come uncovered with room to spare, but the LED
    term is derived off their placements so moving one outward can take over
    rather than quietly ending up back under silicone.

    A requirement rather than a cut now. The pad used to be one full-width slab
    and this band was subtracted from it, severing it in two; the pad is two
    tight lobes that stop short of the band on their own, and
    case.pad_wheel_gap() is what measures by how much."""
    return max(LIP_CLEAR_R, led_y_reach() + params.PAD_LED_CLEARANCE)


def _opening_clip():
    """Plan-view boundary the wheel opening is kept inside of, clear of the
    case's own side wall by WHEEL_OPENING_EDGE. Idle at the opening's current
    radius, which stops well short of it. The LED ring channel used to share
    this clip and has _channel_clip() instead, because the channel is wanted
    flush to the cavity wall rather than held a ledge off it."""
    return _offset_face(params.BOARD_FIT - params.WHEEL_OPENING_EDGE)


def _channel_clip():
    """Plan-view boundary the LED ring channel is kept inside of: the cavity
    wall itself, so where the channel runs out to the wall it stops flush
    against it.

    Live near the X axis, where the mouth's own radius reaches past the wall and
    the ring narrows against two chords. Those chords are the wall, not a ledge
    short of it, so the channel opens into the cavity along the wall the same
    way its mouth opens into the cavity everywhere else, and the roof over it
    lands on a full-height wall rather than on a strip of ceiling. Holding it a
    ledge short left a square corner against the cavity ceiling instead, which
    this removes rather than breaks.

    The ring stays continuous because the wall sits well outside the channel's
    plumb inner wall at either end."""
    return _offset_face(params.BOARD_FIT)


def led_ring_clip_reach(angle):
    """How far from the wheel centre _channel_clip() lets the channel run, along
    the ray at `angle` radians, measured on the clip face rather than worked
    back out of BOARD_FIT.

    Near the X axis this comes in short of led_ring_mouth_outer_r() and the
    channel is chorded off against the cavity wall there. Everywhere else it
    lands far outside the channel and the clip does nothing.
    """
    x, y = board.wheel_center()
    return _face_reach(_channel_clip(), x, y, angle)


def led_radial_reach():
    """(nearest, furthest) any status LED's body reaches from the wheel
    centre, radially: the band the channel has to straddle."""
    wx, wy = board.wheel_center()
    parts = board.components()
    radii = [
        math.hypot(parts[ref][0] - wx, parts[ref][1] - wy)
        for ref in board.refs("D")[1:]
    ]
    return min(radii) - params.LED_BODY / 2, max(radii) + params.LED_BODY / 2


def led_ring_inner_r():
    """The inner wall's radius: LED_RING_WALL of web outside the wheel opening's
    bore. The wall is a plain cylinder, so it holds this radius over the
    channel's whole height and the web is the full LED_RING_WALL at every one of
    them. Also what the LEDs have to sit outside of; the light_path check is
    what catches a layout where the wall grows past an LED's inner edge."""
    return WHEEL_OPENING_R + params.LED_RING_WALL


def led_ring_outer_r():
    """The outer wall's nominal radius: LED_RING_OVER past the furthest LED's
    body edge, derived off the placements so moving an LED outward widens the
    channel rather than leaving it half covered. This wall rakes, so it crosses
    this radius LED_RING_CHAMFER above the mouth rather than holding it."""
    return led_radial_reach()[1] + params.LED_RING_OVER


def led_ring_mouth_outer_r():
    """Channel outer wall at the mouth, its widest. What _channel_clip() has to
    answer for, rather than any radius above it."""
    return led_ring_outer_r() + params.LED_RING_CHAMFER


def led_ring_roof_inner_r():
    """Channel inner wall where it meets the roof. The wall is plumb, so this is
    led_ring_inner_r() again. Kept as a name because the roof is spoken of as a
    pair of radii and the outer one does travel; there is no matching mouth name,
    since the mouth's inner end is the same radius as well."""
    return led_ring_inner_r()


def led_ring_roof_outer_r(fdm=False):
    """Channel outer wall where it meets the roof, at its nearest the wheel."""
    return led_ring_mouth_outer_r() - led_ring_wall_height(fdm)


def led_ring_roof_flat(fdm=False):
    """Width of the flat the channel presents to its roof, once the outer wall
    has raked in across the full height. Only that wall travels, so the flat
    closes from one side. The surface the ring glows through, and what has to
    stay over the LEDs: light_path is what proves it does."""
    return led_ring_roof_outer_r(fdm) - led_ring_roof_inner_r()


def led_ring_web_left():
    """Web left between the bore and the channel: the whole of LED_RING_WALL,
    at every height, because the inner wall is plumb and no longer rakes in
    toward the bore at the mouth. The ring's inner light barrier; led_ring
    probes it on the built shell rather than trusting this."""
    return led_ring_inner_r() - WHEEL_OPENING_R


def led_ring_wall_height(fdm=False):
    """Height of the channel's wall: ceiling underside to the roof. Not the
    cut's own height, which starts a millimetre lower; that overrun is inside
    the cavity, where there is no wall. The outer wall rakes at 45 degrees, so
    this is also how far that wall travels radially, which is what closes the
    roof flat down to led_ring_roof_flat(). The inner wall is plumb and travels
    nothing."""
    return led_ring_top(fdm) - CAVITY_FRONT


def led_ring_channel(fdm=False):
    """The channel itself, as the cut: an annular void from below the ceiling
    underside (open to the cavity, which is where the LED light comes from) up
    to LED_RING_TOP, clipped by _channel_clip() where its outer radius would
    otherwise run past the cavity wall.

    The two walls differ. The inner one is a plain cylinder at
    led_ring_inner_r(), plumb over the whole height, so the web behind it is a
    full LED_RING_WALL everywhere rather than thinnest at the mouth. That web is
    the ring's light barrier and the wheel's own seat, and neither wants it
    spent to flare a wall that faces the bore instead of an LED. The outer one is
    one 45 degree plane running the whole height, widest at the mouth and raking
    in to led_ring_roof_outer_r(), so the section is a right trapezoid that
    closes from one side and leaves led_ring_roof_flat() at the top.

    Flaring the outer wall is what the light wants: it enters at the mouth, off
    LEDs firing up out of the cavity, and a wall raked away from them puts more
    of the roof in view of each one. A 45 degree rake is also what a printer can
    close a ceiling over without support. Revolved from that section rather than
    cut as two cylinders, which is what the plain rectangle was.

    The overrun below the ceiling underside holds the mouth radii. It is there
    to break the cut through into the cavity, and carrying the widest width down
    through it is what leaves the cavity ceiling a clean edge rather than a
    feather.
    """
    x, y = board.wheel_center()
    z0, z1 = CAVITY_FRONT - 1, led_ring_top(fdm)
    inner, mouth_outer = led_ring_inner_r(), led_ring_mouth_outer_r()
    with BuildSketch(Plane.XZ) as section:
        with BuildLine():
            Polyline(
                (inner, z0),
                (mouth_outer, z0),
                (mouth_outer, CAVITY_FRONT),
                (led_ring_roof_outer_r(fdm), z1),
                (inner, z1),
                close=True,
            )
        make_face()
    channel = Pos(x, y, 0) * revolve(section.sketch, Axis.Z)
    return _isect(channel, _slab(_channel_clip(), z0, z1))


def fdm_wheel_opening_r():
    """Radius of the FDM front's own bore: WHEEL_OPENING_R plus
    FDM_WHEEL_OPENING_CLEARANCE.

    The recessed front's bore stays at WHEEL_OPENING_R, and so does
    led_ring_inner_r(), which is derived off it. The extra radius is spent out
    of the web on this one shell rather than by moving the LED ring channel,
    which is the whole reason the FDM front carries a clearance of its own."""
    return WHEEL_OPENING_R + params.FDM_WHEEL_OPENING_CLEARANCE


def fdm_wheel_mouth_r():
    """Widest the FDM front's wheel opening gets, at the face itself, once
    FDM_WHEEL_OPENING_CHAMFER has opened the bore out at 45 degrees.

    What the budget against LED_RING_WALL is measured on, and what the flat face
    has to resume outside of."""
    return fdm_wheel_opening_r() + params.FDM_WHEEL_OPENING_CHAMFER


def _fdm_mouth_budget():
    """Refuse an FDM mouth that reaches the LED ring channel's inner wall.

    The FDM front's widening is taken out of the web, which is a full
    LED_RING_WALL of shell between the bore and the channel, and the widened
    bore plus its chamfer are both spent out of it. At LED_RING_WALL exactly
    the mouth's outer edge goes coincident with the channel's inner wall, which
    is the same coincident-edge trap FDM_OUTLINE_EDGE_CLEAR exists for and
    tears an exported mesh while every solid reading still looks right, so the
    bound is exclusive."""
    spent = params.FDM_WHEEL_OPENING_CLEARANCE + params.FDM_WHEEL_OPENING_CHAMFER
    if spent >= params.LED_RING_WALL:
        raise ValueError(
            f"FDM_WHEEL_OPENING_CLEARANCE {params.FDM_WHEEL_OPENING_CLEARANCE} plus "
            f"FDM_WHEEL_OPENING_CHAMFER {params.FDM_WHEEL_OPENING_CHAMFER} spends "
            f"{spent:.2f} of the {params.LED_RING_WALL:.2f} web LED_RING_WALL leaves "
            "between the wheel opening and the LED ring channel's inner wall"
        )


def wheel_opening(z0, z1, fdm=False):
    """The shell's wheel opening: one plain bore at WHEEL_OPENING_R, ceiling
    underside to flat face, so below the keypad recess's wheel basin the face closes in flush
    to the wheel's main rotating body with only WHEEL_OPENING_CLEARANCE between
    them. The top of the bore is opened out by that recess instead, a dish on
    the same axis whose floor the bore breaks through. No countersink and no
    window any more: nothing seats in it, and the LEDs show through the
    translucent face itself rather than through an opening.

    `fdm` swaps that bore for the printed front's own, the way
    stack.front_face(fdm) swaps the face it rises to. Two things change and
    both follow from that face being flat. The bore widens by
    FDM_WHEEL_OPENING_CLEARANCE, because a printed bore comes back tighter than
    the solid and there is no dish above it taking the fit off the knob. And a
    truncated cone is fused onto the cut, standing at the bore's own radius
    FDM_WHEEL_OPENING_CHAMFER below the face and opening out by that much again
    at it, so the arris the flat face would otherwise leave becomes a 45 degree
    lead-in. The cone carries on past the face at the same rake, so the cut
    breaks through rather than ending on a surface coincident with it.

    Both are spent out of the web, which _fdm_mouth_budget() is what holds.
    Neither touches WHEEL_OPENING_R, since led_ring_inner_r() is derived off it
    and the LED ring channel would travel with any change to it.

    The cone is fused before the clip rather than after, so it is trimmed at
    the case's own side wall exactly as the bore is, rather than reaching past
    a boundary the bore respects."""
    x, y = board.wheel_center()
    if not fdm:
        tool = _hole(x, y, 2 * WHEEL_OPENING_R, z0, z1)
        return _isect(tool, _slab(_opening_clip(), z0, z1))

    _fdm_mouth_budget()
    bore = fdm_wheel_opening_r()
    base = FDM_FACE - params.FDM_WHEEL_OPENING_CHAMFER
    # The rake runs on past the face by MERGE so the cone leaves the solid
    # rather than ending in its surface, the same overrun every other cut here
    # takes for the same reason.
    reach = params.FDM_WHEEL_OPENING_CHAMFER + MERGE
    with BuildSketch(Plane.XZ) as section:
        with BuildLine():
            Polyline(
                (bore, base),
                (bore + reach, base + reach),
                (bore, base + reach),
                close=True,
            )
        make_face()
    cone = Pos(x, y, 0) * revolve(section.sketch, Axis.Z)
    tool = _fuse(_hole(x, y, 2 * bore, z0, z1), cone)
    return _isect(tool, _slab(_opening_clip(), z0, z1))
