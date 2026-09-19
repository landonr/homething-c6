"""The USB-C connector's two features: the through-cut at the -Y end wall, and
the local deeper ceiling over the connector's own footprint."""

from build123d import Box, Pos

import board
import params

from .stack import CAVITY_FRONT, CAVITY_FRONT_USB, MERGE


def _end_window(cx, cz, size_x, size_z, edge_y, sign, inward):
    """One through-cut into an end wall, opening from the cavity side clean
    through the exterior face and well past it. `sign` is +1 for the +Y end
    (D1) and -1 for the -Y end (USB). `WALL * 6` is comfortably past any
    wall thickness this model has used, so it blows through regardless of
    LAP_OUT rather than a reach tuned to the current wall. Reaches `inward`
    back past the edge the other way, into the board, for a clean connection
    to the cavity proper.
    """
    reach = params.WALL * 6
    y_out = edge_y + sign * reach
    y_in = edge_y - sign * inward
    y0, y1 = sorted((y_in, y_out))
    return Pos(cx, (y0 + y1) / 2, cz) * Box(size_x, y1 - y0, size_z)


def usb_slot():
    """The USB-C shell straddles the split plane and overhangs the
    board's -Y edge. A through-cut sized off board.usb_envelope() plus
    USB_CLEARANCE, reaching well past
    the exterior face on both shells so the connector is reachable from
    outside the case without opening it.
    """
    box = board.usb_envelope()
    c = params.USB_CLEARANCE
    edge_y = board.board_profile().bounding_box().min.Y
    return _end_window(
        box.center().X,
        box.center().Z,
        box.size.X + 2 * c,
        box.size.Z + 2 * c,
        edge_y,
        -1,
        params.IR_RELIEF_DEPTH,
    )


def usb_pocket():
    """Local extra ceiling depth over the USB connector's own footprint,
    reaching CAVITY_FRONT_USB, the one place under the front shell still
    taller than a switch. Blind: it stops there rather than breaking
    through to the face, leaving SHELL_FRONT - CAVITY_FRONT_USB of ceiling
    over it, the same outer face plane as everywhere else.

    Padded by USB_CLEARANCE in plan as well as height, on the connector's
    own full envelope, not just the sliver of it that crosses the board
    edge through usb_slot()'s own end-wall opening: this local ceiling
    bump is independent of that opening and stays even though usb_slot()
    is a through-cut again, since the connector's body still needs more
    height than a switch anywhere under this shallower ceiling. See
    usb_slot() for the end wall's own opening, which shares this same
    envelope.
    """
    box = board.usb_envelope()
    c = params.USB_CLEARANCE
    # MERGE at both ends, and the top one is not cosmetic. FRONT_KEEPOUT is
    # sized off the switches, so CAVITY_FRONT_USB alone clears the connector by
    # less than USB_CLEARANCE; the roof has to stand MERGE above it for the
    # margin this pocket is padded for. usb_pocket_clearance() is what caught
    # that. The real roof is CAVITY_FRONT_USB + MERGE, not CAVITY_FRONT_USB,
    # and _chamfer_usb_pocket_lip() measures the wall it ramps from this solid
    # rather than from the stack for the same reason.
    return Pos(box.center().X, box.center().Y, (CAVITY_FRONT + CAVITY_FRONT_USB) / 2) * Box(
        box.size.X + 2 * c,
        box.size.Y + 2 * c,
        CAVITY_FRONT_USB - CAVITY_FRONT + 2 * MERGE,
    )
