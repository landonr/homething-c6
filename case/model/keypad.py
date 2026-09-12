"""The keys themselves: how big each one can be, the one continuous concave
recess sunk into the front face around them and around the wheel, and the soft
pad that carries a stem and a plunger under every switch.

The recess is three superellipse basins on a single centreline joined by two
Hermite bridges into one C1 depth field, cut as a single loft along y. Read
recess_spine() and face_depth_at() first: everything else about it, including
every check, is built off those two."""

import functools
import math
from collections import namedtuple

from build123d import (
    Box,
    BuildLine,
    BuildSketch,
    Face,
    Kind,
    Locations,
    Plane,
    Polyline,
    Pos,
    RectangleRounded,
    extrude,
    loft,
    make_face,
)

import board
import cache
import params

from .hardware import mount_points
from .mic import mic_duct_or, mic_port
from .shape import (
    _cut,
    _fuse,
    _hole,
    _profiles,
    _rounded_prism,
    _slab,
    _squircle_points,
)
from .stack import (
    MERGE,
    PAD_WEB_BOTTOM,
    PAD_WEB_TOP,
    SHELL_FRONT,
    STEM_TOP,
    SWITCH_TOP,
    WHEEL_OPENING_R,
)
from .wheel_ring import (
    led_ring_roof_inner_r,
    led_ring_roof_outer_r,
    pad_clear_y,
)


def key_pitch():
    """Closest spacing of any two switches, which is what the keys have to fit in.

    Taken as the minimum rather than an average because the grid is not exact:
    SW4 sits 0.057 off its column and 0.026 off its row, so the tightest pair is
    12.42 where the nominal is 12.446.
    """
    parts = board.components()
    pts = [parts[ref][:2] for ref in board.refs("SW")]
    return min(
        math.dist(a, b) for i, a in enumerate(pts) for b in pts[i + 1 :]
    )


@functools.cache
def key_size(ref=None):
    """Side of the square key footprint at one switch, or the grid's own size
    for None.

    The grid pitch caps it, and a screw boss can cut it further: the collar
    has to stay outside the key hole, or the hole swallows the boss and
    leaves it hanging off the ceiling by nothing. All eleven take the full
    size now: SW1 and SW2 used to sit close enough to a pair of mounting
    holes to bind against this, back when there were four of them, but the
    board has moved to three and neither is close enough to shrink these
    two below the grid pitch any more. The clip stays, mechanical, in case
    a future layout brings a boss back into range.
    """
    limit = key_pitch() - params.KEY_GAP
    if ref is None:
        return limit
    x, y, _, _ = board.components()[ref]
    # Two circles, not one. The hole in the ceiling has to leave the boss its
    # collar, and the keytop has to stay out of the wider hole the pad needs where
    # the boss passes through it. The pad's is the larger and usually binds.
    collar = params.BOSS_OD / 2 + params.BOSS_COLLAR
    through = collar + params.PAD_BOSS_CLEARANCE

    def clears(size):
        for half, r in ((size / 2 + params.KEY_CLEARANCE, collar), (size / 2, through)):
            for hx, hy in mount_points():
                gap = math.hypot(max(abs(x - hx) - half, 0), max(abs(y - hy) - half, 0))
                if gap < r:
                    return False
        return True

    if clears(limit):
        return limit
    lo, hi = 0.0, limit
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if clears(mid) else (lo, mid)
    return lo


def island_refs(name):
    """The switches one keyed recess covers: KEYPAD_ISLAND_2 for "second",
    everything else for "grid". One reader, because the recess's own coverage
    box, the pad lobe under it and every per-key check have to agree on which
    keys belong where."""
    if name == "second":
        return [ref for ref in board.refs("SW") if ref in params.KEYPAD_ISLAND_2]
    return [ref for ref in board.refs("SW") if ref not in params.KEYPAD_ISLAND_2]


def key_recess(ref):
    """Which recess a switch sits in."""
    return "second" if ref in params.KEYPAD_ISLAND_2 else "grid"


def _key_bounds(refs):
    xs, ys = [], []
    parts = board.components()
    for ref in refs:
        x, y = parts[ref][:2]
        half = key_size(ref) / 2
        xs += [x - half, x + half]
        ys += [y - half, y + half]
    return xs, ys


def keypad_coverage():
    """[(name, x0, y0, x1, y1)] the plan footprint each keyed recess has to
    contain: the nine-key grid, and KEYPAD_ISLAND_2 (SW1, SW2) plus the mic
    inlet, each the bounding box of what it covers padded by KEYPAD_MARGIN on
    every side.

    Not the recess itself. keypad_recesses() grows a superellipse around each
    of these, because a superellipse only touches its own bounding box at the
    four edge midpoints and the corner keys sit nowhere near those.
    """
    out = []
    for name in ("grid", "second"):
        xs, ys = _key_bounds(island_refs(name))
        if name == "second":
            # KEYPAD_ISLAND_2's recess also covers the mic inlet, the other
            # aperture up at that end of the board.
            mx, my = mic_port()
            r = mic_duct_or()
            xs += [mx - r, mx + r]
            ys += [my - r, my + r]
        out.append(
            (
                name,
                min(xs) - params.KEYPAD_MARGIN,
                min(ys) - params.KEYPAD_MARGIN,
                max(xs) + params.KEYPAD_MARGIN,
                max(ys) + params.KEYPAD_MARGIN,
            )
        )
    return out


def exterior_x_bounds():
    """(x0, x1) of the case's own exterior side walls, the LAP_OUT profile's
    own extent. What KEYPAD_EDGE_MARGIN is measured from, and what
    EDGE_R_FRONT's fillet is cut from."""
    box = board.board_profile().bounding_box()
    over = params.BOARD_FIT + params.WALL
    return box.min.X - over, box.max.X + over


def exterior_y_bounds():
    """(y0, y1) of the case's own exterior end walls, the same profile the
    other way. The recesses are far clear of both ends, but the cap in
    keypad_recesses() is written for either axis so a layout change cannot
    quietly walk one off the end of the case."""
    box = board.board_profile().bounding_box()
    over = params.BOARD_FIT + params.WALL
    return box.min.Y - over, box.max.Y + over

@functools.cache
def centerline_x():
    """The x every recess is centred on and mirrored about.

    The three coverage centres and the wheel's own centre agree to a few
    hundredths on this board, which is what makes the whole recess a single
    column along y and so what makes one spine and one loft possible at all.
    They are averaged rather than one of them being picked, and check.py holds
    the spread, so a layout that pulled them apart would fail loudly instead of
    quietly shearing a dish sideways.
    """
    xs = [(x0 + x1) / 2 for _, x0, _, x1, _ in keypad_coverage()]
    xs.append(board.wheel_center()[0])
    return sum(xs) / len(xs)


def centerline_spread():
    """How far the furthest of those centres sits from centerline_x()."""
    xs = [(x0 + x1) / 2 for _, x0, _, x1, _ in keypad_coverage()]
    xs.append(board.wheel_center()[0])
    return max(abs(x - centerline_x()) for x in xs)


def _edge_room_x():
    """Half axis in x the exterior wall leaves, once KEYPAD_EDGE_MARGIN is taken
    off. Read at the centerline rather than at each recess's own centre, so
    both keyed dishes cap at the same half axis and the merged outline is
    symmetric about one line."""
    ex0, ex1 = exterior_x_bounds()
    cx = centerline_x()
    return min(cx - ex0, ex1 - cx) - params.KEYPAD_EDGE_MARGIN


def _edge_room_y(cy):
    """The same in y, for a dish centred there. Idle on this board, the recess
    running nowhere near either end wall, but written for either axis so a
    layout change cannot quietly walk one off the end of the case."""
    ey0, ey1 = exterior_y_bounds()
    return min(cy - ey0, ey1 - cy) - params.KEYPAD_EDGE_MARGIN


Recess = namedtuple("Recess", "name cy ax ay depth n")
"""One basin on the spine: where its centre sits along y, its two superellipse
half axes, how deep it is at that centre, and the exponent its own outline is
drawn with. All three share centerline_x()."""


@functools.cache
def keypad_recesses():
    """{name: Recess} for the three dishes the merged front-face recess is
    built from: the grid, the second island, and the wheel, in that order along
    y and disjoint in y.

    Each is a superellipse of exponent KEYPAD_SQUIRCLE_N about its own centre,
    with a depth that is zero on that curve and greatest at the centre. They
    are no longer separate cuts: keypad_necks() bridges them into one recess
    and recess_spine() is the merged field. What survives per dish is the
    outboard half of its rim, its own depth, and its own deepest point.

    The two keyed recesses are sized to *bound* their coverage box rather than
    to be inscribed in it. A superellipse inscribed in a box touches it only at
    the four edge midpoints and passes well inside the corners, which on this
    layout would put the rim straight through the four corner keys' own holes.
    Growing both half axes by 2^(1/n) is what puts the box's corners on the
    curve instead, and at n=4 that is about a fifth.

    Except in x on this board, where that reaches inside KEYPAD_EDGE_MARGIN.
    The x half axis is capped there and the y one is left alone rather than
    both being scaled back together: the cap costs dish beyond the coverage
    box's corners, and taking it out of one axis leaves more of the margin
    around the corner keys themselves than taking it out of both would.

    The wheel's is not sized off a coverage box at all. It has no keys under
    it, so its half axes are stated outright, WHEEL_BASIN_SPREAD past the bore on
    each axis and square, and what the bore does not swallow is the seat ring
    around the knob. WHEEL_RIM_LEDGE used to be that spread and is only the floor
    now: sizing the basin on the clearance minimum is what left the ring as
    narrow as the minimum. It carries its own lower exponent as well
    (WHEEL_SQUIRCLE_N): a basin that is a ring around a round knob wants a round
    outline, where one that is a field of square keys wants a rounded rectangle.

    That sizing rule still delivers WHEEL_RIM_LEDGE at every angle, and it does
    so for the same reason at either exponent. Above n=2 a superellipse's own
    axes are where it comes closest to its centre, so the half axis *is* the
    clearance, and the diagonals only ever stand further out. Below n=2 that
    inverts and the rule would stop holding, which is why check.py measures the
    clearance around the whole curve rather than trusting the arithmetic.
    """
    keyed = params.KEYPAD_SQUIRCLE_N
    grow = 2 ** (1 / keyed)
    room_x = _edge_room_x()
    out = {}
    for name, x0, y0, x1, y1 in keypad_coverage():
        cy = (y0 + y1) / 2
        depth = params.KEYPAD_DISH_DEPTH_2 if name == "second" else params.KEYPAD_DISH_DEPTH
        out[name] = Recess(
            name,
            cy,
            min((x1 - x0) / 2 * grow, room_x),
            min((y1 - y0) / 2 * grow, _edge_room_y(cy)),
            depth,
            keyed,
        )
    _, wy = board.wheel_center()
    half = WHEEL_OPENING_R + params.WHEEL_BASIN_SPREAD
    out["wheel"] = Recess(
        "wheel",
        wy,
        min(half, room_x),
        min(half, _edge_room_y(wy)),
        params.WHEEL_DISH_DEPTH,
        params.WHEEL_SQUIRCLE_N,
    )
    return {name: out[name] for name in sorted(out, key=lambda n: out[n].cy)}


def recess_span():
    """(y0, y1) the merged recess runs between: the outboard rim of the first
    dish to the outboard rim of the last."""
    dishes = list(keypad_recesses().values())
    return dishes[0].cy - dishes[0].ay, dishes[-1].cy + dishes[-1].ay


# The three spine quantities, per dish, on the centerline. Each is a plain
# function of y and each is what the merged field reduces to inside that dish's
# own body.
def _dish_shape(recess, y):
    """The cross-section shape parameter: the superellipse's own |dy/ay|^n.

    Zero on the basin's centre row, one at its rim. With the local exponent it
    is the only thing besides the local depth and the local half width that the
    cross-section depends on, which is what lets the merged field be exact
    inside a basin and still be built from four scalars per station."""
    return min(abs(y - recess.cy) / recess.ay, 1.0) ** recess.n


def _dish_width(recess, y):
    """Half width of the basin's own plan outline at y, so the outline is
    x = centerline_x() +/- this. Exactly the superellipse."""
    return recess.ax * max(0.0, 1.0 - _dish_shape(recess, y)) ** (1 / recess.n)


def _dish_depth(recess, y):
    """Depth on the centerline at y, which is the superellipse's own sag there:
    at dx=0 the exponent drops out and the profile is a plain circular arc in
    |dy/ay|."""
    u = min(abs(y - recess.cy) / recess.ay, 1.0)
    return recess.depth * math.sqrt(max(0.0, 1.0 - u * u))


SLOPE_STEP = 1e-6
"""Step the junction slopes are read off the dish functions with, by central
difference rather than by differentiating three functions by hand. At this step
the slope is right to about a part in a million, so the tangent break it leaves
at a junction is nine orders of magnitude under a print layer; check.py
measures the continuity rather than trusting it."""


def _slope(f, y):
    return (f(y + SLOPE_STEP) - f(y - SLOPE_STEP)) / (2 * SLOPE_STEP)


Neck = namedtuple("Neck", "name lower upper reach y0 y1")
"""One join between two basins: which two, how far into each it reaches (a pair,
lower then upper), and the two y stations the bridge runs between."""


@functools.cache
def keypad_necks():
    """[Neck] joining consecutive dishes along the spine, one per adjacent pair.

    A join starts each basin's own KEYPAD_JOIN_REACH inside that basin's rim, so
    the bridge has a finite slope to match at both ends and the two ends can be
    reached differently. Matching at the rims themselves is not possible: the
    sag's tangent there is vertical, and a bridge leaving a rim at a vertical
    tangent dives straight through zero.

    Where the bridge starts inside a basin, that basin's own inboard rim stops
    existing. That is the point of the merge, and it is why only the outboard
    halves of the outer two rims are still the superellipse. It is also what the
    reach buys: the further in it starts, the more width the outline has to turn
    through and the rounder the join reads.
    """
    dishes = list(keypad_recesses().values())
    out = []
    for lower, upper in zip(dishes, dishes[1:]):
        reaches = []
        for recess in (lower, upper):
            if recess.name not in params.KEYPAD_JOIN_REACH:
                raise ValueError(
                    f"no KEYPAD_JOIN_REACH entry for the {recess.name} basin: it "
                    "was renamed and how far a join may reach into it is unstated"
                )
            reaches.append(params.KEYPAD_JOIN_REACH[recess.name])
        out.append(
            Neck(
                f"{lower.name}-{upper.name}",
                lower,
                upper,
                tuple(reaches),
                lower.cy + lower.ay - reaches[0],
                upper.cy - upper.ay + reaches[1],
            )
        )
    return out


NECK_WAIST_SAMPLES = 400
"""How finely a join is walked to find its own waist and its own radius. Both
fall out of the bridge rather than being set, so both are measured."""


def neck_waist(neck):
    """(y, half_width, depth) at the narrowest point of one join.

    Measured, not set. The bridge is a single cubic from one dish's width to the
    other's, so where it is narrowest and how narrow that is are whatever the
    two ends and the reach leave.
    """
    span = neck.y1 - neck.y0
    best = None
    for i in range(NECK_WAIST_SAMPLES + 1):
        y = neck.y0 + span * i / NECK_WAIST_SAMPLES
        width = recess_spine(y)[0]
        if best is None or width < best[1]:
            best = (y, width, face_depth_at(centerline_x(), y))
    return best


def neck_radius(neck):
    """Tightest radius the plan outline turns through anywhere in one join.

    This is what "rounder" means and it is the number to read when changing a
    reach. The outline is x = centerline_x() +/- the spine's own width, so its
    curvature is the width function's, and a join that pinches shows up here as
    a small radius long before it shows up as a narrow waist: the waist width
    barely moved when the old two-cubic bridge was dropped, and this roughly
    tripled.
    """
    span = neck.y1 - neck.y0
    step = span / NECK_WAIST_SAMPLES
    tightest = float("inf")
    for i in range(2, NECK_WAIST_SAMPLES - 1):
        y = neck.y0 + span * i / NECK_WAIST_SAMPLES
        first = (recess_spine(y + step)[0] - recess_spine(y - step)[0]) / (2 * step)
        second = (
            recess_spine(y + step)[0]
            - 2 * recess_spine(y)[0]
            + recess_spine(y - step)[0]
        ) / step**2
        if abs(second) > 1e-12:
            tightest = min(tightest, (1 + first * first) ** 1.5 / abs(second))
    return tightest


def _hermite(t, p0, m0, p1, m1, span):
    """Cubic Hermite on [0, 1], with the end slopes given per unit y and the
    interval's own length so they can be."""
    return (
        (2 * t**3 - 3 * t**2 + 1) * p0
        + (t**3 - 2 * t**2 + t) * span * m0
        + (-2 * t**3 + 3 * t**2) * p1
        + (t**3 - t**2) * span * m1
    )


def recess_spine(y):
    """(half_width, depth, shape, exponent) of the merged recess at y:
    everything the cross-section at that station needs.

    Inside a dish's body all three are that dish's own functions, so the field
    there is exactly the superellipse dish it was before the merge. Inside a
    neck all three are Hermite bridges, matching value and slope at both ends,
    which is what makes the merged field C1 across a junction rather than
    merely continuous.

All four get one cubic across the whole join, so nothing has a waypoint of
    its own: the floor simply ramps from one basin surface to the other and the
    outline simply turns from one rim into the other. Width used to get two
    cubics instead, meeting at the join's midpoint at a stated waist with zero
    slope, and that flat spot is what made the joins read as tight pinches: a
    single cubic at the same reach turns through roughly three times the radius.
    What the waist comes out as is now measured (neck_waist()) and bounded from
    below (KEYPAD_NECK_MIN) rather than set.

    The exponent is bridged as well, the wheel's basin carrying its own. It is
    constant inside a basin, so its bridge leaves either end with zero slope and
    the cross-section morphs from one basin's curve to the other's without a
    tangent break of its own.

    Joins are tested first because their intervals deliberately reach inside the
    dishes they bridge.
    """
    for neck in keypad_necks():
        if neck.y0 <= y <= neck.y1:
            lower, upper = neck.lower, neck.upper
            span = neck.y1 - neck.y0
            t = (y - neck.y0) / span
            depth = _hermite(
                t,
                _dish_depth(lower, neck.y0),
                _slope(lambda v: _dish_depth(lower, v), neck.y0),
                _dish_depth(upper, neck.y1),
                _slope(lambda v: _dish_depth(upper, v), neck.y1),
                span,
            )
            shape = _hermite(
                t,
                _dish_shape(lower, neck.y0),
                _slope(lambda v: _dish_shape(lower, v), neck.y0),
                _dish_shape(upper, neck.y1),
                _slope(lambda v: _dish_shape(upper, v), neck.y1),
                span,
            )
            width = _hermite(
                t,
                _dish_width(lower, neck.y0),
                _slope(lambda v: _dish_width(lower, v), neck.y0),
                _dish_width(upper, neck.y1),
                _slope(lambda v: _dish_width(upper, v), neck.y1),
                span,
            )
            exponent = _hermite(t, lower.n, 0.0, upper.n, 0.0, span)
            return (
                max(width, 0.0),
                max(depth, 0.0),
                min(max(shape, 0.0), 1.0),
                max(exponent, 2.0),
            )
    for recess in keypad_recesses().values():
        if abs(y - recess.cy) <= recess.ay:
            return (
                _dish_width(recess, y),
                _dish_depth(recess, y),
                _dish_shape(recess, y),
                recess.n,
            )
    return 0.0, 0.0, 1.0, params.KEYPAD_SQUIRCLE_N


SHAPE_LIMIT = 1e-9
"""How close the shape parameter may come to one before _cross() switches to
its own limit. At one the normalised profile is 0/0, and the limit it tends to
is the superellipse's own outline exponent."""


def _cross(u, shape, n):
    """The cross-section profile across x, normalised to one on the centerline
    and zero at the rim: u is |dx| over the local half width.

    This is the superellipse's own section rather than a shape of its own,
    which is what makes the merged field exactly the basin's own field inside a
    basin body. Substituting the local half width into
    |dx/ax|^n + |dy/ay|^n = s^n leaves s^n = shape + u^n (1 - shape), so the
    whole section is fixed by the shape parameter and the exponent, and dividing
    by its own value at u=0 leaves this.
    """
    if u >= 1.0:
        return 0.0
    if 1.0 - shape < SHAPE_LIMIT:
        return math.sqrt(max(0.0, 1.0 - u**n))
    top = 1.0 - (shape + u**n * (1.0 - shape)) ** (2 / n)
    bottom = 1.0 - shape ** (2 / n)
    return math.sqrt(max(0.0, top / bottom))


def face_depth_at(x, y):
    """How far below SHELL_FRONT the merged recess's floor sits at (x, y), zero
    outside its rim.

    The one piece of recess arithmetic in the model. The loft is built from it,
    check.py measures the built solid against it, and mic.py opens the inlet at
    whatever it says the floor is over the board's acoustic port, so none of
    the three can drift from the others.
    """
    width, depth, shape, n = recess_spine(y)
    if width <= 0.0 or depth <= 0.0:
        return 0.0
    return depth * _cross(abs(x - centerline_x()) / width, shape, n)


def face_floor_at(x, y):
    """The z of that floor."""
    return SHELL_FRONT - face_depth_at(x, y)


DEPTH_OVER_SAMPLES = 400
"""How finely face_depth_over() walks y across a footprint. The x half of that
search is exact, so this is the whole resolution of it; over a counterbore's
own width it puts the samples a few thousandths apart."""


def face_depth_over(x, y, half):
    """Deepest the recess gets anywhere over an axis-aligned square of side
    2*half centred at (x, y).

    Exact in x, sampled in y. The profile falls off monotonically with |dx|, so
    at any y the deepest x over the square is whichever of the centerline or
    the nearer edge lies in it, which is a clamp. Along y the spine has three
    humps and two necks and is not monotone anywhere useful, so that half is
    walked rather than solved.
    """
    xs = min(max(centerline_x(), x - half), x + half)
    return max(
        face_depth_at(xs, y - half + 2 * half * i / DEPTH_OVER_SAMPLES)
        for i in range(DEPTH_OVER_SAMPLES + 1)
    )


def face_plan_margin(x, y, half, samples=None):
    """Least recess left in plan between a keycap counterbore of side 2*half
    centred at (x, y) and the merged rim, measured across the recess.

    The counterbore is a superellipse of KEY_SQUIRCLE_N, the cap chain's own
    exponent, so it is sampled as one rather than as the rounded square it used
    to be. That tightens the reading rather than loosening it: a superellipse
    pulls in from a rounded square's corner, so the hole's outermost point is
    nearer the centre than it was. The exponent is the caps' rather than the
    rim's because it is a cap-chain width being measured; the two were one
    number until the caps got their flanks bowed out.

    What a key hole actually has to satisfy. KEYPAD_MARGIN is stated on the
    coverage box's own edges, and the superellipse bounding that box reaches
    further than the box on the axes and less far at the corners, so the margin
    a corner key really gets is neither of those numbers and has to be
    measured. The rim is x = centerline_x() +/- recess_spine()'s own width, so
    the distance to it across the recess is that width less the point's own
    offset; negative means the rim runs through the hole, and a point past
    either end of the spine reads negative because the width there is zero.
    """
    cx = centerline_x()
    count = params.KEY_SQUIRCLE_POINTS if samples is None else samples
    outline = _squircle_points(x, y, half, half, params.KEY_SQUIRCLE_N, count)
    return min(recess_spine(py)[0] - abs(px - cx) for px, py in outline)


RING_ROOF_ANGLES = 180
RING_ROOF_RADII = 21
"""How the ring roof's own annulus is walked. Both axes, not just the inner
radius: the rotary dish is concentric with the channel and so is deepest over
it at that inner edge, but the grid's and the second island's rims cross the
same annulus from outside and get deeper the further out they reach, so a
single radius answers for one of the three and not the others."""


def ring_roof_left():
    """Thinnest translucent roof left over the LED ring channel, face side.

    LED_RING_ROOF is what the roof would be under a flat face. Three things
    dish the face over the channel: the wheel basin reaching past its own
    half axis on the diagonals, and both necks running out across the annulus
    on the way to the dishes either side. What any of them sinks there comes
    out of this.
    """
    wx, wy = board.wheel_center()
    lo, hi = led_ring_roof_inner_r(), led_ring_roof_outer_r()
    deepest = 0.0
    for i in range(RING_ROOF_ANGLES):
        a = 2 * math.pi * i / RING_ROOF_ANGLES
        for j in range(RING_ROOF_RADII):
            r = lo + (hi - lo) * j / (RING_ROOF_RADII - 1)
            deepest = max(
                deepest, face_depth_at(wx + r * math.cos(a), wy + r * math.sin(a))
            )
    return params.LED_RING_ROOF - deepest


LEDGE_SAMPLES = 2000
"""Points the merged rim is walked at when measuring its clearance from the
wheel opening's bore. Dense because the closest approach is on the wheel
basin's own flanks, where the rim runs nearly parallel to the bore and the
minimum is shallow in y."""


def wheel_ledge_left():
    """Closest the merged rim comes to the wheel opening's bore, radially.

    Measured on the built spine rather than on the wheel basin's own formula,
    so it answers for the joins as well: their bridges take over the outline
    either side of the basin and are free to run somewhere the formula says
    nothing about. Negative would mean the rim crossing into the bore, which
    would put a step in the seat instead of a dished ring.

    It used to read a hundredth under WHEEL_RIM_LEDGE, the basin having been
    sized on exactly that clearance; WHEEL_BASIN_SPREAD sizes it now and this
    stands well clear. The hundredth is still there and TOLERANCE still absorbs
    it: the basin is centred on the shared centreline while the bore is centred
    on the wheel's own centre, and centerline_x() averages the two apart by that
    much.
    """
    cx = centerline_x()
    wx, wy = board.wheel_center()
    y0, y1 = recess_span()
    best = float("inf")
    for i in range(LEDGE_SAMPLES + 1):
        y = y0 + (y1 - y0) * i / LEDGE_SAMPLES
        width = recess_spine(y)[0]
        if width <= 0:
            continue
        for x in (cx - width, cx + width):
            best = min(best, math.hypot(x - wx, y - wy) - WHEEL_OPENING_R)
    return best


def recess_stations():
    """The y values the merged recess is lofted through, sorted.

    Per dish, stations at the superellipse's own parameter rather than at even
    steps in y: both the half width and the depth turn fastest at a rim and
    barely at all in the middle, and even steps in the parameter put the
    stations where the turning is. The outermost is KEYPAD_TIP_WIDTH of a half
    axis wide rather than a point, since a degenerate section is what makes a
    loft come back non-manifold; the superellipse's own end is flat to within
    microns over that width, so the blunt tip it leaves is faithful rather than
    a compromise.

    Plus even steps across each neck, where nothing is singular and the two
    Hermite halves want resolving on their own terms rather than on the
    neighbouring dish's.
    """
    count = params.KEYPAD_RECESS_STATIONS
    ys = set()
    for recess in keypad_recesses().values():
        n = recess.n
        offsets = [
            recess.ay * math.sin((math.pi / 2) * k / count) ** (2 / n)
            for k in range(count)
        ]
        offsets.append(recess.ay * (1 - params.KEYPAD_TIP_WIDTH**n) ** (1 / n))
        for dy in offsets:
            ys.add(round(recess.cy + dy, 9))
            ys.add(round(recess.cy - dy, 9))
    for neck in keypad_necks():
        steps = params.KEYPAD_NECK_STATIONS
        for i in range(steps + 1):
            ys.add(round(neck.y0 + (neck.y1 - neck.y0) * i / steps, 9))
    return sorted(ys)


SECTION_MIN_WIDTH = 0.01
"""Floor under a station's own half width, so one landing exactly on a rim
still makes a closed wire rather than a line and the loft has something to work
with. recess_stations() keeps every station KEYPAD_TIP_WIDTH of a half axis
clear of a rim, so this never fires on the present layout; it is here so that a
future station list cannot turn a loft into a crash."""


def _station_section(y):
    """The merged recess's cross-section at one station, as a face in that
    station's own plane: the floor curve under the recess, carried up the two
    vertical rim walls and closed across MERGE above the face.

    Wound counter-clockwise in (x, z) deliberately. BuildSketch mirrors a
    clockwise sketch about the workplane's own axis, so the sag would come back
    above the face instead of below it.

    The floor's points are spaced by angle across the section rather than
    evenly in x, for the same reason the stations are: the profile stands
    vertical where it meets a rim, and even steps in x leave the last chord
    cutting the corner off.
    """
    width, depth, shape, n = recess_spine(y)
    width = max(width, SECTION_MIN_WIDTH)
    cx = centerline_x()
    count = params.KEYPAD_PROFILE_POINTS
    points = []
    for i in range(count + 1):
        u = math.sin(-math.pi / 2 + math.pi * i / count)
        points.append((cx + u * width, SHELL_FRONT - depth * _cross(abs(u), shape, n)))
    points.append((cx + width, SHELL_FRONT + MERGE))
    points.append((cx - width, SHELL_FRONT + MERGE))
    plane = Plane.XZ.offset(-y)
    with BuildSketch(plane) as sketch:
        with BuildLine(plane):
            Polyline(*points, close=True)
        make_face()
    return sketch.sketch.faces()[0]


@cache.solid
def keypad_recess():
    """The whole front-face recess as the one solid the shell cuts: a smooth
    loft along y through recess_stations()' cross-sections.

    One cut, not five. The three basins and the two joins are one C1 depth
    field (recess_spine()), and the region it covers is a single column along
    y, one interval in x per station, so a loft along that column reproduces
    the field with a single wall surface and no seam in it anywhere. Fusing
    five lofts would have left a tangent-continuous surface with four edges
    across it, and the merge exists precisely so there are none.

    ruled=True, and it has to be. A fitted loft is the obvious choice on a
    surface whose whole point is that it has no creases, and it worked until the
    wheel basin took its own exponent: fitting a spline in y through this many
    sections is unstable, and the parameter change was enough to tip it over
    into diverging outright, returning a solid of negative volume spread over
    half a metre. The stations are what carry the fidelity in y instead, and
    they carry it easily. They are spaced by the superellipse's own parameter,
    so the chord between two of them departs from the field by well under a
    micron anywhere, which is three orders under a print layer and two under
    what check.py's own probes straddle. The other axis is a polyline already
    (KEYPAD_PROFILE_POINTS), so this makes the surface a fine polygonal
    approximation in both directions rather than one, which is the honest
    description of what it always was.

    Every station carries the same point count regardless, so the loft has a
    vertex to match at each and nothing to guess.

    backform.py gave up a fitted loft for the same underlying reason, where it
    overshot its sections rather than diverging. Treat one through many sections
    as suspect in this model.
    """
    return loft([_station_section(y) for y in recess_stations()], ruled=True)


def keypad_recess_facts():
    """What the merged recess came out as: one entry per dish and one per neck,
    plus how close the whole thing comes to the exterior wall.

    Shared by case.py's summary print and check.py's guards, so both read the
    same numbers rather than each re-deriving them.
    """
    ex0, ex1 = exterior_x_bounds()
    cx = centerline_x()
    out = {"dishes": {}, "necks": {}}
    for name, recess in keypad_recesses().items():
        depths = [
            face_depth_at(*board.components()[ref][:2]) for ref in island_refs(name)
        ] if name != "wheel" else []
        out["dishes"][name] = {
            "center": (cx, recess.cy),
            "half": (recess.ax, recess.ay),
            "depth": recess.depth,
            "n": recess.n,
            "key_depths": (min(depths), max(depths)) if depths else None,
        }
    for neck in keypad_necks():
        span = neck.y1 - neck.y0
        floor = min(
            face_depth_at(cx, neck.y0 + span * i / NECK_WAIST_SAMPLES)
            for i in range(NECK_WAIST_SAMPLES + 1)
        )
        waist_y, waist_half, waist_depth = neck_waist(neck)
        out["necks"][neck.name] = {
            "reach": neck.reach,
            "span": (neck.y0, neck.y1),
            "waist": (waist_y, waist_half, waist_depth),
            "radius": neck_radius(neck),
            "floor": floor,
            "ends": (_dish_width(neck.lower, neck.y0), _dish_width(neck.upper, neck.y1)),
        }
    widest = max(r.ax for r in keypad_recesses().values())
    out["edge_gap"] = min(cx - widest - ex0, ex1 - cx - widest)
    out["centerline"] = (cx, centerline_spread())
    out["stations"] = len(recess_stations())
    return out


def centerline_keys_span():
    """(y0, y1) between the outermost key rows of the two keyed islands: the
    grid's own top row's far edge and the second island's bottom row's far
    edge, each taken at the counterbore rather than the switch centre.

    What the recess has to stay open across, which is what check.py's neck
    continuity pass measures. Not the neck's own span: a neck that pinched
    apart would still be a neck, and what would be lost is the recess running
    unbroken from one island's keys to the other's.
    """
    parts = board.components()
    grid = max(parts[ref][1] for ref in island_refs("grid"))
    second = min(parts[ref][1] for ref in island_refs("second"))
    return grid + key_size() / 2, second - key_size() / 2


def pad_lobes():
    """[(name, x0, y0, x1, y1)] one rectangle per keypad island: that island's
    own keys, padded PAD_MARGIN on every side.

    The keys alone. The mic is not in it, unlike the recess above: the pad is
    there to carry stems and plungers, and the inlet's duct comes down outside
    it.
    """
    out = []
    for name in ("grid", "second"):
        xs, ys = _key_bounds(island_refs(name))
        out.append(
            (
                name,
                min(xs) - params.PAD_MARGIN,
                min(ys) - params.PAD_MARGIN,
                max(xs) + params.PAD_MARGIN,
                max(ys) + params.PAD_MARGIN,
            )
        )
    return out


def pad_wheel_gap():
    """Closest either lobe comes to the pad's own wheel clearance band,
    pad_clear_y() either side of the wheel centre.

    The band used to be a cut: the pad was one full-width slab and the bore
    severed it. The lobes are tight rectangles now and stop short of the band
    on their own, so there is nothing left to cut and this is the number that
    says so. It is what keeps the lip's rotating clearance and the LEDs' own
    sight line free of silicone, which is what the band was for.
    """
    _, wy = board.wheel_center()
    half = pad_clear_y()
    return min(
        min(abs(y0 - wy), abs(y1 - wy)) - half for _, _, y0, _, y1 in pad_lobes()
    )


def _pad_limit():
    """The cavity, inset by PAD_FIT: what a lobe is clipped inside if its own
    rectangle would ever reach the wall. Idle at the present layout, both lobes
    sitting well inboard of it."""
    inner, _ = _profiles()
    return Face(inner.outer_wire().offset_2d(-params.PAD_FIT, kind=Kind.INTERSECTION))


def pad_lobe_face(name):
    """One lobe's outline: its rectangle, rounded at PAD_RADIUS, clipped inside
    _pad_limit()."""
    x0, y0, x1, y1 = next(box[1:] for box in pad_lobes() if box[0] == name)
    with BuildSketch() as sketch:
        with Locations(((x0 + x1) / 2, (y0 + y1) / 2)):
            RectangleRounded(x1 - x0, y1 - y0, params.PAD_RADIUS)
    rect = sketch.sketch.faces()[0]
    clipped = extrude(rect, amount=1, dir=(0, 0, 1)) & extrude(
        _pad_limit(), amount=1, dir=(0, 0, 1)
    )
    return clipped.faces().sort_by()[0]


def _stem(x, y):
    """The soft stem a cap sits over, raised out of the pad where a keytop was.

    Square rather than round, because the legend on the cap has an orientation
    and a round stem holds none. It starts inside the web rather than on it, so
    it merges into one solid, and it reaches the socket ceiling, so a press
    drives through the stem rather than through the flange.

    A plain prism, no barb. The flange retains the cap now, and a barb would put
    an undercut on every stem in a moulded pad while fighting the blind assembly
    that seats nine of them at once.
    """
    return _rounded_prism(x, y, params.STEM_W, params.STEM_R, PAD_WEB_BOTTOM, STEM_TOP)


def _boss_clearances(x0, y0, x1, y1):
    """The holes a lobe needs where a front-plate boss passes through it.

    Off the boss's collar, not the boss, so a stem clears the ceiling the collar
    leaves behind as well as the boss itself. A boss whose clearance circle
    crosses the lobe's edge would leave a crescent bite ending in two cusps
    there, so that cut gains a slot out through the edge and becomes an open U
    instead: same rounded end, straight sides, no points. All four edges are
    tested now that a lobe is a tight rectangle rather than the full cavity
    width.
    """
    clearance_d = params.BOSS_OD + 2 * (params.BOSS_COLLAR + params.PAD_BOSS_CLEARANCE)
    r = clearance_d / 2
    bottom, top = PAD_WEB_BOTTOM - 1, STEM_TOP + 1
    out = []
    for x, y in mount_points():
        if x < x0 - r or x > x1 + r or y < y0 - r or y > y1 + r:
            continue
        cut = _hole(x, y, clearance_d, bottom, top)
        for edge, axis, out_dir in (
            (x0, "x", -1),
            (x1, "x", 1),
            (y0, "y", -1),
            (y1, "y", 1),
        ):
            here = x if axis == "x" else y
            if abs(here - edge) >= r:
                continue
            reach = abs(here - edge) + 1
            dx = out_dir * reach / 2 if axis == "x" else 0
            dy = out_dir * reach / 2 if axis == "y" else 0
            size = (reach, clearance_d) if axis == "x" else (clearance_d, reach)
            cut = _fuse(
                cut,
                Pos(x + dx, y + dy, (bottom + top) / 2)
                * Box(size[0], size[1], top - bottom),
            )
        out.append(cut)
    return out


def _mic_clearance():
    """Open-edge clearance around the mic duct's widest ceiling chamfer."""
    x, y = mic_port()
    diameter = 2 * (
        mic_duct_or() + params.STANDOFF_CHAMFER + params.PAD_MIC_CLEARANCE
    )
    return _hole(x, y, diameter, PAD_WEB_BOTTOM - 1, PAD_WEB_TOP + 1)


@cache.solid
def button_pad():
    """One part in the export, two lobes in the mould: one per keypad island,
    each held up against the ceiling by its own plungers.

    Two separate rectangles rather than one slab the wheel bore severs. The old
    shape reached the full cavity width and the full span of every key, so both
    ends of it stretched toward the wheel and the bore had to take the middle
    back out, leaving each lobe with a semicircular bite facing the encoder. A
    lobe padded PAD_MARGIN off its own keys stops short of the wheel on its own
    (pad_wheel_gap()), so nothing is cut there any more and the bite is gone.

    Print in TPU to try it, mould in silicone to keep it.
    """
    parts = board.components()
    lobes = []
    for name, x0, y0, x1, y1 in pad_lobes():
        body = _slab(pad_lobe_face(name), PAD_WEB_BOTTOM, PAD_WEB_TOP)
        raised = []
        for ref in island_refs(name):
            x, y = parts[ref][:2]
            raised.append(_stem(x, y))
            raised.append(_hole(x, y, params.PLUNGER_D, SWITCH_TOP, PAD_WEB_TOP))
        cuts = _boss_clearances(x0, y0, x1, y1)
        if name == "second":
            cuts.append(_mic_clearance())
        lobes.append(_cut(_fuse(body, *raised), *cuts))
    return _fuse(*lobes)
