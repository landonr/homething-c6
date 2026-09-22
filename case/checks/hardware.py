"""Cell clearance: the cell envelope against every modelled solid, every screw
boss, and both shells.

Feature clashes: bosses, ribs and the cell against every part's courtyard. The
only pass that sees the eleven switches, D2-D5 and J1, none of which reach the
STEP assembly. 2D, so it answers where a part sits, never how tall it is.

End screw: the one fastener that closes the two shells, read off both built
shells rather than off the stack that sized it.
"""

import functools

from build123d import Box, Cylinder, Pos, Rot

import board
import case
import params

from .common import TOLERANCE, Problem, _fill_fraction, _volume


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
    # The end screw's block, which hangs off the front skirt into the back's
    # cavity under the board's -Y end. Its box rather than a radius: it is the
    # one cavity feature that is not a round post.
    block = case.end_screw_block().bounding_box()
    features.append(
        (
            "end screw block",
            block.min.X,
            block.min.Y,
            block.max.X,
            block.max.Y,
            block.min.Z,
            case.SUPPORT_TOP,
        )
    )
    # The V2 retention post, on both its own diameter and its root chamfer. This
    # is the pass that sees the eleven
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


def end_screw(front, back):
    """The one screw that closes the two shells, on the built shells.

    Five readings, and none of them restates the stack that sized the feature.
    The block has to have survived the front's fuse and to be standing clear of
    both the back and the cell, or the shells will not close on it. The head
    recess has to land on flat, full-thickness wall rather than on the tip roll,
    which is why the four rim points are probed on the outer face rather than
    the axis alone: a counterbore centred on solid can still have half its rim
    hanging in air. And the thread has to be there, with wall under the head in
    front of it and block behind it.
    """
    problems = []
    block = case.end_screw_block()
    box = block.bounding_box()
    x, z = case.end_screw_axis()
    edge = case.end_wall_edge()

    if len(front.solids()) != 1:
        problems.append(
            Problem(
                f"front shell has {len(front.solids())} solids with the end "
                "screw block fused",
                part="case-front",
            )
        )
    # The top row alone probes further in than the other two: the block's back
    # face is chamfered away at the top for END_SCREW_BLOCK_CHAMFER, so a probe
    # at the back reads air there by construction and would fail on the lead-in
    # rather than on a missed fuse. Stepping inboard of the chamfer puts it back
    # on the top land the board sits over.
    for label, probe_y, probe_z in (
        (
            "under its top",
            box.max.Y - params.END_SCREW_BLOCK_CHAMFER - 0.3,
            case.SUPPORT_TOP - 0.3,
        ),
        ("at the axis", box.max.Y - 0.3, z),
        ("above its bottom", box.max.Y - 0.3, box.min.Z + 0.3),
    ):
        probe = Pos(x, probe_y, probe_z) * Box(0.3, 0.3, 0.3)
        filled = _fill_fraction(front, probe)
        if filled < 1 - TOLERANCE:
            problems.append(
                Problem(
                    f"end screw block is only {filled:.0%} material {label}, so "
                    "it did not survive the front's fuse",
                    box=probe,
                    part="case-front",
                )
            )

    # And the lead-in itself, read as void on the built front. This box sits
    # just inside the top back corner the lead-in takes off, and it is sized
    # and placed off END_SCREW_BLOCK_CHAMFER rather than fixed, so it stays
    # wholly inside the removed wedge at any positive value of it; material
    # here means the wedge stopped being cut and the board has a square arris
    # to land on again. It is the twin of the offset above: that one is on the
    # land the lead-in leaves, this one is in the wedge it removes.
    lead_in = params.END_SCREW_BLOCK_CHAMFER
    probe = Pos(
        x, box.max.Y - 0.25 * lead_in, case.SUPPORT_TOP - 0.25 * lead_in
    ) * Box(0.2 * lead_in, 0.2 * lead_in, 0.2 * lead_in)
    filled = _fill_fraction(front, probe)
    if filled > TOLERANCE:
        problems.append(
            Problem(
                f"the block's top back corner is {filled:.0%} material, so the "
                "board's lead-in chamfer is not cut",
                box=probe,
                part="case-front",
            )
        )

    fouled = _volume(block.intersect(back))
    if fouled > TOLERANCE:
        problems.append(
            Problem(
                f"end screw block runs into the back shell by {fouled:.2f} mm3",
                part="case-front",
            )
        )
    fouled = _volume(block.intersect(case.cell_envelope()))
    if fouled > TOLERANCE:
        problems.append(
            Problem(f"end screw block runs into the cell by {fouled:.2f} mm3")
        )

    # The counterbore's own rim, on the outer face, just inside the wall. A
    # radius a hair past the head's own, so this reads the wall the head lands
    # on rather than the wall the counterbore removed.
    outer = edge - case.LAP_OUT
    rim = params.SHELL_SCREW_HEAD_D / 2 + 0.3
    for dx, dz, where in (
        (rim, 0, "+x"), (-rim, 0, "-x"), (0, rim, "above"), (0, -rim, "below"),
    ):
        probe = Pos(x + dx, outer + 0.3, z + dz) * Box(0.4, 0.4, 0.4)
        filled = _fill_fraction(back, probe)
        if filled < 1 - TOLERANCE:
            problems.append(
                Problem(
                    f"the head recess rim is only {filled:.0%} material {where} "
                    "the axis: the counterbore is off the flat wall",
                    box=probe,
                    part="case-back",
                )
            )

    # Wall left under the head, measured as material rather than subtracted.
    head_bottom = outer + params.SHELL_SCREW_HEAD_H
    cavity = edge - params.BOARD_FIT
    left = cavity - head_bottom
    if left < 1.0:
        problems.append(
            Problem(f"only {left:.2f} of wall is left under the head, wants 1.0")
        )
    # An annulus, not a plug: the clearance bore runs the whole way through this
    # band, so what the head actually bears on is the ring between the two
    # diameters and a solid cylinder here reads 36% void by construction.
    seat = Pos(x, (head_bottom + cavity) / 2, z) * Rot(90, 0, 0) * Cylinder(
        radius=params.SHELL_SCREW_HEAD_D / 2 - 0.1, height=left
    )
    bore = Pos(x, (head_bottom + cavity) / 2, z) * Rot(90, 0, 0) * Cylinder(
        radius=params.SHELL_SCREW_CLEAR_D / 2 + 0.1, height=left + 1
    )
    plug = seat.cut(bore)
    filled = _fill_fraction(back, plug)
    if filled < 1 - TOLERANCE:
        problems.append(
            Problem(
                f"only {filled:.0%} of the {left:.2f} under the head is material",
                box=plug,
                part="case-back",
            )
        )

    # The pilot stops inside the block, and there is block left beyond it.
    # Against a floor rather than against zero. Both numbers come out of the
    # same stack, so a pilot drilled level with the block's back reads a
    # nanometre short of it rather than equal, which passes a bare >= and then
    # asks OCC for a probe box that thick, which it refuses: the pass died on a
    # stack trace instead of reporting the thread it had found open. A floor
    # reads that case as what it is, and anything under it is a skin no thread
    # would survive anyway.
    floor = 0.1
    pilot = case.end_screw_pilot().bounding_box()
    if pilot.max.Y >= box.max.Y - floor:
        problems.append(
            Problem(
                f"the pilot ends at {pilot.max.Y:.2f}, within {floor} of the "
                f"block's own back at {box.max.Y:.2f}, so it is not blind"
            )
        )
    else:
        probe = Pos(x, (pilot.max.Y + box.max.Y) / 2, z) * Box(
            0.3, box.max.Y - pilot.max.Y, 0.3
        )
        filled = _fill_fraction(front, probe)
        if filled < 1 - TOLERANCE:
            problems.append(
                Problem(
                    f"only {filled:.0%} of the block behind the pilot is "
                    "material, so the thread opens out of its own boss",
                    box=probe,
                    part="case-front",
                )
            )
    return problems
