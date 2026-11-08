"""The USB-C opening and the cable boot pocket in the -Y end wall."""

from pathlib import Path
from tempfile import TemporaryDirectory

from build123d import (
    Edge, Kind, Plane, Pos, RectangleRounded, export_brep, extrude, import_brep, offset,
)

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


def round_usb_boot_rim(shell, exterior):
    """Round the outside lip where the pocket meets the back contour."""
    # OCCT rejects these edges on the live boolean result but accepts the BREP copy.
    with TemporaryDirectory() as directory:
        path = Path(directory) / "back.brep"
        export_brep(shell, path)
        shell = import_brep(path).solids()[0]

    floor_y = usb_boot_floor_y()
    outline = usb_boot_outline(floor_y).faces()[0].outer_wire()
    outside_y = exterior.bounding_box().min.Y - params.WALL
    tolerance = 1e-5
    rim = []
    for edge in shell.edges():
        box = edge.bounding_box()
        if box.max.Y >= floor_y - tolerance or box.size.X + box.size.Z < tolerance:
            continue
        x, y, z = edge.position_at(0.5)
        if outline.distance_to((x, floor_y, z)) >= tolerance:
            continue
        # The pocket crosses the lap inside the case as well as the outer wall.
        ray = Edge.make_line((x, outside_y, z), (x, floor_y, z))
        crossing = exterior.intersect(ray)
        if crossing and abs(y - min(v.Y for v in crossing.vertices())) < tolerance:
            rim.append(edge)
    if not rim:
        raise ValueError("USB boot pocket has no exterior rim")
    return shell.fillet(params.USB_BOOT_RIM_R, rim)
