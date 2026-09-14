"""Aperture probes: a hole that never got cut. A switch tops out well below the
ceiling, so a missing button hole collides with nothing and interference alone
stays quiet.
"""

from build123d import Cylinder, Pos

import board
import case

from .common import PROBE_D, TOLERANCE, _volume


def _apertures():
    """(name, x, y, z0, z1), where z0..z1 is the surface the hole must pierce."""
    through_roof = (case.CAVITY_FRONT - 0.1, case.SHELL_FRONT + 1)
    through_floor = (case.SHELL_BACK - 1, case.CAVITY_BACK + 0.1)

    parts = board.components()
    yield ("wheel", *board.wheel_center(), *through_roof)
    for ref in board.refs("SW"):
        yield (ref, *parts[ref][:2], *through_roof)

    # The mic hears through the board, so its inlet pierces the front, at the
    # board's own port hole rather than at the package centre. U2 receives
    # through the back floor on -Z; the broad z probe reaches its local tapered
    # floor rather than assuming CAVITY_BACK exists there. D1 and USB pierce
    # end walls on another axis and are checked in checks.ir.
    yield ("mic port", *case.mic_port(), *through_roof)
    u2 = board.part_envelope("U2", radius=3.0)
    yield ("U2", u2.center().X, u2.center().Y, case.SHELL_BACK - 1, case.BOARD_TOP)


def probe_apertures(shells):
    blocked = []
    for name, x, y, z0, z1 in _apertures():
        probe = Pos(x, y, (z0 + z1) / 2) * Cylinder(
            radius=PROBE_D / 2, height=z1 - z0
        )
        hit = shells.intersect(probe)
        volume = _volume(hit)
        if volume > TOLERANCE:
            blocked.append((name, volume))
    return blocked
