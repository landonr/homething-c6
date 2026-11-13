"""The acoustic inlet over MK1: one funnel, bell at the second keypad recess's
own floor and throat on the board's own acoustic port. A concave fillet band
over the last of the way out, riding the dished floor so the floor cuts it in
one edge, a cone narrowing under it, and MIC_THROAT_MARGIN over the board's
drill at the throat."""

import math

from build123d import Cone, Edge, Face, Plane, Pos, Shell, Solid, Torus, Wire

import board
import params

from .shape import _chamfered_post, _cut, _fuse, _hole
from .stack import BOARD_TOP, CAVITY_FRONT, FDM_FACE, MERGE, SHELL_FRONT


def mic_port():
    """(x, y) of the board's acoustic port hole under MK1."""
    x, y, _ = board.npth_pads("MK1")[0]
    return x, y


def mic_port_drill():
    """Diameter of that hole, read off the board rather than restated here. The
    throat is sized on it, so a board that redrills the port moves the inlet's
    narrow end with it instead of leaving the two out of step."""
    return board.npth_pads("MK1")[0][2]


def mic_duct_or():
    """Outer radius of the duct post. One reader for MIC_DUCT_OD so the plan
    footprint, the keypad island that has to contain it and the wall left around
    the bore all measure the same circle."""
    return params.MIC_DUCT_OD / 2


def mic_duct_footprint():
    x, y = mic_port()
    r = mic_duct_or()
    return ("mic duct", x - r, y - r, x + r, y + r)


def mic_face(fdm=False):
    """The z the inlet actually opens at, which is the keypad recess's own
    floor directly over the board's port rather than SHELL_FRONT: the mic sits
    inside the second island's dish, so the surface around it is already dished
    down by whatever case.face_depth_at() says there. On the FDM front it is
    that front's own flat face, FDM_FACE.

    A function, and a curved surface underneath it, where this was a constant
    over a flat pocket floor. The dish's floor is not level across the mouth,
    so this is only the height the taper and the band's base hang off. The
    band's top follows the floor itself, see mic_band_point().

    The import is inside the call because keypad.py reads mic_port() and
    mic_duct_or() to size the recess this asks about, so the two modules cannot
    both name each other at import time.
    """
    if fdm:
        return FDM_FACE
    from .keypad import face_floor_at

    return face_floor_at(*mic_port())


def mic_throat_d():
    """Diameter at the board end, where the funnel lands on the board's own port
    hole: that drill plus MIC_THROAT_MARGIN. The narrowest the inlet gets, and
    the only width in it the board has a say in."""
    return mic_port_drill() + params.MIC_THROAT_MARGIN


def mic_throat_r():
    return mic_throat_d() / 2


def mic_mouth_r():
    """Radius of the fillet band's top ring, the widest the bore gets. On the
    recessed front the floor cuts the band inside it, at mic_floor_edge_r()."""
    return params.MIC_MOUTH_D / 2


def mic_taper_r():
    """Radius the taper has reached at the top of its run, the base of the
    fillet band, where the cone hands over to the arc. MIC_TAPER_SHARE of the
    way out from the throat to the mouth."""
    return mic_throat_r() + params.MIC_TAPER_SHARE * (mic_mouth_r() - mic_throat_r())


def mic_fillet_r():
    """Radius of the quarter-round finishing the mouth: the mouth less wherever
    MIC_TAPER_SHARE left the taper, which is the one radius carrying the arc
    from the cone's top out to the mouth. Also how far below mic_face() the
    fillet band starts.

    Derived rather than set, so the funnel cannot be given a throat, a taper and
    an arc that disagree about where they meet."""
    return mic_mouth_r() - mic_taper_r()


def mic_taper_top(fdm=False):
    """Where the taper stops and the fillet band begins."""
    return mic_face(fdm) - mic_fillet_r()


def mic_taper_angle():
    """Half angle of the taper's cone, off the duct's own axis, in degrees.
    Reported rather than designed to, and worth reporting because it is what says
    the cone self-supports: the duct is far taller than the bore is wide, so
    however MIC_TAPER_SHARE divides the run this stays a shallow wall rather than
    an overhang, whichever way up the shell is laid on a bed."""
    run = mic_taper_top() - BOARD_TOP
    return math.degrees(math.atan((mic_taper_r() - mic_throat_r()) / run))


def mic_duct_wall_left():
    """Thinnest wall left between the bore and the outside of the duct post,
    which is at the band's top ring where the mouth is at its widest. The bore
    narrows from there all the way down, so it takes less of the post at every
    height below and by the throat it takes almost none: this one height is the
    whole constraint. What bounds MIC_MOUTH_D against MIC_DUCT_OD, since nothing else
    does."""
    return mic_duct_or() - mic_mouth_r()


BAND_SECTIONS = 12
"""Loft sections up the recessed front's fillet band, evenly spaced in arc
angle. Twelve hold the lofted surface within 0.0001 of mic_band_point()
between sections."""

BAND_BEARINGS = 48
"""Points round each band section's periodic spline. The floor term is a gentle
tilt and bow across the mouth, so the spline follows it far closer than the
loft needs."""

PROFILE_ITERATIONS = 50
"""Bisection steps for a band arc angle, which takes the error to float noise."""


def mic_band_point(phi, theta):
    """(rho, z) of the recessed front's fillet band, at arc angle phi on bearing
    theta about the port. phi = 0 is the cone's top and phi = pi/2 the band's
    top ring.

    rho is the quarter-round's. z is the quarter-round's height plus sin(phi)
    times the sum of MIC_MOUTH_LIFT and the floor's rise over mic_face() at that
    point. So phi = 0 is the flat circle the cone ends at, and the top ring runs
    MIC_MOUTH_LIFT above the floor all the way round. The floor then cuts the
    band in one edge at an almost even radius and crease.

    The one formula mic_bore() lofts and mic_profile_r() reads, so the check
    probes the curve the cut is built from.
    """
    from .keypad import face_floor_at

    x, y = mic_port()
    r = mic_fillet_r()
    rho = mic_mouth_r() - r * math.cos(phi)
    floor = face_floor_at(x + rho * math.cos(theta), y + rho * math.sin(theta))
    rise = floor - mic_face() + params.MIC_MOUTH_LIFT
    return rho, mic_taper_top() + math.sin(phi) * (r + rise)


def mic_floor_edge_r():
    """Radius where the recess floor cuts the fillet band, the visible mouth.

    Closed form from mic_band_point() over a level floor: there the band
    stands (r + MIC_MOUTH_LIFT) * sin(phi) above its base, so the floor cuts it
    where sin(phi) = r / (r + MIC_MOUTH_LIFT). The real floor tilts and bows across
    the mouth, which moves the edge by under 0.01 with bearing. Independent of
    the floor term on purpose, so a check placed on it still lands either side
    of the edge when that term is broken.
    """
    r, lift = mic_fillet_r(), params.MIC_MOUTH_LIFT
    return mic_mouth_r() - r * math.sqrt(lift * (2 * r + lift)) / (r + lift)


def mic_profile_r(z, theta=0.0):
    """The inlet's own radius at height z on bearing theta: the throat at and
    below the board, the taper's cone widening up from it, the fillet band's
    rider surface, the mouth at and above the band's top ring. Only the band
    depends on theta. The default, the +x bearing, is the ray every
    _opening_radius probe walks.

    The band's z rises with its arc angle everywhere up to within about a
    degree of the top ring. That is well above the floor edge, so the bisection
    is exact wherever the band is built in material.

    Public because check.py probes the built shell against it. The expectation
    is then the same curve mic_bore() is cut from rather than a second
    description of it that could drift, and the probe is left proving that the
    boolean produced the curve rather than that two formulas agree.

    It flattens off at BOARD_TOP rather than following the cut's overrun below
    it. The cone carries on narrowing down there and the curve deliberately does
    not, because below the board end there is no shell for a probe to find an
    opening in: the overrun only has to break through.
    """
    base = mic_taper_top()
    if z >= mic_band_point(math.pi / 2, theta)[1]:
        return mic_mouth_r()
    if z > base:
        lo, hi = 0.0, math.pi / 2
        for _ in range(PROFILE_ITERATIONS):
            mid = (lo + hi) / 2
            if mic_band_point(mid, theta)[1] < z:
                lo = mid
            else:
                hi = mid
        return mic_band_point(lo, theta)[0]
    if z <= BOARD_TOP:
        return mic_throat_r()
    run = base - BOARD_TOP
    return mic_throat_r() + (mic_taper_r() - mic_throat_r()) * (z - BOARD_TOP) / run


def mic_duct(face=SHELL_FRONT):
    """The duct as a solid post, board to front face, for the funnel to be
    drilled out of afterwards.

    Solid, not the tube it was. A tube is its outer wall less its own straight
    bore, and that bore is subtracted before mic_bore() ever runs, so it wins
    wherever it is the wider of the two. That was harmless while the two agreed
    at the board end. It stopped being harmless when the throat came down onto
    the board's own drill: the funnel is narrower than any sensible tube bore
    over most of its length now, so a tube would have quietly left the taper as a
    straight hole and every number describing it would still have looked right.
    """
    x, y = mic_port()
    return _chamfered_post(
        x,
        y,
        params.MIC_DUCT_OD,
        BOARD_TOP,
        face,
        params.STANDOFF_CHAMFER,
        "upper",
        CAVITY_FRONT,
    )


def _band_ring(phi):
    """One band section: a closed periodic spline through BAND_BEARINGS points
    of mic_band_point() at arc angle phi, starting on the +x bearing like the
    circle at phi = 0."""
    x, y = mic_port()
    points = []
    for i in range(BAND_BEARINGS):
        theta = 2 * math.pi * i / BAND_BEARINGS
        rho, z = mic_band_point(phi, theta)
        points.append((x + rho * math.cos(theta), y + rho * math.sin(theta), z))
    return Wire([Edge.make_spline(points, periodic=True)])


def _riding_mouth():
    """The recessed front's mouth: the fillet band that rides the floor, and a
    chimney at the mouth's radius from the band's top ring up past the face.

    A solid loft cannot cap the band's top ring, which is not planar. So the
    band's side is a smooth loft and the chimney's a ruled loft off the same
    top ring wire, sewn with a flat disc at each end. The band and chimney are
    separate lofts because one smooth loft through the horizontal to vertical
    corner overshoots and cuts into the floor past the edge. The bottom section
    is an exact circle at the taper's top, so the shared flat disc with the
    cone stays exact.
    """
    x, y = mic_port()
    rings = [Wire.make_circle(mic_taper_r(), Plane((x, y, mic_taper_top())))]
    rings += [
        _band_ring(math.pi / 2 * k / BAND_SECTIONS)
        for k in range(1, BAND_SECTIONS + 1)
    ]
    lid = Wire.make_circle(mic_mouth_r(), Plane((x, y, SHELL_FRONT + MERGE)))
    band = Shell.make_loft(rings)
    chimney = Shell.make_loft([rings[-1], lid], ruled=True)
    mouth = Solid(Shell([*band.faces(), *chimney.faces(), Face(rings[0]), Face(lid)]))
    if not mouth.is_valid or len(mouth.solids()) != 1 or mouth.volume <= 0:
        raise ValueError("the mic mouth did not close into one valid solid")
    return mouth


def mic_bore(fdm=False):
    """The whole funnel as a single cut: a stub of the throat at the board, the
    taper's cone opening up off it, the concave fillet band where that reaches
    the floor, and the mouth carried on up past the face.

    With fdm, the funnel ends at the FDM front's own flat face, so that front
    does not move when the recessed front's face moves. Its band is the plain
    quarter-round torus, tangent to that flat face, carried up as a cylinder.
    On the recessed front the band rides the dish floor instead, see
    _riding_mouth().

    One solid rather than a hole plus separate end features, which is what the
    countersink this replaces was. A fillet's base radius *is* the radius of
    whatever runs below it, so as two cuts the mouth and the taper would meet
    along a single circle with each wall running into the other's, which is the
    seam the countersink dodged by starting below its own base where the cone
    was still the narrower of the two. A fillet has no such margin to start in,
    so the two are fused across a shared flat disc at the band's base instead
    and the boolean is left nothing to resolve. Both solids have a real disc
    face there, the cone's top and the mouth's bottom, at the same radius.

    The stub at the board is what the cone cannot do for itself. The cut has to
    pierce the duct's own bottom face at BOARD_TOP, so it needs an overrun below
    it, and the cone narrows as it goes down: carried below the board it would
    arrive at that face at exactly the throat with its end coplanar. So the stub
    carries the throat's full width a millimetre past the face and the cone's own
    narrowing overrun hides inside it rather than being the thing that breaks
    through.
    """
    x, y = mic_port()
    r = mic_fillet_r()
    base = mic_taper_top(fdm)
    stub = _hole(x, y, mic_throat_d(), BOARD_TOP - 1, BOARD_TOP + MERGE)
    # Slope carried a MERGE below the board so the cone ends inside the stub
    # rather than on the face the stub is there to pierce.
    slope = (mic_taper_r() - mic_throat_r()) / (base - BOARD_TOP)
    taper = Pos(x, y, (BOARD_TOP - MERGE + base) / 2) * Cone(
        bottom_radius=mic_throat_r() - MERGE * slope,
        top_radius=mic_taper_r(),
        height=base - (BOARD_TOP - MERGE),
    )
    if not fdm:
        return _fuse(stub, taper, _riding_mouth())
    mouth = _cut(
        _hole(x, y, 2 * mic_mouth_r(), base, SHELL_FRONT + MERGE),
        Pos(x, y, base) * Torus(mic_mouth_r(), r),
    )
    return _fuse(stub, taper, mouth)
