"""The rigid keycaps: the four widths each one is built from, and the cap
itself, body through the face hole with a flange riding the counterbore
behind it."""

from build123d import Pos, RectangleRounded, loft

import board
import cache
import params

from .keypad import face_depth_at, face_depth_over, face_plan_margin, key_size
from .legends import legend_solids
from .shape import _cut, _fuse, _rounded_prism, _squircle_points, _squircle_prism
from .stack import CAP_BOTTOM, CAP_TOP, COUNTERBORE_TOP, MERGE, SHELL_FRONT, STEM_TOP


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
# place a screw boss or the grid pitch has to be reasoned about.
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


def counterbore_land(ref):
    """Ceiling left between this cap's counterbore shoulder and the recess
    floor above it, at the deepest point the recess reaches anywhere over that
    counterbore.

    The land is a function of position now that the floor is curved, so this is
    the worst case rather than one reading: what a cap's flange is caught by is
    the thinnest bit of face over its own bore, and on the key at a dish's
    centre that is the dish's full depth.

    Here rather than in keypad.py because the counterbore's own width comes off
    the cap chain above, and keypad.py cannot import this module without a
    cycle.
    """
    x, y = board.components()[ref][:2]
    depth = face_depth_over(x, y, cap_counterbore(ref) / 2)
    return SHELL_FRONT - depth - COUNTERBORE_TOP


def counterbore_dish_margin(ref):
    """Recess left in plan between this cap's counterbore and the merged rim.
    Negative would put the rim through the hole, which is the failure a
    superellipse inscribed in the coverage box would produce at the four corner
    keys."""
    x, y = board.components()[ref][:2]
    return face_plan_margin(x, y, cap_counterbore(ref) / 2)


def cap_proud(ref):
    """How far a cap's top stands above the recess floor immediately around it.
    CAP_TOP is flush with the flat face by construction, so this is just the
    local depth of the recess at the switch."""
    x, y = board.components()[ref][:2]
    return CAP_TOP - (SHELL_FRONT - face_depth_at(x, y))


@cache.solid
def keycap(ref, legend=True):
    """One rigid cap, built where its switch is rather than at the origin.

    Two widths outside. The body stands in the face hole and is guided straight
    by it; the flange at the base is wider than that hole and rides a counterbore
    behind it, so the cap is captive. Inside is the locating recess over the
    stem: an interference bore on the flats and a lead-in at the mouth.

    Retention is the flange, not the stem. A cap goes in from inside the shell
    and cannot come out through the face, so swapping one means opening the case.

    `legend=False` builds the same cap with its top left blank. Only check.py
    asks for that, so it can weigh a cap against its own blank and read how
    much the deboss actually removed, rather than intersecting the finished
    cap with the solids that are no longer in it.
    """
    x, y, _, _ = board.components()[ref]
    bore = params.STEM_W - 2 * params.STEM_GRIP
    radius = max(params.STEM_R - params.STEM_GRIP, 0.2)
    lead = params.SOCKET_LEAD

    body = _key_prism(x, y, cap_body(ref), CAP_BOTTOM, CAP_TOP)
    flange = _key_prism(
        x, y, cap_flange(ref), CAP_BOTTOM, CAP_BOTTOM + params.CAP_FLANGE_T
    )
    # The taper's rise is capped at half the recess rather than run over the
    # full SOCKET_LEAD: at the old socket depth the lead was a sliver of a long
    # bore, but the recess is only STEM_TOP - CAP_BOTTOM deep now, and running
    # the whole lead in Z would taper right through it and leave no straight
    # bore for STEM_GRIP to interfere against at all. The radial width stays
    # the full lead, so it still funnels the same amount and still costs
    # CAP_WALL the same, only the rise to get there is steeper.
    engagement = STEM_TOP - CAP_BOTTOM
    lead_z = min(lead, engagement / 2)
    socket = _rounded_prism(x, y, bore, radius, CAP_BOTTOM - MERGE, STEM_TOP)
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
