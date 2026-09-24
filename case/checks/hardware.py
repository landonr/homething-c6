"""Cell clearance: the cell envelope against every modelled solid, every screw
boss, and both shells.

Feature clashes: bosses, ribs and the cell against every part's courtyard. The
only pass that sees the eleven switches, D2-D5 and J1, none of which reach the
STEP assembly. 2D, so it answers where a part sits, never how tall it is.

End screw: the one fastener that closes the two shells, read off both built
shells rather than off the stack that sized it.
"""

import functools

from build123d import (
    Box,
    BuildLine,
    BuildSketch,
    Compound,
    Cylinder,
    Plane,
    Polyline,
    Pos,
    Rot,
    extrude,
    make_face,
)

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
    where it does not. The end screw block is read on its built solid.
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

    # The end screw block on its built solid, not its box. Its ramp falls away
    # under the board, so its box overstates what it reaches there.
    block = case.end_screw_block()
    bbox = block.bounding_box()
    for ref, (cx0, cy0, cx1, cy1, cside) in court.items():
        cz0, cz1 = _part_z(ref, cside)
        if (
            min(bbox.max.X, cx1) <= max(bbox.min.X, cx0)
            or min(bbox.max.Y, cy1) <= max(bbox.min.Y, cy0)
            or min(bbox.max.Z, cz1) <= max(bbox.min.Z, cz0)
        ):
            continue
        region = Pos((cx0 + cx1) / 2, (cy0 + cy1) / 2, (cz0 + cz1) / 2) * Box(
            cx1 - cx0, cy1 - cy0, cz1 - cz0
        )
        hit = block.intersect(region)
        if _volume(hit) > TOLERANCE:
            size = Compound(hit.solids()).bounding_box().size
            clashes.append(("end screw block", ref, min(size.X, size.Y, size.Z)))
    return clashes


def end_screw(front, back):
    """The one screw that closes the two shells, on the built shells.

    None of these readings restates the stack that sized the feature. The
    block has to have survived the front's fuse and to be standing clear of
    both the back and the cell, or the shells will not close on it. Its top has
    to be the 45 degree ramp the face down print builds without support, with
    thread cover and a web neck still left under it. The head
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
    # The bottom row probes further in than the axis row: the block's bottom
    # back arris is chamfered away for END_SCREW_BLOCK_BASE_CHAMFER, so a probe
    # at the back reads air there by construction. Stepping inboard of the
    # chamfer puts it back on the land it leaves.
    for label, probe_y, probe_z in (
        ("at the axis", box.max.Y - 0.3, z),
        (
            "above its bottom",
            box.max.Y - params.END_SCREW_BLOCK_BASE_CHAMFER - 0.3,
            box.min.Z + 0.3,
        ),
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

    # The ramp, read as void on the built front: a wedge across the block's
    # width, from 0.2 above a 45 degree line off the end of the ledge up to
    # SUPPORT_TOP and back to the block's own back face. Material in it is a
    # ceiling the face down print has to support again.
    cavity = edge - params.BOARD_FIT
    start = cavity + params.END_SCREW_BLOCK_RAMP_LEDGE
    lift = 0.2
    top = case.SUPPORT_TOP
    with BuildSketch(Plane.YZ) as section:
        with BuildLine():
            Polyline(
                (start + lift, top),
                (box.max.Y, top),
                (box.max.Y, top + lift - (box.max.Y - start)),
                close=True,
            )
        make_face()
    wedge = Pos(x, 0, 0) * extrude(
        section.sketch, amount=params.END_SCREW_BLOCK_W / 2 - 0.2, both=True
    )
    filled = _fill_fraction(front, wedge)
    if filled > TOLERANCE:
        problems.append(
            Problem(
                f"{filled:.0%} of the wedge over the block's 45 degree ramp is "
                "material, so a flat ceiling is left that prints face down on "
                "support",
                box=wedge,
                part="case-front",
            )
        )

    # Cover over the thread where the ramp comes lowest, at the pilot's tip. A
    # floor rather than the ramp's own height, so a steeper ramp or a higher
    # screw that thins this skin fails here.
    cover = 1.0
    pilot = case.end_screw_pilot().bounding_box()
    probe = Pos(x, pilot.max.Y - 0.1, pilot.max.Z + 0.05 + (cover - 0.05) / 2) * Box(
        0.4, 0.2, cover - 0.05
    )
    filled = _fill_fraction(front, probe)
    if filled < 1 - TOLERANCE:
        problems.append(
            Problem(
                f"only {filled:.0%} of the {cover} over the pilot's tip is "
                "material, so the ramp leaves the thread a skin it can split",
                box=probe,
                part="case-front",
            )
        )

    # The web's neck at the block's -Y face, where the ramp leaves it least
    # height over SKIRT_BOTTOM. At least SKIRT_T, so the web that carries the
    # block is no thinner than the skirt it hangs from.
    neck = params.SKIRT_T
    face = box.max.Y - params.END_SCREW_BLOCK_D
    probe = Pos(x, face - 0.1, case.SKIRT_BOTTOM + 0.05 + (neck - 0.05) / 2) * Box(
        params.END_SCREW_BLOCK_W - 0.4, 0.2, neck - 0.05
    )
    filled = _fill_fraction(front, probe)
    if filled < 1 - TOLERANCE:
        problems.append(
            Problem(
                f"only {filled:.0%} of the {neck} web neck over SKIRT_BOTTOM at "
                "the block's -Y face is material, so the ramp cuts the web "
                "thinner than the skirt",
                box=probe,
                part="case-front",
            )
        )

    # The root fillet under the web, the skirt underside it starts on, and its
    # start at the grip skirt relief face, all read as material on the built
    # front. The first box is sized off the fillet's own leg, so it stays
    # inside the fillet at any value of it.
    start = case.end_screw_fillet_start()
    front_leg, back_leg = case.end_screw_root_legs()
    flat = params.END_SCREW_BLOCK_W - 0.4
    for probe, message in (
        (
            Pos(x, face - 0.25 * front_leg, case.SKIRT_BOTTOM - 0.25 * front_leg)
            * Box(flat, 0.2 * front_leg, 0.2 * front_leg),
            "of the root fillet under the web is material, so the neck gets no "
            "depth below SKIRT_BOTTOM",
        ),
        (
            Pos(x, start + 0.1, case.SKIRT_BOTTOM + 0.15) * Box(flat, 0.2, 0.2),
            "of the skirt is material where the root fillet starts, so the "
            "fillet hangs off nothing",
        ),
        # The hypotenuse is 0.2 under SKIRT_BOTTOM at start + 0.2, so this box
        # sits inside it. A fillet that starts inboard of the relief reads void.
        (
            Pos(x, start + 0.25, case.SKIRT_BOTTOM - 0.1) * Box(flat, 0.1, 0.1),
            "of the root fillet is material next to the grip skirt relief, so "
            "the fillet stops short of it and the skirt underside keeps a flat",
        ),
    ):
        filled = _fill_fraction(front, probe)
        if filled < 1 - TOLERANCE:
            problems.append(
                Problem(f"only {filled:.0%} {message}", box=probe, part="case-front")
            )

    # The back's parallel chamfer, read as void on the built back.
    wall = edge - params.BOARD_FIT
    relief = case.SKIRT_BOTTOM - params.SKIRT_FIT
    probe = Pos(x, wall - 0.25 * back_leg, relief - 0.25 * back_leg) * Box(
        flat, 0.2 * back_leg, 0.2 * back_leg
    )
    filled = _fill_fraction(back, probe)
    if filled > TOLERANCE:
        problems.append(
            Problem(
                f"the back's end wall is {filled:.0%} material in its root "
                "chamfer, so the block's fillet has no room",
                box=probe,
                part="case-back",
            )
        )

    # The gap between the two, level with the middle of the band both 45 degree
    # faces share. The fillet's surface there is read off the built front. The
    # fillet meets the skirt's outer face at its top, so it must keep at least
    # the skirt's own clearance to the lap beside it: that much -Y of it has to
    # be void in the built back. The reach runs from the fillet's start, as
    # nothing else of the front hangs below SKIRT_BOTTOM there.
    band = (relief + max(case.SKIRT_BOTTOM - front_leg, relief - back_leg)) / 2
    reach = Pos(x, (start + face) / 2, band) * Box(0.02, face - start, 0.02)
    hit = front.intersect(reach)
    if not hit or not hit.solids():
        problems.append(
            Problem(
                f"the built front has no root fillet at z {band:.2f} to measure "
                "the gap to the back from",
                box=reach,
                part="case-front",
            )
        )
    else:
        surface = Compound(hit.solids()).bounding_box().min.Y
        clearance = case.LAP_IN - case.SKIRT_OUT + params.GRIP_SKIRT_RELIEF
        gap = clearance - 0.05
        probe = Pos(x, surface - 0.02 - gap / 2, band) * Box(flat, gap, 0.2)
        filled = _fill_fraction(back, probe)
        if filled > TOLERANCE:
            problems.append(
                Problem(
                    f"the back fills {filled:.0%} of the skirt's own "
                    f"{clearance:.2f} clearance to the lap, -Y of the block's "
                    "root fillet, so the block can land on the wall",
                    box=probe,
                    part="case-back",
                )
            )

    # The bottom back corner, in the wedge the fold's own lead-in takes off,
    # read as void. Sized and placed off END_SCREW_BLOCK_BASE_CHAMFER
    # so it stays wholly inside the removed wedge at any positive value of it.
    base = params.END_SCREW_BLOCK_BASE_CHAMFER
    probe = Pos(
        x, box.max.Y - 0.25 * base, box.min.Z + 0.25 * base
    ) * Box(0.2 * base, 0.2 * base, 0.2 * base)
    filled = _fill_fraction(front, probe)
    if filled > TOLERANCE:
        problems.append(
            Problem(
                f"the block's bottom back corner is {filled:.0%} material, so "
                "the fold's lead-in chamfer is not cut",
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
