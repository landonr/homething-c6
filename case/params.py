"""Tunable dimensions for the c6remote case. All lengths mm, all angles degrees.

Coordinate frame matches the KiCad STEP export: X is board X, Y is negated board Y,
Z is 0 at the board's bottom copper face and positive upward. Component positions
from c6remote-pos.csv drop straight in with no transform.

Front is the button face, +Z. Back is the battery face, -Z. They correspond to
the board's top and bottom sides respectively.
"""

from pathlib import Path

BOARD_THICKNESS = 1.6
"""Nominal. The exported STEP body measures 1.51 because KiCad omits copper."""

SWITCH_HEIGHT = 1.6
"""TL3315NF160Q actuator height above the board face, from the 160 in the part
number. Not measurable from the design files: the footprint's 3D model is a
0.55mm stub, and being VRML it is dropped from the STEP assembly entirely, so no
check catches this being wrong. Confirm against a real switch before committing
to a pad tool, because every plunger length follows from it.

The keycaps inherit the error 1:1 as protrusion error, and it shows more on a
rigid cap standing proud than it ever did on a soft keytop, so measure before
printing nine of them."""

SWITCH_TRAVEL = 0.25
"""How far a TL3315 actuator moves to make. Family typical, hand-entered from the
datasheet and unconfirmable from the design files, the same epistemic class as
SWITCH_HEIGHT. A press must move the pad web this far to make the switch. The
web flex gives this travel, and the switch is the bottom stop."""
SWITCH_BODY = 4.5
"""Side of the TL3315 body, square in plan, from the footprint description.

The STEP assembly has no switch body, because the footprint's model is VRML and
the export drops it. So the skirt obstacles add a box of this side for each
switch, from the board face up to SWITCH_TOP. The real body is lower than the
actuator top, so the box is a safe envelope."""

# Shell
WALL = 3.0
"""Thicker than a plain shell needs, because the lap splits it: the back's lap,
a fit and the front's skirt all live inside this one thickness. The side catch
detents also need wall behind their roots. At 2.0 the lap is too thin for them.
It costs 2.0 on each of the case's outside dimensions."""
FLOOR = 2.4
"""Back shell floor, under the cavity and over the whole contoured form. No
fastener passes through it any more: the one closure screw enters the -Y end
wall horizontally, so this is sized as a printed floor over a hand-held
volume rather than against a counterbore sunk into it."""
BOARD_FIT = 0.5
"""Gap between the board edge and the inner wall. The cavity walls locate the
board, so the board can sit up to this far off centre on either axis.
The uniform offset changes case length and width by twice the clearance change."""

# Board deflection stops on the inside of the back shell side walls.
SUPPORT_BEARING = 3.0
SUPPORT_GAP = 0.25
SUPPORT_SKIRT_FIT = 0.4
"""Vertical clearance between the top of each board support ledge and the
front skirt relief above it. The front skirt must never land on a ledge,
because the seam shoulder is the only vertical stop. This value is larger than
SUPPORT_GAP. As a result, when a button press pushes the board down, the board
touches the ledges before the skirt does."""
SUPPORT_CLEARANCE = 0.4
SUPPORT_MIN_RUN = 8.0
SUPPORT_MIN_BREAK = 4.8
"""The shortest break, in Y, that a through-board solid opens in a back support
run when it reaches a long side wall. The front skirt relief over each run gets
a lead-in ramp at both ends. The skirt between two ramps must stay solid. This
value keeps the break layout that the screw head width gave before."""
SUPPORT_SOUTH_RUNS = True
"""Include the south-most board support run on each side when true. The front
ledges hold the grip end of the board down from above. The back runs under that
end must capture the same edge from below, or the board would be pinched against
nothing there, so this stays true."""
SUPPORT_UNDER_ANGLE = 60.0
SUPPORT_INNER_R = 0.6
"""Radius on the inboard support edge. It removes the sharp printed tip and
shortens the flat bearing surface by the fillet tangent."""
SUPPORT_MIN_BEARING = 1.5
"""Minimum flat board bearing that must remain after the inboard fillet."""
SUPPORT_SHELL_SKIN = 0.2
"""Keep this exterior shell thickness outside the board support ledges."""
FRONT_LEDGE_GAP = 0.0
"""Vertical gap between the board's top face and the flat underside of each
front ledge. Zero, because the screw bosses that these ledges replace held the
board at exactly this plane, so the board and the ledges meet with the same
stack as before. The back ledges stand SUPPORT_GAP below the board, so this
leaves the board free by that gap and it never clamps."""
FRONT_LEDGE_REACH = 31.5
"""How far from the board's grip (-Y) edge the front ledges may run. The two
screw bosses these replace stood 26.5 in from that edge, so this keeps their
position inside the window with 5.0 to spare. It is bound from above by the
button pad: the grid lobe's grip-side edge stands 33.2 in from the board edge
and the ledges must stay clear of it, so the window ends 1.7 short of that.
checks/front_ledge.py measures the clearance on the built pad."""

# Vertical clearance measured from the board faces, not from z=0.
KEYPAD_PLUNGER_STUB = 0.3
"""How far a plunger stands proud of the switch top before the pad's web
begins, over the keypad: KEYPAD_KEEPOUT in case.py is SWITCH_HEIGHT plus
this, so the web's underside lands just above the switches instead of
the old USB-sized margin, which left 1.7 of unsupported
plunger spanning dead air between the two.

Kept a real, nonzero stub rather than shrinking it to nothing: a press
still has to concentrate through a short, stiff post onto the actuator,
not through the flat web sagging down to meet it. 0.3 is toward the
shallow end of what still reads as a real stub; check.py's
plunger_stub_contact confirms the built pad actually reaches the switch
by it, not merely by the formula."""

PLUNGER_SWITCH_EXTENSION = 1.0
"""Each plunger extends 1.0 mm below SWITCH_TOP. This is approximately twice the
previous extension, so the plunger nearly touches the switch button. It provides
nominal switch engagement."""

LEGACY_NIB_EXTENSION = 0.5
"""Each V2 nib extends 0.5 mm below LEGACY_SWITCH_TOP, 0.5 shorter than
PLUNGER_SWITCH_EXTENSION. The printed V2 top pad of 2026-09-28 held SW1 and SW2
pressed with the case closed. The kept V3 plungers of that pad use it below
SWITCH_TOP too, so they stay SUPPORT_GAP above the nibs and cannot land on a V2
switch body before the switch makes."""

PLUNGER_LOWER_CHAMFER = 0.375
"""45 degree chamfer size at the lower plunger edge. It leaves a flat switch contact."""

STANDOFF_CHAMFER = 1.2
"""Height and radial reach of the root chamfer where the microphone duct meets
its shell. The chamfer is widest at the shell."""
END_SCREW_PILOT_D = 1.7
"""Self-tapping M2 into printed plastic, near the thread's own pitch diameter
of 1.74 rather than down at its 1.567 minor. Deliberately at the loose end of
the 1.6 to 1.7 an M2 self-tap is usually given: the block is a printed post
hanging off the skirt, so it splits along its layer lines long before the
thread it cut would strip, and the failure that costs a whole front shell is
the one worth designing away from. Use 3.2 for a heat-set insert, which is the
usual M2 insert OD."""

# The two shells lap right around the perimeter, back over front. The front's
# cavity wall carries on past the parting plane as a single skirt, and the back's
# wall is hollowed out over that same band down to a thinner outer lap that closes
# over it. The seam is the top edge of that lap, and the outer faces are flush
# across it, so nothing of the front is visible from the side below the seam.
# A shallow groove runs round the outer top edge of the lap. It makes the seam
# a deliberate shadow line, so a small step or gap between the shells does not
# show.
SKIRT_H = 4.0
"""How far the skirt drops below the board top. Raising the seam grows the
skirt upward without moving its lower edge into the support ledges or screw."""
SHELL_SEAM_RISE = 1.65
"""Lift the back lap and visible seam above the board top. The blind catch
pocket keeps about 1.05 of skirt above it and continuous wall behind it. The
support ledges and board mounting heights do not change.

The band this opens, from the support relief top to the seam, carries the
lower land, the pocket and the upper land. Both lands must clear the fab
minimum and the detent sets a floor under the pocket, so at 1.5 the band held
all three only with a lower land of 0.6. This value buys the lower land its
own 1.05 and still leaves the detent room above its tip."""
SKIRT_T = 1.5
"""The back's lap over the skirt. Whatever is left of WALL after this and the fit
is the skirt, so this one number splits the wall between the two shells."""
SKIRT_FIT = 0.30
"""Clearance between the shells. This gap lets the front fold closed and prevents a tight seal."""
LAP_MIN_WALL = 1.0
"""Thinnest wall that the back lap can keep to the outer round under the front
skirt. The shells check measures this wall on the built back shell around the
IR end. A deeper IR-end skirt needs a deeper lap relief. That relief left the
lap near a third of this value, so the IR end uses the plain skirt.

The seam shadow groove also keeps this wall. SKIRT_T less SEAM_SHADOW_DEPTH
must not go below this value."""
SEAM_SHADOW_DEPTH = 0.4
"""How far the seam shadow groove cuts into the back lap, inward from the
outer wall. The groove runs unbroken round the outer top edge of the lap, on
the one back that both fronts use. This depth casts a clear shadow and keeps
1.1 of lap, above LAP_MIN_WALL. The front shoulder bears on the lap top that
is left, SKIRT_T less this value wide."""
SEAM_SHADOW_H = 0.6
"""How far the seam shadow groove runs down the outer wall from the seam. A
taller groove gives a wider shadow line. The groove must stay above every
opening and detent in the back wall, or it cuts into them."""
SIDE_SKIRT_THICKEN = 0.25
"""Extra inward wall on the front skirt, round the grip end and its two corners
and up both long runs. The nominal 0.5 board fit still leaves 0.25 at the board
edge. It also sets the wall behind the side catch pocket, which is this skirt
less SIDE_CATCH_POCKET_DEPTH. This stiffens the printed seam without a change
to either shell's visible outer wall or to the back lap. It runs up to the
cavity ceiling, so the front's inner wall has no step at the seam.

The IR end keeps the plain fit for two reasons. The catch windows' reach is
sized off BOARD_FIT, so it passes a thicker skirt's inner face by only 0.1.
The IR end skirt's flex also sets how the catches close, and this extra wall
makes that skirt about 1.59 times stiffer. The grip end has no catches,
because one screw closes it."""
SIDE_SKIRT_THICKEN_RUN = 0.30
"""Length along each long side over which the stiffener tapers from its full
thickness to the plain board fit at the IR corner tangent. The IR corner arcs
keep the plain fit. The grip end has no taper, because the stiffener runs round
it at full thickness. The run clears the support-cut lead-in beside D1."""
SIDE_CATCH_CENTER_OFFSET = 3.5
"""Position of the side catches toward the IR end from the board's lengthwise
midpoint. The reported bow is near that midpoint; this offset centres each
pocket under it without recording an absolute board coordinate."""
SIDE_CATCH_W = 8.0
"""Length of each hidden side catch along the seam. A short land limits the
amount of PLA that must flex during the final fold closed."""
SIDE_CATCH_H = 1.0
"""Pocket height in the clear band above the front skirt's support relief and
below the raised seam. The pocket does not cut the full-length support runs.

The detent sets the floor. Its upper flank meets the skirt face a fixed
distance above the pocket bottom, and SIDE_CATCH_FIT must fit above that, so
this value cannot go under about 0.85. The rest of the band goes to the two
lands, which both have to clear the fab minimum."""
SIDE_CATCH_LOWER_LAND = 1.05
"""Height of skirt between the top of the built support relief and the pocket
bottom. The detent release flank bears on this lower lip. The pocket does not
need to be central in the band.

A ray cast down from the pocket floor crosses this lip to the support relief
below, so the fab pass reads it as a wall and it must clear the process
minimum. It was 0.6 while the band had no room for more."""
SIDE_CATCH_R = 0.45
"""Round the pocket corners to avoid sharp stress risers in the printed skirt."""
SIDE_CATCH_POCKET_DEPTH = 0.40
"""Depth of the blind cut from the skirt's outer face.

The detent tip stops 0.20 mm short of the floor. The wall behind the floor
has thickness SIDE_CATCH_WALL_MIN."""
SIDE_CATCH_POCKET_CHAMFER = 0.15
"""Inset of the pocket's rounded inner profile from its outer mouth. The
resulting bevel around both lips matches the detent's insertion and release
ramps without widening the mouth or thinning the upper skirt land."""
SIDE_CATCH_WALL_MIN = 1.0
"""Minimum continuous wall behind each blind catch pocket. This is the point
of replacing the through-window: a shallow detent must not sever the skirt."""
SIDE_CATCH_UPPER_LAND_MIN = 1.0
"""Minimum height of intact skirt above the pocket, checked on the built
shell. SIDE_CATCH_LOWER_LAND leaves about 1.05 nominally above its top edge.
If the pocket leaves less, side_catch_bottom() fails."""
SIDE_CATCH_D = 0.50
"""Inward projection of each back-lap detent.

The detent crosses the 0.30 mm shell gap and enters the pocket by 0.20 mm."""
SIDE_CATCH_FLANK_ANGLE = 45.0
"""Angle in degrees between each detent flank and the lap face. The detent
height comes from this angle, SIDE_CATCH_D and SIDE_CATCH_LAND_H. At this
depth, a slope from the pocket height left the flank that faces the bed at 36
degrees to it. 45 keeps both flanks printable in either back-shell orientation."""
SIDE_CATCH_PRELOAD = 0.10
"""Radial interference of the lower (release) flank at the pocket's lower mouth
edge. This sets the detent centre below the pocket centre. The skirt stays
slightly deflected when closed, and the flank force holds the front down on
the seam."""
SIDE_CATCH_LAND_H = 0.1
"""Short full-depth land at the tip of each detent. Both flanks ramp away from
it, so the shell can be opened and closed for service."""
SIDE_CATCH_FIT = 0.20
"""Inset of each detent's two lengthwise ends from the ends of the pocket's
straight lower lip. Past those ends the lip curls up into the rounded pocket
ends and buries the tip, which is a hard stop. It is also the minimum
clearance between the upper flank and the pocket's upper lip at the skirt
face."""
GRIP_SKIRT_RELIEF = 0.20
"""Extra radial clearance on the front skirt at the -Y grip end. The end was
hard to seat; relieving its hidden skirt leaves the outside seam unchanged."""
GRIP_SKIRT_RELIEF_RUN = 4.0
"""Length along each long side over which the grip-end skirt relief fades from
full depth to zero. It starts where the corner arcs end, so the relief runs back
into the skirt face without a step."""
SKIRT_TRANSITION_CHAMFER = 3.0
"""A value above zero enables the front-skirt lead-ins at the support-cut ends.
Each lead-in uses the full exposed height of its cut, not this value, to remove
small steps. Zero disables all skirt lead-ins."""
SKIRT_LEAD_ANGLE = 65.0
"""Lead-in angle in degrees from the flat skirt bottom along Y. A shallow angle reduces contact during assembly."""
SKIRT_LEAD_FIT = 0.20
"""Extra Y clearance at every front-skirt lead-in on both long sides.

The flat strip before the ramp gives the skirt room to pass each ledge."""

# At the IR end, the plain skirt carries two rounded rectangular windows. Each
# window sits CATCH_RISE above the skirt bottom. The back lap has a detent behind
# each window. When the front goes down, the lap rides out over the detent taper.
# Then the lower edge of the window catches under the flat of the detent. As a
# result, that end needs no screw. The front must hook in at that end and then
# fold down, and that is the purpose of this catch. A screw through the grip end
# wall closes the other end.
CATCH_W = 7.0
CATCH_H = 2.4
CATCH_R = 1.0
"""Corner radius of the window. Has to stay under half CATCH_H."""
CATCH_SPACING = 18.0
CATCH_RISE = 1.6
"""Skirt left below each window. This is what actually does the catching, so it is
not free to shrink."""
CATCH_D = 1.1
"""How far a detent stands in off the lap. Bounded above by the skirt it sits in:
past the skirt thickness less the fit it breaks through into the cavity, and the
whole end wall has to flex this far to let the front in."""
CATCH_NOSE_LAND = 0.8
"""Height of the vertical land on the nose of each detent, above the catch face.

Without a land, the lead-in slope meets the catch face in a knife edge. PCBWay
flags that edge, because it is thinner than the SLA minimum wall. At 0.8 the
nose is as thick as FAB_MIN_WALL["SLA"], so the fab pass reads no thin area on
the detent.

The slope starts at the top of the land and ends on the inner face of the lap at
the top of the detent. So the lead-in is steeper. It is 40.2 degrees off the
closing direction, against 35.5 degrees with no land. The front needs about 18%
more push to close. Below 0.8, a thin band stays on the nose. The land must stay
under CATCH_H less two CATCH_FIT, or no slope is left."""
CATCH_FIT = 0.20
CATCH_EMITTER_CLEAR = 2.5
"""Wall kept between the +x window and D1's emitter bore in the same end face.

The +x catch is placed off that bore rather than off the centreline, which is
what CATCH_SPACING would do: mirroring the grip end's spacing lands the window
squarely on the bore, whose position follows D1's lens.
So shells.catch_x() takes whichever is further -x of the spacing and this
clearance, and at the present layout this one governs."""

# One screw at the grip end, driven horizontally through the back's -Y end wall
# into a block the front shell carries behind its skirt. It closes the two
# shells to each other and is the only screw in the case. The cavity walls and
# the support ledges hold the board. Its head is the only hole in the back's
# outer surface. It is an M2 x 5. case.py prints the length the stack computes.
SHELL_SCREW_CLEAR_D = 2.4
"""Clearance hole through the back's -Y end wall. ISO 273 medium clearance for
M2."""
SHELL_SCREW_HEAD_D = 4.2
"""Counterbore in the back's -Y end face, the 4.0 mm largest standard M2 head
plus 0.2. Slacker than
the fits elsewhere in this model on purpose: a head that will not sit flush is
the one screw feature visible from outside the case."""
SHELL_SCREW_HEAD_H = 1.5
"""Counterbore depth, from the outer face of the -Y end wall. It is LAP_OUT less
LAP_IN, so the counterbore floor lands on the lap's inner face. At 1.7 the floor
went past that face, and the strip of relief floor over the counterbore read
under FAB_MIN_WALL["SLA"]. WALL is 3.0 here, so 1.5 of wall is left under the
head. The M2 cheese head, END_SCREW_HEAD_K, sits 0.2 below the outer face. A
pan head is too tall for this depth."""
END_SCREW_HEAD_D = 3.8
"""Head diameter of the modelled screw, the ISO 1207 dk for M2. It must stay
under SHELL_SCREW_HEAD_D, or the head runs into the counterbore wall."""
END_SCREW_HEAD_K = 1.3
"""Head height of the modelled screw, the ISO 1207 k for M2. It must stay
under SHELL_SCREW_HEAD_H, or the head stands proud of the end wall."""
END_SCREW_X_OFFSET = -5.8
"""The screw sits left of centre to keep the USB opening clear.
The negative sign also selects the left side skirt for the block's tie."""
END_SCREW_MODULE_WALL = 0.8
"""Additional separation beyond USB_CLEARANCE between the screw block and the complete module envelope."""
END_SCREW_Z = -5.5
"""Height of the end screw's axis, below the board.

Bounded above by the cover over the pilot's tip. The 45 degree ramp on top of
the block starts at SUPPORT_TOP at the ledge and falls one for one toward +Y,
so a higher axis leaves less cover over the tip than checks/hardware.py
end_screw requires. Above that limit, the counterbore top would reach the
back's lap relief, which is hollowed out for the skirt down to SKIRT_BOTTOM
less the fit. Bounded below by the roll of the back's outer surface through
CONTOUR_TIP_R_GRIP toward the floor. The whole SHELL_SCREW_HEAD_D counterbore
must stay on flat, full-thickness wall. checks/hardware.py end_screw measures
this on the built shells rather than restating it here."""
END_SCREW_BLOCK_W = 22.0
"""Width of the block the end screw threads into, across the case.

A self-tapping screw cuts its own thread into this printed block. The screw
pulls the block toward the -Y wall, so the block bends about x at the web, and
that load goes across the layer lines of a face down print. The 45 degree ramp
takes the depth off the upper block, so width is the only remaining lever on
that bending section and on the web's neck to the skirt.

The board grip tangents and the complete module envelope limit the actual block width.
The side tie stays at web height. The built-shell checks hold the neck,
thread cover, end rounds, and clearance to J1."""
END_SCREW_BLOCK_GAP = 0.5
"""How far the block's own -Y face stands off the back's inner end wall.

Its own number rather than SKIRT_FIT, which is what this was and is too little
for it. SKIRT_FIT is the gap between two faces that are meant to slide past one
another and are held in register by the lap all round them. The block is held
by nothing: it hangs off the skirt on one web, deep inside the cavity, aimed
straight at a wall the fold brings up to meet it. If it lands, it is a hard
stop between the two shells and the whole case bows out at that end, which is
what a printed one did. The gap is 0.2 more than SKIRT_FIT. A smaller gap
brings the pilot closer to where the ramp starts, and this lets the screw sit
higher."""
END_SCREW_BLOCK_D = 4.3
"""How far the block reaches back into the cavity: END_SCREW_PILOT_DEPTH plus
1.3, so the pilot ends inside it and the thread is never drilled out the back
of its own boss. The plus must stay at least 1.1. At 0.5 the cap was under the
PA12 minimum that PCBWay publishes for SLS. At 1.0 the cap measured exactly the
minimum, which the fab pass reads as a hair under.

The block's +Y back face sets the clearance to the cell. The 45 degree ramp
across the top, see END_SCREW_BLOCK_RAMP_LEDGE, falls the whole of this depth,
so a deeper block also takes more off the cover over the pilot's tip."""
END_SCREW_PILOT_DEPTH = 3.0
"""Engagement this one screw takes.

The screw is an M2 x 5. The screw length is the fixed quantity here, so the
pilot is what is left after the wall under the head and END_SCREW_BLOCK_GAP:
5.0 less 1.5 less 0.5. It is one and a half diameters into a self-tapped boss that is
END_SCREW_BLOCK_W wide. This screw only closes two shells and does not carry the
board."""
END_SCREW_BLOCK_BOTTOM = 2.5
"""Material the block carries below the screw axis, so the wall under the
thread is 2.5 around the pilot. Above the axis the block rises to the ramp off the skirt it hangs from, so it is not
symmetric."""
END_SCREW_BLOCK_R = 1.5
"""Round on the block's two +Y vertical edges, in plan.

The block hangs alone in the back's cavity with the shells closing over it, so
its inboard corners are what a misaligned fold catches on first. A round gives
the assembly somewhere to slide instead. Kept under half END_SCREW_BLOCK_D,
which is the shallower plan dimension and so the bound on any plan round here.
The two wall-side corners stay square, so the web and the root fillet run the
block's full width."""
END_SCREW_BLOCK_BASE_CHAMFER = 0.8
"""Lead-in on the block's bottom +Y arris, the corner that leads the fold.

The front hinges in at the IR end and swings down at this one, so the block
sweeps an arc and this corner is the furthest point of it: the first thing to
meet the back's floor if the fold comes in low or off square. It is the same
argument as END_SCREW_BLOCK_R makes in plan, and it wants the same answer, a
lead-in rather than a square arris.

Cut as a wedge across the whole width for the reason the top ramp is: the
arris is the straight edge plus the two plan rounds tangent to it, and an edge
chamfer on that chain tore the exported mesh.

Well under END_SCREW_BLOCK_BOTTOM, so the wedge stays in the material carried
below the screw and never reaches the thread."""
END_SCREW_BLOCK_END_R = 5.0
"""The outer block end follows the back cavity near the grip corner."""
END_SCREW_BLOCK_MODULE_END_R = 1.0
"""The smaller inner end round preserves thread cover beside the module."""
END_SCREW_BLOCK_RAMP_LEDGE = 0.4
"""Flat step the block's top keeps before its 45 degree ramp, measured from the
plain board fit plane, not from the skirt face. skirt_stiffener() moves that
face SIDE_SKIRT_THICKEN inboard at the grip end, so the flat left off the
built skirt is this step less that thickening.

The front prints face down, so the top of the block and its web is a ceiling
hung off the skirt in print. A flat top needs a support tower in the cavity
that is hard to clean out. The ramp falls one for one toward +Y from the end
of this step, so each layer stands on the one before it.

This step is the only flat overhang left. It is small enough to print from the
skirt without support. It also raises the whole ramp by its own length, which
adds that much material over the pilot's tip and in the web's neck at the
block's -Y face, against a ramp that starts at the board fit plane.

Bounded by END_SCREW_BLOCK_GAP. If the step reached the block's own face, the
block would keep a flat ceiling again. checks/hardware.py reads the cover over
the pilot and the neck on the built front."""
END_SCREW_BLOCK_TIE_LAND = 0.8
"""Height of the vertical end face where the side tie stops under the ramp.

The 45 degree ramp falls through the tie, which is only web height. If the tie
runs on, the ramp leaves its underside in a knife edge. PCBWay flags that edge,
because it is thinner than the SLA minimum wall. So the tie stops where the ramp
is still this far above its underside, and a vertical face closes it.

At 0.8 the end face is as thick as FAB_MIN_WALL["SLA"]. The face is vertical as
the front prints face down, so it needs no support. The cut removes only the
tail of the tie, so the tie keeps its full section everywhere else. The land
must stay under the web height, SUPPORT_TOP less SKIRT_BOTTOM."""

END_SCREW_CHAMFER_COVER = 0.85
"""Wall that the back's end wall chamfer leaves over the clearance bore, at the
cavity face.

A chamfer from corner to corner comes down to 0.1 above the bore, and PCBWay
flags the sliver between them. So the chamfer and the block's root fillet both
rise by end_screw_root_lift, and each leg gets that much shorter. The two faces
stay parallel, so the gap between them does not change. The fab pass reads
this wall vertically, from the bore up, and 0.85 keeps it over
FAB_MIN_WALL["SLA"]. A larger value shortens the root fillet more."""

# Cell: a generic 102050 LiPo pouch lying flat along the board underneath it. Its
# leads and PicoBlade plug leave the protection-board end, which faces J1 at the -Y
# (grip) end. The XIAO's charger wants a single-cell 3.0 to 4.2V lithium cell.
CELL_T = 10.0
"""Pouch thickness along Z."""
CELL_W = 20.0
"""Pouch width along X."""
CELL_L = 50.0
"""Pouch length along Y, without the leads and plug."""
CELL_FIT = 1.0
"""Total slack across the width, so half of it each side. Generic pouches vary
in width, so this is looser than a machined cell would need."""
CELL_END_FIT = 1.5
"""Slack along the length, for the same tolerance."""
CELL_TOP_GAP = 0.6
"""Clearance from the cell up to the board. Anything hanging below the board by
more than this counts as an obstacle when picking the bay, so the cell never has
to sit below a component. The stretch-release strips that hold the pouch to the
board sit in this gap, between the board's back face and the pouch."""
CELL_SWELL = 0.5
"""Room under the pouch for thickness tolerance and swelling. A pouch must not be
clamped between the board and the back shell."""

CELL_END_MARGIN = 7.0
"""How far the cell sits from the near end of its bay, which is what pushes the
cell down toward the bottom edge instead of centring it. Wants to stay clear of
CONTOUR_TIP_R and CONTOUR_TIP_R_GRIP, or the rounded-off end eats into the cell.
At the -Y end it is also the room for the plug and the leads between J1 and the pouch."""

BACK_KEEPOUT = 12.0
"""The deepest the cavity gets, over the cell and the grip end. The pouch stack
needs CELL_TOP_GAP + CELL_T + CELL_SWELL, but the end screw block and its
counterbore at the grip end need more. The end_screw and shells_mate checks
fail below this value."""

# Outer form. The back is contoured along its length rather than being a slab: the
# cell sits toward the bottom end, so the case is deep where you hold it and tapers
# from there to whatever the board itself needs. The shape is a loft, and the
# rounding is built into its sections rather than filleted on afterwards.
CONTOUR_END_DEPTH = 7.0
"""Floor under the tapered ends, not the value they take. Each end is derived
from what actually hangs below the board on that side and only falls back to
this when no part needs more depth. Both ends use this minimum with the current board.
The assembly STEP supplies the measured component depths.

The +Y budget is tight around D1's flared bore.
The back rolls up through CONTOUR_TIP_R to meet that face, and reducing this
depth can make the bore break out through the underside. U2's bottom aperture
does not share that constraint; its conformal insert follows whatever back form
this depth produces. Built end-port and receiver-path checks guard both cases."""
CONTOUR_TIP_R = 5.0
"""Radius the back rolls up through at the +Y (IR) end of the case, so the bottom
meets the end face tangentially instead of squaring off into it. D1's bore budget
bounds it there. Keyed to the case's own end, not the board's. The loft's end
regions run over this radius or the plan's own corner, whichever reaches further
in."""
CONTOUR_TIP_R_GRIP = 7.2
"""Radius the back rolls up through at the -Y grip end. The cavity rolls through
this less WALL, tangent to its floor and its end wall, so the corner keeps at
least FLOOR of wall. The end screw head counterbore bounds it, because the lower
rim of that counterbore must stay on the flat end face. The cavity's roll does
not reach the end screw block, because the block stands END_SCREW_BLOCK_GAP off
the back's inner wall. At 7.0 and 7.4 the support envelope loft does not
intersect and the build stops, so test a new value with a full build."""
CONTOUR_BLEND = 22.0
"""Length each taper runs over, measured out from the cell. Long enough that
the hump is a curve to hold rather than a step."""
EDGE_R_BACK_CELL = 12.5
"""Round on the back's bottom edge over the cell. It runs the whole way
round the plan, corners included, because each loft section is as wide as the plan
is at that point. It makes the battery end read as a hand-held dome rather than a
box with its corners removed. The cavity uses this radius less FLOOR, so the shell
keeps its thickness around the corner."""
EDGE_R_BACK_IR = 8.0
"""Round on the back's bottom edge near U2. It is smaller than EDGE_R_BACK_CELL so
the upper taper stays light and every lifted form used by the IR insert remains a
valid rounded section. The profile blends from the cell radius over CONTOUR_BLEND."""
EDGE_R_FRONT_FDM = 0.85
"""Leg length of the FDM front's 45 degree top-edge chamfer. The FDM front is
flat, so it does not take the recessed front's rolled face. front_edge_round()
reads this value.

The smaller FDM groove leaves room for this bevel and flat face beyond the
groove. The bound is KEYPAD_EDGE_MARGIN less half FDM_OUTLINE_W less
FDM_OUTLINE_EDGE_CLEAR. The USB opening is below the board.
checks/fdm.py measures the built face's flat margin. checks/shells.py guards the exported mesh."""

# Apertures in the front shell
KEY_GAP = 1.6
"""Gap between neighbouring keytops. Key size is the switch grid's own pitch less
this, in both directions, so the grid runs the full width and moving a switch
resizes the keys. The switch grid is square to within 0.03, 12.45 across against
12.42 down, so one number covers both and the keys come out square. What binds
is the counterbores rather than the face holes: they sit at the keytop footprint
this sets, so the rib of ceiling between two of them is the thinnest the front
plate gets anywhere."""
KEY_SQUIRCLE_N = 3.0
"""Exponent of the superellipse every width in the keycap chain is drawn on: the
cap body, its flange, the counterbore the flange rides and the face hole the
body stands in, all one curve at four sizes through caps._key_prism().

Its own number rather than the recesses' KEYPAD_SQUIRCLE_N, which the caps used
to share. A cap is a small shape read at arm's length against a large one, and
at four the two read as the same family only in the sense that both have
straightish flanks; the cap wants its sides visibly bowed out so it reads as a
pebble sitting in the dish rather than as a tile. Three is where that shows
without the shape tipping over into the circle it becomes at two.

What is spent for it is the top. A legend has to fit the largest square the cap
holds, whose side is the body times 2^(-1/n) (caps.cap_flat()), and that factor
falls with the exponent: about 0.841 at four against 0.794 here, so a cap this
size gives up around four tenths of a millimetre of usable top. The binding
legends are SW9 and SW11, and check.py's own ink pass against LEGEND_INK_MARGIN
is what says whether a further drop is affordable, not this docstring.

Corner reach moves the other way, which is why the counterbores did not get
tighter against the recess rim: a superellipse's diagonal stands 2^(1/2 - 1/n)
of a half width out, so a lower exponent pulls the corner in rather than
pushing it out, and counterbore_dish_margin() reads slightly more room than it
did at four."""
KEY_SQUIRCLE_POINTS = 64
"""Points a keycap's own superellipse is drawn through, closed. Half what a
recess rim uses for a shape a quarter the size, so the chord is finer here than
there while the front shell still gains a manageable number of faces: every cap
puts two of these prisms in the shell as its counterbore and its face hole, and
they are the busiest cuts in the plate."""
KEY_CLEARANCE = 0.3
"""Gap per side between whatever comes through a key hole and the hole itself.
The SW1 and SW2 moulded keytops only. The nine rigid caps are gapped by
CAP_GUIDE_CLEARANCE instead, because their hole has to guide them rather than
merely clear them. It still bounds the counterbores, which sit inside it."""
WHEEL_CLEARANCE = 0.5
"""Radial gap the pad's own bore leaves around the lip, the widest disc of
ENC1's revolved shape, since nothing under the lip is wider than the lip. The
pad only, now that the shell's opening has WHEEL_OPENING_CLEARANCE of its own:
this gap is buried under the pad and the face's is looked at, so one number
could not answer to both. board.wheel_profile() measures the diameter rather
than it being hand-entered."""
WHEEL_OPENING_CLEARANCE = 0.2
"""Radial gap the shell's own opening leaves around the wheel's fixed bezel,
the part that does reach the ceiling. Tighter than WHEEL_CLEARANCE
because this one is a visible line around the bezel rather than buried
clearance, and the lip never transits the opening so nothing wider has to
pass it."""

WHEEL_LIP_RELIEF = 0.6
"""How far the ceiling lifts clear of the ENC1 lip, measured off CAVITY_FRONT.

The lip is the widest disc of the wheel, a static flange under the fixed
bezel. It is wider than the wheel opening, so it can never pass up through the
face, and the ceiling has to stay off it.

Without this relief the ceiling sits flat at CAVITY_FRONT right across the
lip, with 0.555 of air. CAVITY_FRONT is PAD_WEB_TOP, so that gap is the one
thing that pins the pad web, and through it the counterbore lands. See
PAD_WEB_T.

The relief is a plain annular lift out to led_ring_inner_r(), so it merges
into the LED ring channel's inner wall. Nothing seats in that annulus. The
pad's own bore is at LIP_CLEAR_R, further out, and the only part under it is
the lip.

The size is what the roof above it can pay. A ray cast over the band finds the
roof 1.781 at its thinnest, on the -X side at the ring arch's sag, so a lift
of 0.781 would put it on the PA12 minimum. This value keeps 1.181 there and
still funds the 0.506 that the lands want.

The cost is light. The ring channel now opens into the wheel bore, so the ring
glows into the WHEEL_OPENING_CLEARANCE gap round the bezel. Where the channel
is shallow, at the east and west sides, the lift takes the whole inner wall.
"""
WHEEL_RIM_LEDGE = 1.0
"""Least seat the recess must leave around the wheel opening's bore, measured in
plan from the bore wall out to the rim.

A floor, not a sizing rule. It used to be both, the basin's half axes being the
bore plus exactly this, which left the ring around the knob only as wide as this
number on the axes and reading as a rim rather than a saucer.
WHEEL_BASIN_SPREAD sizes the basin now and this is what check.py holds the
result to, measured around the whole merged rim so the joins are in it too.

It stays meaningful at any exponent at or above two: above two a superellipse's
own axes are where it comes closest to its centre, so the axis half axis is the
clearance everywhere and the diagonals only stand further out."""
WHEEL_BASIN_SPREAD = 4.4
"""How far past the wheel opening's bore the wheel basin's own rim stands on its
axes, and so its half axes: WHEEL_OPENING_R plus this, square aspect. What makes
the dished ring around the knob read as a saucer rather than a rim; at
WHEEL_RIM_LEDGE it was the latter.

Bounded three ways, and the tightest of them is not the obvious one. In x it is
KEYPAD_EDGE_MARGIN against the case wall, the same cap the keyed basins hit. In
depth it is LED_RING_ROOF: a wider basin crosses more of the ring channel's
annulus and does it further down its own sag, so the roof thins as this grows
and check.py's ring stack guard is what holds it.

In y it is the neighbouring basins. The spine is one interval in x per y, which
needs exactly one thing claiming each y, and a basin wide enough to reach past
where its join begins would have two. The joins cover the overlap up to about
four and a half here, so this sits inside that; check.py walks the span and
fails on any y that two basins claim and no join covers, which is the guard that
makes the bound visible rather than a silent wrong answer."""
WHEEL_SQUIRCLE_N = 2.2
"""Exponent that sets the wheel basin's diagonal reach.

The wheel outline blends a circle with this superellipse by angle. The blend
weight is sin²(2θ). It is zero on each cardinal axis and one on each diagonal.
As a result, the axes have circular curvature and the diagonals keep this
superellipse's exact reach.

Two is the lower limit. Below two, the diagonals move inside the axes and can
reduce WHEEL_RIM_LEDGE. The wheel's large KEYPAD_JOIN_REACH keeps both necks
wide enough for their minimum outline radius."""
WHEEL_DISH_DEPTH = 1.4
"""Depth of the wheel basin at its own centre. This gives more finger access
around the knob. The centre is inside the bore, so the cut never reaches it.
What the number really sets is the seat depth at the bore wall. That depth is
about 0.62 of this value on the free axis and about 0.65 on the diagonals.
WHEEL_SQUIRCLE_N sets how much deeper the diagonals are.

LED_RING_ROOF bounds this value, not a counterbore, because no key sits under
this basin. The roof over the ring channel is thinnest where this basin's
diagonals or one of its joins cross the channel. check.py holds a floor under
what is left there."""
WHEEL_RIM_SOFT = 0.0
"""Dish depth over which the wheel basin's floor rolls into the face at its rim.

It is zero, so the dish has no roll. The rim chamfer, RECESS_CHAMFER_W,
replaces it. The plain dish section meets its rim with a vertical tangent,
but the chamfer cuts away the dish within RECESS_CHAMFER_W of the rim, so that
tangent is not built.

If the value is more than zero, keypad.py uses d^3 (3c - 2d) / c^3 where the
depth d is less than this value c. The last c of depth then rolls into the
face with zero slope. The value must stay below the basin's depth, and
keypad_recesses() stops with an error if it does not. KEYPAD_RIM_SOFT and
KEYPAD_RIM_SOFT_2 do the same for the key basins, and the necks blend between
the three."""
KEYPAD_RIM_SOFT = 0.0
"""Dish depth over which the grid basin's floor rolls into the face at its rim.
It is zero, because the rim chamfer replaces the roll. See WHEEL_RIM_SOFT."""
KEYPAD_RIM_SOFT_2 = 0.0
"""Dish depth over which the second basin's floor rolls into the face at its
rim. It is zero, because the rim chamfer replaces the roll. See
WHEEL_RIM_SOFT."""
KEYPAD_LIP_LIFT = 0.6
"""Fraction of the dish depth that the grid and second basins give back at and
past KEYPAD_LIP_CREST.

Each dish floor follows the face, and the face falls toward the side walls.
Without this lift, a key dish floor falls all the way from the centreline to
the rim, and the dish has no lip. keypad.py multiplies the softened depth by
one less this value times a smoothstep of the face drop. The floor then rises
to a crest near the outer key columns and rolls into the face at the same rim.

The rim does not move, and the floors only rise. As a result, the counterbore
lands over the outer columns get thicker. The wheel basin has no lift, and the
necks blend between the basins. The value must be from zero to one."""
KEYPAD_LIP_CREST = 16.0
"""Distance in x from the centreline at which KEYPAD_LIP_LIFT has its full
effect.

The lift follows the face drop at x over the face drop at this distance, so
it follows the superellipse and not x itself. A smaller value moves the crest
toward the centreline and makes the climb to it steeper."""
FACE_CROWN_OVER_WHEEL = 0.241
"""How far the crown of the recessed front's face stands above the knob's
measured top, WHEEL_TOP.

It was 0.135. The counterbore lands then ran 0.54 to 0.75, well under the PA12
minimum that PCBWay publishes for SLS. They needed 0.506 between them.

COUNTERBORE_TOP is built off the cap flange, so lowering it thins the caps
instead. A thinner PAD_WEB_T lowers COUNTERBORE_TOP by the same amount. The
ENC1 lip used to pin the pad web. wheel_lip_relief() lifts the ceiling off the
lip, so the web is free to come down. PAD_WEB_T pays 0.4 of the 0.506, and
this value pays the remaining 0.106.

So the whole front is 0.106 taller than it was, not 0.506. The knob stands
0.617 proud of the face at the wheel opening rim, where it stood 0.723 before.

SHELL_FRONT is WHEEL_TOP plus this value, so a wheel change still moves the
face. The crown runs along the centreline over the knob, but the wheel dish
lowers the face around the knob. As a result, the knob still stands above its
own seat.

This value and FACE_SIDE_DROP set the face together. They hold FACE_WALL_TOP at
the height that the walls, catches and seam are made to. The superellipse then
crosses the wheel bore edge at the height that the keys, the bore and the LED
ring are sized to.

A larger value raises the dish floors and the bore seat with the face, so the
knob stands less proud of its seat. A smaller value lowers the floors, and each
counterbore land gets thinner by the same value, because COUNTERBORE_TOP does
not move with the face."""

FACE_SIDE_DROP = 3.805
"""How far the recessed front's face falls from its crown, SHELL_FRONT, to
FACE_WALL_TOP, where it meets each exterior wall.

Across the width the face is one superellipse of FACE_POWER from side wall to
side wall. It is level at the crown and vertical at each wall, so the face
reads as one round section. No edge shows where a flat panel turns into a
round. This value is the section's height, and FACE_ARCH_HALF is its half
width.

Together with FACE_CROWN_OVER_WHEEL, this value sets FACE_WALL_TOP. A larger
value lowers the face everywhere off the crown. Over the outer key columns and
at the east and west sides of the knob, the counterbore lands and the LED ring
roof then get thinner. checks/keypad.py and checks/wheel_ring.py hold both."""

FACE_POWER = 3.0
"""Exponent of the recessed front's superellipse, across the width and in each
end roll.

At 2 the section is an ellipse. A larger value keeps the face fuller toward
the walls and turns it down faster near them. At 3 and above the face meets
each wall with zero curvature, so the wall runs into the face without a
highlight line. Below 2 the crown has infinite curvature, which shows as a
line along the centreline."""

FACE_END_ROLL = 6.0
"""How far into the plan the recessed front's face rolls down into each end
wall.

Over this length the face section falls to FACE_WALL_TOP with the same
FACE_POWER as across the width, and it meets the end wall vertically. Around
the plan corners the section's half width follows the corner arc, so the face
meets the corner walls vertically too.

The IR-end top-key recess reaches into this roll. Its floor stays under the
face, because every dish depth is measured down from face_z(). A longer roll
lowers the face over the recess tip and toward the mic inlet."""

# Status LEDs: the pad's wheel bore is cut wide enough that the pad never
# reaches over them, and they shine straight through the translucent shell.
# The pad used to carry a hidden flange out over the LEDs that piped light
# inward to a moulded ring plug in a shell window; the translucent case
# material diffuses better than the silicone did, so the pad now just gets
# out of the light's way entirely.
LED_HEIGHT = 0.8
"""XL-2020RGBC body height above the board face. Hand-entered: D2-D7 carry only
a WS2812C-2020 stand-in model, so nothing in the design files can confirm it."""
LED_BODY = 2.0
"""XL-2020RGBC body side, square in plan. Hand-entered for the same reason as
LED_HEIGHT."""
PAD_LED_CLEARANCE = 0.6
"""How far past an LED's own body edge the pad has to stop, so the web's edge
stands clear of the package and does not graze it. pad_keepouts() grows each
LED body by this value, off the LED placements plus LED_BODY, so a moved LED
moves its keep-out. Each ring-insert lobe keep-out reaches past its LED, so the
lobe keep-outs are the ones that notch the pad."""
WHEEL_OPENING_EDGE = 0.65
"""Minimum ceiling between the shell's wheel opening and the side wall. The
opening is clipped to a chord near the X axis if it would come closer than
this, which is what made the case a flat-sided oval before BOARD_FIT was
padded out. At the opening's current radius there is more room than this asks
for and nothing is clipped, so this is idle. The LED ring channel used to share
the clip and no longer does: the channel runs flush to the cavity wall
instead."""

# LED ring channel: an annular void inside the front shell's ceiling, circling
# the wheel opening and passing over D2-D7, so their light spreads around the
# channel and reads as a ring on the face instead of six dots. The channel is
# open to the cavity below (the pad's wheel cut already uncovers the LEDs) and
# roofed by translucent shell, which is the diffuser. On the recessed front the
# roof is LED_RING_FACE_ROOF under the face all the way round.
LED_RING_WALL = 1.25
"""Web between the wheel opening's bore and the channel's inner wall. It is what
keeps the opening a closed cylinder the wheel seats against, and it is the
ring's inner light barrier, so it is not free to thin toward zero. The inner
wall stands at this radius below its top chamfer and widens the web above it.
The check still probes it on the built shell rather than trusting the sum.

It was 1.0, which read 0.84 on the built shell, because LED_RING_INNER_CHAMFER
bevels the top of this wall and the ray crosses the bevel. This web, not the
roof, is the thinnest part of the ring channel: the roof runs 1.50 to 1.68
because the arch sits below the face less LED_RING_FACE_ROOF all the way
round."""
LED_RING_INNER_CHAMFER = 0.40
"""45 degree bevel at the inner wall's top edge on both LED channels. It steps
this far out from the inner wall and this far down from the channel ceiling at
the top of the bevel. The inner wall stays upright below the bevel. On the FDM
front the bevel uses nearly all of the wall.

It was 0.53. The bevel eats the roof flat from the inside, and the roof flat is
what the ring insert's neck is as wide as. At 0.53 the neck measured 0.914 with
RING_INSERT_FIT taken off both sides, under the PA12 minimum that PCBWay
publishes for SLS. This value widens the flat at the crown and carries the neck
over the minimum. It changes nothing at the east and west sides, where
led_ring_bevel() already shortens the leg below this value on its own.

On the recessed front the ceiling changes around the ring, and the bevel hangs
from the local ceiling. At the east and west sides the channel is too shallow
for the full bevel. There the bevel shortens and stays at 45 degrees, so that
LED_RING_INNER_FOOT_MIN of upright inner wall stays above CAVITY_FRONT.
wheel_ring.led_ring_bevel() gives the bevel on each bearing. Everywhere else
the bevel is this value."""
LED_RING_INNER_FOOT_MIN = 0.12
"""Least upright inner wall that the recessed front's LED ring channel keeps
above CAVITY_FRONT, below the inner bevel. Where the channel is too shallow for
the full LED_RING_INNER_CHAMFER, the bevel shortens to keep this much wall. The
channel is shallowest at the east and west sides of the knob. The FDM front
does not use this value."""
LED_RING_CHAMFER = 0.0
"""How much wider than its nominal radius the FDM channel's outer wall opens at
the mouth. That wall rakes at 45 degrees, so this is also how far above the
mouth it crosses led_ring_outer_r(). The inner wall has a separate top bevel
and this does not reach it.

The mouth is the flared end because that is where the light enters, off LEDs
firing up out of the cavity: a wall raked away from them puts more of the roof
in view of each. A 45 degree rake is also what a printer can close a ceiling
over without support.

The recessed front has no such channel any more, so this value reaches the FDM
front alone. Zero keeps the mouth flush with the pad's grid-lobe boundary."""
LED_RING_OVER = 0.6
"""How far past an LED's own body edge the FDM channel's outer wall reaches.
Same job as PAD_LED_CLEARANCE one layer down: derived off the LED placements
plus LED_BODY, so moving an LED moves the channel with it.

It does not stand the package clear of the raked wall, and it must not be
trimmed to. Each LED fires at the middle of that rake on purpose: the rake is
the ring's reflector, and a source aimed at the middle of it throws light
furthest around the channel.

The recessed front reaches the same LEDs a different way, with a dome over each
one on the insert rather than a channel in the shell, so it does not read this
value. See RING_LOBE_SIDE."""
LED_RING_ROOF = 1.675
"""Distance from SHELL_FRONT down to LED_RING_TOP, the depth the FDM front's
own channel is a fraction of.

The recessed front has no channel ceiling left to set. Its ring is one circle
cut from the cavity ceiling clear through the face, and led_ring_insert()
fills it, so no shell sheet covers the light on that front at all. See
led_ring_face_r().

The FDM front keeps a real channel under a real roof, and its depth is
FDM_LED_RING_DEPTH_RATIO of this depth over CAVITY_FRONT. So a change here
moves the FDM front alone."""
LED_RING_FACE_ROOF = 1.0
"""The one wall thickness the LED ring is built to, on both parts.

It is the land of shell over each lobe: the lobes are what hold the insert in,
and each tucks under this much shell before the pocket's 45 degree lead-in
starts. It is also the roof the insert keeps between a dome and its own top,
and the roof the FDM front keeps over its channel.

This value is the minimum wall that PCBWay publishes for PA12 printed by SLS.
The shells are now Somos Taurus by SLA, where the minimum is 0.8, so this value
keeps a margin over that order and still passes an SLS order. The
land is measured vertically and the face slopes, so the wall normal to the face
reads a little under this value.

A smaller value is under the minimum. A larger one pushes each pocket's 45
further down, which costs the lobe depth rather than light, because the light
reaches the face through the insert now and not through shell."""
RING_FOOT_W = 4.0
"""Width of each foot under the ring insert, across its own bearing, at the
foot's mid radius. Each foot is a sector of the band, so its sides are radial.

Wide enough to carry the part without being a pin, and narrow enough to stay
clear of the LEDs either side of it. Each foot sits midway between two of
them, so half this plus the LED body has to fit in half the gap."""
RING_FOOT_GAP = 0.3
"""How far the ring insert's feet stop above the board.

They are a limit on how far the part can drop, not a seat it rests on. A foot
cut to land on the board would have to answer for the board's own float on its
ledges and for the SLS tolerance on both parts, and the way that stack falls is
what decides whether the ring sits flush or stands proud of the face. Adhesive
is what holds it flush, the way it holds the IR window. These only catch it.

So the gap is deliberate: at rest nothing touches, and the feet come into play
only if the bond lets go. Then the ring drops this far and stops, instead of
dropping onto the ENC1 flange. The board reads a little lower than BOARD_TOP in
the STEP assembly, so the built gap is a little larger than this."""
RING_INSERT_FACE_FIT = 0.20
"""Radial clearance from the separate ring insert to the front shell bore.

The same clearance applies around the full joint. Adhesive holds the insert
flush with the front face."""
RING_FLANGE_OVERLAP = 0.30
"""Radial overlap beyond the face bore. The flange blocks view of the PCB."""
RING_FLANGE_T = 0.85
"""Flange thickness. It keeps margin over the 0.80 mm SLA minimum."""
RING_FLANGE_DROP = 0.45
"""Depth of the flange base below the cavity ceiling.

This placement leaves shell above the relief and clearance above the LEDs."""
RING_FLANGE_LOFT_CLEARANCE = 0.05
"""Radial offset of the faceted band step outside the flange's inner cylinder.

The offset prevents tangent intersections and sliver faces during the union."""
RING_BORE_ROUND = 0.6
"""Radius of the round on the ring's inner edge, where the dish meets the
wheel bore.

The ring insert and the one-piece front both carry it. It drops the edge
next to the knob, so the knob stands this much higher over the ring's edge.

It is half of FDM_WHEEL_OPENING_CHAMFER, so it reads as a soft edge and not
as a lead-in. On the X axis the ring is only 1.24 thick at the bore, and this
round leaves 0.64 of plumb bore wall there. A 0.8 round would leave 0.44."""
RING_LIFT_CLEAR = 0.15
"""Minimum radial inset of the round shell bore from the cavity wall.

The separate insert stands a further RING_INSERT_FACE_FIT inside the bore.
The two offsets give its circular outside face clearance during insertion."""
RING_LOBE_SIDE = 0.5
"""Clearance each dome keeps beside its LED on the inner side.

It sets where the dome blends back into the ring's own underside. The outer rim
is not set here. RING_LOBE_GAP sets that, because the rim has to dip below the
LED's top face and the dome then has to climb over the LED's outer corner on
its way back in.

The dome is open on the inner side, which is not a choice. A wall there would
have to stand between the LED's inner edge and the ENC1 lip, and LIP_CLEAR_R
leaves 0.20 of room for it. The inner side loses nothing, because the ring
itself sits directly over the LED's inner half and takes that light."""
RING_LOBE_WRAP = 0.4
"""How far each dome's outer rim dips below its LED's top face.

The ring stops short of the LEDs, so each dome reaches out over one and the
rim is what stops that LED's light escaping past the ring. A rim level with the
LED top would catch none of what leaves the package sideways. This value is
what makes the lobe a wrap rather than a lid."""
RING_LOBE_GAP = 0.3
"""Air each dome keeps over its LED.

The rim sits RING_LOBE_WRAP below the LED's top, so the dome has to climb over
the LED's outer corner on its way back in. led_ring_lobe_rim_r() solves for the
rim radius that leaves exactly this much there, rather than taking the rim off
a radial clearance and reading what that happens to give. So this value is the
built clearance and not a floor under it.

It is RING_FOOT_GAP, the same air the feet keep over the board. Both answer for
the same stack: the board's own float on its ledges, and the SLS tolerance on
the insert."""
RING_LOBE_STRAIGHT = 0.85
"""How straight each dome runs, from a curve that meets the band's underside
flat (zero) to a plain cone (one).

The flare over the dome is a 45 degree plane, so the material between them is
the vertical gap times cos(45), not the vertical gap. A dome that leaves the
band's underside flat has to climb hard in the middle to get there, and the
middle is exactly where the flare sits over it. At zero the wall between the
two came back at 0.88 over 19 mm2, under the SLS minimum, which is the reading
this whole feature exists to remove.

The straighter dome preserves wall thickness under the clearance flare.
The rim moves outward to keep RING_LOBE_GAP at the LED's outer corner.

It also puts a slight angle where the dome meets the band's underside rather
than running in flat. That corner has the whole band over it, so it is a
change of slope and not a feather.

led_ring_lobe_roof() is what holds the result, and it measures normal to the
flare rather than vertically."""
RING_LOBE_WALL = 1.0
"""Thickness of the wall outside each dome's rim.

The rim is the lowest point of the insert's underside, and the dome is open
inward, so this is the one real wall a lobe has.

This value is the PCBWay SLS minimum. It is written out and not read from
FAB_MIN_WALL, because the insert is an SLS part whatever FAB_PROCESS says."""
RING_LOBE_FIT = 0.20
"""Normal clearance between a lobe and its pocket in the front shell.

The clearance applies to the sloped roof, flat roof and pocket sides.
Each lobe rests below a land that keeps the insert captive."""
RING_LOBE_SHOULDER = 0.75
"""Leg of the 45 degree chamfer on the top outer corner of each lobe.

The flat top of a lobe ends in a vertical outer face. On the D7 bearing that
corner stood under the flange of SW6, 0.15 below it. A full press of
SWITCH_TRAVEL took the flange 0.10 into the lobe. This chamfer keeps the
pressed flange about 0.43 clear, and checks/wheel_ring.py measures it.

The corner carries no retention, because the flare ends at its knee before the
flat starts. The dome wall to the chamfer stays at RING_LOBE_WALL or more up
to a leg of about 1.74. led_ring_lobe_roof() measures that wall, and
led_ring_lobes() refuses a lobe that it thins. All six lobes take the same
chamfer."""
# Apertures in the back shell
MIC_THROAT_MARGIN = 2 * BOARD_FIT
"""How much wider than the board's own acoustic port the inlet's throat is,
where the two meet at BOARD_TOP. The throat itself is not a number here: it is
that drill plus this, read at build time through board.npth_pads("MK1") by
case.mic_port_drill(), because the drill belongs to the board and copying it
into this file is how the two quietly stop agreeing.

There is a margin at all for two reasons, and the larger of the two wins.

Alignment. The cavity walls locate the board, so the board can sit up to
BOARD_FIT off centre in any direction and the drill moves with it. The throat
must still uncover the whole drill at that offset. A margin of twice BOARD_FIT
leaves half of it, BOARD_FIT, per side all the way round, which is exactly the
offset the board can have.

Printing. A bore near a single extrusion width does not survive slicing: the
perimeter closes over it. This keeps the narrow end at several extrusion widths,
which is the floor a small bore in a printed part has regardless of what it is
for. The alignment margin is already above that floor."""
MIC_MOUTH_D = 4.5
"""How wide the inlet's mouth is at the top ring of its fillet band, and so the
widest the inlet ever is: the bore is a funnel, bell at the pocket floor and
throat on the board's own port, and this is the bell. An outright width rather
than a multiple of the throat, which is what it used to be: the throat is the
board's number now, and tying the bell to it would mean a different drill
quietly resizing the one dimension the inlet exists for.

A concave fillet rather than the countersink this was, over the last of the way
out. A cone meets the face along a sharp circular corner. The fillet band meets
the recess floor in one shallow edge instead, which is what an inlet a finger
and a stray draught both arrive at wants. On the recessed front the band rides
the dished floor and its top ring runs MIC_MOUTH_LIFT above it, so the floor
cuts the band just inside this width: the visible mouth, case.mic_floor_edge_r(),
is a little narrower than this. case.mic_fillet_r() is the radius, and it is not
free either: it is this mouth less wherever MIC_TAPER_SHARE leaves the taper,
that being the one radius that carries the arc out from the taper's top to here.

Bounded by the duct it is drilled through rather than by anything acoustic: the
mouth is where the bore comes closest to the outside of MIC_DUCT_OD, so it is
the one height the wall is at risk at, and check.py's mic fillet pass reports
what is left. The 4.5 mm mouth keeps the original 0.7 mm radial duct wall by
growing the duct alongside it."""
MIC_MOUTH_LIFT = 0.01
"""How far above the recess floor the top ring of the mic's fillet band runs, on
the recessed front. It sets where the floor cuts the band, about
sqrt(2 * r * MIC_MOUTH_LIFT) inside MIC_MOUTH_D / 2, and the crease there, about
acos(1 - MIC_MOUTH_LIFT / r), with r = case.mic_fillet_r(). A larger lift moves
the edge in and sharpens the crease.

Not zero, because a band tangent to the floor along a whole ring is a
coincident tangent contact that the boolean cannot resolve. It must also exceed
how far the built floor strays from face_floor_at() round the port. Otherwise a
sliver step comes back wherever the built floor is the higher of the two."""
MIC_TAPER_SHARE = 0.25
"""How much of the run out from throat to mouth the taper's cone does, the
fillet finishing the rest. So it is where the two meet, at the base of the fillet
band, stated as a share rather than as the multiple of a fixed bore it used to
be, there being no fixed bore left to state it against.

The taper is the point of the shape. MK1 sits under the board and listens up
through a port hole several times narrower than the bell, so the sound arrives at
the narrow end: a bore of one width the whole way is a tube standing in front of
that hole, and a cone gathering down onto it is a horn. Spending most of the run
on the cone is what puts the gather over the duct's whole height instead of
crowding it into the last of the way out.

Between 0 and 1, and both bounds are real rather than nominal. At 0 there is no
cone and the bore steps straight off the throat. At 1 the cone arrives at the
mouth's own width, which leaves case.mic_fillet_r() at zero and the mouth with a
square corner on the face instead of the fillet it is there for. The cone stays
shallow across that whole range, the duct being far taller than the bore is wide,
so what moves with this is the split rather than anything about printability."""
MIC_DUCT_OD = 5.9
"""Outside of the duct, the post standing from the board up to the front face
with the funnel drilled through it. This keeps 0.7 mm of radial post wall at
the 4.5 mm mouth. Set outright rather than derived from the
bore plus TUBE_WALL, the way it was while the bore was one width: the bore is a
funnel now, so a wall referenced to it would have to name a height, and the
post's outside answers to things that have nothing to do with which height that
is. It has to miss the courtyards it stands over, which check.py's feature
clashes pass holds; it has to sit inside KEYPAD_ISLAND_2 alongside SW1 and SW2,
which the keypad pocket passes hold; and it has to leave wall around the bore at
the bore's widest, which the mic fillet pass holds. Those three, not TUBE_WALL,
are what this is sized against.

It is a solid post rather than the tube it was. A tube's own straight bore is
cut before the funnel is, so it would erase every part of the funnel narrower
than itself, which since the throat came down off the board's drill is most of
the funnel's length."""
MIC_TUBE_CLEARANCE = 0.6
"""MK1 is on the board's bottom side, so its port faces the back shell across the
whole depth of the cell cavity. A tube couples it to the outside rather than
letting it talk to a 21mm box."""
TUBE_WALL = 1.2
UNMODELLED_DEPTH = 6.0
"""How far a part with no 3D model is assumed to hang below the board, used only
to keep the cell clear if the assembly STEP omits a component."""
IR_CLEARANCE = 0.5
"""Margin around U2's complete multi-solid envelope from
board.part_envelope("U2", radius=3.0). It alone sets aperture size.

U2 receives through the back along -Z."""
IR_EMITTER_FIT = 0.2
"""Radial assembly clearance around D1's measured lens at the bore throat."""
IR_EMITTER_CHAMFER_ANGLE = 45.0
"""Chamfer angle per side from D1's optical axis."""
IR_EMITTER_CHAMFER_DEPTH = 0.60
"""Axial chamfer depth from the outer end face. It opens the bore around the
lens tip and keeps a lower lip at the back shell's end roll."""
IR_RELIEF_DEPTH = 1.5
"""How far inside the board edge an end-wall cut reaches, shared by D1's
emitter bore and the USB shell's slot. Both are
through-cuts, so the outward side is not this: it runs well past the exterior
face, and this governs only the inward side, the reach back into the cavity
that connects the opening to it. U2's bottom aperture does not use this."""

# IR window: stepped inside-fit insert closing U2's -Z aperture in the back.
IR_WINDOW_T = 1.15
"""Optical pane thickness from conformal exterior face to interior shoulder.

It is also the shell left over the rebate, because the rebate stops one pane
thickness above the exterior. The back form is curved, so a 1.0 pane left the
shell reading 0.97 normal to that surface, under the PA12 minimum. This value
carries the reading clear of it."""
IR_WINDOW_FLANGE = 0.8
"""Interior flange reach past aperture per side: outward retention and adhesive land."""
IR_WINDOW_FIT = 0.20
"""Clearance per side around flange in rebate; adhesive fills perimeter gap."""
IR_WINDOW_PANE_CLEARANCE = 0.20
"""Clearance per side between the optical pane and the aperture."""
IR_WINDOW_FLANGE_T = 0.8
"""Interior flange thickness, recessed below cavity floor to preserve U2 clearance."""
IR_WINDOW_R = 1.0
"""Corner round on aperture, inherited concentrically by pane and flange."""
USB_CLEARANCE = 0.5
"""Clearance per side around the measured outline of the USB shell in the -Y end
wall. The end screw block also keeps this clearance from the U1 module envelope.
In both places, it must not be less than BOARD_FIT, because the board can sit
BOARD_FIT off centre."""
USB_BOOT_W = 12.5
"""Width of the outside pocket in the -Y end wall for the cable boot. The pocket
outline is an allowance for common USB-C cable boots, not a measured part. A
larger boot does not enter the pocket, so its plug does not seat. The first
print must verify plug seating."""
USB_BOOT_H = 6.6
"""Height of the cable boot pocket. It is an allowance, as USB_BOOT_W is."""
USB_BOOT_R = 1.5
"""Corner radius of the cable boot pocket. It is an allowance, as USB_BOOT_W is."""
USB_BOOT_REACH = 0.35
"""Largest distance from the boot pocket floor to the receptacle mouth while the
plug pushes the board +Y by WHEEL_OPENING_CLEARANCE. A plug extends
approximately 6.65 mm past its boot, and the receptacle shell is 6.20 mm deep.
As a result, the boot must stop within approximately 0.45 mm of the mouth, and this
value keeps a 0.1 mm margin. With this value, the floor is just outboard of the
front skirt."""
USB_BOOT_RIM_R = 0.6
"""Radius at the outside mouth of the USB boot pocket."""
BACK_STL_ANGULAR_TOLERANCE = 0.06
"""Angular deflection in radians for both back shells. This keeps the mesh
closed at the USB rim."""
RESET_BORE_D = 1.6
"""Bore diameter with clearance for a straightened paper clip."""
RESET_CHAMFER_W = 0.5
"""How far the countersink at the outer end of the reset bore reaches past the
bore on its -Y side. Measure it flat, out from the bore wall.

The bore leaves the back where the floor rolls up into the -Y end wall. Without
the countersink, the -Y rim is a knife edge of about 61 degrees, and the fab pass
read it as a 0.12 mm taper. The countersink makes each rim edge obtuse.

The thinnest wall that stays is on a ray from the -Y mouth up to the bore wall.
That ray reads this width divided by the sine of the floor slope at the mouth,
which is about 34 degrees. At 0.45 the ray just clears FAB_MIN_WALL["SLA"], and
0.5 gives a margin of 12%. The countersink also gives a paper clip a lead-in."""
RESET_CHAMFER_ANGLE = 45.0
"""Half angle of the reset countersink about its own axis, in degrees, so 45 is
a 90 degree countersink. A smaller angle makes the mouth narrower across x."""
RESET_CHAMFER_TILT = 12.0
"""How far the axis of the reset countersink leans from the bore axis toward -Y,
in degrees.

The floor under the bore slopes about 16 degrees at the +Y rim and about 34
degrees at the -Y mouth. So a countersink on the bore axis opens much wider on
the +Y side, about 4.3 mm by 3.8 mm. With this lean, the mouth is almost the same
width all round the bore, about 3.0 mm by 2.6 mm.

More lean makes the mouth smaller on the +Y side. At 16 degrees the thinnest ray
moves to the -Y bore wall above the countersink. At 20 degrees that ray is under
FAB_MIN_WALL["SLA"]."""
RESET_GUIDE_WALL = 1.05
"""Guide wall thickness, just over the PA12 minimum that PCBWay publishes for
SLS. It was 0.8, two 0.4 mm extrusion widths, which is an FDM rationale that no
longer applies to a printed shell. At exactly 1.0 the whole tube measured the
minimum, which the fab pass reads as a hair under."""
RESET_GUIDE_GAP = 0.6
"""Minimum gap between the guide tip and the RESET contact face."""
RESET_GUIDE_TOP_DROP = 1.8
"""How far the guide stops below the front skirt, on top of SKIRT_FIT.

The guide tube sits about 2 mm off the case centreline, so near its top the
rolled back form shaves the outboard side alone. At the full height the
inboard wall measured RESET_GUIDE_WALL and the outboard wall fell to 0.605
over the last 1.5 mm. A fatter tube does not help, because the form cuts at a
fixed place whatever the tube's diameter. This value ends the tube below that
band, so every remaining wall is the full thickness.

The cost is guide length. The clip leaves the bore about 2.6 mm under the
RESET contact rather than 1.1 mm. The bore holds the clip's angle over roughly
9 mm before that, so the tip lands within about 0.2 mm of where it would have.

The value is measured off the built form, not derived from it. If the back
contour moves, the fab pass flags the guide again."""
QWIIC_CLEARANCE = 0.5
"""Clearance around the Qwiic housing for a plug approach from the left side."""
QWIIC_CORNER_CHAMFER = 0.3
"""The small corner trim stays within the connector clearance at each corner."""
QWIIC_SKIRT_CLEARANCE = 0.2
"""The hidden front skirt clears the port roof and joins the adjacent support reliefs."""
QWIIC_KNOCKOUT_T = 1.05
"""The flush cover, just over the PA12 minimum that PCBWay publishes for SLS.
It was 0.8, two 0.4 mm extrusion widths. The cover follows the curved back
form, so a flat 1.0 read 0.99 normal to that surface, the same way the IR
window rebate did. The extra 0.05 carries it clear.

A thicker cover is harder to break out, and PA12 bends where resin snaps, so
the knockout needs a cut test on the first print."""
QWIIC_KNOCKOUT_GAP = 0.3
"""The border separates the cover from the wall except at two side bridges."""
QWIIC_KNOCKOUT_TAB_W = 0.8
"""Each side bridge spans four 0.2 mm layers from the panel's lower edge."""
QWIIC_KNOCKOUT_TAB_T = 1.0
"""The two bridges at the PA12 minimum that PCBWay publishes for SLS. It was
0.8, two 0.4 mm extrusion widths. The bridges are what the operator breaks, so
they share the cut test of QWIIC_KNOCKOUT_T."""
QWIIC_KNOCKOUT_ANCHOR = 0.4
"""Each bridge overlaps the panel and wall to keep the back shell one solid."""
BATTERY_PLUG_REACH = 7.0
"""Free space past the PicoBlade mouth for the plug and wire bend.
This is a routing allowance, not a measured plug dimension."""
BATTERY_PLUG_CLEARANCE = 0.5
"""Clearance around the battery connector height and width for the mating plug."""

# Button pad: one soft moulding, flat web with raised keys. The moulded pad has a
# skirt on each lobe's outer edge. Held up against the ceiling by its own
# plungers resting on the switches.
PAD_WEB_T = 0.8
"""Thickness of the pad's flat web, and so the height of the front cavity.

CAVITY_FRONT is PAD_WEB_TOP. This value therefore sets the front shell's inner
ceiling for the whole cavity, not for the keypad alone.

It was 1.2, and the ENC1 lip held it there. The lip is a static flange under
the fixed bezel, wider than the wheel opening. The flat ceiling over it left
only 0.555 of air, which is less than two SLS tolerance bands.

wheel_lip_relief() lifts the ceiling off the lip. That raises the gap to 1.155
and frees this value. See WHEEL_LIP_RELIEF.

Each 0.1 off this value adds 0.1 to every counterbore land, because
COUNTERBORE_TOP is built off CAVITY_FRONT. At 0.8 the lands take 0.4 of the
0.506 that they needed. FACE_CROWN_OVER_WHEEL carries the remaining 0.106, so
the front is 0.4 shorter than the face alone would have made it.

U3 holds it here. The expander is the tallest part that no pad lobe covers, so
the ceiling must clear it directly. It keeps 0.605 of air at this value, about
twice the tolerance that PCBWay publishes for SLS. The lip keeps 0.755.

The value is four 0.2 mm layers. FDM_PAD_GROOVE_DEPTH is two, so the printed
pad keeps its 0.4 hinge on whole layers.
"""
PAD_SKIRT_T = 1.2
"""Width of the moulded pad's skirt wall, measured inward from the lobe outer edge.

The outer face of the wall is flush with the web edge, so the pad keeps its plan
outline. The wall is wide enough to mould and to stiffen the lobe edge.

The one-piece TPU pad has the same skirt, and PCBWay recommends a wall of at
least 1.2 for an FDM print. So the wall is 1.2 and not 1.0.
"""
PAD_SKIRT_CLEARANCE = 0.3
"""Gap from the pad skirt to any board part, in plan and in height.

A board part whose top is within this distance of the skirt bottom, or above
it, and whose plan box grown by this distance reaches the skirt, breaks the
skirt. The switch bodies count, through SWITCH_BODY. On the V3 board no part
breaks the skirt. The V2 top pad breaks its own skirt over the parts its board
puts there, which include the V2 SW1 and SW2 bodies.

This is also the gap the pad keeps from the ring insert's lobes, in
pad_keepouts().
"""
PAD_SKIRT_DEPTH = 1.6
"""How far the moulded pad's skirt wall drops below the web.

The wall stops PAD_SKIRT_CLEARANCE above the board face, the deepest it can go.
stack.py fails if a larger value takes it closer. The clearance is more than
SWITCH_TRAVEL, so a press near a lobe edge cannot put the wall on the board.

No board part stands under the wall in plan. C1, C3, R1, R4 and R5 moved
clear of the lobes, so the depth breaks nothing. It was 0.75 while C3 and R1
stood under the top lobe and R5 under the grid lobe's edge."""
FDM_PAD_GROOVE_W = 1.2
"""Width of each press-isolation relief in the rigid FDM grid lobe.

Wide so each printed key can flex with less
drag from the neighbouring web while still clearing stems and cap seats.
"""
FDM_PAD_GROOVE_DEPTH = 0.4
"""Depth cut from the keytop face only of the FDM pad web at an isolation relief.

The plunger face stays flat, so the pad prints keytops up with clean supports
under the web (support removal, 2026-09-29). The hinge left at the underside is
PAD_WEB_T - FDM_PAD_GROOVE_DEPTH thick.
"""
FDM_PAD_GROOVE_EDGE_OVERTRAVEL = 0.6
"""How far each FDM isolation relief extends past the grid-lobe bounds.

Equal to half FDM_PAD_GROOVE_W so the rounded relief is at full width where it
exits the lobe instead of tapering to a tangent point at the edge.
"""
FDM_PAD_GRID_CHAMFER = FDM_PAD_GROOVE_DEPTH
"""Leg of the 45 degree chamfer on both top lips of every FDM isolation relief.

The lip chamfer reaches the groove floor, so each relief has 45 degree walls
over a flat floor FDM_PAD_GROOVE_W wide. It must stay at or below
FDM_PAD_GROOVE_DEPTH and short of each keytop base. The grid lobe's outer top
edge takes FDM_PAD_EDGE_CHAMFER instead.
"""
PAD_MARGIN = 0.15
"""Web left past the widest thing over the pad, on every side of each lobe.

Each lobe is the hull of its own keycaps, each drawn on the keycap
superellipse at half cap_flange() plus this value. The rigid cap's flange is
the widest part over the pad. The fused TPU and FDM keytops, the stems and the
plungers are narrower, so the pad covers all of them. Each corner follows the
corner cap's own curve.

Where a lobe reaches a wheel keep-out, pad_lobe_face() notches it. The D7 ring
lobe takes the one notch under a key, so the SW6 flange overhangs that notch.

The board keeps its parts clear of this outline by PAD_SKIRT_CLEARANCE, so no
part breaks the skirt. A larger value needs the same clearance from C1, R1 and
the ring-lobe notches."""
FDM_PAD_EDGE_CHAMFER = 0.15
"""Leg of the 45 degree chamfer on the FDM grid lobe's outer top edge.

It must be at most PAD_MARGIN, so the chamfer stops short of each outer keytop
base. As a result, the outer key tiles do not slope down to hinge level as the
groove lips do."""
PAD_JOIN_RADIUS = 1.5
"""Round on the convex corners that the pad's notches leave: where the mic
clearance circle meets the top lobe's edge, and at the mouth of each notch for
pad_keepouts(). pad_lobe_face() cuts a notch only where a lobe reaches it."""
PAD_FIT = 0.3
"""Least gap from each pad lobe to the front's stiffened inner wall.

pad_lobe_face() clips each lobe to this gap. At the present outline the lobes
stop short of it, so the clip is idle. checks/keypad.py holds the gap as a
minimum on the built pads.

The lobes stop short of the wall, so each lobe has two locating tabs that run
out to this gap, see PAD_TAB_W. The tabs are what reads this gap now."""
PAD_TAB_W = 4.0
"""Length along y of each locating tab on the long sides of a pad lobe.

Each lobe has one tab on each long side, at its mid-length. Each tab runs from
the lobe edge out to the PAD_FIT line, so the pad floats no more than PAD_FIT
each way in x, inside SOCKET_LEAD. Without the tabs it floats about 1.5.

The tab reaches about 1.6 in x. This length is about 2.5 times that, so the
soft tab pushes the lobe across and does not fold over. A longer tab locates no
better and only adds a flap. On a pad with a skirt, a 45 degree chamfer under
the tab runs down into the skirt, so the tab prints with no support. The FDM pad
has no skirt, so its tabs are web only."""
PAD_TAB_RADIUS = 0.75
"""Corner round on the outer corners of each locating tab. It must be less than
half the tab's reach in x, so the outer edge keeps a straight run to bear on the
wall."""
PAD_MIC_CLEARANCE = 0.3
"""Gap from the pad to the mic duct's widest chamfer at the ceiling."""
PLUNGER_D = 2.5
"""Contacts the switch actuator. Reaches from the web down to SWITCH_HEIGHT."""

# Keypad recess: one continuous concave recess sunk into the front face, with
# no flat floor and no wall anywhere. Three superellipse-bounded dishes along
# one centreline, over the nine-key grid, over KEYPAD_ISLAND_2 and the mic
# inlet, and around the wheel, joined into a single C1 depth field by two neck
# channels that ramp between them. A cap stands CAP_PROTRUSION above the face,
# plus whatever the recess is locally deep under it.
KEYPAD_SQUIRCLE_N = 4.0
"""Exponent of the superellipse the two keyed basins are bounded by, and of the
keycaps' own plan shape with them: one curve for everything square on the front
face, so a cap reads as belonging to the recess it sits in rather than as a
different family of shape dropped into it. Four is also where an iOS app icon
sits, which is the reference for how a keytop of this size should look.

For the basins:
|dx/ax|^n + |dy/ay|^n = 1. Four is the squircle: full round at n=2, sharp
rectangle as n grows, and 4 is the value that reads as a rounded rectangle
whose corner never stops turning. It also sets how far past its own coverage
box a basin has to reach, since a superellipse only touches the box at the
four edge midpoints and the corners of the outermost keys sit well inside
those: case.keypad_recesses() grows each half axis by 2^(1/n) so the box's own
corners land on the curve, which at n=4 is a growth of about a fifth.

The wheel's basin has its own, see WHEEL_SQUIRCLE_N. A basin that is a field of
square keys wants a rounded rectangle; one that is a ring around a round knob
does not."""
KEYPAD_PROFILE_POINTS = 80
"""Points the floor profile across one loft station is drawn through. A
polyline rather than a fitted spline so every station carries the same vertex
count and the loft between them has nothing to match up. The points sit at the
same fractions of the half width on every station, placed by arc length and by
how far the floor turns there, so the rims and the face's fall toward the
side walls get most of them. At this count no two neighbouring facets differ by
more than about two degrees."""
KEYPAD_RECESS_STATIONS = 20
"""Stations per dish half the recess is lofted through before refinement,
spaced by the superellipse's own parameter rather than evenly in y: both the
half width and the depth turn fastest at a rim and barely at all in the middle,
so even steps in the parameter put the stations where the turning is.
keypad.recess_stations() then adds stations wherever the loft would crease."""
KEYPAD_NECK_STATIONS = 12
"""Extra stations across each neck before refinement, evenly spaced. Nothing is
singular there, and the two Hermite halves want resolving on their own terms
rather than on the spacing the neighbouring dish's rim happens to leave."""
KEYPAD_TIP_WIDTH = 0.15
"""Half width the outermost station still carries, as a fraction of that dish's
own half axis, in place of lofting to a point. A degenerate section is what
makes a loft come back non-manifold. It costs nothing in fidelity: a
superellipse's own end is flat to within microns over this much of its width,
so the blunt tip it leaves sits a few thousandths inside the true rim at a
depth of almost nothing."""
KEYPAD_DISH_DEPTH = 0.87
"""How deep the grid recess is at its own centre, measured down from the
face. SW7 sits at that centre.

Every dish follows the face, so the face lowers the floors toward the side
walls by its own drop. KEYPAD_LIP_LIFT gives part of that drop back near
the outer key columns. Each counterbore land is the lowest floor over the
counterbore less COUNTERBORE_TOP, and check.py holds it above LAND_FLOOR_MIN.
At this value the thinnest land is about 0.54, on SW4, under the outer edge of
the key. Above about 1.08, the land on SW7 is the thinnest. It reaches
LAND_FLOOR_MIN at about 1.28. Both values assume that KEYPAD_DISH_DEPTH_2
moves by the same amount."""
KEYPAD_DISH_DEPTH_2 = 0.67
"""Depth of the second dish at its own centre, measured down from the
face. It is shallower than the grid's because it is less than half as wide in
y. The same depth would curve it visibly harder. The value sets a cap on SW1
or SW2 about as proud as a cap on the grid's outer ring. It changes by the same
amount as KEYPAD_DISH_DEPTH, so the two depths keep their 0.2 difference."""

KEYPAD_JOIN_REACH = {
    "grid": 3.0,
    "wheel": 7.0,
    "second": 2.0,
}
"""How far inside its own rim each basin lets a join begin, keyed by basin. The
wheel's applies to both of its joins.

Per basin rather than per join because that is where the constraints are. What
each number really buys is join roundness: the two reaches either side of a join
are the whole length its plan outline has to turn through on the way from one
rim into the other, so bigger is a wider, gentler flare and smaller is a tight
pinch. check.py measures the radius that comes out and holds a floor under it.

There has to be some reach at all. The sag's tangent at a rim is vertical, so a
bridge that left one there would dive straight through zero and tear the recess
in two; a bridge starting this far in leaves from a finite slope on a floor that
is already a few tenths down. What it costs is the basin's own inboard rim, which
is the point: past this the superellipse stops and the join takes over, and only
the outboard halves of the two outer rims are still the curve.

The two keyed basins are held down by their own outermost key row. Past that a
reach starts reshaping the floor over those keys' counterbores rather than only
outboard of them, which costs no land (the deepest point over a counterbore is
always the one furthest inboard) but does start eating the basin's own surface
where the keys are.

The wheel's is much the largest, and two things make it so. A lower
WHEEL_SQUIRCLE_N is a narrower chord at any given distance from the centre, so
the same reach leaves a join less width to turn through; and a larger
WHEEL_BASIN_SPREAD pushes the basin's rim toward its neighbours, which shortens
the span a join has to turn over. Both cost radius and both are paid for here.
It has room to: no keys sit under that basin, so the only bounds are structural,
that a reach may not pass its own basin's centre and that the wheel's two joins
may not run into each other.

Every reach here takes its join past the wheel opening's bore, so on the two
bearings a join leaves on there is no wheel arc left in the seat at all: the
join flows straight out of the bore wall. That is why the seat reads deeper on
those two bearings than on the free axis."""
KEYPAD_NECK_MIN = 18.0
"""Narrowest the recess may get anywhere at a join, as a full width.

A floor rather than a target, which is the change that made the joins round. It
was once a waist the width was driven to, built as two cubics meeting at the
neck's midpoint with zero slope; forcing that flat spot is what put a tight
corner in the plan outline, and dropping it for one cubic across the whole join
roughly tripled the radius at the same reach. So the waist is now whatever the
two dishes and the reach leave, and this is the bound that says it has not
closed up. Read as a fraction of the wheel's own dish it is a bit over half."""

KEYPAD_MARGIN = 0.5
"""How far a recess's coverage box reaches past its outermost key, and so the
least dish there is around any key in the axis directions. The superellipse is
grown to bound that box, so on the axes it reaches further than this and at the
corners it reaches less; check.py holds the real floor, which is the whole of
every counterbore staying inside its own dish."""
KEYPAD_EDGE_MARGIN = 1.5
"""How clear a recess's own rim is kept of the case's exterior wall. It is a
fixed margin, not sized off the recess geometry, so a future edit to the edge
treatment is what check.py's guard would catch rather than the two quietly
trading margin.

Live, not idle: the grid's coverage box is wide enough that the superellipse
bounding it would reach inside this, so case.keypad_recesses() caps that half
axis here instead. The keys still sit inside the curve with room to spare; what
is given up is dish beyond the box's own corners.

The rim chamfer's top round starts RECESS_CHAMFER_ROUND_OUT outside the rim,
so the face is cut to within this margin less that of the wall."""
RECESS_CHAMFER_W = 1.0
"""Width in plan of the rim chamfer, on the recessed front only. The chamfer
runs all the way round the merged recess, from the rim in toward the dish.

In each section normal to the outline, the chamfer starts with the top
round, RECESS_CHAMFER_ROUND_W, and ends with the inner round,
RECESS_CHAMFER_INNER_ROUND_W, on the dish floor at this distance in. Any
width that the two rounds leave is straight. The two rounds fill the width
now, so the section is one S-curve from the face to the dish. The chamfer
replaces the soft roll the dish had, so WHEEL_RIM_SOFT, KEYPAD_RIM_SOFT and
KEYPAD_RIM_SOFT_2 are zero.

The chamfer does not move the rim outline. recess_outline(), the FDM front's
groove and the outline that the renders read stay where they are. The top
round starts RECESS_CHAMFER_ROUND_OUT outside that outline. If this value is
zero, the front has no chamfer, and the dish runs to the rim."""
RECESS_CHAMFER_ROUND_W = 0.5
"""Width in plan, inside the outline, of the round at the top edge of the rim
chamfer, where the chamfer meets the face. With RECESS_CHAMFER_INNER_ROUND_W
it must not be wider than RECESS_CHAMFER_W.

In each section the round is a parabola. It leaves the face
RECESS_CHAMFER_ROUND_OUT outside the outline with the face's own slope, and
it meets the rest of the section at the same slope. As a result, the rim has
no sharp crease. The built round leaves the face 0.04 to 0.15 inside its
start, at 0.4 to 1.6 degrees. A ring exactly on the face would make the shell
cut fail."""
RECESS_CHAMFER_ROUND_OUT = 0.5
"""How far outside the rim outline the rim chamfer's top round starts, on the
face. The round then has this much more width to turn in, so it is gentler.
On the wheel's east and west sides, where the face still rises to the crown
at the rim, it turns at about 41 degrees per mm, against 92 when it starts on
the outline. The round cuts the face out here, so the face is cut to within
KEYPAD_EDGE_MARGIN less this value of the side wall. The outline, the FDM
front's groove and the dish do not move."""
RECESS_CHAMFER_INNER_ROUND_W = 0.5
"""Width in plan of the round at the inner edge of the rim chamfer, where the
chamfer meets the dish floor. With RECESS_CHAMFER_ROUND_W it must not be
wider than RECESS_CHAMFER_W.

In each section the round is a parabola that ends on the dish floor at
RECESS_CHAMFER_W with the floor's own slope. It curves up into the dish all
the way round. The dish and the inner edge do not move. If this value is
zero, the chamfer meets the dish at a crease."""


# FDM front: a second front shell for a filament printer. Its face carries the
# recess's plan outline as a shallow engraved slot and is otherwise one flat
# plane, so nothing on the cosmetic surface needs support.
#
# The recess cannot be printed face down. It is a dish a few tenths deep over a
# span of tens of millimetres, so its floor is a near-horizontal ceiling a
# fraction of a millimetre off the build plate: too shallow to bridge and too
# wide to span, and support under it prints directly against the one surface on
# the case that is looked at. Face up is no better, because that stands the
# whole cavity on its ceiling. So this variant gives up the dish and keeps the
# line it drew, which a slot narrow enough to bridge can carry.
#
# Nothing else about the shell changes. The caps follow CAP_PROTRUSION from the
# recessed front's face, so they stand an additional FDM_FACE_DROP above this
# lower flat one; each
# counterbore keeps the whole of DISH_HEADROOM as land instead of giving a dish
# depth up to it; and the mic inlet's mouth already runs at constant radius to
# the face, so it opens as a plain hole rather than in a curved floor. What is
# given up with the dish is the finger access around the wheel: the seat that
# dished down to the knob's own lip is flat here, so the wheel is reachable
# across its top face only.
FDM_FACE_DROP = 0.875
"""How far the FDM front's outer face sits below the recessed front's.

The recessed front's face is the raised land the dish is sunk out of. Flatten
that dish and the face has to land at one height or the other, and the raised
one leaves a part thicker than the one it replaces for no reason: the material
the dish took out is simply kept. So this front's face lands at the sunken
level instead, and the part comes out that much slimmer.

The LED channel roof and the counterbore lands limit the drop. The built-shell
checks hold both thicknesses. The underside USB connector needs no front pocket.

FDM_FACE is SHELL_FRONT less this value. If FACE_CROWN_OVER_WHEEL moves the
crown, change this value by the same amount to keep the FDM face where it is.

Caps and the wheel stand this much further proud of the face here than on the
recessed front. Here the caps stand about 1.38 to 1.63 above the face. On the
recessed front they stand about 1.28 to 1.62 above the dish floor. As a result,
a cap on the flat face looks like a cap in a slightly shallower dish. The wheel
standing proud gives the knob back some of the finger access a flat face takes
from it.

checks/fdm.py reads all three ceilings off the built shell, against the same
floors the recessed front's own passes hold them to."""
FDM_OUTLINE_W = 0.6
"""Full width of the engraved outline in the FDM front's face. One 0.6 mm
extrusion gives a fine marking that can bridge face down without support.

The groove is centred on the rim, so it reaches half of this further out than
the rim itself does. EDGE_R_FRONT_FDM keeps its outer edge on the flat of the
top chamfer rather than moving the outline off the rim."""
FDM_OUTLINE_EDGE_CLEAR = 0.3
"""Flat face kept between the groove's outer edge and the inner edge of the
FDM front's top chamfer. What it bounds is EDGE_R_FRONT_FDM.

Not cosmetic. At zero the two edges are coincident, and two coincident edges in
one plane crack a triangulation: the solid stays valid, its bounding box and
widths all read correctly, and the exported STL comes back with nine open edges
along the face. checks/shells.py's parts_are_sound() is what catches that, and
it is the only pass in the model that would. This model has already shipped
that exact failure once. It also buys the same print-safety buffer
KEYPAD_EDGE_MARGIN carries, and for the same reason."""
FDM_OUTLINE_DEPTH = 0.2
"""How far that outline is sunk into the face. One 0.2 mm layer makes a subtle
marking and leaves more material below its bridge.

It has to stay under LED_RING_ROOF as well. The recess's rim passes within a
few hundredths of the LED ring channel's outer wall either side of the wheel,
so a small change on either side puts this groove over a roof that has to carry
the light, and what would be left there is LED_RING_ROOF less this.
checks/fdm.py holds the floor under it for that case rather than for the
clearance the present layout happens to have."""
FDM_LED_RING_DEPTH_RATIO = 0.8
"""LED ring channel depth on the FDM front, as a fraction of the recessed
front's arch depth on the crown line, from CAVITY_FRONT up to LED_RING_TOP.

The flat FDM face does not need the full-height light-spreading void used below
the dished face. A shorter channel keeps it open over the LEDs and gives a
thicker printable roof. This changes only the FDM front. On the recessed front
the ceiling rises above the arch under the face. The outer rake starts that much
higher at the mouth and keeps the arch depth as its height. checks/fdm.py
measures both built shells and holds this ratio. On the recessed front it reads
the height of the outer rake on the crown line.

It was 0.5. wheel_lip_relief() raised the channel's inner floor to
LED_RING_FOOT, and the FDM channel was then too short to hold its inner
chamfer. The chamfer is LED_RING_INNER_CHAMFER and it hangs from the ceiling,
so the ceiling must stand that far above LED_RING_FOOT, plus
LED_RING_INNER_FOOT_MIN. This value leaves a foot of about 0.16.

The cost is the roof under the flat face, which falls from about 1.61 to about
1.12. The mouth still opens at CAVITY_FRONT, so this fraction keeps its old
meaning and checks/fdm.py needs no change.
"""
FDM_WHEEL_OPENING_CLEARANCE = 0.2
"""Extra radius the FDM front's own wheel opening carries, over and above
WHEEL_OPENING_CLEARANCE, so the printed bore clears the wheel's main rotating
body by both together instead of by the moulded front's gap alone.

This front only. The recessed front opens the top of its bore with the keypad
recess's wheel basin, a dish on the same axis whose floor the bore breaks
through, so the knob already has a lead-in there and the tight gap below it
reads as a visible line rather than as a fit. Flatten the dish and the bore
meets the face as a square arris with nothing above it, and the fit is the
whole of the story. A printed bore also comes back tighter than the solid it
was cut from, which the moulded one does not.

It cannot simply be more WHEEL_OPENING_CLEARANCE. led_ring_inner_r() is
WHEEL_OPENING_R plus LED_RING_WALL, so widening that radius drags the LED ring
channel outward with it and off the LEDs the channel is built over. So this is
applied to the FDM shell's bore alone and is spent out of that shell's own web
rather than out of the channel's position.

The web is what bounds the bore. The mouth chamfer may spread past the inner
wall in plan only where the FDM channel has already ended below it;
wheel_opening() checks their actual height overlap."""
FDM_WHEEL_OPENING_CHAMFER = 1.2
"""Lead-in at the mouth of the FDM front's wheel opening, a 45 degree cone
opening the bore out by this much over this much height, ending at the face.

The recessed front wants none, for the same reason it wants no extra
clearance: its wheel basin is already the lead-in, a saucer the knob drops
into. This front's face is flat, so what the knob meets going in is the square
arris where the bore breaks it, and this replaces that arris with a ramp.

45 degrees because the front prints face down. The face lies on the bed and the
hole narrows as it rises off it, so the cone is a self supporting overhang
rather than a ceiling the slicer has to bridge or prop, which is the same trade
FDM_FACE_DROP and the outline groove are built on.

The FDM ring channel is shorter than the recessed front's. At this depth the
cone starts above its roof, so the mouth may be wider than LED_RING_WALL in
plan without cutting into that channel. wheel_opening() checks the cone radius
at the channel's actual top, and checks/fdm.py reads the cone off the built
face."""


# Keycaps: every switch carries a rigid translucent cap over a soft stem
# moulded into the pad, so a legend change is one small reprint rather than a whole
# pad. Each cap is captive. A flange at its base rides a counterbore sunk into the
# ceiling and is wider than the hole through the face above it, so the cap goes in
# from inside and cannot leave through the face.
KEYPAD_ISLAND_2 = ("SW1", "SW2")
"""Which two switches, plus the mic inlet beside them, form the keypad
pocket's second island rather than the nine-key grid's own. A coverage
grouping only now, decoupled from what this pair used to also be,
MOLDED_KEYS: the mounting holes that once cut key_size() back for these
two, forcing a moulded keytop instead of a cap, moved and now leave both
at the full grid size, so they take a cap like every other switch. The
island split stays, since it is still the right footprint grouping (these
two plus the mic sit apart from the grid), it just no longer implies
anything about cap versus keytop.

Keep in board order if this ever grows past a pair: keypad_coverage() does
not sort it."""

CAP_PROTRUSION = 0.75
"""How far a released cap or keytop stands proud of the front face at the
highest key centre.

Every key top stands at that one level, key_top_level(), so a silkscreen or a
laser marks every legend in one pass. The face falls toward the side walls, so
the keys in the outer columns stand prouder of the face than the centre column.

This value is larger than SWITCH_TRAVEL. A full nominal press leaves the top
proud of the face by the difference, so a pressed top stays above the face.
CAP_GUIDE_CLEARANCE leaves each cap room to move through its face hole without
fouling the shell."""
CAP_TOP_T = 1.5
"""Roof over the socket, a shallow locating recess rather than a deep grip.

CAP_PROTRUSION made every cap stand taller over a pad stem that did not change.
The extra height goes into this roof, so the stems and the socket depth stay
the same. LEGEND_DEPTH comes out of the roof. What is left is the translucent
bridge that the pad backlight glows through, so the legend bounds the roof from
below and strength does not."""
CAP_TOP_FILLET = 1.3
"""Radius on the exposed top perimeter of every rigid cap and every FDM or TPU
keytop.

This removes the sharp edge a finger meets without changing the cap's body at
the face hole, its flange, or its captive retention geometry. Three bounds:

The round's lower tangent sits this far below the cap top, while a released cap
stands only CAP_PROTRUSION proud of the face. Above CAP_PROTRUSION, the round
therefore dips into the face hole, and the cap is already curving inward where
it meets the hole rim. At the rim the cap is pulled in from its full
width by about 0.12 mm per side (0.002 mm at 0.8), which only widens the guide
gap there a little and does not affect fit.

It must stay below CAP_TOP_T, so the socket roof stays under the round.

It shrinks the flat top that the legend sits on. legends_present() reads that
flat off the built blank cap and holds LEGEND_INK_MARGIN of bare top around
every legend, so a larger value that runs a legend onto the curve fails there.
This is the binding bound: SW9 and SW11 keep about 0.3 mm of bare top at this
value, so they reach LEGEND_INK_MARGIN near 1.4."""
CAP_WALL = 1.0
"""Thinnest wall the cap may be left with anywhere around its socket. Not a
modelled dimension: the cap's body follows the face hole and its widest bore is
the socket mouth, which stands SOCKET_LEAD out from the bore on each side, so the
wall is whatever falls out between them. check.py holds this floor so future
drift in either number cannot quietly starve it."""
CAP_LIFT = 0.0
"""Air under the cap's flange, from the pad web up to the flange's bottom face.

At zero, the flange rests on the pad web. A press moves the cap, the stem and the
web down together, so the web flex gives SWITCH_TRAVEL. The switch is the bottom
stop. There is no air gap that lets the cap move alone, so a positive value here
adds free play and no travel. The counterbore shoulder stands CAP_FLANGE_FLOAT
above the flange, so it stops the cap only on the way up.
"""

CAP_FLANGE_T = 1.05
"""Thickness of the flange at the cap's base. The flange rests on the pad web.
Its height keeps the cap square on the web, so a thin flange can tilt.

It takes the height that CAP_LIFT gave up when it went to zero. As a result, the
counterbore shoulder stands where it stood before that change. The face land
bounds it from above, and check.py's LAND_FLOOR_MIN holds that land."""
CAP_FLANGE_OVERLAP = 0.6
"""How far the flange reaches past the face hole, per side. This is the retention
now: pull a cap and this is the ledge the face land catches. A cap sitting off
centre spends CAP_GUIDE_CLEARANCE of it, so check.py holds the worst-case
remainder rather than this number."""
CAP_FLANGE_TRIM = 0.2
"""How far the flange is drawn in from the key size, per side. With
CAP_FLANGE_CLEARANCE it puts the counterbore back at exactly the keytop
footprint, so key_size() answers for the counterbore with no second
calculation."""
CAP_FLANGE_CLEARANCE = 0.2
"""Gap per side between the flange and its counterbore. Deliberately looser than
CAP_GUIDE_CLEARANCE: the face land is what holds a cap square, and a counterbore
gripping as tightly would fight it for control of the same axis."""
CAP_FLANGE_FLOAT = 0.15
"""How far a cap lifts before its flange meets the counterbore shoulder. It is
what makes a cap captive rather than clamped, so it still presses freely. Only
STEM_GRIP loads it out, so it is also what a cap rattles through if the grip goes
slack.

Trimmed from 0.2 alongside CAP_LIFT to buy the keypad recesses back out of the
counterbore stack. Still inside check.py's FLANGE_FLOAT_RANGE, with room to
spare unlike CAP_LIFT."""
CAP_GUIDE_CLEARANCE = 0.25
"""Gap per side between the cap body and the face hole it stands in.

A 0.25 mm clearance per side gives the printed cap 0.50 mm total clearance
through the front face. The previous 0.15 mm clearance was too tight for the
printed button and front-shell tolerances. The face land and counterbore still
guide the cap. The retention check holds the flange overlap after this change."""

CAP_GRID_COLUMNS = 3
"""Number of cap columns on the print carrier for a compact layout."""
CAP_GRID_RAIL_W = 2.2
"""Width of the carrier rails so the grid stays rigid during transfer."""
CAP_GRID_END_RAIL_W = 1.4
"""Width of the end rails, which join the side rails without carrying tabs."""
CAP_GRID_END_GAP = 0.6
"""Distance between the widest flange and an end rail to limit the grid length."""
CAP_GRID_CORNER_R = 1.0
"""Radius of the outer corners so the carrier has smooth edges."""
CAP_GRID_INDEX_R = 1.8
"""Larger radius at the SW1 corner to orient the carrier for marking."""
CAP_GRID_GAP = 1.0
"""Distance from the widest flange to the rail for a short FDM bridge."""
CAP_GRID_TAB_T = 1.0
"""Height of each breakaway tab. Formlabs resin needs a 1 mm wall, and the tab stays inside the flange."""
CAP_GRID_TAB_W = 1.0
"""Width of a tab at the flange. The tab widens toward the rail, so it breaks at the flange."""
CAP_GRID_MARK_CLEARANCE = 0.5
"""Minimum distance from engraving to the edge of each flat cap face."""
CAP_GRID_MARK_CONTROL_W = 0.8
"""Stroke width that gives the engraved plus and minus more weight."""
CAP_GRID_MARK_CORNER_R = 0.7
"""Outer radius for the engraved polygon corners."""
CAP_GRID_MARK_TRIANGLE_R = 2.9
"""Circumradius that gives each rounded triangle a span near the circle width."""
CAP_GRID_MARK_SQUARE_W = 3.65
"""Width of the stop square. The smaller width balances its longer outline."""
CAP_GRID_MARK_CIRCLE_SIZE = 5.1
"""Font size that makes the engraved circle approximately 3.9 mm wide."""
CAP_GRID_MARK_CONTROL_SIZE = 4.6
"""Maximum span of the power, microphone, plus, and minus legends."""
CAP_GRID_MARK_DIAMOND_R = 2.2
"""Circumradius of the spare cap's diamond before the corner rounds."""
CAP_GRID_LEGEND_DEPTH = 0.4
"""Depth of the marks that the legend grid cuts into the cap faces for a paint
fill. It is deeper than LEGEND_DEPTH, so a spray coat leaves room for the fill
and a wipe does not empty the recess. It comes out of CAP_TOP_T."""

CAP_FACE_HOLE_CHAMFER = 0.55
"""Radial width of the lead-in cutter around each rigid cap's face hole, on the
axes.

The slope wall of the cutter starts below the face at the hole edge. It rises
to MERGE above the face at this width. As a result, the cut meets the face
inside this width, and the built slope is steeper than
CAP_FACE_HOLE_CHAMFER_ANGLE. counterbore_land() reads the same slope wall.

The straight face hole below the lead-in guides the cap. CAP_FLANGE_OVERLAP
retains the flange.

The land ring over each counterbore sets the upper limit. Each ring must stay
solid over LAND_FLOOR_MIN in checks/keypad.py. The rings on the outer side of
SW4 and SW10 are the thinnest. At about 0.88, the lead-in reaches the mid-line
of the SW4 ring. At about 1.22, counterbore_land() for SW4 goes below
LAND_FLOOR_MIN, and recess_land() fails."""

CAP_FACE_HOLE_CHAMFER_ANGLE = 30.0
"""Sets how far below the face the lead-in cutter starts at the hole edge.

That depth is CAP_FACE_HOLE_CHAMFER times the tangent of this angle. This angle
is not the built slope. The outer edge of the cutter is MERGE above the face,
so the built slope is steeper. See CAP_FACE_HOLE_CHAMFER."""

STEM_W = 4.0
"""Side of the square stem. Square rather than cross or round because a legend
has an orientation and a round stem does not hold one. Roomy because the two
half-size keys are out: the smallest cap left is a full-size key, so the stem is
sized for grip area and stiffness rather than for what SW1 could carry."""
STEM_R = 0.6
"""Corner round on the stem. The socket's inside corners follow it, and a sharp
inside corner is what a printed or moulded socket rounds off anyway, so matching
them is what keeps the fit on the flats where it was designed."""
STEM_GRIP = 0.15
"""Interference per side between each stem and its cap socket. A negative value
is clearance.

The socket bore is STEM_W minus twice this value. The flange retains the cap,
so the grip only preloads the cap against CAP_FLANGE_FLOAT. With zero or
negative grip, a cap can rattle through its float.

The stems are on the TPU pad, and TPU at about 95A grips at this value. If caps
buzz, raise it. If caps do not seat, lower it. Use a positive value only for a
soft pad, because a rigid printed stem binds in an interference fit.
checks/caps.py requires an overlap for a positive value and a gap for zero or a
negative value."""
FDM_CAP_GUIDE_CLEARANCE = 0.35
"""Clearance per side between an integrated FDM keytop and its face hole.

The FDM pad installs from inside the front shell. Its keytops have no captive
flanges, so each must pass through its face hole with printer-tolerant space.
This is larger than CAP_GUIDE_CLEARANCE because the pad and keytops print as
one rigid part, and a tight fit would bind every button at once.
"""
SOCKET_LEAD = 0.8
"""Chamfer around the recess mouth. Without it the mouth is a square edge
arriving on an interference fit and it shaves the stem instead of seating on it.
Twice what a lead-in wants, because assembly is blind: the pad goes down onto
nine recesses at once, and this is what catches the misalignment. It eats into
CAP_WALL, which is what bounds it.

The pad's locating tabs, see PAD_TAB_W, keep its float in x to PAD_FIT each
way, inside this lead. checks/keypad.py holds the float to this value on every
pad variant.

The recess itself is only 0.4 deep now, too shallow to run this full width as
a 1:1 rise without tapering straight through it, so case.py caps the rise at
half the recess and leaves the rest as a genuinely straight, interfering bore.
The radial width, and so the cost to CAP_WALL, is unchanged; only how quickly
it gets there is."""

LEGEND_DEPTH = 0.2
"""How deep a legend line is cut into the cap top: one layer, matching
FDM_OUTLINE_DEPTH so the legends and the front's outline groove are the same
shallow line. Width is LEGEND_STROKE_W's concern. Bounded above by CAP_TOP_T,
which shrank to 1.0 when the face flattened and left less roof to spend."""
LEGEND_STROKE_W = 0.6
"""Line weight of every legend, matching FDM_OUTLINE_W: one extrusion wide, so
an FDM slicer resolves each line as a single pass. Font glyphs are drawn as
their inward outline of this width, SVGs as centerlines thickened to it, so
the weight does not change with a legend's size."""
LEGEND_SIZE = 4.5
"""Default font size for a legend, and the size an SVG's longest side is
scaled to. Sized so a single glyph's strokes stay above what an FDM nozzle
can resolve; below this the thin parts of a symbol close up.

It is a default rather than the size every cap uses, because a font size is
an em, not an ink height, and the eleven legends spend that em very
differently: a solid arrow fills three quarters of it, a hollow one draws
the same outline in a stroke a fraction as wide, and an ASCII hyphen is a
tenth of it. LEGENDS carries a per-entry override for the ones that read
badly at this, rather than this moving and dragging the ones that read
well with it."""
LEGEND_FONT = Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf"
"""Vendored rather than looked up by family name. A system font lookup resolves
differently on every machine, so the same source would cut a different legend,
and DejaVu carries the arrows and technical symbols a keypad wants."""

LEGENDS = {
    "SW1": (("svg", "glyphs/power.svg"), 5.2),
    "SW2": (("svg", "glyphs/mic.svg"), 5.2),
    "SW3": (("svg", "glyphs/cross.svg"), 3.5),
    "SW4": "◀",
    "SW5": "■",
    "SW6": "▲",
    "SW7": ("●", 5.4),
    "SW8": "▼",
    "SW9": (("svg", "glyphs/minus.svg"), 5.5),
    "SW10": "▶",
    "SW11": (("svg", "glyphs/plus.svg"), 5.5),
}
"""What each cap says, one entry per cap. Three forms:

    "X"                     a string, set in LEGEND_FONT at LEGEND_SIZE
    ("svg", path)           artwork, scaled so its inked longest side is LEGEND_SIZE
    (spec, size)            either of the above at its own size instead

A two-tuple starting with the literal "svg" is the artwork form; any other
two-tuple is the sized form, so ("svg", 5.4) is unreachable and a size
always pairs with a spec rather than following one positionally.

Every legend is a line of LEGEND_STROKE_W. A string is a solid font glyph
drawn as its inward outline, so a solid shape reads as an outlined one and
its interior stays standing. An SVG is a set of centerline strokes. The
solid glyphs are the arrows U+25C0/25B6/25BC, the triangle U+25B2, the
square U+25A0 and the disc U+25CF, each checked against the vendored font's
cmap. A glyph too thin to hold an outline raises, so use a solid glyph or an
SVG stroke.

The SVGs under glyphs/ are the escape hatch for marks the font lacks or draws
too thin: power and mic because DejaVu carries neither U+23FB nor any
microphone, the cross, plus and minus because DejaVu's are thin text glyphs
that cannot hold an outline and a line is what they are anyway.

The sizes are ink extents in disguise. LEGEND_SIZE is an em and a glyph
spends it differently, so the disc carries its own size to sit with the
arrows. The SVGs are sized off their longest inked side. Plus and minus
share one size so SW9 and SW11 cut a matched pair, and the cross is sized to
the arrows' ink.

check.py holds every entry to cutting a real deboss, so a typo'd escape or
a glyph the font drops cannot ship as a blank cap."""

PCBWAY_ASSEMBLY_CLEARANCE = 0.20
"""Minimum nominal clearance at mating edges on the PCBWay print order."""

FAB_PROCESS = "SLA"
"""The PCBWay process that check.py measures every printed part against,
with FAB_MIN_WALL[FAB_PROCESS].

The order goes to SLA. The shells are Somos Taurus and the ring insert is
UTR-8100, and both are SLA resins, so every wall is held to the SLA minimum.
An SLS order in PA12 needs this value set back to SLS, because its minimum is
thicker.

If a wall is thinner than the minimum, PCBWay holds the order. You then accept
the risk or make the wall thicker. Source, read on 2026-11-11:
https://www.pcbway.com/helpcenter/3d_engineering_questions/Wall_thickness_issue.html"""

FAB_MIN_WALL = {"SLA": 0.8, "SLS": 1.0}
"""PCBWay's published minimum wall for each process, read on 2026-11-11.

SLA (UTR 8360, Somos Ledo, UTR-8100) is "0.8 mm":
https://www.pcbway.com/rapid-prototyping/3d-printing/3d-printing-SLA.html
SLS PA12 is "1 mm":
https://www.pcbway.com/rapid-prototyping/3d-printing/3d-printing-SLS.html

These are the values on the process pages. The help centre's size table asks
for a thicker wall on a larger part, so a part of the case's length can be held
at a thicker wall than these. The vendor can change these values, so read the
pages again before an order."""
