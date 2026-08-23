"""Caps fit: all eleven rigid caps clear the shell pressed and released, clear each
other, grip their stems, stay captive under the face land, and still go in from
inside. Every part of it is arithmetic the solids cannot show: a cap that grips
nothing still models cleanly, and a flange that would pull through its hole once
the cap sits off centre looks exactly like one that would not.

Caps flush: a cap's top lands level with the flat front face, not merely close
to it. CAP_TOP is SHELL_FRONT + CAP_PROTRUSION by construction and
CAP_PROTRUSION is 0, so this should always read as zero; it exists to catch
CAP_PROTRUSION drifting off zero without CAP_TOP following.

Caps proud of pocket: a cap stands proud of the recess floor around it by
exactly the recess's own local depth there, on top of landing flush with the
face, the same reasoning as caps flush applied to the dished floor instead of
the face.

Legends present: every cap carries a real legend, cut out of one solid cap,
in a glyph the vendored font actually has. A blank cap is the quietest
failure in the model: an empty entry, a mistyped SVG path or a character
DejaVu does not carry all build a cap that passes every other pass here,
the last of them as a .notdef box with more ink than a hyphen. Volume, cmap
coverage, the cut having landed and the ink fitting the flat top, because no
one of those covers the others.
"""

import math

from build123d import Pos
from fontTools.ttLib import TTFont

import board
import case
import params

from .common import TOLERANCE, _volume

CAP_GAP = 0.5
"""Closest two keytops may come in plan. Wider than a moulding needs, because the
caps are separate parts now: two of them out of tolerance in opposite directions
have to still miss each other, and a finger has to find the split."""
MIN_LOCATING_DEPTH = 0.3
"""Shallowest the stem's locating recess may be and still key a cap square in
plan. The recess no longer does the gripping, CAP_FLANGE_T does that in shear
against the face land, so this only has to be deep enough that the cap cannot
tip off the stem's flats before the flange catches it."""
SWAP_MARGIN = 0.1
"""Slack a cap needs on its way in, over the clearance the two holes already
carry. It goes in from inside now, body through the face hole and flange into
the counterbore, so a negative here is a cap that cannot be fitted at all rather
than one that cannot be swapped."""
RETENTION_MIN = 0.3
"""Flange left over the face land with the cap pushed as far off centre as
CAP_GUIDE_CLEARANCE allows. This is the worst case that has to hold, so it is
what CAP_FLANGE_OVERLAP is really sized against."""
COUNTERBORE_RIB = 1.2
"""Thinnest rib of ceiling left between two counterbores. They are the widest
cut in the front plate and they sit at the grid pitch, so this is the front
plate's thinnest section anywhere."""
FLANGE_FLOAT_RANGE = (0.1, 0.5)
"""How far a cap may lift before its flange meets the shoulder. Too little and
tolerance turns the float into a clamp that stops the cap pressing; too much and
STEM_GRIP has more slop to take up than it can."""
TRAVEL_MARGIN = 0.2
"""How much further than SWITCH_TRAVEL a cap has to be able to move. It covers
the stack-up under the switch, which is SWITCH_HEIGHT and so is the least
trustworthy number in the model."""
PERIMETER_SAMPLES = 240
"""Points each cap curve is sampled at when the fits between them are measured
around the whole perimeter. Dense enough that the sampled minimum lands within a
thousandth of the true one at these radii."""

PERIMETER_TOLERANCE = 0.005
"""How far under its stated axis figure a fit may read around the curve before
it counts as a real shortfall. Sampling slop: two concentric similar
superellipses are exactly their axis gap apart at the closest point, so a
correct pair reads the axis figure to within the sample spacing."""

LEGEND_FLOOR = 0.5
"""Roof left under a legend. It is what the pad's backlight crosses, so it is
bounded by wanting to see through it as much as by strength."""


def caps_fit(front, pad, caps):
    """The nine rigid caps against the shell, each other, their stems and the two
    holes each one has to sit in.

    The cap-to-pad overlap is the fit, not a fault: the socket bore is one
    STEM_GRIP narrower than the stem per side, so the two solids are modelled
    interfering on purpose and it is a zero overlap that means a loose cap.
    """
    problems = []
    parts = board.components()

    for ref, cap in caps.items():
        fouled = _volume(front.intersect(cap))
        if fouled > TOLERANCE:
            problems.append(f"{ref}'s cap fouls the front shell by {fouled:.2f} mm3")
        pressed = Pos(0, 0, -params.SWITCH_TRAVEL) * cap
        fouled = _volume(front.intersect(pressed))
        if fouled > TOLERANCE:
            problems.append(f"{ref}'s cap fouls the front shell once pressed")
        if _volume(pad.intersect(cap)) <= TOLERANCE:
            problems.append(f"{ref}'s cap grips nothing: no interference with its stem")

    # A cap's visible width is its body: the flange is behind the face and is
    # answered for by the counterbore rib.
    tops = [
        (ref, *parts[ref][:2], case.cap_body(ref))
        for ref in board.refs("SW")
    ]
    for i, (a, ax, ay, asize) in enumerate(tops):
        for b, bx, by, bsize in tops[i + 1 :]:
            reach = (asize + bsize) / 2
            gap = max(abs(ax - bx) - reach, abs(ay - by) - reach)
            if gap < CAP_GAP:
                problems.append(f"{a} and {b} come within {gap:.2f} of each other")

    depth = case.STEM_TOP - case.CAP_BOTTOM
    if depth < MIN_LOCATING_DEPTH:
        problems.append(f"locating recess is only {depth:.2f} deep")

    float_ = case.COUNTERBORE_TOP - (case.CAP_BOTTOM + params.CAP_FLANGE_T)
    low, high = FLANGE_FLOAT_RANGE
    if not low <= float_ <= high:
        problems.append(f"flange floats {float_:.2f} under the counterbore shoulder")

    # The socket mouth, not the bore: SOCKET_LEAD opens it out on every side and
    # that is the widest the cap is ever hollowed.
    widest = (params.STEM_W - 2 * params.STEM_GRIP) + 2 * params.SOCKET_LEAD
    for ref in case.cap_refs():
        body = case.cap_body(ref)
        flange = case.cap_flange(ref)
        counterbore = case.cap_counterbore(ref)
        hole = case.cap_face_hole(ref)

        wall = (body - widest) / 2
        if wall < params.CAP_WALL:
            problems.append(f"{ref}'s cap is left {wall:.2f} of wall around its socket")

        # Retention, worst case: the body sits hard against one side of the face
        # hole and the flange has to still be caught on the other.
        held = (flange - hole) / 2 - params.CAP_GUIDE_CLEARANCE
        if held < RETENTION_MIN:
            problems.append(
                f"{ref}'s flange holds on {held:.2f} once the cap sits off centre"
            )

        # Insertion is from inside now, so both widths have to pass their own hole.
        if body > hole - 2 * SWAP_MARGIN:
            problems.append(f"{ref}'s cap body will not enter its face hole")
        if flange > counterbore - 2 * SWAP_MARGIN:
            problems.append(f"{ref}'s flange will not enter its counterbore")

        rib = case.key_pitch() - counterbore
        if rib < COUNTERBORE_RIB:
            problems.append(
                f"{ref}'s counterbore leaves {rib:.2f} of ceiling to its neighbour"
            )
        if counterbore > case.key_size(ref) + 2 * params.KEY_CLEARANCE:
            problems.append(f"{ref}'s counterbore reaches past what key_size() cleared")

        if params.STEM_W > hole - 2 * SWAP_MARGIN:
            problems.append(f"{ref}'s bare stem snags its hole with the cap off")

    # The flat top a legend has to fit in is checked in legends_present(), not
    # here: LEGENDS carries a per-entry size now, so comparing one LEGEND_SIZE
    # against every cap would test the wrong number on most of them, and a font
    # size is an em rather than an ink height in the first place.

    # CAP_PROTRUSION dropped out of this check: it is 0 by design now, and the
    # cap is meant to sink SWITCH_TRAVEL into its own face hole on a press
    # rather than stay proud of it. CAP_LIFT is the one travel budget left that
    # still has to clear the switch before anything else bottoms out.
    if params.CAP_LIFT < params.SWITCH_TRAVEL + TRAVEL_MARGIN:
        problems.append(
            f"CAP_LIFT is {params.CAP_LIFT:.2f} against "
            f"{params.SWITCH_TRAVEL:.2f} of travel"
        )

    roof = params.CAP_TOP_T - params.LEGEND_DEPTH
    if roof < LEGEND_FLOOR:
        problems.append(f"legends leave {roof:.2f} of roof to glow through")

    return problems


FACE_FLUSH_TOLERANCE = 0.01
"""How exactly a cap's top has to land on the flat front face. CAP_TOP is
SHELL_FRONT + CAP_PROTRUSION by construction and CAP_PROTRUSION is 0, so this
should read as zero; it is float slop, not a design margin, and a nonzero
reading means CAP_TOP stopped following SHELL_FRONT."""


def cap_fits_around_perimeter():
    """The three fits in the cap chain are no tighter anywhere around the plan
    curve than the axis figures they are stated at.

    caps_fit() does its retention and clearance arithmetic on widths, which is
    only the truth if the axis gap between two of these curves is also their
    closest approach. For concentric similar superellipses it is, and for the
    rounded squares this shape replaced it was too, but neither is obvious and
    the corner is where a plan shape change would break it: a superellipse pulls
    its corner in relative to a rounded square, and had that pulled the flange
    in faster than the hole it would have eaten the retention the caps hang on
    without moving a single number caps_fit() reads.

    Measured on the curves rather than on the built solids because it is the
    curves the arithmetic is about; the solids are covered by caps_fit()'s own
    volume probes against the shell.
    """
    problems = []
    for ref in case.cap_refs():
        widths = (
            ("flange past the face hole", case.cap_face_hole(ref), case.cap_flange(ref)),
            ("counterbore past the flange", case.cap_flange(ref), case.cap_counterbore(ref)),
            ("face hole past the cap body", case.cap_body(ref), case.cap_face_hole(ref)),
        )
        for what, small, large in widths:
            inner = case.cap_outline(small)
            outer = case.cap_outline(large)
            measured = min(
                min(math.hypot(px - qx, py - qy) for qx, qy in outer)
                for px, py in inner
            )
            axis = (large - small) / 2
            if measured < axis - PERIMETER_TOLERANCE:
                problems.append(
                    f"{ref}'s {what} closes to {measured:.3f} around the curve "
                    f"against {axis:.3f} on the axes: the width the fit is stated "
                    "at is no longer its worst case"
                )
    return problems


def caps_flush():
    """A cap's top has to land level with the flat front face, not merely close
    to it: CAP_TOP is SHELL_FRONT + CAP_PROTRUSION by construction. This is what
    would catch the two drifting apart, e.g. a future edit that gave CAP_TOP its
    own value instead of following SHELL_FRONT."""
    off = case.CAP_TOP - case.SHELL_FRONT
    if abs(off) > FACE_FLUSH_TOLERANCE:
        return [
            f"cap top {case.CAP_TOP:.3f} against face {case.SHELL_FRONT:.3f}, "
            f"off by {off:.3f}"
        ]
    return []


MIN_PROUD = 0.2
"""Least a cap may stand proud of the floor around it and still read as
standing in a dish rather than flush with a flat face. It falls out of the
recess depths rather than being designed to, so this is a floor to notice a
recess that got shallow enough to stop showing, not a target."""


def caps_proud_of_pocket():
    """A cap still lands flush with the face (caps_flush covers that), and now
    also has to stand proud of the recess floor immediately around it by
    exactly what face_depth_at() says the recess is worth there.

    Arithmetic, because case.CAP_TOP and the recess floor are both built off
    SHELL_FRONT by construction and the failure this catches is one of them
    stopping following it. Every cap, not one: the floor is curved now, so the
    number is different at every switch and a single reading would only prove
    it at whichever one was picked. The floor guard beside it is what catches a
    recess that quietly went flat.
    """
    problems = []
    for ref in case.cap_refs():
        x, y = board.components()[ref][:2]
        want = case.face_depth_at(x, y)
        proud = case.cap_proud(ref)
        if abs(proud - want) > FACE_FLUSH_TOLERANCE:
            problems.append(
                f"{ref}'s cap stands {proud:.3f} proud of its recess floor, "
                f"wants {want:.3f}"
            )
        if proud < MIN_PROUD:
            problems.append(
                f"{ref}'s cap stands only {proud:.2f} proud of its recess floor, "
                f"wants {MIN_PROUD:.2f}"
            )
    return problems


LEGEND_MIN_VOLUME = 0.2
"""Least a legend may take out of its cap and still be a legend. Comfortably
under the smallest one the current table sets, the minus at SW9, and
comfortably over the zero an entry resolving to no faces at all leaves. It
catches an empty string, an SVG whose paths imported as nothing, and a
legend cut somewhere other than the cap top; it does not catch a missing
glyph, which is what the cmap check beside it is for."""

LEGEND_INK_MARGIN = 0.2
"""Bare cap top left around a legend's ink, per side, inside the flat the
corner radius leaves. Measured against the built ink rather than against the
font size it was set at: LEGENDS' sizes are ems, and a glyph spends its em
anywhere from a tenth to three quarters, so the size alone says nothing about
whether the mark fits."""


def legends_present(caps):
    """Every cap carries a real legend, cut out of one solid cap.

    Four things, because each covers a way of shipping a blank or broken cap
    that the others miss.

    The ink has to be there at all: an entry that resolves to no faces, an
    empty string or an SVG whose paths imported as nothing, builds a
    perfectly good blank cap and no other pass in this file would notice.

    Every character of a string legend has to be in LEGEND_FONT's own cmap.
    Volume alone does not cover this: freetype maps a character the font
    does not carry onto .notdef, which DejaVu draws as a hollow box with
    several times the ink of the smallest legend here, so a missing glyph
    ships as a legend that passes a volume floor and reads as a rectangle.
    That is worth more care than usual now that SW5 carries a hollow box on
    purpose, U+25A1, which the font does have: the two would be told apart
    by nothing else in this file. Checked against the font file rather than
    the rendering for that reason.
    fontTools is build123d's own transitive dependency, through ezdxf, so
    it is present wherever this model builds at all.

    The cut has to have landed: each cap is weighed against the same cap
    built blank, so the number is what the deboss removed rather than what
    its own solids measure, and a cap has to come out as exactly one solid,
    which is what a legend reaching past the roof would break.

    And the ink has to fit the flat top the corner radius leaves, with
    LEGEND_INK_MARGIN around it.
    """
    font = TTFont(params.LEGEND_FONT)
    cmap = font.getBestCmap()

    problems = []
    for ref, cap in caps.items():
        spec, size = case.legend_entry(ref)
        if isinstance(spec, str):
            missing = sorted({c for c in spec if ord(c) not in cmap})
            if missing:
                names = ", ".join(f"U+{ord(c):04X}" for c in missing)
                problems.append(
                    f"{ref}'s legend {spec!r} wants {names}, which "
                    f"{params.LEGEND_FONT.name} does not carry: it would cut "
                    "a .notdef box"
                )

        # Weighed against the same cap built blank, so this is what the deboss
        # actually removed rather than what its solids measure. Not the same
        # number: the mic's four paths overlap each other by a fraction of a
        # millimetre so they read as one groove, and a legend whose solids sit
        # off the cap top entirely would measure full and remove nothing.
        cut = case.keycap(ref, legend=False).volume - cap.volume
        if cut < LEGEND_MIN_VOLUME:
            problems.append(
                f"{ref}'s legend takes {cut:.2f} mm3 out of the cap, wants "
                f"{LEGEND_MIN_VOLUME:.2f}: is the entry empty?"
            )

        solids = case.legend_solids(ref)
        if len(cap.solids()) != 1:
            problems.append(
                f"{ref}'s cap came out as {len(cap.solids())} solids, not one"
            )

        if solids:
            box = solids[0].bounding_box()
            for solid in solids[1:]:
                box = box.add(solid.bounding_box())
            flat = case.cap_flat(ref)
            reach = max(box.size.X, box.size.Y) + 2 * LEGEND_INK_MARGIN
            if reach > flat:
                problems.append(
                    f"{ref}'s legend ink is {box.size.X:.2f} x {box.size.Y:.2f} "
                    f"in {flat:.2f} of flat top, under {LEGEND_INK_MARGIN:.2f} "
                    "of margin"
                )
    return problems
