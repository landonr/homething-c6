"""Board hold-down ledges fused to the front shell's long side walls.

The back shell's support ledges carry the board from below. These mirror them
from above: a flat underside at the board's top face, near the grip end, that
keeps the board down on the back ledges. They are the same blank, cut by the
same kind of obstacle break, so the two rows share their rules.
"""

import math

from build123d import Plane, Pos, mirror

import board
import params

from .shape import _cut, _fuse
from .stack import BOARD_TOP, CAVITY_FRONT, MERGE
from .support import _break_box, _ledge_blank, ledge_breaks

LEDGE_OUTER = params.BOARD_FIT + MERGE
"""How far past the board edge a ledge reaches into the wall, MERGE beyond the
cavity wall's own face so it fuses."""


def front_ledge_bottom():
    """Z of the flat bearing underside."""
    return BOARD_TOP + params.FRONT_LEDGE_GAP


def front_ledge_height():
    """Z span from the bearing plane to the ceiling the wedge is kept under."""
    return CAVITY_FRONT + MERGE - front_ledge_bottom()


def front_ledge_window():
    """(y0, y1) the ledges are kept to: the grip end of the board."""
    box = board.board_profile().bounding_box()
    return box.min.Y, box.min.Y + params.FRONT_LEDGE_REACH


def _v2_bodies():
    """Every V2 part body that exists as a 3D solid, at its V2 placement and
    dropped to the V2 board's own height. A part with no body in either board
    is left to its courtyard."""
    out = []
    for ref in sorted(set(board.components()) & set(board.legacy_components())):
        try:
            solids = board.legacy_part_solids(ref)
        except ValueError:
            continue
        out.extend((ref, Pos(0, 0, -params.SUPPORT_GAP) * solid) for solid in solids)
    return out


def front_ledge_obstacles(clearance=params.SUPPORT_CLEARANCE):
    """[(name, solid)] breaks over the ledge: every top courtyard, every
    assembly solid that stands above the bearing plane, and every V2 body that
    does. Named for the part, so a check or a feature id points at the board."""
    bottom = front_ledge_bottom()
    z0 = BOARD_TOP - MERGE
    z1 = CAVITY_FRONT + MERGE
    items = []
    for ref, (x0, y0, x1, y1, side) in board.courtyards().items():
        if side == "top":
            items.append((ref, x0, y0, x1, y1, None))
    for index, solid in enumerate(board.assembly_solids(), 1):
        box = solid.bounding_box()
        if box.max.Z <= bottom + 1e-6:
            continue
        items.append((f"part solid {index}", box.min.X, box.min.Y, box.max.X, box.max.Y, None))
    for ref, solid in _v2_bodies():
        box = solid.bounding_box()
        if box.max.Z <= bottom + 1e-6:
            continue
        items.append((f"V2 {ref}", box.min.X, box.min.Y, box.max.X, box.max.Y, None))
    return ledge_breaks(items, params.BOARD_FIT, z0, z1, clearance)


def _blank():
    """The back's ledge blank turned over: flat underside at the bearing
    plane, the sloped face on the ceiling side."""
    return Pos(0, 0, front_ledge_bottom()) * mirror(_ledge_blank(LEDGE_OUTER), about=Plane.XY)


def front_ledge_fragments():
    """Surviving obstacle-cut pieces in the window, short ones included."""
    cut = _cut(_blank(), *(solid for _, solid in front_ledge_obstacles()))
    box = board.board_profile().bounding_box()
    y0, y1 = front_ledge_window()
    z0 = front_ledge_bottom() - MERGE
    z1 = front_ledge_bottom() + front_ledge_height()
    bearing = params.SUPPORT_BEARING
    out = []
    for x0, x1 in (
        (box.min.X - LEDGE_OUTER, box.min.X + bearing),
        (box.max.X - bearing, box.max.X + LEDGE_OUTER),
    ):
        clip = _break_box(x0, y0, x1, y1, z0, z1)
        out.extend(cut.intersect(clip).solids())
    return out


def front_ledge_runs():
    return [
        solid
        for solid in front_ledge_fragments()
        if solid.bounding_box().size.Y >= params.SUPPORT_MIN_RUN
    ]


def front_ledges():
    """All runs as one solid to fuse into the front shell, or None."""
    runs = front_ledge_runs()
    return _fuse(*runs) if runs else None
