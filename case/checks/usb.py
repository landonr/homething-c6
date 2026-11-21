"""Clearance and exterior access for the underside USB connector.

The plug approach must be clear through every shell. The USB shell tip must
also clear the front as the board drops in, and the back as the back folds
closed. The cable boot pocket must be clear in every shell, and its floor must
stop near enough to the receptacle mouth for the plug to seat.
"""

from build123d import Face, Kind, Pos, Wire, extrude, offset
from model.usb import usb_boot_floor_y, usb_boot_outline

import board
import params

from .common import TOLERANCE, _volume

CONNECTOR_MARGIN_MIN = 0.2
"""Minimum free margin beside a connector, independent of the cut dimensions."""

BOOT_REACH_MAX = 0.45
"""Plug reach past its boot, approximately 6.65, less the 6.20 REF receptacle shell."""


def usb_clearance(front, front_fdm, back):
    """Probe the plug approach, the assembly sweep of the tip, and the boot pocket."""
    box = board.usb_envelope()
    profile = board.usb_profile()
    outline = profile.bounding_box()
    c = CONNECTOR_MARGIN_MIN
    edge = board.board_profile().bounding_box().min.Y
    y0 = edge - params.WALL * 6
    grown = offset(profile, c, kind=Kind.ARC)
    corridor = extrude(
        Pos(0, y0 - outline.min.Y, 0) * grown, box.max.Y - y0, dir=(0, 1, 0)
    )
    problems = []
    for name, shell in (("front", front), ("FDM front", front_fdm), ("back", back)):
        volume = _volume(shell.intersect(corridor))
        if volume > TOLERANCE:
            problems.append(
                f"{name} shell blocks the USB approach and {c:.2f} margin "
                f"by {volume:.2f} mm3"
            )

    # A convex outline moved in Z sweeps itself plus a full-width band on that side.
    reach = 30.0
    tip_y = box.min.Y - c
    gb = grown.bounding_box()
    zc = profile.center().Z

    def sweep(z0, z1):
        band = Face(Wire.make_polygon(
            [(gb.min.X, gb.min.Y, z0), (gb.max.X, gb.min.Y, z0),
             (gb.max.X, gb.min.Y, z1), (gb.min.X, gb.min.Y, z1)],
            close=True,
        ))
        start = Pos(0, tip_y - gb.min.Y, 0) * (grown + band)
        return extrude(start, edge - tip_y, dir=(0, 1, 0))

    above = sweep(zc, zc + reach)
    below = sweep(zc - reach, zc)
    for name, shell, probe, motion in (
        ("back", back, above, "the back folds closed"),
        ("front", front, below, "the board drops in"),
        ("FDM front", front_fdm, below, "the board drops in"),
    ):
        volume = _volume(shell.intersect(probe))
        if volume > TOLERANCE:
            problems.append(
                f"{name} shell blocks the USB tip as {motion} by {volume:.2f} mm3"
            )

    mouth_y = box.min.Y
    floor_y = usb_boot_floor_y()
    reach = mouth_y + params.WHEEL_OPENING_CLEARANCE - floor_y
    if reach > BOOT_REACH_MAX:
        problems.append(
            f"USB boot pocket floor stops {reach:.2f} from the receptacle mouth, "
            f"more than {BOOT_REACH_MAX:.2f}"
        )
    if floor_y > mouth_y:
        problems.append(
            f"USB boot pocket floor is {floor_y - mouth_y:.2f} inboard of the "
            f"receptacle mouth, so it cuts past the receptacle face"
        )
    boot = extrude(usb_boot_outline(y0), floor_y - y0, dir=(0, 1, 0))
    for name, shell in (("front", front), ("FDM front", front_fdm), ("back", back)):
        volume = _volume(shell.intersect(boot))
        if volume > TOLERANCE:
            problems.append(
                f"{name} shell blocks the USB cable boot by {volume:.2f} mm3"
            )
    return problems
