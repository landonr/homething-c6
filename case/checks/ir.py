"""Built-solid checks for U2's bottom-facing window and unchanged end ports."""

from build123d import Box, Pos

import board
import case
import params

from .common import (
    PROBE_D,
    TOLERANCE,
    Problem,
    _fill_fraction,
    _ray_runs,
    _volume,
)


OPENING_INSET = 0.5
PRESS_INTERFERENCE_REQUIRED = 0.05
"""Required interference per side, independent of production parameter."""
PRESS_PROBE_D = 0.02
FLANGE_OVERLAP_MIN = 0.4
ADHESIVE_LAND_MIN = 0.4


def _receiver_span():
    """Hand-derived aperture contract from U2's complete multi-solid envelope."""
    box = board.part_envelope("U2", radius=3.0)
    c = params.IR_CLEARANCE
    return box.min.X - c, box.max.X + c, box.min.Y - c, box.max.Y + c


def _column(shape, x, y):
    """Built material on one vertical bearing, spanning the whole enclosure."""
    probe = Pos(x, y, -10) * Box(PROBE_D, PROBE_D, 80)
    hit = shape.intersect(probe)
    if hit is None:
        return None
    solids = hit.solids()
    if not solids or _volume(hit) <= TOLERANCE:
        return None
    box = solids[0].bounding_box()
    for solid in solids[1:]:
        box = box.add(solid.bounding_box())
    return box


BEARING_BASE = -50.0
BEARING_SPAN = 80.0
"""Vertical extent a bearing is read over, the whole enclosure either way."""


def _bearing_runs(shape, x, y):
    """Built material down one vertical bearing, as ordered (low, high) z pairs."""
    runs = _ray_runs(
        shape, (x, y, BEARING_BASE), (x, y, BEARING_BASE + BEARING_SPAN)
    )
    return [(BEARING_BASE + lo, BEARING_BASE + hi) for lo, hi in runs]


def _surface_run(shape, x, y):
    """Outermost run at this bearing: the exterior face and the depth behind it.

    The back is a curved form and the insert is conformal to it, so the exterior
    height is a local reading. Across this aperture it rises by more than any of
    these probes is tall, so one height read at one bearing does not serve the
    others.
    """
    runs = _bearing_runs(shape, x, y)
    return runs[0] if runs else None


def _covers(shape, x, y, z):
    """Whether this bearing is inside built material at this height."""
    return any(lo <= z <= hi for lo, hi in _bearing_runs(shape, x, y))


def _floor_bearing_xy():
    """Where the floor is read, split out so a pass that finds no floor there can
    still say which bearing it went looking on."""
    x0, x1, y0, y1 = _receiver_span()
    return x1 + params.IR_WINDOW_FLANGE + params.IR_WINDOW_FIT + PROBE_D, (y0 + y1) / 2


def _floor_bearing(back):
    """Built back-floor bounds beside the receiver feature, at matching y."""
    return _column(back, *_floor_bearing_xy())


def _no_bearing():
    """The miss wants the bearing it was looked for on, which is a line rather
    than a spot."""
    x, y = _floor_bearing_xy()
    return Problem(
        "no built back-floor bearing beside U2's aperture",
        at=(x, y, 0.0), part="case-back",
    )


def end_ports_open(shells):
    """D1 and USB retain real through-openings at their exterior centrelines."""
    edge = board.board_profile().bounding_box()
    lens = board.emitter_envelope()
    usb = board.usb_envelope()
    probes = (
        (
            "D1 bore",
            lens.center().X,
            edge.max.Y + case.LAP_OUT - OPENING_INSET / 2,
            lens.center().Z,
        ),
        (
            "USB",
            usb.center().X,
            edge.min.Y - case.LAP_OUT + OPENING_INSET / 2,
            usb.center().Z,
        ),
    )
    problems = []
    for name, x, y, z in probes:
        probe = Pos(x, y, z) * Box(PROBE_D, OPENING_INSET, PROBE_D)
        frac = _fill_fraction(shells, probe)
        if frac > 0.1:
            problems.append(Problem(
                f"{name} reads {frac:.2f} solid at its exterior wall",
                at=(x, y, z), box=probe,
            ))
    return problems


def receiver_paths(shells, back):
    """U2 sees through -Z while its obsolete +Y sightline is closed."""
    x0, x1, y0, y1 = _receiver_span()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bearing = _floor_bearing(back)
    if bearing is None:
        return [_no_bearing()]

    problems = []
    sightline = Pos(cx, cy, (bearing.min.Z + bearing.max.Z) / 2) * Box(
        PROBE_D,
        PROBE_D,
        bearing.max.Z - bearing.min.Z + 0.4,
    )
    frac = _fill_fraction(back, sightline)
    if frac > 0.1:
        problems.append(Problem(
            f"U2 bottom sightline reads {frac:.2f} solid through the built back floor",
            box=sightline, part="case-back",
        ))

    edge_y = board.board_profile().bounding_box().max.Y + case.LAP_OUT
    u2 = board.part_envelope("U2", radius=3.0)
    obsolete = Pos(cx, edge_y - OPENING_INSET / 2, u2.center().Z) * Box(
        PROBE_D, OPENING_INSET, PROBE_D
    )
    frac = _fill_fraction(shells, obsolete)
    if frac < 0.9:
        problems.append(Problem(
            f"obsolete U2 +Y path reads only {frac:.2f} solid at the end wall",
            box=obsolete,
        ))
    return problems


def receiver_clearance(back, window):
    """Built shell and installed insert stay clear of U2 plus its optical margin."""
    u2 = board.part_envelope("U2", radius=3.0)
    c = params.IR_CLEARANCE
    clearance = Pos(
        u2.center().X,
        u2.center().Y,
        (u2.min.Z - c + u2.max.Z) / 2,
    ) * Box(
        u2.size.X + 2 * c,
        u2.size.Y + 2 * c,
        u2.max.Z - (u2.min.Z - c),
    )
    intruding = (back + window).intersect(clearance)
    fouled = _volume(intruding)
    if fouled > TOLERANCE:
        # The intruding material's own bounds rather than the clearance volume's:
        # the box is there to be looked at, and the whole keepout says only that
        # the failure is somewhere in it.
        return [Problem(f"U2 clearance volume is fouled by {fouled:.2f} mm3",
                        box=intruding)]
    return []


def window_installation(back, window):
    """Insert is flush, press-held, flanged onto adhesive land, and closes."""
    x0, x1, y0, y1 = _receiver_span()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    problems = []

    press = max(params.IR_WINDOW_PRESS, PRESS_INTERFERENCE_REQUIRED)
    inside = PRESS_PROBE_D / 2
    press_points = (
        (x0 - press + inside, cy),
        (x1 + press - inside, cy),
        (cx, y0 - press + inside),
        (cx, y1 + press - inside),
    )
    for x, y in press_points:
        shell = _surface_run(back, x, y)
        if shell is None:
            problems.append(Problem(
                "no built back-shell material beside U2's aperture",
                at=(x, y, 0.0), part="case-back",
            ))
            break
        press_z = shell[0] + params.IR_WINDOW_T / 2
        probe = Pos(x, y, press_z) * Box(PRESS_PROBE_D, PRESS_PROBE_D, PRESS_PROBE_D)
        if _fill_fraction(window, probe) < 0.8 or _fill_fraction(back, probe) < 0.8:
            problems.append(Problem(
                f"IR insert does not fill the full {press:.2f} press band "
                "at every bearing",
                at=(x, y, press_z), box=probe, part="ir-window",
            ))
            break
        # Shell and insert are read on one bearing, so the exterior's own rise
        # cancels out and what is left is the step across the seam.
        flush_error = _surface_run(window, x, y)[0] - shell[0]
        if abs(flush_error) > TOLERANCE:
            problems.append(Problem(
                f"IR insert exterior is {flush_error:+.2f} mm from the built "
                "back surface",
                at=(x, y, shell[0]), part="ir-window",
            ))
            break

    overlap = params.IR_WINDOW_FLANGE / 2
    flange_points = (
        (x1 + overlap, cy),
        (x0 - overlap, cy),
        (cx, y1 + overlap),
        (cx, y0 - overlap),
    )
    for x, y in flange_points:
        shoulder = _surface_run(back, x, y)
        if shoulder is None:
            problems.append(Problem(
                "IR insert flange has no continuous shell shoulder for adhesive",
                at=(x, y, 0.0), part="case-back",
            ))
            break
        depth = shoulder[1] - shoulder[0]
        if abs(depth - params.IR_WINDOW_T) > TOLERANCE:
            problems.append(Problem(
                f"shell shoulder stands {depth:.2f} mm off the exterior here, "
                f"wants the pane's {params.IR_WINDOW_T:.2f}",
                at=(x, y, shoulder[1]), part="case-back",
            ))
            break
        if not _covers(window, x, y, shoulder[1] + PRESS_PROBE_D):
            problems.append(Problem(
                "IR insert flange does not overlap the aperture on every side",
                at=(x, y, shoulder[1]), part="ir-window",
            ))
            break

    # Both of these are read off the parameters rather than off a probe, so the
    # insert as a whole is the most either can point at.
    held = case.ir_window_retention()
    if held < FLANGE_OVERLAP_MIN:
        problems.append(Problem(
            f"IR insert retention is {held:.2f}, wants {FLANGE_OVERLAP_MIN:.2f}",
            part="ir-window",
        ))
    land = params.IR_WINDOW_FLANGE - params.IR_WINDOW_PRESS
    if land < ADHESIVE_LAND_MIN:
        problems.append(Problem(
            f"IR adhesive land is {land:.2f}, wants {ADHESIVE_LAND_MIN:.2f}",
            part="ir-window",
        ))

    pane = _surface_run(window, cx, cy)
    if pane is None:
        problems.append(Problem(
            "IR insert has no material on U2's optical centreline",
            at=(cx, cy, 0.0), part="ir-window",
        ))
    else:
        closure = Pos(cx, cy, pane[0] + params.IR_WINDOW_T / 2) * Box(
            PROBE_D, PROBE_D, params.IR_WINDOW_T
        )
        frac = _fill_fraction(window, closure)
        if frac < 0.9:
            problems.append(Problem(
                f"installed IR insert reads {frac:.2f} solid across its pane "
                "on centreline",
                box=closure, part="ir-window",
            ))
    return problems
