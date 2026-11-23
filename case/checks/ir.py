"""Built-solid checks for U2's bottom-facing window and the end ports."""

import math

from build123d import Box, Pos

import board
import case
import params
from model.backform import back_form

from .common import (
    PROBE_D,
    TOLERANCE,
    Problem,
    _fill_fraction,
    _ray_runs,
    _volume,
)


OPENING_INSET = 0.5
WINDOW_EDGE_TOL = 0.005
"""Precision of the assembly clearance comparison, in mm."""
WINDOW_BOND_LAND_MIN = 0.4
EMITTER_HALF_ANGLE_REQUIRED = 15.0
"""Half-intensity angle of the INL-3AHIR30 from the optical axis."""
EMITTER_CHAMFER_ANGLE_REQUIRED = 45.0


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
    usb = board.usb_profile().center()
    probes = (
        (
            "D1 bore",
            lens.center().X,
            edge.max.Y + case.LAP_OUT - OPENING_INSET / 2,
            lens.center().Z,
        ),
        (
            "USB",
            usb.X,
            edge.min.Y - case.LAP_OUT + OPENING_INSET / 2,
            usb.Z,
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


def emitter_beam_clearance(shells):
    """Read off-axis rays through the assembled end wall."""
    lens = board.emitter_envelope()
    x, _, z = lens.center()
    outer_y = board.board_profile().bounding_box().max.Y + case.LAP_OUT
    radius = max(lens.size.X, lens.size.Z) / 2 + params.IR_EMITTER_FIT - TOLERANCE
    throat_y = outer_y - params.IR_EMITTER_CHAMFER_DEPTH
    start_y = min(lens.max.Y, throat_y)
    depth = outer_y - start_y
    outer_radius = radius + depth * math.tan(math.radians(EMITTER_HALF_ANGLE_REQUIRED))
    problems = []
    for azimuth in range(0, 360, 45):
        angle = math.radians(azimuth)
        dx, dz = math.cos(angle), math.sin(angle)
        start = (x + radius * dx, start_y, z + radius * dz)
        end = (x + outer_radius * dx, outer_y, z + outer_radius * dz)
        runs = _ray_runs(shells, start, end)
        if runs:
            problems.append(Problem(
                f"D1 beam clearance at {azimuth}° around the axis is blocked "
                f"for {runs[0][1] - runs[0][0]:.2f} mm",
                at=end,
            ))
    return problems


def emitter_chamfer_angle(shells):
    """Measure radial growth between two sections of the built chamfer."""
    lens = board.emitter_envelope()
    x, _, z = lens.center()
    outer_y = board.board_profile().bounding_box().max.Y + case.LAP_OUT
    span = params.IR_EMITTER_CHAMFER_DEPTH / 2
    reach = lens.size.X / 2 + params.IR_EMITTER_FIT + params.IR_EMITTER_CHAMFER_DEPTH + OPENING_INSET
    inner_y = outer_y - 1.5 * span
    outer_section_y = inner_y + span
    inner = _ray_runs(shells, (x, inner_y, z), (x + reach, inner_y, z))
    outer = _ray_runs(shells, (x, outer_section_y, z), (x + reach, outer_section_y, z))
    if inner and outer:
        angle = math.degrees(math.atan2(outer[0][0] - inner[0][0], span))
        expected_growth = span * math.tan(math.radians(EMITTER_CHAMFER_ANGLE_REQUIRED))
        if abs(outer[0][0] - inner[0][0] - expected_growth) <= TOLERANCE:
            return []
        return [Problem(f"D1 chamfer measures {angle:.1f}°, wants 45°", at=(x, outer_section_y, z))]
    return [Problem("no built wall beside D1's chamfer", at=(x, outer_section_y, z))]


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


def receiver_clearance(back, window=None):
    """Built shell and installed insert stay clear of U2 plus its optical margin.
    The one-piece back has no insert, so it comes with `window` None."""
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
    intruding = (back if window is None else back + window).intersect(clearance)
    fouled = _volume(intruding)
    if fouled > TOLERANCE:
        # The intruding material's own bounds rather than the clearance volume's:
        # the box is there to be looked at, and the whole keepout says only that
        # the failure is somewhere in it.
        return [Problem(f"U2 clearance volume is fouled by {fouled:.2f} mm3",
                        box=intruding)]
    return []


def _window_edges():
    """Outward normals at the four flats and four rounded corners."""
    x0, x1, y0, y1 = _receiver_span()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    radius = params.IR_WINDOW_R
    corner_component = math.sqrt(0.5)
    yield from (
        (x0, cy, -1, 0), (x1, cy, 1, 0), (cx, y0, 0, -1), (cx, y1, 0, 1),
    )
    inset = radius * (1 - corner_component)
    for x, sx in ((x0, -1), (x1, 1)):
        for y, sy in ((y0, -1), (y1, 1)):
            yield x - sx * inset, y - sy * inset, sx * corner_component, sy * corner_component


def _window_edge_clearances(back, window):
    """Read both gaps and the bond land between the built mating edges."""
    problems = []
    minimum = params.PCBWAY_ASSEMBLY_CLEARANCE
    for x, y, nx, ny in _window_edges():
        shoulder = _surface_run(back, x + 0.03 * nx, y + 0.03 * ny)
        overlap = params.IR_WINDOW_FLANGE / 2
        bond_point = (x + overlap * nx, y + overlap * ny)
        seat = _surface_run(back, *bond_point)
        flange = _surface_run(window, *bond_point)
        if shoulder is None or seat is None or flange is None:
            problems.append(Problem(
                "IR flange or shell shoulder is absent at the adhesive land",
                at=(x, y, 0.0), part="ir-window",
            ))
            continue
        if abs(flange[0] - seat[1]) > TOLERANCE:
            problems.append(Problem(
                "IR flange does not seat on the shell shoulder",
                at=(*bond_point, seat[1]), part="case-back",
            ))
        # Start inside the pane and end beyond the outer flange rebate.
        inward = OPENING_INSET
        outward = params.IR_WINDOW_FLANGE + params.IR_WINDOW_FIT + OPENING_INSET
        edges = {}
        for name, run in (("pane", shoulder), ("flange", flange)):
            z = sum(run) / 2
            start = (x - inward * nx, y - inward * ny, z)
            end = (x + outward * nx, y + outward * ny, z)
            shell_runs = _ray_runs(back, start, end)
            insert_runs = _ray_runs(window, start, end)
            if not shell_runs or not insert_runs:
                problems.append(Problem(
                    f"IR {name} clearance probe misses a mating edge",
                    at=(x, y, z), part="ir-window",
                ))
                continue
            shell_edge = shell_runs[0][0]
            insert_edge = insert_runs[-1][1]
            gap = shell_edge - insert_edge
            if gap < minimum - WINDOW_EDGE_TOL:
                problems.append(Problem(
                    f"IR {name} clearance is {gap:.3f} mm, wants {minimum:.2f} mm",
                    at=(x, y, z), part="ir-window",
                ))
            edges[name] = (shell_edge, insert_edge)
        if "pane" in edges and "flange" in edges:
            land = edges["flange"][1] - edges["pane"][0]
            if land >= WINDOW_BOND_LAND_MIN:
                continue
            problems.append(Problem(
                f"IR adhesive land is {land:.2f} mm, wants {WINDOW_BOND_LAND_MIN:.2f} mm",
                at=(x, y, shoulder[1]), part="ir-window",
            ))
    return problems


def window_installation(back, window):
    """Check the pane, adhesive shoulder, and both fitted clearances."""
    x0, x1, y0, y1 = _receiver_span()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    problems = _window_edge_clearances(back, window)
    pane = _surface_run(window, cx, cy)
    if pane is None:
        problems.append(Problem(
            "IR insert has no material on U2's optical centreline",
            at=(cx, cy, 0.0), part="ir-window",
        ))
    else:
        exterior = _surface_run(back_form(0, 0), cx, cy)
        if exterior is None or abs(pane[0] - exterior[0]) > TOLERANCE:
            problems.append(Problem(
                "IR pane is not flush with the back form at the optical centreline",
                at=(cx, cy, pane[0]), part="ir-window",
            ))
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


WELL_INSET = 0.25
"""How far inside the well's own walls the pane readings stay."""

WELL_STEP = 0.5
"""Step of the pane readings across the well."""


def one_piece_window(one_piece):
    """The one-piece back keeps the insert's optical path. Across the well
    under U2, each vertical bearing meets one run of material, IR_WINDOW_T
    thick, from the exterior. Under the flange it meets IR_WINDOW_T plus
    IR_WINDOW_FLANGE_T. Returns the problems and the thinnest and thickest
    pane readings."""
    part = "case-back-one-piece"
    x0, x1, y0, y1 = _receiver_span()
    inset = OPENING_INSET + WELL_INSET
    problems, panes = [], []
    x = x0 + inset
    while x <= x1 - inset + 1e-9:
        y = y0 + inset
        while y <= y1 - inset + 1e-9:
            runs = _bearing_runs(one_piece, x, y)
            if len(runs) != 1:
                problems.append(Problem(
                    f"U2's beam meets {len(runs)} runs of the one-piece back "
                    "here, wants the pane alone",
                    at=(x, y, runs[0][0] if runs else 0.0), part=part,
                ))
            else:
                depth = runs[0][1] - runs[0][0]
                panes.append(depth)
                if abs(depth - params.IR_WINDOW_T) > TOLERANCE:
                    problems.append(Problem(
                        f"U2's beam crosses {depth:.2f} of the one-piece back "
                        f"here, wants the pane's {params.IR_WINDOW_T:.2f}",
                        at=(x, y, runs[0][1]), part=part,
                    ))
            y += WELL_STEP
        x += WELL_STEP
    flange = params.IR_WINDOW_T + params.IR_WINDOW_FLANGE_T
    mid = (OPENING_INSET + params.IR_WINDOW_FLANGE) / 2
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for x, y in ((x1 + mid - OPENING_INSET, cy), (x0 - mid + OPENING_INSET, cy),
                 (cx, y1 + mid - OPENING_INSET), (cx, y0 - mid + OPENING_INSET)):
        runs = _bearing_runs(one_piece, x, y)
        depth = runs[0][1] - runs[0][0] if runs else 0.0
        if abs(depth - flange) > TOLERANCE:
            problems.append(Problem(
                f"the one-piece back stands {depth:.2f} off the exterior under "
                f"the flange, wants the pane and flange's {flange:.2f}",
                at=(x, y, runs[0][1] if runs else 0.0), part=part,
            ))
    if not panes:
        problems.append(Problem(
            "no pane reading across the one-piece back's well", part=part
        ))
        return problems, None
    return problems, (len(panes), min(panes), max(panes))
