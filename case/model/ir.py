"""U2's bottom window insert and D1's unchanged +Y emitter bore."""

import functools

from build123d import Cylinder, Pos, RectangleRounded, Rot, extrude

import board
import cache
import params

from .backform import back_form
from .shape import _cut, _fuse, _isect
from .stack import BOARD_TOP, LAP_OUT, SHELL_BACK


@functools.cache
def ir_window_span():
    """(x0, x1, y0, y1) of U2's -Z aperture in the back floor.

    U2 is multi-solid: body and four leads all count. A fixed-radius read keeps
    the complete package together before IR_CLEARANCE pads its plan envelope.
    """
    ir = board.part_envelope("U2", radius=3.0)
    c = params.IR_CLEARANCE
    return ir.min.X - c, ir.max.X + c, ir.min.Y - c, ir.max.Y + c


def _bottom_prism(expand=0.0):
    """Rounded vertical prism around the aperture, expanded on every plan side."""
    x0, x1, y0, y1 = ir_window_span()
    sketch = Pos((x0 + x1) / 2, (y0 + y1) / 2, SHELL_BACK - 10) * RectangleRounded(
        x1 - x0 + 2 * expand,
        y1 - y0 + 2 * expand,
        max(params.IR_WINDOW_R + expand, 0.1),
    )
    return extrude(sketch, amount=BOARD_TOP - SHELL_BACK + 20, dir=(0, 0, 1))


def _surface_layer(expand, low, high):
    """Plan-limited layer between two offsets of the built back outer form."""
    body = _isect(_bottom_prism(expand), back_form(0, low, params.EDGE_R_BACK))
    return _cut(body, back_form(0, high, params.EDGE_R_BACK))


def ir_window_opening():
    """U2's nominal rounded aperture through the back floor along -Z."""
    return _bottom_prism()


def ir_window_rebate():
    """Inside relief for flange, stopping one pane thickness above exterior.

    The larger relief exposes a conformal shoulder around the aperture. Insert
    flange lands on that shoulder from inside, with IR_WINDOW_FIT around its
    outer edge for adhesive.
    """
    outer = _bottom_prism(params.IR_WINDOW_FLANGE + params.IR_WINDOW_FIT)
    return _isect(outer, back_form(0, params.IR_WINDOW_T, params.EDGE_R_BACK))


@cache.solid
def ir_window():
    """Exterior-flush stepped insert, installed through back shell from inside.

    Pane follows the actual back-form surface and carries IR_WINDOW_PRESS into
    aperture on every side. Interior flange is an open ring: optical centre
    crosses only IR_WINDOW_T, while ring supplies outward retention and adhesive
    land on shell shoulder.
    """
    pane = _surface_layer(params.IR_WINDOW_PRESS, 0, params.IR_WINDOW_T)
    flange = _surface_layer(
        params.IR_WINDOW_FLANGE,
        params.IR_WINDOW_T,
        params.IR_WINDOW_T + params.IR_WINDOW_FLANGE_T,
    )
    flange = _cut(flange, _bottom_prism(-0.5))
    return _fuse(pane, flange)


def ir_window_retention():
    """Flange left outside pane's press band, per side."""
    return params.IR_WINDOW_FLANGE - params.IR_WINDOW_PRESS


def emitter_bore():
    """D1's unchanged round port through the +Y end wall."""
    lens = board.emitter_envelope()
    edge_y = board.board_profile().bounding_box().max.Y
    radius = max(lens.size.X, lens.size.Z) / 2 + params.IR_EMITTER_FIT
    y_in = edge_y - params.IR_RELIEF_DEPTH
    y_out = edge_y + params.WALL * 6
    return Pos(lens.center().X, (y_in + y_out) / 2, lens.center().Z) * Rot(90, 0, 0) * (
        Cylinder(radius=radius, height=y_out - y_in)
    )


def emitter_reach():
    """How far D1's lens stops short of +Y exterior face."""
    edge_y = board.board_profile().bounding_box().max.Y
    return (edge_y + LAP_OUT) - board.emitter_envelope().max.Y
