"""Boolean and prism primitives shared across features.

The _fuse/_cut/_isect discipline lives here because every builder in the
package depends on it: build123d's operators hand back compounds and
ShapeLists that a later boolean silently throws away, and each of these three
is the version that stays one solid.
"""

import math

from build123d import (
    BuildLine,
    BuildSketch,
    Cone,
    Cylinder,
    Face,
    Kind,
    Polyline,
    Pos,
    RectangleRounded,
    extrude,
    make_face,
)

import board
import params


def _offset_face(distance):
    edge = board.board_profile().outer_wire()
    return Face(edge.offset_2d(distance, kind=Kind.INTERSECTION))


def _profiles():
    return _offset_face(params.BOARD_FIT), _offset_face(params.BOARD_FIT + params.WALL)


def _fuse(*shapes):
    """Union that stays one solid. The `+` operator leaves touching solids as a
    compound, and a later boolean against a compound silently discards most of it."""
    body = shapes[0]
    for shape in shapes[1:]:
        body = body.fuse(shape)
    return body.clean()


def _cut(body, *shapes):
    """Subtract one at a time. Cutting with a compound of disjoint solids leaves
    the cut volumes behind as inverted solids."""
    for shape in shapes:
        body = body.cut(shape)
    return body.clean()


def _isect(a, b):
    """Intersection, as one solid. `&` hands back a ShapeList."""
    return a.intersect(b).solids()[0]


def _slab(face, z0, z1):
    # dir is explicit: the profile comes off the board's bottom face, whose normal
    # points down, and extrude follows the normal.
    return Pos(0, 0, z0) * extrude(face, amount=z1 - z0, dir=(0, 0, 1))


def _ring(inner, outer, z0, z1):
    """A profile-offset band, with overlap available at either boundary."""
    return _cut(
        _slab(_offset_face(outer), z0, z1),
        _slab(_offset_face(inner), z0 - 1, z1 + 1),
    )


def _hole(x, y, diameter, z0, z1):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(radius=diameter / 2, height=z1 - z0)


def _chamfered_post(x, y, diameter, z0, z1, size, root, root_z=None):
    """Make a round post with a chamfer widest at its lower or upper root."""
    if root not in {"lower", "upper"}:
        raise ValueError(f"unknown post root: {root}")
    if size <= 0 or 2 * size >= z1 - z0:
        raise ValueError("post chamfer must be positive and shorter than half the post")

    root_z = (z0 if root == "lower" else z1) if root_z is None else root_z
    if not z0 <= root_z <= z1:
        raise ValueError("post root must be inside the post")
    post_r = diameter / 2
    chamfer_z = root_z + size / 2 if root == "lower" else root_z - size / 2
    chamfer = Pos(x, y, chamfer_z) * Cone(
        bottom_radius=post_r + size if root == "lower" else post_r,
        top_radius=post_r if root == "lower" else post_r + size,
        height=size,
    )
    return _fuse(_hole(x, y, diameter, z0, z1), chamfer)


def _rounded_prism(x, y, size, radius, z0, z1):
    sketch = Pos(x, y, z0) * RectangleRounded(size, size, radius)
    return extrude(sketch, amount=z1 - z0, dir=(0, 0, 1))


def _squircle_points(cx, cy, ax, ay, n, count):
    """Closed point set on the superellipse |dx/ax|^n + |dy/ay|^n = 1, from the
    standard parameterisation x = ax |cos t|^(2/n) sgn(cos t).

    Here rather than in either caller because both the keypad recesses and the
    keycaps are drawn on it and they have to agree: a cap sitting in a dished
    face reads as the same family of shape only if it is literally the same
    curve.
    """
    out = []
    for i in range(count):
        t = 2 * math.pi * i / count
        c, s = math.cos(t), math.sin(t)
        out.append(
            (
                cx + ax * math.copysign(abs(c) ** (2 / n), c),
                cy + ay * math.copysign(abs(s) ** (2 / n), s),
            )
        )
    return out


def _squircle_prism(x, y, size, n, count, z0, z1):
    """A square-aspect superellipse prism: the keycap plan shape, and the two
    holes in the face that a cap passes through.

    Square aspect because a keytop is square, so one size is the whole shape.
    The two holes are the same curve at different sizes rather than offsets of
    it, which is what keeps CAP_FLANGE_OVERLAP and CAP_FLANGE_CLEARANCE meaning
    what they say: concentric similar superellipses sit their stated distance
    apart on the axes, and nowhere around the curve are they closer than that,
    so the axis figure is the worst case exactly as it was for a rounded
    square.
    """
    half = size / 2
    with BuildSketch() as sketch:
        with BuildLine():
            Polyline(*_squircle_points(x, y, half, half, n, count), close=True)
        make_face()
    return _slab(sketch.sketch.faces()[0], z0, z1)
