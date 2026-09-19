"""Tolerances and probe helpers every check module shares."""

from build123d import Box, Compound, Cylinder, Edge, Pos, Vector

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


CROP_MARGIN = 0.5
"""How far outside the probes a crop reaches, on every axis. Slack for the
bounding boxes a boolean reports, which are conservative rather than tight, and
not a working allowance: nothing is ever read out here. Wide enough that no
probe is refused over a rounding difference, narrow enough that the crop stays
a handful of faces rather than a district of the shell."""


class _Crop:
    """A large solid cut down to the neighbourhood of the probes about to be
    read against it, so each of those readings costs a boolean against a handful
    of faces instead of against the whole shell.

    Why this exists. _fill_fraction intersects a probe well under a millimetre
    across with the entire front shell, ten thousand faces including a lofted
    keypad recess, and OCC boolean cost follows the face count of both operands,
    so every tiny reading pays for the whole shell whatever it is actually
    looking at. A pass that bisects, or that walks the ring angle by angle, pays
    that dozens of times over for readings that all live inside one small box.
    Cut the box out once, at the price of a single boolean, and every reading
    inside it is two orders of magnitude cheaper.

    The invariant, and it is absolute: every probe read against a crop must lie
    wholly inside the box the crop was cut from. Material outside that box is
    not in the crop at all, so a probe straying past a wall of it reads as open
    no matter what the shell does out there, and a probe that cannot see
    material is exactly the vacuous pass this model has shipped before.
    Containment is therefore checked on every single reading rather than
    reasoned about once, and a violation raises instead of returning a number
    the crop cannot stand behind: a pass that dies is fixable, a pass that lies
    is not.

    Crops nest. `source` may be another _Crop instead of a solid, and cutting
    out of one is how a pass that reads many neighbouring spots stops paying for
    the whole shell at every one: the parent is cut once out of the shell, and
    each child is then cut out of the few hundred faces the parent holds rather
    than out of ten thousand. Nesting carries its own half of the invariant,
    because a child cannot hold material its parent had already discarded and
    would report its own box as its bounds while missing it. So a child is
    refused unless its parent wholly covers it, the same check and the same
    refusal the probes get.
    """

    def __init__(self, source, lo, hi):
        self.lo = tuple(float(v) for v in lo)
        self.hi = tuple(float(v) for v in hi)
        if isinstance(source, _Crop):
            if not source._inside(self.lo, self.hi):
                source._refuse("child crop", self.lo, self.hi)
            source = source.shape
        if source is None:
            self.shape = None
            return
        centre = [(a + b) / 2 for a, b in zip(self.lo, self.hi)]
        size = [b - a for a, b in zip(self.lo, self.hi)]
        cut = source.intersect(Pos(*centre) * Box(*size))
        # A boolean hands back a list of shapes rather than one. Nothing but a
        # Shape answers intersect(), so the pieces are gathered into a compound;
        # an empty result means no material in the box at all, which every
        # reading below treats as open, exactly as the uncropped shell would.
        pieces = list(cut) if hasattr(cut, "__iter__") else ([cut] if cut else [])
        self.shape = Compound(pieces) if pieces else None

    def _inside(self, lo, hi):
        return all(self.lo[i] <= lo[i] and hi[i] <= self.hi[i] for i in range(3))

    def _refuse(self, what, lo, hi):
        raise RuntimeError(
            f"{what} escapes its crop: it spans {_bounds(tuple(lo) + tuple(hi))} "
            f"and the crop holds only {_bounds(self.lo + self.hi)}. Outside the "
            "crop there is no material to find, so the reading would come back "
            "open whatever the shell does there. Widen the crop; do not trust "
            "the number."
        )

    def fill_fraction(self, probe):
        """_fill_fraction against the crop, refusing any probe the crop does not
        wholly contain."""
        box = probe.bounding_box()
        lo = (box.min.X, box.min.Y, box.min.Z)
        hi = (box.max.X, box.max.Y, box.max.Z)
        if not self._inside(lo, hi):
            self._refuse("probe", lo, hi)
        if self.shape is None:
            return 0.0
        return _fill_fraction(self.shape, probe)

    def ray_runs(self, start, end):
        """_ray_runs against the crop, refusing any segment the crop does not
        wholly contain. A segment leaving the box would come back clipped at the
        box wall, which reads as the shell closing where it does not."""
        lo = tuple(min(a, b) for a, b in zip(start, end))
        hi = tuple(max(a, b) for a, b in zip(start, end))
        if not self._inside(lo, hi):
            self._refuse("ray", lo, hi)
        if self.shape is None:
            return []
        return _ray_runs(self.shape, start, end)


OPENING_PROBE_R = 0.02
OPENING_PROBE_H = 0.05
"""Size of the tiny probe _opening_radius bisects with. Small on purpose: it
is hunting for exactly where a boolean's real opening starts, not confirming
presence or absence at a spot already known to be one or the other."""


OPENING_SEARCH_LO = 10.0
OPENING_SEARCH_HI = 20.0
"""Default bounds of _opening_radius' search, the range every wheel and ring
radius in this model actually falls in. Named rather than left as bare defaults
so that a caller cutting a crop for a bisection it leaves at the default can say
which span it cropped over instead of repeating the number and letting the two
drift apart."""


class OpeningNotFound(RuntimeError):
    """_opening_radius' bisection never met material, so it has no radius to
    report.

    The search narrows on the radius where a shell stops being open, and the
    only thing that narrows it is a probe reading material: every probe that
    reads open pushes the low end out, and if none of them ever reads material
    the search ends with the upper bound it started with and hands that bound
    back. That number measures nothing. It is what an opening genuinely wider
    than the bound looks like, and equally what a feature that was never built
    looks like, and what any height where there is no material on the ray at all
    looks like. A caller comparing it against a requirement smaller than the
    bound reads all three as a generous pass, so a bisection that failed becomes
    a check that cannot fail whatever the geometry does. That is the worst
    defect a pass here can have, and wheel_seat_clearance shipped it for two of
    its five heights: both returned the bound exactly and neither could be made
    to fail by breaking the opening.

    Raised rather than returned as a sentinel for the same reason _Crop refuses
    a probe it cannot contain rather than returning zero: a sentinel puts the
    burden on every caller of a shared helper to remember it exists, and the one
    that forgets goes quiet rather than loud. A caller with something better to
    say about its own feature catches this and reports that reading as a
    failure; one without stops the pass, which is a state somebody fixes.
    """


def _opening_crop(shell, x, y, z_lo, z_hi, lo=OPENING_SEARCH_LO,
                  hi=OPENING_SEARCH_HI, margin=CROP_MARGIN):
    """A _Crop holding every probe an _opening_radius bisection can ever place,
    for a column of sites sharing (x, y) with centre heights anywhere between
    `z_lo` and `z_hi`, all searching between `lo` and `hi`.

    The bisection narrows its interval but never leaves it, and its probe only
    ever stands on the +x ray out of the site, so the whole search lives inside
    the box that span sweeps out once the probe's own radius and half height are
    added. Cropping over the span rather than per iteration is the whole point:
    one expensive boolean buys twenty cheap ones. One crop serves a whole column
    of sites as readily as one, so a pass walking heights up a single feature
    pays for it once.
    """
    return _Crop(
        shell,
        (x + lo - OPENING_PROBE_R - margin,
         y - OPENING_PROBE_R - margin,
         z_lo - OPENING_PROBE_H / 2 - margin),
        (x + hi + OPENING_PROBE_R + margin,
         y + OPENING_PROBE_R + margin,
         z_hi + OPENING_PROBE_H / 2 + margin),
    )


def _opening_radius(shell, x, y, z, lo=OPENING_SEARCH_LO,
                    hi=OPENING_SEARCH_HI, iterations=20, crop=None):
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

    The bisection reads against a _Crop of the shell over its whole search span,
    not against the shell itself. Twenty booleans against the built front cost
    most of a minute; the same twenty against the handful of faces inside the
    span cost almost nothing, for the price of the one boolean that cuts the
    span out. `crop` passes a crop in when a caller has several sites in the
    same column and would rather pay that price once for all of them. It has to
    contain every probe this call will place, which _opening_crop is what builds
    and which the crop itself re-checks on every single reading.

    Raises OpeningNotFound if no probe anywhere in the search ever read
    material, which is the one outcome the returned number cannot describe: see
    that exception for what it costs to hand the bound back instead. The other
    end needs no such guard, because it fails safe on its own. Material filling
    the search all the way down to `lo` walks `hi` down to `lo` and returns it,
    and `lo` is under every radius this model asks for, so a bore that closed
    entirely reports a uselessly small opening rather than a generous one.
    """
    region = crop if crop is not None else _opening_crop(shell, x, y, z, z, lo, hi)
    floor, bound = lo, hi
    probe_r, probe_h = OPENING_PROBE_R, OPENING_PROBE_H
    for _ in range(iterations):
        mid = (lo + hi) / 2
        probe = Pos(x + mid, y, z) * Cylinder(radius=probe_r, height=probe_h)
        if region.fill_fraction(probe) > 0.5:
            hi = mid
        else:
            lo = mid
    if hi == bound:
        raise OpeningNotFound(
            f"no material anywhere between r={floor:.2f} and r={bound:.2f} on the "
            f"+x ray from ({x:.2f}, {y:.2f}) at z={z:.2f}: the bisection never "
            "met the wall it was sent to find, so the only radius it could "
            f"return is the {bound:.2f} bound it started from. That is not an "
            "opening of that radius, it is no reading at all. Probe where the "
            "feature has material, or widen the bound; do not compare the "
            "bound against a requirement."
        )
    return hi
