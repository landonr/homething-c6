"""The Qwiic plug approach through the left side wall."""

import functools

from build123d import Box, Pos, chamfer

from .shape import _cut, _fuse, _isect, _profiles
from .stack import MERGE

import board
import params


def qwiic_slot():
    """Return a straight plug corridor from the housing through the exterior."""
    box = board.part_envelope("J2")
    edge = board.board_profile().bounding_box().min.X
    c = params.QWIIC_CLEARANCE
    x0, x1 = edge - params.WALL * 6, box.max.X + c
    slot = Pos((x0 + x1) / 2, box.center().Y, box.center().Z) * Box(
        x1 - x0, box.size.Y + 2 * c, box.size.Z + 2 * c
    )
    edges = [
        edge for edge in slot.edges()
        if edge.bounding_box().size.X > x1 - x0 - 1e-4
    ]
    return chamfer(edges, params.QWIIC_CORNER_CHAMFER)


def battery_plug_envelope():
    """Return the internal plug and wire corridor past the PicoBlade mouth."""
    box = board.part_envelope("J1")
    c = params.BATTERY_PLUG_CLEARANCE
    x0, x1 = box.max.X, box.max.X + params.BATTERY_PLUG_REACH
    return Pos((x0 + x1) / 2, box.center().Y, box.center().Z) * Box(
        x1 - x0, box.size.Y + 2 * c, box.size.Z + 2 * c
    )


@functools.cache
def _knockout_skin(thickness):
    """Follow the back contour with a constant horizontal wall thickness."""
    # The local import avoids the back-form/cell/battery-corridor dependency cycle.
    from .backform import back_form

    opening = qwiic_slot().bounding_box()
    outer = _profiles()[1].bounding_box().min.X
    local = Pos(outer + params.WALL / 2, opening.center().Y, opening.center().Z) * Box(
        params.WALL + 2 * MERGE,
        opening.size.Y + 2 * (params.QWIIC_KNOCKOUT_ANCHOR + MERGE),
        opening.size.Z + 2 * MERGE,
    )
    form = back_form(0, 0)
    return _cut(_isect(form, local), Pos(thickness, 0, 0) * form)


def qwiic_knockout_panel():
    """Return a flush panel that follows the back's outer contour."""
    opening = qwiic_slot().bounding_box()
    outer = _profiles()[1].bounding_box().min.X
    gap = params.QWIIC_KNOCKOUT_GAP
    blank = Pos(outer + params.WALL / 2, opening.center().Y, opening.center().Z) * Box(
        params.WALL + 2 * MERGE,
        opening.size.Y - 2 * gap,
        opening.size.Z - 2 * gap,
    )
    return _isect(blank, _knockout_skin(params.QWIIC_KNOCKOUT_T))


def qwiic_knockout_tabs():
    """Return two side bridges at the panel's first print layers."""
    panel = qwiic_knockout_panel().bounding_box()
    opening = qwiic_slot().bounding_box()
    overlap = params.QWIIC_KNOCKOUT_ANCHOR
    out = []
    for side in (-1, 1):
        edge = panel.min.Y if side < 0 else panel.max.Y
        wall = opening.min.Y if side < 0 else opening.max.Y
        y0, y1 = sorted((edge - side * overlap, wall + side * overlap))
        outer = _profiles()[1].bounding_box().min.X
        blank = Pos(outer + params.WALL / 2, (y0 + y1) / 2,
                    panel.min.Z + params.QWIIC_KNOCKOUT_TAB_W / 2) * Box(
            params.WALL + 2 * MERGE, y1 - y0, params.QWIIC_KNOCKOUT_TAB_W
        )
        out.append(_isect(blank, _knockout_skin(params.QWIIC_KNOCKOUT_TAB_T)))
    return out


def qwiic_knockout_removal():
    """Remove the panel and free bridge spans, while wall anchors remain."""
    panel = qwiic_knockout_panel().bounding_box()
    opening = qwiic_slot().bounding_box()
    # A small normal extension removes coincident panel faces, but no cavity wall.
    tolerance = 0.01
    main = Pos(panel.center()) * Box(
        panel.size.X + 2 * tolerance,
        panel.size.Y + 2 * tolerance,
        panel.size.Z + 2 * tolerance,
    )
    cuts = [main]
    for tab in qwiic_knockout_tabs():
        box = tab.bounding_box()
        y0 = max(box.min.Y, opening.min.Y - tolerance)
        y1 = min(box.max.Y, opening.max.Y + tolerance)
        cuts.append(Pos(box.center().X, (y0 + y1) / 2, box.center().Z) * Box(
            box.size.X + 2 * tolerance, y1 - y0, box.size.Z + 2 * tolerance
        ))
    return _fuse(*cuts)
