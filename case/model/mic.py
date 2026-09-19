"""The acoustic inlet over MK1: one funnel, bell at the second keypad recess's
own floor and throat on the board's own acoustic port. A concave fillet over the
last of the way out at the floor, a cone narrowing under it, and
MIC_THROAT_MARGIN over the board's drill where the two meet."""

import math

from build123d import Cone, Pos, Torus

import board
import params

from .shape import _chamfered_post, _cut, _fuse, _hole
from .stack import BOARD_TOP, CAVITY_FRONT, MERGE, SHELL_FRONT


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


def mic_face():
    """The z the inlet actually opens at, which is the keypad recess's own
    floor directly over the board's port rather than SHELL_FRONT: the mic sits
    inside the second island's dish, so the surface around it is already dished
    down by whatever case.face_depth_at() says there.

    A function, and a curved surface underneath it, where this was a constant
    over a flat pocket floor. The dish's floor is not level across the mouth,
    so what the funnel is tangent to is the floor at the port itself; over the
    mouth's own width the floor rises by well under a tenth, which the mouth's
    straight run past this height absorbs.

    The import is inside the call because keypad.py reads mic_port() and
    mic_duct_or() to size the recess this asks about, so the two modules cannot
    both name each other at import time.
    """
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
    """Radius the inlet opens out to at mic_face(). The widest it gets."""
    return params.MIC_MOUTH_D / 2


def mic_taper_r():
    """Radius the taper has reached at the top of its run, the base of the
    fillet band, where the cone hands over to the arc. MIC_TAPER_SHARE of the
    way out from the throat to the mouth."""
    return mic_throat_r() + params.MIC_TAPER_SHARE * (mic_mouth_r() - mic_throat_r())


def mic_fillet_r():
    """Radius of the quarter-round finishing the mouth: the mouth less wherever
    MIC_TAPER_SHARE left the taper, which is the one radius leaving the arc
    tangent to mic_face() above and continuous with the cone below. Also how far
    below that face the fillet band starts, a tangent quarter-round sinking
    exactly its own radius.

    Derived rather than set, so the funnel cannot be given a throat, a taper and
    an arc that disagree about where they meet."""
    return mic_mouth_r() - mic_taper_r()


def mic_taper_top():
    """Where the taper stops and the fillet band begins."""
    return mic_face() - mic_fillet_r()


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
    which is at mic_face() where the mouth is at its widest. The bore narrows from
    there all the way down, so it takes less of the post at every height below
    and by the throat it takes almost none: this one height is the whole
    constraint. What bounds MIC_MOUTH_D against MIC_DUCT_OD, since nothing else
    does."""
    return mic_duct_or() - mic_mouth_r()


def mic_profile_r(z):
    """The inlet's own radius at height z: the throat at and below the board, the
    taper's cone widening up from it, the fillet's arc, the mouth at and above
    mic_face(). Monotonic, the funnel having no straight section between the board
    and the face.

    Public because check.py probes the built shell against it. The expectation
    is then the same curve mic_bore() is cut from rather than a second
    description of it that could drift, and the probe is left proving that the
    boolean produced the curve rather than that two formulas agree.

    It flattens off at BOARD_TOP rather than following the cut's overrun below
    it. The cone carries on narrowing down there and the curve deliberately does
    not, because below the board end there is no shell for a probe to find an
    opening in: the overrun only has to break through.
    """
    r = mic_fillet_r()
    base = mic_taper_top()
    if z >= mic_face():
        return mic_mouth_r()
    if z > base:
        return mic_mouth_r() - math.sqrt(r * r - (z - base) ** 2)
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


def mic_bore():
    """The whole funnel as a single cut: a stub of the throat at the board, the
    taper's cone opening up off it, the concave quarter-round where that reaches
    mic_face(), and the mouth carried on past that face.

    One solid rather than a hole plus separate end features, which is what the
    countersink this replaces was. A tangent arc's base radius *is* the radius
    of whatever runs below it, so as two cuts the mouth and the taper would meet
    along a single circle with each wall running into the other's at the arc's
    own tangent, which is the seam the countersink dodged by starting below its
    own base where the cone was still the narrower of the two. A fillet has no
    such margin to start in, so the two are fused across a shared flat disc at
    the band's base instead and the boolean is left nothing to resolve. Both
    solids have a real disc face there, the cone's top and the mouth's bottom,
    and the torus has already taken the mouth's back to the same radius.

    The stub at the board is what the cone cannot do for itself. The cut has to
    pierce the duct's own bottom face at BOARD_TOP, so it needs an overrun below
    it, and the cone narrows as it goes down: carried below the board it would
    arrive at that face at exactly the throat with its end coplanar. So the stub
    carries the throat's full width a millimetre past the face and the cone's own
    narrowing overrun hides inside it rather than being the thing that breaks
    through.

    Above mic_face() the mouth is carried up at constant radius rather than the
    arc continued, because at that height the arc's own tangent is the floor.
    It has to be carried up rather than stopped there: the recess's floor rises
    away from the port, so the last fraction of a millimetre of the mouth's
    upper edge is what the mouth's own straight run takes out on the shallow
    side, and above that the dish has already removed everything.
    """
    x, y = mic_port()
    r = mic_fillet_r()
    base = mic_taper_top()
    stub = _hole(x, y, mic_throat_d(), BOARD_TOP - 1, BOARD_TOP + MERGE)
    # Slope carried a MERGE below the board so the cone ends inside the stub
    # rather than on the face the stub is there to pierce.
    slope = (mic_taper_r() - mic_throat_r()) / (base - BOARD_TOP)
    taper = Pos(x, y, (BOARD_TOP - MERGE + base) / 2) * Cone(
        bottom_radius=mic_throat_r() - MERGE * slope,
        top_radius=mic_taper_r(),
        height=base - (BOARD_TOP - MERGE),
    )
    mouth = _cut(
        _hole(x, y, 2 * mic_mouth_r(), base, SHELL_FRONT + MERGE),
        Pos(x, y, base) * Torus(mic_mouth_r(), r),
    )
    return _fuse(stub, taper, mouth)
