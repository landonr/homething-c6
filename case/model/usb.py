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


def usb_roof():
    """Top of both USB voids: the connector's own envelope plus USB_CLEARANCE.

    One expression for the pocket and the slot, so the two are flush by
    construction. They were not: the slot has always been this, and the pocket
    was CAVITY_FRONT_USB plus MERGE, which stands 0.3 higher for no reason the
    connector asks for. What that cost was ceiling. The step between the two
    roofs was also a ledge in the middle of one continuous void, which is
    material the print has to bridge to and then leave.

    CAVITY_FRONT_USB is where this started and is now the floor under it rather
    than the value itself: FRONT_KEEPOUT was sized to the USB-C shell by hand
    and comes out a couple of tenths under what the measured envelope and its
    clearance actually want, which is the whole reason the MERGE fudge was
    there. Reading the envelope is what makes the number exact.
    """
    box = board.usb_envelope()
    return max(
        CAVITY_FRONT_USB, box.center().Z + box.size.Z / 2 + params.USB_CLEARANCE
    )


def usb_pocket():
    """Local extra ceiling depth over the USB connector's own footprint,
    reaching usb_roof(), the one place under the front shell still taller
    than a switch. Blind: it stops there rather than breaking through to
    the face, leaving the front's own face less usb_roof() of ceiling over
    it, the same outer face plane as everywhere else.

    Padded by USB_CLEARANCE in plan as well as height, on the connector's
    own full envelope, not just the sliver of it that crosses the board
    edge through usb_slot()'s own end-wall opening: this local ceiling
    bump is independent of that opening and stays even though usb_slot()
    is a through-cut again, since the connector's body still needs more
    height than a switch anywhere under this shallower ceiling. See
    usb_slot() for the end wall's own opening, which shares this same
    envelope.

    Symmetric everywhere but the inboard side, which reaches
    USB_POCKET_INBOARD_REACH further in again. That is the side the plug
    arrives from, and what it wants is a run at the connector's full height
    before the ceiling steps back down, rather than the lip standing at the
    end of the connector's own footprint. The lip's ramp is already the whole
    of its height and cannot give more, so the wall moves and the ramp rides
    with it. The reach is the pocket's alone: usb_slot()'s opening through the
    end wall is sized on USB_CLEARANCE and does not grow.
    """
    box = board.usb_envelope()
    c = params.USB_CLEARANCE
    # MERGE at the bottom only, to break cleanly into the cavity below. The top
    # is usb_roof() exactly, which is the slot's own roof, so the two voids meet
    # flush instead of leaving a step in the middle of one opening.
    # _chamfer_usb_pocket_lip() measures the wall it ramps from this solid
    # rather than from the stack, so it follows this without being told.
    top = usb_roof()
    bottom = CAVITY_FRONT - MERGE
    y0 = box.min.Y - c
    y1 = box.max.Y + c + params.USB_POCKET_INBOARD_REACH
    return Pos(box.center().X, (y0 + y1) / 2, (bottom + top) / 2) * Box(
        box.size.X + 2 * c,
        y1 - y0,
        top - bottom,
    )
