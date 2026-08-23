"""The z stack and the derived radii every feature is built from.

One module because these are the constants the rest of the package agrees on:
the cavity ceilings and floors, the wheel's measured profile and the ring radii
that come off it, the lap and skirt planes, and MERGE. Nothing here imports
another model module, so nothing in the package can end up in an import cycle
through a constant.
"""

from pathlib import Path

import board
import params

HERE = Path(__file__).resolve().parent.parent
EXPORT = HERE / "export"

BOARD_TOP = params.BOARD_THICKNESS
CAVITY_BACK = -params.BACK_KEEPOUT
SHELL_BACK = CAVITY_BACK - params.FLOOR

SWITCH_TOP = BOARD_TOP + params.SWITCH_HEIGHT

KEYPAD_KEEPOUT = params.SWITCH_HEIGHT + params.KEYPAD_PLUNGER_STUB
"""Vertical clearance the keypad region of the ceiling actually needs: the
switch, plus KEYPAD_PLUNGER_STUB standing above it before the web begins.
FRONT_KEEPOUT was this before the face dropped, sized to the USB-C shell
rather than to anything under the keys, which is what left 1.7 of dead air
above every switch. FRONT_KEEPOUT still governs CAVITY_FRONT_USB, the one
region that still needs it."""

PAD_WEB_BOTTOM = BOARD_TOP + KEYPAD_KEEPOUT
"""Underside of the pad's web, over the keypad: SWITCH_TOP plus
KEYPAD_PLUNGER_STUB, so the plunger below it is a short, real stub rather
than a long unsupported peg standing in dead air."""

PAD_WEB_TOP = PAD_WEB_BOTTOM + params.PAD_WEB_T
CAVITY_FRONT = PAD_WEB_TOP
"""The keypad region's own cavity ceiling: the web's own top, the same
relationship CAVITY_FRONT always had to the web, just built up from the
switch now instead of down from FRONT_KEEPOUT. This is the default ceiling
height almost everything in the front shell uses; only the USB connector's
own local footprint needs CAVITY_FRONT_USB's deeper pocket instead."""

CAVITY_FRONT_USB = BOARD_TOP + params.FRONT_KEEPOUT
"""The USB connector's own local cavity ceiling, the full clearance
FRONT_KEEPOUT was always sized for. Local to its footprint now rather than
the whole shell: usb_pocket() cuts this depth only over
board.usb_envelope(), inside an outer face that stays flat everywhere at
SHELL_FRONT."""

WHEEL = board.wheel_profile()
"""ENC1's revolved profile, measured off the assembly STEP by
board.wheel_profile() rather than hand-entered. Everything below that used to
be a guess (WHEEL_TOP was BOARD_TOP + 5.75) or trusted board.WHEEL_OD blind now
reads off this instead."""

_WHEEL_OD_DISAGREEMENT = WHEEL.lip_od - board.WHEEL_OD
if abs(_WHEEL_OD_DISAGREEMENT) > 0.1:
    raise ValueError(
        f"board.WHEEL_OD is {board.WHEEL_OD:.2f} but the measured lip is "
        f"{WHEEL.lip_od:.2f}mm, {_WHEEL_OD_DISAGREEMENT:+.2f} apart: fix "
        "WHEEL_OD rather than trusting either blind"
    )

WHEEL_TOP = WHEEL.top
"""Top of ENC1's knob, measured. See WHEEL above."""
WHEEL_LIP_OD = WHEEL.lip_od
WHEEL_LIP_Z0 = WHEEL.lip_z0
WHEEL_LIP_Z1 = WHEEL.lip_z1
WHEEL_MAIN_OD = WHEEL.main_od

SHELL_FRONT = WHEEL_TOP
"""The front shell's one flat outer face: the wheel's own measured top, so
the face closes flush to the knob by construction rather than by tuning a
height constant against it. FACE_HEIGHT used to fix this independently and
left the wheel recessed under the face; deriving it means a wheel change
moves the face with it. Everything under the face is unchanged in kind: the
keypad ceiling is whatever gap this leaves over CAVITY_FRONT, and the USB
pocket's roof is whatever it leaves over CAVITY_FRONT_USB, deliberately the
thinnest ceiling anywhere (usb_pocket_clearance holds its floor)."""

KEYPAD_CEILING = SHELL_FRONT - CAVITY_FRONT
"""Ceiling actually left over the keypad, now that SHELL_FRONT is fixed
and CAVITY_FRONT is not: a derived report value rather than a tunable
input, the inverse of how the two used to relate."""

CAP_TOP = SHELL_FRONT + params.CAP_PROTRUSION
"""Top of a cap. CAP_PROTRUSION is 0, so this is flush with the flat
front face by construction rather than by coincidence."""

CAP_BOTTOM = PAD_WEB_TOP + params.CAP_LIFT
"""Bottom of a cap's flange, and so the air the cap has to move down through."""

COUNTERBORE_TOP = (
    CAVITY_FRONT + params.CAP_LIFT + params.CAP_FLANGE_T + params.CAP_FLANGE_FLOAT
)
"""Shoulder a cap's flange lifts against, and so how far the counterbore is sunk
into the ceiling. What is left between here and SHELL_FRONT is the face land, the
ledge the flange is caught by."""

DISH_HEADROOM = SHELL_FRONT - COUNTERBORE_TOP
"""All the ceiling there is between a cap's counterbore shoulder and the flat
face, and so the whole budget a keypad recess is cut out of. What a dish takes
at any point over a counterbore comes straight out of this; check.py's land
guard holds the rest above LAND_FLOOR_MIN.

There is no single pocket-floor constant any more. The recess is curved, so the
floor is a function of position rather than a plane, and case.face_floor_at()
is what answers for it. Keeping a scalar here would only be a plane nothing is
actually built at."""

STEM_TOP = CAP_TOP - params.CAP_TOP_T
"""Ceiling of the cap's socket, now a shallow locating recess, and the top of
the stem that reaches it. The two meet, so a press drives through the stem
rather than through the flange, and the pad's silicone touches the cap where
the backlight has to cross."""

LIP_CLEAR_R = WHEEL_LIP_OD / 2 + params.WHEEL_CLEARANCE
"""The pad's wheel bore: clearance over the lip, the widest disc of the
revolved shape, is exactly WHEEL_CLEARANCE. The lip never reaches the
ceiling (board.wheel_profile() puts its top WHEEL_CLEARANCE and more below
CAVITY_FRONT, see check.py's wheel_seat_clearance), so this bore is a
pad-side rotating clearance only, not something the shell's own wheel
opening has to match: the board is lowered into an already-closed front
shell, so the shell's opening only ever has to clear whatever of the wheel
passes through it, the housing and knob above the lip, not the lip itself."""

WHEEL_OPENING_R = WHEEL_MAIN_OD / 2 + params.WHEEL_OPENING_CLEARANCE
"""The shell's own wheel opening, a plain bore from the ceiling underside to
the flat face: the main rotating body's radius plus WHEEL_OPENING_CLEARANCE,
its own gap rather than the pad's WHEEL_CLEARANCE, so the face sits flush to
the wheel on a line tight enough to read as one. Narrower than LIP_CLEAR_R,
which is fine for the same reason that bore is pad-only: the lip stays below
the ceiling and never transits the opening. Its top is opened out by the rotary
recess, which is centred on the same axis and reaches WHEEL_RIM_LEDGE past this
on its own axes."""

MERGE = 0.5
"""How far an added feature reaches into the body it grows from. Anything that
merely touches at a plane fuses into a compound rather than one solid, and the
next boolean then discards the whole shell."""

SKIRT_BOTTOM = BOARD_TOP - params.SKIRT_H
"""How far the front's skirt hangs below the parting plane."""

LAP_OUT = params.BOARD_FIT + params.WALL
"""Outer face of the case, which both shells share: the back's lap runs right up
to the parting plane, so the seam is a line rather than a step."""

LAP_IN = LAP_OUT - params.SKIRT_T
"""Inner face of the back's lap, and so the surface the skirt slides against."""

SKIRT_OUT = LAP_IN - params.SKIRT_FIT
"""Outer face of the skirt. Its inner face is the cavity wall's, so the skirt is
that wall carried down rather than a rib added beside it. That matters
structurally: put it anywhere inboard and it shares no plan area with the wall
above, and builds as a ring floating in mid air."""
