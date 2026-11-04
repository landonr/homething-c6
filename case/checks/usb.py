"""Clearance and exterior access for the underside USB connector."""

from build123d import Box, Pos

import board
import params

from .common import TOLERANCE, _volume

CONNECTOR_MARGIN_MIN = 0.2
"""Minimum free margin beside a connector, independent of the cut dimensions."""


def usb_clearance(front, front_fdm, back):
    """Probe the complete shell envelope and its approach through both shells."""
    box = board.usb_envelope()
    c = CONNECTOR_MARGIN_MIN
    edge = board.board_profile().bounding_box().min.Y
    y0 = edge - params.WALL * 6
    y1 = box.max.Y
    corridor = Pos(box.center().X, (y0 + y1) / 2, box.center().Z) * Box(
        box.size.X + 2 * c, y1 - y0, box.size.Z + 2 * c
    )
    problems = []
    for name, shell in (("front", front), ("FDM front", front_fdm), ("back", back)):
        volume = _volume(shell.intersect(corridor))
        if volume > TOLERANCE:
            problems.append(
                f"{name} shell blocks the USB approach and {c:.2f} margin "
                f"by {volume:.2f} mm3"
            )
    return problems
