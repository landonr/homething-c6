"""Four-part case for the c6remote board: front shell, back shell, button pad,
IR window insert.

The back shell carries an AA lying along the board, which is what sets the case
thickness where the cell is. Elsewhere it tapers to what the board needs, so the
back is a contoured hump rather than a slab. The board hangs off the front plate,
on one boss per mounting hole dropping from the ceiling, taking M2 screws driven
from the back. The two shells meet in a lap joint around the whole perimeter, the back
closing over a skirt on the front, and are held by two detents at the grip end and
one screw at the other, which runs up through the back and the board into a front
boss and so clamps all three parts. A rail down each side of the skirt runs in a
channel in the lap and takes the play out of the middle.

The pad is two flat soft lobes with one raised feature per switch, one lobe per
island of keys, each padded off its own keys and so stopping short of the wheel
rather than being cut back from it. Neither reaches over the wheel or the status
LEDs: the light hits the translucent shell directly instead of being piped
through silicone. No skirt. The plungers rest on the switches and hold each lobe
against the ceiling.

SW1 and SW2 raise a moulded keytop, as every key once did. The other nine raise a
stem instead, and a rigid translucent cap sits over each one. The caps are
separate parts carrying the legends, so changing what a key says is one small
reprint rather than a new pad. Each is captive: a flange at its base rides a
counterbore in the ceiling, so it drops in from inside and cannot fall out.

The IR window insert closes the receiver's rounded -Z aperture in the back
floor. Its pane follows the built back contour, presses into the aperture, and
lands flush outside; its open interior flange retains on a continuous shell
shoulder that also carries adhesive. It installs from inside the back shell
before the shells close. The emitter remains separate and unchanged, firing
along +Y through a bare bore drilled to its own lens.

    python case.py            write an STL for each part, shells, pad, window
                              and caps
    python case.py --show     open in ocp-vscode instead of exporting

The geometry lives in model/, one module per feature. This file re-exports it
flat, so `case.X` still names everything it always did and check.py needs no
knowledge of where a given feature moved to.
"""

from model import *  # noqa: F401,F403
from model import main

if __name__ == "__main__":
    main()
