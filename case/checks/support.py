"""Checks for the back shell board support ledges."""

import math

from build123d import Box, Pos

import board
import case
import params
from model.stack import LAP_IN, MERGE, SKIRT_OUT, SUPPORT_TOP

from .common import TOLERANCE, Problem, _Crop, _volume


def support_board_clearance(ledge):
    profile = board.board_profile().bounding_box()
    board_probe = Pos(
        profile.center().X,
        profile.center().Y,
        params.BOARD_THICKNESS / 2,
    ) * Box(profile.size.X, profile.size.Y, params.BOARD_THICKNESS)
    problems = []
    if _volume(ledge.intersect(board_probe)) > TOLERANCE:
        problems.append("support ledge touches the board at rest")
    gap = -ledge.bounding_box().max.Z
    if abs(gap - params.SUPPORT_GAP) > TOLERANCE:
        problems.append(f"support gap is {gap:.2f}, not {params.SUPPORT_GAP:.2f}")
    return problems


def support_part_clearance(ledge):
    problems = []
    for name, obstacle in case.support_obstacles(0.0):
        if _volume(ledge.intersect(obstacle)) > TOLERANCE:
            problems.append(f"support ledge hits {name}")
    for solid in board.assembly_solids():
        overlap = _volume(ledge.intersect(solid))
        if overlap <= TOLERANCE:
            continue
        box = solid.bounding_box()
        problems.append(
            "support ledge hits assembly solid at "
            f"({box.center().X:.2f}, {box.center().Y:.2f}) by {overlap:.2f} mm3"
        )
    return problems


def support_cell_clearance(ledge):
    problems = []
    if _volume(ledge.intersect(case.cell_envelope())) > TOLERANCE:
        problems.append("support ledge hits the cell envelope")
    return problems


def support_flat_bearing(ledge):
    widths = case.support_bearing_widths(ledge)
    return [
        f"support flat bearing on {side} is {width:.2f}, below {params.SUPPORT_MIN_BEARING:.2f}"
        for side, width in widths.items()
        if width < params.SUPPORT_MIN_BEARING - TOLERANCE
    ]


def support_min_run():
    return [
        f"support fragment is only {solid.bounding_box().size.Y:.2f} long"
        for solid in case.support_runs()
        if solid.bounding_box().size.Y < params.SUPPORT_MIN_RUN - TOLERANCE
    ]


def support_printable():
    horizontal = LAP_IN + MERGE + params.SUPPORT_BEARING
    angle = math.degrees(
        math.atan2(
            horizontal * math.tan(math.radians(params.SUPPORT_UNDER_ANGLE)),
            horizontal,
        )
    )
    return [
        f"support underside is {angle:.1f} degrees, below {params.SUPPORT_UNDER_ANGLE:.1f}"
    ] if angle + TOLERANCE < params.SUPPORT_UNDER_ANGLE else []


def support_inner_round(ledge):
    """Confirm each built run retains the rounded inboard surface."""
    top = case.support_top()
    radius = params.SUPPORT_INNER_R
    problems = []
    for index, solid in enumerate(ledge.solids(), 1):
        rounded = [
            face
            for face in solid.faces()
            if str(face.geom_type) == "GeomType.CYLINDER"
            and abs(face.bounding_box().max.Z - top) <= TOLERANCE
            and abs(face.radius - radius) <= TOLERANCE
        ]
        if not rounded:
            problems.append(
                f"support run {index} has no {radius:.2f} radius inboard edge"
            )
    return problems


def support_wall_merge(back):
    return [] if len(back.solids()) == 1 else [
        f"back shell has {len(back.solids())} solids after support fusion"
    ]


def support_case_containment(back):
    outside = _volume(back.cut(case.support_case_envelope()))
    return [] if outside <= TOLERANCE else [
        f"back shell extends outside the case envelope by {outside:.2f} mm3"
    ]


SKIRT_FIT_MARGIN = 0.02
"""Distance each skirt fit probe keeps from the plane it reads beside."""

SKIRT_FIT_SLAB = 0.04
"""Height of the material probes on either side of the skirt fit gap."""


def support_skirt_fit(front, back):
    """The front skirt stands clear of every ledge top by more than SUPPORT_GAP.

    The open band runs SUPPORT_GAP up from SUPPORT_TOP and does not read
    SUPPORT_SKIRT_FIT. The builder reads that parameter, so a band taken off it
    passes any fit. Off SUPPORT_GAP, a fit that lets the skirt reach a ledge
    before the board does fails. The skirt must be material just above the fit,
    so a relief that removes the whole skirt fails too. Each run is read at its
    middle, and the run under a side catch at the catch too.
    """
    board_box = board.board_profile().bounding_box()
    middle = board_box.center().X
    fit = params.SUPPORT_SKIRT_FIT
    margin = SKIRT_FIT_MARGIN
    slab = SKIRT_FIT_SLAB
    catch_y = case.side_catch_y()
    gap = (SUPPORT_TOP + margin, SUPPORT_TOP + params.SUPPORT_GAP + margin)
    ledge = (SUPPORT_TOP - margin - slab, SUPPORT_TOP - margin)
    above = (SUPPORT_TOP + fit + margin, SUPPORT_TOP + fit + margin + slab)
    bands = {"skirt fit gap": gap, "ledge top": ledge, "skirt above the fit": above}
    problems = [
        f"{what} probe band z {z0:.3f} to {z1:.3f} collapses, "
        f"SUPPORT_GAP {params.SUPPORT_GAP:.3f}"
        for what, (z0, z1) in bands.items()
        if z1 - z0 < margin
    ]
    if problems:
        return problems, 0
    z_lo = min(z0 for z0, _ in bands.values()) - 0.1
    z_hi = max(z1 for _, z1 in bands.values()) + 0.1
    sites = 0
    for run in case.support_runs():
        box = run.bounding_box()
        side = -1 if box.center().X < middle else 1
        edge = board_box.min.X if side < 0 else board_box.max.X
        name = "-X" if side < 0 else "+X"
        x0, x1 = sorted((
            edge + side * (params.BOARD_FIT - params.SIDE_SKIRT_THICKEN + 0.05),
            edge + side * (SKIRT_OUT - 0.05),
        ))
        if x1 - x0 < margin:
            problems.append(
                f"{name} skirt fit probe width {x1 - x0:.3f} collapses between "
                "BOARD_FIT less SIDE_SKIRT_THICKEN and SKIRT_OUT"
            )
            continue
        stations = [(f"run at y {box.center().Y:.2f}", box.center().Y)]
        if box.min.Y < catch_y < box.max.Y:
            stations.append(("side catch", catch_y))
        for station, y in stations:
            sites += 1
            lo = (x0 - 0.1, y - 0.5, z_lo)
            hi = (x1 + 0.1, y + 0.5, z_hi)
            crops = {"front": _Crop(front, lo, hi), "back": _Crop(back, lo, hi)}
            for shell, what, (z0, z1), material in (
                ("front", "skirt fit gap", gap, False),
                ("back", "skirt fit gap", gap, False),
                ("back", "ledge top", ledge, True),
                ("front", "skirt above the fit", above, True),
            ):
                probe = Pos((x0 + x1) / 2, y, (z0 + z1) / 2) * Box(
                    x1 - x0, 0.4, z1 - z0
                )
                fraction = crops[shell].fill_fraction(probe)
                if (material and fraction < 0.98) or (not material and fraction > 0.02):
                    problems.append(Problem(
                        f"{name} {station} {shell} {what} at z {z0:.2f} to "
                        f"{z1:.2f} is {fraction:.0%} material, expected "
                        f"{'solid' if material else 'open'}",
                        box=probe,
                    ))
    if not sites and not problems:
        problems.append("no support run to read the skirt fit over")
    return problems, sites
