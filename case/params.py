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
button pad: the grid lobe's grip-side edge stands 32.2 in from the board edge
and the ledges must stay clear of it, so the window ends 0.7 short of that.
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
SKIRT_H = 4.0
"""How far the skirt drops below the board top. Raising the seam grows the
skirt upward without moving its lower edge into the support ledges or screw."""
SHELL_SEAM_RISE = 1.5
"""Lift the back lap and visible seam above the board top. The blind catch
pocket keeps about 1.15 of skirt above it and continuous wall behind it. The
support ledges and board mounting heights do not change."""
SKIRT_T = 1.5
"""The back's lap over the skirt. Whatever is left of WALL after this and the fit
is the skirt, so this one number splits the wall between the two shells."""
SKIRT_FIT = 0.30
"""Clearance between the shells. This gap lets the front fold closed and prevents a tight seal."""
LAP_MIN_WALL = 1.0
"""Thinnest wall that the back lap can keep to the outer round under the front
skirt. The shells check measures this wall on the built back shell around the
IR end. A deeper IR-end skirt needs a deeper lap relief. That relief left the
lap near a third of this value, so the IR end uses the plain skirt."""
SIDE_SKIRT_THICKEN = 0.20
"""Extra inward wall on the front skirt, round the grip end and its two corners
and up both long runs. The nominal 0.5 board fit still leaves 0.3 at the board
edge. This stiffens the printed seam without a change to either shell's
visible outer wall or to the back lap. It runs up to the cavity ceiling, so the
front's inner wall has no step at the seam.

The IR end keeps the plain fit for two reasons. The catch windows' reach is
sized off BOARD_FIT, so it passes a thicker skirt's inner face by only 0.1.
The IR end skirt's flex also sets how the catches close, and this extra wall
makes that skirt about 1.59 times stiffer. The grip end has no catches,
because one screw closes it."""
SIDE_SKIRT_THICKEN_RUN = 1.5
"""Length along each long side over which the stiffener tapers from its full
thickness to the plain board fit at the IR corner tangent. The IR corner arcs
keep the plain fit. The grip end has no taper, because the stiffener runs round
it at full thickness. The taper must stay clear of the support-cut lead-in
ramps, and skirt_lead_in_cuts() fails if it does not."""
SIDE_CATCH_CENTER_OFFSET = 3.5
"""Position of the side catches toward the IR end from the board's lengthwise
midpoint. The reported bow is near that midpoint; this offset centres each
pocket under it without recording an absolute board coordinate."""
SIDE_CATCH_W = 8.0
"""Length of each hidden side catch along the seam. A short land limits the
amount of PLA that must flex during the final fold closed."""
SIDE_CATCH_H = 1.2
"""Pocket height in the clear band above the front skirt's support relief and
below the raised seam. The pocket does not cut the full-length support runs."""
SIDE_CATCH_LOWER_LAND = 0.6
"""Height of skirt between the top of the built support relief and the pocket
bottom. The detent release flank bears on this lower lip. The pocket does not
need to be central in the band. It is as low as a printable lip below it
allows, so the upper land stays long."""
SIDE_CATCH_R = 0.45
"""Round the pocket corners to avoid sharp stress risers in the printed skirt."""
SIDE_CATCH_POCKET_DEPTH = 0.40
"""Blind cut inward from the skirt's outer face. The detent tip stops 0.05
short of the floor. The wall behind the floor is exactly SIDE_CATCH_WALL_MIN,
so a deeper pocket fails the wall check."""
SIDE_CATCH_POCKET_CHAMFER = 0.15
"""Inset of the pocket's rounded inner profile from its outer mouth. The
resulting bevel around both lips matches the detent's insertion and release
ramps without widening the mouth or thinning the upper skirt land."""
SIDE_CATCH_WALL_MIN = 1.0
"""Minimum continuous wall behind each blind catch pocket. This is the point
of replacing the through-window: a shallow detent must not sever the skirt."""
SIDE_CATCH_UPPER_LAND_MIN = 1.0
"""Minimum height of intact skirt above the pocket, checked on the built
shell. SIDE_CATCH_LOWER_LAND leaves about 1.15 nominally above its top edge.
If the pocket leaves less, side_catch_bottom() fails."""
SIDE_CATCH_D = 0.65
"""How far each back-lap detent projects inward. It crosses the 0.30 shell fit
and enters the pocket by 0.35. The earlier 0.15 of engagement held too little
on FDM prints."""
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
SIDE_CATCH_FIT = 0.15
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
SKIRT_LEAD_FIT = 0.1
"""Extra Y relief at every front-skirt lead-in, on both long sides. A 0.1 mm
flat strip before the ramp accommodates printed skirt oversize without holding
the two shells apart; the original ramp angle and support-break positions stay
fixed."""

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
CATCH_FIT = 0.15
CATCH_EMITTER_CLEAR = 2.5
"""Wall kept between the +x window and D1's emitter bore in the same end face.

The +x catch is placed off that bore rather than off the centreline, which is
what CATCH_SPACING would do: mirroring the grip end's spacing lands the window
squarely on the bore, and the bore is drilled to D1's own lens and cannot move.
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
SHELL_SCREW_HEAD_H = 1.7
"""Counterbore depth: the 1.6 mm tallest standard M2 head plus 0.1, so the tallest standard M2 head
lands a shade below the outer face instead of standing in it. It comes out of
the end wall rather than out of FLOOR now, and WALL is 3.0 there, so 1.3 of
wall is left under the head."""
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
END_SCREW_BLOCK_D = 3.7
"""How far the block reaches back into the cavity: END_SCREW_PILOT_DEPTH plus
0.5, so the pilot ends inside it and the thread is never drilled out the back
of its own boss.

The block's +Y back face sets the clearance to the cell. The 45 degree ramp
across the top, see END_SCREW_BLOCK_RAMP_LEDGE, falls the whole of this depth,
so a deeper block also takes more off the cover over the pilot's tip."""
END_SCREW_PILOT_DEPTH = 3.2
"""Engagement this one screw takes.

The screw is an M2 x 5. The screw length is the fixed quantity here, so the
pilot is what is left after the wall under the head and END_SCREW_BLOCK_GAP. It
remains more than one and a half diameters into a self-tapped boss that is
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

The +Y budget is still tight because D1's unchanged bore is drilled to its lens.
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
"""Radial gap the shell's own opening leaves around the wheel's main rotating
body, the part that does reach the ceiling. Tighter than WHEEL_CLEARANCE
because this one is a visible line around the knob rather than buried
clearance, and the lip never transits the opening so nothing wider has to
pass it."""
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
FACE_CROWN_OVER_WHEEL = 0.135
"""How far the crown of the recessed front's face stands above the knob's
measured top, WHEEL_TOP.

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
"""How far past an LED's own body edge the pad's wheel cut has to reach, so
the web's edge stands clear of the package rather than grazing it. One term
of pad_clear_y(), off the LED placements plus LED_BODY, so moving an LED
moves it. The lip's own rotating clearance is the other term. This term
governs at the present layout, because D6 and D7 sit on the wheel's y axis."""
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
# roof is LED_RING_FACE_ROOF under the face, except where the arch holds it up.
LED_RING_WALL = 1.0
"""Web between the wheel opening's bore and the channel's inner wall. It is what
keeps the opening a closed cylinder the wheel seats against, and it is the
ring's inner light barrier, so it is not free to thin toward zero. The inner
wall stands at this radius below its top chamfer and widens the web above it.
The check still probes it on the built shell rather than trusting the sum."""
LED_RING_INNER_CHAMFER = 0.53
"""45 degree bevel at the inner wall's top edge on both LED channels. It steps
0.53 mm out from the inner wall and 0.53 mm down from the channel ceiling at the
top of the bevel. On the recessed front that ceiling changes around the ring.
The bevel follows it, so the bevel is the full height on every bearing. The
inner wall stays upright below the bevel.

The bevel must stay shorter than the lowest inner wall, so the channel stays
open to the cavity below. On the recessed front the inner wall is lowest at the
east and west sides, where the ceiling is lowest. On the FDM front the bevel
uses nearly all of the wall."""
LED_RING_CHAMFER = 0.0
"""How much wider than its nominal radius the channel's outer wall opens at the
mouth. That wall rakes at 45 degrees, so this is also how far above the foot of
the rake it crosses led_ring_outer_r(), and the roof end is then wherever 45
degrees over the channel's own height leaves it rather than anything set here. The inner
wall has a separate top bevel and this does not reach it.

The mouth is the flared end because that is where the light enters, off LEDs
firing up out of the cavity: a wall raked away from them puts more of the roof
in view of each, and the light lands on the middle of the rake, which is the
aim wanted rather than an accident of the layout. See LED_RING_OVER. A 45 degree
rake is also what a printer can close a ceiling over without support.

The web to the bore used to bound this and no longer does, because the inner
wall stopped raking. The cavity wall bounds it now: a wider mouth runs further
past the wall near the X axis, so the ring narrows against a longer chord there.
What it buys is roof, since the flat the ring glows through is the mouth's outer
radius less the channel's own height less the inner wall. Zero keeps the mouth
flush with the pad's grid-lobe boundary on both front variants; the wall still
rakes inward at 45 degrees over the channel height above the foot of the rake.
On the recessed front the outer wall is plumb at the mouth below that foot
where the ceiling is above the arch."""
LED_RING_OVER = 0.6
"""How far past an LED's own body edge the channel's outer wall reaches. Same
job as PAD_LED_CLEARANCE one layer down: derived off the LED placements plus
LED_BODY, so moving an LED moves the channel with it.

It does not stand the package clear of the raked wall, and it must not be
trimmed to. Each LED fires at the middle of that rake on purpose: the rake is
the ring's reflector, and a source aimed at the middle of it throws light
furthest around the channel, which is the best effect this feature has. The
light_path check asks a different question, that the column straight above each
package is void up to the roof, so it catches a package firing into material
without asking it to fire past the reflector."""
LED_RING_ROOF = 1.675
"""Distance from SHELL_FRONT down to the crown of the LED ring channel's arch.
On the crown line this is the roof that the undished face would have over the
arch. LED_RING_TOP, the arch's crown, is SHELL_FRONT less this value.

The arch is the lowest that the channel ceiling can be. The ceiling rises off
the arch to keep LED_RING_FACE_ROOF of roof under the built face. As a result,
the roof on the crown line is LED_RING_FACE_ROOF, not this value.

The ceiling does not drop below the arch, so the channel is never shallower
than the arch makes it. The face falls steeply at the east and west sides of
the knob, to within LED_RING_FACE_ROOF of the arch. The arch, LED_RING_SAG
lower at each side wall, holds the ceiling up there, so the roof is thinner.

The keypad recess sinks the face where the wheel basin's diagonals and both
necks cross the channel. The ceiling goes down with the face until the arch
stops it. check.py's ring stack guard walks the whole annulus and holds a floor
under the thinnest roof.

A smaller value raises the arch. The roof at the east and west sides then gets
thinner, and LED_RING_SAG must grow to keep it. The 45 degree line up from the
mouth also meets the higher arch nearer the wheel. The outer rake ends at that
radius, so the roof flat gets narrower. The FDM front's channel depth is a
fraction of the arch's depth on the crown line, so a change here also changes
the FDM front."""
LED_RING_FACE_ROOF = 0.6
"""Vertical roof that the recessed front's LED ring channel keeps under the
built face, where the arch is lower than the face less this value. The ceiling
is at the face less this value there. As a result, the roof has this thickness
over the diagonals and north and south of the knob. The six LEDs then glow
through an even roof, and more light gets through a near-opaque white material.

The ceiling only rises off the arch. At the east and west sides of the knob the
face falls to the arch, and the arch keeps the ceiling there. ROOF_LEFT_MIN in
checks/wheel_ring.py sets the lower limit, because the roof must bridge the
void in print. The FDM front does not use this value."""
LED_RING_SAG = 0.7
"""How far the LED ring channel's arch falls from LED_RING_TOP on the crown
line to each exterior side wall. The arch is a circular arc with its axis along
y.

The ceiling is the arch, or LED_RING_FACE_ROOF under the built face where that
is higher. At the east and west sides of the knob the face falls faster than
this arch. The ceiling is the arch there, so the roof is thinner than
LED_RING_FACE_ROOF. A larger value lowers the arch there, so the ceiling
follows the face further around the ring and the roof is more even. The ring
roof floor in checks/wheel_ring.py sets the lower limit.

A lower arch also meets the 45 degree line up from the mouth further out, so the
roof flat gets wider near the side walls. The outer rake then starts higher at
the mouth, so the plumb part of the outer wall below the rake gets taller. The
inner bevel is the full LED_RING_INNER_CHAMFER down from the ceiling. Where
the arch is the ceiling, a lower arch leaves less upright inner wall above
CAVITY_FRONT. If none is left, led_ring_channel() stops with an error."""
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
"""How wide the inlet's mouth opens at the face it arrives in, and so the widest
the inlet ever is: the bore is a funnel, bell at the pocket floor and throat on
the board's own port, and this is the bell. An outright width rather than a
multiple of the throat, which is what it used to be: the throat is the board's
number now, and tying the bell to it would mean a different drill quietly
resizing the one dimension the inlet exists for.

A concave fillet rather than the countersink this was, over the last of the way
out. A cone meets the face along a circular corner; a quarter-round tangent to
the face has no edge there at all, which is what an inlet a finger and a stray
draught both arrive at wants, and it is the same feature a moulded port carries.
case.mic_fillet_r() is the radius, and it is not free either: it is this mouth
less wherever MIC_TAPER_SHARE leaves the taper, that being the one radius
leaving the arc tangent to the face above and continuous with the taper below.

Bounded by the duct it is drilled through rather than by anything acoustic: the
mouth is where the bore comes closest to the outside of MIC_DUCT_OD, so it is
the one height the wall is at risk at, and check.py's mic fillet pass reports
what is left. The 4.5 mm mouth keeps the original 0.7 mm radial duct wall by
growing the duct alongside it."""
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

U2 receives through the back along -Z. D1 still fires along +Y through a bore
drilled to its lens, sized by IR_EMITTER_FIT."""
IR_EMITTER_FIT = 0.2
"""Radial gap between D1's lens and the bore it fires through, the emitter's
half of what IR_CLEARANCE is for the receiver. The bore is round and drilled
to board.emitter_envelope()'s own measured lens rather than boxed with a
margin, because the lens is a 3.0 dome and a rounded rectangle around it
would open the end wall wider than the part it passes.

Deliberately a fit rather than a clearance: nothing has to pass through it
on assembly, the board being lowered in from the front with the lens landing
in the bore from behind, so it only has to not touch. Snug also keeps the
open port small, which is the one hole in this case with nothing behind it."""
IR_RELIEF_DEPTH = 1.5
"""How far inside the board edge an end-wall cut reaches, shared by D1's
emitter bore and the USB shell's slot. Both are
through-cuts, so the outward side is not this: it runs well past the exterior
face, and this governs only the inward side, the reach back into the cavity
that connects the opening to it. U2's bottom aperture does not use this."""

# IR window: stepped inside-fit insert closing U2's -Z aperture in the back.
IR_WINDOW_T = 1.0
"""Optical pane thickness from conformal exterior face to interior shoulder."""
IR_WINDOW_FLANGE = 0.8
"""Interior flange reach past aperture per side: outward retention and adhesive land."""
IR_WINDOW_FIT = 0.1
"""Clearance per side around flange in rebate; adhesive fills perimeter gap."""
IR_WINDOW_PRESS = 0.05
"""Pane interference into aperture per side, holding insert while adhesive cures."""
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
"""Angular deflection in radians. This keeps the mesh closed at the USB rim."""
RESET_BORE_D = 1.6
"""Bore diameter with clearance for a straightened paper clip."""
RESET_GUIDE_WALL = 0.8
"""Guide wall thickness for two 0.4 mm extrusion widths."""
RESET_GUIDE_GAP = 0.6
"""Minimum gap between the guide tip and the RESET contact face."""
QWIIC_CLEARANCE = 0.5
"""Clearance around the Qwiic housing for a plug approach from the left side."""
QWIIC_CORNER_CHAMFER = 0.3
"""The small corner trim stays within the connector clearance at each corner."""
QWIIC_SKIRT_CLEARANCE = 0.2
"""The hidden front skirt clears the port roof and joins the adjacent support reliefs."""
QWIIC_KNOCKOUT_T = 0.8
"""The flush cover uses two 0.4 mm extrusion widths through the wall."""
QWIIC_KNOCKOUT_GAP = 0.3
"""The border separates the cover from the wall except at two side bridges."""
QWIIC_KNOCKOUT_TAB_W = 0.8
"""Each side bridge spans four 0.2 mm layers from the panel's lower edge."""
QWIIC_KNOCKOUT_TAB_T = 0.8
"""The two bridges use two 0.4 mm extrusion widths through the wall."""
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
PAD_WEB_T = 1.2
PAD_SKIRT_T = 1.0
"""Width of the moulded pad's skirt wall, measured inward from the lobe outer edge.

The outer face of the wall is flush with the web edge, so the pad keeps its plan
outline. The wall is wide enough to mould and to stiffen the lobe edge.
"""
PAD_SKIRT_CLEARANCE = 0.3
"""Gap from the pad skirt to any board part, in plan and in height.

A board part whose top is within this distance of the skirt bottom, or above it,
and whose plan box grown by this distance reaches the skirt, breaks the skirt.
"""
FDM_PAD_GROOVE_W = 1.2
"""Width of each press-isolation relief in the rigid FDM grid lobe.

Wide so each printed key can flex with less
drag from the neighbouring web while still clearing stems and cap seats.
"""
FDM_PAD_GROOVE_DEPTH = 0.8
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
over a flat floor FDM_PAD_GROOVE_W wide. The grid lobe's outer top edge takes
the same leg, so every key tile slopes down to hinge level on all four sides.
It must stay at or below FDM_PAD_GROOVE_DEPTH and short of each keytop base.
"""
PAD_MARGIN = 1.0
"""Web margin around each island's outermost buttons. Both lobes are full rounded rectangles around their buttons."""
PAD_RADIUS = 4.8
"""Corner radius on both lobes. Keep it below half the smallest lobe width."""
PAD_JOIN_RADIUS = 1.5
"""Round the two corners where the mic clearance circle meets the mic lobe top edge."""
PAD_FIT = 0.3
"""Gap from each pad lobe to the front's stiffened inner wall. The lobes no
longer reach the wheel (see PAD_LED_CLEARANCE and case.pad_wheel_gap()), so
this is a plain fit. It is active: it trims both lobes at the long sides, where
their key rectangles reach past it. checks/keypad.py measures it on the built
pads."""
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
is given up is dish beyond the box's own corners."""
RECESS_CHAMFER_W = 0.5
"""Width in plan of the rim chamfer, on the recessed front only. The chamfer
runs all the way round the merged recess, from the rim in toward the dish.

In each section normal to the outline, the chamfer is a straight line. It
goes from the face at the rim down to the dish floor at this distance in. As
a result, the face turns into the chamfer at a crease on the rim, and the
chamfer turns into the dish at a second crease. There is no step. The
chamfer replaces the soft roll the dish had, so WHEEL_RIM_SOFT,
KEYPAD_RIM_SOFT and KEYPAD_RIM_SOFT_2 are zero.

The chamfer does not move the rim. recess_outline(), the FDM front's groove
and the outline that the renders read stay where they are. If this value is
zero, the front has no chamfer, and the dish runs to the rim."""


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
FDM_LED_RING_DEPTH_RATIO = 0.5
"""LED ring channel depth on the FDM front, as a fraction of the recessed
front's arch depth on the crown line, from CAVITY_FRONT up to LED_RING_TOP.

The flat FDM face does not need the full-height light-spreading void used below
the dished face. Half depth keeps the channel open over the LEDs and gives a
thicker printable roof. This changes only the FDM front. On the recessed front
the ceiling rises above the arch under the face. The outer rake starts that much
higher at the mouth and keeps the arch depth as its height. checks/fdm.py
measures both built shells and holds this ratio. On the recessed front it reads
the height of the outer rake on the crown line."""
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
"""How far a released cap or keytop stands proud of the front face.

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
STEM_GRIP = -0.10
"""Clearance per side between each rigid stem and cap socket.

The flange retains the cap. The clearance prevents a rigid printed stem from
binding in its cap socket. Use a positive value only for a soft pad."""
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
nine recesses at once, and this is what catches the misalignment the pad's own
fit in the cavity allows. It eats into CAP_WALL, which is what bounds it.

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
