"""Shells mate: the front and the back do not occupy the same space, except the
side catch preload on the lower pocket lip. Nothing else covers it, because
every other pass measures a shell against the board.

Interference: components the shells and the plate actually hit in 3D, each
one either a missing aperture or a keepout parameter set too tight.

IR-end lap wall: the back lap keeps LAP_MIN_WALL of wall to its outer round
around the IR end, from the floor of the skirt relief up. The pass measures the
built back shell, so a deeper relief behind the lap fails it.

Seam shadow line: the groove round the outer top edge of the back lap is open
at stations round the whole perimeter, stops at its depth and height, and
leaves LAP_MIN_WALL of lap behind it. Each front closes over the groove as its
ceiling and leaves the groove open.

Parts are sound: every part that gets exported is a valid solid and meshes to a
closed manifold. This is the only pass in the suite that looks at a mesh, and it
exists because everything else looks at the BRep instead. A shell can be torn
open in the STL, which is the artifact that ships and the only thing anyone ever
renders, while every probe in every other module reads the solid behind it and
reports clean.

One-piece front: the recessed front with the ring insert fused in is one solid
with one shell, so no void is closed inside it where the two parts met. It
holds every point that the recessed front and the insert without its feet
hold. Rays read both builds on the ring, on each lobe and across the whole
part.

One-piece back: the back with the IR window fused in is one solid with one
shell. It holds every point that the back and the window hold, and the only
material it adds is the closed IR_WINDOW_FIT gap round the flange. Rays read
both builds over the window and across the whole part.
"""

import math
from collections import Counter

import board
import params

from build123d import Box, Compound, GeomType, Pos, Rot, Vertex

from model import shells
from model.hardware import end_screw_axis, end_screw_block_span
from model.ir import emitter_bore, ir_window_span
from model.qwiic import qwiic_slot
from model.stack import (
    BOARD_TOP,
    CAVITY_FRONT,
    LAP_IN,
    LAP_OUT,
    SHELL_BACK,
    SHELL_FRONT,
    SHELL_SEAM,
    SKIRT_BOTTOM,
    SKIRT_OUT,
    SUPPORT_TOP,
    WHEEL_OPENING_R,
)
from model.support import front_support_cuts
from model.usb import usb_slot

from .common import (
    CROP_MARGIN,
    RUN_MIN,
    TOLERANCE,
    Problem,
    _Crop,
    _ray_runs,
    _volume,
)


EXPORT_STEMS = {
    "front shell": "case-front",
    "one-piece front shell": "case-front-one-piece",
    "back shell": "case-back",
    "one-piece back shell": "case-back-one-piece",
    "button pad": "case-pad",
    "FDM V2 top pad": "case-pad-fdm-v2-top",
    "moulded V2 top pad": "case-pad-v2-top",
    "IR window": "ir-window",
    "end screw": "case-screw",
}


def _stem(name):
    """The export file's stem for a part's display name. A failure that belongs to
    a whole part has no place on it to point at, so the part itself is what a
    viewer has to be handed, and the file it exports to is the one name both
    sides already agree on."""
    if name in EXPORT_STEMS:
        return EXPORT_STEMS[name]
    ref, _, kind = name.partition(" ")
    return f"cap-{ref.lower()}" if kind == "cap" else None


def _solids(shape):
    return list(shape.solids()) if shape else []


def side_catch_zones():
    """One box around each side catch: the pocket's length, the skirt band from
    the ledges to the seam, and the skirt's full thickness out to the lap."""
    board_box = board.board_profile().bounding_box()
    y = shells.side_catch_y()
    zones = []
    for side, edge, name in (
        (-1, board_box.min.X, "-X"),
        (1, board_box.max.X, "+X"),
    ):
        inner = edge + side * (params.BOARD_FIT - params.SIDE_SKIRT_THICKEN)
        lap = edge + side * LAP_IN
        zone = Pos((inner + lap) / 2, y, (SUPPORT_TOP + SHELL_SEAM) / 2) * Box(
            abs(lap - inner), params.SIDE_CATCH_W, SHELL_SEAM - SUPPORT_TOP
        )
        zones.append((name, side, edge, zone))
    return zones


def shells_mate(front, back):
    """The two shells must not occupy the same space, except the side catch
    preload. Returns the problems and each side's preload reading.

    Nothing else covers this. Every other pass measures a shell against the board,
    so a mating feature cut on the wrong side, or a fit that went negative, passes
    all of them and only shows up when the parts will not close.

    The side detents overlap the skirt by design, so each catch has a box where
    overlap is allowed. Inside it the overlap must be the designed kind: the
    release flank on the pocket's lower lip. Its top stays below the pocket
    centre, its inner edge short of the pocket floor, and its ends inside the
    lip's straight run. Anywhere else TOLERANCE holds as before.
    """
    pieces = _solids(front.intersect(back))
    if not pieces:
        return [], {}
    overlap = Compound(pieces)
    zones = side_catch_zones()
    problems = []
    outside = _solids(overlap.cut(*(zone for *_, zone in zones)))
    fouled = sum(solid.volume for solid in outside)
    if fouled > TOLERANCE:
        problems.append(Problem(
            f"front and back overlap by {fouled:.2f} mm3 outside the side catches",
            box=Compound(outside),
        ))
    y = shells.side_catch_y()
    centre = shells.side_catch_bottom() + params.SIDE_CATCH_H / 2
    floor = SKIRT_OUT - params.SIDE_CATCH_POCKET_DEPTH
    straight = params.SIDE_CATCH_W / 2 - params.SIDE_CATCH_R
    readings = {}
    for name, side, edge, zone in zones:
        inside = _solids(overlap.intersect(zone))
        volume = sum(solid.volume for solid in inside)
        if not inside:
            readings[name] = (0.0, None)
            continue
        found = Compound(inside)
        box = found.bounding_box()
        inner = box.min.X - edge if side > 0 else edge - box.max.X
        outer = box.max.X - edge if side > 0 else edge - box.min.X
        reach = max(abs(box.min.Y - y), abs(box.max.Y - y))
        readings[name] = (volume, (inner, outer, box.min.Z, box.max.Z, reach))
        if box.max.Z >= centre:
            problems.append(Problem(
                f"{name} side catch overlap reaches z {box.max.Z:.3f}, not below "
                f"the pocket centre {centre:.3f}: the detent bears on the upper lip",
                box=found,
            ))
        if inner <= floor:
            problems.append(Problem(
                f"{name} side catch overlap reaches {inner:.3f} from the board "
                f"edge, not short of the pocket floor at {floor:.3f}",
                box=found,
            ))
        if reach > straight:
            problems.append(Problem(
                f"{name} side catch overlap runs {reach:.3f} from the catch "
                f"centre, past the pocket's straight lip at {straight:.3f}: the "
                "detent tip is in a rounded pocket end",
                box=found,
            ))
    return problems, readings


def side_seam_retention(front, back):
    """Read the printed skirt, catch and grip relief from the built shells."""
    problems = []
    board_box = board.board_profile().bounding_box()
    y = shells.side_catch_y()
    z0 = shells.side_catch_bottom()
    z = z0 + params.SIDE_CATCH_H / 2
    z_detent = shells.side_catch_detent_centre()

    def probe(crop, label, centre, size, material):
        solid = Pos(*centre) * Box(*size)
        fraction = crop.fill_fraction(solid)
        if (material and fraction < 0.9) or (not material and fraction > 0.1):
            problems.append(Problem(
                f"{label} is {fraction:.0%} material, expected "
                f"{'solid' if material else 'open'}",
                box=solid,
            ))

    for side, edge, name in (
        (-1, board_box.min.X, "-X"),
        (1, board_box.max.X, "+X"),
    ):
        # Fixed sites inside the newly claimed material and interlock. Reading
        # the tunable itself here would let a weakened feature move its probe
        # along with it and give a vacuous pass. The detent sites are fixed
        # off SKIRT_OUT and LAP_IN and the pocket's own lips. Only the
        # engagement probes follow the detent centre, the one height at which
        # the lowered detent is full depth.
        inner = edge + side * (params.BOARD_FIT - 0.1)
        board_gap = edge + side * 0.1
        pocket_x = edge + side * (SKIRT_OUT - 0.12)
        pocket_floor_x = edge + side * (
            params.BOARD_FIT - params.SIDE_SKIRT_THICKEN
            + params.SIDE_CATCH_WALL_MIN - 0.05
        )
        lap_face = edge + side * LAP_IN
        engaged = edge + side * (SKIRT_OUT - 0.08)
        deep = edge + side * (SKIRT_OUT - 0.30)
        root = edge + side * (LAP_IN - 0.1)
        skirt_face = edge + side * (SKIRT_OUT - 0.025)
        gap_face = edge + side * (SKIRT_OUT - 0.02)
        lo_x = min(edge, lap_face) - params.WALL
        hi_x = max(edge, lap_face) + params.WALL
        lo_y = y - params.SIDE_CATCH_W / 2 - 2
        hi_y = y + params.SIDE_CATCH_W / 2 + 2
        front_crop = _Crop(front, (lo_x, lo_y, SKIRT_BOTTOM - 0.1),
                           (hi_x, hi_y, SHELL_SEAM + 0.1))
        back_crop = _Crop(back, (lo_x, lo_y, SKIRT_BOTTOM - 0.1),
                          (hi_x, hi_y, SHELL_SEAM + 0.1))
        probe(front_crop, f"{name} skirt stiffener", (inner, y - params.SIDE_CATCH_W / 2 - 0.7, z),
              (0.1, 0.2, 0.2), True)
        probe(front_crop, f"{name} board edge gap", (board_gap, y - params.SIDE_CATCH_W / 2 - 0.7, z),
              (0.1, 0.2, 0.2), False)
        probe(front_crop, f"{name} catch pocket mouth", (pocket_x, y, z),
              (0.2, 0.2, 0.2), False)
        probe(front_crop, f"{name} continuous pocket floor", (pocket_floor_x, y, z),
              (0.1, 0.2, 0.2), True)
        mouth_x = edge + side * (SKIRT_OUT - 0.05)
        floor_edge_x = edge + side * (
            SKIRT_OUT - params.SIDE_CATCH_POCKET_DEPTH + 0.05
        )
        for lip, lip_z in (
            ("lower", z0 + 0.06),
            ("upper", z0 + params.SIDE_CATCH_H - 0.06),
        ):
            probe(front_crop, f"{name} {lip} pocket bevel mouth", (mouth_x, y, lip_z),
                  (0.04, 0.12, 0.04), False)
            probe(front_crop, f"{name} {lip} pocket bevel floor", (floor_edge_x, y, lip_z),
                  (0.04, 0.12, 0.04), True)
        probe(front_crop, f"{name} interlock opening", (engaged, y, z_detent),
              (0.08, 0.2, 0.08), False)
        probe(front_crop, f"{name} skirt beside pocket", (pocket_x, y - params.SIDE_CATCH_W / 2 - 0.7, z),
              (0.2, 0.2, 0.2), True)
        probe(back_crop, f"{name} engaged detent", (engaged, y, z_detent),
              (0.08, 0.2, 0.08), True)
        probe(back_crop, f"{name} detent tip depth", (deep, y, z_detent),
              (0.08, 0.2, 0.08), True)
        # A ramp is material at the lap and open at the tip depth at one
        # height. A square block fills both sites, and a short block empties
        # both.
        for flank, flank_z in (("lower release", z0), ("upper insertion", z)):
            probe(back_crop, f"{name} {flank} ramp root", (root, y, flank_z),
                  (0.08, 0.2, 0.08), True)
            probe(back_crop, f"{name} {flank} ramp", (deep, y, flank_z),
                  (0.08, 0.2, 0.08), False)
        # Just under the lower lip, inside the skirt face: both shells hold
        # material there only while the release flank is preloaded on it.
        for crop, shell in ((front_crop, "skirt"), (back_crop, "detent")):
            probe(crop, f"{name} lower lip preload {shell}", (skirt_face, y, z0 - 0.02),
                  (0.03, 0.2, 0.02), True)
        # The lip the release flank bears on, from the nominal relief top to
        # the pocket. Fixed off SUPPORT_TOP and the fit, not the built relief,
        # so a relief that climbs into it or a pocket that drops into it
        # fails. The thin foot and crown slabs catch a small shortfall.
        lip0 = SUPPORT_TOP + params.SUPPORT_SKIRT_FIT
        lip1 = lip0 + params.SIDE_CATCH_LOWER_LAND
        lip_in = edge + side * (params.BOARD_FIT - params.SIDE_SKIRT_THICKEN + 0.05)
        lip_out = edge + side * (SKIRT_OUT - 0.05)
        lip_len = params.SIDE_CATCH_W - 2 * params.SIDE_CATCH_R
        for part, part_z0, part_z1 in (
            ("", lip0 + 0.03, lip1 - 0.03),
            (" foot", lip0 + 0.03, lip0 + 0.07),
            (" crown", lip1 - 0.07, lip1 - 0.03),
        ):
            probe(front_crop, f"{name} lower skirt lip{part}",
                  ((lip_in + lip_out) / 2, y, (part_z0 + part_z1) / 2),
                  (abs(lip_out - lip_in), lip_len, part_z1 - part_z0), True)
        probe(back_crop, f"{name} upper lip clearance",
              (gap_face, y, z0 + params.SIDE_CATCH_H - 0.08), (0.04, 0.2, 0.12), False)
        land_z = z0 + params.SIDE_CATCH_H + params.SIDE_CATCH_UPPER_LAND_MIN
        lap_x = edge + side * (LAP_IN + params.SKIRT_T / 2)
        probe(front_crop, f"{name} upper skirt land", (pocket_x, y, land_z),
              (0.2, 0.2, 0.08), True)
        probe(back_crop, f"{name} raised back lap", (lap_x, y, land_z),
              (0.2, 0.2, 0.08), True)

    end_x = board_box.center().X
    end_y = board_box.min.Y - SKIRT_OUT
    # Keep this below the USB opening; moving the side pocket upward does not
    # move the grip-end wall site whose relief this probes.
    end_z = SKIRT_BOTTOM + 1.7
    end_crop = _Crop(
        front,
        (end_x - 1, end_y - 0.5, SKIRT_BOTTOM - 0.1),
        (end_x + 1, end_y + 1, SHELL_SEAM + 0.1),
    )
    probe(end_crop, "grip-end skirt relief", (end_x, end_y + params.GRIP_SKIRT_RELIEF / 2, end_z),
          (0.2, 0.08, 0.2), False)
    probe(end_crop, "grip-end skirt behind relief", (end_x, end_y + params.GRIP_SKIRT_RELIEF + 0.18, end_z),
          (0.2, 0.08, 0.2), True)

    # The first site is fixed off the corner tangent, not the run, so a taper
    # cut short, or the old dead stop, leaves it full.
    yt0, yt1 = shells.corner_tangent_y()
    taper_y = yt0
    run = params.GRIP_SKIRT_RELIEF_RUN
    taper_z = (SKIRT_BOTTOM + SHELL_SEAM) / 2
    for side, edge, name in (
        (-1, board_box.min.X, "-X"),
        (1, board_box.max.X, "+X"),
    ):
        face = edge + side * SKIRT_OUT
        site = edge + side * (SKIRT_OUT - params.GRIP_SKIRT_RELIEF / 2)
        taper_crop = _Crop(
            front,
            (face - 1, taper_y - 0.5, SKIRT_BOTTOM - 0.1),
            (face + 1, taper_y + run + 1.5, SHELL_SEAM + 0.1),
        )
        probe(taper_crop, f"{name} grip relief taper start", (site, taper_y + 0.3, taper_z),
              (0.08, 0.2, 0.2), False)
        probe(taper_crop, f"{name} skirt past grip relief taper", (site, taper_y + run + 0.6, taper_z),
              (0.08, 0.2, 0.2), True)

    # The stiffener runs round the grip corners at full thickness and stops
    # short of the IR ones, so 1.0 past each tangent the grip arcs are
    # material inboard of the plain fit and the IR arcs are open.
    for arc in board.board_profile().outer_wire().edges():
        if arc.geom_type != GeomType.CIRCLE:
            continue
        centre = arc.arc_center
        side = 1 if centre.X > board_box.center().X else -1
        end = 1 if centre.Y > board_box.center().Y else -1
        y = (yt1 if end > 0 else yt0) + end * 1.0
        radius = arc.radius + params.BOARD_FIT - 0.1
        x = centre.X + side * math.sqrt(radius ** 2 - (y - centre.Y) ** 2)
        label = f"{'+X' if side > 0 else '-X'} {'IR' if end > 0 else 'grip'}"
        crop = _Crop(front, (x - 0.5, y - 0.5, taper_z - 0.5), (x + 0.5, y + 0.5, taper_z + 0.5))
        probe(crop, f"{label} corner arc inboard of the board fit", (x, y, taper_z),
              (0.06, 0.06, 0.2), end < 0)

    # The grip end wall, between the -X corner tangent and whichever of the
    # USB slot and the end screw block web starts first.
    ends = [
        e.bounding_box()
        for e in board.board_profile().outer_wire().edges()
        if e.geom_type == GeomType.LINE
        and e.bounding_box().size.Y < 1e-6
        and abs(e.bounding_box().min.Y - board_box.min.Y) < 1e-6
    ]
    wall_x0 = min(b.min.X for b in ends)
    wall_x1 = min(usb_slot().bounding_box().min.X, end_screw_block_span()[0])
    x = (wall_x0 + wall_x1) / 2
    y = board_box.min.Y - (params.BOARD_FIT - 0.1)
    crop = _Crop(front, (x - 0.5, y - 0.5, taper_z - 0.5), (x + 0.5, y + 0.5, taper_z + 0.5))
    probe(crop, f"grip end wall inboard of the board fit at x {x:.2f}", (x, y, taper_z),
          (0.2, 0.06, 0.2), True)

    # Past the IR-end taper the stiffener is back to full thickness.
    thick = params.BOARD_FIT - params.SIDE_SKIRT_THICKEN + 0.05
    at = yt1 - (params.SIDE_SKIRT_THICKEN_RUN + 0.5)
    for side, edge, name in (
        (-1, board_box.min.X, "-X"),
        (1, board_box.max.X, "+X"),
    ):
        x = edge + side * thick
        crop = _Crop(front, (x - 0.5, at - 0.5, taper_z - 0.5), (x + 0.5, at + 0.5, taper_z + 0.5))
        probe(crop, f"{name} full stiffener past its taper at y {at:.2f}", (x, at, taper_z),
              (0.06, 0.2, 0.2), True)

    # The stiffener reaches the ceiling, so the wall has no step at the seam or
    # where the LED ring channel meets it beside the wheel.
    flush = params.BOARD_FIT - 0.1
    flush_z = SHELL_SEAM + 0.3
    side_y = shells.side_catch_y() - params.SIDE_CATCH_W / 2 - 0.7
    _, wheel_y = board.wheel_center()
    grip_x = (wall_x0 + wall_x1) / 2
    sites = []
    for side, edge, name in (
        (-1, board_box.min.X, "-X"),
        (1, board_box.max.X, "+X"),
    ):
        sites.append((
            f"{name} inner wall flush above the seam at y {side_y:.2f}",
            (edge + side * flush, side_y, flush_z), (0.06, 0.2, 0.2),
        ))
        sites.append((
            f"{name} inner wall flush under the LED ring channel at y {wheel_y:.2f}",
            (edge + side * flush, wheel_y, CAVITY_FRONT - 0.3), (0.06, 0.2, 0.2),
        ))
    sites.append((
        f"grip end inner wall flush above the seam at x {grip_x:.2f}",
        (grip_x, board_box.min.Y - flush, flush_z), (0.2, 0.06, 0.2),
    ))
    for label, (px, py, pz), size in sites:
        crop = _Crop(front, (px - 0.5, py - 0.5, pz - 0.5), (px + 0.5, py + 0.5, pz + 0.5))
        probe(crop, label, (px, py, pz), size, True)
    return problems


def side_skirt_lead_ins(front):
    """The support-break ramps remove the complete reinforced skirt width."""
    problems = []
    board_box = board.board_profile().bounding_box()
    middle_y = board_box.center().Y
    runs = front_support_cuts()
    for side, edge, name in (
        (-1, board_box.min.X, "-X"),
        (1, board_box.max.X, "+X"),
    ):
        crossing = [
            run for run in runs
            if (run.bounding_box().center().X < board_box.center().X) == (side < 0)
            and run.bounding_box().min.Y < middle_y < run.bounding_box().max.Y
        ]
        if len(crossing) != 1:
            problems.append(Problem(
                f"{name} has {len(crossing)} support runs at the board midpoint, "
                "so its lead-in has no unambiguous edge"
            ))
            continue
        edge_y = crossing[0].bounding_box().max.Y
        height = crossing[0].bounding_box().max.Z - SKIRT_BOTTOM
        run_length = height / math.tan(math.radians(params.SKIRT_LEAD_ANGLE))
        z = SKIRT_BOTTOM + 0.35
        cropped = _Crop(
            front,
            (edge - params.WALL - 1, edge_y - 0.1, SKIRT_BOTTOM - 0.1),
            (edge + params.WALL + 1, edge_y + run_length + 0.7, SHELL_SEAM + 0.1),
        )
        for position, radial in (
            ("outer", SKIRT_OUT - 0.15),
            ("reinforced inner", params.BOARD_FIT - 0.1),
        ):
            x = edge + side * radial
            for label, y, should_be_material in (
                ("ramp", edge_y + run_length / 2, False),
                ("skirt after ramp", edge_y + run_length + 0.35, True),
            ):
                probe = Pos(x, y, z) * Box(0.12, 0.12, 0.12)
                filled = cropped.fill_fraction(probe)
                if (should_be_material and filled < 0.9) or (
                    not should_be_material and filled > 0.1
                ):
                    problems.append(Problem(
                        f"{name} {position} {label} is {filled:.0%} material, "
                        f"expected {'solid' if should_be_material else 'open'}",
                        box=probe,
                    ))
            # Near the top of the lead-in the original triangular ramp is
            # almost zero-width. This site reads the added fit strip itself.
            if params.SKIRT_LEAD_FIT > 0:
                fit_probe = Pos(
                    x,
                    edge_y + 0.8 * params.SKIRT_LEAD_FIT,
                    SKIRT_BOTTOM + height - 0.05,
                ) * Box(0.02, 0.02, 0.02)
                filled = cropped.fill_fraction(fit_probe)
                if filled > 0.1:
                    problems.append(Problem(
                        f"{name} {position} lead-in fit strip is {filled:.0%} "
                        "material, expected clearance for printed oversize",
                        box=fit_probe,
                    ))
    return problems


LAP_CORNER_ANGLES = (15.0, 35.0, 55.0, 75.0)
"""Plan angles of the corner stations, in degrees from the side normal toward
+Y. The four angles sample the corner round between the side and the end wall."""

LAP_STUB_STEPS = (0.0, 1.5)
"""Distances of the side stub stations back along -Y from each corner tangent.
The IR-end support runs stop short of the second station."""

LAP_FAN = tuple(range(0, 71, 10))
"""Ray angles below horizontal, in degrees, in the plane of the plan normal. The
shortest run of material over this fan approximates the wall normal to the
outer round."""

LAP_RISE = 1.0
LAP_STEP = 0.2
"""The pass reads the lap from the built relief floor up LAP_RISE, at this step."""

LAP_RAY = 4.0
"""Length of each ray. A longer run of material than this reads as this length,
and that is well above LAP_MIN_WALL."""

LAP_EPS = 0.01
"""Distance from a face or from the relief floor to the start of each ray and
level, so that no ray starts on a face."""


def ir_end_lap_stations():
    """(name, plan point, outward plan normal) for each station around the IR end.

    The plan point is on the board outline. A point at offset `d` is the plan
    point plus `d` along the normal, because the offset profiles keep the
    board's corner centres. The corners come from the arcs of the board outline.
    """
    profile = board.board_profile()
    box = profile.bounding_box()
    corners = sorted(
        (
            edge
            for edge in profile.outer_wire().edges()
            if edge.geom_type == GeomType.CIRCLE and edge.arc_center.Y > box.center().Y
        ),
        key=lambda edge: edge.arc_center.X,
    )
    if len(corners) != 2:
        raise ValueError(
            f"expected two corner arcs at the IR end of the board, found {len(corners)}"
        )
    stations = []
    for edge in corners:
        centre, radius = edge.arc_center, edge.radius
        side = 1 if centre.X > box.center().X else -1
        label = "+X" if side > 0 else "-X"
        for step in LAP_STUB_STEPS:
            stations.append((
                f"{label} side stub {step:.1f} before the corner",
                (centre.X + side * radius, centre.Y - step),
                (float(side), 0.0),
            ))
        for angle in LAP_CORNER_ANGLES:
            a = math.radians(angle)
            normal = (side * math.cos(a), math.sin(a))
            stations.append((
                f"{label} corner at {angle:.0f} degrees",
                (centre.X + radius * normal[0], centre.Y + radius * normal[1]),
                normal,
            ))
    minus_x, plus_x = shells.catch_x()
    for label, x in (
        ("behind the -x detent", minus_x),
        ("at the centreline", box.center().X),
        ("behind the +x detent", plus_x),
    ):
        stations.append((f"end wall {label}", (x, box.max.Y), (0.0, 1.0)))
    return stations


def ir_end_lap_wall(back):
    """The thinnest wall the built back lap keeps around the IR end.

    Each station starts in the skirt relief void at the skirt's inner face, at
    SKIRT_BOTTOM. A ray along the outward plan normal finds the lap's inner
    face. A ray down just inboard of that face finds the relief floor, so a
    deeper relief moves every level down with it. From the floor up LAP_RISE,
    each level finds the lap face again. Then the shortest run of material over
    the LAP_FAN rays from that face gives the wall normal to the outer round.

    Returns the problems and the thinnest reading as (wall, station, z, point).
    """
    stations = ir_end_lap_stations()
    near = params.BOARD_FIT
    far = LAP_OUT + LAP_RAY
    xs, ys = [], []
    for _, (px, py), (nx, ny) in stations:
        for offset in (near - LAP_EPS, far):
            xs.append(px + nx * offset)
            ys.append(py + ny * offset)
    margin = CROP_MARGIN
    crop = _Crop(
        back,
        (min(xs) - margin, min(ys) - margin, SHELL_BACK - LAP_RAY - margin),
        (max(xs) + margin, max(ys) + margin, SHELL_SEAM + margin),
    )
    problems = []
    thinnest = None
    levels = int(round(LAP_RISE / LAP_STEP)) + 1
    for name, (px, py), (nx, ny) in stations:
        def at(offset, z):
            return (px + nx * offset, py + ny * offset, z)

        def lap_face(z):
            runs = crop.ray_runs(at(near, z), at(far, z))
            if not runs or runs[0][0] < LAP_EPS:
                return None
            return near + runs[0][0]

        face = lap_face(SKIRT_BOTTOM)
        if face is None:
            problems.append(Problem(
                f"{name} has no skirt relief void at SKIRT_BOTTOM {SKIRT_BOTTOM:.2f} "
                "with a lap face outboard of it, so the lap wall has no reading",
                at=at(near, SKIRT_BOTTOM),
            ))
            continue
        column = at(face - LAP_EPS, SKIRT_BOTTOM)
        down = crop.ray_runs(column, (column[0], column[1], SHELL_BACK - 0.5))
        if not down:
            problems.append(Problem(
                f"{name} relief has no floor under the lap face", at=column,
            ))
            continue
        floor = SKIRT_BOTTOM - down[0][0]
        worst = None
        for level in range(levels):
            z = floor + max(level * LAP_STEP, LAP_EPS)
            face = lap_face(z)
            if face is None:
                problems.append(Problem(
                    f"{name} has no lap face outboard of the relief at z {z:.2f}",
                    at=at(near, z),
                ))
                continue
            start = at(face - LAP_EPS, z)
            for angle in LAP_FAN:
                a = math.radians(angle)
                end = (
                    start[0] + nx * LAP_RAY * math.cos(a),
                    start[1] + ny * LAP_RAY * math.cos(a),
                    z - LAP_RAY * math.sin(a),
                )
                runs = crop.ray_runs(start, end)
                # The ray must enter material at the face it starts beside.
                if not runs or runs[0][0] > LAP_EPS / math.cos(a) + LAP_EPS:
                    continue
                wall = runs[0][1] - runs[0][0]
                if worst is None or wall < worst[0]:
                    worst = (wall, name, z, at(face, z))
        if worst is None:
            problems.append(Problem(
                f"{name} lap has no ray reading at any level", at=column,
            ))
            continue
        if thinnest is None or worst[0] < thinnest[0]:
            thinnest = worst
        wall, _, z, point = worst
        if wall < params.LAP_MIN_WALL - 0.02:
            problems.append(Problem(
                f"{name}: back lap wall is {wall:.2f} mm at z {z:.2f}, under "
                f"LAP_MIN_WALL {params.LAP_MIN_WALL:.2f} (relief floor at "
                f"z {floor:.2f})",
                at=point,
            ))
    return problems, thinnest


SEAM_SHADOW_RUN_STATIONS = 5
"""Evenly spaced stations along each long side between its corner tangents."""

SEAM_SHADOW_END_STATIONS = 3
"""Evenly spaced stations along each end between its corner tangents."""

SEAM_SHADOW_CORNER_ANGLES = (20.0, 45.0, 70.0)
"""Plan angles of the corner stations, in degrees from the side normal toward
the end normal."""

SEAM_SHADOW_INSET = 0.03
"""Inset of the open groove probe from each face of the groove, so the probe
reads the whole groove section but not the faces round it."""

SEAM_SHADOW_PROBE_W = 0.2
"""Length of each probe along the perimeter."""

SEAM_SHADOW_READ_TOL = 0.02
"""How far the built groove depth and height may differ from SEAM_SHADOW_DEPTH
and SEAM_SHADOW_H."""


def seam_shadow_stations():
    """(name, plan point, outward plan normal, front) round the whole perimeter.

    Evenly spaced stations on both long sides and both ends, three on each
    corner arc, and one over each opening, catch and screw in the wall below
    the seam, so a groove that breaks over one of them fails. The plan point is
    on the board outline. A point at offset `d` is the plan point plus `d` along
    the normal, because the offset profiles keep the board's corner centres.
    `front` marks the stations that the front shells are also read at: the
    middle of each side and end, and each corner at 45 degrees.
    """
    profile = board.board_profile()
    box = profile.bounding_box()
    edges = profile.outer_wire().edges()
    yt0, yt1 = shells.corner_tangent_y()
    ends = [
        e.bounding_box() for e in edges
        if e.geom_type == GeomType.LINE and e.bounding_box().size.Y < 1e-6
    ]
    xt0, xt1 = min(b.min.X for b in ends), max(b.max.X for b in ends)
    middle_run = SEAM_SHADOW_RUN_STATIONS // 2
    middle_end = SEAM_SHADOW_END_STATIONS // 2
    stations = []
    for side, x, label in ((-1, box.min.X, "-X"), (1, box.max.X, "+X")):
        for i in range(SEAM_SHADOW_RUN_STATIONS):
            y = yt0 + (i + 0.5) / SEAM_SHADOW_RUN_STATIONS * (yt1 - yt0)
            stations.append(
                (f"{label} side at y {y:.2f}", (x, y), (float(side), 0.0), i == middle_run)
            )
        stations.append((
            f"{label} side over the side catch", (x, shells.side_catch_y()),
            (float(side), 0.0), False,
        ))
    for end, y, label in ((-1, box.min.Y, "grip end"), (1, box.max.Y, "IR end")):
        for i in range(SEAM_SHADOW_END_STATIONS):
            x = xt0 + (i + 0.5) / SEAM_SHADOW_END_STATIONS * (xt1 - xt0)
            stations.append(
                (f"{label} at x {x:.2f}", (x, y), (0.0, float(end)), i == middle_end)
            )
    slot = qwiic_slot().bounding_box()
    qwiic_side = -1 if slot.center().X < box.center().X else 1
    stations.append((
        f"{'-X' if qwiic_side < 0 else '+X'} side over the Qwiic slot",
        (box.min.X if qwiic_side < 0 else box.max.X, slot.center().Y),
        (float(qwiic_side), 0.0), False,
    ))
    grip = [
        ("grip end over the USB slot", usb_slot().bounding_box().center().X),
        ("grip end over the end screw", end_screw_axis()[0]),
    ]
    ir_end = [("IR end over the D1 bore", emitter_bore().bounding_box().center().X)]
    ir_end += [
        (f"IR end over the catch at x {x:.2f}", x) for x in shells.catch_x()
    ]
    for name, x in grip:
        stations.append((name, (x, box.min.Y), (0.0, -1.0), False))
    for name, x in ir_end:
        stations.append((name, (x, box.max.Y), (0.0, 1.0), False))
    for edge in edges:
        if edge.geom_type != GeomType.CIRCLE:
            continue
        centre, radius = edge.arc_center, edge.radius
        side = 1 if centre.X > box.center().X else -1
        end = 1 if centre.Y > box.center().Y else -1
        label = f"{'+X' if side > 0 else '-X'} {'IR' if end > 0 else 'grip'} corner"
        for angle in SEAM_SHADOW_CORNER_ANGLES:
            a = math.radians(angle)
            normal = (side * math.cos(a), end * math.sin(a))
            stations.append((
                f"{label} at {angle:.0f} degrees",
                (centre.X + radius * normal[0], centre.Y + radius * normal[1]),
                normal, angle == 45.0,
            ))
    return stations


def seam_shadow_line(back, fronts):
    """The seam shadow groove on the built back, and each front over it.

    `fronts` is a list of (shell, export stem). At every station, read along
    the outward plan normal. The groove section must be open, inset
    SEAM_SHADOW_INSET from each face it should have. The lap just behind the
    groove floor and the outer wall just under the groove must be material, so
    the groove neither cuts through the lap nor runs down past SEAM_SHADOW_H.

    Rays then measure the built groove. One ray at mid groove height starts in
    the skirt relief void and finds the lap wall left behind the groove. One
    ray under the groove finds the outer wall. The difference is the built
    depth. A ray down from above the seam finds the groove bottom, and so the
    built height. The lap wall must keep LAP_MIN_WALL.

    At the front stations, each front must be material just above the seam
    across the groove's whole depth, because that shoulder is the groove's
    ceiling, and it must leave the groove open.

    Returns the problems and the readings as {"stations", "fronts", "wall",
    "depth", "height"}, each of the last three a (min, max) pair or None.
    """
    depth, height = params.SEAM_SHADOW_DEPTH, params.SEAM_SHADOW_H
    inset, wide = SEAM_SHADOW_INSET, SEAM_SHADOW_PROBE_W
    mid_z = SHELL_SEAM - height / 2
    under_z = SHELL_SEAM - height - 0.1
    top_z = SHELL_SEAM + 0.5
    z_lo = SHELL_SEAM - height - 0.5
    z_hi = SHELL_SEAM + 0.6
    near, far = LAP_IN - 0.5, LAP_OUT + 0.5
    groove = LAP_OUT - depth / 2
    stations = seam_shadow_stations()
    box = board.board_profile().bounding_box()
    reach = LAP_OUT + 2
    band = (
        (box.min.X - reach, box.min.Y - reach, z_lo - CROP_MARGIN),
        (box.max.X + reach, box.max.Y + reach, z_hi + CROP_MARGIN),
    )

    def at(point, normal, offset, z):
        return (point[0] + normal[0] * offset, point[1] + normal[1] * offset, z)

    def probe(point, normal, offset, z, radial, tall):
        angle = math.degrees(math.atan2(normal[1], normal[0]))
        return Pos(*at(point, normal, offset, z)) * Rot(0, 0, angle) * Box(
            radial, wide, tall
        )

    def crop(parent, point, normal):
        ends = [at(point, normal, offset, 0) for offset in (near, far)]
        lo = (min(e[0] for e in ends) - CROP_MARGIN,
              min(e[1] for e in ends) - CROP_MARGIN, z_lo)
        hi = (max(e[0] for e in ends) + CROP_MARGIN,
              max(e[1] for e in ends) + CROP_MARGIN, z_hi)
        return _Crop(parent, lo, hi)

    def open_groove(point, normal):
        return probe(
            point, normal, groove, mid_z, depth - 2 * inset, height - 2 * inset
        )

    problems = []
    walls, depths, heights = [], [], []
    back_band = _Crop(back, *band)
    for name, point, normal, _ in stations:
        local = crop(back_band, point, normal)
        site = open_groove(point, normal)
        filled = local.fill_fraction(site)
        if filled > 0.1:
            problems.append(Problem(
                f"{name}: the seam shadow groove is {filled:.0%} material, "
                "expected open",
                box=site, part="case-back",
            ))
            continue
        for label, offset, z, tall in (
            ("lap behind the groove floor", LAP_OUT - depth - 0.1, mid_z,
             height - 2 * inset),
            ("outer wall under the groove", LAP_OUT - 0.1, under_z, 0.1),
        ):
            site = probe(point, normal, offset, z, 0.1, tall)
            filled = local.fill_fraction(site)
            if filled < 0.9:
                problems.append(Problem(
                    f"{name}: the {label} is {filled:.0%} material, expected "
                    "solid, so the groove runs past SEAM_SHADOW_DEPTH or "
                    "SEAM_SHADOW_H",
                    box=site, part="case-back",
                ))
        lap = local.ray_runs(at(point, normal, near, mid_z), at(point, normal, far, mid_z))
        wall = local.ray_runs(
            at(point, normal, near, under_z), at(point, normal, far, under_z)
        )
        if len(lap) != 1 or len(wall) != 1:
            problems.append(Problem(
                f"{name}: rays across the lap read {len(lap)} runs of material "
                f"at z {mid_z:.2f} and {len(wall)} at z {under_z:.2f}, expected "
                "one each",
                at=at(point, normal, LAP_OUT, mid_z), part="case-back",
            ))
            continue
        left = lap[0][1] - lap[0][0]
        built_depth = wall[0][1] - lap[0][1]
        walls.append(left)
        depths.append(built_depth)
        if left < params.LAP_MIN_WALL - 0.02:
            problems.append(Problem(
                f"{name}: the back lap is {left:.2f} mm behind the seam shadow "
                f"groove, under LAP_MIN_WALL {params.LAP_MIN_WALL:.2f}",
                at=at(point, normal, near + lap[0][1], mid_z), part="case-back",
            ))
        if abs(built_depth - depth) > SEAM_SHADOW_READ_TOL:
            problems.append(Problem(
                f"{name}: the built seam shadow groove is {built_depth:.3f} deep, "
                f"SEAM_SHADOW_DEPTH is {depth:.3f}",
                at=at(point, normal, near + lap[0][1], mid_z), part="case-back",
            ))
        down = local.ray_runs(
            at(point, normal, groove, top_z), at(point, normal, groove, z_lo + 0.1)
        )
        if not down:
            problems.append(Problem(
                f"{name}: no wall under the seam shadow groove down to "
                f"z {z_lo + 0.1:.2f}",
                at=at(point, normal, groove, mid_z), part="case-back",
            ))
            continue
        built_height = SHELL_SEAM - (top_z - down[0][0])
        heights.append(built_height)
        if abs(built_height - height) > SEAM_SHADOW_READ_TOL:
            problems.append(Problem(
                f"{name}: the built seam shadow groove is {built_height:.3f} tall, "
                f"SEAM_SHADOW_H is {height:.3f}",
                at=at(point, normal, groove, top_z - down[0][0]), part="case-back",
            ))

    front_stations = [s for s in stations if s[3]]
    for front, part in fronts:
        front_band = _Crop(front, *band)
        for name, point, normal, _ in front_stations:
            local = crop(front_band, point, normal)
            ceiling = probe(
                point, normal, groove, SHELL_SEAM + 0.1, depth - 2 * inset, 0.1
            )
            filled = local.fill_fraction(ceiling)
            if filled < 0.9:
                problems.append(Problem(
                    f"{name}: the {part} shoulder over the seam shadow groove is "
                    f"{filled:.0%} material, expected solid",
                    box=ceiling, part=part,
                ))
            site = open_groove(point, normal)
            filled = local.fill_fraction(site)
            if filled > 0.1:
                problems.append(Problem(
                    f"{name}: the {part} fills {filled:.0%} of the seam shadow "
                    "groove, expected open",
                    box=site, part=part,
                ))

    def span(values):
        return (min(values), max(values)) if values else None

    return problems, {
        "stations": len(stations),
        "fronts": len(front_stations),
        "wall": span(walls),
        "depth": span(depths),
        "height": span(heights),
    }


MESH_TOLERANCE = 0.05
"""Linear deflection the soundness pass tessellates at. Finer than the STL
export's own default, so a mesh that closes here closes there too."""

VERTEX_PLACES = 5
"""Decimals a mesh vertex is rounded to before edges are matched up. The
tessellator emits the shared vertices of adjacent faces at the same coordinates,
so this only has to absorb the last bit or two of float noise; a sound part
reads exactly zero open edges at this rounding, which is what makes the count
worth asserting on."""


def _open_edges(shape):
    """How many edges of `shape`'s own mesh are not shared by exactly two
    triangles. Zero for a closed manifold, and anything else is a hole in it or
    a self-overlap.

    Raises whatever the tessellator raises. A solid malformed enough that it
    cannot be meshed at all throws out of here rather than returning a count,
    and parts_are_sound() reports that as its own kind of failure: a part that
    will not mesh is a part that will not export.
    """
    vertices, triangles = shape.tessellate(MESH_TOLERANCE)
    points = [
        tuple(round(c, VERTEX_PLACES) for c in (v.X, v.Y, v.Z)) for v in vertices
    ]
    counts = Counter()
    for tri in triangles:
        pts = [points[i] for i in tri]
        for a, b in ((pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])):
            if a != b:
                counts[frozenset((a, b))] += 1
    return sum(1 for shared in counts.values() if shared != 2)


def parts_are_sound(parts):
    """Every exported part is a valid solid and meshes to a closed manifold.

    The only pass here that reads a mesh rather than the BRep behind it, and the
    reason it exists is that the two can disagree in exactly the direction that
    matters. A keypad recess lofted through an unstable spline once came back as
    a single solid that BRepCheck called valid, that filled a plausible bounding
    box, and that every local probe in checks/keypad.py agreed with; the STL cut
    from it was torn wide open across the front face and was the only place the
    damage was visible. Nobody renders a BRep.

    Three readings per part. `is_valid` is BRepCheck and is the cheap one,
    catching a solid that is already malformed. The mesh count is the one that
    would have caught that recess: it walks the triangles and requires every
    edge to be shared by exactly two of them, which is the definition of the
    closed surface a printed part has to be. And the meshing is done inside a
    try, because a solid can be broken past the point of tessellating at all;
    that throws rather than returning a torn mesh, and an exception escaping
    here would take the whole pass down instead of reporting the part.
    """
    problems = []
    for name, shape in parts.items():
        part = _stem(name)
        if not shape.is_valid:
            problems.append(Problem(f"{name} is not a valid solid", part=part))
        if len(shape.solids()) < 1:
            problems.append(Problem(f"{name} has no solid in it at all", part=part))
        if shape.volume <= 0:
            problems.append(Problem(
                f"{name} has a volume of {shape.volume:.2f}", part=part
            ))
        try:
            loose = _open_edges(shape)
        except Exception as exc:
            problems.append(Problem(
                f"{name} will not mesh at all ({type(exc).__name__}): it cannot "
                "be exported, whatever the solid behind it says",
                part=part,
            ))
            continue
        if loose:
            problems.append(Problem(
                f"{name} meshes to {loose} open or non-manifold edges: the "
                "exported surface is torn, whatever the solid behind it says",
                part=part,
            ))
    return problems


ONE_PIECE_TOL = 0.02
"""How far from the one-piece front a point of the two-part build can lie and
still count as held.

The insert's band is a ruled loft through LED_RING_STATIONS sections. Its bore
and its inner step are facets a few thousandths inside the round cuts that the
one-piece front takes, and its top is chords a few thousandths over the dish.
A point in those facets is in the two-part build and not in the one-piece
front. A real hole is a ring part that is not there, and it reads tenths."""

ONE_PIECE_RING_R = 22.6
"""Radius off the wheel axis that the dense rays reach to, past the outer face
of every lobe."""

ONE_PIECE_BEARINGS = 144
"""Bearings of the dense rays round the wheel: about one millimetre of arc at
the lobes, so each lobe takes several."""

ONE_PIECE_STEP = 0.15
"""Radial step of the rays that drop through the ring."""

ONE_PIECE_GRID = 2.0
"""Step of the coarse grid of rays over the whole part."""

ONE_PIECE_LEAN = 0.03
"""How far each ray leans off its axis for each unit along it. See
_one_piece_rays()."""

ONE_PIECE_SHOWN = 10
"""Most misses the one-piece check reports one by one. A front with no ring at
all misses on thousands of rays, and the worst few say where."""

ONE_PIECE_MEASURED = 200
"""Most misses the one-piece check measures off the surface. Each measure costs
a distance query, and a front with no ring would pay thousands of them for a
verdict that the first one already gives. The rest are only counted."""


def _one_piece_rays(front):
    """(start, end) of each ray the one-piece check reads.

    Rays that drop through a polar grid over the ring and its lobes, radial
    rays at heights from the lobe rims to the face, and a coarse grid that drops
    through the whole part. The polar grid walks each dome and each joint of
    the two-part build. The radial rays cross the bore and the band's plumb
    side. The coarse grid holds the rest of the shell.

    Every ray leans by ONE_PIECE_LEAN. A ray that runs along a face of the
    insert's loft reads a run that is not there, and a plumb ray at the bore
    radius did exactly that. A leaning ray crosses each plumb face and each
    level face, and does not run along it."""
    wx, wy = board.wheel_center()
    top = SHELL_FRONT + 1
    low = BOARD_TOP - 0.5
    drop = top - low
    lean_x, lean_y = ONE_PIECE_LEAN * drop, 0.6 * ONE_PIECE_LEAN * drop
    count = ONE_PIECE_BEARINGS
    for i in range(count):
        a = 2 * math.pi * (i + 0.5) / count
        r = WHEEL_OPENING_R - 0.3
        while r < ONE_PIECE_RING_R:
            x, y = wx + r * math.cos(a), wy + r * math.sin(a)
            yield (x, y, top), (x + lean_x, y + lean_y, low)
            r += ONE_PIECE_STEP
    near, far = WHEEL_OPENING_R - 1, ONE_PIECE_RING_R + 0.4
    rise = ONE_PIECE_LEAN * (far - near)
    for z in (2.1, 2.5, 3.0, 3.5, 3.9, 4.1, 4.2, 4.35, 4.6, 5.0, 5.5, 6.0, 6.5):
        for i in range(count):
            a = 2 * math.pi * (i + 0.25) / count
            c, s = math.cos(a), math.sin(a)
            yield (
                (wx + near * c, wy + near * s, z),
                (wx + far * c, wy + far * s, z + rise),
            )
    box = front.bounding_box()
    drop = box.max.Z - box.min.Z + 2
    x = box.min.X + 0.37
    while x < box.max.X:
        y = box.min.Y + 0.41
        while y < box.max.Y:
            yield (
                (x, y, box.max.Z + 1),
                (x + ONE_PIECE_LEAN * drop, y + 0.6 * ONE_PIECE_LEAN * drop,
                 box.min.Z - 1),
            )
            y += ONE_PIECE_GRID
        x += ONE_PIECE_GRID


def _uncovered(want, have):
    """The parts of the runs `want` that the runs `have` do not cover."""
    out = []
    for first, last in want:
        at = first
        for lo, hi in have:
            if hi <= at or lo >= last:
                continue
            if lo > at:
                out.append((at, lo))
            at = max(at, hi)
        if at < last:
            out.append((at, last))
    return [(a, b) for a, b in out if b - a > RUN_MIN]


def _merged(*run_lists):
    out = []
    for first, last in sorted(run for runs in run_lists for run in runs):
        if out and first <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], last))
        else:
            out.append((first, last))
    return out


def one_piece_front(front, insert, one_piece):
    """The one-piece front is one solid with one shell, and it holds every
    point that the recessed front and the footless ring insert hold.

    One shell is what proves that no closed void is left inside where the two
    parts met. The containment is read along rays: on each ray, the runs of
    the front and of the insert together must lie inside the runs of the
    one-piece front. The insert's loft stands a few thousandths off the true
    cuts, so a run that is not inside still passes if it is no longer than
    ONE_PIECE_TOL, or if its middle is within ONE_PIECE_TOL of the one-piece
    front's own surface. Returns the problems and the readings."""
    problems = []
    part = "case-front-one-piece"
    solids = one_piece.solids()
    shells = one_piece.shells()
    if len(solids) != 1:
        problems.append(Problem(
            f"the one-piece front is {len(solids)} solids, not one", part=part
        ))
    if len(shells) != 1:
        problems.append(Problem(
            f"the one-piece front has {len(shells)} shells, not one: a second "
            "shell is a void closed inside the part, where the insert met the "
            "front",
            part=part,
        ))
    if not one_piece.is_valid:
        problems.append(Problem("the one-piece front is not a valid solid", part=part))

    wx, wy = board.wheel_center()
    top = SHELL_FRONT + 1
    reach = ONE_PIECE_RING_R + CROP_MARGIN
    ring_box = Pos(wx, wy, (BOARD_TOP - 1 + top) / 2) * Box(
        2 * reach, 2 * reach, top - BOARD_TOP + 1
    )
    near = one_piece.intersect(ring_box)
    if isinstance(near, list):
        near = Compound(list(near))
    inner = reach - 1

    def in_box(p):
        return (
            abs(p[0] - wx) < inner and abs(p[1] - wy) < inner
            and BOARD_TOP < p[2] < top - 1
        )

    rays = held = unmeasured = 0
    worst = 0.0
    misses = []
    for start, end in _one_piece_rays(front):
        rays += 1
        want = _merged(_ray_runs(front, start, end), _ray_runs(insert, start, end))
        have = _ray_runs(one_piece, start, end)
        span = [b - a for a, b in zip(start, end)]
        length = math.sqrt(sum(c * c for c in span))
        for first, last in _uncovered(want, have):
            if last - first <= ONE_PIECE_TOL:
                held += 1
                continue
            if len(misses) >= ONE_PIECE_MEASURED:
                unmeasured += 1
                continue
            t = (first + last) / 2 / length
            p = tuple(a + t * c for a, c in zip(start, span))
            off = (near if in_box(p) else one_piece).distance_to(Vertex(*p))
            if off <= ONE_PIECE_TOL:
                held += 1
                worst = max(worst, off)
            else:
                misses.append((off, last - first, p))
    misses.sort(reverse=True)
    for off, run, p in misses[:ONE_PIECE_SHOWN]:
        problems.append(Problem(
            f"the one-piece front misses {run:.3f} of material that the "
            f"two-part build holds, {off:.3f} from its own surface, over "
            f"ONE_PIECE_TOL {ONE_PIECE_TOL:.3f}",
            at=p, part=part,
        ))
    more = len(misses) - min(len(misses), ONE_PIECE_SHOWN) + unmeasured
    if more:
        problems.append(Problem(
            f"{more} more runs miss material of the two-part build",
            part=part,
        ))
    return problems, {"rays": rays, "held": held, "worst": worst}


ONE_PIECE_BACK_STEP = 0.2
"""Step of the dense rays over the IR window. Each side of the flange and of
the closed IR_WINDOW_FIT gap then takes several rays."""

ONE_PIECE_BACK_REACH = 1.0
"""How far past the rebate the dense rays reach, into plain floor."""


def _one_piece_back_rays(back):
    """(start, end) of each ray the one-piece back check reads: a dense grid
    that drops through the IR window and a coarse grid over the whole part.
    Each ray leans by ONE_PIECE_LEAN, for the reason in _one_piece_rays()."""
    x0, x1, y0, y1 = ir_window_span()
    m = params.IR_WINDOW_FLANGE + params.IR_WINDOW_FIT + ONE_PIECE_BACK_REACH
    top, low = BOARD_TOP, SHELL_BACK - 1
    drop = top - low
    lean_x, lean_y = ONE_PIECE_LEAN * drop, 0.6 * ONE_PIECE_LEAN * drop
    x = x0 - m + 0.013
    while x < x1 + m:
        y = y0 - m + 0.017
        while y < y1 + m:
            yield (x, y, top), (x + lean_x, y + lean_y, low)
            y += ONE_PIECE_BACK_STEP
        x += ONE_PIECE_BACK_STEP
    box = back.bounding_box()
    drop = box.max.Z - box.min.Z + 2
    x = box.min.X + 0.37
    while x < box.max.X:
        y = box.min.Y + 0.41
        while y < box.max.Y:
            yield (
                (x, y, box.max.Z + 1),
                (x + ONE_PIECE_LEAN * drop, y + 0.6 * ONE_PIECE_LEAN * drop,
                 box.min.Z - 1),
            )
            y += ONE_PIECE_GRID
        x += ONE_PIECE_GRID


def one_piece_back(back, window, one_piece):
    """The one-piece back is one solid with one shell. It holds every point
    that the back and the IR window hold, and it adds material only in the
    gap between the two.

    Rays read both builds. On each ray, the runs of the back and the window
    together must lie inside the runs of the one-piece back. A run of the
    one-piece back that neither part holds passes only if its middle is
    between the two parts, no further from both together than IR_WINDOW_FIT
    plus ONE_PIECE_TOL. That is the closed adhesive gap round the flange.
    Returns the problems and the readings."""
    problems = []
    part = "case-back-one-piece"
    solids = one_piece.solids()
    shells_ = one_piece.shells()
    if len(solids) != 1:
        problems.append(Problem(
            f"the one-piece back is {len(solids)} solids, not one", part=part
        ))
    if len(shells_) != 1:
        problems.append(Problem(
            f"the one-piece back has {len(shells_)} shells, not one: a second "
            "shell is a void closed inside the part",
            part=part,
        ))
    if not one_piece.is_valid:
        problems.append(Problem("the one-piece back is not a valid solid", part=part))

    x0, x1, y0, y1 = ir_window_span()
    m = params.IR_WINDOW_FLANGE + params.IR_WINDOW_FIT + ONE_PIECE_BACK_REACH + 1
    crop = Pos((x0 + x1) / 2, (y0 + y1) / 2, (SHELL_BACK + BOARD_TOP) / 2) * Box(
        x1 - x0 + 2 * m, y1 - y0 + 2 * m, BOARD_TOP - SHELL_BACK + 2
    )
    near = back.intersect(crop)
    if isinstance(near, list):
        near = Compound(list(near))
    gap = params.IR_WINDOW_FIT + ONE_PIECE_TOL

    rays = filled = 0
    worst = 0.0
    misses, extras = [], []
    for start, end in _one_piece_back_rays(back):
        rays += 1
        want = _merged(_ray_runs(back, start, end), _ray_runs(window, start, end))
        have = _ray_runs(one_piece, start, end)
        span = [b - a for a, b in zip(start, end)]
        length = math.sqrt(sum(c * c for c in span))

        def at(first, last):
            t = (first + last) / 2 / length
            return tuple(a + t * c for a, c in zip(start, span))

        for first, last in _uncovered(want, have):
            if last - first > ONE_PIECE_TOL:
                misses.append((last - first, at(first, last)))
        for first, last in _uncovered(have, want):
            if last - first <= ONE_PIECE_TOL:
                continue
            p = at(first, last)
            across = near.distance_to(Vertex(*p)) + window.distance_to(Vertex(*p))
            if across <= gap:
                filled += 1
                worst = max(worst, across)
            else:
                extras.append((across, last - first, p))
    misses.sort(reverse=True)
    for run, p in misses[:ONE_PIECE_SHOWN]:
        problems.append(Problem(
            f"the one-piece back misses {run:.3f} of material that the back "
            "and the IR window hold",
            at=p, part=part,
        ))
    extras.sort(reverse=True)
    for across, run, p in extras[:ONE_PIECE_SHOWN]:
        problems.append(Problem(
            f"the one-piece back holds {run:.3f} of material that neither the "
            f"back nor the IR window holds, {across:.3f} across from one to the "
            f"other, over IR_WINDOW_FIT plus ONE_PIECE_TOL {gap:.3f}",
            at=p, part=part,
        ))
    more = max(len(misses) - ONE_PIECE_SHOWN, 0) + max(len(extras) - ONE_PIECE_SHOWN, 0)
    if more:
        problems.append(Problem(
            f"{more} more runs differ from the two-part build", part=part
        ))
    return problems, {"rays": rays, "filled": filled, "worst": worst}


def interference(parts):
    # One part at a time: Q3's model against the fused shells made the common
    # come back as a null shape, while each shell alone reads it cleanly.
    z_lo = min(p.bounding_box().min.Z for p in parts)
    z_hi = max(p.bounding_box().max.Z for p in parts)
    placements = [(ref, x, y) for ref, (x, y, _, _) in board.components().items()]
    placements.append(("ENC1", *board.wheel_center()))

    hits = []
    for solid in board.assembly_solids():
        box = solid.bounding_box()
        if box.min.Z >= z_hi or box.max.Z <= z_lo:
            continue
        volume = sum(_volume(p.intersect(solid)) for p in parts)
        if volume <= TOLERANCE:
            continue
        center = box.center()
        ref = min(
            placements, key=lambda p: math.hypot(p[1] - center.X, p[2] - center.Y)
        )[0]
        hits.append((ref, volume, box.min.Z, box.max.Z))
    return hits
