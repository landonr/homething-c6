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

That roof came out at 0.86 at the east and west sides, under the minimum wall
PCBWay publishes for SLS, and nothing in the stack reached it. So on the
recessed front the roof is not shell at all. led_ring_window() cuts it away,
and with it the web in to the bore, and led_ring_insert() is the part that
fills both. The shell then keeps one opening from the bore out to the roof
flat, with no thin sheet anywhere, and the lit band runs to the knob. The FDM
front keeps its own roof and web, which are thick enough.

The one-piece front is the recessed front with the insert fused in, for a clear
print. It keeps the ring as shell, fuses the six lobes, and closes the fit over
each lobe with led_ring_lobe_fills().
"""

import functools
import math

from build123d import (
    Axis,
    Box,
    BuildLine,
    BuildSketch,
    Circle,
    Face,
    Locations,
    Plane,
    Polyline,
    Pos,
    Rectangle,
    Rot,
    Wire,
    loft,
    make_face,
    revolve,
)

import board
import cache
import params

from .shape import _cut, _face_reach, _fuse, _hole, _isect, _offset_face, _slab
from .stack import (
    BOARD_TOP,
    CAVITY_FRONT,
    FDM_FACE,
    LIP_CLEAR_R,
    MERGE,
    PAD_SKIRT_BOTTOM,
    PAD_WEB_TOP,
    SHELL_FRONT,
    SKIRT_BOTTOM,
    STIFFENED_WALL,
    WHEEL_OPENING_R,
)

LED_RING_TOP = SHELL_FRONT - params.LED_RING_ROOF
"""Crown of the recessed front's channel arch, on the crown line. The arch is
lower everywhere off the crown line: led_ring_ceiling_at() gives it at each x.
The arch sets where the outer rake ends, see led_ring_flat_outer_r(). The
ceiling rises off the arch under the face: led_ring_ceiling_under() gives it.
The FDM channel depth comes from this value."""

LED_RING_FOOT = CAVITY_FRONT + params.WHEEL_LIP_RELIEF
"""The plane the channel's inner wall stands on.

wheel_lip_relief() lifts the ceiling off the ENC1 lip out to
led_ring_inner_r(), so the inner wall's foot is this high rather than
CAVITY_FRONT. The mouth, the rake and the outer wall still start at
CAVITY_FRONT, because the relief does not reach them.

Where the channel is shallow, at the east and west sides, this leaves less
height for the inner bevel. led_ring_bevel() shortens the leg there, the same
way it already did against CAVITY_FRONT."""


def led_ring_top(fdm=False):
    """Height the FDM front's flat channel ceiling sits at, and the reference
    depth it is a fraction of.

    The recessed front has no channel ceiling of its own, so its value here is
    a reference and not a surface: LED_RING_TOP, which LED_RING_ROOF sets under
    SHELL_FRONT. The FDM front keeps a real channel and takes
    FDM_LED_RING_DEPTH_RATIO of that depth over CAVITY_FRONT, because its own
    face sits lower and a full-depth channel would thin its roof.
    """
    if not fdm:
        return LED_RING_TOP
    return CAVITY_FRONT + params.FDM_LED_RING_DEPTH_RATIO * (
        LED_RING_TOP - CAVITY_FRONT
    )


def _plan_box(x0, y0, x1, y1):
    with BuildSketch() as sketch:
        with Locations(((x0 + x1) / 2, (y0 + y1) / 2)):
            Rectangle(x1 - x0, y1 - y0)
    return sketch.sketch.faces()[0]


@functools.cache
def pad_keepouts():
    """[Face] what the pad's lobes stay out of round the wheel, in plan: the
    lip's own rotating clearance, each LED body grown by PAD_LED_CLEARANCE, and
    each ring-insert lobe grown by PAD_SKIRT_CLEARANCE.

    A ring lobe counts only where it stands between the skirt bottom and the
    web top, because its flare above the ceiling stands in the shell and not in
    the cavity. All of them come off the placements, so a moved LED moves its
    keep-out. pad_lobe_face() notches each lobe round these, so the pad still
    covers the cap flanges everywhere else."""
    wx, wy = board.wheel_center()
    with BuildSketch() as lip:
        with Locations((wx, wy)):
            Circle(LIP_CLEAR_R)
    out = [lip.sketch.faces()[0]]
    parts = board.components()
    for ref in board.refs("D")[1:]:
        x, y, rot = parts[ref][:3]
        a = math.radians(rot)
        half = (
            params.LED_BODY / 2 * (abs(math.cos(a)) + abs(math.sin(a)))
            + params.PAD_LED_CLEARANCE
        )
        out.append(_plan_box(x - half, y - half, x + half, y + half))
    grow = params.PAD_SKIRT_CLEARANCE
    z0, z1 = PAD_SKIRT_BOTTOM - grow, PAD_WEB_TOP + grow
    slab = Pos(0, 0, (z0 + z1) / 2) * Box(1000, 1000, z1 - z0)
    for lobe in led_ring_lobes():
        section = lobe & slab
        if not section.solids():
            continue
        box = section.bounding_box()
        out.append(
            _plan_box(box.min.X - grow, box.min.Y - grow, box.max.X + grow, box.max.Y + grow)
        )
    return out


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
    """Width of the band between the bore and the channel's inner wall.

    It is the FDM front's web, shell on that front from the ceiling to the
    face. The recessed front has no web: the ring runs from the bore outward in
    one piece, and the light reaches the knob across it."""
    return led_ring_inner_r() - WHEEL_OPENING_R


@functools.cache
def led_ring_face_r():
    """Radius of the ring: one circle on every bearing.

    This is the opening in the shell face. The insert is a smaller circle
    inside it, and the radial gap lets the insert pass the cavity wall.

    RING_LIFT_CLEAR inside that wall where the wall comes in closest, which is
    near the X axis. Everywhere else the wall stands further out and the circle
    clears it by more.

    The ring used to run out to led_ring_mouth_outer_r(), 1.85 further, under a
    shell roof that came back at 0.86 against an SLS minimum of 1.00. Near the
    X axis the cavity wall chorded both the channel and the insert flat. Pulling
    the ring inside the wall answers both at once: no shell covers the ring, so
    no sheet over it can be thin, and no chord cuts the circle. What the roof
    used to do, carrying each LED's light up to the face, the insert does, and
    led_ring_lobes() is how the light gets into it."""
    return (
        min(led_ring_clip_reach(angle) for angle in _ring_angles())
        - params.RING_LIFT_CLEAR
    )


def led_ring_insert_outer_r():
    """Radius of the insert at its joint with the front shell."""
    return led_ring_face_r() - params.RING_INSERT_FACE_FIT


def led_ring_flange_outer_r():
    return led_ring_face_r() + params.RING_FLANGE_OVERLAP


def led_ring_flange_z():
    bottom = CAVITY_FRONT - params.RING_FLANGE_DROP
    return bottom, bottom + params.RING_FLANGE_T


def led_ring_flange():
    """The annular flange below the visible seam, with overlap into the band."""
    x, y = board.wheel_center()
    bottom, top = led_ring_flange_z()
    root = LIP_CLEAR_R
    return _cut(
        _hole(x, y, 2 * led_ring_flange_outer_r(), bottom, top),
        _hole(x, y, 2 * root, bottom - MERGE, top + MERGE),
    )


def led_ring_flange_relief():
    """Clear the flange along its full insertion path from inside the shell."""
    x, y = board.wheel_center()
    _, top = led_ring_flange_z()
    clearance = params.PCBWAY_ASSEMBLY_CLEARANCE
    return _hole(
        x, y, 2 * (led_ring_flange_outer_r() + clearance),
        SKIRT_BOTTOM - MERGE, top + clearance,
    )


def led_ring_lobe_refs():
    """The LEDs that get a lobe: all six status LEDs."""
    return board.refs("D")[1:]


def _lobe_at(ref):
    """(bearing in radians from +X, radius from the wheel axis) of `ref`."""
    wx, wy = board.wheel_center()
    x, y = board.components()[ref][:2]
    return math.atan2(y - wy, x - wx) % (2 * math.pi), math.hypot(x - wx, y - wy)


def led_ring_lobe_bearing(ref):
    """Bearing of `ref`'s lobe, in radians from +X."""
    return _lobe_at(ref)[0]


def led_ring_lobe_rim_z():
    """Height of every dome's rim, RING_LOBE_WRAP under the LEDs' top face.

    The lowest the insert reaches. It is under the LED top on purpose: that is
    what makes each lobe wrap its LED rather than sit over it."""
    return BOARD_TOP + params.LED_HEIGHT - params.RING_LOBE_WRAP


def led_ring_lobe_blend_r(ref):
    """Radius where `ref`'s dome runs back into the ring's own underside,
    RING_LOBE_SIDE inside that LED's body edge.

    The dome has no slope at this end, so the two surfaces meet with no edge
    between them and the lobe has no feather there."""
    _, r = _lobe_at(ref)
    return r - params.LED_BODY / 2 - params.RING_LOBE_SIDE


def _dome_z(rim_r, blend_r, r):
    """Height at radius `r` of a dome rising from its rim to the cavity ceiling.

    RING_LOBE_STRAIGHT mixes a straight cone with a parabola that meets the
    ring's underside flat. The mix is what keeps a full RING_LOBE_WALL between
    the dome and the 45 degree flare over it: the flare is a plane at 45, so
    the material between the two is the vertical gap times cos(45), and the
    parabola on its own is highest in the middle, which is where the flare
    sits.

    Both ends are fixed whatever the mix. The rim sits under the LED's top
    face, so the surface has to climb over that LED's outer corner on its way
    in, and led_ring_lobe_rim_r() is what sets the rim radius that leaves
    RING_LOBE_GAP there."""
    w = params.RING_LOBE_STRAIGHT
    u = (rim_r - r) / (rim_r - blend_r)
    rim_z = led_ring_lobe_rim_z()
    return rim_z + (CAVITY_FRONT - rim_z) * (w * u + (1 - w) * u * (2 - u))


@functools.cache
def led_ring_lobe_rim_r(ref):
    """Radius of the outer rim of `ref`'s dome.

    Solved, not set. The rim is RING_LOBE_WRAP under the LED's top face, so
    where the rim sits decides how much air the dome leaves over that LED's
    outer top corner. A rim too near the package grazes it. One too far out
    drags the whole lobe outward and buys nothing. This is the radius that
    leaves RING_LOBE_GAP over the corner.

    The dome's height over any fixed radius rises with the rim radius, so a
    bisection finds it."""
    _, led_r = _lobe_at(ref)
    led_out = led_r + params.LED_BODY / 2
    blend = led_ring_lobe_blend_r(ref)
    want = BOARD_TOP + params.LED_HEIGHT + params.RING_LOBE_GAP
    lo, hi = led_out, led_out + 4.0
    if _dome_z(hi, blend, led_out) < want:
        raise ValueError(
            f"the dome over {ref} cannot clear its own LED: a rim 4.00 past the "
            f"package still leaves only "
            f"{_dome_z(hi, blend, led_out) - BOARD_TOP - params.LED_HEIGHT:.2f} "
            f"over its outer corner, against RING_LOBE_GAP "
            f"{params.RING_LOBE_GAP:.2f}. RING_LOBE_WRAP "
            f"{params.RING_LOBE_WRAP:.2f} is too deep a wrap for a package this "
            f"wide"
        )
    for _ in range(60):
        mid = (lo + hi) / 2
        if _dome_z(mid, blend, led_out) < want:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def led_ring_lobe_dome_z(ref, r):
    """Height of `ref`'s dome at radius `r`, between its rim and its blend."""
    return _dome_z(led_ring_lobe_rim_r(ref), led_ring_lobe_blend_r(ref), r)


def led_ring_lobe_half(ref):
    """Half the arc `ref`'s lobe covers, in radians: RING_LOBE_SIDE past that
    LED's own corners, the same clearance the dome keeps beside it radially."""
    _, r = _lobe_at(ref)
    return math.asin((params.LED_BODY / 2 + params.RING_LOBE_SIDE) / r)


def led_ring_lobe_pocket_half(ref):
    """Half angle that leaves the specified gap normal to each pocket side."""
    return led_ring_lobe_half(ref) + math.asin(
        params.RING_LOBE_FIT / led_ring_insert_outer_r()
    )


LOBE_FACE_SAMPLES = 16
"""Bearings each lobe's land is measured at, across its own arc. The face falls
along the arc as well as across it, and the land is the insert's whole
retention, so it is taken at the lobe's worst bearing and not at its middle."""


def led_ring_lobe_land_z(ref):
    """Height the shell's pocket for `ref` starts its 45 degree lead-in at.

    LED_RING_FACE_ROOF under the lowest the built face gets over that lobe's
    arc, so the land over the pocket is never under the minimum wall. It is
    thinnest right where the 45 starts, against the ring's circle, and thickens
    outward, because the face falls away more slowly than one in one."""
    from .keypad import face_floor_at

    wx, wy = board.wheel_center()
    angle, _ = _lobe_at(ref)
    half, r = led_ring_lobe_pocket_half(ref), led_ring_face_r()
    bearings = [
        angle - half + 2 * half * i / LOBE_FACE_SAMPLES
        for i in range(LOBE_FACE_SAMPLES + 1)
    ]
    return (
        min(
            face_floor_at(wx + r * math.cos(a), wy + r * math.sin(a))
            for a in bearings
        )
        - params.LED_RING_FACE_ROOF
    )


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
"""Bearings the ring insert's band is lofted through, at equal intervals from
+X: 2.5 degrees, or about 0.8 mm of arc at the face circle. The loft is ruled
between them, and the one surface that has to land flush with the shell's is
the top, which follows the dish. Each multiple of 90 degrees is a station, so a
probe on one of those bearings reads one section exactly."""


def _ring_angles():
    """The bearings of the ring insert's stations, in radians from +X."""
    return [2 * math.pi * i / LED_RING_STATIONS for i in range(LED_RING_STATIONS)]


def wheel_lip_relief():
    """The ceiling lifted clear of the ENC1 lip, out to the ring channel's
    inner wall.

    A plain annular lift rather than a step in _ring_section(), because the
    channel's inner wall is only LED_RING_INNER_FOOT_MIN tall at the east and
    west sides. A section step there would invert. As a cut of its own it
    merges with the channel wherever the two meet, and takes the whole wall
    where the wall is shorter than the lift.

    It reaches MERGE below CAVITY_FRONT so it breaks through the ceiling
    rather than ending on it. The annulus holds nothing: the pad's bore is at
    LIP_CLEAR_R, further out, and the lip is the only part under it.
    """
    x, y = board.wheel_center()
    top = CAVITY_FRONT + params.WHEEL_LIP_RELIEF
    tool = _hole(x, y, 2 * led_ring_inner_r(), CAVITY_FRONT - MERGE, top)
    return _isect(tool, _slab(_channel_clip(), CAVITY_FRONT - MERGE - 1, top + 1))


RING_INSERT_TOP_POINTS = 16
"""Points along the ring insert's top face, at equal intervals from the roof
flat's outer end in to where led_ring_bore_round() leaves the dish.

The top is the dish, and the dish is a bowl, so a chord between two points on
it stands proud of it. The insert's top is the one face that has to land flush
with the shell's own, which is why this is denser than
LED_RING_CEILING_POINTS: the top spans from the bore now rather than from the
inner bevel, about twice the reach, and the sag goes as the square of the
spacing."""


def _insert_section(angle, *, step_radius=LIP_CLEAR_R):
    """[(r, z)] of the ring insert's band on the bearing `angle`.

    The ring without its lobes: a plain band from the wheel bore out to
    led_ring_face_r(), under the dish, standing on the cavity ceiling. Its one
    plumb side is the circle that shows at the face, so that side takes
    RING_INSERT_FACE_FIT. The top lands flush with the shell's own. The bore
    faces the knob, where the shell's seat used to stand, so it keeps that
    radius and WHEEL_OPENING_CLEARANCE with it, and takes no fit.
    The top meets the bore on led_ring_bore_round(), not on a sharp edge.

    The underside stands at LED_RING_FOOT inside the step and drops to
    CAVITY_FRONT outside it. With the flange, the step clears the analytic
    cylinder at LIP_CLEAR_R. Adhesive holds the insert in place. The feet
    catch it if the adhesive fails, and the lobes retain it at the front.

    Every station returns the same number of points, which the ruled loft
    needs.
    """
    from .keypad import face_floor_at

    wx, wy = board.wheel_center()
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    outer = led_ring_insert_outer_r()
    count = RING_INSERT_TOP_POINTS
    arc = led_ring_bore_round(angle)
    start = arc[0][0]
    radii = [outer - (outer - start) * i / (count - 1) for i in range(count)]
    top = [(r, face_floor_at(wx + r * cos_a, wy + r * sin_a)) for r in radii]
    return [
        (WHEEL_OPENING_R, LED_RING_FOOT),
        (step_radius, LED_RING_FOOT),
        (step_radius, CAVITY_FRONT),
        (outer, CAVITY_FRONT),
        *top,
        *arc[1:],
    ]


RING_BORE_ROUND_POINTS = 12
"""Points along the round on the ring's inner edge, from the dish down to the
bore. A chord between two of them cuts inside the arc by about
RING_BORE_ROUND * (1 - cos(half the step)), which is under 0.002 here."""


def led_ring_bore_round(angle, trim=0.0):
    """[(r, z)] of the round on the ring's inner edge on the bearing `angle`.

    The points run from where the round leaves the dish down to where it meets
    the plumb bore at WHEEL_OPENING_R. The arc has radius RING_BORE_ROUND and
    is tangent to both.

    The dish is not level at the bore. It falls outward on the X axis, where
    the face rolls off, and rises on the crown. So the round takes the dish's
    slope where it leaves it, and the arc's centre stands RING_BORE_ROUND out
    from the bore on every bearing.

    `trim` stops the arc that many radians short of each tangent point.
    _insert_section() ends the insert's top on the whole arc, and
    led_ring_bore_round_cut() cuts the trimmed arc into the one-piece front.
    """
    from .keypad import face_floor_at

    wx, wy = board.wheel_center()
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def dish(r):
        return face_floor_at(wx + r * cos_a, wy + r * sin_a)

    radius = params.RING_BORE_ROUND
    centre_r = WHEEL_OPENING_R + radius
    leave = centre_r
    step = 0.01
    for _ in range(4):
        slope = math.atan((dish(leave + step) - dish(leave - step)) / (2 * step))
        leave = centre_r - radius * math.sin(slope)
    centre_z = dish(leave) - radius * math.cos(slope)
    if centre_z <= LED_RING_FOOT:
        raise ValueError(
            f"RING_BORE_ROUND {radius:.2f} takes the whole bore wall at "
            f"{math.degrees(angle):.0f} degrees: the round meets the bore at "
            f"{centre_z:.2f}, at or under the insert's foot at {LED_RING_FOOT:.2f}"
        )
    first, last = math.pi / 2 + slope + trim, math.pi - trim
    return [
        (
            centre_r + radius * math.cos(first + (last - first) * i / (RING_BORE_ROUND_POINTS - 1)),
            centre_z + radius * math.sin(first + (last - first) * i / (RING_BORE_ROUND_POINTS - 1)),
        )
        for i in range(RING_BORE_ROUND_POINTS)
    ]


BORE_ROUND_CUT_STEP = 0.01
"""How far the one-piece front's round cut stops short of the dish and of the
bore, measured normal to each.

A cut that meets either surface on its tangent line meshes torn. The loft's
chords and the true surface cross many times along that line, so the
tessellator finds slivers there. Stopped this far short, each end of the cut
crosses its surface at an angle. The step it leaves is under any print's
resolution, and it is more than the 0.004 that the bore's chords sag inside
the true bore.

At the bore, the cut runs on down the arc's own tangent and through the bore,
rather than in square from the arc's end. A square end leaves a ledge parallel
to the underside, and checks/fab.py reads that as a sheet and not an edge."""


def _bore_round_cut_section(angle):
    """[(r, z)] of the material the round takes off the one-piece front on the
    bearing `angle`: under the air over the dish, over the trimmed arc, down its
    tangent into the bore, and MERGE into the bore so the cut leaves the solid
    rather than ending on its surface."""
    trim = math.acos(1 - BORE_ROUND_CUT_STEP / params.RING_BORE_ROUND)
    arc = led_ring_bore_round(angle, trim)
    (top_r, top_z), (low_r, low_z) = arc[0], arc[-1]
    over = top_z + 1
    past = WHEEL_OPENING_R - BORE_ROUND_CUT_STEP
    below = low_z - (low_r - past) / math.tan(trim)
    inside = WHEEL_OPENING_R - MERGE
    return [*arc, (past, below), (inside, below), (inside, over), (top_r, over)]


def led_ring_bore_round_cut():
    """The cut that rounds the one-piece front's inner ring edge.

    It is lofted through the same stations as led_ring_insert(), off the same
    led_ring_bore_round() arc, trimmed by BORE_ROUND_CUT_STEP at each end. So
    the one-piece front carries the insert's round to within that step."""
    return _ring_loft(_bore_round_cut_section)


LOBE_DOME_POINTS = 24
"""Points along one dome, from its rim in to where it blends into the ring's
underside. The dome is a parabola and a chord between two points cuts inside
it, so the LED's own outer corner, which the dome clears by RING_LOBE_GAP,
wants them close together."""

LOBE_WEDGE_POINTS = 12
"""Points on the arc of the plan wedge each lobe is cut to. The arc stands a
millimetre outside the lobe's own outer face, so these only have to keep its
chord from reaching in that far."""


def led_ring_lobe_flare(ref):
    """(inner radius, height there, flat top) of `ref`'s lobe's 45 degree flare.

    The vertical offset at the flare gives RING_LOBE_FIT normal to the 45 degree
    pocket roof. The same gap is vertical at the flat ceiling. The inner end
    overlaps the band so the build can fuse the two solids."""
    face = led_ring_face_r()
    inner = led_ring_insert_outer_r() - MERGE
    flare_drop = math.sqrt(2) * params.RING_LOBE_FIT
    return (
        inner,
        led_ring_lobe_land_z(ref) + face - inner - flare_drop,
        CAVITY_FRONT - params.RING_LOBE_FIT,
    )


def led_ring_lobe_outer_r(ref):
    """Radius of `ref`'s lobe's vertical outer face: RING_LOBE_WALL outside the
    dome rim."""
    return led_ring_lobe_rim_r(ref) + params.RING_LOBE_WALL


def led_ring_lobe_lid(ref):
    """[(r, z)] of the top of `ref`'s lobe, from the ring's circle outward.

    The 45 degree flare down to its knee, the flat top, and the
    RING_LOBE_SHOULDER chamfer down to the vertical outer face. The chamfer
    keeps a pressed cap flange off the corner, see RING_LOBE_SHOULDER."""
    inner, top, flat = led_ring_lobe_flare(ref)
    knee = inner + top - flat
    outer = led_ring_lobe_outer_r(ref)
    leg = params.RING_LOBE_SHOULDER
    if leg <= 0:
        return [(inner, top), (knee, flat), (outer, flat)]
    if outer - leg <= knee:
        raise ValueError(
            f"RING_LOBE_SHOULDER {leg:.2f} runs past the knee of {ref}'s flare "
            f"at {knee:.2f}, so the lobe has no flat top left"
        )
    return [(inner, top), (knee, flat), (outer - leg, flat), (outer, flat - leg)]


def _lobe_section(ref):
    """[(r, z)] of `ref`'s lobe, as radius from the wheel axis and height.

    Going round from the ring's own circle: the 45 degree flare down to just
    under the cavity ceiling, the flat top, the RING_LOBE_SHOULDER chamfer, the
    outer face down to the rim, the rim land, and the dome back in and up to
    the ring's underside.

    The flare carries light into the ring and tucks under the shell land.
    The pocket clears the lobe by RING_LOBE_FIT.

    The dome is open on the inner side. A wall there would have to stand
    between the LED's inner edge and the ENC1 lip, and LIP_CLEAR_R leaves 0.20
    of room for one. Nothing is lost by leaving it out: the ring sits directly
    over that half of the package and takes its light.

    The last two points reach MERGE above the cavity ceiling, inside the ring's
    own body, so the fuse has volume to work with rather than two faces lying
    on each other.
    """
    rim, blend = led_ring_lobe_rim_r(ref), led_ring_lobe_blend_r(ref)
    inner, _, _ = led_ring_lobe_flare(ref)
    dome = [
        (r, _dome_z(rim, blend, r))
        for r in (
            rim - (rim - blend) * i / (LOBE_DOME_POINTS - 1)
            for i in range(LOBE_DOME_POINTS)
        )
    ]
    return [
        *led_ring_lobe_lid(ref),
        (led_ring_lobe_outer_r(ref), led_ring_lobe_rim_z()),
        *dome,
        (blend, CAVITY_FRONT + MERGE),
        (inner, CAVITY_FRONT + MERGE),
    ]


def _lobe_pocket_section(ref):
    """[(r, z)] of the pocket the shell opens for `ref`'s lobe.

    A triangle: the 45 degree lead-in from the ring's circle down to the cavity
    ceiling, and the ceiling itself. Below the ceiling the cavity is open
    already, so the tool only has to break through, which is why its floor runs
    a millimetre under.

    This is the whole of what the shell gives up for the lobes. The flare
    crosses the ceiling about 1.3 out from the ring, so the shell loses a wedge
    that size at six places and keeps everything else. The land over it is
    LED_RING_FACE_ROOF where it is thinnest, against the ring's circle, and
    thickens outward."""
    r0, top = led_ring_face_r(), led_ring_lobe_land_z(ref)
    low = CAVITY_FRONT - 1
    return [(r0, top), (r0 + top - low, low), (r0, low)]


LOBE_ROOF_SAMPLES = 201
"""Points the dome is walked at when measuring the roof over it. Dense because
the dome and the flare run nearly parallel where they come closest, so the
minimum is shallow and sits between any two coarse samples."""


def led_ring_lobe_roof(ref):
    """Least material between `ref`'s dome and the insert's own top over it.

    Measured normal to that top and not vertically. The flare over the dome is
    a plane at 45 degrees, so a vertical gap of one millimetre is a wall of
    0.71, and reading it vertically is what passed a 0.88 wall that the fab
    pass then found. checks/fab.py measures by inward rays, which is this
    distance, so this is the reading that has to hold.

    Walked rather than reasoned. The top is the 45 over the flare, the flat
    beyond its knee, and the RING_LOBE_SHOULDER chamfer, and the dome's slope
    changes all the way along, so where the two come closest is neither end
    nor a corner between them. The chamfer comes closest to the dome near the
    rim. The vertical outer face is not read, because RING_LOBE_WALL sets it."""
    rim, blend = led_ring_lobe_rim_r(ref), led_ring_lobe_blend_r(ref)
    lid = led_ring_lobe_lid(ref)
    least = math.inf
    for i in range(LOBE_ROOF_SAMPLES):
        r = rim - (rim - blend) * i / (LOBE_ROOF_SAMPLES - 1)
        point = (r, _dome_z(rim, blend, r))
        for a, b in zip(lid, lid[1:]):
            least = min(least, _point_to_segment(point, a, b))
    return least


def _point_to_segment(p, a, b):
    """Distance from (r, z) `p` to the segment `a` to `b` in the same plane."""
    dr, dz = b[0] - a[0], b[1] - a[1]
    t = ((p[0] - a[0]) * dr + (p[1] - a[1]) * dz) / (dr * dr + dz * dz)
    t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - (a[0] + t * dr), p[1] - (a[1] + t * dz))


def _lobe_solid(ref, section, half):
    """One lobe, or one pocket: `section` revolved about the wheel axis and cut
    to a plan wedge `half` radians either side of `ref`'s own bearing."""
    wx, wy = board.wheel_center()
    angle, _ = _lobe_at(ref)
    points = section(ref)
    with BuildSketch(Plane.XZ) as profile:
        with BuildLine():
            Polyline(*points, close=True)
        make_face()
    body = Pos(wx, wy, 0) * revolve(profile.sketch, Axis.Z)
    reach = led_ring_lobe_rim_r(ref) + params.RING_LOBE_WALL + 1
    plan = [(wx, wy)]
    for i in range(LOBE_WEDGE_POINTS + 1):
        a = angle - half + 2 * half * i / LOBE_WEDGE_POINTS
        plan.append((wx + reach * math.cos(a), wy + reach * math.sin(a)))
    with BuildSketch() as wedge:
        with BuildLine():
            Polyline(*plan, close=True)
        make_face()
    zs = [z for _, z in points]
    return _isect(body, _slab(wedge.sketch.faces()[0], min(zs) - 1, max(zs) + 1))


def led_ring_lobes():
    """The six blisters on the insert's underside, one over each LED.

    The ring stops short of the LEDs now, at led_ring_face_r(), so none of it
    sits over the outer half of a package. Each lobe reaches out and down
    instead: a dome that wraps its LED, a wall outside the dome's rim, and the
    45 degree flare back up into the shell that carries the light in and holds
    the part.

    They are local on purpose. A flare all the way round would reach past the
    cavity wall near the X axis and the insert could not lift past it. See
    led_ring_face_r().
    """
    least = params.RING_LOBE_WALL
    lobes = []
    for ref in led_ring_lobe_refs():
        roof = led_ring_lobe_roof(ref)
        if roof < least - 1e-9:
            raise ValueError(
                f"the dome over {ref} leaves {roof:.2f} of insert above it, "
                f"under RING_LOBE_WALL {least:.2f}: RING_LOBE_WRAP "
                f"{params.RING_LOBE_WRAP:.2f} or RING_LOBE_GAP "
                f"{params.RING_LOBE_GAP:.2f} has taken the dome too high, or "
                f"RING_LOBE_SHOULDER {params.RING_LOBE_SHOULDER:.2f} has cut "
                f"too far in"
            )
        lobes.append(_lobe_solid(ref, _lobe_section, led_ring_lobe_half(ref)))
    return lobes


def led_ring_lobe_pockets():
    """The six pockets the shell opens for the lobes.

    Each pocket gives the lobe RING_LOBE_FIT across each side face."""
    return [
        _lobe_solid(
            ref,
            _lobe_pocket_section,
            led_ring_lobe_pocket_half(ref),
        )
        for ref in led_ring_lobe_refs()
    ]


def _lobe_fill_section(ref):
    """[(r, z)] of the fill that closes the fit over `ref`'s lobe on the
    one-piece front.

    The insert's lobe stops RING_LOBE_FIT under the cavity ceiling. The
    one-piece front fills this gap to join the lobe to the shell.

    The fill starts RING_LOBE_FIT under the lobe's flat top, inside the lobe,
    and stops MERGE over the ceiling, inside the shell. So each of its joints
    overlaps material and does not only touch it.

    Its outer side continues the RING_LOBE_SHOULDER chamfer up to the ceiling.
    The chamfer stays one plane, so a pressed SW6 flange meets the same surface
    as on the two-part build.

    Its inner end stands MERGE inboard of the point where the flare crosses its
    top. So the top inner corner is inside the flare and not on its surface.
    """
    _, _, flat = led_ring_lobe_flare(ref)
    knee = led_ring_lobe_lid(ref)[1][0]
    outer = led_ring_lobe_outer_r(ref)
    leg = params.RING_LOBE_SHOULDER
    top = CAVITY_FRONT + MERGE
    dip = min(params.RING_LOBE_FIT, leg) if leg > 0 else params.RING_LOBE_FIT
    low = flat - dip
    start = knee - (top - flat) - MERGE
    dome = led_ring_lobe_dome_z(ref, start)
    if dome >= low:
        raise ValueError(
            f"the fill over {ref}'s lobe starts at r {start:.2f}, where the "
            f"dome stands at {dome:.2f}, over the fill's bottom at {low:.2f}: "
            f"the fill would hang below the lobe"
        )
    if leg <= 0:
        return [(start, low), (outer, low), (outer, top), (start, top)]
    corner = outer - leg
    return [
        (start, low),
        (corner + dip, low),
        (corner - (top - flat), top),
        (start, top),
    ]


def led_ring_lobe_fills():
    """The six fills that close the fit over the lobes on the one-piece front.

    front_shell(one_piece=True) fuses them before its key cuts. So a
    counterbore that reaches over a lobe stays open, and the gap under it stays
    the gap a cap needs."""
    return [
        _lobe_solid(ref, _lobe_fill_section, led_ring_lobe_half(ref))
        for ref in led_ring_lobe_refs()
    ]


def _ring_loft(section):
    """Close a ruled loft through `section` at every station.

    Nothing clips it. The ring stands inside the cavity wall on every bearing
    now, so there is no chord to cut and the loft is the whole band. The cavity
    wall used to cut both the channel and the insert flat near the X axis, and
    that flat is what stopped the part going in."""
    wx, wy = board.wheel_center()
    faces, top = [], -math.inf
    for angle in _ring_angles():
        points = section(angle)
        for i, ((r0, z0), (r1, z1)) in enumerate(zip(points, points[1:] + points[:1])):
            if math.hypot(r1 - r0, z1 - z0) < 1e-6:
                raise ValueError(
                    f"the LED ring section repeats point {i} at "
                    f"{math.degrees(angle):.0f} degrees, r {r0:.3f} z {z0:.3f}"
                )
        top = max(top, *(z for _, z in points))
        faces.append(
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
    solid = loft([*faces, faces[0]], ruled=True)
    if len(solid.solids()) != 1 or not solid.is_valid:
        raise ValueError("the LED ring loft did not close into one solid")
    return solid


def led_ring_foot_angles():
    """Bearings of the insert's feet, midway between neighbouring LEDs.

    Derived off the placements rather than named, so moving an LED moves the
    feet with it. The six LEDs leave six gaps: four short ones and two wide
    ones on the X axis, and every gap gets a foot at its middle, which is as
    far from the light as that gap allows.

    The two on the X axis are the weaker pair. The board ends level with the
    ring there, so they overhang its edge and bear on less of it than the other
    four. They are redundancy rather than the main support.
    """
    wx, wy = board.wheel_center()
    parts = board.components()
    bearings = sorted(
        math.atan2(parts[ref][1] - wy, parts[ref][0] - wx) % (2 * math.pi)
        for ref in board.refs("D")[1:]
    )
    return tuple(
        (first + ((bearings[(i + 1) % len(bearings)] - first) % (2 * math.pi)) / 2)
        % (2 * math.pi)
        for i, first in enumerate(bearings)
    )


FOOT_CHORD_INSET = 0.001
"""How far inside the band's facets the outer arc of each foot stands.

The band is a ruled loft through LED_RING_STATIONS sections, so its outer face
is a polygon with its corners on led_ring_face_r(). An arc on that circle
stands past the middle of each facet, and the fuse leaves a sliver face there.
So the arc stands this far inside the facets' own inner radius."""


def led_ring_feet():
    """Feet under the insert that catch it if its bond fails.

    Each lobe tucks under a land of shell, so the part cannot pass forward
    through the face. But nothing stands under it, so it can drop onto the ENC1
    flange. Adhesive holds it flush, and these feet stop it if the bond fails.

    They stop RING_FOOT_GAP above the board and do not rest on it. A foot that
    touches the board must answer for the board's float and the SLS tolerance
    on both parts. If that stack goes the wrong way, the ring stands proud of
    the face.

    Each foot is a sector of the band, concentric with the wheel. Its outer
    face is an arc just inside the band's facets, see FOOT_CHORD_INSET, so it
    follows the band's outline and nothing stands past it. The feet were boxes
    before, and the two corners of each flat outer face stood past the band.
    RING_FOOT_W is the width at the mid radius.

    The inner face is an arc at LIP_CLEAR_R and not at the band's own inner
    edge, which stands further in. The band is above the ENC1 lip and clears it
    on height. A foot passes the lip, so it answers to the rotating envelope.

    They go MERGE into the insert's underside and do not only touch it, so the
    fuse has volume to work with.
    """
    wx, wy = board.wheel_center()
    inner = LIP_CLEAR_R
    outer = (
        led_ring_insert_outer_r() * math.cos(math.pi / LED_RING_STATIONS)
        - FOOT_CHORD_INSET
    )
    low = BOARD_TOP + params.RING_FOOT_GAP
    high = CAVITY_FRONT + MERGE
    least = params.FAB_MIN_WALL[params.FAB_PROCESS]
    if outer - inner < least:
        raise ValueError(
            f"the ring insert's feet are only {outer - inner:.2f} wide, under "
            f"the {least:.2f} minimum wall: the band runs {inner:.2f} to "
            f"{outer:.2f}, so RING_LIFT_CLEAR {params.RING_LIFT_CLEAR:.2f} has "
            f"pulled led_ring_face_r() in too near LIP_CLEAR_R"
        )
    half = params.RING_FOOT_W / 2 / ((inner + outer) / 2)
    with BuildSketch(Plane.XZ) as profile:
        with BuildLine():
            Polyline(
                (inner, low), (outer, low), (outer, high), (inner, high), close=True
            )
        make_face()
    foot = revolve(profile.sketch, Axis.Z, revolution_arc=math.degrees(2 * half))
    return [
        Pos(wx, wy, 0) * Rot(0, 0, math.degrees(angle - half)) * foot
        for angle in led_ring_foot_angles()
    ]


@cache.solid
def led_ring_insert(feet=True, flange=True):
    """The translucent ring that fills the void the shell leaves round the
    wheel.

    It is a light guide rather than a window. Six lobes reach down over the six
    LEDs and feed the band, and the band carries that light round to the east
    and west, where no LED sits and the face would otherwise read as six dots.

    It goes in from inside the shell and rises straight up. The band and lobes
    clear the cavity wall along that path.

    The lobes are what hold it. Each tucks under LED_RING_FACE_ROOF of shell,
    so the part cannot pass outward through the face at all. It can still drop
    back into the cavity, so it needs adhesive the way the IR window does, and
    led_ring_feet() catches it if the bond lets go. Glue it while the front
    shell lies face down, before the board goes in.

    It also carries the band the shell used to hold between the ring and the
    bore, so the lit face runs to the knob with no shell sheet anywhere in it.

    Print it in UTR-8100 by SLA, with the translucent finish. The Somos
    Taurus shell is opaque, so this part is the only path the light has to
    the face. A polished clear part shows six bright points and no band,
    because clear resin does not scatter light.

    The flange blocks the sightline through the face seam. The feet and flange
    can be omitted for comparison with the one-piece front.
    """
    step_radius = LIP_CLEAR_R
    if flange:
        step_radius += params.RING_FLANGE_LOFT_CLEARANCE
    return _fuse(
        _ring_loft(functools.partial(_insert_section, step_radius=step_radius)),
        *led_ring_lobes(),
        *(led_ring_feet() if feet else []),
        *([led_ring_flange()] if flange else []),
    )


def led_ring_channel(fdm=False):
    """The void the LED ring lives in, as the cut. The two fronts take very
    different shapes.

    The recessed front has no channel at all any more. Its cut is one plain
    bore at led_ring_face_r(), from under the cavity ceiling clear through the
    face, with a pocket at each of the six LEDs for that lobe's 45 degree
    flare. So the shell keeps no roof, no inner wall and no web over the ring,
    and led_ring_insert() is the whole of what the light passes through. That
    is the point: the roof read 0.86 at the east and west sides, under the SLS
    minimum, and nothing in the stack reached it.

    What is left of the shell there is the land over each pocket, which is
    LED_RING_FACE_ROOF at its thinnest, and that land is also the insert's
    retention.

    The FDM front keeps the old channel, because its own face sits lower and
    its roof and web are thick enough to print. It is one section revolved: an
    inner wall at led_ring_inner_r() under a 45 degree bevel, a flat ceiling at
    led_ring_top(True), and an outer wall that rakes in at 45 degrees from the
    mouth. The mouth is the flared end because that is where the light enters,
    off LEDs firing up out of the cavity.

    The overrun below the cavity ceiling holds the mouth radii, so the cut
    breaks through into the cavity and leaves that ceiling a clean edge rather
    than a feather.
    """
    x, y = board.wheel_center()
    if not fdm:
        # No clip. The circle stands inside the cavity wall on every bearing,
        # which is the whole job of led_ring_face_r(), and the pockets sit
        # above the cavity ceiling where there is no wall to answer to.
        return _fuse(
            _hole(x, y, 2 * led_ring_face_r(), CAVITY_FRONT - 1, SHELL_FRONT + 1),
            *led_ring_lobe_pockets(),
        )
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
