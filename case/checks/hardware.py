"""Cell clearance: the cell envelope against every modelled solid, every screw
boss, and both shells.

Feature clashes: bosses, ribs and the cell against every part's courtyard. The
only pass that sees the eleven switches, D2-D5 and J1, none of which reach the
STEP assembly. 2D, so it answers where a part sits, never how tall it is.
"""

import functools

from build123d import Box, Pos

import board
import case
import params

from .common import TOLERANCE, _volume


def cell_clearance():
    """The cell against everything on the board, and against the shells."""
    cell = case.cell_envelope()
    hits = []
    for solid in board.assembly_solids():
        volume = _volume(cell.intersect(solid))
        if volume > TOLERANCE:
            box = solid.bounding_box()
            hits.append((f"solid at ({box.center().X:.1f},{box.center().Y:.1f})", volume))
    # Courtyards carry no height, so only use them for parts the STEP is missing.
    for ref, (x0, y0, x1, y1, side) in board.courtyards().items():
        if side != "bottom":
            continue
        try:
            board.part_envelope(ref)
            continue
        except ValueError:
            pass
        footprint = Pos(
            (x0 + x1) / 2, (y0 + y1) / 2, -params.UNMODELLED_DEPTH / 2
        ) * Box(x1 - x0, y1 - y0, params.UNMODELLED_DEPTH)
        volume = _volume(cell.intersect(footprint))
        if volume > TOLERANCE:
            hits.append((f"{ref}, assumed {params.UNMODELLED_DEPTH} deep", volume))
    volume = _volume(case.back_shell().intersect(cell))
    if volume > TOLERANCE:
        hits.append(("the back shell", volume))
    return hits


@functools.cache
def _part_z(ref, side):
    """(min_z, max_z) a part occupies. Measured where there is a 3D model, and
    assumed to fill the cavity on its side of the board where there is not.

    Cached: a bounding box over every assembly solid is not cheap, and this is
    asked the same question once per case feature.
    """
    try:
        box = board.part_envelope(ref)
        return box.min.Z, box.max.Z
    except (ValueError, KeyError):
        if side == "bottom":
            return -params.UNMODELLED_DEPTH, 0.0
        return params.BOARD_THICKNESS, case.CAVITY_FRONT


def feature_clashes():
    """Case features that sit inside the cavity, against every part's courtyard.

    This is the only pass that sees the switches, D2-D5 and J1, none of which
    reach the STEP assembly. Courtyards carry no height, so a part's z span comes
    from its model where it has one, and is assumed to fill its side of the cavity
    where it does not.
    """
    court = board.courtyards()
    features = []
    for x, y, _ in board.mounting_holes():
        r = params.BOSS_OD / 2
        # The boss hangs off the ceiling above the board, the screw head sits
        # under it. Comparing either against the wrong side of the board means
        # comparing it against nothing it can reach. SHELL_FRONT, not
        # CAVITY_FRONT: the boss now carries its own material past the
        # keypad region's own (thinner) ceiling, all the way to the one
        # flat face, so its real height would otherwise be understated here.
        features.append(
            ("boss", x - r, y - r, x + r, y + r, case.BOARD_TOP, case.SHELL_FRONT)
        )
        root_r = r + params.STANDOFF_CHAMFER
        features.append(
            (
                "boss root",
                x - root_r,
                y - root_r,
                x + root_r,
                y + root_r,
                case.CAVITY_FRONT - params.STANDOFF_CHAMFER,
                case.CAVITY_FRONT,
            )
        )
        h = params.SCREW_HEAD_D / 2
        features.append(
            ("screw head", x - h, y - h, x + h, y + h, -params.SCREW_HEAD_H, 0.0)
        )
    sx, sy = case.closure_point()
    r = params.SHELL_SCREW_OD / 2
    features.append(
        ("closure post", sx - r, sy - r, sx + r, sy + r, case.closure_floors()[1], 0.0)
    )
    root_r = r + params.STANDOFF_CHAMFER
    floor = case.closure_floors()[1]
    features.append(
        (
            "closure post root",
            sx - root_r,
            sy - root_r,
            sx + root_r,
            sy + root_r,
            floor,
            floor + params.STANDOFF_CHAMFER,
        )
    )
    # The V2 retention post, on both its own diameter and its root chamfer, the
    # same pair the closure post carries. This is the pass that sees the eleven
    # switches and D2-D5, so it is what says the post clears a part with no model.
    lx, ly = board.legacy_retention_point()
    floor = case.legacy_retention_floors()[1]
    r = params.LEGACY_RETENTION_OD / 2
    features.append(
        (
            "legacy post",
            lx - r,
            ly - r,
            lx + r,
            ly + r,
            floor,
            case.SUPPORT_TOP,
        )
    )
    root_r = r + params.STANDOFF_CHAMFER
    features.append(
        (
            "legacy post root",
            lx - root_r,
            ly - root_r,
            lx + root_r,
            ly + root_r,
            floor,
            floor + params.STANDOFF_CHAMFER,
        )
    )

    mx, my = case.mic_port()
    r = params.MIC_DUCT_OD / 2
    features.append(
        ("mic duct", mx - r, my - r, mx + r, my + r, case.BOARD_TOP, case.SHELL_FRONT)
    )
    root_r = r + params.STANDOFF_CHAMFER
    features.append(
        (
            "mic duct root",
            mx - root_r,
            my - root_r,
            mx + root_r,
            my + root_r,
            case.CAVITY_FRONT - params.STANDOFF_CHAMFER,
            case.CAVITY_FRONT,
        )
    )

    clashes = []
    for name, fx0, fy0, fx1, fy1, fz0, fz1 in features:
        for ref, (cx0, cy0, cx1, cy1, cside) in court.items():
            cz0, cz1 = _part_z(ref, cside)
            overlap = [
                min(fx1, cx1) - max(fx0, cx0),
                min(fy1, cy1) - max(fy0, cy0),
                min(fz1, cz1) - max(fz0, cz0),
            ]
            if min(overlap) > 0:
                clashes.append((name, ref, min(overlap)))
    return clashes
