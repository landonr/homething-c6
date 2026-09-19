"""Tolerances and probe helpers every check module shares."""

from build123d import Cylinder, Edge, Pos, Vector

TOLERANCE = 0.05
PROBE_D = 0.5
RUN_MIN = 1e-3
"""Shortest run of material _ray_runs keeps. A ray grazing a wall tangentially
leaves a piece far shorter than any printed feature, and one of those between
two real runs reads as a boundary that is not there."""


def _point(value):
    """A case-frame point out of a Vector, a shape's centre, or three numbers."""
    if value is None:
        return None
    if hasattr(value, "center"):
        value = value.center()
    if hasattr(value, "X"):
        value = (value.X, value.Y, value.Z)
    return [round(float(v), 3) for v in value]


def _bounds(value):
    """A case-frame box as [x0, y0, z0, x1, y1, z1], out of a shape, a bounding
    box, or the six numbers themselves. A probe is the usual argument: it is the
    volume the pass actually read, so it is the volume worth drawing."""
    if value is None:
        return None
    if hasattr(value, "bounding_box"):
        value = value.bounding_box()
    if hasattr(value, "min"):
        value = (value.min.X, value.min.Y, value.min.Z,
                 value.max.X, value.max.Y, value.max.Z)
    return [round(float(v), 3) for v in value]


class Problem(str):
    """One failure line that also says where on the model it is.

    A str subclass, so a pass goes on appending and printing lines exactly as it
    did and only the lines worth pointing at have to be upgraded: a plain string
    still reports, it just cannot be drawn. The location is in the case frame,
    the frame case/export/c6remote-features.json is written in, so the viewer can
    draw it against the geometry and a reader can paste it into the viewer's
    Focus box unchanged.

    `at` is the spot a reading was taken at and `box` the volume it spanned,
    which for most passes is the probe itself; a pass gives whichever it
    measured. `part` is the export file's stem, for a failure that belongs to a
    whole part rather than to a place on one.
    """

    def __new__(cls, text, at=None, box=None, part=None):
        self = super().__new__(cls, text)
        self.at = _point(at)
        self.box = _bounds(box)
        self.part = part
        return self

    def as_dict(self):
        out = {"text": str(self)}
        for key in ("at", "box", "part"):
            value = getattr(self, key, None)
            if value is not None:
                out[key] = value
        return out


def _volume(shape):
    return sum(s.volume for s in shape.solids()) if shape else 0.0


def _fill_fraction(shape, probe):
    """How much of a probe's own volume is material, as a fraction rather
    than the mm3 TOLERANCE elsewhere: a narrow probe can be small enough
    that even a fully solid one reads under TOLERANCE, so an absolute floor
    cannot tell blocked from open for it. A fraction scales with whatever
    probe asks it, so it stays meaningful regardless."""
    probe_volume = _volume(probe)
    if probe_volume <= 0:
        return 0.0
    return _volume(shape.intersect(probe)) / probe_volume


def _ray_runs(shape, start, end):
    """Where `shape` is material along the segment from `start` to `end`, as
    (from, to) distances off `start`, in order.

    A probe answers "is this spot open". This answers "where does it open and
    where does it close", which is what a feature bounded by two unrelated
    surfaces needs: the gaps between the runs are the voids the built solid
    actually has along that line, so one reading covers every surface that can
    close in on the void rather than one radius chosen in advance.
    """
    line = Edge.make_line(start, end)
    hit = shape.intersect(line)
    runs = []
    for piece in hit.edges() if hit else []:
        origin = Vector(start)
        a = ((piece @ 0) - origin).length
        b = ((piece @ 1) - origin).length
        runs.append((min(a, b), max(a, b)))
    return sorted(run for run in runs if run[1] - run[0] > RUN_MIN)


OPENING_PROBE_R = 0.02
OPENING_PROBE_H = 0.05
"""Size of the tiny probe _opening_radius bisects with. Small on purpose: it
is hunting for exactly where a boolean's real opening starts, not confirming
presence or absence at a spot already known to be one or the other."""


def _opening_radius(shell, x, y, z, lo=10.0, hi=20.0, iterations=20):
    """The true radius, at (x, y, z), where `shell` stops being open and
    starts being material: a binary search on a tiny probe rather than
    trusting whatever formula was meant to produce that radius. Exists
    because of exactly this file's own history: the old ring window's face
    radius and its seat's 45 degree reach both looked right on paper while
    _wheel_hole quietly erased them, and only a probe on the built solid
    ever caught it.

    `lo`/`hi` bound the search and default to the range every wheel/ring
    radius in this model actually falls in; narrow them for a different
    feature rather than widening the iteration count to compensate.
    """
    probe_r, probe_h = OPENING_PROBE_R, OPENING_PROBE_H
    for _ in range(iterations):
        mid = (lo + hi) / 2
        probe = Pos(x + mid, y, z) * Cylinder(radius=probe_r, height=probe_h)
        if _fill_fraction(shell, probe) > 0.5:
            hi = mid
        else:
            lo = mid
    return hi
