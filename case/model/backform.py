"""The back's contoured outer form: how deep it reaches below the board at
every point along it, and the loft that turns that curve into a solid.

Its own module rather than part of shells.py, because hardware.py's closure
screw reads contour_depth() to find the floor under it while shells.py reads
both this and hardware.py. Keeping the curve below both breaks that cycle.
"""

import functools
import math

from build123d import Plane, RectangleRounded, loft

import board
import params

from .cell import cradle_span
from .shape import _offset_face
from .stack import SHELL_BACK, SHELL_FRONT


@functools.cache
def under_board():
    """[(y0, y1, depth)] of everything hanging below the board.

    Measured off the assembly where a part has a model, and assumed
    UNMODELLED_DEPTH deep where it does not. This is what the contour's ends are
    sized from, rather than one constant for both: U2 is the deepest thing at the
    +Y end and J1 at the -Y end, they are measured and assumed respectively, and
    no single number serves both.

    Neither reaches CONTOUR_END_DEPTH as the board stands, so both ends fall back
    to it and this only says by how much. U2 did reach past it while it was a
    through-hole receiver straddling the board; the SMD part that replaced it
    hangs nothing like as far, which is what let CONTOUR_END_DEPTH come down.
    """
    spans = []
    for solid in board.assembly_solids():
        box = solid.bounding_box()
        if box.min.Z < -0.05:
            spans.append((box.min.Y, box.max.Y, -box.min.Z))
    for ref, (_, y0, _, y1, side) in board.courtyards().items():
        if side != "bottom":
            continue
        try:
            board.part_envelope(ref)
        except ValueError:
            spans.append((y0, y1, params.UNMODELLED_DEPTH))
    return tuple(spans)


@functools.cache
def end_depth(sign):
    """Cavity plus floor at one tapered end, from whatever hangs below the board
    out past the cradle on that side. CONTOUR_END_DEPTH is only the fallback."""
    lo, hi = cradle_span()
    deepest = max(
        (d for y0, y1, d in under_board() if (y1 > hi if sign > 0 else y0 < lo)),
        default=0.0,
    )
    clear = max(params.CONTOUR_END_DEPTH, params.CELL_TOP_GAP + deepest)
    return clear + params.FLOOR


def _tip_lift(y):
    """How far the back rolls up as it approaches the end of the case, so the
    bottom meets the end face tangentially. Keyed to the case's own end, not the
    board's, or the roll finishes before the end face and leaves a lip."""
    box = board.board_profile().bounding_box()
    over = params.BOARD_FIT + params.WALL
    r = params.CONTOUR_TIP_R
    d = min(y - (box.min.Y - over), (box.max.Y + over) - y)
    d = min(max(d, 0.0), r)
    return r - math.sqrt(max(r * r - (r - d) ** 2, 0.0))


def contour_depth(y):
    """How deep the back reaches below the board at this point along it.

    Full depth over the cell and its cradle, tapering to each end's own derived
    depth past them, then rolling up through CONTOUR_TIP_R at the very ends. The
    cell sits toward the bottom, so the deep part is where the hand is.
    """
    deep = -SHELL_BACK
    lo, hi = cradle_span()
    if lo <= y <= hi:
        return deep - _tip_lift(y)
    sign = 1 if y > hi else -1
    t = min((y - hi if sign > 0 else lo - y) / params.CONTOUR_BLEND, 1.0)
    base = deep + (end_depth(sign) - deep) * t * t * (3 - 2 * t)
    return base - _tip_lift(y)


def back_edge_radius(y):
    """Bottom-edge radius at y, roundest over the cell and smallest near U2.

    The blend shares the upper contour taper. This keeps the hand-held battery
    section fully domed, then makes one C1 transition to the slimmer IR end.
    """
    _, hi = cradle_span()
    if y <= hi:
        return params.EDGE_R_BACK_CELL
    t = min((y - hi) / params.CONTOUR_BLEND, 1.0)
    blend = t * t * (3 - 2 * t)
    return (
        params.EDGE_R_BACK_CELL
        + (params.EDGE_R_BACK_IR - params.EDGE_R_BACK_CELL) * blend
    )


SECTION_GAP = 0.2
"""Closest two loft sections may sit over the flats. Sampling the taper and the
rolled end independently landed two 0.05 apart, and the sliver of a face between
them was enough to leave the loft unable to intersect anything."""

END_STEP = 0.06
"""Closest two sections may sit inside an end region. The angle-spaced stations
crowd toward the vertical tangent without limit, and past this they are buying
accuracy finer than the tessellator carries anyway."""

SECTION_OVERRUN = 3.0
"""How far the loft runs past the case. Ending it flush with the plan prism means
the two bodies share their end faces, and the intersection then fails outright."""

END_SECTIONS = 20
"""Stations in each end region. They are spaced by equal angle from the end face,
not by equal y: both the tip roll and the plan corner stand vertical where they
meet that face, so an equal-y step there spans more of either curve than the
whole rest of it put together."""


@functools.cache
def _plan_face(inset):
    """The plan profile the form follows at this inset: the case outline itself
    at 0, and the same outline pulled in by the wall for the cavity."""
    return _offset_face(params.BOARD_FIT + params.WALL - inset)


@functools.cache
def _plan_chord(inset, y):
    """(centre, half width) of that profile across this point along it.

    Clamped to the profile's own ends, so the sections that overrun the case
    repeat its end width instead of asking for a chord that is not there.
    """
    face = _plan_face(inset)
    box = face.bounding_box()
    y = min(max(y, box.min.Y), box.max.Y)
    xs = [
        v.X
        for e in face.intersect(Plane(origin=(0, y, 0), z_dir=(0, 1, 0))).edges()
        for v in e.vertices()
    ]
    return (min(xs) + max(xs)) / 2, (max(xs) - min(xs)) / 2


def _plan_bias(inset, ys, i):
    """How far past its chord a section sits, so the ruled faces between sections
    stay outside the profile instead of chording inside it.

    Where the loft is the narrower of the two bodies it is the loft that shows,
    and a chord across a turning run of the plan would replace that run's arc
    with a flat over the whole height of the wall. Each section is pushed out by
    the worst shortfall of the runs either side of it, which is nothing at all
    along the straight sides and a hair around the corners.
    """
    out = 0.0
    for j in (i - 1, i):
        if 0 <= j < len(ys) - 1:
            y0, y1 = ys[j], ys[j + 1]
            chord = (_plan_chord(inset, y0)[1] + _plan_chord(inset, y1)[1]) / 2
            out = max(out, _plan_chord(inset, (y0 + y1) / 2)[1] - chord)
    return out


@functools.cache
def end_reach():
    """How far in from each end a section has to track a curve rather than a
    straight run: the tip roll, or the plan corner if that is the longer."""
    face = _plan_face(0.0)
    box = face.bounding_box()
    wire = face.outer_wire()
    x = max(v.X for v in wire.vertices())
    ys = [v.Y for v in wire.vertices() if x - v.X < 1e-6]
    runs = (min(ys) - box.min.Y, box.max.Y - max(ys))
    return max(params.CONTOUR_TIP_R, *runs)


def _end_stations(tip, step):
    """Stations through one end region, angle-spaced from the end face.

    Keyed to the outer profile's corner, which is where the surface that shows
    turns. The cavity's own corner starts a wall further in and is sampled more
    coarsely, which leaves its floor a hair proud of tangency at the corner and
    so a hair of extra wall. Resolving that one too doubles the section count
    for a face nobody sees.
    """
    reach = end_reach()
    out = set()
    for i in range(END_SECTIONS + 1):
        angle = math.pi * i / (2 * END_SECTIONS)
        out.add(tip + step * reach * (1 - math.cos(angle)))
    return out


def _contour_samples():
    """Where to cut sections for the loft. Dense through the tapers and the end
    regions, sparse over the flats, because a section costs real time."""
    box = board.board_profile().bounding_box()
    lo, hi = cradle_span()
    over = params.BOARD_FIT + params.WALL
    ends = (box.min.Y - over, box.max.Y + over)
    b = params.CONTOUR_BLEND
    reach = end_reach()

    ys = {lo, hi, ends[0] - SECTION_OVERRUN, ends[1] + SECTION_OVERRUN, *ends}
    for start in (lo - b, hi):
        for i in range(21):
            y = start + b * i / 20
            # The end regions carry their own stations. A taper station inside
            # one creates a short ruled face beside a long face and shows as a
            # kink.
            if any(abs(y - tip) < reach for tip in ends):
                continue
            ys.add(y)
    crowded = set()
    for tip, step in zip(ends, (1, -1)):
        crowded |= _end_stations(tip, step)
    ys |= crowded

    out = []
    for y in sorted(ys):
        if not ends[0] - SECTION_OVERRUN <= y <= ends[1] + SECTION_OVERRUN:
            continue
        gap = END_STEP if out and y in crowded and out[-1] in crowded else SECTION_GAP
        if not out or y - out[-1] >= gap:
            out.append(y)
    return out


@functools.cache
def back_form(inset, lift, corner_inset=0.0):
    """The back's outer surface as a solid, or with inset and lift, its cavity.

    A loft rather than a prism cut to shape, so the rounding on the long bottom
    edges follows the taper instead of only existing where the case is deepest.
    corner_inset offsets the round vertically for an inner cavity. It is also why
    there is no fillet in this model: intersecting a prism with a contour leaves
    degenerate zero-length edges along the bottom, and OCC will not fillet across
    those at any radius.

    Each section is as wide as the plan profile is at that point, not as wide as
    the case. The round then lands tangent to the wall the whole way round,
    including where the plan turns its corners, rather than only on the straight
    sides: a full-width section meets a corner wall part way up its round, and
    that is the abrupt edge the ends used to carry.
    """
    ys = _contour_samples()
    top = SHELL_FRONT + 10
    sections = []
    for i, y in enumerate(ys):
        depth = contour_depth(y) - lift
        center, half = _plan_chord(inset, y)
        half += _plan_bias(inset, ys, i)
        radius = max(
            min(
                back_edge_radius(y) - corner_inset,
                half - 0.01,
                (top + depth) / 2 - 0.01,
            ),
            0.4,
        )
        plane = Plane(
            origin=(center, y, (top - depth) / 2),
            x_dir=(1, 0, 0),
            z_dir=(0, -1, 0),
        )
        sections.append(plane * RectangleRounded(2 * half, top + depth, radius))
    # Ruled, not smooth. A smooth loft overshoots between sections, which put the
    # body 1.26 wider than its own sections on one side and left it failing to
    # intersect the plan prism at all.
    return loft(sections, ruled=True)
