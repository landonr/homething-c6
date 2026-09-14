"""Light path: the pad is genuinely open over each LED, the LED fires up into
the ring channel's void rather than into material, and the roof over the
channel is genuinely solid, so the light exits through case material rather
than into silicone or out an accidental hole. The moulded light-pipe ring
these passes once probed is gone: the pad no longer reaches over the LEDs at
all; the light pipe is the channel inside the shell now. The roof is measured
up to the local front-face floor, which the keypad recess dishes down where its
wheel dish's diagonals and both its necks cross the channel, rather than to any
one plane.

Led ring: the channel itself, on the built shell. Void all the way around
(one blocked sector and the ring shows as arcs, which is the failure the
feature exists to avoid), a solid web between it and the wheel opening's
bore, and a solid roof over it everywhere, including where the keypad recess
overlaps it in plan and the roof is at its thinnest. The web is
probed where LED_RING_CHAMFER leaves it narrowest, down at the mouth, since that
is the corner the chamfer breaks and a probe standing at the wall's own radius
would miss the one end that can run out of material.

Wheel seat clearance: the shell's own wheel opening clears the housing and
knob (board.wheel_profile()'s main_od and top) by WHEEL_OPENING_CLEARANCE, its
own gap rather than the pad's WHEEL_CLEARANCE, at every
height from the ceiling underside to the knob's own peak, and the lip stays
clear of the ceiling in the first place. Replaces a claim that the shell's
opening had to match the lip so it could pass through on assembly, which
does not happen: the board is lowered into an already-closed front shell, so
the lip never transits the ceiling. Probed on the built shell by bisecting
for the true opening radius, not trusted from WHEEL_OPENING_R, because this
exact feature was once silently erased by a stale full-ceiling clearance cut
while the formulas behind it still looked right on paper.

Wheel rotation clearance: nothing of the pad or the front shell may intrude
inside the wheel's rotating envelope, at the lip's own clearance radius at and
below its top face and at the main body's clearance above it, where the shell's
opening now closes in flush.
"""

import math

import board
import case
import params
from build123d import Cylinder, Pos

from .common import (
    OPENING_PROBE_H,
    OPENING_PROBE_R,
    PROBE_D,
    TOLERANCE,
    _fill_fraction,
    _opening_radius,
    _volume,
)


def light_path(shells, pad):
    """Each LED fires up through open air into the ring channel, and the roof
    over it is solid translucent shell.

    All three legs of the path: the pad's wheel cut genuinely uncovers the LED
    (probe the pad over the package and expect air, the inverse of the flange
    this replaced), the shell is genuinely open from the package top to the
    channel's own ceiling (the LED must land in the void, not under the
    channel's inner or outer rim), and the roof is genuinely closed between
    there and the local face floor, the thinnest the face gets over an LED, so
    the light lands on case material rather than escaping through a hole that
    should not exist over an LED.
    """
    problems = _ring_stack_sane()
    if problems:
        return problems
    parts = board.components()
    z0 = params.BOARD_THICKNESS + params.LED_HEIGHT
    for ref in board.refs("D")[1:]:
        x, y, _, _ = parts[ref]
        opening = Pos(x, y, (z0 + case.PAD_WEB_TOP) / 2) * Cylinder(
            radius=PROBE_D / 2, height=case.PAD_WEB_TOP - z0
        )
        if _volume(pad.intersect(opening)) > TOLERANCE:
            problems.append(f"{ref} is still covered: silicone over it")

        channel = Pos(x, y, (z0 + case.LED_RING_TOP) / 2) * Cylinder(
            radius=PROBE_D / 2, height=case.LED_RING_TOP - z0 - 0.02
        )
        if _volume(shells.intersect(channel)) > TOLERANCE:
            problems.append(f"{ref} fires into material: the channel is not open over it")

        floor = case.face_floor_at(x, y)
        roof = Pos(x, y, (case.LED_RING_TOP + floor) / 2) * Cylinder(
            radius=PROBE_D / 2, height=floor - case.LED_RING_TOP - 0.04
        )
        if _fill_fraction(shells, roof) < 0.99:
            problems.append(f"{ref} has no solid roof above the channel to shine through")
    return problems


WEB_PROBE_D = 0.2
"""Width of led_ring's web probe. Narrower than the shared PROBE_D because the
web is LED_RING_WALL less LED_RING_CHAMFER where the chamfer bites at the mouth
and PROBE_D no longer fits inside that with any margin: a probe that hangs into
the channel reads a sound web as open. Small enough to leave room either side
down there, which is the only height where the fit is close."""

ROOF_FLAT_MIN = 0.5
"""Narrowest roof flat led_ring will accept between the channel's two walls.
Both run at 45 degrees over the full height, so the flat is the mouth's width
less twice that height and it closes as either end moves. A floor rather than a
design target: the probes need somewhere to stand, and a ring glowing through a
slit narrower than this is not the ring the feature is for."""

ROOF_LEFT_MIN = 0.5
"""Thinnest translucent roof the ring may glow through, wherever the keypad
recess crosses the channel. Bounded by the print, a roof this thin bridging a
void, rather than by anything optical: the shell diffuses better the thicker it
is, so nothing optical wants it near the floor."""

LED_RING_SAMPLES = 24
"""Angles sampled around the channel for led_ring: 15 degrees apart, a few
millimetres of arc at the channel's own radius, so anything blocking enough of
the ring to show as a dark sector is caught. The count was once justified by
the gap between the two keypad islands, a sector the ring had to survive; no
keypad recess reaches the channel at all now, so arc length is most of what it
answers to. The other half is the roof probe riding along with it: the rotary
recess thins the roof on the four diagonals and where each neck crosses, and 24
samples land on all of those exactly."""


def _ring_stack_sane():
    """Arithmetic bounds the probes need before they can even be built: the
    channel's ceiling has to sit above its floor and far enough below the dished
    face that a roof is left, and the two 45 degree walls have to still leave a
    roof between them, or the probe cylinders come out with non-positive heights
    or standing in material and the pass dies in build123d instead of reporting
    what went wrong."""
    problems = []
    if case.LED_RING_TOP <= case.CAVITY_FRONT + 0.1:
        problems.append(
            f"LED_RING_ROOF leaves no channel: ceiling {case.LED_RING_TOP:.2f} "
            f"against the cavity underside at {case.CAVITY_FRONT:.2f}"
        )
    if case.ring_roof_left() <= ROOF_LEFT_MIN:
        problems.append(
            f"the keypad recess leaves only {case.ring_roof_left():.2f} of roof "
            f"over the ring channel, wants {ROOF_LEFT_MIN:.2f}: the recess is "
            "deeper than LED_RING_ROOF can spend where the wheel dish's "
            "diagonals or a neck cross the channel"
        )
    if case.led_ring_roof_flat() <= ROOF_FLAT_MIN:
        problems.append(
            f"the channel's walls leave only {case.led_ring_roof_flat():.2f} of "
            f"roof flat between them, wants {ROOF_FLAT_MIN:.2f}: at 45 degrees "
            "each wall travels the channel's own height, so a taller channel or "
            "a narrower mouth closes the ring off at the top"
        )
    return problems


def led_ring(front):
    """The channel proves out on the built shell, all the way around.

    Three probes per angle, at a radius just inside the channel's inner wall
    so the clip chords near the X axis can never reach it: the channel itself
    is void (a blocked sector turns the ring into arcs), the web between it
    and the wheel opening's bore is solid (or the opening stops being a
    closed seat and light leaks at the wheel instead of through the roof),
    and the roof above it is solid up to the local front-face floor, which is
    where it is thinnest wherever the keypad recess overlaps the ring in plan.

    All three run the channel's full height, so where they can stand is set by
    the narrowest the channel gets over that run. Both walls rake at 45 degrees
    the whole way, so the void and roof probes sit on the middle of the roof
    flat, which is the narrow end, and the web probe sits mid-web at the mouth,
    which is the thin end of the web on the other side of that same wall. Both
    are derived from the built radii rather than nominal ones, and the web probe
    is narrower than the shared PROBE_D (WEB_PROBE_D) because 0.4 of web has no
    room for it.
    """
    problems = _ring_stack_sane()
    if problems:
        return problems
    wx, wy = board.wheel_center()
    r_void = (case.led_ring_roof_inner_r() + case.led_ring_roof_outer_r()) / 2
    r_web = case.WHEEL_OPENING_R + case.led_ring_web_left() / 2
    z0, z1 = case.CAVITY_FRONT + 0.05, case.LED_RING_TOP - 0.05
    problems = []
    for i in range(LED_RING_SAMPLES):
        a = 2 * math.pi * i / LED_RING_SAMPLES
        deg = round(math.degrees(a))
        void = Pos(wx + r_void * math.cos(a), wy + r_void * math.sin(a), (z0 + z1) / 2) * Cylinder(
            radius=PROBE_D / 2, height=z1 - z0
        )
        if _volume(front.intersect(void)) > TOLERANCE:
            problems.append(f"channel blocked at {deg} degrees")

        web = Pos(wx + r_web * math.cos(a), wy + r_web * math.sin(a), (z0 + z1) / 2) * Cylinder(
            radius=WEB_PROBE_D / 2, height=z1 - z0
        )
        if _fill_fraction(front, web) < 0.99:
            problems.append(f"web to the wheel opening open at {deg} degrees")

        rx, ry = wx + r_void * math.cos(a), wy + r_void * math.sin(a)
        floor = case.face_floor_at(rx, ry)
        roof = Pos(rx, ry, (case.LED_RING_TOP + floor) / 2) * Cylinder(
            radius=PROBE_D / 2, height=floor - case.LED_RING_TOP - 0.04
        )
        if _fill_fraction(front, roof) < 0.99:
            problems.append(f"roof open over the channel at {deg} degrees")
    return problems


WHEEL_SEAT_SAMPLES = 5
"""Heights sampled between CAVITY_FRONT and the wheel's own top for
wheel_seat_clearance: enough to span the opening's whole run rather than
resampling one or two points every run."""


def wheel_seat_clearance(front):
    """The shell's own wheel opening clears everything of the wheel that
    actually reaches the ceiling: the housing and knob,
    board.wheel_profile()'s main_od and top, by at least
    WHEEL_OPENING_CLEARANCE at every height from the ceiling underside up to
    the knob's own peak. That is the opening's own gap; WHEEL_CLEARANCE is the
    pad's, against the lip, and this pass has nothing to do with it. The
    opening is built to exactly that radius now, flush to the wheel, so this
    is the pass that catches anything eating into it.

    This is the real guard behind what used to be a claim that the shell's
    hole had to be sized to the lip so it could pass through on assembly.
    It does not: the board is lowered into an already-closed front shell,
    so the lip stops well short of the ceiling and never transits it. That
    fact is checked first, arithmetic, since it is what excuses the lip
    from the rest of this check; the opening itself is then measured by
    _opening_radius on the built shell at several heights, not trusted from
    WHEEL_OPENING_R, because this exact feature was silently erased by
    _wheel_hole while the formulas behind it still looked right on paper.
    """
    problems = []
    profile = board.wheel_profile()

    if profile.lip_z1 + params.WHEEL_CLEARANCE > case.CAVITY_FRONT:
        problems.append(
            f"lip top {profile.lip_z1:.3f} plus WHEEL_CLEARANCE reaches the "
            f"ceiling underside at {case.CAVITY_FRONT:.2f}: the lip is not "
            "clear of it, so the shell's opening has to answer for it too"
        )
        return problems

    wx, wy = board.wheel_center()
    needed = profile.main_od / 2 + params.WHEEL_OPENING_CLEARANCE
    # The face is flush to the knob's top now, so the top sample pulls in by
    # the probe's own height: exactly at the face plane the probe straddles
    # material and air and reads open no matter what the opening does.
    z0, z1 = case.CAVITY_FRONT, profile.top - OPENING_PROBE_H
    # Bounded inside the ring channel's inner wall: past it the material is
    # no longer monotonic along the radius (web, channel void, outer wall),
    # and a bisect that wanders into the void reads the channel's outer wall
    # as the opening, hiding an undersized seat behind a passing number. Off
    # the mouth radius, the smaller of the two: LED_RING_CHAMFER cuts that
    # corner in toward the bore, so the wall radius above it is inside the void
    # at the heights this samples lowest.
    hi = case.led_ring_mouth_inner_r() - OPENING_PROBE_R
    for i in range(WHEEL_SEAT_SAMPLES):
        z = z0 + (z1 - z0) * i / (WHEEL_SEAT_SAMPLES - 1)
        opening = _opening_radius(front, wx, wy, z, hi=hi)
        if opening < needed - OPENING_PROBE_R:
            problems.append(
                f"opening only {opening:.2f} at z={z:.2f}, wants {needed:.2f}"
            )
    return problems


def rotation_clearance(front, pad):
    """Nothing of the pad or the shell may intrude inside the wheel's rotating
    envelope: LIP_CLEAR_R at and below the lip's top face, where the widest
    disc has to clear, and WHEEL_OPENING_R above it, where the shell's opening
    closes in flush on the main body. The lip being the widest disc is what
    lets the pad's plain bore answer for the main body too, so that fact is
    checked first, arithmetic, rather than assumed.
    """
    hits = []
    if case.WHEEL_LIP_OD < case.WHEEL_MAIN_OD:
        hits.append(
            f"lip {case.WHEEL_LIP_OD:.2f} is narrower than the main body "
            f"{case.WHEEL_MAIN_OD:.2f}: the pad's bore is sized to the wrong disc"
        )
    wx, wy = board.wheel_center()
    regions = [
        ("at and below the lip", case.WHEEL_LIP_Z0, case.WHEEL_LIP_Z1, case.LIP_CLEAR_R),
        ("above the lip", case.WHEEL_LIP_Z1, case.WHEEL_TOP + 1, case.WHEEL_OPENING_R),
    ]
    for label, z0, z1, radius in regions:
        probe = Pos(wx, wy, (z0 + z1) / 2) * Cylinder(radius=radius - 0.05, height=z1 - z0)
        for name, shell in (("pad", pad), ("front shell", front)):
            volume = _volume(shell.intersect(probe))
            if volume > TOLERANCE:
                hits.append(
                    f"{name} intrudes {volume:.2f} mm3 inside the wheel's clearance {label}"
                )
    return hits
