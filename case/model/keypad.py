"""The keys themselves: how big each one can be, the one continuous concave
recess sunk into the front face around them and around the wheel, and the soft
pad that carries a stem and a plunger under every switch.

The recess has two superellipse basins and one angular-blend wheel basin. Two
necks join them into one C1 depth field, cut as one loft along y. Read
recess_spine() and face_depth_at() first: everything else about it, including
every check, is built off those two."""

import bisect
import functools
import math
from collections import namedtuple

from build123d import (
    Box,
    BuildLine,
    BuildSketch,
    Circle,
    Cone,
    Face,
    Kind,
    Locations,
    Plane,
    Polyline,
    Pos,
    RectangleRounded,
    Shell,
    Solid,
    Wire,
    extrude,
    fillet,
    loft,
    make_face,
    offset,
)

import board
import cache
import params

from .legends import legend_solids
from .mic import mic_duct_or, mic_port
from .shape import (
    _cut,
    _fuse,
    _hole,
    _isect,
    _offset_face,
    _rounded_prism,
    _slab,
    _squircle_points,
    _squircle_prism,
)
from .stack import (
    CAP_BOTTOM,
    EXTERIOR,
    FDM_FACE,
    LEGACY_SWITCH_TOP,
    MERGE,
    PAD_SKIRT_BOTTOM,
    PAD_WEB_BOTTOM,
    PAD_WEB_TOP,
    SHELL_FRONT,
    STIFFENED_WALL,
    SWITCH_TOP,
    WHEEL_OPENING_R,
    cap_top,
    face_z,
    stem_top,
)
from .wheel_ring import (
    led_ring_ceiling_under,
    led_ring_clip_reach,
    led_ring_flat_outer_r,
    led_ring_roof_inner_r,
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


def key_size(ref=None):
    """Side of the square key footprint: the grid pitch less KEY_GAP. Every
    switch takes the same size, so `ref` is accepted for the callers that name
    a switch and does not change the answer."""
    return key_pitch() - params.KEY_GAP


def island_refs(name):
    """The switches one keyed recess covers: KEYPAD_ISLAND_2 for "second",
    everything else for "grid". One reader, because the recess's own coverage
    box, the pad lobe under it and every per-key check have to agree on which
    keys belong where."""
    if name == "second":
        return [ref for ref in board.refs("SW") if ref in params.KEYPAD_ISLAND_2]
    return [ref for ref in board.refs("SW") if ref not in params.KEYPAD_ISLAND_2]


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
    own extent. What KEYPAD_EDGE_MARGIN is measured from, and where the face
    meets the wall at FACE_WALL_TOP."""
    return EXTERIOR[0], EXTERIOR[2]


def exterior_y_bounds():
    """(y0, y1) of the case's own exterior end walls, the same profile the
    other way. keypad_recesses() caps the half axes on this axis as well, so a
    layout change cannot walk a recess off the end of the case."""
    return EXTERIOR[1], EXTERIOR[3]


def _centres():
    """The x of the three coverage centres and of the wheel's own centre."""
    xs = [(x0 + x1) / 2 for _, x0, _, x1, _ in keypad_coverage()]
    return xs + [board.wheel_center()[0]]


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
    xs = _centres()
    return sum(xs) / len(xs)


def centerline_spread():
    """How far the furthest of those centres sits from centerline_x()."""
    return max(abs(x - centerline_x()) for x in _centres())


Recess = namedtuple("Recess", "name cy ax ay depth n rounding soft lift")
"""One basin on the spine: where its centre sits along y, its two superellipse
half axes, its depth at that centre, and the exponent of its outline. Then how
far its outline rounds toward a circle on the axes (see _level()), the depth of
its soft rim, and its lip lift (see _spine_depth()). All three basins share
centerline_x()."""


@functools.cache
def keypad_recesses():
    """{name: Recess} for the three dishes the merged front-face recess is
    built from: the grid, the second island, and the wheel, in that order along
    y and disjoint in y.

    Each is a superellipse of its own exponent about its own centre, with a
    depth that is zero on that curve and greatest at the centre. They are not
    separate cuts: keypad_necks() bridges them into one recess and
    recess_spine() is the merged field. What survives per dish is the outboard
    half of its rim, its own depth, and its own deepest point.

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
    around the corner keys themselves than taking it out of both would. The
    same cap applies in y, which no basin reaches on this board.

    The wheel's is not sized off a coverage box at all. It has no keys under
    it, so its half axes are stated outright, WHEEL_BASIN_SPREAD past the bore on
    each axis and square, and what the bore does not swallow is the seat ring
    around the knob. WHEEL_RIM_LEDGE used to be that spread and is only the floor
    now: sizing the basin on the clearance minimum is what left the ring as
    narrow as the minimum. Its full axis rounding gives the cardinal axes
    circular curvature. WHEEL_SQUIRCLE_N keeps exact superellipse reach on the
    diagonals.

    That sizing rule still delivers WHEEL_RIM_LEDGE at every angle, and it does
    so for the same reason at either exponent. Above n=2 a superellipse's own
    axes are where it comes closest to its centre, so the half axis *is* the
    clearance, and the diagonals only ever stand further out. Below n=2 that
    inverts and the rule would stop holding, which is why check.py measures the
    clearance around the whole curve rather than trusting the arithmetic.
    """
    keyed = params.KEYPAD_SQUIRCLE_N
    grow = 2 ** (1 / keyed)
    ex0, ey0, ex1, ey1 = EXTERIOR
    cx = centerline_x()
    room_x = min(cx - ex0, ex1 - cx) - params.KEYPAD_EDGE_MARGIN

    def room_y(cy):
        return min(cy - ey0, ey1 - cy) - params.KEYPAD_EDGE_MARGIN

    soft = {
        "grid": "KEYPAD_RIM_SOFT",
        "second": "KEYPAD_RIM_SOFT_2",
        "wheel": "WHEEL_RIM_SOFT",
    }
    out = {}
    for name, x0, y0, x1, y1 in keypad_coverage():
        cy = (y0 + y1) / 2
        depth = params.KEYPAD_DISH_DEPTH_2 if name == "second" else params.KEYPAD_DISH_DEPTH
        out[name] = Recess(
            name,
            cy,
            min((x1 - x0) / 2 * grow, room_x),
            min((y1 - y0) / 2 * grow, room_y(cy)),
            depth,
            keyed,
            0.0,
            getattr(params, soft[name]),
            params.KEYPAD_LIP_LIFT,
        )
    _, wy = board.wheel_center()
    half = WHEEL_OPENING_R + params.WHEEL_BASIN_SPREAD
    out["wheel"] = Recess(
        "wheel",
        wy,
        min(half, room_x),
        min(half, room_y(wy)),
        params.WHEEL_DISH_DEPTH,
        params.WHEEL_SQUIRCLE_N,
        1.0,
        getattr(params, soft["wheel"]),
        0.0,
    )
    for recess in out.values():
        if not 0.0 <= recess.soft < recess.depth:
            raise ValueError(
                f"{soft[recess.name]} {recess.soft:.2f} must be at least zero and "
                f"less than the {recess.name} basin's depth {recess.depth:.2f}, "
                f"or the dish centre loses depth"
            )
    if not 0.0 <= params.KEYPAD_LIP_LIFT <= 1.0:
        raise ValueError(
            f"KEYPAD_LIP_LIFT {params.KEYPAD_LIP_LIFT:.2f} must be from zero to "
            "one, or the key dish floors rise above the face"
        )
    return {name: out[name] for name in sorted(out, key=lambda n: out[n].cy)}


def recess_span():
    """(y0, y1) the merged recess runs between: the outboard rim of the first
    dish to the outboard rim of the last."""
    dishes = list(keypad_recesses().values())
    return dishes[0].cy - dishes[0].ay, dishes[-1].cy + dishes[-1].ay


def _level(x, v, n, rounding):
    """How far out the normalized point (x, v) = (|dx/ax|, |dy/ay|) sits in a
    basin: zero at its centre and one on its rim.

    With no rounding it is the superellipse level (x^n + v^n)^(1/n). The
    rounding blends the outline's radius toward the unit circle by cos^2 of
    twice the point's angle. As a result, the curvature on each axis is
    circular and the reach on the diagonals stays the superellipse's own."""
    h = math.hypot(x, v)
    if h == 0.0:
        return 0.0
    squircle = h / (x**n + v**n) ** (1 / n)
    blend = rounding * ((x * x - v * v) / (h * h)) ** 2
    return h / (squircle + blend * (1.0 - squircle))


def _rim_x(v, n, rounding):
    """Half width of a basin's plan outline at v = |dy/ay|, over its x half
    axis: where _level() reaches one. A plain superellipse has a closed form.
    A rounded one is bisected, its rim lying inside 2^(1/2 - 1/n)."""
    if v >= 1.0:
        return 0.0
    if rounding == 0.0:
        return (1.0 - v**n) ** (1 / n)
    lo, hi = 0.0, 2 ** (0.5 - 1 / n)
    for _ in range(52):
        mid = (lo + hi) / 2
        if _level(mid, v, n, rounding) < 1.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


Spine = namedtuple("Spine", "width depth shape n rounding edge soft lift")
"""Everything the cross-section at one y needs: the half width, the depth on
the centerline, the shape |dy/ay|^n, the exponent, the axis rounding, the half
width over the x half axis, the soft rim depth, and the lip lift."""

SPINE_LIMITS = (
    (0.0, math.inf),
    (0.0, math.inf),
    (0.0, 1.0),
    (2.0, math.inf),
    (0.0, 1.0),
    (0.0, math.inf),
    (0.0, math.inf),
    (0.0, 1.0),
)
"""The range each Spine field of a neck is held to. A cubic with end slopes
can overshoot its two ends."""


def _basin_spine(recess, y):
    """One basin's own Spine at y.

    The shape is the only thing besides the depth, the half width and the
    exponent that the basin's cross-section depends on. That is what lets the
    merged field be exact inside a basin and still be built from one Spine per
    station. The centerline depth is the superellipse's own sag: at dx=0 the
    exponent drops out and the profile is a plain circular arc in |dy/ay|."""
    v = min(abs(y - recess.cy) / recess.ay, 1.0)
    edge = _rim_x(v, recess.n, recess.rounding)
    return Spine(
        recess.ax * edge,
        recess.depth * math.sqrt(max(0.0, 1.0 - v * v)),
        v**recess.n,
        recess.n,
        recess.rounding,
        edge,
        recess.soft,
        recess.lift,
    )


def wheel_basin_width(y):
    """Half width of the unjoined wheel basin outline at y."""
    return _basin_spine(keypad_recesses()["wheel"], y).width


SLOPE_STEP = 1e-6
"""Step the junction slopes are read off the basin's Spine with, by central
difference rather than by differentiating each field by hand. At this step
the slope is right to about a part in a million, so the tangent break it leaves
at a junction is nine orders of magnitude under a print layer; check.py
measures the continuity rather than trusting it."""


def _basin_slope(recess, y):
    """d/dy of one basin's Spine at y. The fields that are constant in a basin
    come out exactly zero."""
    above = _basin_spine(recess, y + SLOPE_STEP)
    below = _basin_spine(recess, y - SLOPE_STEP)
    return Spine(*((a - b) / (2 * SLOPE_STEP) for a, b in zip(above, below)))


Neck = namedtuple("Neck", "name lower upper reach y0 y1 ends floor")
"""One join between two basins: which two, how far into each it reaches (a pair,
lower then upper), and the two y stations the bridge runs between. `ends` is
the lower basin's Spine and its slope at y0, then the upper basin's at y1.
`floor` is the centreline depth across the join, see _neck_floor()."""


KEY_ROW_FLATTEN = 3.0
"""How far in from its key row nearest a neck a keyed basin's centreline floor
turns flat. The basin's own floor still climbs about 0.02 per mm at that row,
and over this length the turn stays gentle and inside the row's counterbores."""


def _depth_and_slope(recess, y):
    return _basin_spine(recess, y).depth, _basin_slope(recess, y).depth


def _piece(ya, da, ma, yb, db, mb):
    """A Hermite piece (y0, y1, d0, m0, d1, m1) of depth, in y order."""
    return (ya, yb, da, ma, db, mb) if ya < yb else (yb, ya, db, mb, da, ma)


def _neck_floor(lower, upper):
    """[(y0, y1, d0, m0, d1, m1)]: the two Hermite pieces, in y order, that the
    centreline depth follows across the join of a keyed basin and the wheel
    basin.

    The floor must not rise between the two basins. Each basin's own depth falls
    toward its rim, so a bridge between those two ends leaves a ridge across the
    join. Here the keyed basin's floor turns flat at its key row nearest the
    wheel, over KEY_ROW_FLATTEN. From that row the depth grows as the cube of
    the distance, so the floor leaves the row flat and then only falls. The
    cube meets the wheel basin's own profile at the point where its end slope
    equals the wheel's own slope. On this board that point is inside the bore.
    The plan outline does not change, because only the depth is bridged."""
    keyed, wheel = (upper, lower) if lower.name == "wheel" else (lower, upper)
    toward = 1.0 if wheel.cy > keyed.cy else -1.0
    rows = [board.components()[ref][1] for ref in island_refs(keyed.name)]
    row = max(rows) if toward > 0 else min(rows)
    start = row - toward * min(KEY_ROW_FLATTEN, abs(row - keyed.cy))
    level = _basin_spine(keyed, row).depth
    if _basin_spine(wheel, wheel.cy).depth <= level:
        raise ValueError(
            f"the wheel basin must be deeper than the {keyed.name} basin's key "
            "row, or the floor across their join cannot fall into the wheel"
        )

    def short(y):
        depth, slope = _depth_and_slope(wheel, y)
        return slope * (y - row) > 3 * (depth - level)

    near, far = row, wheel.cy
    for _ in range(60):
        mid = (near + far) / 2
        near, far = (mid, far) if short(mid) else (near, mid)
    meet = (near + far) / 2
    return sorted(
        [
            _piece(start, *_depth_and_slope(keyed, start), row, level, 0.0),
            _piece(row, level, 0.0, meet, *_depth_and_slope(wheel, meet)),
        ]
    )


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
        for recess in (lower, upper):
            if recess.name not in params.KEYPAD_JOIN_REACH:
                raise ValueError(
                    f"no KEYPAD_JOIN_REACH entry for the {recess.name} basin: it "
                    "was renamed and how far a join may reach into it is unstated"
                )
        reach = (
            params.KEYPAD_JOIN_REACH[lower.name],
            params.KEYPAD_JOIN_REACH[upper.name],
        )
        y0 = lower.cy + lower.ay - reach[0]
        y1 = upper.cy - upper.ay + reach[1]
        ends = (
            _basin_spine(lower, y0),
            _basin_slope(lower, y0),
            _basin_spine(upper, y1),
            _basin_slope(upper, y1),
        )
        name = f"{lower.name}-{upper.name}"
        floor = _neck_floor(lower, upper)
        out.append(Neck(name, lower, upper, reach, y0, y1, ends, floor))
    return out


NECK_WAIST_SAMPLES = 400
"""How finely a join is walked to find its own waist and its own radius. Both
fall out of the bridge rather than being set, so both are measured."""


def _neck_walk(neck):
    """[(y, half width)] at NECK_WAIST_SAMPLES even steps across one join, both
    ends included."""
    span = neck.y1 - neck.y0
    count = NECK_WAIST_SAMPLES
    ys = [neck.y0 + span * i / count for i in range(count + 1)]
    return [(y, recess_spine(y).width) for y in ys]


def neck_waist(neck):
    """(y, half_width, depth) at the narrowest point of one join.

    Measured, not set. The bridge is a single cubic from one dish's width to the
    other's, so where it is narrowest and how narrow that is are whatever the
    two ends and the reach leave.
    """
    width, y = min((width, y) for y, width in _neck_walk(neck))
    return y, width, face_depth_at(centerline_x(), y)


def neck_radius(neck):
    """Tightest radius the plan outline turns through anywhere in one join.

    This is what "rounder" means and it is the number to read when changing a
    reach. The outline is x = centerline_x() +/- the spine's own width, so its
    curvature is the width function's, and a join that pinches shows up here as
    a small radius long before it shows up as a narrow waist.
    """
    widths = [width for _, width in _neck_walk(neck)]
    step = (neck.y1 - neck.y0) / NECK_WAIST_SAMPLES
    tightest = math.inf
    for i in range(2, NECK_WAIST_SAMPLES - 1):
        first = (widths[i + 1] - widths[i - 1]) / (2 * step)
        second = (widths[i + 1] - 2 * widths[i] + widths[i - 1]) / step**2
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
    """The Spine at y: everything the cross-section at that station needs.

    Inside a dish's body it is that dish's own _basin_spine(). Inside a neck,
    each field but the depth is one Hermite cubic across the whole join. The
    cubic matches the value and the slope of each basin at its end of the join,
    so the merged field is C1 across a junction rather than only continuous.
    The exponent, the axis rounding, the soft rim and the lip lift are constant
    in a basin, so they leave either end with zero slope. The section then morphs from one
    basin's curve to the other's without a tangent break of its own.

    The depth follows the neck's own floor instead (_neck_floor()), from the
    key row nearest the wheel into the wheel basin, so the floor does not rise
    between the two. It is C1 as well.

    The outline has no waypoint of its own: it turns from one rim into the
    other. What the waist comes out as is measured (neck_waist()) and bounded
    from below (KEYPAD_NECK_MIN) rather than set.

    Joins are tested first because their intervals deliberately reach inside the
    dishes they bridge.
    """
    spine = _plain_spine(y)
    for neck in keypad_necks():
        for y0, y1, *ends in neck.floor:
            if y0 <= y <= y1:
                depth = _hermite((y - y0) / (y1 - y0), *ends, y1 - y0)
                return spine._replace(depth=max(depth, 0.0))
        if neck.y0 <= y <= neck.y1:
            side = neck.lower if y < neck.floor[0][0] else neck.upper
            return spine._replace(depth=_basin_spine(side, y).depth)
    return spine


def _plain_spine(y):
    """recess_spine() before a neck's floor sets the depth."""
    for neck in keypad_necks():
        if neck.y0 <= y <= neck.y1:
            span = neck.y1 - neck.y0
            t = (y - neck.y0) / span
            return Spine(
                *(
                    min(max(_hermite(t, *ends, span), lo), hi)
                    for *ends, (lo, hi) in zip(*neck.ends, SPINE_LIMITS)
                )
            )
    for recess in keypad_recesses().values():
        if abs(y - recess.cy) <= recess.ay:
            return _basin_spine(recess, y)
    return Spine(0.0, 0.0, 1.0, params.KEYPAD_SQUIRCLE_N, 0.0, 0.0, 0.0, 0.0)


def _cross(spine, u):
    """The cross-section profile across x, normalised to one on the centerline
    and zero at the rim: u is |dx| over the local half width.

    This is the basin's own section rather than a shape of its own, which is
    what makes the merged field exactly the basin's own field inside a basin
    body. With v = shape^(1/n), the point sits at (u * edge, v) and the rim at
    (edge, v). Their _level() values rho and rim give the section
    sqrt((rim^2 - rho^2) / (rim^2 - v^2)). Inside a basin the rim level is one,
    so depth * _cross() is the basin's own depth * sqrt(1 - rho^2).
    """
    if u >= 1.0:
        return 0.0
    _, _, shape, n, rounding, edge, _, _ = spine
    v = shape ** (1 / n)
    rim = _level(edge, v, n, rounding)
    span = rim * rim - v * v
    if span <= 0.0:
        return 0.0
    rho = _level(u * edge, v, n, rounding)
    return math.sqrt(max(0.0, rim * rim - rho * rho) / span)


def face_depth_at(x, y):
    """The merged recess's depth field at (x, y): how far its floor sits below
    the built face, stack.face_z(). It is zero outside the start of the rim
    chamfer's top round, RECESS_CHAMFER_ROUND_OUT outside the rim.

    Every basin is cut down from that face, and the dish's own zero contour is
    the rim, the recess_outline() plan outline. The face lowers each
    floor by its own drop off the crown, but it does not move the rim. In the
    two key basins, the lip lift gives part of that drop back, see
    _spine_depth(). The soft rim roll, _soft_rim(), is set to zero, because
    the rim chamfer replaces it.

    The one piece of recess arithmetic in the model. The loft is built from it,
    check.py measures the built solid against it, and mic.py opens the inlet at
    whatever it says the floor is over the board's acoustic port, so none of
    the three can drift from the others.

    Within RECESS_CHAMFER_W inside the rim, the depth is the rim chamfer's
    (_chamfer_z()). In each section normal to the outline, a round leaves the
    face at the rim for RECESS_CHAMFER_ROUND_W, and a second round meets the
    dish floor RECESS_CHAMFER_W in, RECESS_CHAMFER_INNER_ROUND_W wide
    (_rim_section()). The loft
    reads the dish alone, _spine_depth(), and keypad_chamfer() cuts the
    chamfer.
    """
    return _field_depth(recess_spine(y), x, y)


def _field_depth(spine, x, y):
    """face_depth_at() at (x, y), from a recess_spine(y) result already in hand:
    the chamfer's depth from where its top round leaves the face to the
    chamfer's inner ring, the dish's own depth inside that ring, and zero
    outside the top round's start."""
    if params.RECESS_CHAMFER_W <= 0.0:
        return _spine_depth(spine, x, y)
    if not _in_ring(_start_index(), x, y):
        return 0.0
    if _in_ring(_chamfer_index(), x, y):
        return _spine_depth(spine, x, y)
    return max(0.0, face_z(x, y) - _chamfer_z(x, y))


CHAMFER_GRID = 0.5
"""Cell size, in mm, of the plan grids that the chamfer's lookups file
polygon edges and floor triangles in, so a query reads a few and not all."""


def _ring_index(ring):
    """{row: [(x0, y0, x1, y1)]}: the edges of one closed polygon, filed under
    each CHAMFER_GRID row of y that they span."""
    index = {}
    for (x0, y0, *_), (x1, y1, *_) in zip(ring, ring[1:] + ring[:1]):
        j0 = math.floor(min(y0, y1) / CHAMFER_GRID)
        j1 = math.floor(max(y0, y1) / CHAMFER_GRID)
        for j in range(j0, j1 + 1):
            index.setdefault(j, []).append((x0, y0, x1, y1))
    return index


@functools.cache
def _start_index():
    return _ring_index(_chamfer_rings()[0])


@functools.cache
def _chamfer_index():
    return _ring_index(_chamfer_rings()[2])


def _in_ring(index, x, y):
    """Whether (x, y) is inside the polygon of one _ring_index(): an even-odd
    count of the edges that a ray from the point toward +x crosses."""
    inside = False
    for x0, y0, x1, y1 in index.get(math.floor(y / CHAMFER_GRID), ()):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


@functools.cache
def _chamfer_cells():
    """{cell: [triangle]}: the chamfer floor's triangles, filed under each
    CHAMFER_GRID cell that their plan bounding box touches."""
    cells = {}
    for tri in _chamfer_floor():
        xs = [p[0] for p in tri]
        ys = [p[1] for p in tri]
        i0, i1 = (math.floor(v / CHAMFER_GRID) for v in (min(xs), max(xs)))
        j0, j1 = (math.floor(v / CHAMFER_GRID) for v in (min(ys), max(ys)))
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                cells.setdefault((i, j), []).append(tri)
    return cells


def _chamfer_z(x, y):
    """The chamfer floor's z over (x, y), by barycentric weights in the floor
    triangle that holds the point. A point on no triangle, which only float
    error at a triangle edge can leave, takes the triangle it is least
    outside."""
    best = None
    cell = (math.floor(x / CHAMFER_GRID), math.floor(y / CHAMFER_GRID))
    for a, b, c in _chamfer_cells().get(cell, ()):
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        wa = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det
        wb = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det
        wc = 1.0 - wa - wb
        least = min(wa, wb, wc)
        if best is None or least > best[0]:
            best = (least, wa * a[2] + wb * b[2] + wc * c[2])
        if least >= 0.0:
            break
    return best[1] if best else face_z(x, y)


def _spine_depth(spine, x, y, least=None):
    """The dish's own depth at (x, y), from a recess_spine(y) result already in
    hand, with no rim chamfer. The loft is built from this. A softened depth under
    `least`, RIM_DEPTH_MIN by default, is zero.

    The lip lift then multiplies the softened depth by one less spine.lift
    times _lip_rise(). The floor then sits closer to the face toward the side
    walls, so a key dish has a crest near its outer key columns. The
    cutoff reads the depth before the lift, so the rim does not move."""
    if spine.width <= 0.0 or spine.depth <= 0.0:
        return 0.0
    dx = abs(x - centerline_x())
    soft = _soft_rim(spine.depth * _cross(spine, dx / spine.width), spine.soft)
    if soft < (RIM_DEPTH_MIN if least is None else least):
        return 0.0
    if spine.lift <= 0.0:
        return soft
    return soft * (1.0 - spine.lift * _lip_rise(dx, y))


def _lip_rise(dx, y):
    """Smoothstep, from zero on the centerline to one at and past
    KEYPAD_LIP_CREST, of the face drop at dx from the centerline over the drop
    at KEYPAD_LIP_CREST. The drop is read at the same y, so the rise follows
    the superellipse and not dx itself."""
    cx = centerline_x()
    crown = face_z(cx, y)
    reach = crown - face_z(cx + params.KEYPAD_LIP_CREST, y)
    if reach <= 1e-9:
        return 1.0
    t = min(max((crown - face_z(cx + dx, y)) / reach, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


RIM_DEPTH_MIN = 0.005
"""Least dish depth the field keeps. A softened depth under this is zero.

The soft rim meets the face with zero slope, so near a rim, and over a long
stretch near each tip, the floor is only microns under the face. The loft then
crosses the face at a grazing angle, and the cut leaves slivers that mesh torn.
With this floor, the field ends with a step of this height, and every loft
point that has less depth is lifted RIM_LIFT above the face, so the loft
crosses the face steeply. The step is far under a print layer, and the rim
moves inward by about a tenth."""


def _soft_rim(d, c):
    """Depth d with its last c rolled into the face: d^3 (3c - 2d) / c^3 below
    c, and d itself from c down.

    The plain section meets its rim with a vertical tangent. This map has value
    c and slope one at d = c, and it goes as 3 d^3 / c^2 near zero. As a
    result, the floor meets the face with zero slope, and nothing deeper than c
    changes. Every basin has its own c, and the necks blend between them. See
    WHEEL_RIM_SOFT."""
    if c <= 0.0 or d >= c:
        return d
    return d**3 * (3 * c - 2 * d) / c**3


def face_floor_at(x, y):
    """The z of the built recessed front's outer surface at (x, y): the depth
    field under the built face. It is the face itself outside the rim, the
    rim chamfer just inside it, and the dish further in. It is never above
    the face, because every basin is cut down from the face."""
    return face_z(x, y) - face_depth_at(x, y)


FLOOR_OVER_SAMPLES = 80
"""How finely face_floor_over() walks each axis across a footprint. Over a
counterbore's own width it puts the samples about 0.15 apart. Five times as
many rows moves no land by more than a nanometre."""


def face_floor_over(x, y, half):
    """Lowest the built surface gets anywhere over an axis-aligned square of
    side 2*half centred at (x, y).

    The surface is the built face less the depth field, the rim chamfer's
    depth near the rim and the dish further in. Across x the face falls away from the
    crown and the dish gets shallower away from the centerline. As a result,
    the lowest point can be inside the square, so both axes are walked. The
    centerline is added to the x samples, because the dish is deepest there.
    """
    cx = centerline_x()
    count = FLOOR_OVER_SAMPLES
    steps = [2 * half * i / count - half for i in range(count + 1)]
    xs = [x + step for step in steps]
    if x - half < cx < x + half:
        xs.append(cx)
    lowest = math.inf
    for py in (y + step for step in steps):
        spine = recess_spine(py)
        lowest = min(
            lowest, *(face_z(px, py) - _field_depth(spine, px, py) for px in xs)
        )
    return lowest


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
    return min(recess_spine(py).width - abs(px - cx) for px, py in outline)


RING_ROOF_ANGLES = 180
RING_ROOF_RADII = 21
"""How the ring roof's own annulus is walked. Both axes, not just the inner
radius: the rotary dish is concentric with the channel and so is deepest over
it at that inner edge, but the grid's and the second island's rims cross the
same annulus from outside and get deeper the further out they reach, so a
single radius answers for one of the three and not the others."""


def ring_roof_left():
    """Thinnest translucent roof left over the LED ring channel, face side.

    The roof is the built surface less led_ring_ceiling_under(). That ceiling
    is the arch, or LED_RING_FACE_ROOF under the built face where that is
    higher. As a result, the roof is LED_RING_FACE_ROOF wherever the ceiling
    follows the face. It is thinner only where the face falls to the arch, at
    the east and west sides of the knob, where the channel comes near the side
    walls. Three things dish the face over the channel: the wheel basin past
    its own half axis on the diagonals, and both necks on their way to the
    dishes either side. The ceiling goes down with them until the arch stops
    it, and what they sink past that comes out of this value.

    The walk covers the roof flat on each bearing, from the top of the inner
    bevel out to led_ring_flat_outer_r(). Near the X axis the cavity wall cuts
    the channel off inside that radius, so there the walk stops at
    led_ring_clip_reach().
    """
    wx, wy = board.wheel_center()
    lo = led_ring_roof_inner_r()
    thinnest = math.inf
    for i in range(RING_ROOF_ANGLES):
        a = 2 * math.pi * i / RING_ROOF_ANGLES
        hi = min(led_ring_flat_outer_r(a), led_ring_clip_reach(a))
        for j in range(RING_ROOF_RADII):
            r = lo + (hi - lo) * j / (RING_ROOF_RADII - 1)
            x, y = wx + r * math.cos(a), wy + r * math.sin(a)
            thinnest = min(thinnest, face_floor_at(x, y) - led_ring_ceiling_under(x, y))
    return thinnest


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
        width = recess_spine(y).width
        if width <= 0:
            continue
        for x in (cx - width, cx + width):
            best = min(best, math.hypot(x - wx, y - wy) - WHEEL_OPENING_R)
    return best


def _base_stations():
    """The y values recess_stations() refines, sorted.

    Per dish, stations at the superellipse's own parameter rather than at even
    steps in y: both the half width and the depth turn fastest at a rim and
    barely at all in the middle, and even steps in the parameter put the
    stations where the turning is. The outermost is KEYPAD_TIP_WIDTH of a half
    axis wide rather than a point, since a degenerate section is what makes a
    loft come back non-manifold; the superellipse's own end is flat to within
    microns over that width, so the blunt tip it leaves is faithful rather than
    a compromise.

    Plus even steps across each neck, and the ends of each neck's floor pieces,
    where the floor's curvature steps. Stations closer than STATION_GAP_MIN
    merge into one, but the two tips stay where they are.
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
            ys.add(recess.cy + dy)
            ys.add(recess.cy - dy)
    for neck in keypad_necks():
        steps = params.KEYPAD_NECK_STATIONS
        ys.update(neck.y0 + (neck.y1 - neck.y0) * i / steps for i in range(steps + 1))
        ys.update(y for piece in neck.floor for y in piece[:2])
    ys = sorted(ys)
    out = [ys[0]]
    for y in ys[1:-1]:
        if y - out[-1] >= STATION_GAP_MIN and ys[-1] - y >= STATION_GAP_MIN:
            out.append(y)
    return out + [ys[-1]]


PROFILE_SAMPLES = 800
"""Points each base station is sampled at to place the profile points."""


@functools.cache
def _profile_u():
    """The u = dx / half width of each profile point, rim to rim, that every
    station uses: KEYPAD_PROFILE_POINTS + 1 values from -1 to 1.

    Half of the points go by arc length and half by how far the floor turns.
    The arc length and the turn at each u are the most any base station has
    there, mirrored about the centerline. One set for every station keeps each
    ruling of the loft at one u, so no patch twists where two stations would
    have placed their points differently."""
    count = PROFILE_SAMPLES
    dense = [math.sin(-math.pi / 2 + math.pi * k / count) for k in range(count + 1)]
    length = [0.0] * count
    turn = [0.0] * (count + 1)
    for y in _base_stations():
        points = _floor_points(y, dense)
        width = max(recess_spine(y).width, SECTION_MIN_WIDTH)
        angles = []
        for k in range(count):
            (xa, _, za), (xb, _, zb) = points[k], points[k + 1]
            length[k] = max(length[k], math.hypot(xb - xa, zb - za) / width)
            angles.append(math.atan2(zb - za, xb - xa))
        for k in range(1, count):
            turn[k] = max(turn[k], abs(angles[k] - angles[k - 1]))
    weight = [
        length[k] / sum(length) + (turn[k] + turn[k + 1]) / sum(turn)
        for k in range(count)
    ]
    weight = [(w + v) / 2 for w, v in zip(weight, reversed(weight))]
    total = [0.0]
    for w in weight:
        total.append(total[-1] + w)
    out = []
    for i in range(1, params.KEYPAD_PROFILE_POINTS):
        target = total[-1] * i / params.KEYPAD_PROFILE_POINTS
        k = bisect.bisect_left(total, target)
        f = (target - total[k - 1]) / (total[k] - total[k - 1])
        out.append(dense[k - 1] + f * (dense[k] - dense[k - 1]))
    return (-1.0, *out, 1.0)


def _floor_points(y, us):
    """[(x, y, z)] of the floor at station y at each u: the built face less the
    softened depth after the lip lift, with no RIM_DEPTH_MIN cut and no
    RIM_LIFT."""
    spine = recess_spine(y)
    width = max(spine.width, SECTION_MIN_WIDTH)
    xs = [centerline_x() + u * width for u in us]
    return [(x, y, face_z(x, y) - _spine_depth(spine, x, y, 0.0)) for x in xs]


FACET_ANGLE = 2.0
"""Largest angle, in degrees, the loft may leave between the normals of two
neighbouring patches across a station, or between two corners of one patch.
recess_stations() halves every span that leaves more."""

STATION_GAP_MIN = 0.025
"""Closest two stations may sit. recess_stations() does not halve a span
shorter than twice this, so no loft face becomes a sliver."""


def _patch_normal(p00, p10, p01, p11, u, v):
    """Unit normal of the ruled patch on four corners at (u, v): u runs from
    p00 to p10 across a station, v from p00 to p01 along y."""
    su = [(1 - v) * (b - a) + v * (d - c) for a, b, c, d in zip(p00, p10, p01, p11)]
    sv = [(1 - u) * (c - a) + u * (d - b) for a, b, c, d in zip(p00, p10, p01, p11)]
    n = (
        su[1] * sv[2] - su[2] * sv[1],
        su[2] * sv[0] - su[0] * sv[2],
        su[0] * sv[1] - su[1] * sv[0],
    )
    size = math.sqrt(sum(c * c for c in n)) or 1.0
    return [c / size for c in n]


def _angle(a, b):
    return math.acos(max(-1.0, min(1.0, sum(p * q for p, q in zip(a, b)))))


def _crease(a, m, b):
    """Largest angle at section m between the patches from a to m and m to b."""
    return max(
        _angle(
            _patch_normal(a[k], a[k + 1], m[k], m[k + 1], 0.5, 1.0),
            _patch_normal(m[k], m[k + 1], b[k], b[k + 1], 0.5, 0.0),
        )
        for k in range(len(m) - 1)
    )


def _twist(a, b):
    """Largest angle between opposite corners of a patch from a to b."""
    worst = 0.0
    for k in range(len(a) - 1):
        corners = (a[k], a[k + 1], b[k], b[k + 1])
        for (u, v), (s, t) in (((0, 0), (1, 1)), ((1, 0), (0, 1))):
            n0 = _patch_normal(*corners, u, v)
            worst = max(worst, _angle(n0, _patch_normal(*corners, s, t)))
    return worst


@functools.cache
def recess_stations():
    """The y values the merged recess is lofted through, sorted.

    It starts from _base_stations(). Then it halves each span whose patches
    crease or twist more than FACET_ANGLE, or that shows such a crease at its
    midpoint. At a station that creases, it halves the spans on both sides.
    The rims, the end roll and the necks bend the floor fastest, so the
    new stations go there. It does not halve a span shorter than twice
    STATION_GAP_MIN.
    """
    ys = _base_stations()
    inner = _profile_u()[1:-1]
    section = functools.lru_cache(maxsize=None)(lambda y: _floor_points(y, inner))
    limit = math.radians(FACET_ANGLE)
    while True:
        split = set()
        for i, (ya, yb) in enumerate(zip(ys, ys[1:])):
            if yb - ya < 2 * STATION_GAP_MIN:
                continue
            a, b = section(ya), section(yb)
            if _twist(a, b) > limit or _crease(a, section((ya + yb) / 2), b) > limit:
                split.add(i)
        for i in range(1, len(ys) - 1):
            if _crease(section(ys[i - 1]), section(ys[i]), section(ys[i + 1])) > limit:
                split.update(
                    j for j in (i - 1, i) if ys[j + 1] - ys[j] >= 2 * STATION_GAP_MIN
                )
        if not split:
            return tuple(ys)
        ys = sorted(set(ys) | {(ys[i] + ys[i + 1]) / 2 for i in split})


SECTION_MIN_WIDTH = 0.01
"""Floor under a station's own half width, so one landing exactly on a rim
still makes a closed wire rather than a line and the loft has something to work
with. recess_stations() keeps every station KEYPAD_TIP_WIDTH of a half axis
clear of a rim, so this never fires on the present layout; it is here so that a
future station list cannot turn a loft into a crash."""


RIM_LIFT = 0.02
"""How far above the built face each station's two rim points sit. The floor
follows the face, so its rim lands on the face itself. The face is curved
and the loft is ruled between stations. Without the lift, the rim edge between
two stations dips a few hundred-thousandths into the shell and leaves a sliver
of rim wall. The lift keeps that edge above the face, so the floor's steep last
facet crosses the face cleanly. The visible rim moves inward by about a
hundredth."""


def _station_floor(y, tip=False):
    """[(x, z)] of the floor curve at one station, rim to rim: the points
    _station_section() closes into a face.

    The floor is the dish alone, face_z() less _spine_depth(), with no rim
    chamfer.
    The two rim points, and every point with no depth under RIM_DEPTH_MIN, are
    held RIM_LIFT above the built face. At a `tip` station, one of the two
    ends of the recess, every point is held there. The points sit at the same
    _profile_u() on every station.

    A tip is only microns deep, and its section is the loft's end cap. Left at
    that depth, the cap cuts a step wall microns high into the face. Where the
    second dish's tip reaches the IR end roll, the face slopes steeply in y,
    and that wall meshed torn. With the tip lifted, the ruled faces from the
    station before it cross the face instead, as the rim faces do."""
    spine = recess_spine(y)
    width = max(spine.width, SECTION_MIN_WIDTH)
    cx = centerline_x()
    us = _profile_u()
    points = []
    for i, u in enumerate(us):
        px = cx + u * width
        face = face_z(px, y)
        depth = _spine_depth(spine, px, y)
        lifted = tip or i in (0, len(us) - 1) or depth <= 0.0
        points.append((px, face + RIM_LIFT if lifted else face - depth))
    return points


def recess_floor_min():
    """(z, x, y) of the lowest point the recess loft is built through.

    The loft is ruled between stations and its sections are polylines, so its
    lowest point is one of these points. It is not always the deepest dish
    centre. The face can put a rim point near a side wall lower than any floor
    under the crown."""
    stations = recess_stations()
    return min(
        (z, x, y)
        for i, y in enumerate(stations)
        for x, z in _station_floor(y, tip=i in (0, len(stations) - 1))
    )


def _station_section(y, tip=False):
    """The merged recess's cross-section at one station, as a face in that
    station's own plane: the floor curve under the recess, carried up the two
    vertical rim walls and closed across MERGE above the crown.

    The floor is the dish's own depth field under the built face, with no
    rim chamfer. The two rim points are held RIM_LIFT above that face.

    The floor's points sit where the floor turns, not at even steps in x. See
    _profile_u().
    """
    points = _station_floor(y, tip)
    top = SHELL_FRONT + MERGE
    points += [(points[-1][0], top), (points[0][0], top)]
    return Face(Wire.make_polygon([(x, y, z) for x, z in points], close=True))


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
    half a metre. The stations are what carry the fidelity in y instead.
    recess_stations() adds them until no two neighbouring patches differ in
    normal by more than FACET_ANGLE, so the faceting does not show near the
    rims. The other axis is a polyline already (KEYPAD_PROFILE_POINTS), so this
    makes the surface a fine polygonal approximation in both directions rather
    than one, which is the honest description of what it always was.

    Every station carries the same points at the same _profile_u(), so the
    loft has a vertex to match at each and nothing to guess.

    backform.py gave up a fitted loft for the same underlying reason, where it
    overshot its sections rather than diverging. Treat one through many sections
    as suspect in this model.
    """
    stations = recess_stations()
    last = len(stations) - 1
    return loft(
        [_station_section(y, i in (0, last)) for i, y in enumerate(stations)],
        ruled=True,
    )


def recess_outline():
    """The merged recess's plan outline, as one closed face in the z=0 plane.

    Built from the same half widths the loft's own sections are, read at the
    same recess_stations(), so the line the FDM front draws in its face is the
    rim the recessed front has there and not an approximation of it. Up the
    right-hand side and back down the left: the field is one interval in x per
    station by construction, which is what makes the outline a single closed
    polygon rather than several loops.

    Nothing clamps it. On the recessed front the rim runs where the face
    already turns down toward the side walls. On the FDM front a small chamfer
    leaves flat face for it.
    Clamping the outline was the other way round and it
    showed: it flat-sided the line over most of its length and carried it into
    the LED ring channel.
    """
    with BuildSketch(Plane.XY) as sketch:
        with BuildLine(Plane.XY):
            Polyline(*_outline_points(), close=True)
        make_face()
    return sketch.sketch.faces()[0]


@functools.cache
def _outline_points():
    """[(x, y)] of the outline polygon, counter-clockwise: up the right-hand
    rim at each recess_stations() station and back down the left."""
    cx = centerline_x()
    rim = [(recess_spine(y).width, y) for y in recess_stations()]
    points = [(cx + width, y) for width, y in rim]
    points += [(cx - width, y) for width, y in reversed(rim)]
    return tuple(points)


@cache.solid
def keypad_outline_groove():
    """The FDM front's face marking: recess_outline() as a shallow slot.

    A true 2D offset either side of the outline rather than the outline's own
    half width moved in x. The two differ wherever the outline turns away from
    the y axis, which is both tips and the outboard flank of every rim, and
    moving x there leaves the slot wider than it was asked for and closes it to
    a filled blob at the tips, where the outline's own width falls under the
    offset. Kind.ARC rounds the outside of a convex turn, which is what a
    constant-width slot around a closed curve is.

    Cut to FDM_OUTLINE_DEPTH and carried MERGE past the face, so the cut
    breaks through the plane rather than leaving a skin of it behind.
    """
    face = recess_outline()
    band = offset(
        face, amount=params.FDM_OUTLINE_W / 2, kind=Kind.ARC
    ) - offset(face, amount=-params.FDM_OUTLINE_W / 2, kind=Kind.ARC)
    groove = extrude(band, amount=params.FDM_OUTLINE_DEPTH + MERGE)
    return Pos(0, 0, FDM_FACE - params.FDM_OUTLINE_DEPTH) * groove


CHAMFER_POINT_GAP = 0.25
"""Longest edge, in mm, on each ring of the chamfer cutter. The floor triangles
follow the chamfer linearly between the points."""

CHAMFER_SKIRT = 0.05
"""How far outside the outline the chamfer cutter's floor reaches, rising
RIM_LIFT above the face there. The floor then crosses the face at the outline
at an angle, so the rim crease is on the outline and no sliver of wall is
left at the rim. The face outside the outline is not cut."""

CHAMFER_RIM_LIFT = 0.001
"""How far above the face the chamfer cutter's floor sits on the outline.

The face is convex upward, so between two outline points it stands up to
0.0001 above the straight edge that joins them. On the face itself, the
skirt dips under the face along those edges and leaves lens-shaped slivers,
and then the cut fails without an error and leaves the face whole. With
this lift the skirt stays above the face. The chamfer then crosses the face
less than 0.01 inside the outline."""

CHAMFER_SLOPE_STEP = 0.005
"""Step, in mm along the inward normal, of the difference that reads the
face's slope at the outline for the top round."""

CHAMFER_ROUND_RINGS = 12
"""Rings of each round of the rim chamfer. The top round's rings run from its
first ring to its end. Each facet of the top round turns less than 5 degrees.
The largest turn is where the first facet meets the second, so more rings do
little there."""

CHAMFER_ROUND_GAP = 0.002
"""How far under the face the top round's first ring sits in each section.

The round leaves the face with the face's own slope, so near its start it
stays within the face's 0.0001 chord bulge. A ring of points there leaves
slivers, and the shell cut then fails without an error and leaves the front
whole. The first ring sits where the round is this far under the face. The
facet from the round's start to it crosses the face at 0.4 to 1.6 degrees,
and it stands less than 0.001 off the round."""

CHAMFER_SEAM_LIFT = 0.001
"""How far above the dish the chamfer cutter's floor crosses the clip wall.

The loft is clipped by a prism on the chamfer's inner ring, so the clip has a
vertical wall there. If the cutter's own inner wall or floor edge stands on
the same points, the fuse or the shell cut fails, and at a 1.0 chamfer the
front lost the whole recess. The cutter's floor therefore crosses the clip
wall at this height, and the chamfer ends in a step this tall. The step is
far under a print layer."""

CHAMFER_SEAM_REACH = 0.004
"""How far past the inner ring the straight chamfer of the cutter's floor
runs, CHAMFER_SEAM_LIFT above the dish. Its points are staggered half a
point gap from the inner ring's points. If a floor edge crossed the clip wall
on one of the wall's vertical edges, the mesh would get zero-area triangles
along the seam."""

CHAMFER_OVERLAP = 0.1
"""How far past the inner ring the chamfer cutter reaches over the dish. Its
floor rises from CHAMFER_SEAM_REACH to CHAMFER_OVERLAP_RISE above the dish,
so it does not touch the dish floor, and its inner wall stands inside the
clipped loft."""

CHAMFER_OVERLAP_RISE = 0.05
"""Height of the chamfer cutter's floor above the dish at its inner wall."""

CHAMFER_TOP_RISE = 0.5
"""How far the chamfer cutter's top stands above the loft's top, so that the
two tops are not coplanar."""


def _segment_foot(segment, x, y):
    """(distance, px, py, s) from (x, y) to its nearest point on one outline
    segment, s the arc length of that point along the outline."""
    ax, ay, bx, by, s, length = segment
    dx, dy = bx - ax, by - ay
    t = ((x - ax) * dx + (y - ay) * dy) / (length * length) if length > 0 else 0.0
    t = min(max(t, 0.0), 1.0)
    px, py = ax + t * dx, ay + t * dy
    return math.hypot(x - px, y - py), px, py, s + t * length


@functools.cache
def _outline_segments():
    """((ax, ay, bx, by, s, length), ...) round the outline polygon, with s the
    arc length at each segment's start."""
    points = _outline_points()
    out, s = [], 0.0
    for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
        length = math.hypot(bx - ax, by - ay)
        out.append((ax, ay, bx, by, s, length))
        s += length
    return tuple(out)


def _offset_ring(amount, z_at, phase=0.0):
    """[(x, y, z, s)] the true 2D offset of the outline by `amount`, out when
    positive, each edge cut to CHAMFER_POINT_GAP, counter-clockwise and
    starting at its least s. z is z_at(x, y, px, py) with (px, py) the nearest
    outline point, and s is that point's arc length. A phase of 0.5 puts each
    point half a step along its edge."""
    faces = offset(recess_outline(), amount=amount, kind=Kind.ARC).faces()
    if len(faces) != 1 or faces[0].inner_wires():
        raise ValueError(
            f"the outline offset {amount:.2f} is not one simple loop, so "
            "RECESS_CHAMFER_W is too wide for the recess"
        )
    plan = []
    for edge in faces[0].outer_wire().order_edges():
        count = max(1, math.ceil(edge.length / CHAMFER_POINT_GAP))
        for i in range(count):
            point = edge.position_at((i + phase) / count)
            if not plan or math.dist(plan[-1], (point.X, point.Y)) > 1e-6:
                plan.append((point.X, point.Y))
    if math.dist(plan[0], plan[-1]) <= 1e-6:
        plan.pop()
    area = sum(
        ax * by - bx * ay for (ax, ay), (bx, by) in zip(plan, plan[1:] + plan[:1])
    )
    if area < 0.0:
        plan.reverse()
    segments = _outline_segments()
    ring = []
    for x, y in plan:
        _, px, py, s = min(_segment_foot(segment, x, y) for segment in segments)
        ring.append((x, y, z_at(x, y, px, py), s))
    start = min(range(len(ring)), key=lambda i: ring[i][3])
    ring = ring[start:] + ring[:start]
    for a, b in zip(ring, ring[1:]):
        if b[3] < a[3] - 1e-9:
            raise ValueError(
                f"the outline offset {amount:.2f} turns back along the outline "
                f"near ({b[0]:.2f}, {b[1]:.2f})"
            )
    return ring


@functools.lru_cache(maxsize=None)
def _station_points(i):
    """The loft's floor points at station i, as _station_floor() gives them."""
    stations = recess_stations()
    return _station_floor(stations[i], tip=i in (0, len(stations) - 1))


def _loft_z(x, y):
    """The z of the built loft's floor over (x, y). Each loft face is ruled
    between the same edge of two neighbouring stations, so at a given y it is
    a straight line between the two stations' points, and x places the point
    on it."""
    stations = recess_stations()
    i = min(max(bisect.bisect_right(stations, y) - 1, 0), len(stations) - 2)
    v = (y - stations[i]) / (stations[i + 1] - stations[i])
    a, b = _station_points(i), _station_points(i + 1)
    for (ax0, az0), (ax1, az1), (bx0, bz0), (bx1, bz1) in zip(a, a[1:], b, b[1:]):
        x0, x1 = ax0 + v * (bx0 - ax0), ax1 + v * (bx1 - ax1)
        if x0 <= x <= x1 and x1 > x0:
            u = (x - x0) / (x1 - x0)
            z0, z1 = az0 + v * (bz0 - az0), az1 + v * (bz1 - az1)
            return z0 + u * (z1 - z0)
    raise ValueError(f"({x:.2f}, {y:.2f}) is not over the recess loft's floor")


def _rim_section(px, py, nx, ny):
    """z(t), the rim chamfer's section at t in from outline point (px, py)
    along the inward normal (nx, ny). t is negative outside the outline.

    The top round is a parabola from RECESS_CHAMFER_ROUND_OUT outside the
    outline, where it leaves the face with the face's slope, to
    RECESS_CHAMFER_ROUND_W inside it. For RECESS_CHAMFER_INNER_ROUND_W before
    RECESS_CHAMFER_W it is a second parabola that meets the loft's floor there
    with the floor's slope. Between them it is straight, tangent to both. If
    the two rounds fill the width, the section is one S-curve. Past
    RECESS_CHAMFER_W it runs on, tangent. The start point stands
    CHAMFER_RIM_LIFT above the face."""
    width, out = params.RECESS_CHAMFER_W, params.RECESS_CHAMFER_ROUND_OUT
    top, inner = params.RECESS_CHAMFER_ROUND_W, params.RECESS_CHAMFER_INNER_ROUND_W
    if top < 0.0 or inner < 0.0 or out < 0.0 or top + inner > width:
        raise ValueError(
            f"RECESS_CHAMFER_ROUND_W {top:.2f}, RECESS_CHAMFER_INNER_ROUND_W "
            f"{inner:.2f} and RECESS_CHAMFER_ROUND_OUT {out:.2f} must not be "
            "negative, and the two rounds inside the outline must not be wider "
            f"than RECESS_CHAMFER_W, {width:.2f}"
        )
    step = CHAMFER_SLOPE_STEP
    sx, sy = px - out * nx, py - out * ny
    z0 = face_z(sx, sy) + CHAMFER_RIM_LIFT
    zw = _loft_z(px + width * nx, py + width * ny)
    face_slope = (face_z(sx + step * nx, sy + step * ny) - face_z(sx, sy)) / step
    dish = _loft_z(px + (width + step) * nx, py + (width + step) * ny)
    dish_slope = (dish - zw) / step
    span, reach = width + out, top + out
    slope = (zw - z0 - dish_slope * inner / 2 - face_slope * reach / 2) / (
        span - (reach + inner) / 2
    )
    z_top = z0 + (face_slope + slope) * reach / 2

    def z(t):
        u = t + out
        if u < reach:
            return z0 + u * (face_slope + (slope - face_slope) * u / (2 * reach))
        if t >= width:
            return zw + (dish_slope if inner else slope) * (t - width)
        if t > width - inner:
            v = width - t
            return zw - v * (dish_slope + (slope - dish_slope) * v / (2 * inner))
        return z_top + slope * (u - reach)

    return z


def _round_rings(base):
    """(start, rings): the ring where the top round leaves the face, and the
    rings of the two rounds, each a list of (x, y, z, s) with one point for
    each outline point in `base`.

    Each section marches along its own normal from its outline point. The
    start ring is RECESS_CHAMFER_ROUND_OUT outside the outline. The top
    round's CHAMFER_ROUND_RINGS rings run from where it is CHAMFER_ROUND_GAP
    under the face to RECESS_CHAMFER_ROUND_W in. The inner round's rings start
    RECESS_CHAMFER_INNER_ROUND_W before RECESS_CHAMFER_W, or one step after
    the top round's last ring if that is the same place, and stop one step
    short of RECESS_CHAMFER_W. s is the outline point's own s."""
    width, out = params.RECESS_CHAMFER_W, params.RECESS_CHAMFER_ROUND_OUT
    top, inner = params.RECESS_CHAMFER_ROUND_W, params.RECESS_CHAMFER_INNER_ROUND_W
    steps = CHAMFER_ROUND_RINGS
    inner_ts = []
    if inner > 0.0:
        begin = width - inner
        first = 0 if begin > top + 1e-9 else 1
        inner_ts = [begin + inner * j / steps for j in range(first, steps)]
    rounded = top + out > 0.0
    start = []
    rings = [[] for _ in range((steps if rounded else 0) + len(inner_ts))]
    count = len(base)
    for i, (px, py, s) in enumerate(base):
        ax, ay, _ = base[i - 1]
        bx, by, _ = base[(i + 1) % count]
        length = math.hypot(bx - ax, by - ay)
        nx, ny = (ay - by) / length, (bx - ax) / length
        section = _rim_section(px, py, nx, ny)
        start.append((px - out * nx, py - out * ny, section(-out), s))
        ts = []
        if rounded:

            def under(t):
                return face_z(px + t * nx, py + t * ny) - section(t)

            if under(top) < CHAMFER_ROUND_GAP:
                raise ValueError(
                    f"the top round ends less than {CHAMFER_ROUND_GAP} under "
                    f"the face near ({px:.2f}, {py:.2f}), so "
                    "RECESS_CHAMFER_ROUND_W is too narrow"
                )
            lo, hi = -out, top
            for _ in range(30):
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if under(mid) >= CHAMFER_ROUND_GAP else (mid, hi)
            ts = [hi + (top - hi) * j / (steps - 1) for j in range(steps)]
        for ring, t in zip(rings, ts + inner_ts):
            ring.append((px + t * nx, py + t * ny, section(t), s))
    return start, rings


@functools.cache
def _chamfer_rings():
    """(outer, rounds, inner, skirt), the rings of the chamfer's floor, each a
    list of (x, y, z, s), counter-clockwise from the same place.

    The outer ring is where the top round leaves the face, CHAMFER_RIM_LIFT
    above it, RECESS_CHAMFER_ROUND_OUT outside the outline polygon, one point
    for each outline point at CHAMFER_POINT_GAP. rounds are _round_rings().
    The inner ring is the true 2D offset of the outline RECESS_CHAMFER_W in,
    on the loft's own floor, so the chamfer meets the dish there. The skirt is
    the offset CHAMFER_SKIRT past the outer ring, RIM_LIFT above the face
    there and at the outer ring. s is the arc length of each point's nearest
    outline point."""
    base = []
    for ax, ay, bx, by, s, length in _outline_segments():
        count = max(1, math.ceil(length / CHAMFER_POINT_GAP))
        for i in range(count):
            t = i / count
            base.append((ax + t * (bx - ax), ay + t * (by - ay), s + t * length))
    outer, rounds = _round_rings(base)
    inner = _offset_ring(
        -params.RECESS_CHAMFER_W, lambda x, y, px, py: _loft_z(x, y)
    )
    out = params.RECESS_CHAMFER_ROUND_OUT
    reach = out + CHAMFER_SKIRT

    def skirt_z(x, y, px, py):
        sx, sy = px + (x - px) * out / reach, py + (y - py) * out / reach
        return max(face_z(x, y), face_z(sx, sy)) + RIM_LIFT

    return outer, rounds, inner, _offset_ring(reach, skirt_z)


def _strip(outer, inner):
    """[(a, b, c)] the triangles between two rings, outer around inner.

    The two rings advance together in s, one point at a time on whichever ring
    is behind, so each triangle spans one ring edge and one point of the
    other ring, and every triangle is planar. Each must turn counter-clockwise
    in plan, or the strip has folded over itself."""
    total = sum(segment[5] for segment in _outline_segments())
    n_out, n_in = len(outer), len(inner)
    i = j = 0
    triangles = []
    while i < n_out or j < n_in:
        s_out = outer[i + 1][3] if i + 1 < n_out else total + outer[0][3]
        s_in = inner[j + 1][3] if j + 1 < n_in else total + inner[0][3]
        if i < n_out and (j >= n_in or s_out <= s_in):
            triangles.append((outer[i], outer[(i + 1) % n_out], inner[j % n_in]))
            i += 1
        else:
            triangles.append((outer[i % n_out], inner[(j + 1) % n_in], inner[j]))
            j += 1
    for a, b, c in triangles:
        turn = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if turn <= 0.0:
            raise ValueError(
                f"the chamfer floor folds near ({a[0]:.2f}, {a[1]:.2f}): its "
                "rings do not advance together"
            )
    return triangles


def _index_strip(outer, inner):
    """[(a, b, c)] the triangles between two rings with one point each for the
    same outline points, two triangles between each pair of neighbours. Each
    must turn counter-clockwise in plan, or the strip has folded."""
    count = len(outer)
    triangles = []
    for i in range(count):
        k = (i + 1) % count
        triangles.append((outer[i], outer[k], inner[i]))
        triangles.append((outer[k], inner[k], inner[i]))
    for a, b, c in triangles:
        turn = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if turn <= 0.0:
            raise ValueError(
                f"the rim chamfer's rounds fold near ({a[0]:.2f}, {a[1]:.2f}): "
                "they reach too far in for the outline's curves"
            )
    return triangles


def _rim_floor(outer, rounds, last):
    """The floor triangles from the outer ring through the top round's rings
    to the ring `last`."""
    rings = [outer, *rounds]
    triangles = []
    for a, b in zip(rings, rings[1:]):
        triangles += _index_strip(a, b)
    return triangles + _strip(rings[-1], last)


@functools.cache
def _chamfer_floor():
    """The chamfer's own triangles, from the outline through the top round to
    the inner ring."""
    outer, rounds, inner, _ = _chamfer_rings()
    return tuple(_rim_floor(outer, rounds, inner))


def _polygon_face(points):
    return Face(Wire.make_polygon([p[:3] for p in points], close=True))


def _seam_z(x, y, px, py):
    """z of the chamfer cutter's floor just past the inner ring: the straight
    chamfer run on, or the dish if that is higher, CHAMFER_SEAM_LIFT up."""
    t = math.hypot(x - px, y - py)
    section = _rim_section(px, py, (x - px) / t, (y - py) / t)
    return max(section(t), _loft_z(x, y)) + CHAMFER_SEAM_LIFT


@cache.solid
def keypad_chamfer():
    """The rim chamfer cutter: the column over the strip from the skirt to
    CHAMFER_OVERLAP past the chamfer's inner ring, from its floor up to
    CHAMFER_TOP_RISE over the loft's top.

    Outside the outline the floor is the skirt strip, which stays above the
    face. From the outline it is the rim section, as _chamfer_floor() has it,
    but it runs on past the inner ring to the seam ring and crosses the clip
    wall CHAMFER_SEAM_LIFT above the dish. The floor then rises clear of the dish
    to the inner wall. Both walls are vertical and the top is flat. Raises
    when RECESS_CHAMFER_W is zero."""
    if params.RECESS_CHAMFER_W <= 0.0:
        raise ValueError("RECESS_CHAMFER_W is zero, so there is no chamfer")
    outer, rounds, _, skirt = _chamfer_rings()
    seam = _offset_ring(
        -(params.RECESS_CHAMFER_W + CHAMFER_SEAM_REACH), _seam_z, phase=0.5
    )
    wall = _offset_ring(
        -(params.RECESS_CHAMFER_W + CHAMFER_OVERLAP),
        lambda x, y, px, py: _loft_z(x, y) + CHAMFER_OVERLAP_RISE,
    )
    top = SHELL_FRONT + MERGE + CHAMFER_TOP_RISE
    floor = [*_strip(skirt, outer), *_rim_floor(outer, rounds, seam)]
    faces = [_polygon_face(t) for t in (*floor, *_strip(seam, wall))]
    for ring in (skirt, wall):
        for a, b in zip(ring, ring[1:] + ring[:1]):
            faces.append(
                _polygon_face([a, b, (b[0], b[1], top), (a[0], a[1], top)])
            )
    faces.append(
        Face(
            Wire.make_polygon([(p[0], p[1], top) for p in skirt], close=True),
            [Wire.make_polygon([(p[0], p[1], top) for p in wall], close=True)],
        )
    )
    chamfer = Solid(Shell(faces))
    if not chamfer.is_valid or chamfer.volume <= 0.0:
        raise ValueError("the chamfer cutter did not close into a valid solid")
    return chamfer


def _chamfer_prism():
    """The column over the chamfer's inner ring, through the whole height of
    the recess loft. The chamfer cutter's floor crosses its walls."""
    _, _, inner, _ = _chamfer_rings()
    box = keypad_recess().bounding_box()
    z0, z1 = box.min.Z - 1.0, box.max.Z + 1.0
    base = Face(Wire.make_polygon([(p[0], p[1], z0) for p in inner], close=True))
    return extrude(base, amount=z1 - z0, dir=(0, 0, 1))


@cache.solid
def keypad_recess_cut():
    """What the recessed front cuts for its recess: the loft, keypad_recess(),
    kept inside the chamfer's inner ring, fused with the rim chamfer cutter,
    keypad_chamfer().

    Between the outline and that ring the surface is the chamfer: the top
    round from the face, any straight section, and the inner round into the
    dish floor (_rim_section()). Inside
    the ring the dish does not change, and neither do the loft and the
    outline. With RECESS_CHAMFER_W at zero it is the loft alone."""
    if params.RECESS_CHAMFER_W <= 0.0:
        return keypad_recess()
    return _fuse(_isect(keypad_recess(), _chamfer_prism()), keypad_chamfer())


def outline_length():
    """Length of the outline's own centreline, for a pass that wants the mean
    width the built groove came out as rather than the one it was asked for."""
    return recess_outline().outer_wire().length


def keypad_recess_facts():
    """What the merged recess came out as: one entry per dish and one per neck,
    plus how close the whole thing comes to the exterior wall.

    Shared by case.py's summary print and check.py's guards, so both read the
    same numbers rather than each re-deriving them.
    """
    ex0, ex1 = exterior_x_bounds()
    cx = centerline_x()
    parts = board.components()
    out = {"dishes": {}, "necks": {}}
    for name, recess in keypad_recesses().items():
        depths = [
            face_depth_at(*parts[ref][:2]) for ref in island_refs(name)
        ] if name != "wheel" else []
        out["dishes"][name] = {
            "center": (cx, recess.cy),
            "half": (recess.ax, recess.ay),
            "depth": recess.depth,
            "n": recess.n,
            "key_depths": (min(depths), max(depths)) if depths else None,
        }
    for neck in keypad_necks():
        out["necks"][neck.name] = {
            "reach": neck.reach,
            "span": (neck.y0, neck.y1),
            "waist": neck_waist(neck),
            "radius": neck_radius(neck),
            "floor": min(face_depth_at(cx, y) for y, _ in _neck_walk(neck)),
            "ends": (neck.ends[0].width, neck.ends[2].width),
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
    """The stiffened wall, inset by PAD_FIT: what each lobe is clipped inside.

    Active on both lobes, whose key rectangles reach past it at the long
    sides. Taken off STIFFENED_WALL everywhere, so the plain IR end keeps a
    wider gap than PAD_FIT."""
    wall = _offset_face(STIFFENED_WALL)
    return Face(wall.outer_wire().offset_2d(-params.PAD_FIT, kind=Kind.INTERSECTION))


def _mic_clearance_radius():
    """Radius of the mic duct's open-edge clearance circle, shared by the 2D
    lobe outline and the 3D `_mic_clearance()` cut so the two cannot drift."""
    return mic_duct_or() + params.STANDOFF_CHAMFER + params.PAD_MIC_CLEARANCE


def pad_lobe_face(name):
    """The lobe's rounded rectangle, clipped inside the stiffened wall.

    The mic lobe also loses the mic clearance circle, and the two corners
    where that circle meets the top edge take PAD_JOIN_RADIUS."""
    x0, y0, x1, y1 = next(box[1:] for box in pad_lobes() if box[0] == name)
    with BuildSketch() as sketch:
        with Locations(((x0 + x1) / 2, (y0 + y1) / 2)):
            RectangleRounded(x1 - x0, y1 - y0, params.PAD_RADIUS)
    contour = sketch.sketch.faces()[0]
    if name == "second":
        mx, my = mic_port()
        radius = _mic_clearance_radius()
        with BuildSketch() as notch:
            with Locations((mx, my)):
                Circle(radius)
        contour = contour - notch.sketch.faces()[0]
        corners = [
            vertex for vertex in contour.vertices()
            if abs(vertex.Y - y1) < 1e-6 and abs(vertex.X - mx) < radius + 0.1
        ]
        contour = contour.fillet_2d(params.PAD_JOIN_RADIUS, corners)
    clipped = extrude(contour, amount=1, dir=(0, 0, 1)) & extrude(
        _pad_limit(), amount=1, dir=(0, 0, 1)
    )
    return clipped.faces().sort_by()[0]


def _grid_axes(axis):
    """Ordered grid row or column coordinates, read from SW3 through SW11.

    SW4 and SW7 are slightly off their nominal column or row. Group positions
    within 0.1 mm so each physical grid line still produces one coordinate.
    """
    index = 0 if axis == "x" else 1
    values = sorted(board.components()[ref][index] for ref in island_refs("grid"))
    groups = []
    for value in values:
        if not groups or value - groups[-1][-1] > 0.1:
            groups.append([value])
        else:
            groups[-1].append(value)
    if len(groups) != 3:
        raise ValueError(f"nine-button grid has {len(groups)} {axis} lines, not three")
    return [sum(group) / len(group) for group in groups]


def _pad_groove_specs():
    """FDM isolation-groove plan data derived from the nine switch coordinates.

    Each tuple is (orientation, centre, run0, run1). A vertical groove runs
    along Y between adjacent switch columns. A horizontal groove runs along X
    between adjacent switch rows. Only the grid lobe appears here.
    """
    _, x0, y0, x1, y1 = next(box for box in pad_lobes() if box[0] == "grid")
    columns = _grid_axes("x")
    rows = _grid_axes("y")
    edge = -params.FDM_PAD_GROOVE_EDGE_OVERTRAVEL
    return tuple(
        ("vertical", (a + b) / 2, y0 + edge, y1 - edge)
        for a, b in zip(columns, columns[1:])
    ) + tuple(
        ("horizontal", (a + b) / 2, x0 + edge, x1 - edge)
        for a, b in zip(rows, rows[1:])
    )


def _pad_grooves():
    """Rounded flat-bottom FDM cuts for each grid centreline, from the keytop face only.

    The plunger face stays flat for supports.
    """
    width = params.FDM_PAD_GROOVE_W
    depth = params.FDM_PAD_GROOVE_DEPTH
    if width <= 0 or depth <= 0:
        raise ValueError("pad groove width and depth must be positive")
    if depth >= params.PAD_WEB_T:
        raise ValueError("FDM pad groove depth leaves no web")
    chamfer = params.FDM_PAD_GRID_CHAMFER
    if not 0 < chamfer <= depth:
        raise ValueError("FDM pad groove chamfer must be positive and at most the groove depth")
    cuts = []
    for orientation, centre, run0, run1 in _pad_groove_specs():
        length = run1 - run0
        if length <= width:
            raise ValueError("pad groove edge treatment leaves no groove run")
        x, y = ((centre, (run0 + run1) / 2) if orientation == "vertical"
                else ((run0 + run1) / 2, centre))
        size_x, size_y = ((width, length) if orientation == "vertical"
                          else (length, width))
        with BuildSketch() as sketch:
            with Locations((x, y)):
                # build123d requires a radius strictly below half the narrow
                # dimension. One micron preserves the intended semicircle.
                RectangleRounded(size_x, size_y, width / 2 - 0.001)
        face = sketch.sketch.faces()[0]
        cut = _slab(face, PAD_WEB_TOP - depth, PAD_WEB_TOP + MERGE)
        # Negative taper grows the slot 1 mm per 1 mm of height (45 degrees).
        flare = extrude(Pos(0, 0, PAD_WEB_TOP - chamfer) * face,
                        amount=chamfer + MERGE, taper=-45)
        cuts.append(_fuse(cut, flare))
    return cuts


def _stem(ref):
    """The soft stem a cap sits over, raised out of the pad where a keytop was.

    Square rather than round, because the legend on the cap has an orientation
    and a round stem holds none. It starts inside the web rather than on it, so
    it merges into one solid, and it reaches the socket ceiling, so a press
    drives through the stem rather than through the flange.

    A plain prism, no barb. The flange retains the cap now, and a barb would put
    an undercut on every stem in a moulded pad while fighting the blind assembly
    that seats nine of them at once.

    It stops at stem_top(ref), so a stem under a lower cap in an outer column is
    shorter by the same value.
    """
    x, y = board.components()[ref][:2]
    return _rounded_prism(
        x, y, params.STEM_W, params.STEM_R, PAD_WEB_BOTTOM, stem_top(ref)
    )


def fdm_cap_body(ref):
    """Side of an integrated FDM keytop."""
    flange = key_size(ref) - 2 * params.CAP_FLANGE_TRIM
    face_hole = flange - 2 * params.CAP_FLANGE_OVERLAP
    return face_hole - 2 * params.FDM_CAP_GUIDE_CLEARANCE


def fdm_keycap_bottom():
    """Bottom of each integrated FDM keytop, flush with its lobe web."""
    return PAD_WEB_TOP


def fdm_keycap(ref, legend=True):
    """One solid keytop for the FDM pad, fused across its lobe web.

    It keeps the normal cap's visible superellipse, exposed-top fillet, and
    debossed legend, but it has no flange or socket. Its bottom is flush with
    the web, which removes the cap-to-stem step. The keytops stop short of the
    grid grooves, so each button still has independent flex. `legend=False`
    leaves the top blank for geometry checks.
    """
    x, y = board.components()[ref][:2]
    body = _squircle_prism(
        x,
        y,
        fdm_cap_body(ref),
        params.KEY_SQUIRCLE_N,
        params.KEY_SQUIRCLE_POINTS,
        fdm_keycap_bottom(),
        cap_top(ref),
    )
    top_edges = [
        edge
        for edge in body.edges()
        if edge.bounding_box().min.Z > cap_top(ref) - 0.01
    ]
    if not top_edges:
        raise ValueError(f"{ref}'s FDM keytop has no top perimeter edges to fillet")
    body = fillet(top_edges, params.CAP_TOP_FILLET)
    marks = legend_solids(ref, x, y) if legend else []
    return _cut(body, *marks)


def _mic_clearance():
    """Open-edge clearance around the mic duct's widest ceiling chamfer."""
    x, y = mic_port()
    return _hole(x, y, 2 * _mic_clearance_radius(), PAD_SKIRT_BOTTOM - 1, PAD_WEB_TOP + 1)


def plunger(x, y, contact=SWITCH_TOP, extension=params.PLUNGER_SWITCH_EXTENSION):
    """Build one plunger with a 45 degree lower-edge chamfer and flat contact.

    `contact` is the switch top it engages and `extension` how far it reaches
    below it. The V2 top pad's nibs pass LEGACY_SWITCH_TOP and
    LEGACY_NIB_EXTENSION, so they engage a V2 switch by a shorter extension.
    """
    z0 = contact - extension
    size = params.PLUNGER_LOWER_CHAMFER
    radius = params.PLUNGER_D / 2
    if size <= 0 or size >= radius or size >= PAD_WEB_TOP - z0:
        raise ValueError("plunger lower chamfer must leave a flat contact and upper shaft")
    contact_radius = radius - size
    chamfer = Pos(x, y, z0 + size / 2) * Cone(
        bottom_radius=contact_radius,
        top_radius=radius,
        height=size,
    )
    shaft = _hole(x, y, params.PLUNGER_D, z0 + size, PAD_WEB_TOP)
    return _fuse(chamfer, shaft)


@functools.cache
def _skirt_ring(name, bottom=PAD_SKIRT_BOTTOM):
    """The moulded skirt before any break: lobe outline less its PAD_SKIRT_T inset."""
    face = pad_lobe_face(name)
    inner = Face(face.outer_wire().offset_2d(-params.PAD_SKIRT_T, kind=Kind.ARC))
    return _cut(
        _slab(face, bottom, PAD_WEB_BOTTOM + MERGE),
        _slab(inner, bottom - 1, PAD_WEB_BOTTOM + MERGE + 1),
    )


@functools.cache
def _v3_skirt_obstacles():
    """[(ref, solid)] every V3 assembly solid under its STEP component reference."""
    return [
        (ref, solid)
        for ref, solids in sorted(board.placement_groups().items())
        for solid in solids
    ]


def _skirt_breaks(name, obstacles, bottom):
    """[(ref, box)] cuts that open a skirt of the given `bottom` over each of
    `obstacles`, a list of (ref, solid)."""
    clear = params.PAD_SKIRT_CLEARANCE
    ring = _skirt_ring(name, bottom)
    ring_box = ring.bounding_box()
    groups = {}
    for ref, solid in obstacles:
        box = solid.bounding_box()
        if box.max.Z <= bottom - clear:
            continue
        if (box.max.X + clear < ring_box.min.X or box.min.X - clear > ring_box.max.X
                or box.max.Y + clear < ring_box.min.Y or box.min.Y - clear > ring_box.max.Y):
            continue
        reach = Pos((box.min.X + box.max.X) / 2, (box.min.Y + box.max.Y) / 2, 0) * Box(
            box.max.X - box.min.X + 2 * clear,
            box.max.Y - box.min.Y + 2 * clear,
            100,
        )
        hit = ring.intersect(reach)
        if hit is None or not hit.solids():
            continue
        groups.setdefault(ref, []).append(box)
    z0, z1 = bottom - 1, PAD_WEB_BOTTOM + MERGE + 1
    out = []
    for ref in sorted(groups):
        boxes = groups[ref]
        lo_x = min(b.min.X for b in boxes) - clear
        hi_x = max(b.max.X for b in boxes) + clear
        lo_y = min(b.min.Y for b in boxes) - clear
        hi_y = max(b.max.Y for b in boxes) + clear
        out.append((ref, Pos((lo_x + hi_x) / 2, (lo_y + hi_y) / 2, (z0 + z1) / 2)
                    * Box(hi_x - lo_x, hi_y - lo_y, z1 - z0)))
    return out


def pad_skirt_breaks(name):
    """[(ref, box)] cuts that open the skirt over each board part it would touch.

    A part counts if its top is above PAD_SKIRT_BOTTOM less PAD_SKIRT_CLEARANCE
    and its plan box, grown by PAD_SKIRT_CLEARANCE, reaches the skirt. One box
    per nearest placement, over all of that part's solids.
    """
    return _skirt_breaks(name, _v3_skirt_obstacles(), PAD_SKIRT_BOTTOM)


def pad_skirt(name):
    """The moulded lobe's skirt: a PAD_SKIRT_T wall flush with the lobe outline.

    It drops from the web to PAD_SKIRT_BOTTOM, level with the plungers, and is
    cut open over each board part before it fuses to the web. The moulded and
    TPU pads share it.
    """
    return _cut(_skirt_ring(name), *(box for _, box in pad_skirt_breaks(name)))


@functools.cache
def legacy_skirt_obstacles():
    """[(ref, solid)] what the V2 top pad's skirt must clear, in the case frame
    with the V2 board in place: the V3 body of each V2 top-side part moved to
    its V2 placement and dropped SUPPORT_GAP.

    Every V2 part on the top side that has a V3 body is moved. The break rule
    then keeps only those that reach the second lobe's skirt.
    """
    legacy = board.legacy_components()
    out = []
    for ref in sorted(board.placement_groups()):
        if ref not in legacy or legacy[ref][3] != "top":
            continue
        for solid in board.legacy_part_solids(ref):
            out.append((ref, Pos(0, 0, -params.SUPPORT_GAP) * solid))
    return out


def legacy_pad_skirt():
    """The second lobe's skirt for the V2 top pad: bottom level with the V3
    pad's skirt (PAD_SKIRT_BOTTOM), broken over the V2 obstacles."""
    return _cut(
        _skirt_ring("second", PAD_SKIRT_BOTTOM),
        *(box for _, box in legacy_skirt_breaks()),
    )


def legacy_skirt_breaks():
    """[(name, box)] the V2 top pad's skirt breaks, by the same rule as
    pad_skirt_breaks over legacy_skirt_obstacles()."""
    return _skirt_breaks("second", legacy_skirt_obstacles(), PAD_SKIRT_BOTTOM)


@cache.solid
def button_pad(fdm=False, skirt=None, grooves=True, legend=True, v2=False):
    """Build two pad lobes supported by their switch plungers.

    The mic lobe is a full rounded rectangle with the mic clearance circle cut from its top edge.
    Both lobes stop outside the wheel clearance band. With fdm=True, the
    printed keytops and legends are fused to their lobe webs in this export.
    `skirt` adds the perimeter skirt and defaults to the moulded pad only.
    `grooves` applies only when `fdm` is true; False gives the FDM pad a plain grid web with no grooves and no edge chamfer.
    `legend` False leaves every printed keytop blank. `v2` swaps the second lobe for `legacy_top_pad`, so one part fits a V2 board.
    """
    return _fuse(
        *(
            legacy_top_pad(skirt=bool(skirt), fdm=fdm, legend=legend)
            if v2 and name == "second"
            else _pad_lobe(name, fdm, skirt=skirt, grooves=grooves, legend=legend)
            for name, *_ in pad_lobes()
        )
    )


def _pad_lobe(
    name,
    fdm,
    nibs=(),
    plunger_extension=params.PLUNGER_SWITCH_EXTENSION,
    skirt=None,
    grooves=True,
    skirt_part=None,
    legend=True,
):
    """Build one pad lobe. Each (x, y) in `nibs` adds a plunger to a V2 switch.

    `skirt` None means a skirt only when `fdm` is false. `skirt_part` replaces
    the lobe's own skirt solid. `plunger_extension` is how far each of the lobe's own
    plungers reaches below SWITCH_TOP. `grooves` applies only when `fdm` is true.
    `legend` False leaves the printed keytops blank.
    """
    parts = board.components()
    x0, y0, x1, y1 = next(box[1:] for box in pad_lobes() if box[0] == name)
    body = _slab(pad_lobe_face(name), PAD_WEB_BOTTOM, PAD_WEB_TOP)
    skirt = not fdm if skirt is None else skirt
    if fdm and grooves and name == "grid":
        c = params.FDM_PAD_GRID_CHAMFER
        face = pad_lobe_face(name)
        body = _fuse(
            _slab(face, PAD_WEB_BOTTOM, PAD_WEB_TOP - c),
            # The lobe face points -Z, so the taper needs an explicit +Z.
            extrude(Pos(0, 0, PAD_WEB_TOP - c) * face, amount=c, dir=(0, 0, 1), taper=45),
        )
    if skirt:
        body = _fuse(body, pad_skirt(name) if skirt_part is None else skirt_part)
    raised = []
    for ref in island_refs(name):
        x, y = parts[ref][:2]
        raised.append(_stem(ref))
        raised.append(plunger(x, y, extension=plunger_extension))
        if fdm:
            raised.append(fdm_keycap(ref, legend=legend))
    raised.extend(
        plunger(x, y, LEGACY_SWITCH_TOP, params.LEGACY_NIB_EXTENSION)
        for x, y in nibs
    )
    cuts = []
    if name == "second":
        cuts.append(_mic_clearance())
    elif fdm and grooves:
        cuts.extend(_pad_grooves())
    return _cut(_fuse(body, *raised), *cuts)


@cache.solid
def legacy_top_pad(skirt=False, fdm=True, legend=True):
    """Build the pad's SW1/SW2 lobe for a V2 board only.

    It keeps the V3 plungers and adds one nib at each V2 switch, which sits
    further -Y and lower, on the back ledges. Nibs and kept plungers both
    extend LEGACY_NIB_EXTENSION below their own switch top, so the plungers
    stay SUPPORT_GAP above the nibs.
    `skirt` adds the one-piece TPU pad's skirt, ending level with the V3 pad's
    skirt (PAD_SKIRT_BOTTOM) and broken over the V2 parts. With `fdm` false the lobe is the
    moulded pad's: plain web, stems for the separate caps, no fused keytops.
    `legend` False leaves the fused keytops blank.
    """
    legacy = board.legacy_components()
    nibs = [legacy[ref][:2] for ref in island_refs("second")]
    return _pad_lobe(
        "second",
        fdm=fdm,
        nibs=nibs,
        plunger_extension=params.LEGACY_NIB_EXTENSION,
        skirt=skirt,
        skirt_part=legacy_pad_skirt() if skirt else None,
        legend=legend,
    )
