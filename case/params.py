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
SWITCH_HEIGHT. It is the floor under CAP_LIFT and CAP_PROTRUSION: a cap that
cannot move this far bottoms out before the switch makes."""

# Shell
WALL = 3.0
"""Thicker than a plain shell needs, because the lap splits it: the back's lap, a
fit and the front's skirt all live inside this one thickness, and the skirt then
has a rail standing off it into a channel cut in the lap. At 2.0 the lap is left
too thin to take that channel. It costs 2.0 on each of the case's outside
dimensions."""
FLOOR = 2.4
"""Back shell floor, under the cavity and over the whole contoured form. No
fastener passes through it any more: the one closure screw enters the -Y end
wall horizontally, so this is sized as a printed floor over a hand-held
volume rather than against a counterbore sunk into it."""
BOARD_FIT = 0.5
"""Gap between the board edge and the inner wall. Board screws locate the board.
The uniform offset changes case length and width by twice the clearance change."""

# Board deflection stops on the inside of the back shell side walls.
SUPPORT_BEARING = 3.0
SUPPORT_GAP = 0.25
SUPPORT_CLEARANCE = 0.4
SUPPORT_MIN_RUN = 8.0
SUPPORT_SOUTH_RUNS = False
"""Include the south-most board support run on each side when true. The board
is carried by the front plate's bosses, and the runs nearest the grip end back
onto the cell bay rather than onto anything that deflects, so this stays
false."""
SUPPORT_UNDER_ANGLE = 60.0
SUPPORT_INNER_R = 0.6
"""Radius on the inboard support edge. It removes the sharp printed tip and
shortens the flat bearing surface by the fillet tangent."""
SUPPORT_MIN_BEARING = 1.5
"""Minimum flat board bearing that must remain after the inboard fillet."""
SUPPORT_SHELL_SKIN = 0.2
"""Keep this exterior shell thickness outside the board support ledges."""

# Vertical clearance measured from the board faces, not from z=0.
FRONT_KEEPOUT = 4.5
"""Clears the USB-C shell at 4.21 above the board face, the tallest thing under
the ceiling anywhere near it. ENC1 reaches 5.75 but passes through the wheel
opening rather than under the ceiling, so it does not set this.

Local to the USB connector's own footprint now, not the whole ceiling: the
keypad has nothing tall over it, so its own region drops to KEYPAD_KEEPOUT
instead, and the USB region keeps a locally deeper cavity, reaching this
full depth, inside an outer face that is flat everywhere. Case.py's
CAVITY_FRONT_USB is that local boundary; CAVITY_FRONT is the keypad one."""

KEYPAD_PLUNGER_STUB = 0.3
"""How far a plunger stands proud of the switch top before the pad's web
begins, over the keypad: KEYPAD_KEEPOUT in case.py is SWITCH_HEIGHT plus
this, so the web's underside lands just above the switches instead of
FRONT_KEEPOUT's old, USB-sized margin, which left 1.7 of unsupported
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

PLUNGER_LOWER_CHAMFER = 0.375
"""45 degree chamfer size at the lower plunger edge. It leaves a flat switch contact."""

BACK_KEEPOUT = 15.3
"""The deepest the cavity ever gets, which is over the cell: CELL_TOP_GAP, then
the cell diameter, then slack. Nothing else under the board comes close, because
the cell is placed in a run with nothing hanging into it, so it sits right up
under the board rather than below whatever is in the way."""

# M2 from the back, through the board's own 2.4mm holes, into blind bosses
# hanging off the front plate. One per hole, so three: a pair at the grip end,
# straddling the cell rather than crossing it, and a single one on the centreline
# at the IR end. Heads sit on the board's underside. The back shell carries no
# screw mounts at all.
#
# The fastener is M2 because the board says so. H1-H3 are
# Library:MountingHole_2.4mm_M2 footprints, whose own description calls the hole
# a loose fit on M2 and marks the 4.0mm DIN965 head as the keepout to check
# copper against. Everything below is that decision carried into the case rather
# than a size chosen here, so a future fastener change starts at the board.
BOSS_OD = 5.0
"""Boss outside diameter. Q1 set this once, the boss at the IR end passing
within 0.21 of it, but the mounting holes moved and nothing on the board is
near one any more: the closest top-side courtyard to any boss is U1, 6.28 from
the +X grip-end hole, which would take an OD past 12 to reach. So what holds
this at 5.0 now is the wall left around the pilot, 1.65 a side at BOSS_PILOT_D,
in a printed post a self-tapping screw is cutting its own thread into. The
smaller M2 screw would allow less, but nothing asks for less: BOSS_COLLAR's
clip on key_size() is idle at the current layout too, so shrinking this buys
no key size back either."""
LEGACY_RETENTION_OD = 5.5
"""V2 retention post outside diameter. This adds 0.25 mm of radial wall over
the front bosses, so the tall free-standing post prints with more material
around its M2 pilot. The extra width clears the V3 cavity components."""
STANDOFF_CHAMFER = 1.2
"""Height and radial reach of the root chamfer on each screw boss, the V2
retention post, and the microphone duct. The chamfer is widest where each post
meets its shell."""
BOSS_COLLAR = 1.0
"""Ceiling kept around a boss, so a key hole never swallows it and leaves it
hanging off nothing. It is not cut out of the keys: key_size() shrinks whichever
key would reach a boss instead, so this bounds the keys rather than notching
them. Idle at the current layout, where all eleven keys come out full size; it
bound SW1 and SW2 back when a mounting hole sat beside each."""
BOSS_PILOT_D = 1.7
"""Self-tapping M2 into printed plastic, near the thread's own pitch diameter
of 1.74 rather than down at its 1.567 minor. Deliberately at the loose end of
the 1.6 to 1.7 an M2 self-tap is usually given: the boss is a printed post
standing free off the ceiling, so it splits along its layer lines long before
the thread it cut would strip, and the failure that costs a whole front shell
is the one worth designing away from. Use 3.2 for a heat-set insert, which is
the usual M2 insert OD."""
BOSS_PILOT_DEPTH = 4.4
"""Thread engagement, 2.2 diameters of it at M2, comfortably past the 2 a
self-tap in plastic wants. No longer all the depth there is, either: the boss
carries its own material from the board right up to SHELL_FRONT now, 6.4 of
post, so this is a chosen engagement rather than whatever the ceiling left
over. It also sets the short screws' length, BOARD_THICKNESS plus this, which
case.py prints.

The back's V2 retention post reads this, LEGACY_RETENTION_OD,
BOSS_PILOT_D and STANDOFF_CHAMFER too, so the optional V2 screw is the same
fastener at the same engagement rather than a second stack to keep in step."""
SCREW_HEAD_D = 4.0
SCREW_HEAD_H = 1.6
"""The largest standard M2 head, in both directions, since these two exist only
as a keepout under the board and the cheapest way to be right about a fastener
nobody has bought yet is to model the worst one. ISO 7045 pan head is 4.0 across
and 1.6 tall at their maxima; DIN 965 countersunk is 3.8 and 1.2. The board
reasons the same way and reaches the same number: H1-H3 carry a 4.0 circle on
Cmts.User as their copper keepout, called out there as the largest standard M2
head.

The head sits on the board's underside rather than sinking into it, the hole
being a plain 2.4 through with no countersink, so it occupies z -1.6 to 0 and
what it has to dodge is bottom-side parts, not anything in the front cavity."""

# The two shells lap right around the perimeter, back over front. The front's
# cavity wall carries on past the parting plane as a single skirt, and the back's
# wall is hollowed out over that same band down to a thinner outer lap that closes
# over it. The seam is the top edge of that lap, and the outer faces are flush
# across it, so nothing of the front is visible from the side below the seam.
SKIRT_H = 4.0
"""How far the skirt drops below the parting plane."""
SKIRT_T = 1.5
"""The back's lap over the skirt. Whatever is left of WALL after this and the fit
is the skirt, so this one number splits the wall between the two shells."""
SKIRT_FIT = 0.30
"""Clearance between the shells. This gap lets the front fold closed and prevents a tight seal."""
SKIRT_TRANSITION_CHAMFER = 3.0
"""Vertical rise at the deep-skirt ends. Support-cut ends use their full exposed height to remove small steps. Zero disables all skirt lead-ins."""
SKIRT_LEAD_ANGLE = 65.0
"""Lead-in angle in degrees from the flat skirt bottom along Y. A shallow angle reduces contact during assembly."""

# At the IR end the skirt runs deeper than anywhere else and carries two rounded
# rectangular windows. The back's lap grows a detent behind each: the lap rides out
# over the taper as the front goes down, and the window's lower edge then catches
# under the flat. That end needs no screw as a result, and the front has to be
# hooked in there and folded down, which is the point of it. The grip end is the
# one closed by a screw now, through its own end wall.
CATCH_SKIRT_H = 7.0
"""Skirt depth at the IR end, against SKIRT_H everywhere else. It has to be deep
enough to carry a window and still leave CATCH_RISE under it."""
CATCH_SPAN = 8.0
"""How far the deepened section runs in from the IR end.

Bounded by the board support runs rather than by the catches themselves. Both
side runs stop at y -34.36 at that end and their own skirt lead-ins occupy the
1.0 above that, so a deepened section reaching past -33.36 would put the deep
skirt on top of them. This leaves its inboard face at -32.71, which clears them
by about six tenths. It was 15.66 while the deepened section was at the grip
end, where nothing but the plain skirt was in the way."""
CATCH_W = 7.0
CATCH_H = 2.4
CATCH_R = 1.0
"""Corner radius of the window. Has to stay under half CATCH_H."""
CATCH_SPACING = 18.0
CATCH_RISE = 1.6
"""Skirt left below each window. This is what actually does the catching, so it is
not free to shrink."""
CATCH_D = 0.8
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
# into a block the front shell carries behind its skirt. So it closes the two
# shells to each other; the board is held by its own three screws into the front
# plate's bosses, and every mounting hole keeps a short screw. Its head is the
# only hole in the back's outer surface. Same M2 x 6 as the board screws:
# case.py prints the length the stack computes.
SHELL_SCREW_CLEAR_D = 2.4
"""Clearance hole through the back's -Y end wall, matched to the board's own 2.4
holes rather than chosen: the same M2 passes a 2.4 at H1-H3, so drilling the
shell tighter than the board would hold this screw to a fit the rest of the
stack does not. Also ISO 273 medium clearance for M2, which is where the
board's own 2.4 comes from."""
SHELL_SCREW_HEAD_D = 4.2
"""Counterbore in the back's -Y end face, SCREW_HEAD_D plus 0.2. Slacker than
the fits elsewhere in this model on purpose: a head that will not sit flush is
the one screw feature visible from outside the case."""
SHELL_SCREW_HEAD_H = 1.7
"""Counterbore depth: SCREW_HEAD_H plus 0.1, so the tallest standard M2 head
lands a shade below the outer face instead of standing in it. It comes out of
the end wall rather than out of FLOOR now, and WALL is 3.0 there, so 1.3 of
wall is left under the head."""
END_SCREW_X_OFFSET = 5.8
"""How far +x of the board's centreline the end screw's axis runs.

Set by what is behind the wall rather than by the wall, and by which way the
block is free to grow. R8's courtyard is the near obstacle, so the block's -x
face is what the column has to clear; J1 sits well -x of that and nothing at
all sits +x of the block until the side wall. So the width went on the +x side
and the axis moved out with it by half of what was added, which leaves the -x
face exactly where it was, clear of R8, with the block wider the other way.
The block the screw threads into is centred on this axis."""
END_SCREW_Z = -6.5
"""Height of the end screw's axis, below the board.

Bounded both ways by the -Y wall's own section. Above, the back's lap is
hollowed out for the skirt down to SKIRT_BOTTOM less the fit, so a head
counterbore any higher would break into that relief instead of sinking into
solid wall. Below, the back's outer surface rolls away through
CONTOUR_TIP_R toward the floor. This leaves the whole SHELL_SCREW_HEAD_D
counterbore on flat, full-thickness wall, which checks/hardware.py's end_screw
pass measures on the built back rather than restating here."""
END_SCREW_BLOCK_W = 10.0
"""Width of the block the end screw threads into, across the case.

Wider than BOSS_OD for the same reason the V2 post is: it is a printed feature
a self-tapping screw cuts its own thread into, and it is loaded in withdrawal
along its own weakest direction, the layer lines of a part printed face down.
It is wider than that reason alone asks because the room is free: the whole
+x span from the block to the side wall is empty, so the extra width costs
nothing and every millimetre of it is thread the screw can pull against."""
END_SCREW_BLOCK_D = 4.9
"""How far the block reaches back into the cavity: BOSS_PILOT_DEPTH plus 0.5,
so the pilot ends inside it and the thread is never drilled out the back of
its own boss."""
END_SCREW_BLOCK_BOTTOM = 2.5
"""Material the block carries below the screw axis, matching BOSS_OD/2 so the
wall under the thread is what it is around every other M2 in this case. Above
the axis the block runs on up to SUPPORT_TOP, so it is not symmetric: that is
where it meets the skirt it hangs from."""
END_SCREW_BLOCK_R = 1.5
"""Round on the block's vertical edges, in plan.

The block hangs alone in the back's cavity with the shells closing over it, so
its corners are what a misaligned fold catches on first; a round gives the
assembly somewhere to slide instead. Kept under half END_SCREW_BLOCK_D, which
is the shallower plan dimension and so the bound on any plan round here. The
two wall-side corners end up buried: the web that ties the block to the skirt
runs past them by this radius plus MERGE, so the bridge stays full width."""
END_SCREW_BLOCK_CHAMFER = 1.5
"""Lead-in on the block's top +Y arris, where the board lands on it.

The block's top is SUPPORT_TOP, so SUPPORT_GAP is the whole of the clearance
the board has over it, and the block reaches END_SCREW_BLOCK_D inboard of the
board's own -Y edge. That puts a square arris under the board and well inside
its footprint, so it is the first thing the board's end strikes when the board
goes in at any tilt, with nothing like enough gap to clear it. The chamfer
turns that catch into a ramp the board slides down.

Forty five degrees because the front prints face down, so this face builds
upward and is self supporting; anything steeper would need support in the one
orientation that keeps support off the cosmetic face.

Bounded twice. It has to stay well inside END_SCREW_BLOCK_D so the block keeps
a top land for the board to sit over rather than being cut to a knife edge,
and well inside the height between SUPPORT_TOP and the top of the pilot, which
is END_SCREW_Z plus half BOSS_PILOT_D, so the ramp never opens the thread."""

# Cell: one AA lying along the board underneath it, horizontally, in the same
# saddle cradle the 18650 used. Change these for another format and the cavity,
# cradle and case thickness follow.
CELL_D = 14.5
CELL_L = 50.5
"""AA at its catalogue maximum, which is also the envelope for a 14500: that cell
is the AA form factor in single-cell lithium, so it drops into this bay with no
change here. Electrically it is the only one of the AA chemistries that does,
because the XIAO's charger wants 3.0 to 4.2V. See the README."""
CELL_FIT = 0.4
CELL_END_FIT = 1.0
CELL_TOP_GAP = 0.6
"""Clearance from the cell up to the board. Anything hanging below the board by
more than this counts as an obstacle when picking the bay, so the cell never has
to sit below a component."""

CELL_END_MARGIN = 7.0
"""How far the cradle sits from the near end of its bay, which is what pushes the
cell down toward the bottom edge instead of centring it. Wants to stay clear of
CONTOUR_TIP_R, or the rounded-off end eats into the cell."""
CRADLE_T = 1.6
"""Saddle ribs at each end of the cell. Their notches cradle it, their faces stop
it sliding along its axis."""

# Outer form. The back is contoured along its length rather than being a slab: the
# cell sits toward the bottom end, so the case is deep where you hold it and tapers
# from there to whatever the board itself needs. The shape is a loft, and the
# rounding is built into its sections rather than filleted on afterwards.
CONTOUR_END_DEPTH = 7.0
"""Floor under the tapered ends, not the value they take. Each end is derived
from what actually hangs below the board on that side and only falls back to
this when nothing does. Both ends fall back to it as the board stands: U2 is a
low SMD part and receives through the back floor rather than setting an end
depth, while the -Y end asks for J1's assumed depth and comes up short too.

The +Y budget is still tight because D1's unchanged bore is drilled to its lens.
The back rolls up through CONTOUR_TIP_R to meet that face, and reducing this
depth can make the bore break out through the underside. U2's bottom aperture
does not share that constraint; its conformal insert follows whatever back form
this depth produces. Built end-port and receiver-path checks guard both cases."""
CONTOUR_TIP_R = 5.0
"""Radius the back rolls up through at each end of the case, so the bottom meets
the end face tangentially instead of squaring off into it. Keyed to the case's own
end, not the board's. The loft's end regions run over this radius or the plan's own
corner, whichever reaches further in."""
CONTOUR_BLEND = 22.0
"""Length each taper runs over, measured out from the cradle. Long enough that
the hump is a curve to hold rather than a step."""
EDGE_R_BACK_CELL = 12.5
"""Round on the back's bottom edge over the cell and cradle. It runs the whole way
round the plan, corners included, because each loft section is as wide as the plan
is at that point. It makes the battery end read as a hand-held dome rather than a
box with its corners removed. The cavity uses this radius less FLOOR, so the shell
keeps its thickness around the corner."""
EDGE_R_BACK_IR = 8.0
"""Round on the back's bottom edge near U2. It is smaller than EDGE_R_BACK_CELL so
the upper taper stays light and every lifted form used by the IR insert remains a
valid rounded section. The profile blends from the cell radius over CONTOUR_BLEND."""
EDGE_R_FRONT = 2.5
"""Round on the front's top edge. Small: it is a face full of key holes, and the
outermost sit close to the wall. The FDM front carries its own, see
EDGE_R_FRONT_FDM."""
EDGE_R_FRONT_FDM = 0.6
"""Round on the FDM front's top edge, in place of EDGE_R_FRONT.

Much harder, and the outline is what makes it so. That front draws the recess's
rim as a groove in the face, the rim sits KEYPAD_EDGE_MARGIN off the wall, and
the groove is centred on it, so the groove's outer edge is half a width further
out than that. What is left for the round is everything inboard of that edge
less FDM_OUTLINE_EDGE_CLEAR, and this is exactly that bound: the softest edge
the outline leaves room for rather than a number chosen for its own sake.
checks/fdm.py measures the flat the built shell actually has and holds the
relationship, so widening the groove or moving the rim fails there instead of
quietly putting the line back on the curve.

It reads better on this front anyway. A 2.5 round on a face with a dish in it
is a continuous fall from the middle of the face to the side wall. On a flat
face it is 2.5 of dome either side of a plane, which is the "weird" the variant
first came back as."""

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
merely clear them. It still bounds the counterbores: key_size() keeps a key
clear of the screw bosses at this radius, and the counterbore sits inside it."""
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
WHEEL_DISH_DEPTH = 0.9
"""Depth of the wheel basin at its own centre. The centre is inside the bore, so
none of it is ever cut: what the number really sets is the seat depth at the bore
wall, which is about a third of this on the free axis and just under half on the
diagonals, WHEEL_SQUIRCLE_N having brought the diagonals in from where the
squircle put them. Bounded by LED_RING_ROOF rather than by any counterbore, no
key sitting under this basin: the roof over the ring channel is thinnest where
this basin's diagonals or one of its joins cross the channel, and check.py holds
a floor under what is left there."""

# Status LEDs: the pad's wheel bore is cut wide enough that the pad never
# reaches over them, and they shine straight through the translucent shell.
# The pad used to carry a hidden flange out over the LEDs that piped light
# inward to a moulded ring plug in a shell window; the translucent case
# material diffuses better than the silicone did, so the pad now just gets
# out of the light's way entirely.
LED_HEIGHT = 0.8
"""XL-2020RGBC body height above the board face. Hand-entered: D2-D5 have no 3D
model at all, so nothing in the design files can confirm it."""
LED_BODY = 2.0
"""XL-2020RGBC body side, square in plan. Hand-entered for the same reason as
LED_HEIGHT."""
PAD_LED_CLEARANCE = 0.6
"""How far past an LED's own body edge the pad's wheel cut has to reach, so
the web's edge stands clear of the package rather than grazing it. One term
of pad_clear_y(), off the LED placements plus LED_BODY, so moving an LED
moves it; the lip's own rotating clearance is the other term and governs at
the present layout."""
WHEEL_OPENING_EDGE = 0.65
"""Minimum ceiling between the shell's wheel opening and the side wall. The
opening is clipped to a chord near the X axis if it would come closer than
this, which is what made the case a flat-sided oval before BOARD_FIT was
padded out. At the opening's current radius there is more room than this asks
for and nothing is clipped, so this is idle. The LED ring channel used to share
the clip and no longer does: the channel runs flush to the cavity wall
instead."""

# LED ring channel: an annular void inside the front shell's ceiling, circling
# the wheel opening and passing over D2-D5, so their light spreads around the
# channel and reads as a ring on the face instead of four dots. The channel is
# open to the cavity below (the pad's wheel cut already uncovers the LEDs) and
# roofed by LED_RING_ROOF of translucent shell, which is the diffuser.
LED_RING_WALL = 1.0
"""Web between the wheel opening's bore and the channel's inner wall. It is what
keeps the opening a closed cylinder the wheel seats against, and it is the
ring's inner light barrier, so it is not free to thin toward zero. That wall
stands plumb, so this is the web at every height rather than a radius the wall
crosses once. The check still probes it on the built shell rather than trusting
the sum."""
LED_RING_CHAMFER = 0.0
"""How much wider than its nominal radius the channel's outer wall opens at the
mouth. That wall rakes at 45 degrees, so this is also how far above the mouth it
crosses led_ring_outer_r(), and the roof end is then wherever 45 degrees over
the channel's own height leaves it rather than anything set here. The inner wall
is plumb and this does not reach it.

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
rakes inward at 45 degrees over the channel height above that mouth."""
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
LED_RING_ROOF = 1.2
"""Translucent roof left over the channel, face side: the surface the ring
actually glows through. The keypad recess overlaps the channel in plan where the
wheel basin's diagonals reach past its own half axis and where either of its
joins runs out across the annulus, and what the recess sinks there comes out of
this roof; the difference is the thinnest the roof gets anywhere, and check.py's
ring stack guard is what holds a floor under it, walking the whole annulus rather
than one radius."""
# Apertures in the back shell
MIC_THROAT_MARGIN = 0.5
"""How much wider than the board's own acoustic port the inlet's throat is,
where the two meet at BOARD_TOP. The throat itself is not a number here: it is
that drill plus this, read at build time through board.npth_pads("MK1") by
case.mic_port_drill(), because the drill belongs to the board and copying it
into this file is how the two quietly stop agreeing.

There is a margin at all for two reasons, and the tighter of the two wins.

Alignment. The case is located on the board by three M2 screws through holes the
board itself calls a loose fit, so the duct and the drill can sit a couple of
tenths out of concentric, and the throat still has to uncover the whole drill
rather than shading part of it. Half of this is what that buys, per side, all the
way round.

Printing. A bore near a single extrusion width does not survive slicing: the
perimeter closes over it. This keeps the narrow end at several extrusion widths,
which is the floor a small bore in a printed part has regardless of what it is
for, and it is the reason not to chase the drill any closer than this."""
MIC_MOUTH_D = 3.0
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
what is left. Raise it for a wider bell until that wall gets thin, or raise the
duct with it."""
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
MIC_DUCT_OD = 4.4
"""Outside of the duct, the post standing from the board up to the front face
with the funnel drilled through it. Set outright rather than derived from the
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
to keep the cell off it. J1 is the one that matters."""
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
"""Margin around the USB-C shell, sizing the -Y end wall's own through-cut
past the connector's measured envelope, the same role IR_CLEARANCE plays at
the other end. Also the plan margin usb_pocket() keeps clear of the
connector's footprint in the ceiling above it."""
USB_POCKET_LIP_CHAMFER = 1.6
"""Chamfer on the pocket's inboard lip, the convex corner where usb_pocket()'s
wall meets the cavity ceiling one board width in from the end wall. The USB-C
connector catches on that square corner during assembly, so the 45 degree cut
gives it a lead-in instead.

This is the wall's full height, CAVITY_FRONT up to the pocket roof, so the
wall becomes one ramp with no square face left anywhere on it. That roof is
case.usb_roof(), the connector's own envelope plus USB_CLEARANCE, so the wall
is 1.6 and not the 1.4 the stack planes suggest. It was 1.9 while the pocket
stood MERGE higher than the slot for no reason the connector asked for. The
roof also bounds the cut, which cannot climb past it, so the ceiling over the
ramp stays as thick as the ceiling over the connector.
_chamfer_usb_pocket_lip() measures the built wall and fails if this value goes
past it, which is what caught the change."""
USB_POCKET_INBOARD_REACH = 2.0
"""How much further inboard usb_pocket() reaches than the connector's own
envelope plus USB_CLEARANCE, on the +Y side alone.

What it buys is run. The plug enters along +Y and wants the connector's full
height under it for a while before the ceiling steps back down to CAVITY_FRONT,
so it slides home instead of catching on the lip. USB_POCKET_LIP_CHAMFER
already ramps that lip over the whole of its own height and
_chamfer_usb_pocket_lip() refuses any more, so the lip itself cannot give
anything further; moving the wall is what is left, and the ramp rides with it
because that function reads the wall off the built pocket.

A separate number rather than more USB_CLEARANCE because that one also sizes
usb_slot(), the through-cut in the end wall, and the opening the connector
shows through must not grow: it is the line around the plug on the exterior
face. This pocket is blind and internal, so it can grow where the slot cannot,
and asymmetric because only the inboard side is in the plug's way.

What it costs is reach on the thinnest roof in the model. usb_roof() up to the
face leaves 1.04 on the recessed front and 0.64 on the FDM front, and this
carries that run this much further inboard. Nothing structural is in the band;
the nearest mounting bosses stand well past it. checks/usb.py reads the wall
and its ramp off the built front rather than off this."""

# Button pad: one soft moulding, flat web with raised keys and no skirt. Held up
# against the ceiling by its own plungers resting on the switches.
PAD_WEB_T = 1.2
PAD_GROOVE_W = 0.8
"""Width of each press-isolation groove in the nine-button pad lobe.

The grooves divide the web between adjacent buttons but leave more web than
the 0.7 mm minimum key gap. This keeps the pad one moulded part.
"""
PAD_GROOVE_DEPTH = 0.3
"""Depth cut from each face of the pad web at an isolation groove.

The two cuts leave PAD_WEB_T - 2 * PAD_GROOVE_DEPTH of centre material.
"""
PAD_GROOVE_EDGE_RETENTION = 1.0
"""Material retained between each isolation groove end and the grid-lobe edge.

This continuous frame keeps the nine buttons in one pad and prevents a groove
from opening at the perimeter.
"""
PAD_MARGIN = 1.0
"""Web margin around each island's outermost buttons. The mic island follows each button above a shared lower bridge."""
PAD_RADIUS = 4.8
"""Corner radius on the grid lobe and each mic-island button contour. Keep it below half the smallest contour width."""
PAD_JOIN_RADIUS = 1.5
"""Round the inner corners between the two button contours and their lower connecting web."""
PAD_FIT = 0.3
"""Gap to the shell's inner wall. Once kept small so the pad stayed wider than
the wheel bore; the lobes no longer reach the wheel at all (see
PAD_LED_CLEARANCE and case.pad_wheel_gap()), so this is back to being a plain
fit, and idle at the present layout since both lobes sit well inside the
cavity."""
PAD_BOSS_CLEARANCE = 0.4
"""Gap where a front-plate boss passes through the pad, measured off the boss's
ceiling collar rather than the boss, so the keytop stays clear of both."""
PAD_MIC_CLEARANCE = 0.3
"""Gap from the pad to the mic duct's widest chamfer at the ceiling."""
PLUNGER_D = 2.5
"""Contacts the switch actuator. Reaches from the web down to SWITCH_HEIGHT."""

# Keypad recess: one continuous concave recess sunk into the front face, with
# no flat floor and no wall anywhere. Three superellipse-bounded dishes along
# one centreline, over the nine-key grid, over KEYPAD_ISLAND_2 and the mic
# inlet, and around the wheel, joined into a single C1 depth field by two neck
# channels that ramp between them. A cap still lands flush with the face, so it
# stands proud of whatever the recess is locally deep under it.
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
KEYPAD_PROFILE_POINTS = 64
"""Points the floor profile across one loft station is drawn through. A
polyline rather than a fitted spline so every station carries the same vertex
count and the loft between them has nothing to match up; spaced by angle across
the section, so at this count the chord sag on the widest station is a few
thousandths, well under a print layer."""
KEYPAD_RECESS_STATIONS = 20
"""Stations per dish half the recess is lofted through, spaced by the
superellipse's own parameter rather than evenly in y: both the half width and
the depth turn fastest at a rim and barely at all in the middle, so even steps
in the parameter put the stations where the turning is."""
KEYPAD_NECK_STATIONS = 12
"""Extra stations across each neck, evenly spaced. Nothing is singular there,
and the two Hermite halves want resolving on their own terms rather than on the
spacing the neighbouring dish's rim happens to leave."""
KEYPAD_TIP_WIDTH = 0.15
"""Half width the outermost station still carries, as a fraction of that dish's
own half axis, in place of lofting to a point. A degenerate section is what
makes a loft come back non-manifold. It costs nothing in fidelity: a
superellipse's own end is flat to within microns over this much of its width,
so the blunt tip it leaves sits a few thousandths inside the true rim at a
depth of almost nothing."""
KEYPAD_DISH_DEPTH = 0.8
"""How deep the grid recess is at its own centre, which is where SW7 sits, so
this is also the whole land the deepest counterbore gives up. What bounds it is
SHELL_FRONT less COUNTERBORE_TOP less check.py's LAND_FLOOR_MIN, which
case.DISH_HEADROOM is the first two terms of; this spends about seven tenths of
that budget and leaves the rest, rather than being tuned to land exactly on the
floor the way the old flat pocket's inset was."""
KEYPAD_DISH_DEPTH_2 = 0.6
"""Depth of the second dish at its own centre. Shallower than the grid's
because it is less than half as wide in y, so the same depth would curve it
visibly harder; chosen so a cap on SW1 or SW2 stands proud by about what a cap
on the grid's outer ring does, rather than so the two centres match."""

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
"""How clear a recess's own rim is kept of the case's exterior wall. Set to
EDGE_R_FRONT plus a 0.3 print-safety buffer, not sized off the recess geometry,
so a future edit to the fillet is what check.py's guard would catch rather than
the two quietly trading margin.

Live, not idle: the grid's coverage box is wide enough that the superellipse
bounding it would reach inside this, so case.keypad_recesses() caps that half
axis here instead. The keys still sit inside the curve with room to spare; what
is given up is dish beyond the box's own corners."""


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
# Nothing else about the shell changes. The caps are flush with the face by
# construction (CAP_PROTRUSION), so they stay flush with a flat one; each
# counterbore keeps the whole of DISH_HEADROOM as land instead of giving a dish
# depth up to it; and the mic inlet's mouth already runs at constant radius to
# the face, so it opens as a plain hole rather than in a curved floor. What is
# given up with the dish is the finger access around the wheel: the seat that
# dished down to the knob's own lip is flat here, so the wheel is reachable
# across its top face only.
FDM_FACE_DROP = 0.4
"""How far the FDM front's outer face sits below the recessed front's.

The recessed front's face is the raised land the dish is sunk out of. Flatten
that dish and the face has to land at one height or the other, and the raised
one leaves a part thicker than the one it replaces for no reason: the material
the dish took out is simply kept. So this front's face lands at the sunken
level instead, and the part comes out that much slimmer.

What bounds it is not the dish's own depth, which is 0.6 to 0.9, but the
ceilings the drop thins outside that dish: the USB pocket's roof against
USB_CEILING_MIN and the thinnest counterbore land against LAND_FLOOR_MIN. The
USB pocket is the tight one: its roof is 1.04 on the recessed front, against
USB_CEILING_MIN's 0.4, so 0.64 is all there is. The FDM LED channel is only
half the recessed front's depth and therefore leaves a thicker roof of its own.
This takes most of the USB bound while retaining a real margin.

The drop is therefore a little short of the dish it stands in for, which runs
0.6 to 0.9. The face lands near the shallow end of the recess rather than on
its floor. Going further means raising usb_roof(), and the connector's own
envelope is what sets that.

Caps and the wheel stand proud by this much, against the 0.47 to 0.80 the caps
already stand proud by on the recessed front, so a cap on a flat face reads as
one sitting a little shallower in a dish. The wheel standing proud gives the
knob back some of the finger access a flat face takes from it.

checks/fdm.py reads all three ceilings off the built shell, against the same
floors the recessed front's own passes hold them to."""
FDM_OUTLINE_W = 1.2
"""Full width of the engraved outline in the FDM front's face. Two extrusions
of a 0.6 nozzle, or three of a 0.4 nozzle: wide enough that the marking reads
clearly after printing while still short enough for the layer above it to
bridge without support.

The groove is centred on the rim, so it reaches half of this further out than
the rim itself does. That is what EDGE_R_FRONT_FDM is sized against: the round
gives way to the outline rather than the outline being moved off the rim to
make room for the round."""
FDM_OUTLINE_EDGE_CLEAR = 0.3
"""Flat face kept between the groove's outer edge and the tangent line of the
FDM front's own edge round. What it bounds is EDGE_R_FRONT_FDM.

Not cosmetic. At zero the two edges are coincident, and two coincident edges in
one plane crack a triangulation: the solid stays valid, its bounding box and
widths all read correctly, and the exported STL comes back with nine open edges
along the face. checks/shells.py's parts_are_sound() is what catches that, and
it is the only pass in the model that would. This model has already shipped
that exact failure once. It also buys the same print-safety buffer
KEYPAD_EDGE_MARGIN carries, and for the same reason."""
FDM_OUTLINE_DEPTH = 0.4
"""How far that outline is sunk into the face. Two 0.2 layers, so the slot is
half as deep as it is wide and the bridge over it is two layers rather than a
stack of them.

It has to stay under LED_RING_ROOF as well. The recess's rim passes within a
few hundredths of the LED ring channel's outer wall either side of the wheel,
so a small change on either side puts this groove over a roof that has to carry
the light, and what would be left there is LED_RING_ROOF less this.
checks/fdm.py holds the floor under it for that case rather than for the
clearance the present layout happens to have."""
FDM_LED_RING_DEPTH_RATIO = 0.5
"""LED ring channel depth on the FDM front, as a fraction of the recessed
front's channel depth.

The flat FDM face does not need the full-height light-spreading void used below
the dished face. Half depth keeps the channel open over the LEDs while leaving
a thicker printable roof. This changes only the FDM front; the recessed front
retains the full channel. checks/fdm.py measures both built shells and holds
this ratio rather than trusting the construction."""
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

The web is what bounds it. This plus FDM_WHEEL_OPENING_CHAMFER has to stay
inside LED_RING_WALL, so the widened bore and the cone that opens it never
reach the channel's inner wall; wheel_opening() raises if they do. Coincident
is as bad as past: FDM_OUTLINE_EDGE_CLEAR is the note on what two coincident
edges in one surface do to an exported mesh."""
FDM_WHEEL_OPENING_CHAMFER = 0.6
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

Shares FDM_WHEEL_OPENING_CLEARANCE's budget against LED_RING_WALL: the widened
bore plus this cone stay inside the web, so the mouth's own widest radius stops
short of the LED ring channel's inner wall. wheel_opening() raises naming both
if that is ever untrue, and checks/fdm.py reads the cone off the built face."""


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

CAP_PROTRUSION = 0.0
"""How far a cap stands proud of the front face. Zero: the face is flat, so
a cap's top is CAP_TOP = SHELL_FRONT + CAP_PROTRUSION by construction,
flush with the surrounding face rather than proud of it. A press sinks
the cap SWITCH_TRAVEL into its own face hole instead of dropping it from
proud toward flush; CAP_GUIDE_CLEARANCE already leaves it room to do that
without fouling the shell."""
CAP_TOP_T = 1.0
"""Roof over the socket, now a shallow locating recess rather than a deep grip:
the flush face left no room for the old 1.4. LEGEND_DEPTH comes out of it, and
what is left is the translucent bridge the pad's backlight glows through, so it
is bounded below by the legend rather than by strength."""
CAP_TOP_FILLET = 0.4
"""Radius on the exposed top perimeter of every rigid cap.

This removes the sharp edge a finger meets without changing the cap's body at
the face hole, its flange, or its captive retention geometry. It stays below
CAP_TOP_T, so the socket roof remains below the rounded edge."""
CAP_WALL = 1.0
"""Thinnest wall the cap may be left with anywhere around its socket. Not a
modelled dimension: the cap's body follows the face hole and its widest bore is
the socket mouth, which stands SOCKET_LEAD out from the bore on each side, so the
wall is whatever falls out between them. check.py holds this floor so future
drift in either number cannot quietly starve it."""
CAP_LIFT = 0.45
"""Air under the cap's flange, from the pad web up to the flange's bottom face.
This is the travel the cap has before the flange lands on the web, so it has to
stay clear of SWITCH_TRAVEL. The counterbore shoulder sits CAP_FLANGE_FLOAT above
the flange and so arrests nothing on the way down, which leaves this the only
bottom-out guard now that CAP_PROTRUSION is 0 and a press is expected to sink
the cap into its own face hole rather than merely toward flush.

Trimmed from 0.5 to make room for the keypad recesses without deepening the
counterbore: SWITCH_TRAVEL plus its check.py margin is 0.45 exactly, so this
is the least CAP_LIFT can be, zero slack rather than a chosen number."""

CAP_FLANGE_T = 0.6
"""Thickness of the flange at the cap's base. It is the whole retention feature
and it is loaded in shear against the face land, so what bounds it below is
strength in a printed cap rather than the counterbore it has to fit in."""
CAP_FLANGE_OVERLAP = 0.6
"""How far the flange reaches past the face hole, per side. This is the retention
now: pull a cap and this is the ledge the face land catches. A cap sitting off
centre spends CAP_GUIDE_CLEARANCE of it, so check.py holds the worst-case
remainder rather than this number."""
CAP_FLANGE_TRIM = 0.2
"""How far the flange is drawn in from the key size, per side. With
CAP_FLANGE_CLEARANCE it puts the counterbore back at exactly the keytop
footprint, so key_size()'s screw-boss logic answers for the counterbore with no
second calculation."""
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

CAP_FACE_HOLE_CHAMFER = 1.00
"""Small edge break around each rigid cap's opening in the front face.

The cap is still guided by the straight face hole below this chamfer, and its
flange is still retained by the unchanged CAP_FLANGE_OVERLAP. 1.00 mm gives a
visible lead-in without consuming much of the face land or making the
gap around a flush cap read as another counterbore."""

CAP_FACE_HOLE_CHAMFER_ANGLE = 30.0
"""Angle of the rigid-cap hole lead-in measured up from the outer face.

Thirty degrees gives the 1.00 mm radial break a shallow lead-in while leaving
the unchanged straight bore below it to guide the cap."""

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

LEGEND_DEPTH = 0.4
"""How deep a legend is cut into the cap top. At least one extrusion width, or an
FDM slicer drops the deboss entirely: a resin print cuts this crisp, but FDM is
marginal at 0.4 and worth test-printing before committing nine caps to it.
Bounded above by CAP_TOP_T, which shrank to 1.0 when the face flattened and left
less roof to spend."""
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
    "SW2": (("svg", "glyphs/mic.svg"), 5.0),
    "SW3": ("✕", 5.9),
    "SW4": "◀",
    "SW5": "■",
    "SW6": "▲",
    "SW7": ("○", 5.4),
    "SW8": "▼",
    "SW9": (("svg", "glyphs/minus.svg"), 5.5),
    "SW10": "▶",
    "SW11": (("svg", "glyphs/plus.svg"), 5.5),
}
"""What each cap says, one entry per cap. Three forms:

    "X"                     a string, set in LEGEND_FONT at LEGEND_SIZE
    ("svg", path)           artwork, scaled so its longest side is LEGEND_SIZE
    (spec, size)            either of the above at its own size instead

A two-tuple starting with the literal "svg" is the artwork form; any other
two-tuple is the sized form, so ("svg", 5.4) is unreachable and a size
always pairs with a spec rather than following one positionally.

Prefer the string. A Unicode glyph out of a symbol-bearing font needs no
new file and cuts the same on any machine, and DejaVu carries every arrow
and geometric shape here: the solid arrows are U+25C0/25BC/25B6 plus the
triangle U+25B2 and square U+25A0, the hollow circle U+25CB and the cross
U+2715, each checked against the vendored font's own cmap rather than
assumed. The SVGs under glyphs/ are the escape hatch, drawn as filled
closed paths because import_svg gives wires to fill and a stroked path
would arrive as a hairline that cuts nothing. Power and mic are SVGs
because DejaVu carries neither U+23FB POWER SYMBOL nor any microphone;
plus and minus are SVGs because DejaVu's own are thin text glyphs with no
heavy variant in the font, and the bar thickness is the point.

The arrows are a d-pad of three, left on SW4, down on SW8 and right on
SW10, the three directions the layout actually has. SW6's triangle is a
shape key, not a fourth direction, but it is drawn solid (U+25B2 rather
than the hollow U+25B3) so an up-pointing triangle does not read as an
outlined odd one out beside three filled arrows, and SW5's square follows
it solid (U+25A0) for the same reason.

The sizes are ink heights in disguise. LEGEND_SIZE is an em, and a
hollow shape draws its outline in roughly a fifteenth of it, so
U+25CB goes up to keep its stroke printable and to sit with the solid
shapes; U+2715 is drawn well inside its own em, so it goes up to sit at
the arrows' ink height rather than reading a size smaller than the key
beside it. The SVGs are sized off their own longest side: height for
power and mic, so they land a little under the arrows rather than over,
and bar length for plus and minus, whose bars come from the same drawing,
so SW9 and SW11 cut a matched pair by construction.

check.py holds every entry to cutting a real deboss, so a typo'd escape or
a glyph the font drops cannot ship as a blank cap."""
