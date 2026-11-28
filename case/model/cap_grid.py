"""Print carrier for the rigid caps, blank or with the marks cut for a paint fill."""

import math

from build123d import Align, Axis, Box, Polygon, Pos, Rot, extrude, fillet

import board
import cache
import params

from .cap_marks import fitted_mark, flat_faces_at, safe_area
from .caps import cap_flange, cap_refs, keycap
from .shape import _fuse, _slab
from .stack import CAP_BOTTOM, MERGE, cap_top


def _round_frame(frame):
    bounds = frame.bounding_box()
    vertical_edges = frame.edges().filter_by(Axis.Z)
    corners = [
        edge for edge in vertical_edges
        if any(math.isclose(edge.center().X, x) for x in (bounds.min.X, bounds.max.X))
        and any(math.isclose(edge.center().Y, y) for y in (bounds.min.Y, bounds.max.Y))
    ]

    # The low-Y corner in print orientation is upper left after flipping about X.
    def at_index_corner(edge):
        center = edge.center()
        return math.isclose(center.X, bounds.min.X) and math.isclose(center.Y, bounds.min.Y)

    frame = fillet(
        [edge for edge in corners if not at_index_corner(edge)],
        params.CAP_GRID_CORNER_R,
    )
    index_corner = next(edge for edge in frame.edges().filter_by(Axis.Z) if at_index_corner(edge))
    return fillet(index_corner, params.CAP_GRID_INDEX_R)


def keycap_grid_layout():
    """Return the pitch and (ref, x, y) centers in print coordinates."""
    refs = cap_refs()
    columns = params.CAP_GRID_COLUMNS
    refs += [refs[-1]] * (-len(refs) % columns)
    pitch = max(map(cap_flange, refs)) + params.CAP_GRID_RAIL_W + 2 * params.CAP_GRID_GAP
    slots = []
    for index, ref in enumerate(refs):
        row, column = divmod(index, columns)
        slots.append((ref, column * pitch, row * pitch))
    return pitch, slots


@cache.solid
def keycap_grid():
    """Place the blank faces on the build plane in switch order, then add spares."""
    pitch, slots = keycap_grid_layout()
    columns = params.CAP_GRID_COLUMNS
    rows = len(slots) // columns
    refs = [ref for ref, _, _ in slots]
    flange_width = max(map(cap_flange, refs))
    rail_width = params.CAP_GRID_RAIL_W
    end_width = params.CAP_GRID_END_RAIL_W
    tab_thickness = params.CAP_GRID_TAB_T
    tab_width = params.CAP_GRID_TAB_W
    rail_x = [(column - 0.5) * pitch for column in range(columns + 1)]
    rail_height = max(cap_top(ref) for ref in refs) - CAP_BOTTOM
    base_align = (Align.CENTER, Align.CENTER, Align.MIN)

    end_reach = flange_width / 2 + params.CAP_GRID_END_GAP + end_width
    frame_length = (rows - 1) * pitch + 2 * end_reach
    rails = [
        Pos(x, (rows - 1) * pitch / 2, 0)
        * Box(rail_width, frame_length, rail_height, align=base_align)
        for x in rail_x
    ]
    end_center = end_reach - end_width / 2
    rails.extend(
        Pos((columns - 1) * pitch / 2, y, 0)
        * Box(columns * pitch + rail_width, end_width, rail_height, align=base_align)
        for y in (-end_center, (rows - 1) * pitch + end_center)
    )
    frame = _round_frame(_fuse(*rails))
    tabs = []
    caps = []
    placements = board.components()
    for index, (ref, x, y) in enumerate(slots):
        column = index % columns
        board_x, board_y = placements[ref][:2]
        top = cap_top(ref)
        caps.append(
            Pos(x, y, top) * Rot(180, 0, 0) * Pos(-board_x, -board_y, 0)
            * keycap(ref, legend=False)
        )
        # Keep both ends of the tab below the pad contact face and above the guide.
        tab_z = top - CAP_BOTTOM - (params.CAP_FLANGE_T + tab_thickness) / 2
        for side, rail in ((-1, rail_x[column]), (1, rail_x[column + 1])):
            edge = x + side * cap_flange(ref) / 2
            inner = edge - side * MERGE
            outer = rail - side * (rail_width / 2 - MERGE)
            tab = Polygon(
                (inner, y - tab_width / 2),
                (edge, y - tab_width / 2),
                (outer, y - tab_width),
                (outer, y + tab_width),
                (edge, y + tab_width / 2),
                (inner, y + tab_width / 2),
                align=None,
            )
            tabs.append(_slab(tab, tab_z, tab_z + tab_thickness))

    grid = _fuse(frame, *tabs, *caps)
    if len(grid.solids()) != 1 or not grid.is_valid:
        raise ValueError("Breakaway keycap grid must be one valid solid")
    return grid


@cache.solid
def keycap_grid_legends():
    """Cut the marking artwork CAP_GRID_LEGEND_DEPTH into the grid's cap faces.

    The marks are fitted in the face-up view of the marking export, then mapped
    back to the print orientation, so the cuts match the artwork and the spare
    keeps its diamond.
    """
    grid = keycap_grid()
    bounds = grid.bounding_box()
    face_up = Pos(-bounds.min.X, bounds.min.Y) * Rot(180, 0, 0)
    to_print = face_up.inverse()
    flat_faces = flat_faces_at(grid, 0)
    _, slots = keycap_grid_layout()
    cutters = []
    seen = set()
    for ref, x, y in slots:
        area = face_up * safe_area(flat_faces, x, y, ref)
        center = Pos(x - bounds.min.X, -(y - bounds.min.Y))
        for face in fitted_mark(ref, ref in seen, center, area):
            cutters.append(extrude(
                Pos(0, 0, -MERGE) * (to_print * face),
                amount=MERGE + params.CAP_GRID_LEGEND_DEPTH,
                dir=(0, 0, 1),
            ))
        seen.add(ref)
    marked = grid.cut(*cutters)
    if len(marked.solids()) != 1 or not marked.is_valid:
        raise ValueError("Legend keycap grid must be one valid solid")
    return marked
