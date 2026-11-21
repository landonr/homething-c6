"""Checks for the front shell's board hold-down ledges.

Every pass reads the BUILT front shell. The ledge material is cut out of it
inside the board outline, along each long side, above the bearing plane and
under the ceiling. Nothing else of the front stands there, so what is found
there is the ledges as the shell really has them.
"""

import math

from build123d import Compound, Pos, extrude

import board
import case
import params

from .common import TOLERANCE, Problem, _Crop, _volume

CLEARANCE_MIN = 0.2
"""Least gap a ledge may keep off a part. A fixed floor, not the parameter that
builds the breaks, so zeroing SUPPORT_CLEARANCE fails here instead of agreeing."""

SELF_SUPPORT_MIN = 45.0
"""Shallowest face angle, off horizontal, that prints face down without
support. A fixed floor for the same reason: a shallow SUPPORT_UNDER_ANGLE must
fail rather than be measured against itself."""

PRESS_STATES = (("released", 0.0), ("pressed", -params.SWITCH_TRAVEL))
"""The two pad offsets the pad fit is read at."""

SIDES = (("-X", -1), ("+X", 1))


def _edge(side):
    box = board.board_profile().bounding_box()
    return box.min.X if side < 0 else box.max.X


_CROPS = {}
"""Crops by (front id, side), so one boolean against the shell serves every
pass. The front is kept in the entry so its id cannot be reused."""


def _zone_crop(front, side):
    key = (id(front), side)
    if key not in _CROPS:
        _CROPS[key] = (front, _build_zone_crop(front, side))
    return _CROPS[key][1]


def _build_zone_crop(front, side):
    """The front's material inside the board outline in one ledge strip: from
    the board edge in to SUPPORT_BEARING, from just under the bearing plane to
    the ceiling. Wall material lies outside the outline, including round the
    corner arcs, and the end screw block lies below the plane, so neither is in
    it."""
    box = board.board_profile().bounding_box()
    edge = _edge(side)
    x0, x1 = sorted((edge, edge - side * params.SUPPORT_BEARING))
    lo = (x0, box.min.Y - 0.5, case.BOARD_TOP - 0.2)
    hi = (x1, box.max.Y + 0.5, case.CAVITY_FRONT - 0.05)
    strip = _Crop(front, lo, hi).shape
    if strip is None:
        return _Crop(None, lo, hi)
    outline = Pos(0, 0, lo[2]) * extrude(board.board_profile(), amount=hi[2] - lo[2], dir=(0, 0, 1))
    inside = strip.intersect(outline)
    pieces = list(inside.solids()) if inside else []
    return _Crop(Compound(pieces) if pieces else None, lo, hi)


def front_ledge_material(front):
    """{side: [solid]} the ledge material the built front has, one per run."""
    out = {}
    for name, side in SIDES:
        shape = _zone_crop(front, side).shape
        out[name] = list(shape.solids()) if shape is not None else []
    return out


def front_ledge_window(front):
    """Every side has a run inside the window, no ledge material stands outside
    it, and every run is at least SUPPORT_MIN_RUN long."""
    box = board.board_profile().bounding_box()
    y0 = box.min.Y
    y1 = y0 + params.FRONT_LEDGE_REACH
    problems = []
    for name, runs in front_ledge_material(front).items():
        if not runs:
            problems.append(f"{name} has no front ledge inside the window")
        for run in runs:
            b = run.bounding_box()
            if b.min.Y < y0 - TOLERANCE or b.max.Y > y1 + TOLERANCE:
                problems.append(
                    f"{name} front ledge spans y {b.min.Y:.2f} to {b.max.Y:.2f}, "
                    f"outside the window {y0:.2f} to {y1:.2f}"
                )
            if b.size.Y < params.SUPPORT_MIN_RUN - TOLERANCE:
                problems.append(
                    f"{name} front ledge is only {b.size.Y:.2f} long, below "
                    f"SUPPORT_MIN_RUN {params.SUPPORT_MIN_RUN:.2f}"
                )
    return problems


def front_ledge_fused(front):
    """The ledges are part of the one front solid. Material found in the strip
    is only there if the fuse kept it, so the count and the presence together
    say it is fused rather than missing or loose."""
    problems = []
    if len(front.solids()) != 1:
        problems.append(f"front shell has {len(front.solids())} solids with the ledges fused")
    for name, runs in front_ledge_material(front).items():
        if not runs:
            problems.append(f"{name} has no ledge material in the built front")
    return problems


def _sites(run, side):
    """(y) readings on the straight part of a run's board edge, where the strip
    is parallel to the axis: the middle and one inside each end."""
    ty0, ty1 = case.corner_tangent_y()
    b = run.bounding_box()
    lo, hi = max(b.min.Y, ty0) + 1.0, min(b.max.Y, ty1) - 1.0
    if hi < lo:
        return []
    return sorted({lo, (lo + hi) / 2, hi})


def front_ledge_bearing(front):
    """(problems, sites): at each run the built front is material from
    BOARD_TOP + FRONT_LEDGE_GAP up, over a flat at least SUPPORT_MIN_BEARING wide.

    A vertical ray one millimetre in from the board edge reads where the ledge
    underside is. A horizontal ray just above that plane reads how far the flat
    runs in before the inboard round starts."""
    problems = []
    sites = 0
    board_top = params.BOARD_THICKNESS
    want = board_top + params.FRONT_LEDGE_GAP
    for name, side in SIDES:
        crop = _zone_crop(front, side)
        edge = _edge(side)
        for run in front_ledge_material(front)[name]:
            for y in _sites(run, side):
                sites += 1
                x = edge - side * 1.0
                z0 = case.BOARD_TOP - 0.15
                runs = crop.ray_runs((x, y, z0), (x, y, case.CAVITY_FRONT - 0.1))
                if not runs:
                    problems.append(Problem(
                        f"{name} front ledge has no material above the board at y {y:.2f}",
                        at=(x, y, want),
                    ))
                    continue
                z = z0 + runs[0][0]
                if z < board_top - TOLERANCE:
                    problems.append(Problem(
                        f"{name} front ledge underside at y {y:.2f} is z {z:.3f}, "
                        f"inside the board, whose top face is {board_top:.3f}",
                        at=(x, y, z),
                    ))
                elif abs(z - want) > TOLERANCE:
                    problems.append(Problem(
                        f"{name} front ledge underside at y {y:.2f} is z {z:.3f}, "
                        f"not the board top plus FRONT_LEDGE_GAP, {want:.3f}",
                        at=(x, y, z),
                    ))
                zh = want + 0.03
                xi = edge - side * params.SUPPORT_BEARING
                span = _Crop(
                    crop, (min(edge, xi), y - 0.1, zh - 0.1), (max(edge, xi), y + 0.1, zh + 0.1)
                ).ray_runs((edge, y, zh), (xi, y, zh))
                width = span[0][1] if span else 0.0
                if width < params.SUPPORT_MIN_BEARING - TOLERANCE:
                    problems.append(Problem(
                        f"{name} front ledge flat bearing at y {y:.2f} is {width:.2f}, "
                        f"below SUPPORT_MIN_BEARING {params.SUPPORT_MIN_BEARING:.2f}",
                        at=(edge - side * width, y, want),
                    ))
    if not sites and not problems:
        problems.append("no front ledge run has a straight edge to read")
    return problems, sites


def front_ledge_clearance(front):
    """Each built ledge stands SUPPORT_CLEARANCE off every top courtyard, every
    assembly solid above the bearing plane, and every V2 body above it.

    The floor is CLEARANCE_MIN, not the parameter. Courtyards are read in plan
    against each run's box, since a run is straight.
    Solids are read as distances between the built ledge and the real solid."""
    problems = []
    bottom = case.BOARD_TOP + params.FRONT_LEDGE_GAP
    need = CLEARANCE_MIN
    runs = [r for rs in front_ledge_material(front).values() for r in rs]
    court = {
        ref: rect for ref, rect in board.courtyards().items() if rect[4] == "top"
    }
    for run in runs:
        b = run.bounding_box()
        for ref, (x0, y0, x1, y1, _) in court.items():
            dx = max(x0 - b.max.X, b.min.X - x1, 0.0)
            dy = max(y0 - b.max.Y, b.min.Y - y1, 0.0)
            if math.hypot(dx, dy) < need:
                problems.append(Problem(
                    f"front ledge at y {b.min.Y:.2f} to {b.max.Y:.2f} is "
                    f"{math.hypot(dx, dy):.2f} from {ref}'s courtyard",
                    box=run,
                ))
        solids = [(f"assembly solid {i}", s) for i, s in enumerate(board.assembly_solids(), 1)]
        for ref in sorted(set(board.components()) & set(board.legacy_components())):
            try:
                bodies = board.legacy_part_solids(ref)
            except ValueError:
                continue
            solids += [(f"V2 {ref}", Pos(0, 0, -params.SUPPORT_GAP) * s) for s in bodies]
        for name, solid in solids:
            sb = solid.bounding_box()
            if sb.max.Z <= bottom + 1e-6:
                continue
            if sb.max.X < b.min.X - 5 or sb.min.X > b.max.X + 5:
                continue
            if sb.max.Y < b.min.Y - 5 or sb.min.Y > b.max.Y + 5:
                continue
            gap = run.distance_to(solid)
            if gap < need:
                problems.append(Problem(
                    f"front ledge at y {b.min.Y:.2f} to {b.max.Y:.2f} is {gap:.2f} "
                    f"from {name}",
                    box=run,
                ))
    return problems, len(runs)


def front_ledge_intact(front):
    """Nothing cut after the fuse took material out of a ledge: each built run
    is wholly inside the built front. This is what a key, the recess, the LED
    ring or the wheel opening reaching a ledge would break."""
    problems = []
    for run in case.front_ledge_runs():
        lost = run.volume - _volume(front.intersect(run))
        if lost > TOLERANCE:
            b = run.bounding_box()
            problems.append(Problem(
                f"front shell cuts {lost:.2f} mm3 out of the ledge at y "
                f"{b.min.Y:.2f} to {b.max.Y:.2f}",
                box=run,
            ))
    return problems


def front_ledge_printable(front):
    """The face toward the ceiling rises at SUPPORT_UNDER_ANGLE or steeper, and
never below SELF_SUPPORT_MIN.

    Two horizontal rays at different heights up the built slope read where it
    stands, and the angle comes from the pair. Printed face down, that face is
    the overhang."""
    problems = []
    sites = 0
    base = case.BOARD_TOP + params.FRONT_LEDGE_GAP
    z_a = base + 1.4
    z_b = case.CAVITY_FRONT - 0.4
    for name, side in SIDES:
        crop = _zone_crop(front, side)
        edge = _edge(side)
        for run in front_ledge_material(front)[name]:
            for y in _sites(run, side)[:1]:
                xs = []
                for z in (z_a, z_b):
                    xi = edge - side * params.SUPPORT_BEARING
                    found = _Crop(
                        crop, (min(edge, xi), y - 0.1, z - 0.1), (max(edge, xi), y + 0.1, z + 0.1)
                    ).ray_runs((edge, y, z), (xi, y, z))
                    xs.append(found[0][1] if found else None)
                sites += 1
                if None in xs or xs[0] - xs[1] <= 0:
                    problems.append(Problem(
                        f"{name} front ledge slope is not readable at y {y:.2f}",
                        at=(edge, y, z_a),
                    ))
                    continue
                angle = math.degrees(math.atan2(z_b - z_a, xs[0] - xs[1]))
                if angle < max(params.SUPPORT_UNDER_ANGLE - 1.0, SELF_SUPPORT_MIN):
                    problems.append(Problem(
                        f"{name} front ledge slope is {angle:.1f} degrees, below "
                        f"SUPPORT_UNDER_ANGLE {params.SUPPORT_UNDER_ANGLE:.1f} or the "
                        f"{SELF_SUPPORT_MIN:.0f} degree print floor",
                        at=(edge, y, z_a),
                    ))
    if not sites and not problems:
        problems.append("no front ledge slope to read")
    return problems, sites


def front_ledge_fit(front, pads, caps):
    """The ledges stay clear of every pad and cap, released and pressed. `pads`
    is {name: solid}, `caps` is {ref: solid}. A cap moves with its pad."""
    problems = []
    runs = [r for rs in front_ledge_material(front).values() for r in rs]
    for run in runs:
        for state, offset in PRESS_STATES:
            for name, pad in pads.items():
                hit = _volume(run.intersect(Pos(0, 0, offset) * pad))
                if hit > TOLERANCE:
                    problems.append(Problem(
                        f"front ledge fouls pad {name} by {hit:.2f} mm3 when {state}",
                        box=run,
                    ))
            for ref, cap in caps.items():
                hit = _volume(run.intersect(Pos(0, 0, offset) * cap))
                if hit > TOLERANCE:
                    problems.append(Problem(
                        f"front ledge fouls cap {ref} by {hit:.2f} mm3 when {state}",
                        box=run,
                    ))
    return problems, len(runs)
