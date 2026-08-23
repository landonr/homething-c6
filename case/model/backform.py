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


SECTION_GAP = 0.2
"""Closest two loft sections may sit. Sampling the taper and the rolled end
independently landed two 0.05 apart, and the sliver of a face between them was
enough to leave the loft unable to intersect anything."""

SECTION_OVERRUN = 3.0
"""How far the loft runs past the case. Ending it flush with the plan prism means
the two bodies share their end faces, and the intersection then fails outright."""


def _contour_samples():
    """Where to cut sections for the loft. Dense through the tapers and the rolled
    ends, sparse over the flats, because a section costs real time."""
    box = board.board_profile().bounding_box()
    lo, hi = cradle_span()
    over = params.BOARD_FIT + params.WALL
    ends = (box.min.Y - over, box.max.Y + over)
    b = params.CONTOUR_BLEND

    ys = {lo, hi, ends[0] - SECTION_OVERRUN, ends[1] + SECTION_OVERRUN, *ends}
    for start in (lo - b, hi):
        ys |= {start + b * i / 20 for i in range(21)}
    for tip, step in zip(ends, (1, -1)):
        ys |= {tip + step * params.CONTOUR_TIP_R * i / 10 for i in range(11)}

    out = []
    for y in sorted(ys):
        if ends[0] - SECTION_OVERRUN <= y <= ends[1] + SECTION_OVERRUN and (
            not out or y - out[-1] >= SECTION_GAP
        ):
            out.append(y)
    return out


@functools.cache
def back_form(inset, lift, radius):
    """The back's outer surface as a solid, or with inset and lift, its cavity.

    A loft rather than a prism cut to shape, so the rounding on the long bottom
    edges follows the taper instead of only existing where the case is deepest.
    It is also why there is no fillet in this model: intersecting a prism with a
    contour leaves degenerate zero-length edges along the bottom, and OCC will
    not fillet across those at any radius.

    Sections are the full case width, so its vertical sides land on the plan
    profile's own sides and the two bodies agree there.
    """
    box = board.board_profile().bounding_box()
    width = box.size.X + 2 * (params.BOARD_FIT + params.WALL) - 2 * inset
    top = SHELL_FRONT + 10
    sections = []
    for y in _contour_samples():
        depth = contour_depth(y) - lift
        plane = Plane(
            origin=(box.center().X, y, (top - depth) / 2),
            x_dir=(1, 0, 0),
            z_dir=(0, -1, 0),
        )
        sections.append(plane * RectangleRounded(width, top + depth, radius))
    # Ruled, not smooth. A smooth loft overshoots between sections, which put the
    # body 1.26 wider than its own sections on one side and left it failing to
    # intersect the plan prism at all.
    return loft(sections, ruled=True)
