"""USB pocket clearance: the local deeper cavity over the USB connector's own
footprint clears its body at the slot's specified margins, probed against
board.usb_envelope() on the built shell rather than trusted from
CAVITY_FRONT_USB alone, and the ceiling left above the pocket has not gone
below USB_CEILING_MIN.

USB pocket reach: the pocket's inboard wall stands USB_POCKET_INBOARD_REACH
past the connector's envelope and its clearance, and the lip's ramp came with
it. That reach is what the plug slides in along, so what is worth reading is
the run of full-height void the built front actually leaves inboard of the
connector, and where along it the shell closes again. Read by ray along +Y at
several heights: each ray gives the ramp's own y at that height, the run before
it is the clear approach, and the rise over run between the heights is the 45
degrees the ramp is cut at. The ramp's top is then compared against the built
pocket's own wall, because _chamfer_usb_pocket_lip() takes the wall off that
solid and the whole point of the reach is that the two moved together.
"""

from build123d import Box, Pos, chamfer

import board
import case
import params

from .common import TOLERANCE, _ray_runs, _volume

USB_CEILING_MIN = 0.4
"""Thinnest the ceiling may be left over the USB pocket, the local bump
where the cavity reaches CAVITY_FRONT_USB instead of the keypad region's
own shallower CAVITY_FRONT. On the scale of what a keypad recess sinks into
the face: a thin, deliberate wall rather than a structural ceiling, since
nothing loads it directly, but not free to vanish either."""


def usb_pocket_clearance(front):
    """The USB pocket actually clears the connector's own body, probed
    against board.usb_envelope() on the built shell rather than trusted
    from CAVITY_FRONT_USB and USB_CLEARANCE alone: interference() would
    eventually catch a real collision too, but reports it as a nameless
    colliding solid rather than pointing at this specific feature, and this
    proves the specified side and roof margins. The raised slot bottom trades
    away USB_SLOT_BOTTOM_RAISE of its original lower margin. Its four 45 degree
    corners remove a small triangle from that clearance envelope, so the
    probe clips those corners too before reading the built shell.

    Also holds the ceiling left over the pocket to USB_CEILING_MIN,
    arithmetic, the same trap recess_land() guards on the keypad side.
    """
    problems = []
    # Off the built pocket, not off CAVITY_FRONT_USB, which is the floor under
    # usb_roof() rather than the roof itself. Reading the solid is what makes
    # the number the one the part actually has.
    remaining = case.SHELL_FRONT - case.usb_pocket().bounding_box().max.Z
    if remaining < USB_CEILING_MIN - TOLERANCE:
        problems.append(
            f"USB pocket leaves only {remaining:.2f} of ceiling, wants "
            f"{USB_CEILING_MIN:.2f}"
        )

    box = board.usb_envelope()
    c = params.USB_CLEARANCE
    bottom = box.min.Z - c + params.USB_SLOT_BOTTOM_RAISE
    top = box.max.Z + c
    grown = Pos(box.center().X, box.center().Y, (bottom + top) / 2) * Box(
        box.size.X + 2 * c, box.size.Y + 2 * c, top - bottom
    )
    y_span = grown.bounding_box().size.Y
    longitudinal_edges = [
        edge for edge in grown.edges()
        if edge.bounding_box().size.Y > y_span - 1e-4
    ]
    probe = chamfer(longitudinal_edges, params.USB_CORNER_CHAMFER)
    fouled = _volume(front.intersect(probe))
    if fouled > TOLERANCE:
        problems.append(
            f"front shell reaches inside the USB slot's specified clearance "
            f"by {fouled:.2f} mm3"
        )
    return problems


RAMP_SAMPLES = 3
"""Heights the lip's ramp is read at, spanning the wall between the cavity
ceiling and the pocket roof. Three rather than two because two give one slope
and no way to tell a ramp from a chord across a round: three give two slopes
that have to agree with each other as well as with 45 degrees."""

RAMP_PROBE_INSET = 0.1
"""How far off the cavity ceiling and the pocket roof the outermost rays stand.
Both are horizontal boundaries of the wall being read, and a ray in either
plane runs along a surface rather than across it."""

RAMP_SLOPE_TOLERANCE = 0.06
"""How far the ramp's measured run per unit of height may sit from the 1.0 a 45
degree chamfer has. Boolean and tessellation slop at the ends of a step a
millimetre and a half long, not an allowance on the angle. The top of the wall
also keeps OCC_CHAMFER_GAP of square face, since OCCT refuses a chamfer that
consumes its own face exactly, so the topmost ray is a micron shy of the ramp
proper."""

RAMP_TOLERANCE = 0.05
"""How far the ramp's own top, extrapolated back to the pocket roof, may sit
from the built pocket's inboard wall."""


def usb_pocket_reach(front):
    """The pocket's inboard wall stands where USB_POCKET_INBOARD_REACH puts it,
    and the lip's ramp came with it.

    Three claims off one sweep of rays along +Y through the built front, at the
    pocket's own centre in x, at heights spanning the wall.

    The wall moved. The built pocket's inboard face is read off that solid and
    has to stand USB_POCKET_INBOARD_REACH past the connector's measured
    envelope plus USB_CLEARANCE, which is what says the reach is asymmetric and
    on the side the plug arrives from rather than having grown the clearance
    everywhere. usb_slot() is sized on USB_CLEARANCE alone and is not read
    here, deliberately: the connector's opening through the end wall must not
    grow, and usb_pocket_clearance() is what holds it to the envelope.

    The void is real. Each ray starts at the connector's own inboard face,
    inside the pocket, and the run before the shell first closes is the clear
    approach the plug has at that height. At the pocket roof that run has to be
    the whole of USB_CLEARANCE plus the reach, which is the thing the reach was
    bought for and is a reading of the built front rather than of the box that
    cut it.

    The ramp rode with it. Those same first-material readings are the ramp's
    own y at each height, so the run per unit of height between them is the 45
    degrees USB_POCKET_LIP_CHAMFER is cut at, and the line they lie on
    extrapolated back to the roof is where the ramp starts. That has to be the
    built pocket's wall, which is what says _chamfer_usb_pocket_lip() followed
    the pocket rather than the envelope it used to measure from.
    """
    problems = []
    pocket = case.usb_pocket().bounding_box()
    envelope = board.usb_envelope()
    wall_y = pocket.max.Y
    reach = wall_y - (envelope.max.Y + params.USB_CLEARANCE)
    if abs(reach - params.USB_POCKET_INBOARD_REACH) > TOLERANCE:
        problems.append(
            f"the built pocket's inboard wall stands {reach:.2f} past the "
            f"connector's envelope and USB_CLEARANCE, where "
            f"USB_POCKET_INBOARD_REACH says "
            f"{params.USB_POCKET_INBOARD_REACH:.2f}"
        )

    x = pocket.center().X
    roof = pocket.max.Z
    start_y = envelope.max.Y
    # Past the ramp's own foot at the cavity ceiling, so a ray that meets
    # nothing means the shell never closed rather than that the ray stopped
    # short of where it does.
    end_y = wall_y + params.USB_POCKET_LIP_CHAMFER + params.WALL
    lo, hi = case.CAVITY_FRONT + RAMP_PROBE_INSET, roof - RAMP_PROBE_INSET
    read = []
    for i in range(RAMP_SAMPLES):
        z = lo + (hi - lo) * i / (RAMP_SAMPLES - 1)
        runs = _ray_runs(front, (x, start_y, z), (x, end_y, z))
        if not runs:
            problems.append(
                f"the front shell never closes inboard of the USB pocket at "
                f"z={z:.2f}, out to {end_y - start_y:.2f} past the connector"
            )
            read.append(None)
            continue
        read.append((z, start_y + runs[0][0]))

    if any(entry is None for entry in read):
        return problems

    top_z, top_y = read[-1]
    clear = top_y - start_y
    want = params.USB_CLEARANCE + params.USB_POCKET_INBOARD_REACH
    # The topmost ray stands RAMP_PROBE_INSET under the roof, and the ramp has
    # already run that far inboard by the time it gets there, so the run at the
    # roof itself is that much shorter than the one the ray reads.
    at_roof = clear - RAMP_PROBE_INSET
    if at_roof < want - TOLERANCE:
        problems.append(
            f"the plug has only {at_roof:.2f} of full-height run inboard of the "
            f"connector, where USB_CLEARANCE and USB_POCKET_INBOARD_REACH "
            f"together buy {want:.2f}"
        )

    for (z_lo, y_lo), (z_hi, y_hi) in zip(read, read[1:]):
        slope = (y_lo - y_hi) / (z_hi - z_lo)
        if abs(slope - 1) > RAMP_SLOPE_TOLERANCE:
            problems.append(
                f"the USB pocket's lip runs {slope:.2f} inboard per unit of "
                f"height between z={z_lo:.2f} and z={z_hi:.2f}, where the 45 "
                f"degree ramp USB_POCKET_LIP_CHAMFER cuts runs 1.00"
            )
            break

    ramp_top = top_y - (roof - top_z)
    if abs(ramp_top - wall_y) > RAMP_TOLERANCE:
        problems.append(
            f"the lip's ramp starts at y {ramp_top:.2f} at the pocket roof, where "
            f"the built pocket's own inboard wall is at {wall_y:.2f}: "
            f"_chamfer_usb_pocket_lip() is ramping a wall that is not there"
        )
    return problems
