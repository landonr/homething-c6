"""The USB-C opening and the cable boot pocket in the -Y end wall."""

from build123d import Kind, Plane, Pos, RectangleRounded, extrude, offset

import board
import params


def usb_slot():
    """Cut the measured USB shell outline plus USB_CLEARANCE through the -Y end wall.

    The cut starts outside the wall and ends inside the board edge, past the
    USB shell or IR_RELIEF_DEPTH, whichever is longer.
    """
    box = board.usb_envelope()
    c = params.USB_CLEARANCE
    edge_y = board.board_profile().bounding_box().min.Y
    # WALL * 6 clears any end wall and lap this model has used.
    y_out = edge_y - params.WALL * 6
    y_in = edge_y + max(params.IR_RELIEF_DEPTH, box.max.Y + c - edge_y)
    outline = offset(board.usb_profile(), c, kind=Kind.ARC)
    start = Pos(0, y_out - outline.bounding_box().min.Y, 0) * outline
    return extrude(start, y_in - y_out, dir=(0, 1, 0))


def usb_boot_floor_y():
    """Return the Y of the boot pocket floor.

    The floor is USB_BOOT_REACH from the receptacle mouth while the plug pushes
    the board +Y by WHEEL_OPENING_CLEARANCE.
    """
    return (
        board.usb_envelope().min.Y
        + params.WHEEL_OPENING_CLEARANCE
        - params.USB_BOOT_REACH
    )


def usb_boot_outline(y):
    """Return the boot pocket outline as a face in the XZ plane at `y`."""
    centre = board.usb_profile().center()
    plane = Plane(origin=(centre.X, y, centre.Z), x_dir=(1, 0, 0), z_dir=(0, 1, 0))
    return plane * RectangleRounded(
        params.USB_BOOT_W, params.USB_BOOT_H, params.USB_BOOT_R
    )


def usb_boot_pocket():
    """Cut a pocket for the cable boot from the outside of the -Y end wall.

    The pocket lets the boot come near enough to the receptacle for the plug
    to seat.
    """
    floor_y = usb_boot_floor_y()
    y_out = board.board_profile().bounding_box().min.Y - params.WALL * 6
    return extrude(usb_boot_outline(y_out), floor_y - y_out, dir=(0, 1, 0))
