"""The z stack and the derived radii every feature is built from.

One module because these are the constants the rest of the package agrees on:
the cavity ceilings and floors, the wheel's measured profile and the ring radii
that come off it, the lap and skirt planes, and MERGE. Nothing here imports
another model module, so nothing in the package can end up in an import cycle
through a constant.
"""

import functools
import math
from pathlib import Path

import board
import params

HERE = Path(__file__).resolve().parent.parent
EXPORT = HERE / "export"

BOARD_TOP = params.BOARD_THICKNESS
CAVITY_BACK = -params.BACK_KEEPOUT
SHELL_BACK = CAVITY_BACK - params.FLOOR

SWITCH_TOP = BOARD_TOP + params.SWITCH_HEIGHT

SUPPORT_TOP = -params.SUPPORT_GAP
"""Top of the back shell's support ledges, the plane under the board. Here
rather than in support.py so hardware.py can build to the same plane without
importing the module that imports it."""

LEGACY_BOARD_TOP = SUPPORT_TOP + params.BOARD_THICKNESS
"""Top face of a V2 board. A V2 board rests on the back ledges at SUPPORT_TOP,
so it sits SUPPORT_GAP lower than V3's BOARD_TOP, where the front ledges bear
on a V3 board."""

LEGACY_SWITCH_TOP = LEGACY_BOARD_TOP + params.SWITCH_HEIGHT
"""A V2 switch's actuator top, the SWITCH_TOP of a board resting on the back ledges.
The V2 top pad's nibs are built down to this."""

KEYPAD_KEEPOUT = params.SWITCH_HEIGHT + params.KEYPAD_PLUNGER_STUB
"""Clearance above the board for the switch and its short pad plunger."""

PAD_WEB_BOTTOM = BOARD_TOP + KEYPAD_KEEPOUT
"""Underside of the pad's web, over the keypad: SWITCH_TOP plus
KEYPAD_PLUNGER_STUB, so the plunger below it is a short, real stub rather
than a long unsupported peg standing in dead air."""

PAD_SKIRT_BOTTOM = SWITCH_TOP - params.PLUNGER_SWITCH_EXTENSION
"""Bottom of the moulded pad's skirt, level with the V3 plunger contacts, so
the pad stands level on both. The V2 top pads use it too, so every lobe's
skirt ends on one plane whichever board it is on."""

PAD_WEB_TOP = PAD_WEB_BOTTOM + params.PAD_WEB_T
CAVITY_FRONT = PAD_WEB_TOP
"""The front ceiling meets the top of the pad web."""

WHEEL = board.wheel_profile()
"""ENC1's revolved profile, measured off the assembly STEP by
board.wheel_profile() rather than hand-entered. Everything below that used to
be a guess (WHEEL_TOP was BOARD_TOP + 5.75) or trusted board.WHEEL_OD blind now
reads off this instead."""

_WHEEL_OD_DISAGREEMENT = WHEEL.lip_od - board.WHEEL_OD
if abs(_WHEEL_OD_DISAGREEMENT) > 0.1:
    raise ValueError(
        f"board.WHEEL_OD is {board.WHEEL_OD:.2f} but the measured lip is "
        f"{WHEEL.lip_od:.2f}mm, {_WHEEL_OD_DISAGREEMENT:+.2f} apart: fix "
        "WHEEL_OD rather than trusting either blind"
    )

WHEEL_TOP = WHEEL.top
"""Top of ENC1's knob, measured. See WHEEL above."""
WHEEL_LIP_OD = WHEEL.lip_od
WHEEL_LIP_Z0 = WHEEL.lip_z0
WHEEL_LIP_Z1 = WHEEL.lip_z1
WHEEL_MAIN_OD = WHEEL.main_od

SHELL_FRONT = WHEEL_TOP + params.FACE_CROWN_OVER_WHEEL
"""The crown of the recessed front's outer face, FACE_CROWN_OVER_WHEEL above
the wheel's own measured top. The face still comes from the measured knob, so a
wheel change moves the face with it.

The crown is the highest line of the face. It runs along y on the exterior
centreline between the two end rolls. face_z() gives the face height at each
plan point. Use this constant only as a bound, for example a probe start or a
cut above the whole face. The keypad ceiling is whatever gap the face leaves
over CAVITY_FRONT. The LED channel and counterbore checks hold their remaining
face thickness."""

FACE_WALL_TOP = SHELL_FRONT - params.FACE_SIDE_DROP
"""Height where the recessed front's face meets every exterior wall, side and
end. The face is vertical there, so the wall runs straight up into it."""

_EXTERIOR = board.board_profile().bounding_box()
_EXTERIOR_OVER = params.BOARD_FIT + params.WALL

EXTERIOR = (
    _EXTERIOR.min.X - _EXTERIOR_OVER,
    _EXTERIOR.min.Y - _EXTERIOR_OVER,
    _EXTERIOR.max.X + _EXTERIOR_OVER,
    _EXTERIOR.max.Y + _EXTERIOR_OVER,
)
"""(x0, y0, x1, y1) of the case's exterior walls, the LAP_OUT profile's own
extent."""

FACE_ARCH_X = (_EXTERIOR.min.X + _EXTERIOR.max.X) / 2
"""The x of the face's crown: the centre of the exterior side walls."""

FACE_ARCH_HALF = (_EXTERIOR.max.X - _EXTERIOR.min.X) / 2 + _EXTERIOR_OVER
"""Half the exterior width, from the crown to each side wall. Along the
straight side walls the face's superellipse has this half width."""


@functools.cache
def _plan():
    """(x0, x1, y0, y1, corners): the exterior plan profile, a rectangle with
    four corner arcs. x0 and x1 are the side walls, y0 and y1 are the grip and
    IR end walls. corners maps (right, ir) to the (x, y, r) of each arc.

    Each arc keeps its own centre and radius, because the board corners differ
    by a few tenths of a micron. A profile of any other form stops here rather
    than giving a wrong face."""
    from build123d import GeomType, Kind

    wire = (
        board.board_profile()
        .outer_wire()
        .offset_2d(_EXTERIOR_OVER, kind=Kind.INTERSECTION)
    )
    lines = [e for e in wire.edges() if e.geom_type == GeomType.LINE]
    arcs = [e for e in wire.edges() if e.geom_type == GeomType.CIRCLE]
    sides = sorted(
        (e for e in lines if abs(e.start_point().X - e.end_point().X) < 1e-6),
        key=lambda e: e.start_point().X,
    )
    ends = sorted(
        (e for e in lines if abs(e.start_point().Y - e.end_point().Y) < 1e-6),
        key=lambda e: e.start_point().Y,
    )
    x0, x1 = sides[0].start_point().X, sides[-1].start_point().X
    y0, y1 = ends[0].start_point().Y, ends[-1].start_point().Y
    corners = {
        (a.arc_center.X > (x0 + x1) / 2, a.arc_center.Y > (y0 + y1) / 2): (
            a.arc_center.X,
            a.arc_center.Y,
            a.radius,
        )
        for a in arcs
    }
    if len(lines) != 4 or len(sides) != 2 or len(ends) != 2 or len(corners) != 4:
        raise ValueError(
            "face_z() needs the exterior plan profile to be a rounded rectangle"
        )
    return x0, x1, y0, y1, corners


def _span(y):
    """(x0, x1) of the exterior plan at y: the side walls, or the corner arcs
    within a corner radius of an end wall."""
    x0, x1, _, _, corners = _plan()
    out = [x0, x1]
    for (right, ir), (cx, cy, r) in corners.items():
        if (y > cy) if ir else (y < cy):
            dy = min(abs(y - cy), r)
            out[right] = cx + (1 if right else -1) * math.sqrt(r * r - dy * dy)
    return out[0], out[1]


def _roll(w):
    """(1 - (1 - w)^n)^(1/n) for n = FACE_POWER and w clamped into [0, 1]. It is
    zero with a vertical tangent at w = 0 and one with zero slope at w = 1. The
    face is _roll(1 - u) across x and _roll(v) along y."""
    w = min(max(w, 0.0), 1.0)
    n = params.FACE_POWER
    return (1 - (1 - w) ** n) ** (1 / n)


def _end_v(y):
    """Distance from the nearer end wall as a fraction of FACE_END_ROLL."""
    _, _, y0, y1, _ = _plan()
    return min(y - y0, y1 - y) / params.FACE_END_ROLL


def face_z(x, y):
    """Height of the recessed front's built outer face at (x, y), before any
    recess.

    Across x the face is one superellipse of power FACE_POWER from side wall to
    side wall. It rises FACE_SIDE_DROP from FACE_WALL_TOP to the crown at
    SHELL_FRONT. Its half width is the plan's own at each y, so each section
    reaches FACE_WALL_TOP exactly on the plan outline, around the corners too.
    Along y the section height rolls down into each end wall over FACE_END_ROLL
    with the same power. The face is vertical at every wall. Outside the plan
    the height is FACE_WALL_TOP.

    face_body() builds a spline fit to this formula. The build stops if the fit
    strays more than FACE_FIT_TOLERANCE from it."""
    x0, x1 = _span(y)
    u = abs(2 * x - x0 - x1) / (x1 - x0)
    return FACE_WALL_TOP + params.FACE_SIDE_DROP * _roll(1 - u) * _roll(_end_v(y))


FACE_SECTION_SPANS = 128
"""Knot spans across the face's superellipse section, even in arc length. The
fit needs far fewer. But the mesher places its nodes from the knots, and at 48
spans the exported STL sagged up to 0.018 below the face. At 128 it stays
within 0.01."""

FACE_END_SPANS = 40
"""Knot spans along y over each end of the face. They run past the end roll and
the corner arc, and FACE_END_GRADE packs them toward the end wall."""

FACE_END_GRADE = 2.0
"""Exponent of the knot spacing over each end. Above one, the knots crowd
toward the end wall, where each corner arc turns into it."""

FACE_MIDDLE_KNOT = 4.0
"""Largest knot spacing along y between the two ends, in millimetres of crown.
The face there is the same section all along, so the fit needs no knots there.
These knots keep each face patch short, see FACE_PATCH_SPANS."""

FACE_FIT_SAMPLES = 4000
"""Points per end that the station fit is solved on."""

FACE_FIT_TOLERANCE = 1e-4
"""Largest error that face_body() accepts in its spline fit of face_z(). It is
measured normal to the face, so at a wall it is the error in plan. A parameter
change that the fit cannot follow stops the build here."""


def _basis(knots, ts):
    """Cubic B-spline basis on a clamped knot vector: one row per parameter in
    ts, one column per pole."""
    import numpy as np

    knots, ts = np.asarray(knots, float), np.asarray(ts, float)
    values = np.zeros((len(ts), len(knots) - 1))
    for i in range(len(knots) - 1):
        if knots[i] < knots[i + 1]:
            values[:, i] = (ts >= knots[i]) & (ts < knots[i + 1])
    values[ts >= knots[-1], np.nonzero(knots[:-1] < knots[1:])[0][-1]] = 1.0
    for p in range(1, 4):
        nxt = np.zeros((len(ts), len(knots) - 1 - p))
        for i in range(len(knots) - 1 - p):
            if knots[i + p] > knots[i]:
                nxt[:, i] += (ts - knots[i]) / (knots[i + p] - knots[i]) * values[:, i]
            if knots[i + p + 1] > knots[i + 1]:
                nxt[:, i] += (
                    (knots[i + p + 1] - ts)
                    / (knots[i + p + 1] - knots[i + 1])
                    * values[:, i + 1]
                )
        values = nxt
    return values


def _fit(basis, data, fixed):
    """Poles that fit data by least squares on basis, with the poles that fixed
    maps held at their given values."""
    import numpy as np

    free = [i for i in range(basis.shape[1]) if i not in fixed]
    rest = data - sum(basis[:, i] * v for i, v in fixed.items())
    poles = np.zeros(basis.shape[1])
    poles[free] = np.linalg.lstsq(basis[:, free], rest, rcond=None)[0]
    for i, v in fixed.items():
        poles[i] = v
    return poles


@functools.cache
def _face_section():
    """(knots, xs, zs, error): the unit superellipse of FACE_POWER as a cubic
    B-spline, with xs and zs its poles. x runs from -1 to 1, and z rises from 0
    to 1 and falls back.

    The first two and the last two poles stand on x = -1 and x = 1, so the curve
    leaves each wall vertically. error is the largest distance from the curve to
    the formula, scaled to FACE_ARCH_HALF."""
    import numpy as np

    n = params.FACE_POWER
    phi = np.linspace(0.0, math.pi / 2, 20001)
    r = (np.cos(phi) ** n + np.sin(phi) ** n) ** (-1 / n)
    hx, hz = r * np.cos(phi), r * np.sin(phi)
    hx[-1], hz[0] = 0.0, 0.0
    xs = np.concatenate([-hx, hx[-2::-1]])
    zs = np.concatenate([hz, hz[-2::-1]])
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(xs), np.diff(zs)))])
    spans = FACE_SECTION_SPANS
    knots = [0.0] * 4 + [i / spans for i in range(1, spans)] + [1.0] * 4
    basis = _basis(knots, s / s[-1])
    last = basis.shape[1] - 1
    px = _fit(basis, xs, {0: -1.0, 1: -1.0, last - 1: 1.0, last: 1.0})
    pz = _fit(basis, zs, {0: 0.0, last: 0.0})
    px, pz = (px - px[::-1]) / 2, (pz + pz[::-1]) / 2
    dense = _basis(knots, np.linspace(0.0, 1.0, 20001))
    radial = (np.abs(dense @ px) ** n + np.abs(dense @ pz) ** n) ** (1 / n)
    error = float(np.max(np.abs(radial - 1))) * FACE_ARCH_HALF
    return knots, px, pz, error


def _wall_normal_x(y, right):
    """The x part of the outward plan normal on one side wall at y."""
    for (side, ir), (_, cy, r) in _plan()[4].items():
        if side == right and ((y > cy) if ir else (y < cy)):
            return math.sqrt(max(r * r - min(abs(y - cy), r) ** 2, 0.0)) / r
    return 1.0


@functools.cache
def _face_stations():
    """(knots, ys, centres, halves, heights, error): the knot vector along y,
    the poles of each station quantity, and the fit error.

    Each station is one section across x. Its centre and half width are the
    plan's own at its y, and its height is the end roll's. The parameter is arc
    length along the crown, so the stations crowd into the end rolls. There the
    crown rises as the FACE_POWER root of the distance from the wall, and arc
    length makes that rise smooth.

    The first two and the last two poles of y, centre and half width are equal,
    so the face leaves each end wall vertically. A double knot sits where the
    corner arcs meet the side walls, because the plan's curvature jumps there.
    error is the largest fit error normal to the face."""
    import numpy as np

    n, roll, drop = params.FACE_POWER, params.FACE_END_ROLL, params.FACE_SIDE_DROP
    _, _, y0, y1, corners = _plan()
    e = np.linspace(0.0, 1.0, 4001)
    d_roll = roll * (1 - (1 - e**n) ** (1 / n))
    s_roll = np.concatenate(
        [[0.0], np.cumsum(np.hypot(np.diff(d_roll), drop * np.diff(e)))]
    )

    def s_at(d):
        if d <= roll:
            return float(np.interp(d, d_roll, s_roll))
        return s_roll[-1] + d - roll

    def d_at(s):
        return np.where(
            s <= s_roll[-1], np.interp(s, s_roll, d_roll), roll + s - s_roll[-1]
        )

    middle = s_at((y1 - y0) / 2)
    total = 2 * middle
    reach = s_at(max(roll, *(c[2] for c in corners.values())) + 1.0)
    if 2 * reach >= total:
        raise ValueError("the face's end rolls overlap along the case")
    steps = math.ceil((total - 2 * reach) / FACE_MIDDLE_KNOT)
    middle_knots = [reach + (total - 2 * reach) * k / steps for k in range(1, steps)]
    ends = []
    for ir in (False, True):
        wall = y1 if ir else y0
        joint = sum(abs(wall - corners[(side, ir)][1]) for side in (False, True)) / 2
        graded = [
            reach * (k / FACE_END_SPANS) ** FACE_END_GRADE
            for k in range(1, FACE_END_SPANS + 1)
        ]
        # Each special knot takes the place of its nearest graded one, so no
        # span is left too short to hold a sample.
        for special in (s_at(roll), s_at(joint)):
            graded.remove(min(graded, key=lambda k: abs(k - special)))
        ends.append(sorted(graded + [s_at(roll)] + [s_at(joint)] * 2))
    inner = ends[0] + middle_knots + sorted(total - k for k in ends[1])
    knots = np.array([0.0] * 4 + inner + [total] * 4) / total

    near = 1.2 * reach * np.linspace(0.0, 1.0, FACE_FIT_SAMPLES) ** FACE_END_GRADE
    between = np.linspace(near[-1], total - near[-1], 8 * steps)[1:-1]
    ss = np.concatenate([near, between, total - near[::-1]])
    ys = np.where(
        ss <= middle,
        y0 + d_at(np.minimum(ss, middle)),
        y1 - d_at(np.minimum(total - ss, middle)),
    )
    basis = _basis(knots, ss / total)
    last = basis.shape[1] - 1

    def ends_held(values, held):
        fixed = {0: values[0], last: values[-1]}
        if held:
            fixed.update({1: values[0], last - 1: values[-1]})
        return fixed

    py = _fit(basis, ys, ends_held(ys, True))
    ys = basis @ py
    spans = np.array([_span(y) for y in ys])
    centres, halves = spans.mean(axis=1), (spans[:, 1] - spans[:, 0]) / 2
    heights = drop * np.array([_roll(_end_v(y)) for y in ys])
    pc = _fit(basis, centres, ends_held(centres, True))
    ph = _fit(basis, halves, ends_held(halves, True))
    pb = _fit(basis, heights, ends_held(heights, False))

    error = 0.0
    for right, sign in ((False, -1), (True, 1)):
        miss = np.abs(basis @ pc + sign * (basis @ ph) - spans[:, int(right)])
        normal = np.array([_wall_normal_x(y, right) for y in ys])
        error = max(error, float(np.max(miss * normal)))
    dy, dh = np.gradient(ys, ss), np.gradient(heights, ss)
    slant = np.abs(dy) / np.maximum(np.hypot(dy, dh), 1e-300)
    miss = np.abs(basis @ pb - heights) * slant
    error = max(error, float(np.max(miss)))
    return knots, py, pc, ph, pb, error


FACE_PATCH_SPANS = 8
"""Knot spans in each direction of one face patch. A boolean tests every tool
face against every patch that it overlaps. With the whole face as one patch,
the keypad recess cut took twenty times as long. At 16 spans the exported STL
sagged up to 0.06 below the face."""


def _bspline_patches(poles, u_knots, v_knots):
    """Faces that cover the cubic B-spline surface with these poles, poles[i][j]
    at u_knots pole i and v_knots pole j, both knot vectors clamped. Each face
    covers FACE_PATCH_SPANS knot spans in each direction.

    Each face is on its own segment of the surface. Faces on one shared
    surface would merge again in the clean() after each boolean.

    build123d has Edge.make_bspline() but nothing that makes a surface from
    poles and knots, so this is the one place the model builds OCP geometry."""
    from build123d import Face
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.Geom import Geom_BSplineSurface
    from OCP.gp import gp_Pnt
    from OCP.TColgp import TColgp_Array2OfPnt
    from OCP.TColStd import TColStd_Array1OfInteger, TColStd_Array1OfReal

    def flat(values, kind):
        out = kind(1, len(values))
        for i, v in enumerate(values):
            out.SetValue(i + 1, v)
        return out

    def distinct(knots):
        values, mults = [], []
        for k in knots:
            if values and k == values[-1]:
                mults[-1] += 1
            else:
                values.append(float(k))
                mults.append(1)
        breaks = sorted(set(values[::FACE_PATCH_SPANS]) | {values[-1]})
        return (
            flat(values, TColStd_Array1OfReal),
            flat(mults, TColStd_Array1OfInteger),
            list(zip(breaks, breaks[1:])),
        )

    grid = TColgp_Array2OfPnt(1, len(poles), 1, len(poles[0]))
    for i, row in enumerate(poles):
        for j, p in enumerate(row):
            grid.SetValue(i + 1, j + 1, gp_Pnt(*p))
    (uk, um, us), (vk, vm, vs) = distinct(u_knots), distinct(v_knots)
    faces = []
    for u0, u1 in us:
        for v0, v1 in vs:
            surface = Geom_BSplineSurface(grid, uk, vk, um, vm, 3, 3)
            surface.Segment(u0, u1, v0, v1)
            faces.append(Face(BRepBuilderAPI_MakeFace(surface, 1e-7).Face()))
    return faces


@functools.cache
def face_body():
    """The recessed front's outer body before any cut: the exterior plan from
    SKIRT_BOTTOM up to the face, which is face_z() everywhere.

    The face is one B-spline surface in patches. Each pole is a pole of the unit
    section from _face_section(), scaled and placed by a pole of the stations
    from _face_stations(). As a result, every section is the same superellipse,
    and every boundary pole is on FACE_WALL_TOP. The walls are the face's own
    boundary edges carried down to SKIRT_BOTTOM, so the face meets each wall
    exactly and vertically. The face is a spline for the reason that
    arch_block() gives."""
    from build123d import Face, Shell, Solid, Wire

    s_knots, sx, sz, s_error = _face_section()
    t_knots, ty, tc, th, tb, t_error = _face_stations()
    error = s_error + t_error
    if error > FACE_FIT_TOLERANCE:
        raise ValueError(
            f"the face spline strays {error:.2g} from face_z(), more than "
            f"FACE_FIT_TOLERANCE {FACE_FIT_TOLERANCE:g}"
        )
    poles = [
        [(c + x * h, y, FACE_WALL_TOP + z * b) for y, c, h, b in zip(ty, tc, th, tb)]
        for x, z in zip(sx, sz)
    ]
    patches = _bspline_patches(poles, s_knots, t_knots)

    def level(edge, z):
        return all(abs(p.Z - z) < 1e-7 for p in (edge @ 0, edge @ 0.5, edge @ 1))

    down = (0, 0, SKIRT_BOTTOM - FACE_WALL_TOP)
    walls = [
        Face.extrude(e, down)
        for patch in patches
        for e in patch.edges()
        if level(e, FACE_WALL_TOP)
    ]
    floor = [e for wall in walls for e in wall.edges() if level(e, SKIRT_BOTTOM)]
    body = Solid(Shell([*patches, *walls, Face(Wire(floor))]))
    if not body.is_valid or body.volume <= 0:
        raise ValueError("face_body() did not close into a valid solid")
    return body


def _arch_r(sag):
    return (FACE_ARCH_HALF**2 + sag**2) / (2 * sag)


def arch_z(x, crown, sag):
    """Height at x of a circular arch with its axis along y: crown at
    FACE_ARCH_X and sag lower at each exterior side wall. The LED ring channel
    ceiling is such an arch. The face is not."""
    if sag <= 0:
        return crown
    r, dx = _arch_r(sag), x - FACE_ARCH_X
    return crown - r + math.sqrt(r * r - dx * dx)


def arch_block(z_low, crown, sag):
    """A prism along Y whose top is arch_z(x, crown, sag) and whose bottom is
    z_low.

    The arc is one rational quadratic Bezier segment, which is an exact circle.
    It is not an analytic circle on purpose. On an analytic cylinder, OCCT
    intersects each planar facet with a closed-form ellipse. A key-hole chamfer
    facet that is almost parallel to the axis gives an ellipse millions of
    millimetres long. The cut then fails without an error. The spline surface
    goes through the general intersection code, which has no such case."""
    from build123d import Box, Edge, Face, Pos, Wire, extrude

    half = FACE_ARCH_HALF + ARCH_BLOCK_MARGIN
    x0, x1 = FACE_ARCH_X - half, FACE_ARCH_X + half
    y0 = EXTERIOR[1] - ARCH_BLOCK_MARGIN
    y1 = EXTERIOR[3] + ARCH_BLOCK_MARGIN
    if sag <= 0:
        return Pos(FACE_ARCH_X, (y0 + y1) / 2, (z_low + crown) / 2) * Box(
            x1 - x0, y1 - y0, crown - z_low
        )
    r = _arch_r(sag)
    theta = math.asin(half / r)
    side = arch_z(x0, crown, sag)
    # The control point is where the end tangents meet. Its weight cos(theta)
    # makes the quadratic an exact arc of the circle.
    apex = crown - r + r / math.cos(theta)
    arc = Edge.make_bspline(
        [(x1, y0, side), (FACE_ARCH_X, y0, apex), (x0, y0, side)],
        [0, 0, 0, 1, 1, 1],
        2,
        [1, math.cos(theta), 1],
    )
    wire = Wire(
        [
            Edge.make_line((x0, y0, z_low), (x1, y0, z_low)),
            Edge.make_line((x1, y0, z_low), (x1, y0, side)),
            arc,
            Edge.make_line((x0, y0, side), (x0, y0, z_low)),
        ]
    )
    return extrude(Face(wire), amount=y1 - y0, dir=(0, 1, 0)).solids()[0]


ARCH_BLOCK_MARGIN = 10.0
"""How far arch_block() reaches past the exterior on every side, so that no
face of the block lies on a face of the solid it trims."""

FDM_FACE = SHELL_FRONT - params.FDM_FACE_DROP
"""The FDM front's own outer face, FDM_FACE_DROP below the recessed front's.

That front replaces the keypad recess with an outline scribed in a flat face,
and a flat face at SHELL_FRONT would keep all the material the dish removed.
This is the same plane taken down to where the dish's own floor is, so the part
is as slim as the one it stands in for. Everything under it is unchanged and at
its own z, which is why the ceilings it thins are what bound the drop rather
than anything moving with it."""


def front_face(fdm=False):
    """Which of the two outer faces a front shell is built to. The FDM face is
    flat. For the recessed front this is the crown, and face_z() gives the
    height at each plan point."""
    return FDM_FACE if fdm else SHELL_FRONT


KEYPAD_CEILING = SHELL_FRONT - CAVITY_FRONT
"""Ceiling actually left over the keypad at the crown, now that SHELL_FRONT is
fixed and CAVITY_FRONT is not: a derived report value rather than a tunable
input, the inverse of how the two used to relate."""


def cap_top(ref):
    """Top of the released cap on switch `ref`: CAP_PROTRUSION above the built
    face at the cap's centre.

    Each cap top is flat. A cap in an outer column stands lower than a cap on
    the centreline, by the face's drop at its x, so the row of cap tops follows
    the face."""
    x, y = board.components()[ref][:2]
    return face_z(x, y) + params.CAP_PROTRUSION


CAP_BOTTOM = PAD_WEB_TOP + params.CAP_LIFT
"""Bottom of a cap's flange. With CAP_LIFT at zero it rests on the pad web."""

COUNTERBORE_TOP = (
    CAVITY_FRONT + params.CAP_LIFT + params.CAP_FLANGE_T + params.CAP_FLANGE_FLOAT
)
"""Shoulder a cap's flange lifts against, and so how far the counterbore is sunk
into the ceiling. What is left between here and the face is the face land, the
ledge the flange is caught by."""

DISH_HEADROOM = SHELL_FRONT - COUNTERBORE_TOP
"""All the ceiling there is between a cap's counterbore shoulder and the face
at its crown, and so the whole budget a keypad recess is cut out of. What a
dish takes at any point over a counterbore comes straight out of this; check.py's land
guard holds the rest above LAND_FLOOR_MIN. Off the centreline the face also
takes its drop out of this budget, because every dish follows the face.

There is no single pocket-floor constant any more. The recess is curved, so the
floor is a function of position rather than a plane, and case.face_floor_at()
is what answers for it. Keeping a scalar here would only be a plane nothing is
actually built at."""


def stem_top(ref):
    """Ceiling of the socket in the cap on switch `ref`, and the top of the stem
    that reaches it: CAP_TOP_T under that cap's own top. The two meet, so a
    press drives through the stem rather than through the flange, and the pad's
    silicone touches the cap where the backlight has to cross. A stem under a
    lower cap is shorter by the same value, so every cap roof stays CAP_TOP_T
    thick."""
    return cap_top(ref) - params.CAP_TOP_T

LIP_CLEAR_R = WHEEL_LIP_OD / 2 + params.WHEEL_CLEARANCE
"""The pad's wheel bore: clearance over the lip, the widest disc of the
revolved shape, is exactly WHEEL_CLEARANCE. The lip never reaches the
ceiling (board.wheel_profile() puts its top WHEEL_CLEARANCE and more below
CAVITY_FRONT, see check.py's wheel_seat_clearance), so this bore is a
pad-side rotating clearance only, not something the shell's own wheel
opening has to match: the board is lowered into an already-closed front
shell, so the shell's opening only ever has to clear whatever of the wheel
passes through it, the bezel and knob above the lip, not the lip itself."""

WHEEL_OPENING_R = WHEEL_MAIN_OD / 2 + params.WHEEL_OPENING_CLEARANCE
"""The shell's own wheel opening, a plain bore from the ceiling underside to
the face: the fixed bezel's radius plus WHEEL_OPENING_CLEARANCE,
its own gap rather than the pad's WHEEL_CLEARANCE, so the bore closes around
the wheel on a line tight enough to read as one. Narrower than LIP_CLEAR_R,
which is fine for the same reason that bore is pad-only: the lip stays below
the ceiling and never transits the opening. Its top is opened out by the rotary
recess, which is centred on the same axis and reaches WHEEL_RIM_LEDGE past this
on its own axes."""

MERGE = 0.5
"""How far an added feature reaches into the body it grows from. Anything that
merely touches at a plane fuses into a compound rather than one solid, and the
next boolean then discards the whole shell."""

SKIRT_BOTTOM = BOARD_TOP - params.SKIRT_H
"""Lower edge of the front skirt, held relative to the board top."""

SHELL_SEAM = BOARD_TOP + params.SHELL_SEAM_RISE
"""Top of the back lap and front skirt. Raising this seam grows the thin
mating band upward without changing the board's own Z stack."""

LAP_OUT = params.BOARD_FIT + params.WALL
"""Outer face of the case, which both shells share: the back's lap runs right up
to the parting plane, so the seam is a line rather than a step."""

LAP_IN = LAP_OUT - params.SKIRT_T
"""Inner face of the back's lap, and so the surface the skirt slides against."""

SKIRT_OUT = LAP_IN - params.SKIRT_FIT
"""Outer face of the skirt. Its inner face is the cavity wall's, so the skirt is
that wall carried down rather than a rib added beside it. That matters
structurally: put it anywhere inboard and it shares no plan area with the wall
above, and builds as a ring floating in mid air."""

STIFFENED_WALL = params.BOARD_FIT - params.SIDE_SKIRT_THICKEN
"""Offset of the front's inner wall from the board edge wherever
skirt_stiffener() runs, from the skirt bottom to the cavity ceiling. The IR end
keeps BOARD_FIT."""
