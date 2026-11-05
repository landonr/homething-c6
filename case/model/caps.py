"""The rigid keycaps: the four widths each one is built from, and the cap
itself, body through the face hole with a flange riding the counterbore
behind it."""

import math

from build123d import Pos, RectangleRounded, fillet, loft

import board
import cache
import params

from .keypad import face_floor_at, face_floor_over, face_plan_margin, key_size
from .legends import legend_solids
from .shape import _cut, _fuse, _rounded_prism, _squircle_points, _squircle_prism
from .stack import CAP_BOTTOM, COUNTERBORE_TOP, MERGE, cap_top, front_face, stem_top


def _key_prism(x, y, size, z0, z1):
    """The keycap plan shape at one size: a superellipse of KEY_SQUIRCLE_N, the
    caps' own exponent, lower than the recesses' KEYPAD_SQUIRCLE_N so the flanks
    bow out further.

    The one place the cap's plan shape is stated. Everything in the chain goes
    through it at a different size, the cap body and its flange here and the
    counterbore and face hole that shells.py cuts, so all four are the same
    curve scaled and the fits between them keep their meaning.
    """
    return _squircle_prism(
        x, y, size, params.KEY_SQUIRCLE_N, params.KEY_SQUIRCLE_POINTS, z0, z1
    )


def cap_outline(size, x=0.0, y=0.0):
    """The keycap plan curve at one size, as points. What _key_prism() extrudes,
    exposed so check.py can measure the fits between two of them around the
    whole perimeter rather than trusting the axis figure they are stated at."""
    half = size / 2
    return _squircle_points(
        x, y, half, half, params.KEY_SQUIRCLE_N, params.KEY_SQUIRCLE_POINTS
    )


def cap_flat(ref):
    """Side of the largest axis-aligned square that fits on this cap's top,
    which is what a legend has to fit inside.

    A superellipse's own inscribed square touches it on the diagonals, where
    |x| = |y| = half * 2^(-1/n), so the side is the cap body times that factor.
    Exact for the shape _key_prism() builds, where the number this replaced was
    a proxy: the rounded square's flat run, its side less twice the corner
    radius, which stopped off the curvature entirely and so understated the room
    by a wide margin. There is no straight run at all on a superellipse, so that
    proxy could not carry over even in principle.

    Tracks KEY_SQUIRCLE_N rather than the recesses' exponent, so lowering the
    caps' one to bow their flanks out costs top here and the ink pass sees it.
    """
    return cap_body(ref) * 2 ** (-1 / params.KEY_SQUIRCLE_N)


def cap_refs():
    """The switches that take a cap, in board order. All eleven now."""
    return board.refs("SW")


# Four widths, each derived from the one above it, so key_size() is the only
# place the grid pitch has to be reasoned about.
def cap_flange(ref):
    """Outside of the flange at a cap's base. Drawn in from the key size so that
    the counterbore around it lands back on the keytop footprint."""
    return key_size(ref) - 2 * params.CAP_FLANGE_TRIM


def cap_counterbore(ref):
    """The recess sunk into the ceiling for the flange to ride in."""
    return cap_flange(ref) + 2 * params.CAP_FLANGE_CLEARANCE


def cap_face_hole(ref):
    """The hole through the face land. Narrower than the flange by
    CAP_FLANGE_OVERLAP a side, which is what makes the cap captive."""
    return cap_flange(ref) - 2 * params.CAP_FLANGE_OVERLAP


def cap_body(ref):
    """The visible part of a cap, which stands in the face hole and is guided
    straight by it."""
    return cap_face_hole(ref) - 2 * params.CAP_GUIDE_CLEARANCE


def _face_surface_z(px, py, fdm):
    """The z of a front's outer face at (px, py) before any key hole: the flat
    FDM face, or face_floor_at() on the recessed front."""
    return front_face(True) if fdm else face_floor_at(px, py)


def cap_face_hole_lead_in(ref, fdm=False):
    """The triangles of the lead-in cutter around this cap's face hole, as
    [(wall, (a, b, c))] with each corner a case-frame point.

    The cutter is a triangular tube on three rings of KEY_SQUIRCLE_POINTS
    points. Each point takes the face height at its own plan position. The low
    ring is on the face hole outline, CAP_FACE_HOLE_CHAMFER times the tangent of
    CAP_FACE_HOLE_CHAMFER_ANGLE below the face. The high ring is on the same
    outline, MERGE above the face. The outer ring is the outline scaled out to
    CAP_FACE_HOLE_CHAMFER wider a side on the axes, also MERGE above the face.

    The "slope" wall joins the low ring to the outer ring, and it is the only
    wall that cuts the face. The "bore" and "lid" walls close the tube. Each
    quad splits on the diagonal from its first low point, because under a dish
    its four corners are not coplanar.

    front_shell() cuts all of these triangles, and counterbore_land_at() reads
    the slope wall off the same ones, so the land arithmetic and the cut cannot
    disagree.
    """
    x, y = board.components()[ref][:2]
    size = cap_face_hole(ref)
    amount = params.CAP_FACE_HOLE_CHAMFER
    depth = amount * math.tan(math.radians(params.CAP_FACE_HOLE_CHAMFER_ANGLE))
    inner_xy = cap_outline(size, x, y)
    outer_xy = cap_outline(size + 2 * amount, x, y)
    low = [(px, py, _face_surface_z(px, py, fdm) - depth) for px, py in inner_xy]
    high = [(px, py, _face_surface_z(px, py, fdm) + MERGE) for px, py in inner_xy]
    outer = [(px, py, _face_surface_z(px, py, fdm) + MERGE) for px, py in outer_xy]

    triangles = []
    count = len(inner_xy)
    for i in range(count):
        j = (i + 1) % count
        for wall, (a, b, c, d) in (
            ("bore", (low[i], low[j], high[j], high[i])),
            ("lid", (high[i], high[j], outer[j], outer[i])),
            ("slope", (low[i], low[j], outer[j], outer[i])),
        ):
            triangles.append((wall, (a, b, c)))
            triangles.append((wall, (a, c, d)))
    return triangles


def _lead_in_slope_z(ref, px, py, fdm=False):
    """The z of the lead-in's slope wall over (px, py), interpolated on the
    triangle of cap_face_hole_lead_in() that holds the point in plan. None where
    no slope triangle is over the point, which is inside the face hole or
    outside the lead-in."""
    for wall, (a, b, c) in cap_face_hole_lead_in(ref, fdm):
        if wall != "slope":
            continue
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-12:
            continue
        wa = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / det
        wb = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / det
        wc = 1.0 - wa - wb
        if min(wa, wb, wc) >= -1e-9:
            return wa * a[2] + wb * b[2] + wc * c[2]
    return None


LAND_SIDES = (("+x", 1, 0), ("-x", -1, 0), ("+y", 0, 1), ("-y", 0, -1))
"""The four axis sides of a key that its land ring is read on."""


def counterbore_land_sites(ref):
    """[(side, x, y)] on the land ring's mid-line, one on each axis side.

    The land ring is the face between the face hole and the counterbore wall,
    (cap_counterbore - cap_face_hole)/2 wide a side. Its mid-line is half that,
    (cap_counterbore - cap_face_hole)/4, out from the face hole edge.
    counterbore_land() reads its arithmetic here, and the checks probe the built
    shells at the same points. All four sides, because a dish slopes across a
    key and so one side is thinner than the others.
    """
    x, y = board.components()[ref][:2]
    r = (cap_face_hole(ref) + cap_counterbore(ref)) / 4
    return [(side, x + sx * r, y + sy * r) for side, sx, sy in LAND_SIDES]


def counterbore_land_at(ref, px, py, fdm=False):
    """Land at one plan point over this cap's counterbore: the built top surface
    there less COUNTERBORE_TOP. The top is the lower of the outer face and the
    face-hole lead-in's slope wall, where that wall reaches the point."""
    top = _face_surface_z(px, py, fdm)
    slope = _lead_in_slope_z(ref, px, py, fdm)
    if slope is not None:
        top = min(top, slope)
    return top - COUNTERBORE_TOP


def counterbore_land(ref, fdm=False):
    """Thinnest face land over this cap's counterbore shoulder, as the lower of
    two readings, each less COUNTERBORE_TOP.

    The first is the lowest the outer face gets anywhere over the counterbore's
    square, from face_floor_over(). It covers the dish and the face's own fall:
    on the key at a dish's centre that is the dish's full depth, and toward the
    side walls the face can be lower than a shallow dish floor. It ignores the
    key's own holes.

    The second is counterbore_land_at() on the land ring's mid-line, at the
    four counterbore_land_sites(). That reading counts the face-hole lead-in, on
    the triangles that front_shell() cuts. The lead-in cuts deepest at the hole
    edge, so a lead-in that reaches the mid-line shows here first.

    `fdm` reads the FDM front, whose face is flat at FDM_FACE and carries the
    same lead-in.

    Here rather than in keypad.py because the counterbore's own width comes off
    the cap chain above, and keypad.py cannot import this module without a
    cycle.
    """
    x, y = board.components()[ref][:2]
    if fdm:
        face = front_face(True)
    else:
        face = face_floor_over(x, y, cap_counterbore(ref) / 2)
    ring = min(
        counterbore_land_at(ref, px, py, fdm)
        for _, px, py in counterbore_land_sites(ref)
    )
    return min(face - COUNTERBORE_TOP, ring)


def counterbore_dish_margin(ref):
    """Recess left in plan between this cap's counterbore and the merged rim.
    Negative would put the rim through the hole, which is the failure a
    superellipse inscribed in the coverage box would produce at the four corner
    keys."""
    x, y = board.components()[ref][:2]
    return face_plan_margin(x, y, cap_counterbore(ref) / 2)


def cap_proud(ref):
    """How far a cap's top stands above the built face at its own centre.
    cap_top() is CAP_PROTRUSION above the undished face there, so this is
    CAP_PROTRUSION plus how far the dish sinks below that face. The
    dish is shallower away from the centreline, so a cap in an outer column
    stands a little less proud of its dish than a cap on the centreline."""
    x, y = board.components()[ref][:2]
    return cap_top(ref) - face_floor_at(x, y)


@cache.solid
def keycap(ref, legend=True):
    """One rigid cap, built where its switch is rather than at the origin.

    Two widths outside. The body stands in the face hole and is guided straight
    by it; the flange at the base is wider than that hole and rides a counterbore
    behind it, so the cap is captive. Inside is the locating recess over the
    stem: an interference bore on the flats and a lead-in at the mouth.

    Retention is the flange, not the stem. A cap goes in from inside the shell
    and cannot come out through the face, so swapping one means opening the case.

    `legend=False` builds the same cap with its top left blank. The export
    writes it as the `-blank` cap STL. check.py also asks for it, so it can
    weigh a cap against its own blank and read how much the deboss actually
    removed, rather than intersecting the finished cap with the solids that are
    no longer in it.
    """
    x, y, _, _ = board.components()[ref]
    bore = params.STEM_W - 2 * params.STEM_GRIP
    radius = max(params.STEM_R - params.STEM_GRIP, 0.2)
    lead = params.SOCKET_LEAD

    top = cap_top(ref)
    body = _key_prism(x, y, cap_body(ref), CAP_BOTTOM, top)
    top_edges = [
        edge
        for edge in body.edges()
        if edge.bounding_box().min.Z > top - 0.01
    ]
    if not top_edges:
        raise ValueError(f"{ref}'s cap has no top perimeter edges to fillet")
    body = fillet(top_edges, params.CAP_TOP_FILLET)
    flange = _key_prism(
        x, y, cap_flange(ref), CAP_BOTTOM, CAP_BOTTOM + params.CAP_FLANGE_T
    )
    # The taper's rise is capped at half the recess rather than run over the
    # full SOCKET_LEAD: at the old socket depth the lead was a sliver of a long
    # bore, but the recess is only stem_top() - CAP_BOTTOM deep now, and running
    # the whole lead in Z would taper right through it and leave no straight
    # bore for STEM_GRIP to interfere against at all. The radial width stays
    # the full lead, so it still funnels the same amount and still costs
    # CAP_WALL the same, only the rise to get there is steeper.
    engagement = stem_top(ref) - CAP_BOTTOM
    lead_z = min(lead, engagement / 2)
    socket = _rounded_prism(x, y, bore, radius, CAP_BOTTOM - MERGE, stem_top(ref))
    mouth = loft(
        [
            Pos(x, y, CAP_BOTTOM - MERGE)
            * RectangleRounded(bore + 2 * lead, bore + 2 * lead, radius + lead),
            Pos(x, y, CAP_BOTTOM)
            * RectangleRounded(bore + 2 * lead, bore + 2 * lead, radius + lead),
            Pos(x, y, CAP_BOTTOM + lead_z) * RectangleRounded(bore, bore, radius),
        ],
        ruled=True,
    )
    marks = legend_solids(ref, x, y) if legend else []
    return _cut(_fuse(body, flange), socket, mouth, *marks)
