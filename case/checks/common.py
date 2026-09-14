"""Tolerances and probe helpers every check module shares."""

from build123d import Cylinder, Pos

TOLERANCE = 0.05
PROBE_D = 0.5


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
