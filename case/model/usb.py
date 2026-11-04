"""The USB-C opening through the -Y end wall."""

from build123d import Box, Pos, chamfer

import board
import params



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


def _chamfer_window_corners(window, length, lower):
    """Clip the X/Z corners along the USB opening's full Y reach."""
    box = window.bounding_box()
    corners = [
        edge
        for edge in window.edges()
        if edge.bounding_box().size.Y > box.size.Y - 1e-4
        and (
            abs(edge.center().Z - box.max.Z) < 1e-4
            or (lower and abs(edge.center().Z - box.min.Z) < 1e-4)
        )
    ]
    expected = 4 if lower else 2
    if len(corners) != expected:
        raise ValueError(f"expected {expected} USB corner edges, found {len(corners)}")
    return chamfer(corners, length)


def usb_slot():
    """Clear the complete underside shell through the -Y end wall."""
    box = board.usb_envelope()
    c = params.USB_CLEARANCE
    edge_y = board.board_profile().bounding_box().min.Y
    bottom = box.min.Z - c
    top = box.max.Z + c
    window = _end_window(
        box.center().X,
        (bottom + top) / 2,
        box.size.X + 2 * c,
        top - bottom,
        edge_y,
        -1,
        max(params.IR_RELIEF_DEPTH, box.max.Y + c - edge_y),
    )
    return _chamfer_window_corners(window, params.USB_CORNER_CHAMFER, lower=True)
