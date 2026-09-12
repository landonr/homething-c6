"""Checks for the back shell board support ledges."""

import math

from build123d import Box, Pos

import board
import case
import params
from model.stack import LAP_IN, MERGE

from .common import TOLERANCE, _volume


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
