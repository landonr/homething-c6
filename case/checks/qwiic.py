"""Built-shell access for Qwiic and internal space for the battery lead."""

from build123d import Box, Pos
from model.shape import _cut, _isect

import math

import board
import case
import params

from .common import TOLERANCE, Problem, _Crop, _volume, _fill_fraction, _ray_runs
from .usb import CONNECTOR_MARGIN_MIN


def qwiic_access(front, front_fdm, back):
    """Probe a straight plug approach from the exterior to the connector mouth."""
    box = board.part_envelope("J2")
    c = CONNECTOR_MARGIN_MIN
    edge = board.board_profile().bounding_box().min.X
    x0, x1 = edge - params.WALL * 6, box.max.X
    corridor = Pos((x0 + x1) / 2, box.center().Y, box.center().Z) * Box(
        x1 - x0, box.size.Y + 2 * c, box.size.Z + 2 * c
    )
    problems = []
    opened_back = back.cut(case.qwiic_knockout_removal())
    for name, shape in (("front shell", front), ("FDM front shell", front_fdm),
                        ("back shell after panel removal", opened_back),
                        ("cell", case.cell_envelope())):
        volume = _volume(shape.intersect(corridor))
        if volume > TOLERANCE:
            problems.append(f"{name} blocks the J2 plug approach by {volume:.2f} mm3")
    return problems


def battery_lead_clearance(front, front_fdm, back):
    """Probe the internal free volume for the battery plug and wire bend."""
    corridor = case.battery_plug_envelope()
    problems = []
    for name, shape in (("front shell", front), ("FDM front shell", front_fdm),
                        ("back shell", back),
                        ("cell", case.cell_envelope())):
        volume = _volume(shape.intersect(corridor))
        if volume > TOLERANCE:
            problems.append(f"{name} blocks the J1 lead corridor by {volume:.2f} mm3")
    for ref, solids in board.placement_groups().items():
        if ref == "J1":
            continue
        for solid in solids:
            volume = _volume(solid.intersect(corridor))
            if volume > TOLERANCE:
                problems.append(f"{ref} blocks the J1 lead corridor by {volume:.2f} mm3")
    return problems


def qwiic_knockout(back):
    """Probe the default cover, its border, and exactly two printable bridges."""
    panel = case.qwiic_knockout_panel()
    box = panel.bounding_box()
    problems = []
    if len(back.solids()) != 1:
        problems.append("the knockout is not connected to the back shell as one solid")
    if _fill_fraction(back, panel) < 1 - TOLERANCE:
        problems.append("the default Qwiic cover has missing material")
    opening = case.qwiic_slot().bounding_box()
    neighbor_lo = opening.min.Y - params.QWIIC_KNOCKOUT_ANCHOR - 0.2
    neighbor_hi = opening.max.Y + params.QWIIC_KNOCKOUT_ANCHOR + 0.2
    for z in (box.min.Z + 0.1, box.center().Z, box.max.Z - 0.1):
        runs = _ray_runs(back, (box.min.X - 1, box.center().Y, z),
                         (box.max.X + params.WALL, box.center().Y, z))
        walls = [
            _ray_runs(back, (box.min.X - 1, y, z), (box.max.X + params.WALL, y, z))
            for y in (neighbor_lo, neighbor_hi)
        ]
        expected = ((walls[0][0][0] + walls[1][0][0]) / 2
                    if all(walls) else None)
        if not runs or expected is None or abs(runs[0][0] - expected) > TOLERANCE:
            problems.append(f"the built Qwiic cover is not flush with the neighboring wall at z {z:.2f}")
        elif runs[0][1] - runs[0][0] < 0.8 - TOLERANCE:
            problems.append("the built Qwiic cover is thinner than two 0.4 mm extrusion widths")

    # This belt excludes the panel and the original wall. Only bridge material remains.
    window = case.qwiic_slot()
    depth = Pos(box.center()) * Box(box.size.X, 2 * params.WALL + box.size.Y,
                                  2 * params.WALL + box.size.Z)
    inner = Pos(box.center()) * Box(box.size.X + 1, box.size.Y, box.size.Z)
    belt = _cut(_isect(window, depth), inner)
    hit = back.intersect(belt)
    bridges = list(hit.solids()) if hit else []
    if len(bridges) != 2:
        problems.append(f"the built cover has {len(bridges)} bridge contacts, wants exactly two")
    else:
        sides = []
        for bridge in bridges:
            bb = bridge.bounding_box()
            sides.append(-1 if bb.center().Y < box.center().Y else 1)
            if abs(bb.min.Z - box.min.Z) > TOLERANCE:
                problems.append("a Qwiic bridge does not support the first panel layer")
            if bb.size.X < 0.8 - TOLERANCE or bb.size.Z < 0.8 - TOLERANCE:
                problems.append("a built Qwiic bridge is below the 0.8 mm print target")
            if bb.size.X * bb.size.Z > 0.8 + TOLERANCE:
                problems.append("a built Qwiic bridge exceeds the 0.8 mm2 breakout target")
            for z in (bb.min.Z + 0.1, bb.center().Z, bb.max.Z - 0.1):
                runs = _ray_runs(back, (bb.min.X - 1, bb.center().Y, z),
                                 (bb.max.X + 1, bb.center().Y, z))
                if not runs or runs[0][1] - runs[0][0] < 0.8 - TOLERANCE:
                    problems.append("a built Qwiic bridge is thinner than two 0.4 mm extrusion widths")
                    break
        if sorted(sides) != [-1, 1]:
            problems.append("the two Qwiic bridges are not on opposite panel sides")

    gap = 0.2
    probes = [
        Pos(box.center().X, box.center().Y, box.min.Z - gap / 2)
        * Box(box.size.X, box.size.Y - gap, gap),
        Pos(box.center().X, box.center().Y, box.max.Z + gap / 2)
        * Box(box.size.X, box.size.Y - gap, gap),
    ]
    z0, z1 = box.min.Z + 1.1, box.max.Z - 0.1
    for side in (-1, 1):
        edge = box.min.Y if side < 0 else box.max.Y
        probes.append(Pos(box.center().X, edge + side * gap / 2, (z0 + z1) / 2)
                      * Box(box.size.X, gap, z1 - z0))
    for probe in probes:
        if _volume(back.intersect(probe)) > TOLERANCE:
            problems.append("the built knockout border has less than 0.20 mm free clearance")
            break
    return problems


def qwiic_skirt_transition(front, front_fdm):
    """Read a flat core and continuous, monotone end profiles on both built skirts."""
    opening = case.qwiic_slot().bounding_box()
    _, y0, _, y1, _ = board.courtyards()["J2"]
    y0 -= params.SUPPORT_CLEARANCE
    y1 += params.SUPPORT_CLEARANCE
    edge = board.board_profile().bounding_box().min.X
    low = case.SKIRT_BOTTOM - 0.1
    high = opening.max.Z + 0.6
    slope = math.tan(math.radians(params.SKIRT_LEAD_ANGLE))
    reach = (high - case.SKIRT_BOTTOM) / slope + params.SKIRT_LEAD_FIT + 0.2
    xs = (edge - case.SKIRT_OUT + 0.12,
          edge - (case.SKIRT_OUT + case.STIFFENED_WALL) / 2,
          edge - case.STIFFENED_WALL - 0.12)
    problems = []
    for part, shell in (("case-front", front), ("case-front-fdm", front_fdm)):
        crop = _Crop(shell, (min(xs) - 0.1, y0 - reach - 0.1, low - 0.1),
                     (max(xs) + 0.1, y1 + reach + 0.1, high + 0.1))

        def roof_at(x, y):
            runs = crop.ray_runs((x, y, low), (x, y, high))
            if not runs:
                problems.append(Problem("the Qwiic skirt has no retained upper wall",
                                        at=(x, y, high), part=part))
                return None
            return low + runs[0][0]

        for x in xs:
            core = []
            for fraction in (0, 0.125, 0.25, 0.5, 0.75, 0.875, 1):
                y = y0 + fraction * (y1 - y0)
                roof = roof_at(x, y)
                if roof is not None:
                    core.append(roof)
                    if not opening.max.Z + 0.1 - TOLERANCE <= roof <= opening.max.Z + 0.3 + TOLERANCE:
                        problems.append(Problem(
                            "the Qwiic keepout roof leaves a tongue or removes too much upper wall",
                            at=(x, y, roof), part=part,
                        ))
                wall = Pos(x, y, opening.max.Z + 0.4) * Box(0.04, 0.04, 0.04)
                if crop.fill_fraction(wall) < 0.9:
                    problems.append(Problem("the Qwiic skirt removes its retained upper wall",
                                            box=wall, part=part))
            if core and max(core) - min(core) > 0.02:
                problems.append(Problem("the Qwiic skirt roof is not flat across its support keepout",
                                        at=(x, (y0 + y1) / 2, min(core)), part=part))
            for boundary, direction in ((y0, 1), (y1, -1)):
                offsets = {-reach + (reach + 0.1) * i / 40 for i in range(41)}
                offsets.update((-0.02, 0.02,
                                -params.SKIRT_LEAD_FIT - 0.02,
                                -params.SKIRT_LEAD_FIT + 0.02))
                previous = None
                for offset in sorted(offsets):
                    y = boundary + direction * offset
                    roof = roof_at(x, y)
                    if roof is not None and previous is not None:
                        old_offset, old_roof = previous
                        rise = roof - old_roof
                        if rise < -0.02:
                            problems.append(Problem(
                                "the Qwiic skirt edge drops toward the opening, leaving a tooth",
                                at=(x, y, roof), part=part,
                            ))
                            break
                        if rise > slope * (offset - old_offset) + 0.03:
                            problems.append(Problem(
                                "the Qwiic skirt edge has a step steeper than its lead-in",
                                at=(x, y, roof), part=part,
                            ))
                            break
                    if roof is not None:
                        previous = (offset, roof)
    return problems
