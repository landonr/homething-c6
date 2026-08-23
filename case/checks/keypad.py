"""Pad fit: the pad drops into the front shell without fouling it. Every
switch takes a cap now, so nothing of the pad itself still has to come
out the far side; caps_fit() covers all eleven against the shell.

Plunger stub contact: every switch's plunger actually lands on SWITCH_TOP,
not merely in the formula, probed on the built pad rather than trusted from
KEYPAD_PLUNGER_STUB alone: a clearance cut or a wrong z reference could leave
one short or overlong without any volume-based check noticing either.

Pad lobes clear the wheel: the pad is two tight rectangles now and the wheel
bore that used to sever one slab into them is gone, so what used to be
guaranteed by a cut has to be measured instead. Both the lip's rotating
clearance and the LEDs' sight line depend on it.

Recesses open: the front face is genuinely dished at the depth face_depth_at()
says, probed beside every key, beside the mic, on the wheel's own seat on four
bearings, and at each neck's waist. Beside, not over: over a key the face is
open from the cavity right through, so a probe there reads open whether the
recess was cut or not.

Neck continuity: the recess runs unbroken along its centreline from one
island's keys to the other's, so no parameter change can silently pinch it
apart; no join runs past either basin's own centre and no two joins overlap;
each join's waist clears KEYPAD_NECK_MIN and is narrower than both the widths it
bridges rather than bulging between them; and each join's plan outline still
turns through a generous radius rather than closing to a corner, which is the
whole difference between a merged recess and two trays with a slot between
them.

Neck blends smoothly: the merged field's own one-sided slopes agree at every
junction and waist, in depth and in plan width both, which is what says a neck
meets a dish with no tangent break and the outline has no cusp.

Recess land: the ceiling left over each counterbore, at the deepest point the
dish reaches over it, has not gone below what the flange stack can spare.
Probed and then checked arithmetically, because the solids build a
valid-looking shell right up until it goes negative.

Recess margins: every counterbore stays inside the recess's rim in plan (a
superellipse inscribed in the coverage box rather than bounding it would put
the rim through the four corner keys' holes), the rim stays KEYPAD_EDGE_MARGIN
clear of the case's exterior wall, and the three dish centres and the wheel's
own centre still share one x, which is what makes the whole recess a single
column along y and so what one spine and one loft depend on.
"""

import math

from build123d import Cylinder, Pos

import board
import case
import params

from .common import PROBE_D, TOLERANCE, _fill_fraction, _volume


def pad_fits(front, pad):
    """The pad has to drop into the front shell without fouling it.

    Every switch takes a stem and a cap now rather than nine stems plus two
    moulded keytops, so there is nothing here still coming through the
    front face to probe per key: caps_fit() covers all eleven, stems
    included, against the shell, each other and their sockets.
    """
    fouled = _volume(front.intersect(pad))
    if fouled > TOLERANCE:
        return [f"pad fouls the front shell by {fouled:.2f} mm3"]
    return []


PLUNGER_CONTACT_TOLERANCE = 0.05
"""How exactly a plunger's own bottom has to land on the switch top it
rests on. Float slop, not a design margin: case.SWITCH_TOP is what
button_pad() builds every plunger down to by construction."""

PLUNGER_PROBE_SPAN = 0.6
"""Height of the plunger_stub_contact probe, centred on SWITCH_TOP: wide
enough either side to catch the plunger's own bottom face cleanly, narrow
enough that it still means something rather than always finding material
somewhere in a probe reaching into the web proper."""


def plunger_stub_contact(pad):
    """Every switch's plunger actually reaches down to land on SWITCH_TOP,
    not merely in the formula: probed on the built pad, since a clearance
    cut or a wrong z reference could leave a plunger short, or long enough
    to overshoot into the switch, without any volume-based check noticing
    either (a shorter or longer peg still has plenty of material, just not
    where KEYPAD_PLUNGER_STUB says it should be).
    """
    problems = []
    parts = board.components()
    half = PLUNGER_PROBE_SPAN / 2
    for ref in board.refs("SW"):
        x, y = parts[ref][:2]
        z0, z1 = case.SWITCH_TOP - half, case.SWITCH_TOP + half
        probe = Pos(x, y, (z0 + z1) / 2) * Cylinder(radius=PROBE_D / 2, height=z1 - z0)
        hit = pad.intersect(probe)
        if _volume(hit) <= TOLERANCE:
            problems.append(f"{ref}'s plunger does not reach near the switch top")
            continue
        bottom = min(s.bounding_box().min.Z for s in hit.solids())
        off = bottom - case.SWITCH_TOP
        if abs(off) > PLUNGER_CONTACT_TOLERANCE:
            problems.append(
                f"{ref}'s plunger bottom at {bottom:.3f} against switch top "
                f"{case.SWITCH_TOP:.3f}, off by {off:.3f}"
            )
    return problems


def pad_clears_wheel(pad):
    """Neither lobe reaches into the band the wheel needs to itself.

    Arithmetic first, on the lobe rectangles, and then on the built pad's own
    solids, because the two can disagree: a lobe is clipped against the cavity
    and cut for a screw boss after its rectangle is drawn, and a stem is raised
    on it after that. What the band protects is the lip's rotating clearance
    and the LEDs firing up past the pad, both of which the bore used to
    guarantee by construction and neither of which anything cuts for now.
    """
    problems = []
    gap = case.pad_wheel_gap()
    if gap <= 0:
        problems.append(
            f"a pad lobe reaches {-gap:.2f} into the wheel's own "
            f"{case.pad_clear_y():.2f} band"
        )
    _, wy = board.wheel_center()
    half = case.pad_clear_y()
    for solid in pad.solids():
        box = solid.bounding_box()
        if box.min.Y < wy + half and box.max.Y > wy - half:
            problems.append(
                f"a built pad solid spans y {box.min.Y:.2f} .. {box.max.Y:.2f}, "
                f"inside the wheel's band at {wy - half:.2f} .. {wy + half:.2f}"
            )
    return problems


FLOOR_PROBE_DEPTH = 0.3
"""How far under a recess floor recesses_open() probes for solid shell. Deep
enough to read as a band rather than a plane, shallow enough to stay above the
ring channel's own roof, which is the next void down anywhere the keypad recess
crosses it."""
FLOOR_PROBE_SLOP = 0.01
"""Fraction of the solid half of a floor probe allowed to be void. A fully
solid probe this narrow reads well under TOLERANCE in mm3, so an absolute floor
could not tell it from a void; anything genuinely sinking past the floor takes
far more than this."""
AIR_PROBE_SLOP = 0.05
"""Fraction of the open half of a floor probe allowed to be material. Not zero,
because the floor is curved across the probe's own width, so the probe's outer
side stands a little above the height its centre's floor sets and catches a
sliver of the dish wall; on the shallowest site here that reads under a
thousandth. Also a fraction rather than a volume, and for the same reason the
solid half is: a probe whose height is the local depth is only tenths of a
millimetre tall at a shallow site, so a fully blocked one measures less than
TOLERANCE in mm3. An undished face reads 1.0."""
FLOOR_PROBE_LIFT = 0.025
"""How far above a floor the open half of a probe starts, and how far below it
the solid half stops. Small: the point is to straddle the surface
face_depth_at() predicts, not to confirm that a hole several millimetres deep
is a hole. It also has to clear the loft's own faceting between stations, which
is a few thousandths at worst, and it does by several times over."""
FLOOR_PROBE_MIN_DEPTH = 4 * FLOOR_PROBE_LIFT
"""Least local depth a probe site may have and still be worth reading. The two
halves stand twice FLOOR_PROBE_LIFT apart, so at a shallower site the open half
is barely taller than the slop between them and neither reading distinguishes
much. A site that shallow is reported rather than passed. The shallowest site
here is a neck waist, and it clears this by a third; the recess's own floor
under a waist is held by neck_continuity() rather than by this."""
HOLE_MARGIN = PROBE_D / 2 + 0.15
"""How far clear of any hole in the face a probe site has to sit. The probe's
own radius plus enough that a rounded corner or a boolean's own edge cannot
reach into it."""


JOIN_SITE_SAMPLES = 200
"""How finely a join is walked looking for its narrowest station clear of every
hole. At this count the site lands within a few hundredths of the narrowest open
point there is."""


def _clear_of_holes(x, y, own):
    """Whether a probe standing at (x, y) is clear of everything else cut
    through the face there: every cap's counterbore, the mic's mouth and the
    wheel's bore. `own` names the hole the site was offset off, which is the
    one it sits exactly on the margin of and so the one no float comparison can
    answer for.

    This is the whole difficulty in probing a recess floor. Directly over a key
    or the mic the face is open from the cavity right through, so a probe there
    reads open whether the recess was cut or not, which is a pass that proves
    nothing. Every site has to stand on face that only the dish can have sunk.
    """
    parts = board.components()
    for ref in board.refs("SW"):
        if ref == own:
            continue
        kx, ky = parts[ref][:2]
        half = case.cap_counterbore(ref) / 2 + HOLE_MARGIN
        if abs(x - kx) < half and abs(y - ky) < half:
            return False
    if own != "mic":
        mx, my = case.mic_port()
        if math.hypot(x - mx, y - my) < case.mic_mouth_r() + HOLE_MARGIN:
            return False
    wx, wy = board.wheel_center()
    return math.hypot(x - wx, y - wy) >= case.WHEEL_OPENING_R + HOLE_MARGIN


def _probe_sites():
    """[(label, x, y)] where recesses_open() reads the face.

    One beside every key and one beside the mic, offset just past that hole's
    own edge in whichever of the four axis directions the dish is deepest,
    which is always the one facing the recess centre. That is what makes the
    reading local: it is the floor immediately around that key's own cap, at
    whatever depth face_depth_at() says the recess is worth there, so a dish
    built on the wrong centre or at the wrong depth disagrees at the key
    nearest it and not only in aggregate.

    Plus the wheel's seat on four bearings and each join's own waist. The wheel
    dish is a superellipse around a round bore, so its seat is narrowest and
    shallowest on the free axis and widest and deepest on the diagonals; and the
    two bearings a join leaves on are different again, both reaches taking the
    bridge past the bore so the seat there is neck rather than dish and reads
    deeper. The waists are where the merged field is at its shallowest anywhere
    between the islands, so they are the sites a bridge built the wrong way
    would show up at first.
    """
    parts = board.components()
    sites = []
    targets = [
        (ref, *parts[ref][:2], case.cap_counterbore(ref) / 2)
        for ref in board.refs("SW")
    ]
    targets.append(("mic", *case.mic_port(), case.mic_mouth_r()))
    for label, x, y, edge in targets:
        reach = edge + HOLE_MARGIN
        best = None
        for dx, dy in ((reach, 0), (-reach, 0), (0, reach), (0, -reach)):
            px, py = x + dx, y + dy
            if not _clear_of_holes(px, py, label):
                continue
            depth = case.face_depth_at(px, py)
            if best is None or depth > best[0]:
                best = (depth, px, py)
        if best is None:
            sites.append((f"beside {label}", None, None))
            continue
        sites.append((f"beside {label}", best[1], best[2]))

    wx, wy = board.wheel_center()
    r = case.WHEEL_OPENING_R + params.WHEEL_RIM_LEDGE / 2
    sites.append(("on the wheel seat on the axis", wx + r, wy))
    sites.append(
        ("on the wheel seat on the diagonal", wx + r * 0.70711, wy + r * 0.70711)
    )
    # The two bearings a neck leaves on: the seat carries on into the neck
    # there rather than feathering back to the face, so these read deeper than
    # the free axis does and are the only sites that see a neck at the bore.
    sites.append(("on the wheel seat toward the grid", wx, wy - r))
    sites.append(("on the wheel seat toward the second island", wx, wy + r))
    cx = case.centerline_x()
    for neck in case.keypad_necks():
        # The narrowest point of the join that is actually face. Its true waist
        # can sit inside the wheel opening's bore, both reaches being longer
        # than WHEEL_RIM_LEDGE, and a probe standing in the bore reads the bore
        # rather than the recess. So the whole join is walked and the narrowest
        # station clear of every hole is taken.
        span = neck.y1 - neck.y0
        best = None
        for i in range(JOIN_SITE_SAMPLES + 1):
            y = neck.y0 + span * i / JOIN_SITE_SAMPLES
            if not _clear_of_holes(cx, y, None):
                continue
            width = case.recess_spine(y)[0]
            if best is None or width < best[0]:
                best = (width, y)
        sites.append(
            (
                f"at the {neck.name} join's narrowest open point",
                cx,
                best[1] if best else None,
            )
        )
    return sites


def recesses_open(front):
    """The front face is genuinely dished, at the depth face_depth_at() says,
    at every site in _probe_sites().

    Two readings per site: open from just above the local floor to the face,
    and solid from just below it. Together they say the surface is where the
    arithmetic puts it, which is more than either says alone. Open alone is
    what a probe standing over a key hole reads whether anything was cut or
    not; solid alone is what an uncut flat face reads.
    """
    problems = []
    for label, x, y in _probe_sites():
        if x is None or y is None:
            problems.append(f"no clear face to probe {label}: it is all hole")
            continue
        depth = case.face_depth_at(x, y)
        if depth < FLOOR_PROBE_MIN_DEPTH:
            problems.append(
                f"the face is only {depth:.3f} down {label}, too flat for this "
                f"pass to mean anything"
            )
            continue
        floor = case.SHELL_FRONT - depth
        z0, z1 = floor + FLOOR_PROBE_LIFT, case.SHELL_FRONT + 0.05
        air = Pos(x, y, (z0 + z1) / 2) * Cylinder(radius=PROBE_D / 2, height=z1 - z0)
        if _fill_fraction(front, air) > AIR_PROBE_SLOP:
            problems.append(f"the face is not dished {label}")
        z0, z1 = floor - FLOOR_PROBE_DEPTH, floor - FLOOR_PROBE_LIFT
        solid = Pos(x, y, (z0 + z1) / 2) * Cylinder(
            radius=PROBE_D / 2, height=z1 - z0
        )
        if _fill_fraction(front, solid) < 1 - FLOOR_PROBE_SLOP:
            problems.append(f"something cuts past the recess floor {label}")
    return problems


LAND_FLOOR_MIN = 0.3
"""Thinnest the ceiling may be left under a recess floor, over the counterbore.
A real design floor: what is left between COUNTERBORE_TOP and the dish above it
is the ledge a cap's flange is caught by, and the deepest point of the grid
recess sits directly over SW7's own counterbore."""


def recess_land(front):
    """The land over every counterbore has not gone below LAND_FLOOR_MIN.

    The arithmetic first, because it is the half that knows where the dish
    reaches deepest over a given counterbore and by how much it misses. Then the
    built shell, in the ring between the face hole and the counterbore wall,
    which is the land itself: it has to be solid over the whole of
    LAND_FLOOR_MIN above the shoulder, which is what says the two holes and the
    dish above them actually left a ledge rather than the numbers merely
    allowing one.
    """
    problems = []
    parts = board.components()
    for ref in board.refs("SW"):
        land = case.counterbore_land(ref)
        if land < LAND_FLOOR_MIN:
            problems.append(
                f"{ref}'s counterbore is left {land:.2f} of land under its recess, "
                f"wants {LAND_FLOOR_MIN:.2f}"
            )
            continue
        x, y = parts[ref][:2]
        # Mid-ring between the face hole and the counterbore wall, on the +x
        # side. The counterbore is square, so the ring is a constant width
        # everywhere along a flat and this is as good a spot on it as any.
        r = (case.cap_face_hole(ref) + case.cap_counterbore(ref)) / 4
        z0, z1 = case.COUNTERBORE_TOP, case.COUNTERBORE_TOP + LAND_FLOOR_MIN
        probe = Pos(x + r, y, (z0 + z1) / 2) * Cylinder(
            radius=PROBE_D / 2, height=z1 - z0
        )
        if _fill_fraction(front, probe) < 0.99:
            problems.append(
                f"{ref}'s face land is not solid over the {LAND_FLOOR_MIN:.2f} "
                "above its counterbore shoulder"
            )
    return problems


CENTERLINE_SPREAD_MAX = 0.1
"""How far the three dish centres and the wheel's own centre may sit from the
shared centreline. The whole construction rests on the recess being a single
column along y with one interval in x per station, which is only true while they
share an x; on this board they agree to a couple of hundredths and the model
averages them. Past this the averaging would be shearing a dish sideways rather
than absorbing float, and that is worth failing on rather than shipping."""


def recess_margins():
    """Every counterbore inside the recess's rim, the rim clear of the case's
    exterior wall, and the dish centres still sharing one x.

    Plan geometry, on the recess definitions rather than on the built solid,
    because what these catch is a rim landing somewhere it should not and a rim
    is exactly what keypad_recesses() and recess_spine() state.
    recess_edge_clearance() below is the built-solid half of the same subject.

    The counterbore margin is the one that is not obvious. A superellipse only
    touches its own bounding box at the four edge midpoints, so one inscribed
    in the coverage box would pass inside all four corners of it and cut
    straight through the corner keys' holes; keypad_recesses() grows it to
    bound the box instead, and this is what proves the growth is enough after
    KEYPAD_EDGE_MARGIN has capped it back.

    So is the wheel seat's own ledge. The wheel basin is sized by stating its
    half axes at WHEEL_RIM_LEDGE past the bore, and that only delivers the
    ledge at every angle while its exponent is at or above two: above two a
    superellipse is closest to its centre on its own axes, so the half axis is
    the clearance, and below two the diagonals come in nearer instead and the
    sizing rule would quietly stop meaning what it says. WHEEL_SQUIRCLE_N is a
    tunable now, so the clearance is measured around the merged rim rather than
    trusted from the rule, and the joins are in that measurement too.
    """
    problems = []
    for ref in board.refs("SW"):
        margin = case.counterbore_dish_margin(ref)
        if margin <= 0:
            problems.append(
                f"{ref}'s counterbore crosses the recess rim by {-margin:.2f}"
            )
    facts = case.keypad_recess_facts()
    if facts["edge_gap"] < params.KEYPAD_EDGE_MARGIN - TOLERANCE:
        problems.append(
            f"the recess is only {facts['edge_gap']:.2f} from the exterior wall, "
            f"wants {params.KEYPAD_EDGE_MARGIN:.2f}"
        )
    spread = facts["centerline"][1]
    if spread > CENTERLINE_SPREAD_MAX:
        problems.append(
            f"the recess centres are {spread:.3f} apart in x, over "
            f"{CENTERLINE_SPREAD_MAX:.2f}: they no longer share a centreline"
        )
    ledge = case.wheel_ledge_left()
    if ledge < params.WHEEL_RIM_LEDGE - TOLERANCE:
        problems.append(
            f"the recess rim comes within {ledge:.3f} of the wheel opening's "
            f"bore, under WHEEL_RIM_LEDGE at {params.WHEEL_RIM_LEDGE:.2f}: the "
            "seat is no longer the ledge the basin is sized on"
        )
    return problems




NECK_DEPTH_MIN = 0.05
"""Shallowest the recess may get anywhere along its centreline between the two
islands' outermost key rows. A floor under the merge itself rather than a design
target: a join's floor is whatever the two dishes it bridges leave, so a change
to a depth, a half axis or a KEYPAD_JOIN_REACH could ramp it through zero and
tear the recess into three, which would still build a valid shell and would still
look right in every other pass. The present layout leaves several times this."""

JOIN_RADIUS_MIN = 1.0
"""Tightest radius a join's plan outline may turn through. This is what holds
the joins round. The reaches are what set it and nothing else in the model would
notice them shrinking: a tight join builds cleanly, keeps its depth, keeps its
waist width and simply reads as a pinch between two trays instead of one
continuous recess. Set under the tighter of the two present joins with room, so
it catches a reach cut back rather than tracking the current numbers."""

COVERAGE_SAMPLES = 3000
"""Points the recess span is walked at when checking that exactly one thing
claims each y. Dense because an uncovered overlap opens as a narrow band between
a basin's rim and where its join begins, and a coarse walk would step over it."""

NECK_WALK_SAMPLES = 800
"""Points the centreline is walked at between the key rows. At this count they
sit a few hundredths apart, well inside the width of any dip a cubic bridge can
produce."""


def neck_continuity():
    """The recess runs unbroken along its centreline from one island's keys to
    the other's, and each join is a real rounded join rather than a pinch.

    The merge is the whole point of the joins, and it is not something the
    solids can be trusted to show: three dishes that had pinched apart would
    still build one perfectly valid cut solid, one that simply ran to zero
    depth twice on the way. So the field is walked instead, on the same
    face_depth_at() the loft is built from.

    Then the structural bounds. A join may not run past either basin's own
    deepest point, or that basin would stop reaching the depth it is stated at;
    two joins may not overlap, or the basin between them would have no body left
    and the spine would be reading two bridges at once; and exactly one thing has
    to claim every y along the span, which is the assumption the whole
    single-column construction rests on.

    That last one is what bounds WHEEL_BASIN_SPREAD in y. A basin wide enough to
    reach past where its own join begins overlaps its neighbour somewhere no
    join covers, and there recess_spine() has two basins to choose from and
    silently takes the first. It still builds, still stays continuous and still
    passes everything else; the only sign is that one stretch of rim follows the
    wrong basin's curve. All of these are invariants of the construction rather
    than matters of taste, and none of them shows up anywhere else.

    Then three things about each join in plan. Its waist has to clear
    KEYPAD_NECK_MIN, which is the floor under how narrow the recess may get. It
    has to stay narrower than both the widths it bridges, since a cubic between
    two ends whose slopes point outward would bulge in the middle and the
    outline would read as three shapes joined by lozenges. And its outline has
    to turn through at least JOIN_RADIUS_MIN, which is the guard that actually
    keeps the joins round: nothing else here would notice a reach cut back, a
    tight join being narrow in no measurement except its own curvature.
    """
    problems = []
    necks = case.keypad_necks()
    for neck in necks:
        if neck.y0 <= neck.lower.cy:
            problems.append(
                f"the {neck.name} join starts at y={neck.y0:.2f}, past the "
                f"{neck.lower.name} dish's own centre at {neck.lower.cy:.2f}: its "
                "reach has swallowed the basin it bridges from"
            )
        if neck.y1 >= neck.upper.cy:
            problems.append(
                f"the {neck.name} join ends at y={neck.y1:.2f}, past the "
                f"{neck.upper.name} dish's own centre at {neck.upper.cy:.2f}: its "
                "reach has swallowed the basin it bridges to"
            )
    for lower, upper in zip(necks, necks[1:]):
        if upper.y0 <= lower.y1:
            problems.append(
                f"the {lower.name} and {upper.name} joins overlap between "
                f"y={upper.y0:.2f} and {lower.y1:.2f}: the dish between them has "
                "no body left"
            )
    basins = list(case.keypad_recesses().values())
    span0, span1 = case.recess_span()
    for i in range(COVERAGE_SAMPLES + 1):
        y = span0 + (span1 - span0) * i / COVERAGE_SAMPLES
        if any(neck.y0 <= y <= neck.y1 for neck in necks):
            continue
        claiming = [b.name for b in basins if abs(y - b.cy) <= b.ay]
        if len(claiming) > 1:
            problems.append(
                f"at y={y:.2f} the {' and '.join(claiming)} basins both claim the "
                "spine and no join covers it: their rims overlap outside a join, "
                "so the outline there follows whichever is listed first"
            )
            break
    cx = case.centerline_x()
    y0, y1 = case.centerline_keys_span()
    for i in range(NECK_WALK_SAMPLES + 1):
        y = y0 + (y1 - y0) * i / NECK_WALK_SAMPLES
        depth = case.face_depth_at(cx, y)
        if depth < NECK_DEPTH_MIN:
            problems.append(
                f"the recess is only {depth:.3f} deep on the centreline at "
                f"y={y:.2f}, wants {NECK_DEPTH_MIN:.2f}: a join has pinched it "
                "apart"
            )
            break
    for label, facts in case.keypad_recess_facts()["necks"].items():
        waist = facts["waist"][1]
        if 2 * waist < params.KEYPAD_NECK_MIN:
            problems.append(
                f"the {label} join narrows to {2 * waist:.2f}, under "
                f"{params.KEYPAD_NECK_MIN:.2f}"
            )
        for end in facts["ends"]:
            if waist > end + TOLERANCE:
                problems.append(
                    f"the {label} join swells to {2 * waist:.2f} against a "
                    f"{2 * end:.2f} end: it bulges rather than pinching"
                )
        if facts["radius"] < JOIN_RADIUS_MIN:
            problems.append(
                f"the {label} join's outline turns through only "
                f"{facts['radius']:.2f}, under {JOIN_RADIUS_MIN:.2f}: its "
                "KEYPAD_JOIN_REACH is too short for the join to read as round"
            )
    return problems


BLEND_STEP = 0.002
"""How far either side of a junction the one-sided slopes are read. Far enough
out that the difference quotient is not float noise, close enough that a real
tangent break has not yet been averaged away."""
BLEND_SLOPE_TOLERANCE = 0.02
"""How closely the two one-sided slopes have to agree, per unit y. The bridges
match slopes exactly by construction and the junction values come off a central
difference, so a passing reading is float noise; what this has to catch is a
bridge built without slope matching, which disagrees by whole units."""


def _one_sided_slope(read, y, step):
    """The slope of `read` approaching y from one side, to second order. A
    negative step reads the other side, the formula being symmetric in it.

    A plain difference quotient will not do here. Curvature is deliberately
    discontinuous at these junctions (the field is C1, not C2), and a first
    order quotient carries a curvature term proportional to its own step, so it
    reports a break of its own wherever a junction sits on a steeply turning
    part of a dish's rim. Three points on one side cancel that term, leaving
    only genuine tangency.
    """
    return (
        3 * read(y) - 4 * read(y - step) + read(y - 2 * step)
    ) / (2 * step)


def neck_blends_smoothly():
    """The merged field is C1 across every junction and waist, in depth and in
    plan width both.

    This is what "one recess" means rather than three cuts that touch. A join
    that merely met a dish at the same depth would leave a crease running
    across the floor and a cusp in the outline at the rim, which is the failure
    the old neck-joined pocket spent a blend radius on avoiding. Measured on
    the field rather than on the solid, because the field is what the loft
    reproduces and a crease in it would be faithfully lofted.

    The waist is read as well as the two junctions. Nothing is spliced there
    any more, one cubic spanning the whole join, so it passes by construction;
    it is checked so that a future bridge built in two pieces again cannot put a
    flat spot back without saying so.
    """
    problems = []
    cx = case.centerline_x()
    h = BLEND_STEP
    for neck in case.keypad_necks():
        for where, y in (
            ("start", neck.y0),
            ("waist", case.neck_waist(neck)[0]),
            ("end", neck.y1),
        ):
            label = f"{neck.name} join {where}"
            for what, read in (
                ("floor", lambda v: case.face_depth_at(cx, v)),
                ("outline", lambda v: case.recess_spine(v)[0]),
            ):
                before = _one_sided_slope(read, y, h)
                after = _one_sided_slope(read, y, -h)
                if abs(after - before) > BLEND_SLOPE_TOLERANCE:
                    problems.append(
                        f"the {label}'s {what} turns from {before:+.3f} to "
                        f"{after:+.3f} per mm across it, a tangent break"
                    )
    return problems


SOLID_BOX_TOLERANCE = 0.05
"""How far the built recess's own bounding box may sit from the extent its field
says it should have. The plan tips overshoot their outermost station by a hair
and the loft's own approximation costs less than that, so this is float and
tessellation slop rather than a design margin."""


def recess_solid_sane():
    """The built recess is the solid its own field describes: one piece, of
    positive volume, filling the box the spine spans and no more.

    This is not a design check, it is a guard on the loft. Lofting a spline in y
    through this many sections was unstable, and when it went it went
    spectacularly: a single valid-looking solid of negative volume spread over
    half a metre in every direction, which every arithmetic pass in this file
    still agreed with because the arithmetic was never wrong. What caught it was
    two features at the far end of the case failing for no reason. So the built
    solid is measured against its own definition before anything else probes it,
    and the loft is ruled now precisely so this cannot recur quietly.
    """
    solid = case.keypad_recess()
    problems = []
    if len(solid.solids()) != 1:
        problems.append(f"the recess came out as {len(solid.solids())} solids, not one")
    if solid.volume <= 0:
        problems.append(
            f"the recess has a volume of {solid.volume:.2f}: the loft came out "
            "inside out"
        )
    cx = case.centerline_x()
    widest = max(r.ax for r in case.keypad_recesses().values())
    deepest = max(r.depth for r in case.keypad_recesses().values())
    y0, y1 = case.recess_span()
    box = solid.bounding_box()
    for what, got, want in (
        ("min x", box.min.X, cx - widest),
        ("max x", box.max.X, cx + widest),
        ("min y", box.min.Y, y0),
        ("max y", box.max.Y, y1),
        ("min z", box.min.Z, case.SHELL_FRONT - deepest),
        ("max z", box.max.Z, case.SHELL_FRONT + case.MERGE),
    ):
        if abs(got - want) > SOLID_BOX_TOLERANCE:
            problems.append(
                f"the recess's {what} is {got:.3f} where its field says "
                f"{want:.3f}: the loft is not the shape it was built from"
            )
    return problems


def recess_edge_clearance(front):
    """The built recess stays clear of the case's exterior side wall, keeping it
    out of EDGE_R_FRONT's fillet zone.

    Measured on the built solid's own bounding box rather than on the
    superellipse recess_margins() reads, so a cut that came out wider than its
    own definition, or one built on the wrong centre, is caught here rather
    than passing on the strength of the arithmetic that produced it. The
    smoothed loft overshoots its stations by a couple of thousandths in plan,
    which is what TOLERANCE absorbs here.
    """
    ex0, ex1 = case.exterior_x_bounds()
    limit = params.KEYPAD_EDGE_MARGIN
    box = case.keypad_recess().bounding_box()
    gap = min(box.min.X - ex0, ex1 - box.max.X)
    if gap < limit - TOLERANCE:
        return [
            f"the built recess is only {gap:.2f} from the side wall, "
            f"wants {limit:.2f}"
        ]
    return []
