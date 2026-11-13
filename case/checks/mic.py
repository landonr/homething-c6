"""Mic fillet: the inlet is the one continuous funnel it is described as, bell
at the recess floor it arrives in and throat at the board, with a real cone between them
rather than a straight bore. Probed by bisecting for the true opening radius at
several heights up each band, the same reasoning as wheel seat clearance: a
mouth referenced to the wrong face, or one cut entirely above the floor, removes
nothing and leaves an inlet the aperture probe still reads as open, and a taper
dropped from the fuse leaves the same. Several heights per band rather than one
because the ends of a band cannot tell an arc from a cone or from the plain bore
either might have been built as, and the middle can.
"""

import math

import case

from .common import (
    CROP_MARGIN,
    OpeningNotFound,
    Problem,
    _Crop,
    _opening_crop,
    _opening_radius,
)

MIC_DUCT_WALL_MIN = 0.5
"""Thinnest the mic duct's wall may be left where the mouth has widened the bore
into it. The duct is a free-standing printed post in the cavity, so what bounds
MIC_MOUTH_D against MIC_DUCT_OD is the post surviving the print rather than
anything acoustic. The mouth is the only height that answers to this: the bore
narrows all the way down from there, so by the throat it takes almost none of the
post at all."""

MIC_RADIUS_TOLERANCE = 0.05
"""How closely the inlet's measured radius has to match case.mic_profile_r()
at the same height. Float slop over _opening_radius' own probe width, not a
design margin."""

MIC_SEARCH_LO = 0.0
MIC_SEARCH_HI = 3.0
"""Bounds the inlet's opening radius is bisected between, narrower than
_opening_radius' own wheel-sized defaults because this is a funnel a few
millimetres across. Named rather than left inline because the crop the
bisection reads against is cut over exactly this span, and a crop that did not
cover the whole search would be a probe reading open air beyond its own edge.
The high bound is comfortably outside anything the funnel can legitimately open
to, so a bore that has gone wrong reads as the bound itself and fails loudly
rather than converging on a plausible wrong number."""

MIC_TAPER_FRACTIONS = (0.2, 0.4, 0.6, 0.8)
"""Where up the taper the opening is probed, as fractions of the cone's own run
from BOARD_TOP to the fillet band's base. What each has to tell apart is the cone
from the plain bore the run would be if the cone were dropped from the fuse, and
the cone stands clear of that by several times MIC_RADIUS_TOLERANCE at all four.
The margin grew with the taper: the throat came down onto the board's own drill,
so the cone's radial run is most of the bell's width now rather than a quarter of
it.

The two lowest are also what catch the other way this cone can be lost, which is
a duct built hollow rather than solid. A tube's own straight bore is subtracted
before the funnel is cut, so it flattens the taper everywhere it is the wider of
the two, which is the bottom of the run: the upper fractions sit above where any
sensible tube bore would reach and cannot see it happen.

The bottom of the run is left out because nothing there could tell them apart:
the taper *is* the throat where it meets the board, by construction, so the two
agree exactly and only diverge with height. The top is left out for the opposite
reason, that the fillet band's own base probe already sits there."""

MIC_FILLET_FRACTIONS = (0.0, 0.5, 0.75)
"""Where up the fillet band the opening is probed, as fractions of the band's
own height. The base is included as the junction rather than as proof of the
arc: the arc, the taper carried straight on and a plain bore all agree there,
which is exactly what makes it worth reading, since a mouth cut on the wrong
reference does not. The two above it are what prove the arc, and what they have
to tell it from is the taper continued straight to the mouth.

They clear MIC_RADIUS_TOLERANCE by about twice over, not the wide margin they
had when the bore below the band ran straight: the band shares its radial room
with the taper now, so it is shorter, and an arc and a chamfer across a short
band are never far apart. The taper's own fractions carry the weight instead,
having a long run to diverge over.

The top of the band is not among them. See MIC_MOUTH_STANDOFF."""

MIC_MOUTH_STANDOFF = 0.05
"""How far below case.mic_face() the topmost probe sits, absolute rather than a
fraction of the fillet band, which is the point of it: a probe centred on the
face would have half its own height standing in the open pocket above it and
could never read half full, so the bisection would report the inlet open out to
its search bound. On the +x ray the floor cuts the band about level with
mic_face(), so this keeps the whole probe, half height included, about 0.02
below that edge and in the band's built material. A fraction was this once and
stopped serving, the band having got short enough that the same fraction no
longer clears the probe's own height. mic_mouth_edge reads the edge itself."""

MIC_EDGE_BEARINGS = 12
"""Bearings round the port that mic_mouth_edge reads, every 30 degrees. The
floor's rise across the mouth is a tilt along y, so +y, where the old mouth
left its step, and -y, where the floor cut into the old fillet, are both
among them."""

MIC_EDGE_OUTER_STANDOFF = 0.06
"""How far outside case.mic_floor_edge_r() the floor reading sits. The edge
moves under 0.01 with bearing, so this is clear of it everywhere. It must stay
well inside case.mic_mouth_r(), because the old step stood at that radius and
a reading past it sees the intact floor whatever the band does."""

MIC_EDGE_INNER_STANDOFF = 0.15
"""How far inside case.mic_floor_edge_r() the band reading sits. There the band
is about 0.03 below the floor, three times MIC_EDGE_TOLERANCE, so a reading
that found the floor instead of the band cannot pass as the band."""

MIC_EDGE_TOLERANCE = 0.01
"""How closely each top hit has to match the surface it should land on. The
built floor stays within 0.001 of face_floor_at() round the port and the
lofted band within 0.0001 of mic_band_point(). This is about a ninth of the old
step on the +y side, so a step of that size cannot pass."""

MIC_EDGE_RAY_HALF = 0.3
"""Half height of each vertical ray, about case.mic_face(). It must clear the
floor's rise across the mouth, under 0.1, and the band's sink below the floor
at the inner reading."""


def mic_fillet(front):
    """The inlet is one funnel from the board's port to the second recess's own
    floor: a real cone up most of it and a real concave fillet finishing it
    there.

    The floor is dished rather than flat, so the taper and the band's base hang
    off case.mic_face(), the floor directly over the port. The band's upper part
    rides the floor, so its radius at a height depends on bearing. Every probe
    walks the +x ray, so each reads against case.mic_profile_r(z, 0.0).
    mic_mouth_edge proves where the band meets the floor.

    Probed on the built shell by bisecting for the true opening radius at each
    height, the same reasoning as wheel_seat_clearance: a mouth cut on the wrong
    reference, or one whose cut landed entirely above the face and removed
    nothing, still leaves an inlet a plain aperture probe reads as open, and
    every number describing it still looks right on paper. The taper answers to
    this too, and to more besides: its cone is fused into the same cut across a
    stub and an overrun, so it is the part of the inlet that can fail by having
    been discarded from the fuse rather than by being the wrong size, and either
    way what is left is a straight bore the aperture probe is just as happy
    with.

    Each reading is compared against case.mic_profile_r() at the same height,
    which is the curve case.mic_bore() is cut from rather than a second
    description of it. So the pass proves the boolean produced that curve, not
    that two formulas agree: perturb the solid and the probes disagree with it,
    which is exactly what a rebuilt mouth of the wrong width does.

    A probe's crossing lands on its own centre height rather than being
    smeared across its span, the opening radius being monotonic in z over the
    whole funnel, so the finite probe height costs nothing in accuracy anywhere
    except at the mouth itself. See MIC_MOUTH_STANDOFF for what is done there.

    A site where the bisection never met material at all is reported as one
    unmeasurable site and the remaining sites are still read, the same way
    wheel_seat_clearance handles it. Letting OpeningNotFound out instead would
    be honest but needlessly coarse: it is exactly the shape a broken inlet
    takes, one or two low sites with no duct wall left around them, so the first
    of them would abort the pass and take with it the duct wall problem, every
    site above it, and the sited lines the viewer draws from. The failure that
    stops a pass dead is the one nobody can place; this one knows its own height
    and its own band, so it says so and the pass carries on to say what else is
    wrong.

    Plus the wall the mouth leaves in the duct it is drilled through,
    arithmetic, which is the only thing bounding MIC_MOUTH_D against
    MIC_DUCT_OD.
    """
    problems = []
    left = case.mic_duct_wall_left()
    if left < MIC_DUCT_WALL_MIN:
        problems.append(
            f"mouth leaves {left:.2f} of duct wall, wants {MIC_DUCT_WALL_MIN:.2f}"
        )

    x, y = case.mic_port()
    r = case.mic_fillet_r()
    base = case.mic_taper_top()
    run = base - case.BOARD_TOP

    heights = [
        (f"{f:.0%} up the taper", case.BOARD_TOP + f * run)
        for f in MIC_TAPER_FRACTIONS
    ]
    heights += [(f"{f:.0%} up the fillet", base + f * r) for f in MIC_FILLET_FRACTIONS]
    heights.append(("just below the mouth", case.mic_face() - MIC_MOUTH_STANDOFF))

    # One crop of the shell for all eight sites, cut before any of them is read.
    # Every probe stands on the duct's own axis between the same two search
    # bounds, so the whole set lives in one small box from the lowest height to
    # the highest, and cutting that box once turns a hundred and sixty readings
    # against the built front's ten thousand faces into a hundred and sixty
    # against a few dozen. It changes nothing about where or how wide anything
    # is probed, only what the probe is intersected with, and the crop refuses
    # outright any probe it does not wholly contain: a site that wandered
    # outside it would stop the pass rather than quietly read the funnel open.
    zs = [z for _, z in heights]
    crop = _opening_crop(front, x, y, min(zs), max(zs), MIC_SEARCH_LO, MIC_SEARCH_HI)

    for where, z in heights:
        want = case.mic_profile_r(z, 0.0)
        try:
            got = _opening_radius(
                front, x, y, z, lo=MIC_SEARCH_LO, hi=MIC_SEARCH_HI, crop=crop
            )
        except OpeningNotFound as missing:
            problems.append(f"inlet unmeasurable {where} at z={z:.2f}: {missing}")
            continue
        if abs(got - want) > MIC_RADIUS_TOLERANCE:
            problems.append(
                f"inlet opens {2 * got:.2f} {where} at z={z:.2f}, wants "
                f"{2 * want:.2f}"
            )
    return problems


def mic_mouth_edge(front):
    """The mouth meets the recess floor in one edge all the way round, with no
    step.

    On each of MIC_EDGE_BEARINGS bearings a vertical ray reads the built
    front's top surface twice. MIC_EDGE_OUTER_STANDOFF outside
    case.mic_floor_edge_r() the top hit must be the floor, face_floor_at().
    MIC_EDGE_INNER_STANDOFF inside it the top hit must be the fillet band,
    case.mic_band_point() at that radius, and below the floor. A band top that
    stands below the floor leaves a step, and the outer reading then lands on
    the band instead of the floor. A floor that runs on in past the edge fails
    the inner reading.
    """
    x0, y0 = case.mic_port()
    edge = case.mic_floor_edge_r()
    r, mouth = case.mic_fillet_r(), case.mic_mouth_r()
    z_mid = case.mic_face()
    z_hi, z_lo = z_mid + MIC_EDGE_RAY_HALF, z_mid - MIC_EDGE_RAY_HALF
    reach = edge + MIC_EDGE_OUTER_STANDOFF
    crop = _Crop(
        front,
        (x0 - reach - CROP_MARGIN, y0 - reach - CROP_MARGIN, z_lo - CROP_MARGIN),
        (x0 + reach + CROP_MARGIN, y0 + reach + CROP_MARGIN, z_hi + CROP_MARGIN),
    )
    def top_hit(rho, theta):
        x, y = x0 + rho * math.cos(theta), y0 + rho * math.sin(theta)
        runs = crop.ray_runs((x, y, z_hi), (x, y, z_lo))
        return x, y, (z_hi - runs[0][0] if runs else None)

    problems = []
    inner = edge - MIC_EDGE_INNER_STANDOFF
    phi_in = math.acos((mouth - inner) / r)
    for i in range(MIC_EDGE_BEARINGS):
        theta = 2 * math.pi * i / MIC_EDGE_BEARINGS
        bearing = math.degrees(theta)

        rho = edge + MIC_EDGE_OUTER_STANDOFF
        x, y, got = top_hit(rho, theta)
        want = case.face_floor_at(x, y)
        if got is None or abs(got - want) > MIC_EDGE_TOLERANCE:
            seen = "no material" if got is None else f"top at z={got:.3f}"
            problems.append(
                Problem(
                    f"mic mouth edge at bearing {bearing:.0f}: {seen} at rho "
                    f"{rho:.3f} outside the edge, wants the floor at z={want:.3f}",
                    at=(x, y, want),
                )
            )

        _, band_z = case.mic_band_point(phi_in, theta)
        x, y, got = top_hit(inner, theta)
        floor = case.face_floor_at(x, y)
        if got is None or abs(got - band_z) > MIC_EDGE_TOLERANCE:
            seen = "no material" if got is None else f"top at z={got:.3f}"
            problems.append(
                Problem(
                    f"mic mouth edge at bearing {bearing:.0f}: {seen} at rho "
                    f"{inner:.3f} inside the edge, wants the fillet band at "
                    f"z={band_z:.3f}",
                    at=(x, y, band_z),
                )
            )
        elif floor - got <= MIC_EDGE_TOLERANCE:
            problems.append(
                Problem(
                    f"mic mouth edge at bearing {bearing:.0f}: fillet band at "
                    f"z={got:.3f} at rho {inner:.3f} is not below the floor at "
                    f"z={floor:.3f}, wants it more than {MIC_EDGE_TOLERANCE:.3f} below",
                    at=(x, y, got),
                )
            )
    return problems
