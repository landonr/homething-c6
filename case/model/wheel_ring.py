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
by LED_RING_ROOF of translucent shell, its two walls plumb with a 45 degree
chamfer breaking each bottom corner so the mouth opens wider than the rest. The
four LEDs fire up into it and the channel carries their light around the wheel,
so the face shows a ring rather than four dots.
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

from .shape import _hole, _isect, _offset_face, _slab
from .stack import CAVITY_FRONT, LIP_CLEAR_R, SHELL_FRONT, WHEEL_OPENING_R

LED_RING_TOP = SHELL_FRONT - params.LED_RING_ROOF
"""Ceiling of the channel, and so the underside of the roof the ring glows
through."""


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
    """Plan-view boundary the wheel opening and the LED ring channel are kept
    inside of, clear of the case's own side wall by WHEEL_OPENING_EDGE. Idle
    for the opening at its current radius, live for the channel: its outer
    wall runs past this near the X axis, at the mouth by more than higher up
    now that LED_RING_CHAMFER breaks that corner, so the ring narrows against
    two chords there rather than cutting toward the wall, and stays continuous
    because the clip sits well outside the channel's inner radius at either
    end."""
    return _offset_face(params.BOARD_FIT - params.WHEEL_OPENING_EDGE)


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
    """The inner wall's nominal radius: LED_RING_WALL of web outside the wheel
    opening's bore. The wall is one 45 degree plane rather than a cylinder, so
    it holds this radius at exactly one height, LED_RING_CHAMFER above the
    mouth, and stands further out above it. Still the number the web is
    reasoned from, and still what the LEDs have to sit outside of; the
    light_path check is what catches a layout where the wall grows past an
    LED's inner edge."""
    return WHEEL_OPENING_R + params.LED_RING_WALL


def led_ring_outer_r():
    """The outer wall's nominal radius: LED_RING_OVER past the furthest LED's
    body edge, derived off the placements so moving an LED outward widens the
    channel rather than leaving it half covered. Crossed LED_RING_CHAMFER above
    the mouth, the same way the inner one is."""
    return led_radial_reach()[1] + params.LED_RING_OVER


def led_ring_mouth_inner_r():
    """Channel inner wall at the mouth, the closest the void ever comes to the
    bore. The whole wall is built off this: it is the fixed end, since the web
    left here is the ring's light barrier and there is none to spare."""
    return led_ring_inner_r() - params.LED_RING_CHAMFER


def led_ring_mouth_outer_r():
    """Channel outer wall at the mouth, its widest. What _opening_clip() has to
    answer for, rather than any radius above it."""
    return led_ring_outer_r() + params.LED_RING_CHAMFER


def led_ring_roof_inner_r():
    """Channel inner wall where it meets the roof, at its furthest from the
    bore. Derived, not set: 45 degrees over the wall's own height means the
    radius travels exactly that height."""
    return led_ring_mouth_inner_r() + led_ring_wall_height()


def led_ring_roof_outer_r():
    """Channel outer wall where it meets the roof, at its nearest the wheel."""
    return led_ring_mouth_outer_r() - led_ring_wall_height()


def led_ring_roof_flat():
    """Width of the flat the channel actually presents to its roof, once both
    walls have converged across the full height. The surface the ring glows
    through, and what has to stay over the LEDs: light_path is what proves it
    does."""
    return led_ring_roof_outer_r() - led_ring_roof_inner_r()


def led_ring_web_left():
    """Thinnest web left between the bore and the channel: LED_RING_WALL less
    the chamfer, down at the mouth where the wall comes closest. The ring's
    inner light barrier at its weakest, and what bounds LED_RING_CHAMFER."""
    return led_ring_mouth_inner_r() - WHEEL_OPENING_R


def led_ring_wall_height():
    """Height of the channel's wall: ceiling underside to the roof. Not the
    cut's own height, which starts a millimetre lower; that overrun is inside
    the cavity, where there is no wall. At 45 degrees this is also the radial
    distance each wall travels, which is what closes the roof flat down to
    led_ring_roof_flat()."""
    return LED_RING_TOP - CAVITY_FRONT


def led_ring_channel():
    """The channel itself, as the cut: an annular void from below the ceiling
    underside (open to the cavity, which is where the LED light comes from) up
    to LED_RING_TOP, clipped by _opening_clip() where its outer radius would
    otherwise run into the side wall's own ceiling margin.

    Neither wall is plumb anywhere. Each is one 45 degree plane running the
    channel's whole height, widest at the mouth and converging on the roof, so
    the section is a trapezoid closing upward. The mouth is the fixed end
    because that is where the web to the bore is thinnest and there is none to
    give away; the roof is wherever 45 degrees over led_ring_wall_height()
    leaves it, and what is left there is led_ring_roof_flat(). Revolved from
    that section rather than cut as two cylinders, which is what the plain
    rectangle was.

    Flaring the mouth is what the light wants: it enters there, off LEDs firing
    up out of the cavity, and a wall raked away from them puts more of the roof
    in view of each one. A 45 degree rake is also what a printer can close a
    ceiling over without support.

    The overrun below the ceiling underside holds the mouth radii. It is there
    to break the cut through into the cavity, and carrying the widest width down
    through it is what leaves the cavity ceiling a clean edge rather than a
    feather.
    """
    x, y = board.wheel_center()
    z0, z1 = CAVITY_FRONT - 1, LED_RING_TOP
    mouth_inner, mouth_outer = led_ring_mouth_inner_r(), led_ring_mouth_outer_r()
    with BuildSketch(Plane.XZ) as section:
        with BuildLine():
            Polyline(
                (mouth_inner, z0),
                (mouth_outer, z0),
                (mouth_outer, CAVITY_FRONT),
                (led_ring_roof_outer_r(), z1),
                (led_ring_roof_inner_r(), z1),
                (mouth_inner, CAVITY_FRONT),
                close=True,
            )
        make_face()
    channel = Pos(x, y, 0) * revolve(section.sketch, Axis.Z)
    return _isect(channel, _slab(_opening_clip(), z0, z1))


def wheel_opening(z0, z1):
    """The shell's wheel opening: one plain bore at WHEEL_OPENING_R, ceiling
    underside to flat face, so below the keypad recess's wheel basin the face closes in flush
    to the wheel's main rotating body with only WHEEL_OPENING_CLEARANCE between
    them. The top of the bore is opened out by that recess instead, a dish on
    the same axis whose floor the bore breaks through. No countersink and no
    window any more: nothing seats in it, and the LEDs show through the
    translucent face itself rather than through an opening."""
    x, y = board.wheel_center()
    return _isect(
        _hole(x, y, 2 * WHEEL_OPENING_R, z0, z1), _slab(_opening_clip(), z0, z1)
    )
