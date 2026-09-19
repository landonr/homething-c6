"""Light path: the pad is genuinely open over each LED, the LED fires up into
the ring channel's void rather than into material, and the roof over the
channel is genuinely solid, so the light exits through case material rather
than into silicone or out an accidental hole. The moulded light-pipe ring
these passes once probed is gone: the pad no longer reaches over the LEDs at
all; the light pipe is the channel inside the shell now. The roof is measured
up to the local front-face floor, which the keypad recess dishes down where its
wheel dish's diagonals and both its necks cross the channel, rather than to any
one plane.

Led ring: the channel itself, on the built shell. Void all the way around
(one blocked sector and the ring shows as arcs, which is the failure the
feature exists to avoid), a solid web between it and the wheel opening's
bore, and a solid roof over it everywhere, including where the keypad recess
overlaps it in plan and the roof is at its thinnest. The inner wall is plumb, so
the web is a full LED_RING_WALL at every height and one probe standing mid-web
answers for all of it. The channel is measured rather than sampled at one
radius: a ray is cast out at each angle and the void between the web and
whatever closes in on it is read off the built shell. That matters because two
unrelated surfaces close the channel and they close it at different angles. The
outer wall closes it everywhere, and near the X axis the cavity wall chords it
off well inside that, by design. A probe at one radius asks for width
nothing built it with out there, which is what ROOF_FLAT_MIN is for instead: the
measured width has to clear it at every angle.

Wheel seat clearance: the shell's own wheel opening clears the housing
(board.wheel_profile()'s main_od) by WHEEL_OPENING_CLEARANCE, its own gap
rather than the pad's WHEEL_CLEARANCE, at every height there is shell to cut
the opening through, which is the ceiling underside up to the front face's own
dished floor over the seat and not up to the knob's peak; above that floor
there is no seat and rotation_clearance holds the claim instead. And the lip
stays clear of the ceiling in the first place. Replaces a claim that the shell's
opening had to match the lip so it could pass through on assembly, which
does not happen: the board is lowered into an already-closed front shell, so
the lip never transits the ceiling. Probed on the built shell by bisecting
for the true opening radius, not trusted from WHEEL_OPENING_R, because this
exact feature was once silently erased by a stale full-ceiling clearance cut
while the formulas behind it still looked right on paper.

Wheel rotation clearance: nothing of the pad or the front shell may intrude
inside the wheel's rotating envelope, at the lip's own clearance radius at and
below its top face and at the main body's clearance above it, where the shell's
opening now closes in flush.
"""

import math

import board
import case
import params
from build123d import Cylinder, Pos

from .common import (
    CROP_MARGIN,
    OPENING_PROBE_H,
    OPENING_PROBE_R,
    OPENING_SEARCH_LO,
    PROBE_D,
    RUN_MIN,
    TOLERANCE,
    OpeningNotFound,
    _Crop,
    _fill_fraction,
    _opening_crop,
    _opening_radius,
    _volume,
)


def light_path(shells, pad):
    """Each LED fires up through open air into the ring channel, and the roof
    over it is solid translucent shell.

    All three legs of the path: the pad's wheel cut genuinely uncovers the LED
    (probe the pad over the package and expect air, the inverse of the flange
    this replaced), the shell is genuinely open from the package top to the
    channel's own ceiling (the LED must fire into the void, not into the web or
    the ceiling outside the channel), and the roof is genuinely closed between
    there and the local face floor, the thinnest the face gets over an LED, so
    the light lands on case material rather than escaping through a hole that
    should not exist over an LED.
    """
    problems = _ring_stack_sane()
    if problems:
        return problems
    parts = board.components()
    z0 = params.BOARD_THICKNESS + params.LED_HEIGHT
    for ref in board.refs("D")[1:]:
        x, y, _, _ = parts[ref]
        opening = Pos(x, y, (z0 + case.PAD_WEB_TOP) / 2) * Cylinder(
            radius=PROBE_D / 2, height=case.PAD_WEB_TOP - z0
        )
        if _volume(pad.intersect(opening)) > TOLERANCE:
            problems.append(f"{ref} is still covered: silicone over it")

        # The package's own column, not its footprint: its outer edge sits under
        # the raked outer wall by design, because that rake is what the LEDs are
        # aimed at. See LED_RING_OVER.
        channel = Pos(x, y, (z0 + case.LED_RING_TOP) / 2) * Cylinder(
            radius=PROBE_D / 2, height=case.LED_RING_TOP - z0 - 0.02
        )
        if _volume(shells.intersect(channel)) > TOLERANCE:
            problems.append(f"{ref} fires into material: the channel is not open over it")

        floor = case.face_floor_at(x, y)
        roof = Pos(x, y, (case.LED_RING_TOP + floor) / 2) * Cylinder(
            radius=PROBE_D / 2, height=floor - case.LED_RING_TOP - 0.04
        )
        if _fill_fraction(shells, roof) < 0.99:
            problems.append(f"{ref} has no solid roof above the channel to shine through")
    return problems


WEB_PROBE_D = 0.2
"""Width of led_ring's web probe. Set when the channel's inner wall raked and
LED_RING_CHAMFER left only 0.4 of web down at the mouth, where PROBE_D could not
stand without hanging into the channel and reading a sound web as open. That
wall is plumb now and the web is a full LED_RING_WALL at every height, so this
reads the web's middle fifth and PROBE_D would fit with 0.25 either side."""

BAND_PROBE_GAP = 0.05
"""Standoff the void probe keeps off each wall of the channel it stands in. It
sets what counts as blocked: anything reaching further than this into the
measured width trips the probe. The probe is capped at PROBE_D regardless, so
this is live only where the channel runs narrower than PROBE_D plus twice it."""

VOID_FILL_MAX = 0.01
"""How much of the void probe may read as material before the channel counts as
blocked, as a fraction rather than the mm3 TOLERANCE. The probe is sized to the
width measured at its own angle, so it is not one fixed volume: a probe narrowed
to a third holds a ninth of the volume, and one absolute floor cannot mean the
same thing at both sizes. At the current geometry every probe comes out at the
full PROBE_D, so this reads the same as TOLERANCE would; it is the narrowed case
it exists for."""

ROOF_FLAT_MIN = 0.5
"""Narrowest the channel may run at the roof, where its walls are closest.

Two passes hold it. _ring_stack_sane() applies it to the section the ring is
revolved from, which is arithmetic and answers for the whole ring at once: the
inner wall is plumb and the outer one rakes 45 degrees over the full height, so
that flat is the mouth's outer radius less the height less the inner wall.
led_ring() then applies it again to the width it measures at each angle on the
built shell, which is the one that catches the cavity wall chording the channel
near the X axis, since no radius in the section knows about the clip.

A floor rather than a design target: the probes need somewhere to stand, and a
ring glowing through a slit narrower than this is not the ring the feature is
for. One value for both passes because both measure the same thing, the gap
between whatever two surfaces are closest at the roof."""

ROOF_LEFT_MIN = 0.5
"""Thinnest translucent roof the ring may glow through, wherever the keypad
recess crosses the channel. Bounded by the print, a roof this thin bridging a
void, rather than by anything optical: the shell diffuses better the thicker it
is, so nothing optical wants it near the floor."""

LED_RING_SAMPLES = 24
"""Angles sampled around the channel for led_ring: 15 degrees apart, a few
millimetres of arc at the channel's own radius, so anything blocking enough of
the ring to show as a dark sector is caught. The count was once justified by
the gap between the two keypad islands, a sector the ring had to survive; no
keypad recess reaches the channel at all now, so arc length is most of what it
answers to. The other half is the roof probe riding along with it: the rotary
recess thins the roof on the four diagonals and where each neck crosses, and 24
samples land on all of those exactly."""


RING_CROP_SECTORS = 4
"""How many crops of the shell led_ring cuts, each serving a run of consecutive
angles that then cut their own out of it.

Measured, not chosen. Every reading wants a crop small enough to be a handful
of faces, but cutting each of the 24 straight out of the built front costs
about 1.4 seconds of boolean apiece and dominates the pass. Cutting one crop
covering the whole ring and reading everything against that is far worse: the
box bounding the ring holds over half the shell's faces, because the wheel is
where the keypad recess crosses in plan, and 96 readings against 5284 faces
took three times as long as the per-angle crops did. Nesting is what wins. One
crop per quarter of the ring holds about 1400 faces, and an angle's crop comes
out of that for a fraction of what it costs out of the shell.

Four rather than more or fewer because the two costs pull opposite ways: every
extra sector is another cut against the whole front, and every sector dropped
makes all 24 angle cuts dearer. Two and four measure about the same and eight
is worse, so this sits on the flat of the curve rather than on a peak, and
LED_RING_SAMPLES can move a good way either side of 24 without stranding it."""


def _ring_crop_box(wx, wy, r_in, r_out, angles, z_lo):
    """The box holding every reading led_ring takes at `angles`: each angle's
    ray from `r_in` out to `r_out`, the widest probe that can stand anywhere on
    it, and margin, over the whole height from below the channel up past the
    front face. No face floor is above the undished face, so SHELL_FRONT tops it
    whatever the keypad recess does over the channel.

    One builder for both levels of the crop, which is what makes the nesting
    sound rather than merely plausible: a sector's box is this function over its
    own angles, so it is at least the union of its members' boxes by
    construction and contains every one of them. _Crop checks that anyway when
    it cuts a child out of a parent, and refuses rather than hand back a crop
    quietly missing the material outside its parent.
    """
    pad = PROBE_D / 2 + CROP_MARGIN
    xs = [wx + r * math.cos(a) for a in angles for r in (r_in, r_out)]
    ys = [wy + r * math.sin(a) for a in angles for r in (r_in, r_out)]
    return (
        (min(xs) - pad, min(ys) - pad, z_lo - CROP_MARGIN),
        (max(xs) + pad, max(ys) + pad, case.SHELL_FRONT + CROP_MARGIN),
    )


def _ring_stack_sane():
    """Arithmetic bounds the probes need before they can even be built: the
    channel's ceiling has to sit above its floor and far enough below the dished
    face that a roof is left, and the raked outer wall has to still leave a roof
    between itself and the plumb inner one, or the probe cylinders come out with
    non-positive heights or standing in material and the pass dies in build123d
    instead of reporting what went wrong."""
    problems = []
    if case.LED_RING_TOP <= case.CAVITY_FRONT + 0.1:
        problems.append(
            f"LED_RING_ROOF leaves no channel: ceiling {case.LED_RING_TOP:.2f} "
            f"against the cavity underside at {case.CAVITY_FRONT:.2f}"
        )
    if case.ring_roof_left() <= ROOF_LEFT_MIN:
        problems.append(
            f"the keypad recess leaves only {case.ring_roof_left():.2f} of roof "
            f"over the ring channel, wants {ROOF_LEFT_MIN:.2f}: the recess is "
            "deeper than LED_RING_ROOF can spend where the wheel dish's "
            "diagonals or a neck cross the channel"
        )
    if case.led_ring_roof_flat() <= ROOF_FLAT_MIN:
        problems.append(
            f"the channel's walls leave only {case.led_ring_roof_flat():.2f} of "
            f"roof flat between them, wants {ROOF_FLAT_MIN:.2f}: the outer wall "
            "rakes 45 degrees and so travels the channel's own height, and a "
            "taller channel or a narrower mouth closes the ring off at the top"
        )
    return problems


def _channel_width(crop, angle, z):
    """(inner, outer) radii of the channel's void at `angle`, height `z`, read
    off the built shell.

    One ray out from the wheel centre, from mid-web to led_ring_mouth_outer_r(),
    which nothing of the channel reaches past. The first run of material it
    crosses is the web, and the void after that run is the channel. The void
    ends wherever the shell closes again, so one reading covers the outer wall,
    the cavity wall's own chord, and anything that has blocked the channel, none
    of which share a formula and only one of which any radius in the model knows
    about.

    `crop` is that angle's crop of the built shell rather than the shell itself,
    for the same reason every other reading here takes one: a line against the
    front's ten thousand faces costs a second, and the same line against the few
    dozen the crop holds costs nothing measurable. The crop spans the whole ray
    by construction, and refuses the reading outright if it does not, because a
    segment clipped at a crop wall would report the shell closing where it does
    not.

    Two answers are not a width, and the caller reports each rather than
    measuring off it. None at all means the ray began in air: it starts mid-web,
    which is material by design, so the web has gone. `outer` of None means the
    shell never opened again out to led_ring_mouth_outer_r(), which is either a
    ring severed there or a channel running out past its own outer wall.
    """
    wx, wy = board.wheel_center()
    r0 = case.WHEEL_OPENING_R + case.led_ring_web_left() / 2
    r1 = case.led_ring_mouth_outer_r()
    dx, dy = math.cos(angle), math.sin(angle)
    runs = crop.ray_runs(
        (wx + r0 * dx, wy + r0 * dy, z), (wx + r1 * dx, wy + r1 * dy, z)
    )
    if not runs or runs[0][0] > RUN_MIN:
        return None
    inner = r0 + runs[0][1]
    return inner, (r0 + runs[1][0] if len(runs) > 1 else None)


def led_ring(front):
    """The channel proves out on the built shell, all the way around.

    Three things per angle: the channel is a void of usable width, the web
    between it and the wheel opening's bore is solid (or the opening stops
    being a closed seat and light leaks at the wheel instead of through the
    roof), and the roof above it is solid up to the local front-face floor,
    which is where it is thinnest wherever the keypad recess overlaps the ring
    in plan.

    The width is measured rather than assumed. _channel_width() reads it off
    the shell at the roof, which is the narrow end: the inner wall is plumb and
    the outer one rakes inward going up, so a width that clears ROOF_FLAT_MIN
    there clears it over the whole height. Measuring is what lets one pass
    answer for both surfaces that close the channel. The outer wall closes it
    everywhere and the cavity wall closes it harder near the X axis, and
    that wall is nowhere in the radii the channel is revolved from, so probing at
    a fixed radius asked for full width at exactly the two angles the design
    narrows on purpose. It is also what makes this a measurement rather than the
    formula restated: a ring severed anywhere reads as one unbroken run of
    material along that ray, which has no width to report and fails as severed,
    and a ring merely pinched reads a width under ROOF_FLAT_MIN.

    A void probe then stands in the middle of the measured width, over the
    channel's full height, sized to that width less BAND_PROBE_GAP either side
    and capped at PROBE_D. The ray reads one line, so the probe is what covers
    the height between the ends the ray saw and catches an obstruction that does
    not reach either wall.

    The web probe is unaffected by any of this: the clip reaches nowhere near
    the bore, and the wall in front of it is plumb, so one full-height probe
    mid-web answers for the whole web. The roof probe follows the measured
    width's own middle, so across a chord it reads the roof over the part of the
    ring that is left rather than over material.

    Every one of those readings, the ray included, is taken against a crop of
    the shell cut for that one angle rather than against the shell itself. Each
    angle asks four questions of a sliver of geometry a couple of millimetres
    across, and against the built front each of them costs a boolean over ten
    thousand faces. The angle's crop spans its whole ray, from mid-web out to
    the mouth's own outer radius, and the whole height from below the channel up
    past the front face, so the web probe, the ray, the void probe and the roof
    probe all sit inside it wherever the measured width puts them.

    Those crops are themselves cut out of RING_CROP_SECTORS crops of the
    shell rather than out of the shell each time, which is the difference
    between the pass taking half a minute and a sixth of one. Nothing about
    where or how wide anything is probed changes; only what it is intersected
    with does, and every level of that checks containment on every reading and
    refuses what it cannot hold, because a probe outside its crop reads open
    whatever the shell does there, which is how a pass like this goes vacuous.
    """
    problems = _ring_stack_sane()
    if problems:
        return problems
    wx, wy = board.wheel_center()
    r_web = case.WHEEL_OPENING_R + case.led_ring_web_left() / 2
    r_out = case.led_ring_mouth_outer_r()
    z0, z1 = case.CAVITY_FRONT + 0.05, case.LED_RING_TOP - 0.05
    per_sector = math.ceil(LED_RING_SAMPLES / RING_CROP_SECTORS)
    problems = []
    for first in range(0, LED_RING_SAMPLES, per_sector):
        angles = [
            2 * math.pi * i / LED_RING_SAMPLES
            for i in range(first, min(first + per_sector, LED_RING_SAMPLES))
        ]
        sector = _Crop(front, *_ring_crop_box(wx, wy, r_web, r_out, angles, z0))

        for a in angles:
            deg = round(math.degrees(a))
            cos_a, sin_a = math.cos(a), math.sin(a)
            crop = _Crop(sector, *_ring_crop_box(wx, wy, r_web, r_out, [a], z0))

            web = Pos(
                wx + r_web * cos_a, wy + r_web * sin_a, (z0 + z1) / 2
            ) * Cylinder(radius=WEB_PROBE_D / 2, height=z1 - z0)
            if crop.fill_fraction(web) < 0.99:
                problems.append(f"web to the wheel opening open at {deg} degrees")

            width = _channel_width(crop, a, z1)
            if width is None:
                problems.append(
                    f"no web at all at {deg} degrees: the shell is open where "
                    f"{case.led_ring_web_left():.2f} of light barrier should stand "
                    "between the bore and the channel"
                )
                continue
            inner, outer = width
            if outer is None:
                problems.append(
                    f"channel severed at {deg} degrees: the shell never opens again "
                    f"between the web and {case.led_ring_mouth_outer_r():.2f}, so the "
                    "ring reads as arcs"
                )
                continue
            if outer - inner < ROOF_FLAT_MIN:
                problems.append(
                    f"channel down to {outer - inner:.2f} at {deg} degrees, wants "
                    f"{ROOF_FLAT_MIN:.2f}: it runs {inner:.2f} to {outer:.2f} there, "
                    f"against an inner wall at {case.led_ring_inner_r():.2f} and an "
                    f"outer one at {case.led_ring_roof_outer_r():.2f}"
                )
                continue

            mid_r = (inner + outer) / 2
            rx, ry = wx + mid_r * cos_a, wy + mid_r * sin_a
            probe_d = min(PROBE_D, outer - inner - 2 * BAND_PROBE_GAP)
            void = Pos(rx, ry, (z0 + z1) / 2) * Cylinder(
                radius=probe_d / 2, height=z1 - z0
            )
            filled = crop.fill_fraction(void)
            if filled > VOID_FILL_MAX:
                problems.append(
                    f"channel blocked at {deg} degrees: {filled:.0%} of the "
                    f"{outer - inner:.2f} it measures there is material"
                )

            floor = case.face_floor_at(rx, ry)
            roof = Pos(rx, ry, (case.LED_RING_TOP + floor) / 2) * Cylinder(
                radius=PROBE_D / 2, height=floor - case.LED_RING_TOP - 0.04
            )
            if crop.fill_fraction(roof) < 0.99:
                problems.append(f"roof open over the channel at {deg} degrees")
    return problems


WHEEL_SEAT_SAMPLES = 5
"""Heights sampled across the run of shell the wheel opening is actually cut
through, from the cavity ceiling underside up to the front face's own floor over
the seat, for wheel_seat_clearance: enough to span that run rather than
resampling one or two points every run. It used to span up to the wheel's own
top, which is above the shell out there, and the two samples that reached past
the face floor read the same empty air whatever the opening did."""


def wheel_seat_clearance(front):
    """The shell's own wheel opening clears the wheel's main rotating body,
    board.wheel_profile()'s main_od, by at least WHEEL_OPENING_CLEARANCE at
    every height there is shell for it to be cut through: from the cavity
    ceiling underside up to the front face's own floor over the seat. That is
    the opening's own gap; WHEEL_CLEARANCE is the pad's, against the lip, and
    this pass has nothing to do with it. The opening is built to exactly that
    radius now, flush to the wheel, so this is the pass that catches anything
    eating into it.

    This is the real guard behind what used to be a claim that the shell's
    hole had to be sized to the lip so it could pass through on assembly.
    It does not: the board is lowered into an already-closed front shell,
    so the lip stops well short of the ceiling and never transits it. That
    fact is checked first, arithmetic, since it is what excuses the lip
    from the rest of this check; the opening itself is then measured by
    _opening_radius on the built shell at several heights, not trusted from
    WHEEL_OPENING_R, because this exact feature was silently erased by
    _wheel_hole while the formulas behind it still looked right on paper.

    Why the span stops at the face floor and not at the knob's peak, which is
    what it claimed before. The bore is cut from under the ceiling to past the
    face, but the shell it is cut out of ends at the face, and over the wheel
    that face is the keypad recess's wheel basin: a dish whose floor is
    case.face_floor_at() and not SHELL_FRONT. Just outside the bore that floor
    sits half a millimetre below the knob's own top, so between the two there is
    no front shell on this ray at any radius the search covers. Sampling up
    there sent the bisection to find a wall above all the material there was,
    and a bisection that meets nothing used to return its own upper bound:
    17.03 against a requirement of 16.05, which passes, and passes no matter
    what the opening does. So the span ends at that floor, read at `needed`,
    the tightest radius the seat is allowed to have and therefore the lowest the
    floor gets anywhere a reading can land: wider seats meet the floor further
    out, where it is higher still.

    Both ends then pull in by the probe's own height, and for one reason. A
    probe centred on a horizontal boundary straddles material and air, so it
    fills half at most, and the bisection wants a strict majority; every radius
    reads open and the search saturates again. The top had this pull-in
    already, against the face plane it was then thought to end at. The bottom
    never did, and sat exactly on the cavity ceiling underside, which is such a
    boundary: that is why breaking the opening failed only the three interior
    samples.

    Above the face floor the claim is rotation_clearance's, which is where it
    belongs. There is no seat up there to measure a radius of, only the
    requirement that nothing of the shell reaches inside WHEEL_OPENING_R
    between the lip's top face and past the knob's peak, and that pass probes
    that whole band by volume.

    Saturation is loud now rather than laundered. _opening_radius raises instead
    of handing back its bound, and each height catches that and reports itself
    unmeasured, so a span that goes wrong again, or a seat that grows out past
    the bound the ring channel's inner wall puts on the search, fails rather
    than passes for free.
    """
    problems = []
    profile = board.wheel_profile()

    if profile.lip_z1 + params.WHEEL_CLEARANCE > case.CAVITY_FRONT:
        problems.append(
            f"lip top {profile.lip_z1:.3f} plus WHEEL_CLEARANCE reaches the "
            f"ceiling underside at {case.CAVITY_FRONT:.2f}: the lip is not "
            "clear of it, so the shell's opening has to answer for it too"
        )
        return problems

    wx, wy = board.wheel_center()
    needed = profile.main_od / 2 + params.WHEEL_OPENING_CLEARANCE
    # The run of shell the opening is cut through, both ends pulled in off their
    # own boundary plane by the probe's own height so that no sample straddles
    # one. See the docstring: a straddling probe is half air at every radius and
    # the bisection it feeds cannot find anything.
    z0 = case.CAVITY_FRONT + OPENING_PROBE_H
    z1 = case.face_floor_at(wx + needed, wy) - OPENING_PROBE_H
    if z1 <= z0:
        problems.append(
            f"no shell left to seat the wheel against: the face floor over the "
            f"opening is at {case.face_floor_at(wx + needed, wy):.2f}, against a "
            f"cavity ceiling underside at {case.CAVITY_FRONT:.2f}"
        )
        return problems
    # Bounded inside the ring channel's inner wall: past it the material is
    # no longer monotonic along the radius (web, channel void, outer wall),
    # and a bisect that wanders into the void reads the channel's outer wall
    # as the opening, hiding an undersized seat behind a passing number. That
    # wall is plumb, so one radius bounds every height this samples.
    hi = case.led_ring_inner_r() - OPENING_PROBE_R
    # One crop of the shell for all five heights. Every probe of every bisection
    # stands on the same +x ray out of the wheel axis between OPENING_SEARCH_LO
    # and that bound, so the lot of them live in one thin box spanning the
    # heights sampled, and cutting it once replaces a hundred booleans against
    # the built front with a hundred against a few dozen faces. It moves no
    # probe and changes no bound; it only changes what the probe meets. The crop
    # refuses any probe it does not wholly contain, so the alternative to a
    # correct crop here is a stopped pass, not a seat measured against nothing.
    crop = _opening_crop(front, wx, wy, z0, z1, OPENING_SEARCH_LO, hi)
    for i in range(WHEEL_SEAT_SAMPLES):
        z = z0 + (z1 - z0) * i / (WHEEL_SEAT_SAMPLES - 1)
        try:
            opening = _opening_radius(front, wx, wy, z, hi=hi, crop=crop)
        except OpeningNotFound as missing:
            problems.append(
                f"opening unmeasurable at z={z:.2f}: {missing}"
            )
            continue
        if opening < needed - OPENING_PROBE_R:
            problems.append(
                f"opening only {opening:.2f} at z={z:.2f}, wants {needed:.2f}"
            )
    return problems


def rotation_clearance(front, pad):
    """Nothing of the pad or the shell may intrude inside the wheel's rotating
    envelope: LIP_CLEAR_R at and below the lip's top face, where the widest
    disc has to clear, and WHEEL_OPENING_R above it, where the shell's opening
    closes in flush on the main body. The lip being the widest disc is what
    lets the pad's plain bore answer for the main body too, so that fact is
    checked first, arithmetic, rather than assumed.
    """
    hits = []
    if case.WHEEL_LIP_OD < case.WHEEL_MAIN_OD:
        hits.append(
            f"lip {case.WHEEL_LIP_OD:.2f} is narrower than the main body "
            f"{case.WHEEL_MAIN_OD:.2f}: the pad's bore is sized to the wrong disc"
        )
    wx, wy = board.wheel_center()
    regions = [
        ("at and below the lip", case.WHEEL_LIP_Z0, case.WHEEL_LIP_Z1, case.LIP_CLEAR_R),
        ("above the lip", case.WHEEL_LIP_Z1, case.WHEEL_TOP + 1, case.WHEEL_OPENING_R),
    ]
    for label, z0, z1, radius in regions:
        probe = Pos(wx, wy, (z0 + z1) / 2) * Cylinder(radius=radius - 0.05, height=z1 - z0)
        for name, shell in (("pad", pad), ("front shell", front)):
            volume = _volume(shell.intersect(probe))
            if volume > TOLERANCE:
                hits.append(
                    f"{name} intrudes {volume:.2f} mm3 inside the wheel's clearance {label}"
                )
    return hits
