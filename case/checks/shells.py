"""Shells mate: the front and the back do not occupy the same space, except the
side catch preload on the lower pocket lip. Nothing else covers it, because
every other pass measures a shell against the board.

Interference: components the shells and the plate actually hit in 3D, each
one either a missing aperture or a keepout parameter set too tight.

IR-end lap wall: the back lap keeps LAP_MIN_WALL of wall to its outer round
around the IR end, from the floor of the skirt relief up. The pass measures the
built back shell, so a deeper relief behind the lap fails it.

Parts are sound: every part that gets exported is a valid solid and meshes to a
closed manifold. This is the only pass in the suite that looks at a mesh, and it
exists because everything else looks at the BRep instead. A shell can be torn
open in the STL, which is the artifact that ships and the only thing anyone ever
renders, while every probe in every other module reads the solid behind it and
reports clean.
"""

import math
from collections import Counter

import board
import params

from build123d import Box, Compound, GeomType, Pos

from model import shells
from model.stack import (
    LAP_IN,
    LAP_OUT,
    SHELL_BACK,
    SHELL_SEAM,
    SKIRT_BOTTOM,
    SKIRT_OUT,
    SUPPORT_TOP,
)
from model.support import front_support_cuts

from .common import CROP_MARGIN, TOLERANCE, Problem, _Crop, _volume


EXPORT_STEMS = {
    "front shell": "case-front",
    "back shell": "case-back",
    "button pad": "case-pad",
    "FDM V2 top pad": "case-pad-fdm-v2-top",
    "IR window": "ir-window",
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

    # A ring stiffener clipped at the board edge fills this site, 1.0 past
    # each corner tangent and inboard of the plain fit.
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
              (0.06, 0.06, 0.2), False)

    # Past each taper the stiffener is back to full thickness.
    thick = params.BOARD_FIT - params.SIDE_SKIRT_THICKEN + 0.05
    reach = params.SIDE_SKIRT_THICKEN_RUN + 0.5
    for at in (yt0 + reach, yt1 - reach):
        for side, edge, name in (
            (-1, board_box.min.X, "-X"),
            (1, board_box.max.X, "+X"),
        ):
            x = edge + side * thick
            crop = _Crop(front, (x - 0.5, at - 0.5, taper_z - 0.5), (x + 0.5, at + 0.5, taper_z + 0.5))
            probe(crop, f"{name} full stiffener past its taper at y {at:.2f}", (x, at, taper_z),
                  (0.06, 0.2, 0.2), True)
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


def interference(shells):
    shells_box = shells.bounding_box()
    placements = [(ref, x, y) for ref, (x, y, _, _) in board.components().items()]
    placements.append(("ENC1", *board.wheel_center()))

    hits = []
    for solid in board.assembly_solids():
        box = solid.bounding_box()
        if box.min.Z >= shells_box.max.Z or box.max.Z <= shells_box.min.Z:
            continue
        overlap = shells.intersect(solid)
        volume = _volume(overlap)
        if volume <= TOLERANCE:
            continue
        center = box.center()
        ref = min(
            placements, key=lambda p: math.hypot(p[1] - center.X, p[2] - center.Y)
        )[0]
        hits.append((ref, volume, box.min.Z, box.max.Z))
    return hits
