"""The FDM front: the same shell with its face finished differently.

Face is flat: at every site checks/keypad.py probes the recessed front's dish,
this front's outer surface is one plane at FDM_FACE. The two passes read the
same places and want opposite answers, deliberately, because the whole claim
about this variant is that it prints face down and that claim is exactly
"nothing on the face hangs in the air". A surface below the plane at one of
those sites is a dish that survived into the variant that exists to have
none.

Outline is cut: the slot is where the outline is, at the depth it was asked
for, and there is real material left under every point of it. One ray down
through the face at each sample rather than a pair of probes: what the ray
returns is where the built shell opens and closes along that line, so the top
of the first run is the groove's own floor and the length of that run is the
roof under it, and no second reading has to agree with the first about where
the floor was.

The roof is the live half. The rim passes within a few hundredths of the LED
ring channel's outer wall either side of the wheel, so a small change on either
could put the groove over the ring, and what would be left there is
LED_RING_ROOF less the groove's own depth. The floor is set for that case
rather than for the couple of millimetres the present layout happens to leave.

Edge round is hard: the flat the built shell actually has, out to its own top
edge round, is EDGE_R_FRONT_FDM's and not EDGE_R_FRONT's, and the groove sits
on that flat with FDM_OUTLINE_EDGE_CLEAR to spare. This is the pass that holds
the trade the variant is built on. The outline is the recessed front's own rim,
which runs inside EDGE_R_FRONT, so the round is what has to give; if it ever
stops giving, the groove lands on the curve of the edge instead of on flat
face, and at the limit its outer edge goes coincident with the round's own and
tears the exported mesh.

Ceilings hold: the three thicknesses FDM_FACE_DROP takes from, the USB
pocket's roof, the LED ring's roof and every counterbore's land, are each still
above the floor the recessed front's own pass holds them to. The drop is the
one part of this variant that removes material the keypad recess never reached,
so it is the one part that cannot be justified by saying the recessed front
already lives with it.

Outline solid sane: the cut itself is one closed band of the width and depth it
was built from, measured off the solid rather than restated from the offsets
that made it. A 2D offset can come back self-intersecting on a
concave turn and leave a band that pinches or doubles back, and the mean width
is what says it did not.
"""

import math

from build123d import Box, Pos

import board
import case
import params

from .common import CROP_MARGIN, TOLERANCE, Problem, _Crop, _ray_runs, _volume
from .keypad import LAND_FLOOR_MIN, _probe_sites
from .usb import USB_CEILING_MIN
from .wheel_ring import ROOF_LEFT_MIN

FACE_PROBE_START = 0.2
"""How far above the face each ray starts. Only has to clear the plane."""

FACE_TOLERANCE = 0.01
"""How far a read surface may sit from FDM_FACE. Tessellation and boolean slop
only: that face is one plane by construction, so anything real here is a dish
left in it or a feature standing proud of it."""

OUTLINE_SAMPLES = 96
"""Points around the outline each ray pass reads, about one every 3mm. The
outline's own geometry is checked exactly by outline_solid_sane(); these are
here to catch a stretch of it that the shell closed up or opened out from
under, which is a regional failure rather than a point one."""

OUTLINE_START = 0.2
"""How far above the face each ray starts. Only has to clear the plane."""

OUTLINE_DEPTH_TOLERANCE = 0.02
"""How far the built groove's floor may sit from FDM_OUTLINE_DEPTH."""

OUTLINE_ROOF_MIN = 0.6
"""Thinnest material the groove may leave under itself anywhere, before the
first void below. A real design floor rather than a restatement of the
geometry: the binding case is where the outline crosses the LED ring channel,
where what is left is LED_RING_ROOF less FDM_OUTLINE_DEPTH, and this is three
0.2 layers under that. Deepening the groove or thinning the ring roof is what
this is here to stop, in either order."""

WIDTH_TOLERANCE = 0.02
"""How far the built band's mean width may sit from FDM_OUTLINE_W."""

EDGE_TOLERANCE = 0.02
"""Slack on the two edge readings. EDGE_R_FRONT_FDM is set to exactly the bound
the outline leaves, so both come out on their limit and this is offset and
boolean slop only."""

PLANE_TOLERANCE = 1e-6
"""How flat a face has to lie to count as the front's own outer plane."""

BOX_TOLERANCE = 0.01
"""How far the built band's own bounding box may sit from the outline's, grown
by half a width."""

TOP_FILLET_TOLERANCE = 0.02
"""Allowed radial error on an FDM keytop's exposed-edge fillet.

This is boolean and curve approximation slop. The sampled profile is an arc,
so a larger difference means the top edge is sharp or has a different radius.
"""


def fdm_pad_fits(front, pad):
    """Probe the complete FDM button export against its matching front shell."""
    problems = []
    for state, offset in (("released", 0), ("pressed", -params.SWITCH_TRAVEL)):
        fouled = _volume(front.intersect(Pos(0, 0, offset) * pad))
        if fouled > TOLERANCE:
            problems.append(
                Problem(
                    f"the FDM pad fouls the FDM front by {fouled:.2f} mm3 when {state}",
                    part="c6remote-case-pad-fdm",
                )
            )
    return problems


def fdm_keytops_are_attached(pad):
    """Every printed keytop must be flush with and fused to its lobe web."""
    problems = []
    for ref in case.cap_refs():
        x, y = board.components()[ref][:2]
        bottom = case.fdm_keycap(ref).bounding_box().min.Z
        if abs(bottom - case.PAD_WEB_TOP) > TOLERANCE:
            problems.append(
                Problem(
                    f"{ref}'s FDM keytop starts at {bottom:.3f}, but its pad web "
                    f"ends at {case.PAD_WEB_TOP:.3f}",
                    at=(x, y, bottom),
                    part="c6remote-case-pad-fdm",
                )
            )
        top = Pos(x, y, (case.CAP_BOTTOM + case.CAP_TOP) / 2) * Box(
            case.fdm_cap_body(ref) / 3,
            case.fdm_cap_body(ref) / 3,
            (case.CAP_TOP - case.CAP_BOTTOM) / 3,
        )
        web = Pos(x, y, (case.PAD_WEB_BOTTOM + case.PAD_WEB_TOP) / 2) * Box(
            params.STEM_W / 3,
            params.STEM_W / 3,
            params.PAD_WEB_T / 2,
        )
        top_solids = [solid for solid in pad.solids() if _volume(solid.intersect(top)) > TOLERANCE]
        web_solids = [solid for solid in pad.solids() if _volume(solid.intersect(web)) > TOLERANCE]
        if len(top_solids) != 1 or top_solids != web_solids:
            problems.append(
                Problem(
                    f"{ref}'s FDM keytop is not fused to its pad lobe",
                    at=(x, y, case.CAP_TOP),
                    part="c6remote-case-pad-fdm",
                )
            )
    return problems


def fdm_keytops_have_top_fillets():
    """Probe each blank FDM keytop's built side profile for the rigid cap's
    exposed-top fillet.

    The ray runs along the plan's X axis, clear of the legend. A fillet of
    CAP_TOP_FILLET has a quarter-circle profile. Three heights prove that the
    exposed edge is the same radius, while the flat bottom remains untouched.
    """
    problems = []
    radius = params.CAP_TOP_FILLET
    for ref in case.cap_refs():
        x, y = board.components()[ref][:2]
        keytop = case.fdm_keycap(ref, legend=False)
        half = case.fdm_cap_body(ref) / 2
        for depth in (radius / 4, radius / 2, 3 * radius / 4):
            z = case.CAP_TOP - depth
            reach = half + radius + 1
            runs = _ray_runs(keytop, (x - reach, y, z), (x + reach, y, z))
            if len(runs) != 1:
                problems.append(
                    Problem(
                        f"{ref}'s FDM keytop has {len(runs)} material runs at its "
                        "top-edge fillet probe",
                        at=(x, y, z),
                        part="c6remote-case-pad-fdm",
                    )
                )
                break
            got = runs[0][1] - reach
            want = half - radius + math.sqrt(radius**2 - (radius - depth) ** 2)
            if abs(got - want) > TOP_FILLET_TOLERANCE:
                problems.append(
                    Problem(
                        f"{ref}'s FDM keytop reaches {got:.3f} from its centre "
                        f"{depth:.3f} below its top, where a {radius:.2f} mm "
                        f"fillet reaches {want:.3f}",
                        at=(x + got, y, z),
                        part="c6remote-case-pad-fdm",
                    )
                )
                break
    return problems


def _samples():
    """[(x, y)] evenly spaced along the outline's centreline."""
    wire = case.recess_outline().faces()[0].outer_wire()
    out = []
    for i in range(OUTLINE_SAMPLES):
        point = wire @ (i / OUTLINE_SAMPLES)
        out.append((point.X, point.Y))
    return out


def face_is_flat(front):
    """The FDM front's outer surface is one plane at FDM_FACE, at every site
    checks/keypad.py reads the recessed front's dish at.

    One ray down per site rather than a pair of fill probes. What the ray gives
    is where the surface is, so this reads the same whether a dish survived into
    the variant, which puts the surface below the plane, or the face was built
    at the wrong height, which puts it anywhere else, and it needs no reference
    to how deep the recess would have been there. The sites are
    checks/keypad.py's own, so the two passes read the same places with opposite
    verdicts: dished there, flat here.
    """
    problems = []
    top_z = case.FDM_FACE + FACE_PROBE_START
    for label, x, y in _probe_sites():
        if x is None or y is None:
            continue
        runs = _ray_runs(front, (x, y, top_z), (x, y, case.CAVITY_FRONT - 1))
        if not runs:
            problems.append(
                Problem(
                    f"the FDM face has no material under it at all {label}",
                    at=(x, y, case.FDM_FACE),
                    part="c6remote-case-front-fdm",
                )
            )
            continue
        surface = top_z - runs[0][0]
        if abs(surface - case.FDM_FACE) > FACE_TOLERANCE:
            problems.append(
                Problem(
                    f"the FDM front's surface is at {surface:.3f} {label} where "
                    f"FDM_FACE says {case.FDM_FACE:.3f}: this face has to be one "
                    f"flat plane to print face down",
                    at=(x, y, surface),
                    part="c6remote-case-front-fdm",
                )
            )
    return problems


def outline_is_cut(front):
    """The slot is cut where the outline is, to FDM_OUTLINE_DEPTH, and leaves
    at least OUTLINE_ROOF_MIN of material under it everywhere.

    One ray per sample, down through the face into the cavity. The first run of
    material along it starts at the groove's floor and ends at whatever opens
    below, so one reading gives both the depth that was cut and the roof that
    is left. A sample with no run at all is the groove opening straight into
    the cavity, which is the failure the LED ring channel could produce.
    """
    missing, shallow, thin = [], [], []
    top = case.FDM_FACE + OUTLINE_START
    bottom = case.CAVITY_FRONT - 1
    for x, y in _samples():
        runs = _ray_runs(front, (x, y, top), (x, y, bottom))
        if not runs:
            missing.append((x, y))
            continue
        start, end = runs[0]
        depth = start - OUTLINE_START
        if abs(depth - params.FDM_OUTLINE_DEPTH) > OUTLINE_DEPTH_TOLERANCE:
            shallow.append((depth, x, y))
        if end - start < OUTLINE_ROOF_MIN:
            thin.append((end - start, x, y))

    # One line per kind of failure rather than per sample. The samples have no
    # names of their own, so a hundred identical lines would say nothing the
    # worst one does not; the count is what says whether a stretch of the
    # outline went or a single point did.
    problems = []
    if missing:
        x, y = missing[0]
        problems.append(
            Problem(
                f"{len(missing)} of {OUTLINE_SAMPLES} points on the outline have "
                f"no material under them at all: the groove opens straight into "
                f"the cavity",
                at=(x, y, case.FDM_FACE),
                part="c6remote-case-front-fdm",
            )
        )
    if shallow:
        depth, x, y = max(shallow, key=lambda s: abs(s[0] - params.FDM_OUTLINE_DEPTH))
        problems.append(
            Problem(
                f"{len(shallow)} of {OUTLINE_SAMPLES} points on the outline are "
                f"cut to the wrong depth, worst {depth:.3f} where "
                f"FDM_OUTLINE_DEPTH says {params.FDM_OUTLINE_DEPTH:.3f}",
                at=(x, y, case.FDM_FACE - depth),
                part="c6remote-case-front-fdm",
            )
        )
    if thin:
        roof, x, y = min(thin)
        problems.append(
            Problem(
                f"{len(thin)} of {OUTLINE_SAMPLES} points on the outline leave "
                f"under {OUTLINE_ROOF_MIN:.2f} of material below the groove, "
                f"thinnest {roof:.2f}",
                at=(x, y, case.FDM_FACE - params.FDM_OUTLINE_DEPTH),
                part="c6remote-case-front-fdm",
            )
        )
    return problems


def outline_solid_sane():
    """The cut itself is one band of the width and depth it was built from.

    Measured off the built solid. A 2D offset is the one operation here that
    can hand back a self-intersecting wire, on a concave turn tighter than the
    offset, and what that produces is a band that pinches shut or doubles back
    over itself. Neither shows in the shell it is cut from, because a cut by a
    pinched band is still a cut; it shows as a mean width that is not the width
    it was asked for.
    """
    groove = case.keypad_outline_groove()
    problems = []
    if len(groove.solids()) != 1:
        problems.append(
            f"the outline groove came out as {len(groove.solids())} solids, not one"
        )
    if groove.volume <= 0:
        problems.append(f"the outline groove has a volume of {groove.volume:.2f}")
        return problems

    height = params.FDM_OUTLINE_DEPTH + case.MERGE
    width = groove.volume / height / case.outline_length()
    if abs(width - params.FDM_OUTLINE_W) > WIDTH_TOLERANCE:
        problems.append(
            f"the built groove averages {width:.3f} wide where FDM_OUTLINE_W "
            f"says {params.FDM_OUTLINE_W:.3f}: the offset that made it did not "
            f"hold its own width"
        )

    plan = case.recess_outline().bounding_box()
    box = groove.bounding_box()
    half = params.FDM_OUTLINE_W / 2


    for what, got, want in (
        ("min x", box.min.X, plan.min.X - half),
        ("max x", box.max.X, plan.max.X + half),
        ("min y", box.min.Y, plan.min.Y - half),
        ("max y", box.max.Y, plan.max.Y + half),
        ("min z", box.min.Z, case.FDM_FACE - params.FDM_OUTLINE_DEPTH),
        ("max z", box.max.Z, case.FDM_FACE + case.MERGE),
    ):
        if abs(got - want) > BOX_TOLERANCE:
            problems.append(
                f"the groove's {what} is {got:.3f} where the outline it was "
                f"offset from says {want:.3f}"
            )
    return problems


def _roof_at(front, x, y):
    """Thickness of the first material the FDM front has under its own face at
    (x, y), or None where it has none at all.

    The face is one plane, so the first run down from above it starts at that
    plane and ends at whatever void is under it. That run is the ceiling, and
    which ceiling it is depends only on where the ray is put.
    """
    top = case.FDM_FACE + FACE_PROBE_START
    runs = _ray_runs(front, (x, y, top), (x, y, case.BOARD_TOP))
    if not runs:
        return None
    start, end = runs[0]
    return end - start


def ceilings_hold(front):
    """The three ceilings FDM_FACE_DROP thins are all still above their floors.

    The drop is the one thing about this variant that takes material from
    somewhere the keypad recess never touched. The recess is a dish in the
    middle of the face; the drop is the whole plane, so it comes off the USB
    pocket's roof, the LED ring's roof and every counterbore's land alike, none
    of which the dish reaches. Each is read off the built shell against the same
    floor the recessed front's own pass holds it to, so the two fronts are
    judged by one standard and the drop cannot be widened past what any of them
    can give.

    The ring is the tight one. Its roof is LED_RING_ROOF less the drop, and
    LED_RING_ROOF is the smallest of the three to begin with.
    """
    problems = []
    usb = board.usb_envelope()
    ring_r = (case.led_ring_roof_inner_r() + case.led_ring_roof_outer_r()) / 2
    wx, wy = board.wheel_center()
    sites = [
        ("the USB pocket's roof", usb.center().X, usb.center().Y, USB_CEILING_MIN),
        ("the LED ring's roof", wx + ring_r, wy, ROOF_LEFT_MIN),
        ("the LED ring's roof opposite", wx - ring_r, wy, ROOF_LEFT_MIN),
    ]
    parts = board.components()
    for ref in board.refs("SW"):
        x, y = parts[ref][:2]
        # Mid-ring between the face hole and the counterbore wall, as
        # checks/keypad.py's recess_land() reads the same land on the other
        # front. The counterbore is square, so the ring is a constant width
        # along a flat and this is as good a spot on it as any.
        r = (case.cap_face_hole(ref) + case.cap_counterbore(ref)) / 4
        sites.append((f"{ref}'s face land", x + r, y, LAND_FLOOR_MIN))

    for label, x, y, floor in sites:
        roof = _roof_at(front, x, y)
        if roof is None:
            problems.append(
                Problem(
                    f"{label} has no material in it at all",
                    at=(x, y, case.FDM_FACE),
                    part="c6remote-case-front-fdm",
                )
            )
            continue
        if roof < floor - TOLERANCE:
            problems.append(
                Problem(
                    f"{label} is {roof:.2f} thick on the FDM front, against a "
                    f"floor of {floor:.2f}: FDM_FACE_DROP has taken more than "
                    f"this ceiling had to give",
                    at=(x, y, case.FDM_FACE - roof),
                    part="c6remote-case-front-fdm",
                )
            )
    return problems


def _wall_gap(x0, x1, y0, y1):
    """How far a plan extent stays inside the case's exterior wall, at its
    closest of the four sides."""
    ex0, ex1 = case.exterior_x_bounds()
    ey0, ey1 = case.exterior_y_bounds()
    return min(x0 - ex0, ex1 - x1, y0 - ey0, ey1 - y1)


def edge_round_is_hard(front):
    """The FDM front's top edge round is EDGE_R_FRONT_FDM's, and the groove sits
    on the flat it leaves with FDM_OUTLINE_EDGE_CLEAR to spare.

    Read off the built shell's own outer plane rather than off the radius that
    was passed to fillet(). What the round costs is flat face, and flat face is
    what the outline needs, so the thing worth measuring is how much of it came
    out. The groove cuts that plane into two regions, the island inside the
    outline and the field outside it, so the extent is taken over every face
    lying in the plane rather than over one.
    """
    front_plane = case.FDM_FACE
    boxes = [
        face.bounding_box()
        for face in front.faces()
        if abs(face.bounding_box().min.Z - front_plane) < PLANE_TOLERANCE
        and abs(face.bounding_box().max.Z - front_plane) < PLANE_TOLERANCE
    ]
    if not boxes:
        return [
            Problem(
                "the FDM front has no face in its own outer plane at all",
                part="c6remote-case-front-fdm",
            )
        ]
    problems = []
    want = case.front_edge_round(True)
    got = _wall_gap(
        min(b.min.X for b in boxes),
        max(b.max.X for b in boxes),
        min(b.min.Y for b in boxes),
        max(b.max.Y for b in boxes),
    )
    if abs(got - want) > EDGE_TOLERANCE:
        problems.append(
            Problem(
                f"the FDM front's flat face stops {got:.2f} short of the wall "
                f"where EDGE_R_FRONT_FDM says {want:.2f}: the round it was "
                f"built with is not the one this front is supposed to carry",
                part="c6remote-case-front-fdm",
            )
        )

    groove = case.keypad_outline_groove().bounding_box()
    left = _wall_gap(groove.min.X, groove.max.X, groove.min.Y, groove.max.Y) - got
    if left < params.FDM_OUTLINE_EDGE_CLEAR - EDGE_TOLERANCE:
        problems.append(
            Problem(
                f"only {left:.2f} of flat face is left outboard of the groove, "
                f"against FDM_OUTLINE_EDGE_CLEAR's {params.FDM_OUTLINE_EDGE_CLEAR:.2f}: "
                f"the outline is on the shoulder of the edge round, and at zero "
                f"its outer edge goes coincident with that round's own and tears "
                f"the exported mesh",
                part="c6remote-case-front-fdm",
            )
        )
    return problems
