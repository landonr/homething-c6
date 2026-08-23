"""USB pocket clearance: the local deeper cavity over the USB connector's own
footprint actually clears its body by USB_CLEARANCE, probed against
board.usb_envelope() on the built shell rather than trusted from
CAVITY_FRONT_USB alone, and the ceiling left above the pocket has not gone
below USB_CEILING_MIN.
"""

from build123d import Box, Pos

import board
import case
import params

from .common import TOLERANCE, _volume

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
    is what proves the pocket clears with USB_CLEARANCE of the margin it
    was cut for rather than merely not touching by accident.

    Also holds the ceiling left over the pocket to USB_CEILING_MIN,
    arithmetic, the same trap recess_land() guards on the keypad side.
    """
    problems = []
    remaining = case.SHELL_FRONT - case.CAVITY_FRONT_USB
    if remaining < USB_CEILING_MIN - TOLERANCE:
        problems.append(
            f"USB pocket leaves only {remaining:.2f} of ceiling, wants "
            f"{USB_CEILING_MIN:.2f}"
        )

    box = board.usb_envelope()
    c = params.USB_CLEARANCE
    grown = Pos(box.center().X, box.center().Y, box.center().Z) * Box(
        box.size.X + 2 * c, box.size.Y + 2 * c, box.size.Z + 2 * c
    )
    fouled = _volume(front.intersect(grown))
    if fouled > TOLERANCE:
        problems.append(
            f"front shell reaches inside USB_CLEARANCE of the connector by "
            f"{fouled:.2f} mm3"
        )
    return problems
