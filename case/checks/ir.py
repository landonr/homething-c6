"""Built-solid checks for U2's bottom-facing window and unchanged end ports."""

from build123d import Box, Pos

import board
import case
import params

from .common import PROBE_D, TOLERANCE, _fill_fraction, _volume


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


def _floor_bearing(back):
    """Built back-floor bounds beside the receiver feature, at matching y."""
    x0, x1, y0, y1 = _receiver_span()
    x = x1 + params.IR_WINDOW_FLANGE + params.IR_WINDOW_FIT + PROBE_D
    return _column(back, x, (y0 + y1) / 2)


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
            problems.append(f"{name} reads {frac:.2f} solid at its exterior wall")
    return problems


def receiver_paths(shells, back):
    """U2 sees through -Z while its obsolete +Y sightline is closed."""
    x0, x1, y0, y1 = _receiver_span()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bearing = _floor_bearing(back)
    if bearing is None:
        return ["no built back-floor bearing beside U2's aperture"]

    problems = []
    sightline = Pos(cx, cy, (bearing.min.Z + bearing.max.Z) / 2) * Box(
        PROBE_D,
        PROBE_D,
        bearing.max.Z - bearing.min.Z + 0.4,
    )
    frac = _fill_fraction(back, sightline)
    if frac > 0.1:
        problems.append(
            f"U2 bottom sightline reads {frac:.2f} solid through the built back floor"
        )

    edge_y = board.board_profile().bounding_box().max.Y + case.LAP_OUT
    u2 = board.part_envelope("U2", radius=3.0)
    obsolete = Pos(cx, edge_y - OPENING_INSET / 2, u2.center().Z) * Box(
        PROBE_D, OPENING_INSET, PROBE_D
    )
    frac = _fill_fraction(shells, obsolete)
    if frac < 0.9:
        problems.append(
            f"obsolete U2 +Y path reads only {frac:.2f} solid at the end wall"
        )
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
    fouled = _volume((back + window).intersect(clearance))
    if fouled > TOLERANCE:
        return [f"U2 clearance volume is fouled by {fouled:.2f} mm3"]
    return []


def window_installation(back, window):
    """Insert is flush, press-held, flanged onto adhesive land, and closes."""
    x0, x1, y0, y1 = _receiver_span()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bearing = _floor_bearing(back)
    if bearing is None:
        return ["no built back-floor bearing beside U2's aperture"]
    outer = bearing.min.Z
    pane_top = outer + params.IR_WINDOW_T
    problems = []

    window_column = _column(window, cx, cy)
    if window_column is None:
        problems.append("IR insert has no material on U2's optical centreline")
    else:
        flush_error = window_column.min.Z - outer
        if abs(flush_error) > TOLERANCE:
            problems.append(
                f"IR insert exterior is {flush_error:+.2f} mm from the built back surface"
            )

    press_z = outer + params.IR_WINDOW_T / 2
    press = max(params.IR_WINDOW_PRESS, PRESS_INTERFERENCE_REQUIRED)
    inside = PRESS_PROBE_D / 2
    press_points = (
        (x0 - press + inside, cy),
        (x1 + press - inside, cy),
        (cx, y0 - press + inside),
        (cx, y1 + press - inside),
    )
    for x, y in press_points:
        probe = Pos(x, y, press_z) * Box(PRESS_PROBE_D, PRESS_PROBE_D, PRESS_PROBE_D)
        if _fill_fraction(window, probe) < 0.8 or _fill_fraction(back, probe) < 0.8:
            problems.append(
                f"IR insert does not fill the full {press:.2f} press band "
                "at every bearing"
            )
            break

    overlap = params.IR_WINDOW_FLANGE / 2
    flange_points = (
        (x1 + overlap, cy),
        (x0 - overlap, cy),
        (cx, y1 + overlap),
        (cx, y0 - overlap),
    )
    flange_z = pane_top + PRESS_PROBE_D
    shoulder_z = pane_top - PRESS_PROBE_D
    for x, y in flange_points:
        flange_probe = Pos(x, y, flange_z) * Box(PROBE_D / 2, PROBE_D / 2, PRESS_PROBE_D)
        shoulder_probe = Pos(x, y, shoulder_z) * Box(
            PROBE_D / 2, PROBE_D / 2, PRESS_PROBE_D
        )
        if _fill_fraction(window, flange_probe) < 0.8:
            problems.append("IR insert flange does not overlap the aperture on every side")
            break
        if _fill_fraction(back, shoulder_probe) < 0.8:
            problems.append("IR insert flange has no continuous shell shoulder for adhesive")
            break

    held = case.ir_window_retention()
    if held < FLANGE_OVERLAP_MIN:
        problems.append(
            f"IR insert retention is {held:.2f}, wants {FLANGE_OVERLAP_MIN:.2f}"
        )
    land = params.IR_WINDOW_FLANGE - params.IR_WINDOW_PRESS
    if land < ADHESIVE_LAND_MIN:
        problems.append(
            f"IR adhesive land is {land:.2f}, wants {ADHESIVE_LAND_MIN:.2f}"
        )

    closure = Pos(cx, cy, outer + params.IR_WINDOW_T / 2) * Box(
        PROBE_D, PROBE_D, params.IR_WINDOW_T
    )
    frac = _fill_fraction(window, closure)
    if frac < 0.9:
        problems.append(
            f"installed IR insert reads {frac:.2f} solid across its pane on centreline"
        )
    return problems
