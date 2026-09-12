"""The two shells and their joint features: the front skirt, the deep catch
section, the back lap, and the detents.
"""

from build123d import (
    Box,
    Plane,
    Pos,
    Rectangle,
    RectangleRounded,
    extrude,
    fillet,
    loft,
)

import board
import cache
import params

from .backform import back_form
from .caps import _key_prism, cap_counterbore, cap_face_hole
from .hardware import (
    closure_cuts,
    legacy_retention_pilot,
    legacy_retention_post,
    mount_points,
    shell_standoff,
)
from .support import front_support_cuts, support_runs
from .ir import emitter_bore, ir_window_opening, ir_window_rebate
from .keypad import keypad_recess
from .mic import mic_bore, mic_duct
from .shape import (
    _cut,
    _chamfered_post,
    _fuse,
    _hole,
    _isect,
    _offset_face,
    _profiles,
    _ring,
    _slab,
)
from .stack import (
    BOARD_TOP,
    CAVITY_FRONT,
    COUNTERBORE_TOP,
    LAP_IN,
    LAP_OUT,
    MERGE,
    SHELL_BACK,
    SHELL_FRONT,
    SKIRT_BOTTOM,
    SKIRT_OUT,
)
from .usb import usb_pocket, usb_slot
from .wheel_ring import led_ring_channel, wheel_opening


def skirt_relief():
    """What the back gives up so its lap can close over the skirt: everything its
    wall has inboard of the lap, over the skirt's height and a fit below it."""
    return [
        _ring(
            params.BOARD_FIT - 6,
            LAP_IN,
            SKIRT_BOTTOM - params.SKIRT_FIT,
            BOARD_TOP + 1,
        )
    ]


def skirt_cuts():
    """What turns the front's wall below the parting plane into the skirt: the
    cavity carried down past it, and everything outboard of the skirt, which is
    the space the back's lap closes into."""
    return [
        _slab(_offset_face(params.BOARD_FIT), SKIRT_BOTTOM - 1, BOARD_TOP),
        _ring(SKIRT_OUT, LAP_OUT + 6, SKIRT_BOTTOM - 1, BOARD_TOP),
    ]


DEEP_BOTTOM = BOARD_TOP - params.CATCH_SKIRT_H
"""How far the skirt reaches at the grip end."""

CATCH_Z0 = DEEP_BOTTOM + params.CATCH_RISE
"""Bottom of each window, and so the top of the skirt that catches under a detent."""


def catch_region():
    """Limits the deepened skirt to the grip end."""
    box = board.board_profile().bounding_box()
    y0 = box.min.Y - params.BOARD_FIT - params.WALL
    return Pos(box.center().X, y0 + params.CATCH_SPAN / 2, 0) * Box(
        300, params.CATCH_SPAN, 300
    )


def catch_x():
    cx = board.board_profile().bounding_box().center().X
    return [cx - params.CATCH_SPACING / 2, cx + params.CATCH_SPACING / 2]


def deep_skirt():
    """The skirt carried further down, at the grip end only."""
    return _isect(
        _ring(params.BOARD_FIT, SKIRT_OUT, DEEP_BOTTOM, SKIRT_BOTTOM + MERGE),
        catch_region(),
    )


def catch_windows():
    """Two rounded rectangles through the deepened skirt."""
    edge = board.board_profile().bounding_box().min.Y
    y = edge - (params.BOARD_FIT + SKIRT_OUT) / 2
    reach = (SKIRT_OUT - params.BOARD_FIT) / 2 + 0.3
    out = []
    for x in catch_x():
        plane = Plane(
            origin=(x, y, CATCH_Z0 + params.CATCH_H / 2),
            x_dir=(1, 0, 0),
            z_dir=(0, -1, 0),
        )
        sketch = plane * RectangleRounded(params.CATCH_W, params.CATCH_H, params.CATCH_R)
        out.append(extrude(sketch, amount=reach, both=True))
    return out


def catch_relief():
    """The back's lap is hollowed out this much further down over the deepened
    section, so the longer skirt has somewhere to go."""
    return _isect(
        _ring(
            params.BOARD_FIT - 6,
            LAP_IN,
            DEEP_BOTTOM - params.SKIRT_FIT,
            SKIRT_BOTTOM,
        ),
        catch_region(),
    )


def catch_detents():
    """A wedge on the inside of the lap behind each window, thickest at its base.

    Built as the window's own profile, inset by the fit, intersected with the
    wedge. A plain rectangle lofted to a sliver is simpler and is what this was
    first: it fouled all four rounded corners and stood proud of the window's top,
    which is what the shells-mate pass reported.
    """
    edge = board.board_profile().bounding_box().min.Y
    base, tip = edge - LAP_IN - MERGE, edge - LAP_IN + params.CATCH_D
    f = params.CATCH_FIT
    z0, z1 = CATCH_Z0 + f, CATCH_Z0 + params.CATCH_H - f
    out = []
    for x in catch_x():
        plane = Plane(
            origin=(x, (base + tip) / 2, (z0 + z1) / 2), x_dir=(1, 0, 0), z_dir=(0, -1, 0)
        )
        profile = plane * RectangleRounded(
            params.CATCH_W - 2 * f, params.CATCH_H - 2 * f, max(params.CATCH_R - f, 0.2)
        )
        prism = extrude(profile, amount=(tip - base) / 2 + 1, both=True)
        wedge = loft(
            [
                Pos(x, (base + tip) / 2, z0) * Rectangle(params.CATCH_W + 2, tip - base),
                Pos(x, base + 0.05, z1) * Rectangle(params.CATCH_W + 2, 0.1),
            ],
            ruled=True,
        )
        out.append(_isect(prism, wedge))
    return out


def shared_cuts():
    """D1 and USB end-wall cuts shared by both shells, unchanged for U2's move."""
    return [usb_slot(), emitter_bore()]


@cache.solid
def back_shell():
    inner, outer = _profiles()
    form = back_form(0, 0)
    # Inset by the wall and lifted by the floor, so the shell keeps its thickness
    # around the rounded corner instead of thinning into it.
    cavity = back_form(params.WALL, params.FLOOR, params.FLOOR)

    shell = _isect(_slab(outer, SHELL_BACK, BOARD_TOP), form)
    shell = _cut(
        shell,
        _isect(_slab(inner, SHELL_BACK, BOARD_TOP + 1), cavity),
        *skirt_relief(),
    )

    # U2 receives through this shell's floor. Its opening and inside flange
    # rebate stay back-only; D1 and USB retain their shared end-wall cuts.
    shell = _cut(shell, catch_relief())
    shell = _fuse(
        shell,
        shell_standoff(),
        legacy_retention_post(),
        *support_runs(),
        *catch_detents(),
    )
    return _cut(
        shell,
        *shared_cuts(),
        ir_window_opening(),
        ir_window_rebate(),
        *closure_cuts(),
        legacy_retention_pilot(),
    )


@cache.solid
def front_shell():
    # The body is built to SHELL_FRONT and filleted there before any key or
    # wheel hole is cut into it: at this point the only top edge loop is the
    # outer perimeter, so the fillet cannot land on an aperture's own edge by
    # construction rather than by filtering for it afterwards. See back_form's
    # docstring for why a fillet cannot be trusted against a loft's own edges.
    inner, outer = _profiles()
    body = _slab(outer, SKIRT_BOTTOM, SHELL_FRONT)
    body = fillet(
        [e for e in body.edges() if e.bounding_box().min.Z > SHELL_FRONT - 0.01],
        params.EDGE_R_FRONT,
    )
    shell = _cut(body, _slab(inner, BOARD_TOP - 0.01, CAVITY_FRONT), *skirt_cuts())

    # The mic hears through the board, so the inlet is on the front. A duct down
    # to the board keeps it coupled to the board's own port hole instead of to
    # the whole cavity, and mic_bore() drills the funnel through it as one solid,
    # opening in the keypad recess's own curved floor rather than SHELL_FRONT.
    # The duct goes in solid: see mic_duct() for why it cannot be the tube it was.
    # Bosses reach SHELL_FRONT, not CAVITY_FRONT: the keypad region's own
    # ceiling is too thin now to hold BOSS_PILOT_DEPTH under it, so each
    # boss carries its own material the rest of the way to the flat face,
    # the "local pad" the USB pocket has on the void side instead. No
    # overshoot past SHELL_FRONT: the fuse already overlaps real volume
    # over the whole keypad ceiling's own depth, and going further would
    # poke the boss through the one outer face plane.
    bosses = [
        _chamfered_post(
            x,
            y,
            params.BOSS_OD,
            BOARD_TOP,
            SHELL_FRONT,
            params.STANDOFF_CHAMFER,
            "upper",
            CAVITY_FRONT,
        )
        for x, y in mount_points()
    ]
    shell = _fuse(
        shell,
        mic_duct(),
        deep_skirt(),
        *bosses,
    )
    # No local pocket for D1 any more. It sat on the front of the board once,
    # its dome standing taller than the keypad region's own ceiling; on the
    # back it clears the front shell entirely except for the leads bent up
    # through the board, which stop well under CAVITY_FRONT.
    # The support ledges cross the skirt plane to reach the back lap. Match their
    # derived breaks in the skirt so the shells can close around them.
    shell = _cut(shell, usb_pocket(), *front_support_cuts())

    parts = board.components()
    # No collar cut around the bosses. key_size() sizes each key to clear them, so
    # subtracting the collar from the hole as well only shaves a sliver off the two
    # keys that sit at the limit, and it shows as ceiling overhanging a cap.
    #
    # Every key takes two holes now: the counterbore its cap's flange rides in,
    # and the narrower hole through the face land above that. The face hole runs
    # the full depth rather than stopping at the shoulder, which is harmless
    # because it is strictly inside the counterbore.
    keys = []
    for ref in board.refs("SW"):
        x, y = parts[ref][:2]
        keys.append(
            _key_prism(x, y, cap_counterbore(ref), CAVITY_FRONT - 1, COUNTERBORE_TOP)
        )
        keys.append(
            _key_prism(x, y, cap_face_hole(ref), CAVITY_FRONT - 1, SHELL_FRONT + 1)
        )
    pilots = [
        _hole(x, y, params.BOSS_PILOT_D, BOARD_TOP - 0.1, BOARD_TOP + params.BOSS_PILOT_DEPTH)
        for x, y in mount_points()
    ]
    return _cut(
        shell,
        *pilots,
        *catch_windows(),
        wheel_opening(CAVITY_FRONT - 1, SHELL_FRONT + 1),
        led_ring_channel(),
        mic_bore(),
        *keys,
        keypad_recess(),
        *shared_cuts(),
    )
