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
annular channel circling the wheel opening, open to the cavity below, under a
roof of translucent shell. On the recessed front the ceiling is
LED_RING_FACE_ROOF under the built face, or the arch where the arch is higher.
The arch is lower all the way round, so the roof is even. The inner wall is
upright below a 45 degree bevel at the ceiling, so the web to the wheel's bore
is at least LED_RING_WALL. The bevel shortens where the channel is shallow.
The outer wall is plumb at the mouth, then rakes in at 45 degrees up to the
ceiling. Where the ceiling is above the arch, the rake starts that much higher,
so the roof flat keeps its width. The light enters across the flare of the
rake. The six LEDs fire up into the channel, and the channel carries their
light around the wheel, so the face shows a ring and not six dots.
"""

import functools
import math

from build123d import (
    Axis,
    BuildLine,
    BuildSketch,
    Face,
    GeomType,
    Plane,
    Polyline,
    Pos,
    Wire,
    loft,
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
    STIFFENED_WALL,
    WHEEL_OPENING_R,
    arch_z,
)

LED_RING_TOP = SHELL_FRONT - params.LED_RING_ROOF
"""Crown of the recessed front's channel arch, on the crown line. The arch is
lower everywhere off the crown line: led_ring_ceiling_at() gives it at each x.
The arch sets where the outer rake ends, see led_ring_flat_outer_r(). The
ceiling rises off the arch under the face: led_ring_ceiling_under() gives it.
The FDM channel depth comes from this value."""


def led_ring_ceiling_at(x):
    """The recessed channel's arch at x: LED_RING_TOP on the crown line, on a
    circular arc that falls LED_RING_SAG to each side wall.

    The arch is the lowest that the ceiling can be, so the channel is never
    shallower than the arch makes it. LED_RING_SAG keeps it below the face less
    LED_RING_FACE_ROOF on the roof flat, so the ceiling follows the face all
    the way round. If the arch rises above that at the east and west sides of
    the knob, it holds the ceiling up and the roof gets thinner, and
    keypad.ring_roof_left() counts that."""
    return arch_z(x, LED_RING_TOP, params.LED_RING_SAG)


def led_ring_ceiling_under(x, y):
    """Ceiling of the recessed front's channel at the plan point (x, y) on the
    roof flat: the arch, or LED_RING_FACE_ROOF under the built face where that
    is higher.

    The ceiling only rises off the arch. As a result, the roof is never thicker
    than LED_RING_FACE_ROOF. It is thinner only where the face falls to the
    arch, and LED_RING_SAG keeps the arch low enough that it does not."""
    # keypad.py imports this module, so the import must stay local.
    from .keypad import face_floor_at

    face = face_floor_at(x, y) - params.LED_RING_FACE_ROOF
    return max(led_ring_ceiling_at(x), face)


def led_ring_flat_outer_r(angle):
    """Outer end of the recessed channel's roof flat on the bearing `angle`, in
    radians from +X. A 45 degree line up from the mouth at CAVITY_FRONT meets
    the arch at this radius. The outer rake ends on the ceiling at this radius.
    Where the ceiling is above the arch, the rake starts higher at the mouth, so
    a raised ceiling does not make the flat narrower. See led_ring_rake_foot().

    The line falls 1 in 1 outward and the arch falls more slowly, so they meet
    once between the inner wall and the mouth. A bisection finds that point."""
    wx, _ = board.wheel_center()
    mouth = led_ring_mouth_outer_r()
    lo, hi = led_ring_inner_r(), mouth
    for _ in range(60):
        mid = (lo + hi) / 2
        rake = CAVITY_FRONT + mouth - mid
        if rake > led_ring_ceiling_at(wx + mid * math.cos(angle)):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def led_ring_rake_foot(angle):
    """Height on the bearing `angle`, in radians from +X, where the recessed
    channel's outer wall stops its plumb part at the mouth and starts its 45
    degree rake.

    The rake goes from the mouth up to the ceiling at led_ring_flat_outer_r(),
    so it is as high as it is wide. Where the ceiling there is on the arch, the
    rake starts at CAVITY_FRONT and the outer wall has no plumb part. Where the
    ceiling is above the arch, the rake starts that much higher, and the outer
    wall is plumb at the mouth below it."""
    wx, wy = board.wheel_center()
    flat_out = led_ring_flat_outer_r(angle)
    rake_top = CAVITY_FRONT + led_ring_mouth_outer_r() - flat_out
    ceiling = led_ring_ceiling_under(
        wx + flat_out * math.cos(angle), wy + flat_out * math.sin(angle)
    )
    # The bisection can leave the 45 degree line a rounding error over the arch.
    return CAVITY_FRONT + max(0.0, ceiling - rake_top)


def led_ring_bevel(angle):
    """Leg of the recessed channel's 45 degree inner bevel on the bearing
    `angle`, in radians from +X: how far the bevel steps out from the inner wall
    and down from the ceiling at its top edge.

    It is LED_RING_INNER_CHAMFER where the channel is tall enough. At the east
    and west sides of the knob the channel is shallower, and the bevel shortens
    so that LED_RING_INNER_FOOT_MIN of upright inner wall stays above
    CAVITY_FRONT. The ceiling at the top edge moves with the leg, so a bisection
    finds the leg. Zero means that the channel has no height for a bevel at
    all, and led_ring_channel() stops with an error."""
    wx, wy = board.wheel_center()
    inner = led_ring_inner_r()
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def spare(leg):
        r = inner + leg
        top = led_ring_ceiling_under(wx + r * cos_a, wy + r * sin_a)
        return top - CAVITY_FRONT - params.LED_RING_INNER_FOOT_MIN - leg

    full = params.LED_RING_INNER_CHAMFER
    if spare(full) >= 0:
        return full
    if spare(0.0) <= 0:
        return 0.0
    lo, hi = 0.0, full
    for _ in range(40):
        mid = (lo + hi) / 2
        if spare(mid) >= 0:
            lo = mid
        else:
            hi = mid
    return lo


def led_ring_bevel_edge_r(angle):
    """Radius of the recessed channel's inner bevel top edge on the bearing
    `angle`, in radians from +X. The roof flat starts here. It is
    led_ring_roof_inner_r() where the bevel is full, and nearer the inner wall
    where led_ring_bevel() shortens it."""
    return led_ring_inner_r() + led_ring_bevel(angle)


def led_ring_bevel_top(angle):
    """Height of the recessed channel's ceiling at the top edge of the inner
    bevel, on the bearing `angle`. The bevel goes led_ring_bevel(angle) down
    from this height to the inner wall."""
    wx, wy = board.wheel_center()
    r = led_ring_bevel_edge_r(angle)
    return led_ring_ceiling_under(wx + r * math.cos(angle), wy + r * math.sin(angle))


def led_ring_top(fdm=False):
    """Height of the channel's arch, or its flat ceiling, on the crown line.

    On the recessed front this is the arch's crown, and the outer rake is this
    high above CAVITY_FRONT on the crown line. The ceiling rises above the arch
    under the face, see led_ring_ceiling_under(), and the rake starts that much
    higher at the mouth. The FDM front shortens the
    wall from the cavity side and keeps this height as its flat ceiling, so
    the roof under its lower flat face is thicker.
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
    clearance and led_y_reach() plus PAD_LED_CLEARANCE. The LED term governs
    at the present layout: D6 and D7 sit on the wheel's y axis, so their full
    radial reach counts in y. It is derived off the placements, so moving an
    LED outward widens the band rather than quietly ending up back under
    silicone.

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
    inner wall at either end.

    The wheel sits on the long sides, where skirt_stiffener() carries the wall
    SIDE_SKIRT_THICKEN inboard of the board fit up to the ceiling. At the fit
    itself the channel cut a notch into that wall below the ceiling."""
    return _offset_face(STIFFENED_WALL)


@functools.cache
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
    this radius LED_RING_CHAMFER above the foot of the rake rather than holding
    it."""
    return led_radial_reach()[1] + params.LED_RING_OVER


def led_ring_mouth_outer_r():
    """Channel outer wall at the mouth, its widest. On the recessed front the
    outer wall is plumb at this radius up to led_ring_rake_foot(). What
    _channel_clip() has to answer for, rather than any radius above it."""
    return led_ring_outer_r() + params.LED_RING_CHAMFER


def led_ring_roof_inner_r():
    """Inner edge of the channel roof after the full LED_RING_INNER_CHAMFER.
    This is the FDM front's on every bearing, and the recessed front's wherever
    its bevel is full. led_ring_bevel_edge_r() gives the recessed front's on
    each bearing."""
    return led_ring_inner_r() + params.LED_RING_INNER_CHAMFER


def led_ring_roof_outer_r(fdm=False):
    """Channel outer wall where its rake meets the roof on the crown line. On
    the recessed front this is led_ring_flat_outer_r() at its nearest the
    wheel, because the arch is highest on the crown line."""
    return led_ring_mouth_outer_r() - led_ring_wall_height(fdm)


def led_ring_roof_flat(fdm=False):
    """Width of the flat at the roof between the inner bevel and the outer
    rake, at its narrowest, on the crown line. This is the surface the ring
    glows through; light_path proves it still covers the LEDs."""
    return led_ring_roof_outer_r(fdm) - led_ring_roof_inner_r()


def led_ring_web_left():
    """Minimum web between bore and channel, below the inner top chamfer.
    The bevel widens it toward the roof; led_ring probes the built shell."""
    return led_ring_inner_r() - WHEEL_OPENING_R


def led_ring_wall_height(fdm=False):
    """Height of the outer rake on the crown line, from CAVITY_FRONT up to
    led_ring_top(). Not the cut's own height, which starts a millimetre lower;
    that overrun is inside the cavity, where there is no wall. The rake is at
    45 degrees, so this is also how far the wall travels radially, which closes
    the roof flat to led_ring_roof_flat().

    On the recessed front the rake has this height on the crown line too, but
    the walls are taller where the ceiling rises off the arch. The outer wall is
    plumb at the mouth below the rake, up to led_ring_rake_foot(), and the inner
    wall carries its bevel up to the raised ceiling. Where the ceiling is lower
    than the arch's crown, at the east and west sides, the walls are shorter."""
    return led_ring_top(fdm) - CAVITY_FRONT


LED_RING_STATIONS = 144
"""Bearings that the recessed channel is lofted through, at equal intervals
from +X: 2.5 degrees, or about 0.8 mm of arc on the roof flat. The loft is
ruled between them. Over the roof flat inside the cavity wall, its ceiling then
departs from led_ring_ceiling_under() by less than 0.005. The largest
departures are where the ceiling leaves the arch near the X axis. Each multiple
of 90 degrees is a station, so a probe on one of those bearings reads one
section exactly."""

LED_RING_CEILING_POINTS = 8
"""Points on the ceiling of each section, at equal intervals from the outer
wall to the top of the inner bevel. The ceiling changes slowly along a radius,
so more points change the loft less than more stations do."""


def _ring_angles():
    """The bearings of the recessed channel's stations, in radians from +X."""
    return [2 * math.pi * i / LED_RING_STATIONS for i in range(LED_RING_STATIONS)]


def led_ring_inner_foot():
    """Least upright inner wall that the recessed channel keeps above
    CAVITY_FRONT, below the foot of its inner bevel, over all stations. The
    bevel hangs from the local ceiling and shortens where the channel is
    shallow, so this is LED_RING_INNER_FOOT_MIN at the east and west sides."""
    foot = min(led_ring_bevel_top(a) - led_ring_bevel(a) for a in _ring_angles())
    return foot - CAVITY_FRONT


def _ring_section(angle):
    """[(r, z)] of the recessed channel's section on the bearing `angle`, as
    radius from the wheel axis and height, in order: the overrun's floor, the
    plumb part of the outer wall at the mouth, the 45 degree outer rake, the
    ceiling, the inner bevel and the inner wall. The ceiling ends at
    led_ring_bevel_edge_r(), and the bevel goes led_ring_bevel() down from it.

    The rake goes up from the mouth at led_ring_rake_foot() to the ceiling at
    led_ring_flat_outer_r(). Where the ceiling is above the arch there, the
    rake starts that much higher than CAVITY_FRONT, and the outer wall is plumb
    at the mouth below it. The rake keeps its 45 degrees and its height, so the
    roof flat does not get narrower. Every section has the same number of
    points, which the ruled loft needs."""
    wx, wy = board.wheel_center()
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    inner, mouth = led_ring_inner_r(), led_ring_mouth_outer_r()
    bevel = led_ring_bevel(angle)
    flat_in, flat_out = inner + bevel, led_ring_flat_outer_r(angle)
    count = LED_RING_CEILING_POINTS
    ceiling = []
    for i in range(count):
        r = flat_out - (flat_out - flat_in) * i / (count - 1)
        ceiling.append((r, led_ring_ceiling_under(wx + r * cos_a, wy + r * sin_a)))
    bevel_top = ceiling[-1][1]
    z0 = CAVITY_FRONT - 1
    return [
        (inner, z0),
        (mouth, z0),
        (mouth, led_ring_rake_foot(angle)),
        *ceiling,
        (inner, bevel_top - bevel),
    ]


def _recessed_ring_channel():
    """The recessed front's channel: a ruled loft through _ring_section() at
    every station, closed on itself, clipped by _channel_clip()."""
    wx, wy = board.wheel_center()
    sections, top = [], -math.inf
    for angle in _ring_angles():
        points = _ring_section(angle)
        top = max(top, *(z for _, z in points))
        sections.append(
            Face(
                Wire.make_polygon(
                    [
                        (wx + r * math.cos(angle), wy + r * math.sin(angle), z)
                        for r, z in points
                    ],
                    close=True,
                )
            )
        )
    # The same face first and last makes the loft close on itself, with no end
    # caps to glue.
    channel = loft([*sections, sections[0]], ruled=True)
    caps = [
        f
        for f in channel.faces()
        if f.geom_type == GeomType.PLANE
        and abs(f.normal_at().Y) > 1 - 1e-9
        and abs(f.center().Y - wy) < 1e-6
    ]
    if caps or len(channel.solids()) != 1 or not channel.is_valid:
        raise ValueError("the LED ring channel loft did not close into one solid")
    # The clip's slab reaches past the loft at both ends, so no face of the one
    # lies on a face of the other.
    return _isect(channel, _slab(_channel_clip(), CAVITY_FRONT - 2, top + 1))


def led_ring_channel(fdm=False):
    """The channel itself, as the cut: an annular void from below the ceiling
    underside (open to the cavity, which is where the LED light comes from) up
    to the ceiling, clipped by _channel_clip() where its outer radius would
    otherwise run past the cavity wall.

    On the recessed front the ceiling is led_ring_ceiling_under(): the arch,
    or LED_RING_FACE_ROOF under the built face where that is higher. That
    surface is not a revolution, so the channel is a ruled loft through one
    section at each of LED_RING_STATIONS bearings. The inner wall stands at
    led_ring_inner_r() and bevels out 45 degrees through led_ring_bevel(),
    measured down from the local ceiling. That is the full
    LED_RING_INNER_CHAMFER except at the east and west sides, where the channel
    is shallow and the bevel shortens to keep LED_RING_INNER_FOOT_MIN of
    upright inner wall. The outer
    wall is plumb at the mouth up to led_ring_rake_foot(), then rakes in at 45
    degrees up to the ceiling at led_ring_flat_outer_r(). Where the ceiling is
    above the arch, the rake starts that much higher. As a result, the raised
    ceiling does not make the roof flat narrower. The FDM front's channel stays
    flat at led_ring_top(), revolved as one section.

    The web behind the inner wall is at least LED_RING_WALL everywhere.

    Flaring the outer wall is what the light wants: it enters at the mouth, off
    LEDs firing up out of the cavity, and a wall raked away from them puts more
    of the roof in view of each one. A 45 degree rake is also what a printer can
    close a ceiling over without support.

    The overrun below the ceiling underside holds the mouth radii. It is there
    to break the cut through into the cavity, and carrying the widest width down
    through it is what leaves the cavity ceiling a clean edge rather than a
    feather.
    """
    if not fdm:
        least = min(led_ring_bevel(a) for a in _ring_angles())
        foot = led_ring_inner_foot()
        if least <= 0 or foot < params.LED_RING_INNER_FOOT_MIN - 1e-6:
            raise ValueError(
                f"the recessed LED channel has no room for its inner bevel at "
                f"the inner wall's east and west sides: the bevel is "
                f"{least:.2f} and leaves {foot:.2f} of upright wall, wants "
                f"LED_RING_INNER_FOOT_MIN {params.LED_RING_INNER_FOOT_MIN:.2f}. "
                f"LED_RING_SAG {params.LED_RING_SAG:.2f} and LED_RING_FACE_ROOF "
                f"{params.LED_RING_FACE_ROOF:.2f} put the ceiling too low there"
            )
        return _recessed_ring_channel()
    x, y = board.wheel_center()
    z0, z1 = CAVITY_FRONT - 1, led_ring_top(fdm)
    if params.LED_RING_INNER_CHAMFER >= led_ring_wall_height(fdm):
        raise ValueError("LED_RING_INNER_CHAMFER consumes the LED channel wall")
    inner, mouth_outer = led_ring_inner_r(), led_ring_mouth_outer_r()
    top = z1
    with BuildSketch(Plane.XZ) as section:
        with BuildLine():
            Polyline(
                (inner, z0),
                (mouth_outer, z0),
                (mouth_outer, CAVITY_FRONT),
                (led_ring_roof_outer_r(fdm), top),
                (led_ring_roof_inner_r(), top),
                (inner, z1 - params.LED_RING_INNER_CHAMFER),
                close=True,
            )
        make_face()
    channel = Pos(x, y, 0) * revolve(section.sketch, Axis.Z)
    return _isect(channel, _slab(_channel_clip(), z0, top))


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
    """Keep the FDM bore and cone clear of the channel where their heights meet.

    The printed channel stops below the recessed front's channel. A wide mouth
    above that roof can cross its inner radius in plan without opening the
    channel. At the printed channel's actual top, the cone is widest of all
    heights that can meet it. Keep that radius strictly inside its inner wall;
    coincident edges can tear the exported mesh even when the solid is valid.
    """
    base = FDM_FACE - params.FDM_WHEEL_OPENING_CHAMFER
    overlap_height = max(0, led_ring_top(True) - base)
    spent = params.FDM_WHEEL_OPENING_CLEARANCE + overlap_height
    if spent >= params.LED_RING_WALL:
        raise ValueError(
            f"the FDM wheel mouth reaches {spent:.2f} into the "
            f"{params.LED_RING_WALL:.2f} LED_RING_WALL web at the printed "
            f"channel roof; FDM_WHEEL_OPENING_CHAMFER "
            f"{params.FDM_WHEEL_OPENING_CHAMFER:.2f} cuts into the channel"
        )


def wheel_opening(z0, z1, fdm=False):
    """The shell's wheel opening: one plain bore at WHEEL_OPENING_R, ceiling
    underside to the face, so below the keypad recess's wheel basin the face closes in flush
    to the wheel's fixed bezel with only WHEEL_OPENING_CLEARANCE between
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

    The bore stays inside the web, and _fdm_mouth_budget() holds the cone clear
    of the shorter FDM ring channel where their heights meet.
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
