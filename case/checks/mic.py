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

import case

from .common import _opening_crop, _opening_radius

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
its search bound. That is inherent to the mouth being tangent to the floor
rather than an edge on it, and no finite probe resolves the last sliver of it. A
fraction was this once and stopped serving, the band having got short enough
that the same fraction no longer clears the probe's own height."""


def mic_fillet(front):
    """The inlet is one funnel from the board's port to the second recess's own
    floor: a real cone up most of it and a real concave fillet finishing it
    there.

    The floor is dished rather than flat, so the reference the whole funnel
    hangs off is case.mic_face(), the floor directly over the port, and the
    probes read against case.mic_profile_r() built on the same number. The
    floor rises away from the port across the mouth's own width, by well under
    a tenth, which the mouth's straight run past that height absorbs and which
    the topmost probe sits below.

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
        want = case.mic_profile_r(z)
        got = _opening_radius(
            front, x, y, z, lo=MIC_SEARCH_LO, hi=MIC_SEARCH_HI, crop=crop
        )
        if abs(got - want) > MIC_RADIUS_TOLERANCE:
            problems.append(
                f"inlet opens {2 * got:.2f} {where} at z={z:.2f}, wants "
                f"{2 * want:.2f}"
            )
    return problems
