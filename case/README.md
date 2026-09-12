# Case

Enclosure model for the c6remote board, written in [build123d](https://build123d.readthedocs.io/)
so the source is Python and diffs are readable. Geometry that exists in the KiCad
files is read from them rather than retyped, so moving a switch moves its hole.

Four parts plus a keycap per grid key: a front shell, a back shell, a soft button
pad, an IR window insert over the receiver, and one rigid cap for each switch.
Only STLs are written. `case.py` prints the closed size and the other headline numbers when it
runs, which is where to read them: this file deliberately carries none, because
they move with every change and are cheaper to remeasure than to maintain.

## Setup

```bash
cd case
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

## Use

```bash
scripts/export-case-refs.sh      # from the repo root, after any board change
.venv/bin/python board.py        # what the model reads out of the board
.venv/bin/python case.py         # write STLs into case/export/
.venv/bin/python check.py        # verify the case against the board
.venv/bin/python case.py --show  # preview, needs `uv pip install ocp-vscode`
```

The model reads the board instead of duplicating it: mounting holes and the
wheel centre come from `c6remote-kicad/c6remote.kicad_pcb`, component placements
from `c6remote-kicad/export/c6remote-pos.csv`, and keepout heights plus the USB,
mic and IR window positions from the STEP assembly exported by
`scripts/export-case-refs.sh`. Never hand-transcribe a board coordinate into the
case model. Add a reader to `board.py` instead.

After a board change moves the outline, a mounting hole, or a component the case
opens onto, rerun `scripts/export-case-refs.sh` from the repository root, then
run `.venv/bin/python check.py` from this directory. The check intersects the
shells with every solid in the assembly and reports what hits. It is not part of
the pre-commit hook because the case is not a fabrication output and the assembly
STEP it needs is untracked.

## Current IR layout

The board uses an SMD `TSOP6136TT` receiver in a top-view package. Its lens
receives perpendicular to the board through the bottom face, along -Z. The back
shell opens there with a rounded aperture derived from U2's complete body and
lead envelope, gathered with a 3.0mm radius and then padded by `IR_CLEARANCE`.
The old receiver opening through the `+Y` end wall is closed. `D1` remains a
horizontal emitter firing along +Y through its unchanged bare bore.

## Materials

**The shells print in a tinted translucent filament**, the candy iMac look:
colour you can see the inside of rather than an opaque box. Nothing in the model
knows that, and nothing has to. Only STLs are written and an STL carries no
colour or material, so this is a choice made at the slicer and it moves no
geometry here.

It does change one part's story, and only one. The IR window insert has to pass
940nm, and if the shell filament passes it then the insert prints in the same
filament as the shells rather than being the one bought piece in the case. See
The IR end for the caveat, which has not gone away: how well a filament passes
940nm is a property of that filament rather than of anything in this model, so it
is checked against a real remote on a first print and believed after that.

The other three parts already had a material and keep it. The pad is moulded in a
translucent silicone, prototyped in TPU. The caps are translucent PETG, printed
top face down. Each of those is translucent for the backlight's sake rather than
for looks, which is why the shells joining them costs the design nothing.

## Assembly

The board hangs off the front plate. Three bosses drop from the ceiling to the
board and take M2 screws driven from the back, heads sitting on the board's
underside: a pair at the grip end, straddling the cell rather than crossing it,
and a single one on the centreline at the IR end, since the pair that used to sit
there merged into one when the board went from four mounting holes to three.

**The fastener is M2 because the board says so.** It was M2.5 until the board
replaced the plain `Edge.Cuts` circles it drilled with `H1`-`H3`, real
`MountingHole_2.4mm_M2` footprints whose own description calls the hole a loose
fit on M2 and marks the largest standard M2 head as the copper keepout. The
whole screw stack in `params.py` follows that: pilot, head, clearance and
counterbore are all sized to M2 now, and the boss is the one thing that did not
shrink with it. `case.py` prints both screw lengths, derived from the stack
rather than quoted, so a future change of fastener starts at the board and is
read back out of the model rather than transcribed into it.

## How the shells close

It is a lap joint, **back over front**. The front's cavity wall carries on past the
parting plane as a single **skirt**, `SKIRT_H` deep, and the back's wall is
hollowed out over that same band down to a thinner outer **lap**, `SKIRT_T`, that
closes over it with `SKIRT_FIT` between. The lap runs right up to the parting
plane, so the seam is a line rather than a step and the outer faces are flush
across it: nothing of the front is visible from the side below the seam. It runs
the whole perimeter, broken only at two end-wall openings: the USB shell's slot
at one end and the emitter's bore at the other. U2's receiver aperture pierces
only the back floor and does not cut the lap or front skirt. See The IR end and
Notes on the awkward bits for what all of this costs.

**The skirt is the cavity wall carried down, and it has to be.** Put it anywhere
inboard of that, in the slack `BOARD_FIT` already has, and it shares no plan area
with the wall above it: an earlier attempt built as a ring floating in mid air,
which showed up as the front shell coming out in two solids. Because its inner face
is fixed at the cavity wall, the lap, the fit and the skirt all have to fit outboard
of it inside one `WALL`. This arrangement keeps the lap at full thickness around
the perimeter.

Before this the front lapped over the back through a groove between two concentric
skirts, and before that a single skirt sleeved over a stepped-back wall. Same joint
in the same wall each time; only the side that shows changes.

Two features hold the shells together. The continuous skirt and lap align the
shells without side rails or channels.

**Two detents** at the grip end. There the skirt runs deeper than anywhere else,
down to `CATCH_SKIRT_H`, and carries two rounded rectangular windows. The lap grows
a wedge behind each, thickest at its base: the end wall rides out over the taper as
the front goes down, and the window's lower edge then catches under the flat.
`CATCH_RISE` is the skirt left below each window, so it is what actually does the
catching, and `CATCH_D` is bounded by the skirt it lands in: past the skirt
thickness less the fit it breaks through into the cavity.

That end takes no screw as a result. It also means the front has to be engaged
there first and folded down, which is the assembly order.

The detent is the window's own profile inset by the fit, intersected with the
wedge, rather than a plain rectangle lofted to a sliver. The simpler version fouled
all four rounded corners and stood proud of the window's top; the shells-mate pass
is what reported it.

A **screw** at the IR end, up through the back's floor and an internal standoff,
through the board's own mounting hole, and into the front plate's boss. So it
clamps all three parts rather than just the two shells, and it replaces the short
screw at that hole instead of adding to the count. `closure_point()` picks the hole
with the clearest run under the board: the grip-end pair are over the cell bay, so
it always lands on the single IR-end hole instead, the board's mounting holes
having gone from four to three since the pair up there merged into one on the
centreline. Its head is the only hole in the back's outside face.

Prepare the back shell first: press the IR window insert through its aperture
from inside until its pane is flush outside, apply adhesive on the continuous
shoulder under its interior flange, and let the joint set. Then assemble
front-plate-down: caps in, pad in, board on, the two short screws, hook the grip
end's detents, fold the other end down, then drive the long screw.
The caps go first and they have to: they are captive behind the ceiling, so
nothing can put one in once the pad is over them. See Keycaps. The window insert
also goes into the back shell before the two shells meet, while its inside flange
and adhesive land remain accessible: see The IR end.

The pad drops into the front shell from inside. It is one soft moulding, flat
except for its features: one raised feature per switch and a plunger under each
one resting on its switch. No skirt. The plungers are what hold it up against
the ceiling.

Every key raises a stem and takes a cap: see Keycaps.

The keys are squares with rounded corners. The side is the switch grid's own pitch
less `KEY_GAP`, in both directions, so the grid runs the full width of the case and
follows the board. That works because the switch grid is itself square to within
0.03. All eleven come out full size now: SW1 and SW2 used to come out smaller,
cut back by a pair of mounting holes that moved away, see Keycaps.

There is no moulded ring around the wheel any more. The pad used to carry a
light pipe there: a flange reaching out over the LEDs, a plug rising through
a countersunk window in the shell, flush with the wheel's top, the light
travelling inward through the silicone to a visible ring. The case prints in
a translucent material, and that material diffuses the light better than the
silicone path ever did, so the whole assembly came out: the flange, the plug,
the seat chamfers that centred it, and the shell's countersunk window with
them. What replaced it is three much simpler features.

The pad gets out of the light's way entirely, and it does it by not being
there rather than by being cut back. It is two lobes, one per key island,
each its own island's keys padded `PAD_MARGIN` on all four sides and rounded at
`PAD_RADIUS`, clipped inside the cavity by `PAD_FIT` if it ever reached that
far. Neither reaches the wheel, so nothing has to be subtracted around it.

`pad_clear_y()` is what they have to stay out of: whichever asks for more of
the lip's own rotating clearance (the lip is the widest disc of the revolved
shape and sits inside the web's own height) and the LEDs' reach plus
`PAD_LED_CLEARANCE`. The lip governs at the present layout, so the LEDs come
uncovered with margin and the light goes straight up through open air into the
ring channel. It used to be a cut: the pad was one slab reaching the full
cavity width and the full span of every key, and a straight full-width band
subtracted from it severed it into the two lobes, leaving each with a
semicircular bite facing the encoder. `pad_wheel_gap()` measures the clearance
now and `check.py` holds it, on the lobe rectangles and on the built pad's own
solids, since nothing cuts for it any more.

The ring channel is where the light goes instead of dead into a uniform
ceiling: an annular void inside the shell, circling the wheel opening and
passing over all four LEDs, cut in `led_ring_channel()`. Its floor is open
to the cavity, its inner wall stands `LED_RING_WALL` of web outside the
wheel opening's bore, its outer wall reaches `LED_RING_OVER` past the
furthest LED's body edge (derived off the placements, so moving an LED
moves it), and `LED_RING_ROOF` of translucent shell is left over it, the
surface the ring actually glows through. The LEDs fire into the void and
the channel carries the light around the wheel, so the face reads as a
lit ring rather than four dots.

Neither wall is plumb anywhere. Each is one 45 degree plane running the
channel's whole height, widest at the mouth and converging on the roof, so the
section is a trapezoid closing upward. Those nominal radii are the one height
each wall passes through rather than the wall itself: `LED_RING_CHAMFER` is how
much wider than its own the mouth opens, and equally how far up the wall crosses
it. Flaring the mouth is what the light wants, since that is where it enters,
off LEDs firing up out of the cavity, and a wall raked away from them puts more
of the roof in view of each one. A 45 degree rake is also what a printer can
close a ceiling over without support.

The mouth is the fixed end because the inner wall rakes toward the wheel's
bore, so the web is thinnest down there and `LED_RING_CHAMFER` comes straight
out of `LED_RING_WALL`, which is a light barrier as much as it is structure.
Holding the roof instead and letting the mouth fall where it liked would put
that wall inside the bore and delete the barrier outright. What the mouth's
width buys at the other end is roof: the flat the ring actually glows through
is that width less twice the channel's height, so a channel that grew taller or
a mouth that narrowed would close the ring off at the top. `check.py` holds a
floor under that flat, and `light_path` is what proves every LED still fires
into the void through it. The millimetre of overrun below the ceiling underside
carries the mouth's own width down through it, which is what leaves the cavity
ceiling a clean edge rather than a feather.

Near the X axis the channel runs past the same side-wall clip the wheel
opening is guarded by (`WHEEL_OPENING_EDGE`), at the mouth by more than
higher up, so it narrows against a chord there rather than cutting toward
the wall, and stays continuous because the clip sits well outside its inner
radius at either end. The rotary keypad recess overlaps the ring in plan on its
four diagonals, where the superellipse reaches past its own half axis, and what
the dish sinks there comes out of `LED_RING_ROOF`. That is the thinnest the
roof gets anywhere, and `check.py`'s ring stack guard holds a floor under it.

The shell's wheel opening closes in flush to the wheel: one plain bore at
the main rotating body's radius plus `WHEEL_OPENING_CLEARANCE`, ceiling
underside to flat face, nothing seated in it. That gap is the opening's own,
tighter than the `WHEEL_CLEARANCE` the pad keeps around the lip, because this
one is a visible line around the knob and the pad's is buried.

Only the seat around it is opened out, and it is not a feature of its own: it
is the keypad recess's own wheel basin, centred on the wheel and reaching
`WHEEL_RIM_LEDGE` past the bore on each of its own axes and further on its
diagonals, which the bore then cuts straight through the middle of. So the
encoder sits in the same continuous recess the keys do rather than in a bore
punched through a flat plane beside them, and what is left around the knob is a
curved ring, deepest and widest on the diagonals and carrying on into a neck on
the two bearings a neck leaves on. See Keypad recess.

Below the seat the bore is unchanged and still narrower than the lip, which
is fine for the same reason the old window never had to pass the lip either:
the board is lowered into an already-closed front shell, so the lip stops
below the ceiling and never transits the opening (see the assembly note
below). `check.py`'s wheel seat clearance pass measures the built opening
against `board.wheel_profile()`'s housing and knob, the parts that do reach
the ceiling, rather than trusting `WHEEL_OPENING_R`'s formula: an earlier
full-ceiling clearance cut once silently erased the opening's real shape
while the formulas behind it still looked right on paper. The face is flush
to the wheel's top as well as its side now: `SHELL_FRONT` is `WHEEL_TOP`
itself, the measured knob height, rather than a height constant tuned above
it, so the knob finishes level with the face and a wheel change moves the
face with it.

Print in TPU to try the pad, mould it in a silicone to keep it; the shells
are what have to print translucent now, so the light path is the case
material itself rather than anything moulded.

## The dropped face

The ceiling used to be one height everywhere, `FRONT_KEEPOUT` above the
board, sized to the tallest thing under it: the USB-C shell. Every switch
sits far shorter than that, so the pad's web floated well clear of them,
and each plunger was a long, unsupported peg spanning the difference. That
is gone. The keypad region of the ceiling now sits at `CAVITY_FRONT`,
`KEYPAD_KEEPOUT` above the board: the switch height plus
`KEYPAD_PLUNGER_STUB`, a short, real stub rather than dead air, so a press
still concentrates through a stiff post onto the actuator rather than
through a web sagging down to meet it.

`SHELL_FRONT` no longer follows `CAVITY_FRONT` down. The two were coupled
through a ceiling constant once, so dropping `CAVITY_FRONT` to sit on the
switches would have dropped the face with it, leaving no room for the
counterbore stack over the keys. `SHELL_FRONT` decoupled from it, first as
a fixed `FACE_HEIGHT` constant and now as `WHEEL_TOP` itself, the wheel's
own measured knob height, so the face closes flush to the wheel by
construction instead of standing a tuned distance above it. The keypad
ceiling is whatever gap that leaves: `KEYPAD_CEILING` in case.py, a report
value rather than a tunable input. The counterbore, the land, the keypad
recesses and caps flush with the face all still follow `SHELL_FRONT` the same
way they always did; only where the fixed height comes from changed.

The USB-C shell is still the tallest thing under the shell, just no longer
everywhere. `usb_pocket()` keeps a local pocket over the connector's own
footprint, reaching `CAVITY_FRONT_USB`, `FRONT_KEEPOUT`'s full original
depth, inside an outer face that stays flat at `SHELL_FRONT` everywhere,
the keypad included. It is a bump on the cavity side only, never on the one
outer face plane: nothing about the case's outside says where it is. With
the face down at the wheel's top, the roof over this pocket is deliberately
the thinnest ceiling anywhere; `check.py`'s USB pocket pass holds it above
its own floor, `USB_CEILING_MIN`, and nothing loads it directly.

D1 needed the same treatment once and no longer does. While the emitter sat
on the board's front, its dome stood taller than `CAVITY_FRONT` across its
whole footprint, not only where the lens overhung the +Y wall, so it had a
local ceiling pocket of its own alongside the wall relief. The emitter moved
to the board's bottom side, and both went with it: the only part of `D1`
still in the front shell's half of the case is its leads bent up through the
board, which stop well short of the keypad ceiling. `usb_pocket()` is the
only local ceiling pocket left. See Notes on the awkward bits.

The bosses needed the same treatment for a different reason. `BOSS_PILOT_DEPTH`
is a fixed screw length, not something that shrinks with the ceiling above
it, and the keypad region's own thinner ceiling no longer has room for it.
Each boss now carries its own material past that ceiling, all the way to
`SHELL_FRONT`, the same local-pad idea as the USB pocket with material on
the void side instead: a full-depth post for the pilot hole regardless of
how thin the ceiling around it has gone. `check.py`'s feature clashes and
interference passes see the boss at its real, taller extent now, not the
keypad ceiling's own shorter one, which is what would have hidden a
collision with a switch or a courtyard the boss now reaches further into.

One consequence carries through to the wheel: `SHELL_FRONT` is `WHEEL_TOP`
now, so the knob finishes flush with the face, neither recessed under it
the way the fixed `FACE_HEIGHT` left it nor standing proud the way it
briefly did while `SHELL_FRONT` was coupled to the dropped `CAVITY_FRONT`.

## The IR end

The two IR parts now use different faces. `U2` is the SMD TSOP6136TT receiver on
the board's bottom side and receives perpendicular to the board along -Z. It
looks through a rounded aperture in the contoured back floor. `D1` remains the
horizontal through-hole emitter and fires along +Y through the end wall. Its
bare round bore is still drilled to the measured lens with `IR_EMITTER_FIT`
around it. Nothing covers or otherwise changes that bore.

**U2's whole package sets the aperture.** The Panhead STEP model is multiple
solids, so the model gathers body and leads with
`board.part_envelope("U2", radius=3.0)` before adding `IR_CLEARANCE` in plan.
The aperture is the rounded rectangle around that complete envelope. The old
receiver relief in the +Y end wall is absent and the wall is solid there.

The lens looks like it should poke out of that bore and does not. It stops short
of the exterior face by more than the wall is thick, so it sits back down the
bore rather than standing proud of the case; `case.py` prints where it lands, and
`board.emitter_envelope()` is what measures it, so a future emitter that does
reach daylight shows up there rather than in an assumption here.

**The window is a separate conformal stepped insert installed from inside.** Its
outer pane follows the actual back surface from the exterior to `IR_WINDOW_T`,
so the installed outside face is flush with the shell instead of recessed or
proud. The pane extends into the nominal aperture by `IR_WINDOW_PRESS`, 0.05mm
per side, which holds it while adhesive cures. An open interior flange extends
past the pane by `IR_WINDOW_FLANGE`: it retains the insert against outward force
without adding thickness across the optical centreline.

The back's larger inside rebate stops one pane thickness above the exterior.
That leaves a continuous shell shoulder under the flange. The shoulder is both
the mechanical stop and the adhesive land; `IR_WINDOW_FIT` leaves room around
the flange perimeter for adhesive. Installation is therefore inside-first:
press the pane down through the back-floor aperture until its conformal outside
surface is flush, bond the flange to the shoulder, then close the shells.

**Print it in the shell filament, and use IR-pass acrylic only if that fails.**
The first print must be tested at 940nm with a real remote because visible
translucency does not prove near-IR transmission. If range or angle is poor,
replace it with IR-pass acrylic made to the same stepped, conformal geometry.
The old flat-sheet outline is not a drop-in fallback for this contoured insert.
The export name remains `c6remote-ir-window.stl` for either manufacturing path.

## Keycaps

Every key gets a rigid cap over a soft stem. The stem is moulded into the pad
where a keytop used to be; the cap is a separate part carrying the legend, so
changing what a key says is one small reprint instead of a whole new pad.

All eleven now: `SW1` and `SW2` used to be `MOLDED_KEYS`, the pair the screw
bosses cut back to about half size, too small for a recess, a wall around it
and a legend all to fit, so they kept the keytop moulded straight into the pad
instead and stood `KEY_PROTRUSION` proud of an otherwise flush face. The
mounting holes that shrank them moved, from four down to three, and neither of
the two left is close enough to bind these two any more: `key_size("SW1")` and
`key_size("SW2")` both come out at the full grid size now, the same as every
other key, so they take a cap like the rest and the face is one flush height
throughout. `MOLDED_KEYS`, `KEY_PROTRUSION` and the moulded-keytop branch in
`button_pad()` are gone rather than kept idle, since nothing exercises them any
more; if a future layout ever binds a key against a boss again, `key_size()`
still shrinks it the same way it always did, it would just need a keytop path
rebuilt rather than reawakened.

**A cap is a squircle in plan, not a rounded square.** Every keytop, the nine
grid keys and `SW1` and `SW2` with them, is bounded by a superellipse, the same
family of curve the keypad recesses are drawn on, so a cap reads as belonging
to the dish it sits in rather than as a different family of shape dropped into
it. The corner is one continuous blend running out over each side, with no
flat-to-curve transition to see.

The caps carry their own exponent, `KEY_SQUIRCLE_N`, below the recesses'
`KEYPAD_SQUIRCLE_N` rather than equal to it. They shared one number at first,
and at the recesses' value a cap's flanks read as straight: a small shape seen
next to a large one wants more bow in its sides than the large one does before
it stops looking like a tile. The caps' exponent is lowered until the sides
visibly bulge, and stops short of two, which is the circle.

Two things move when it drops, in opposite directions. The largest square the
cap top holds shrinks, since a superellipse's inscribed square touches it on
the diagonals and that contact comes in as the exponent falls, so the room a
legend has to fit in `LEGEND_INK_MARGIN` gets tighter; `SW9` and `SW11` carry
the widest ink and are what bind. Corner reach goes the other way: a lower
exponent pulls the diagonals in, so a counterbore's outermost point sits nearer
its own centre and `counterbore_dish_margin()` reads more room against the
recess rim, not less. Both are measured by `check.py` rather than argued here.

`_key_prism()` is the only place the shape is stated and the whole chain goes
through it at four sizes: the cap body, its flange, and the counterbore and face
hole that `shells.py` cuts. So all four are the same curve scaled rather than
offsets of one another, which is what lets `CAP_FLANGE_OVERLAP`,
`CAP_FLANGE_CLEARANCE` and `CAP_GUIDE_CLEARANCE` keep meaning what they say.
Two concentric similar superellipses sit exactly their stated gap apart at their
closest approach, on the axes, and stand further apart everywhere else, so each
of those widths is still its own worst case. That is not obvious and it is not
assumed: `check.py` walks all three fits around the full perimeter, because a
corner that pulled in faster than its neighbour would eat the retention without
moving a single number the width arithmetic reads.

What the corner does change is that it pulls *in* relative to a rounded square,
by about half a millimetre at this size. That buys diagonal clearance, and it
costs top area: see the legend note below.

**A cap cannot fall out, and it cannot be swapped from outside either.** Each
cap carries a solid flange at its base, wider than the hole through the front
face by `CAP_FLANGE_OVERLAP` a side, riding in a counterbore sunk into the
ceiling behind that face. Pull on a cap and the flange catches under the face
land. So the cap goes in from *inside* the shell, and **changing a legend
means opening the case**: back off, the two board screws out, board out, pad
out, cap out. That is a deliberate trade and not a bug to be rediscovered
later. The retention it buys is positive rather than frictional, which is what
the previous stem-and-barb arrangement could not promise.

`KEYPAD_CEILING` carries both features and is thick enough to now that
`SHELL_FRONT` no longer follows `CAVITY_FRONT` down. The counterbore takes
`CAP_LIFT`, `CAP_FLANGE_T` and `CAP_FLANGE_FLOAT` of it, and what is left above is
the face land. `CAP_FLANGE_FLOAT` is why the cap still presses freely: it is
captive, not clamped. The cap's top sits flush with the face rather than proud
of it, `CAP_PROTRUSION` is 0, so a press sinks it `SWITCH_TRAVEL` into its own
face hole instead of dropping it from proud toward flush; the guide clearance
already leaves it room to do that.

**The cap is guided straight by two lands and a locating recess.** The visible
body stands in the face hole at `CAP_GUIDE_CLEARANCE` a side, deliberately
tighter than `KEY_CLEARANCE`, because that hole aligns the cap rather than
merely clearing it. The flange runs in the counterbore at
`CAP_FLANGE_CLEARANCE`, looser on purpose so the two are not fighting over the
same axis. The recess over the stem is the primary guide, and everything is
square, so nothing can rotate.

The stem stays a rounded square while the cap around it went to a superellipse,
which is deliberate rather than an oversight: nothing outside the cap sees the
stem, the socket is moulded to match it, and the two only have to agree with
each other. The stem is a rounded square rather than a cross or a cylinder, because a legend
has an orientation and a round stem holds none, and it runs the full recess
depth so the stem meets the ceiling. That is the load path: a press drives
through the stem, not through the flange, and the pad's translucent silicone
touches the cap where the backlight has to cross into it. There is no barb on
it. `STEM_GRIP` is what is left of the old fit, and its job now is preload
against `CAP_FLANGE_FLOAT`: if a cap rattles, raise it, and do not touch the
flange stack. Prototype the fit in TPU before committing to a mould.

The recess is shallow now, `CAP_TOP_T` came down to 1.0 when the face
flattened and left no room for a deep grip, so it registers the cap in plan
rather than doing much to hold it upright; retention and squareness both come
from the flange and the face land instead. `SOCKET_LEAD` is still generous
because the pad is fitted blind: it goes down onto every stem at once with the
caps already in the shell and nothing visible, so the mouth has to funnel a
stem in rather than land square on it. `CAP_WALL` is what bounds it, since the
mouth is the widest the cap is ever hollowed.

Legends come from `LEGENDS`, one entry per cap, debossed `LEGEND_DEPTH` into the
cap top. A string is set in `LEGEND_FONT`, which is vendored under `fonts/` rather
than looked up by family name so the same source cuts the same legend on any
machine. That font carries every arrow and geometric shape the keypad uses, so
most entries are a single Unicode glyph and need no file of their own. A
`("svg", path)` pair is the escape hatch for artwork no font carries, imported
and scaled to `LEGEND_SIZE`: the power symbol and the microphone are drawn that
way under `glyphs/`, DejaVu having neither. Legends need no rotation: the model's
+Y is away from the grip, so they read the right way up with the grip end toward
you.

**An SVG legend has to be filled outlines, not strokes.** `import_svg` hands
back closed wires that the model fills, so a stroked path arrives as a hairline
and cuts nothing at all. Both files under `glyphs/` are built from filled closed
paths with no hole in any of them: the power symbol's ring is broken at the top,
which makes it a C rather than an annulus, and the microphone's yoke is a band
open at the top for the same reason. Holes are not forbidden in principle, a font
glyph like a hollow triangle carries one and cuts correctly, but the SVG branch
falls back to filling each wire on its own where a document imports as wires
rather than faces, and that fill would swallow a hole.

**A legend can carry its own size**, `(spec, size)` in place of a bare spec.
`LEGEND_SIZE` is an em rather than an ink height, and the eleven legends spend
that em very differently: a solid arrow fills most of it, a hollow one draws the
same outline in a stroke a fraction as wide, and a hyphen would be a sliver of
it. The hollow shapes all go up together so their strokes stay printable and so
they read as one set, and the cross, plus and minus go up to sit at the arrows'
own ink height rather than reading a size smaller than the key beside them. Per
entry rather than globally, so the ones that already read well are not dragged
along. `case.py` prints each legend's measured ink and how much it cuts.

**What the keypad says.** Three of the arrows are a d-pad, left, down and
right, and there is no up: nothing on the layout reads as up any more, so that
cap joined a set of four outline shapes instead, a cross, a square, a triangle
and a circle. `SW1` and `SW2` keep their SVG power and microphone marks, and
the last pair are a minus and a plus. The minus is `U+2212` rather than the
ASCII hyphen, which stays a sliver whatever size it is set at: the true minus
sign is drawn to the plus's own bar length, so the pair comes out matched, and
`case.py`'s measured ink confirms it rather than the choice being taken on
trust.

Print a cap top face down. The deboss then needs no support and comes out crisp,
and `CAP_TOP_T` less `LEGEND_DEPTH` is the translucent roof left for the pad's
backlight to glow through. In that orientation the flange is a stepped overhang
partway up, which prints without support at this scale and is the right way round
regardless, because the legend is what has to come out clean. Translucent PETG on FDM is the material; a resin print
is worth it for legend detail.

Caps are exported one STL per ref, translated to the origin. `keycap()` builds them
where their switches are, which is what `--show` wants and is nowhere near what a
slicer wants. `c6remote-caps.json` is where each one came back from, written
alongside the STLs so anything reassembling the export reads it rather than
rediscovering the switch positions. It is caps only: the shells and the IR
window insert are exported where they belong in the case frame, so they need no
entry, and giving one an entry there would name it a keycap.

## Keypad recess

One continuous concave recess sunk into the front face, with no flat floor and
no wall anywhere. It runs the length of the keypad as three dished basins on a
single centreline, over the key grid, over `KEYPAD_ISLAND_2` (`SW1` and `SW2`)
and the mic inlet beside them, and around the wheel, joined by two neck channels
that ramp between them and flare out into each basin's rim.

Each basin is bounded in plan by a superellipse, and its depth is zero on that
curve and greatest at its centre, following a circular-arc sag: flat at the
bottom of the basin, steepening toward the rim.

The two keyed basins use `KEYPAD_SQUIRCLE_N`, a squircle: a rounded rectangle
whose corner never stops turning, which is what lets a rim be one continuous
curve with no arc-to-line junction to blend, and which is the right shape for a
field of square keys. The wheel's uses its own lower `WHEEL_SQUIRCLE_N`, because
a ring around a round knob wants a round outline instead. A superellipse has
zero curvature exactly on its axes at any exponent above two, so what the
exponent really sets is how far either side of a flank the outline stays
visually straight; at the keyed value that was long enough on a basin this size
to read as a flat edge beside the knob, and the lower one brings it close to the
circle's own. What is spent for it is corner reach, the diagonals of a
superellipse standing further out the higher the exponent, so the seat ring
widens less toward its corners than it used to. Two is the floor and it is a
real one, not a matter of taste: see the seat below.

A rim is where the recess feathers back into the face, and it reads as a crisp
boundary rather than a soft one. Strictly there is a wall there, the sag having
a vertical tangent in its own normalised coordinate, but a half axis is many
times the depth, which compresses that wall into far less than a print layer.
At print resolution it is an edge. A sag that feathers properly at the rim, a
parabola or a raised cosine, was rejected for the opposite reason: both put
almost all the depth in the middle and leave the outer keys barely dished,
which is where most of the keys are.

### One field

The three basins and the two necks are one **depth field**, `face_depth_at()`,
and it is the only recess arithmetic in the model: the cut is lofted from it,
`check.py` measures the built solid against it, and the mic inlet opens at
whatever it says the floor is over the board's acoustic port. Nothing can drift
from anything else because there is nothing else.

The field works because the whole recess is a single column along y: the basin
centres share an x to within a few hundredths, and they are disjoint in y, so
every y has exactly one interval in x. `recess_spine()` is that column, three
scalars per y: how wide the recess is, how deep it is on the centreline, which
cross-section it carries, and which exponent that section is drawn with. Inside
a basin's body all four are that basin's own superellipse functions, so the
field there is exactly the dish it would be on its own. Inside a join all four
are cubic Hermite bridges, one each, matching value **and slope** at both ends,
which is what makes the field C1 across a junction rather than merely
continuous. So the floor simply ramps from one basin surface to the other and
the outline simply turns from one rim into the other, with no waypoint of its
own in any of them. The exponent is bridged along with the rest, since the
wheel's differs from its neighbours': it is constant inside a basin, so its
bridge leaves either end with zero slope and the cross-section morphs from one
basin's curve to the other's without a tangent break of its own.

### Rounding the joins

The width bridge was two cubics once, meeting at the join's midpoint at a
stated waist with zero slope. It held that width exactly and it read badly:
forcing a flat spot in the middle of the turn puts the tightest curvature of
the whole outline right at the waist, so the join looked like a slot pinched
between two trays rather than one shape flowing through. Dropping it for a
single cubic across the join roughly tripled the radius at the same reach, with
the waist barely moving.

What sets the roundness instead is `KEYPAD_JOIN_REACH`, keyed **per basin**:
how far inside its own rim each basin lets a join begin, and so how much width
the outline has to turn through. Per basin rather than per join because that is
where the constraints are. The two keyed basins are held down by their own
outermost key row: past that a reach starts reshaping the floor over those keys'
counterbores rather than only outboard of them, which costs no land (the deepest
point over a counterbore is always the one furthest inboard) but does start
eating the basin's surface where the keys are.

The wheel's reach is much the largest, and its exponent is why. A rounder
outline is a narrower chord at any given distance from the centre, so the same
reach leaves a join far less width to turn through and the radius collapses; the
reach has to grow to pay for the roundness. It has room to, no keys sitting
under that basin, and paying it left both joins rounder than they were before
the flanks were rounded at all. What `check.py` holds are the structural bounds:
a reach may not run past its own basin's centre, or that basin would stop
reaching the depth it is stated at, and two joins may not overlap, or the basin
between them would have no body left.

There has to be some reach at all. The sag's tangent at a rim is vertical, so a
bridge leaving from one would dive straight through zero and tear the recess in
two. What the reach costs is the basin's inboard rim, which is the point of the
merge: only the outboard halves of the two outer rims are still the superellipse
they were drawn from. Every reach takes its bridge past the wheel opening's bore,
so on the two bearings a join leaves on there is none of the wheel basin's own
curve left in the seat at all and the join flows straight out of the bore wall,
which is why the seat reads deeper there than on the free axis.

The waist is then measured rather than set. `KEYPAD_NECK_MIN` is the floor under
how narrow the recess may get, and `check.py` holds both that and a floor under
the radius the outline actually turns through, since a reach cut back would
show up in nothing else: a tight join still builds cleanly, still keeps its
depth and still keeps most of its waist width.

### One cut

`keypad_recess()` builds the whole thing as **one** solid: a loft along y
through `recess_stations()`, each station a cross-section made of the floor curve
carried up two vertical rim walls and closed across `MERGE` above the face. One
loft, one wall surface, no seam anywhere. Fusing five lofts would have left a
tangent-continuous surface with four edges across it, and the merge exists
precisely so there are none. Stations are spaced by the superellipse's own
parameter rather than evenly, because both the width and the depth turn fastest
at a rim and barely at all in the middle, with extra even steps across each
join; the outermost carries `KEYPAD_TIP_WIDTH` of its half axis rather than being
a point, since a degenerate section is what makes a loft come back non-manifold,
and a superellipse's own end is flat to within microns over that much of its
width so the blunt tip is faithful. The section is wound counter-clockwise
deliberately: `BuildSketch` mirrors a clockwise sketch, which puts the sag above
the face instead of below it.

The loft is **ruled**, and that is the hard-won part. Fitting a spline in y
through this many sections is the obvious choice on a surface whose whole point
is having no creases, and it worked until the wheel basin took its own exponent;
that change was enough to tip the fit into diverging outright, returning a single
valid-looking solid of negative volume spread over half a metre. Nothing in the
arithmetic was wrong, so every plan-geometry pass still agreed with it, and what
surfaced it was two features at the opposite end of the case failing for no
reason. The stations carry the fidelity in y instead and carry it easily, their
spacing putting the chord within well under a micron of the field. The other axis
was already a polyline, so this makes the surface a fine polygonal approximation
in both directions rather than one, which is the honest description of what it
always was. `check.py` now measures the built solid against the box its own field
spans before anything else probes it, so this cannot recur quietly.

This is the second place in the model where a smooth loft had to be given up for
a ruled one, and for the same underlying reason: see the back shell under Notes
on the awkward bits, where the fit overshoots its own sections instead of
diverging outright. Treat a fitted loft through many sections as suspect here.

### Sizing

The two keyed basins are sized to **bound** their coverage box, not to be
inscribed in it. The box is the island's own keys padded `KEYPAD_MARGIN` on
every side, and a superellipse inscribed in a box touches it only at the four
edge midpoints and passes well inside all four corners, which on this layout
would run the rim straight through the corner keys' holes. Growing both half
axes puts the box's corners on the curve instead. Except in x, where that
reaches inside `KEYPAD_EDGE_MARGIN` of the case's exterior wall, so that half
axis is capped there and the y one is left alone: the cap costs recess beyond
the box's corners, and taking it out of one axis leaves more around the corner
keys than taking it out of both. What `check.py` holds is the thing that
actually matters, every counterbore inside the rim, rather than either stated
margin.

The wheel's basin is not sized off a coverage box at all. It has no keys under
it, so its half axes are stated outright, `WHEEL_BASIN_SPREAD` past the wheel
opening's bore on each axis and square. `WHEEL_RIM_LEDGE` used to be that
spread, and sizing the basin on the clearance minimum is exactly what left the
ring around the knob as narrow as the minimum: a rim rather than a saucer. It is
only the floor now, and `check.py` holds the built rim to it.

Three things bound the spread, and the tightest is not the obvious one. In x it
is `KEYPAD_EDGE_MARGIN` against the case wall, the same cap the keyed basins
hit. In depth it is `LED_RING_ROOF`, since a wider basin crosses more of the ring
channel's annulus and does it further down its own sag. In y it is the
neighbouring basins, and that one binds first: the spine is one interval in x per
y, so exactly one thing has to claim each y, and a basin wide enough to reach
past where its own join begins overlaps its neighbour somewhere no join covers.
Nothing about that failure is visible downstream, since the recess still builds
and stays continuous and only one stretch of rim quietly follows the wrong
basin's curve, so `check.py` walks the span and fails on it by name.

The bore then cuts straight through the basin's middle, so what is left is a
curved seat ring around the knob, deepest and widest on the diagonals where the
superellipse reaches furthest and shallowest on the free axis. On the two
bearings a join leaves on, the seat carries on into the join rather than
feathering back to the face, so it reads deeper there; the wheel's reach is
longer than `WHEEL_BASIN_SPREAD`, so on those two bearings the bridge takes over
inside the bore and none of the basin's own curve is left in the visible seat at
all.

That sizing rule is also where the exponent's floor of two comes from. Above two
a superellipse is closest to its own centre on its axes, so the stated half axis
*is* the clearance and the diagonals only ever stand further out; below two that
inverts, the diagonals come in nearer, and `WHEEL_RIM_LEDGE` stops being the
clearance the seat is sized on. Since the exponent is a tunable, `check.py`
measures the clearance around the merged rim rather than trusting the rule, which
covers the joins as well: their bridges take over the outline either side of the
basin and the rule says nothing about where those run.

That is also where the ring channel's roof gets thin: the wheel basin's
diagonals cross the channel's inner edge, and both necks run out across the
same annulus on the way to the basins either side. What any of them sinks there
comes out of `LED_RING_ROOF`, and `check.py`'s ring stack guard holds a floor
under what is left, walking the whole annulus rather than one radius, since the
basin nearest the channel crosses it from outside and gets deeper the further
out it reaches. Rounding the wheel's flanks bought roof back here: a lower
exponent reaches less far on the diagonals, so the basin crosses less of the
annulus than the squircle did.

### What the checks hold

`check.py` measures the built solid against its own field first: one piece, of
positive volume, filling exactly the box the spine spans. That is a guard on the
loft rather than on the design, and the section above says why it exists.

Then it proves the merge rather than assuming it. The field is walked along
the centreline between the two islands' outermost key rows and has to stay
strictly deeper than a floor, because three basins that had pinched apart would
still build one perfectly valid cut solid that simply ran to nothing twice on
the way. Each join's waist has to clear `KEYPAD_NECK_MIN` and stay narrower
than both the widths it bridges, and each join's outline has to turn through at
least a floor radius, which is the guard that keeps them round. A reach also may
not run past its own basin's centre, and two joins may not overlap: both are
invariants of the construction that nothing else would notice breaking. The
merged rim has to clear the wheel opening's bore by `WHEEL_RIM_LEDGE`, which is
what makes the wheel basin's sizing rule mean what it says at whatever exponent
it is given. The one-sided
slopes of both the floor and the plan outline are read either side of every
junction and waist, which is what says a join meets a basin with no tangent
break and the outline has no cusp; those slopes are taken to second order, since
curvature is deliberately discontinuous at a junction and a first-order quotient
would report a break of its own wherever a junction sits on a steeply turning
part of a rim. The built solid is then probed beside every key, beside the mic,
on the wheel seat on four bearings and at both waists, open just above the local
floor and solid just below it, so the surface is where the field puts it. And
the basin centres are still required to share one x, since the whole
single-column construction rests on it.

### What sits in it

The mic opens through the curved floor rather than a plane. `mic_face()` reads
the recess's own depth directly over the board's acoustic port, and the whole
funnel hangs off that, so the concave fillet at the mouth is tangent to the
floor where the port is. Across the mouth's own width the floor rises away from
the port by a fraction of a print layer, which the mouth's straight run past
that height absorbs.

Caps are unaffected in how they are built and land flush with the face exactly
where `CAP_TOP` has always put them, so each one stands proud of the floor
around it by whatever the recess is locally deep: most at the key nearest a
basin's centre, least at the corner keys. That is the whole point of the shape.
What it costs comes out of the flange stack rather than a thicker keypad
ceiling: `CAP_LIFT` and `CAP_FLANGE_FLOAT` each gave up a little of their own
room, and the binding constraint is the deepest point the recess reaches over
any counterbore, which is `SW7`, sitting under the grid basin's own centre. No
join reaches the deepest point over any counterbore, so merging the basins and
then rounding the joins both cost the land nothing.

A full-depth tray existed here once and was removed. A shallow pocket joined
across the wheel by a neck band replaced it, then three independent squircle
dishes replaced that. This is the two ideas together: the dishes' curvature and
the pocket's continuity, with the join done in the depth field rather than by
blending a plan outline and drafting a wall off it.

## The cell

One AA lies along the board underneath it, horizontally, pushed toward the bottom
end of the case by `CELL_END_MARGIN` rather than centred, so the deep part of the
case is the part the hand holds.

Its diameter is what sets the thickness there, and only there. The cell's top face
sits one `CELL_TOP_GAP` below the board, not below whatever happens to be in the
way: anything hanging lower than that counts as an obstacle and the bay is chosen
from the runs that have none. That costs bay length, and buys the cell sitting
right up under the board instead of clearing a component it never needed to be
near. `case.py` prints the run it found, which is still far longer than one cell
needs.

**Only a 14500 works electrically.** The bay is sized to AA at its catalogue
maximum, so an alkaline, a NiMH and a 14500 all drop in, but the XIAO charges and
regulates from a single lithium cell at 3.0 to 4.2V. A 14500 is that chemistry in
the AA form factor, so it needs nothing. Alkaline at 1.5V and NiMH at 1.2V do not,
and no arrangement of them fits the window without changing the board: three NiMH
in series lands in range but wants delta-V charging, not the XIAO's CC/CV.

Swapping the cell means unclipping the back. There is no door, and the contacts
are not modelled.

Two saddle ribs cradle it: the notch locates it in X and Z, the rib faces stop it
sliding. Vertically it can lift `CELL_TOP_GAP` before it touches the board, so it
wants a foam pad or a strip of tape.

`CELL_D` and `CELL_L` are the only things to change for another format. Cavity
depth, cradle, contour and case thickness all follow.

## The back's shape

The back is not a slab. It runs full depth over the cell and its cradle, which is
down at the bottom end, then tapers away over `CONTOUR_BLEND` toward the top, and
rolls up through `CONTOUR_TIP_R` at each end so the bottom meets the end face
tangentially instead of squaring into it. `case.py` prints the heights.

**Each end's depth is derived, not chosen.** `end_depth()` takes whatever hangs
below the board out past the cradle on that side, so the two ends can differ.
Both currently fall back to `CONTOUR_END_DEPTH`: U2's low SMD package opens
through the back floor instead of setting an end-wall depth, while J1's assumed
depth at the other end comes up short too.

The +Y fallback is still constrained by D1. Its unchanged bare bore is drilled
to the measured lens rather than clipped to an available wall, so reducing the
end depth can make the rolled bottom edge break into it. U2 no longer spends any
of that end-wall budget. Its aperture and insert follow the contoured floor, and
the receiver-path and clearance passes probe that built geometry directly.
`IR_RELIEF_DEPTH` now belongs only to the D1 and USB end ports.

The cell and cradle have the largest bottom-edge round. The round transitions over
the upper contour taper to `EDGE_R_BACK_IR` near U2. This keeps the battery area
full in the hand, but leaves a smaller valid section for the lifted IR insert.

**The round runs the whole way round the plan, corners included.** Each loft
section is as wide as the plan profile is at that point, not as wide as the case.
The round then lands tangent to the wall everywhere along the perimeter. A
full-width section lands tangent on the straight sides only. Where the plan turns
a corner, that section meets the wall part way up its round, and the abrupt edge
this leaves is what both ends used to carry. Each section also sits a hair outside
its own chord, because a straight run between two sections falls inside a turning
plan and would put a flat where the wall's arc must be.

Each end region carries its own stations, spaced by equal angle from the end face.
Both the tip roll and the plan corner stand vertical where they meet that face, so
an equal-y step there spans more of either curve than the whole rest of it.
`END_SECTIONS` sets the count and `END_STEP` stops the crowding at the tangent. The
stations track the outer profile's corner only, because a section costs real time
and memory. The cavity's corner starts a wall further in and is sampled more
coarsely. That leaves its floor a hair proud of tangency at the corner, and so a
hair of extra wall, on a face nobody sees.

The shape is a loft, not a prism cut to size, and that is deliberate. The rounding
on the bottom edges has to follow the taper, or it only exists where the case
is deepest. It is also why there is no fillet anywhere in the back shell:
intersecting a prism with a contour leaves degenerate zero-length edges along the
bottom, and OCC refuses to fillet across those at any radius at all. Two further
traps, both of which cost a debugging round and are guarded by named constants now:
the sections must be ruled rather than smoothly interpolated, because a smooth loft
overshoots its own sections and stops intersecting the plan profile; and the loft
has to run past the case, because ending it flush means the two bodies share their
end faces and the intersection fails outright.

The front keeps a small round on its top edge, from an ordinary fillet: it is a
plain prism at that point, with one clean edge loop and no contour to trip over.

## Verification

`check.py` is the part worth keeping. Thirty-one passes, because no single one
is sufficient:

- **Aperture probes** catch a hole that never got cut. A switch tops out well
  below the ceiling, so a missing key hole collides with nothing and the
  interference pass stays quiet.
- **Pad fit** confirms the pad drops into the front shell without fouling it.
  Nothing of the pad comes through the front face to probe per key any more,
  every switch taking a stem and a cap rather than nine stems plus two moulded
  keytops: caps fit covers all eleven of those against the shell instead.
- **Plunger stub contact** confirms every switch's plunger actually lands on
  `SWITCH_TOP`, not merely in the formula. Probed on the built pad, since a
  clearance cut or a wrong z reference could leave one short, or long enough
  to overshoot into the switch, without any volume-based check noticing
  either.
- **Caps fit** puts each of the eleven caps against the shell released and pressed, against its
  neighbours in plan, and against its own stem, then checks the arithmetic the
  solids cannot show: locating recess depth, wall left around it, the flange
  still caught by the face land with the cap pushed as far off centre as its
  guide clearance allows, the insertion path in through both holes, the flange's
  axial float, the rib of ceiling left between two counterbores, travel against
  `SWITCH_TRAVEL`, and the roof and the flat top left for a legend. The cap-to-pad
  overlap is the fit rather than a fault, so it is a zero overlap that is reported.
- **Cap fits around perimeter** confirms the flange overlap, the counterbore
  clearance and the guide clearance are each no tighter anywhere around the cap
  curve than the width they are stated at. Caps fit does all its retention
  arithmetic on widths, which is only the truth if the axis gap between two of
  these curves is also their closest approach. It is, for concentric similar
  superellipses as it was for the rounded squares they replaced, but neither is
  obvious and the corner is exactly where a plan-shape change breaks it: had the
  flange's corner pulled in faster than the hole's, the retention would have
  gone without a single width moving.
- **Caps flush** confirms a cap's top actually lands level with the flat front
  face, not merely close to it. `CAP_TOP` is `SHELL_FRONT` plus `CAP_PROTRUSION`
  by construction and `CAP_PROTRUSION` is 0, so this should always read as
  zero; it exists to catch the two coming apart.
- **Caps proud of pocket** confirms every cap stands above the recess floor
  around it by exactly the local depth of that recess, on top of landing flush
  with the face. Both are built from `SHELL_FRONT`, so the difference should
  always read as `face_depth_at()` exactly; it exists to catch the two drifting
  apart. Every cap rather than one, the floor being curved now, so a single
  reading would only prove it at whichever key was picked. A floor beside it
  catches a recess that went shallow enough to stop showing at all.
- **Legends present** confirms every cap carries a real legend, cut out of one
  solid cap, in a glyph the vendored font actually has. A blank cap is the
  quietest failure in the model: an empty entry, a mistyped SVG path or a
  character DejaVu does not carry all build a cap that passes every other pass
  here. The last of those is why the font's own cmap is read rather than the
  rendering trusted: freetype maps a character the font lacks onto `.notdef`,
  which DejaVu draws as a hollow box with several times the ink of the smallest
  legend here, so it would clear any volume floor and ship as a legend that
  reads as a rectangle. That matters more than it used to, one cap now carrying
  a hollow box on purpose: nothing but the cmap tells `U+25A1` apart from a
  glyph the font dropped. Each
  cap is also weighed against the same cap built blank, so the volume is what
  the deboss removed rather than what its solids measure, and the ink is
  measured against the largest square the cap's own curve holds rather than the
  font size it was set at. That last number changed with the cap shape and it is
  worth being precise about which part of the change did what. It used to be a
  proxy, the rounded square's side less twice its corner radius, which stopped
  off the curvature entirely and understated the room badly. A superellipse has
  no straight run at all, so the proxy could not carry over even in principle,
  and it is now the exact inscribed square. Two legends were failing against the
  proxy and pass against the exact figure; both would also have passed against
  the exact figure computed for the old rounded square, so the criterion is what
  resolved them, not the shape. The shape moved it the other way, costing usable
  top, and giving the caps their own lower `KEY_SQUIRCLE_N` costs a little more
  again: the inscribed square's contact is on the diagonals and a lower exponent
  brings it in. `SW9` and `SW11` carry the widest ink and are what this pass
  binds on. `LEGEND_INK_MARGIN` is unchanged.
- **Mic fillet** confirms the inlet is really the funnel it is described as: a
  real cone up most of the duct and a concave quarter-round finishing it at the
  floor it arrives in, the second keypad recess's own dish directly over the
  board's port rather than the front face. Probed
  by bisecting for the true opening radius, the same reasoning as wheel seat
  clearance: a mouth referenced to the wrong height, or one cut entirely above
  the floor, removes nothing and leaves an inlet the aperture probe still reads
  as open, and a taper dropped from the fuse leaves the same. Probed at several
  heights up each band rather than one, because the ends of a band cannot tell
  an arc from a cone or the plain bore either might have been built as and the
  middle can, and each reading is compared against the same curve `mic_bore()`
  is cut from rather than a second description of it. The taper's probes carry
  most of the weight, having a long run to diverge over, and the two lowest of
  them are what would catch the duct being built hollow again, which is the way
  the taper can be erased rather than merely mis-sized. The fillet's own band is
  short, sharing its radial room with the taper. The mouth itself is the one
  height that cannot be probed at all: being tangent to the floor rather than an
  edge on it, no finite probe resolves the last sliver, so the topmost probe sits
  a fixed standoff below that floor instead of at a fraction of the band.
- **Shells mate** confirms the front and the back do not occupy the same space.
  Nothing else covers this: every other pass measures a shell against the board, so
  a mating feature cut on the wrong side passes all of them and only shows up when
  the parts will not close.
- **Light path** checks all three legs of each LED's route out: the pad's own
  opening is genuinely cut over the package (probed for air, the inverse of
  the flange it replaced), the shell is genuinely open from the package top
  into the ring channel's void, and the roof over the channel is genuinely
  solid up to the local face floor, the thinnest the face gets there, so the
  light lands on translucent case material rather than escaping through a
  hole that should not exist over an LED.
- **Led ring** probes the channel itself on the built shell, all the way
  around: void at every sampled angle (one blocked sector and the ring shows
  as arcs), a solid web between it and the wheel opening's bore, and a solid
  roof over it everywhere, including on the four diagonals where the rotary
  recess overlaps the ring in plan and the roof is at its thinnest. Both walls rake the whole way,
  so each probe stands at the narrow end of whatever it measures: the void and
  roof probes on the middle of the roof flat, the web probe mid-web at the
  mouth, on a probe narrow enough to fit a web that thin. The pass also holds a
  floor under the roof flat itself, arithmetic, because two walls raking at 45
  over the channel's own height will close on each other if either end moves
  far enough. The same reasoning bounds the wheel seat clearance search inside
  the channel's inner wall at its mouth radius, the smaller of the two, because
  past that wall the material stops being monotonic along the radius and a
  bisect that wanders into the void would read the channel's outer wall as the
  opening.
- **Cell clearance** puts the cell envelope against every modelled solid, every
  screw boss, and both shells.
- **Feature clashes** put the bosses, screw heads, cradle ribs and mic duct
  against every part's courtyard. This is the only pass that sees the eleven
  switches, `D2`-`D5` and `J1`, none of which reach the STEP assembly. Courtyards
  carry no height, so a part's z span comes from its model where it has one and is
  assumed to fill its side of the cavity where it does not. That matters: while it
  was purely 2D it compared the bosses against the wrong side of the board
  entirely, so it never once tested them against the switches they sit among, and
  it reported a cradle rib fouling `C4` when the two are nowhere near in z.
- **End ports open** confirms D1's unchanged +Y bore and the USB shell's -Y
  slot remain real through-cuts at their end-wall centrelines.
- **Receiver paths** confirms U2 has a clear -Z sightline through the bare back
  shell and that its obsolete +Y end-wall path is now closed.
- **Receiver clearance** puts the built back shell and installed insert against
  U2's complete radius-3.0 envelope, so no body or lead is hidden by a
  single-solid read.
- **IR window installation** confirms the conformal outside surface is flush,
  the full 0.05mm press band bears on all four sides, the interior flange
  overlaps on all four sides, the shell shoulder stays continuous as an
  adhesive land, and the installed pane closes the optical centreline. D1's
  bore stays outside this insert and remains unchanged.
- **Parts are sound** confirms every exported part is a valid solid that meshes
  to a closed manifold: each triangle edge shared by exactly two triangles, and
  the meshing attempted inside a try, since a solid can be broken past the point
  of tessellating at all. It is the only pass that reads a mesh rather than the
  BRep behind it, and it exists because the two can disagree in the direction
  that matters. A keypad recess lofted through an unstable spline once came back
  as one solid that BRepCheck called valid, filling a plausible bounding box,
  which every local probe agreed with; the STL cut from it was torn open across
  the front face, and that was the only place the damage showed. Nobody renders
  a BRep.
- **Interference** collides the shells and the window insert with every solid
  in the 3D assembly.
- **Wheel seat clearance** confirms the shell's own wheel opening clears the
  housing and knob (`board.wheel_profile()`'s `main_od` and `top`) by
  `WHEEL_OPENING_CLEARANCE` at every height from the ceiling underside to the
  knob's own peak, and that the lip stays clear of the ceiling in the first
  place. The opening is built to exactly that clearance now, flush to the wheel
  everywhere below the keypad recess's own seat, so this is the pass that
  catches anything eating into it. Probed on the built
  shell by bisecting for the true opening radius rather than trusted from
  `WHEEL_OPENING_R`, because this exact opening was once silently erased by
  a stale full-ceiling clearance cut while the formulas behind it still
  looked right on paper.
- **Wheel rotation clearance** confirms nothing of the pad or the front shell
  intrudes inside the wheel's rotating envelope: the lip's own clearance
  radius at and below its top face, and the main body's clearance above it,
  where the shell's opening closes in flush. The lip being the widest disc,
  which is what lets the pad's plain bore answer for the main body too, is
  checked first as arithmetic rather than assumed.
- **Pad clears wheel** confirms neither pad lobe reaches into the band the
  wheel needs to itself, `pad_clear_y()` either side of its centre. This used
  to be guaranteed by construction: the pad was one slab and that band was
  subtracted from it. Nothing cuts for it now, so it is measured, on the lobe
  rectangles and then on the built pad's own solids, since a lobe is clipped
  and cut for a screw boss after its rectangle is drawn.
- **Recesses open** confirms the front face is genuinely dished, at the depth
  `face_depth_at()` says, beside every key, beside the mic, on the wheel's seat
  on four bearings and at each neck's waist. Beside, not over: directly over a
  key or the mic the face is open from the cavity right through, so a probe
  there reads open whether the recess was cut or not, which is a pass that
  proves nothing. Each site is offset just past its own hole's edge in whichever
  direction the recess is deepest, and clear of every other hole in the face.
  The waists are where the field is shallowest anywhere between the islands, so
  they are where a bridge built the wrong way would show up first. Two readings per
  site, open above the local floor and solid below it, because open alone is
  what a hole reads and solid alone is what an uncut flat face reads. Both are
  fractions of the probe rather than volumes: a probe whose height is the local
  depth is only tenths of a millimetre tall at a shallow site, so a fully
  blocked one measures less than the shared volume tolerance.
- **Recess land** confirms the ceiling left over every counterbore, at the
  deepest point the recess reaches over it, has not gone below what the
  flange stack can spare. Probed on the built shell in the ring between the
  face hole and the counterbore wall, which is the land itself, and then
  checked arithmetically, since that is the only half that can report a
  shortfall before it is deep enough for a probe to see.
- **USB pocket clearance** confirms the local deeper cavity over the USB
  connector's own footprint actually clears its body by `USB_CLEARANCE`,
  probed against `board.usb_envelope()` on the built shell rather than
  trusted from `CAVITY_FRONT_USB` alone, and that the ceiling left above the
  pocket has not gone below its own floor.
- **Recess margins** confirms three things about where the rim lands, all plan
  geometry on the recess definition: every counterbore sits inside the rim, the
  rim clears the case's exterior wall by `KEYPAD_EDGE_MARGIN`, and the basin
  centres still share one x. The first is the one that is not obvious. A
  superellipse touches its own bounding box only at the four edge midpoints, so
  one inscribed in the coverage box would pass inside all four corners of it and
  cut straight through the corner keys' holes; the basins are grown to bound the
  box instead, and this is what proves the growth is still enough after
  `KEYPAD_EDGE_MARGIN` has capped it back. The last is the assumption the whole
  single-column construction rests on.
- **Neck continuity** confirms the recess runs unbroken along its centreline
  from one island's outermost key row to the other's, and that each neck's
  waist is narrower than both the widths it bridges rather than bulging between
  them. Walked on the field rather than probed on the solid, because basins
  that had pinched apart would still build one perfectly valid cut solid that
  simply ran to nothing twice on the way. It also holds the structural bounds
  on a reach and a spread: no join past its own basin's centre, no two joins
  overlapping, and exactly one thing claiming every y along the span, that last
  being what stops a basin widened past its own join from silently taking over a
  stretch of its neighbour's rim.
- **Neck blends smoothly** confirms the field is tangent-continuous across
  every junction and waist, in the floor and in the plan outline both, by
  reading the one-sided slopes either side. That is what "one recess" means
  rather than three cuts that touch: a neck merely meeting a basin at the same
  depth would leave a crease across the floor and a cusp in the outline, which
  is the failure the old neck-joined pocket spent a blend radius on avoiding.
- **Recess edge clearance** confirms the same wall clearance on the built
  solid's own bounding box rather than on the superellipse above, so a cut that
  came out wider than its definition, or one built on the wrong centre, is
  caught here rather than passing on the strength of the arithmetic that
  produced it. The smoothed loft overshoots its stations by a couple of
  thousandths in plan, which is what the shared tolerance absorbs.

## Coordinate frame

X is board X, Y is negated board Y, Z is 0 at the board's bottom face and positive
upward. That is what KiCad's STEP export uses, and `c6remote-pos.csv` already
carries negated Y, so component positions drop in with no transform.

## What is derived, and what is not

Read from `c6remote.kicad_pcb`: the mounting holes, off any footprint whose name
carries `MountingHole` so a change of hole size or fastener still matches with no
edit here, the wheel centre as the mean of the four ANO cutouts, every
footprint's courtyard, and the acoustic port drilled under `MK1`.

Read from `c6remote-pos.csv`: every component placement, so the eleven key
positions and the four LED bearings follow the board.

Read from the assembly STEP: keepout heights, the USB-C shell, `U2`'s complete
body-and-lead envelope and `D1`'s lens. U2 goes through
`board.part_envelope("U2", radius=3.0)` so all nearby solids of its split STEP
model count. Those use measured geometry rather than the placement alone,
because a footprint anchor is not a part centre: `U2`'s sits off its body and
`U1`'s is a module corner nowhere near the connector. For single-solid reads,
`board.part_solid()` takes volume rather than distance to settle that ambiguity;
U2 needs the bounded multi-solid read described under Notes on the awkward bits.
The USB-C shell is found by shape rather than by ref at all, as the solid
overhanging the board's -Y edge, since no placement points at it.

`D1` is read twice over, by `board.emitter_envelope()`: the part nearest its
placement, then clipped to what is past the board's +Y edge before being boxed.
The clip is the point. A bounding box of the whole part is dominated by the leads
bent up through the board and by a rim wider than the lens, none of which reaches
the end wall the bore is cut in, so the box has to be taken of the overhang rather
than of the part.

Also read from the assembly STEP: the wheel's own revolved profile, through
`board.wheel_profile()`. `ENC1` carries no placement row, so it cannot go
through `part_envelope()`; the reader instead finds its solids the same way
`board.keepouts()` does, nearest the wheel centre, and separates the revolved
discs from the part's own pin and legs by which ones come out square in plan.
It answers for the wheel's top, its lip (the widest disc, and what the pad's
bore clears), and the main rotating body above the lip that the shell's own
opening closes in flush on.

Hand-entered: `board.WHEEL_OD`, cross-checked at import time against
`wheel_profile()`'s measured lip rather than trusted blind, and everything in
`params.py`.

## Notes on the awkward bits

**The mic hears through the board.** `MK1` is on the bottom side and bottom-ported,
and the board carries a hole under it for exactly that reason, which is what the
front silk mic mark refers to. So the inlet is on the *front* face, with a duct
from the ceiling down to the board to keep it coupled to that hole rather than to
the whole front cavity. There is no port in the back.

**The inlet is a funnel, not a bore: bell at the floor, throat on the board's
own port.** The sound arrives at the narrow end, up through a drill in the board
several times narrower than the bell, so a bore of one width the whole way is a
tube standing in front of that hole while a cone gathering down onto it is a
horn. The throat sits at `BOARD_TOP` and is almost that drill: the board's own
number plus `MIC_THROAT_MARGIN`, and no more of a margin than two things ask for.
Half of it per side is alignment slop, the case being located on the board by
screws through holes the board itself calls a loose fit, so the throat still
uncovers the whole drill when the two sit a couple of tenths out of concentric.
The rest is the floor under any small bore in a printed part, a hole near one
extrusion width being a hole the perimeter closes over.

**The drill comes off the board, not out of `params.py`.** `case.mic_port_drill()`
reads it through `board.npth_pads`, the same reader that already gives the port
its position, so a board that redrills the port moves the inlet's narrow end with
it. Only the margin is a parameter.

**It is filleted where it opens, not countersunk.** A cone meets the face along
a circular corner; a concave quarter-round tangent to the face has no edge there
at all, which is what a port a finger and a stray draught both arrive at wants,
and it is the same feature a moulded inlet carries. `MIC_MOUTH_D` sets how far
the mouth opens, outright rather than as a multiple of the throat, because the
throat is the board's number now and tying the bell to it would let a different
drill resize the one dimension the inlet exists for.

Neither the fillet's radius nor the cone's angle is set directly.
`MIC_TAPER_SHARE` says how much of the run out from throat to mouth the cone
does, and `case.mic_fillet_r()` is then the mouth less where that leaves off,
which is the one radius leaving the arc tangent to the face above and continuous
with the cone below. So the two cannot be given values that disagree about where
they meet, and the bounds on the share are real: at nothing there is no cone, and
at all of it there is no fillet. The cone stays shallow across that whole range,
the duct being far taller than the bore is wide, so it self-supports whichever
way up the shell is laid on a bed; `case.py` prints the angle.

What bounds the mouth is the duct it is drilled through rather than anything
acoustic. `MIC_DUCT_OD` is the post's outside, set outright rather than as the
bore plus a wall, since a funnel's bore has no one width to reference a wall to.
It answers to three things instead: the courtyards it stands over, the keypad
island it sits inside, and the wall left at the mouth, where the bore comes
closest to it. That last one is the only height at risk, the bore narrowing all
the way down from there, and `case.py` and `check.py` both report it.

The whole funnel is cut as **one** solid, `mic_bore()`, rather than a hole and
separate end features. A tangent arc's base radius *is* the radius of whatever
runs below it, so as two cuts the mouth and the taper would meet along a single
circle with each wall running into the other's at the arc's own tangent, which is
the seam the countersink this replaces dodged by starting below its own base
where the cone was still the narrower of the two. A fillet has no such margin to
start in, so those two are fused across a shared flat disc at the band's base
instead and the boolean is left nothing to resolve.

The taper needs a stub of the throat under it for a related reason. The cut has
to pierce the duct's own bottom face at `BOARD_TOP`, so it needs an overrun past
it, and a cone narrowing downward carried past that face arrives there at exactly
the throat with its end coplanar. So a straight stub carries the throat's full
width a millimetre below the face, the way the plain bore always did, and the
cone's own narrowing overrun hides inside that instead of being the thing that
breaks through.

**And the duct is a solid post, not the tube it was.** A tube is its outer wall
less its own straight bore, and that bore is subtracted before `mic_bore()` ever
runs, so it wins wherever it is the wider of the two. That was harmless while the
bore was one width and the two agreed at the board end. It stopped being harmless
when the throat came down onto the drill: the funnel is narrower than any sensible
tube bore over most of its length now, so a tube would quietly have left the taper
as a straight hole with every number describing it still looking right. So the
duct goes in solid and the funnel is drilled through it, and two of `check.py`'s
taper probes sit low enough to catch it if it ever goes back.

The surface it opens in is the second keypad recess's own curved floor, not
`SHELL_FRONT`. The inlet is inside that recess alongside `SW1` and `SW2`, so the
face around it is already dished, and `case.mic_face()` reads the depth directly
over the board's port so the whole funnel follows it. A function rather than a
constant, and a curved surface rather than a plane, which costs one thing: the
floor rises away from the port across the mouth's own width, by a fraction of a
print layer, so the fillet is tangent to the floor at the port and not quite at
the mouth's shallow edge. Above that height the mouth is carried up at constant
radius rather than the arc continued, since there the arc's own tangent is the
floor, and it has to be carried up rather than stopped because of exactly that
rise; above the floor the dish has already taken everything.

**The USB shell and D1 still pierce their end walls; U2 pierces the back
floor.** `usb_slot()` and `emitter_bore()` remain end-wall through-cuts sized
from `board.usb_envelope()` and `board.emitter_envelope()`. U2's top-view lens
receives along -Z instead, so `ir_window_opening()` cuts only the back shell's
contoured floor from its complete radius-3.0 envelope plus `IR_CLEARANCE`. The
old +Y receiver cut is deliberately closed. Separate built-solid checks prove
both the new sightline and the retained end ports.

`D1`'s bore is sized off the lens where it crosses the board edge, not off
its whole solid: `board.emitter_envelope()` clips the part to what is past
the edge before boxing it. The whole part is twice as tall, carrying its
leads bent up through the board and a rim wider than the lens, and an
opening sized to that box would notch the skirt over its full height for
geometry that never arrives at the wall.

**A split STEP model needs a bounded multi-solid read.** U2's body, lead frame,
and four legs are separate solids, and a nearest-solid lookup can answer with
one leg. Its
aperture therefore uses `board.part_envelope("U2", radius=3.0)`, gathering the
complete package while excluding the next component. The offset guard still
throws out a neighbouring part, so a component with no 3D model raises rather
than quietly answering with whatever is beside it.

**The pad's two lobes are the design, and nothing cuts them apart.** It once
had to stay wider than the wheel bore or the wheel cut it into two, and what was
left either side was a bridge of silicone carrying no load. Once the cut had to
uncover the LEDs too, keeping the pad whole stopped being possible: that cut is
wider than the pad. So the constraint inverted through two steps. First the cut
became a full-width straight band rather than a circle, because an over-wide
circle's arc runs out through the pad's sides in knife-edge slivers that read as
moulding defects. Then the cut went away entirely: a lobe padded off its own
island's keys stops short of the wheel on its own, so there is nothing to
subtract and no semicircular bite left facing the encoder. What was a cut is now
a clearance `check.py` measures.

**The lip never reaches the ceiling, and the shell's wheel opening no
longer pretends it has to.** Assembly is front-plate-down: the board is
lowered into an already-closed front shell, so the wheel approaches the
ceiling from the cavity side and stops there, rather than the shell
dropping down over an already-mounted board and needing to clear the
lip on the way. `board.wheel_profile()`'s lip sits comfortably below
`CAVITY_FRONT` at rest and never transits it, in assembly or service, so
the shell's opening only has to clear what actually reaches the ceiling:
the housing and the knob riding inside it, both narrower than the lip.
That is what lets the opening close in flush to the main body at
`WHEEL_OPENING_CLEARANCE`, narrower than the lip below it. An older `_wheel_hole()`
cut the lip's own, wider radius through the whole ceiling regardless, on a
claim written for a different assembly order that predates this one, and it
quietly erased the then-window's narrower opening everywhere the two
overlapped, which was everywhere, until it was removed. `check.py`'s wheel
seat clearance pass is the real guard in its place, checked on the built
shell against the housing and knob directly rather than trusted from a
formula.

`BOARD_FIT` is padded well past what the board needs. Sized to the board, the
old ring window ran past the side of the case near the X axis and had to be
clipped to a chord, giving it a flat at each side; the padding bought a
complete circle. The window and the pad's bridges are both gone but the
padding stays, and `WHEEL_OPENING_EDGE`'s chord clip with it, as the idle
guard against a wheel or wall move. The profile is offset uniformly, so it
lengthens the case as much as it widens it.

**Two of the keys cannot be full size, and the screw bosses are why.** Each boss
keeps a `BOSS_COLLAR` of ceiling, or a key hole reaching it swallows the boss and
leaves it hanging off nothing, and the pad needs a wider hole again where the boss
passes through it. `SW1` and `SW2` sit 6.50 from the two IR-end mounting holes,
which is closer than a full-size key's own half-width, so they bind.

`key_size()` resolves that per switch rather than globally: the grid pitch caps
every key, and a boss cuts back whichever key reaches it. Nine come out at the full
size and those two at about half. It is derived, so moving a screw or a switch
resizes the keys that care and leaves the rest alone.

The alternative was notching those two around the collar, which is what an earlier
version did through a `boss_collars()` cut. A quarter of the key disappeared into
the bite and it read as damage, so the cut is gone and the sizing is the only
mechanism now. Shrinking the key is also what keeps the pad honest: its clearance
hole is wider than the ceiling collar, so it is usually the binding circle of the
two.

There is no room to keep them full size by moving them instead. The space between
the wheel opening and those bosses is about a full-size key's own width, so
shifting one away from a boss walks it toward the wheel basin's own rim.

**`params.SWITCH_HEIGHT` is the weakest number in the model, and more of it
leans on that now than used to.** Every plunger length follows from it and
nothing in the design files can confirm it: the TL3315 footprint's 3D model
is a stub, and being VRML it is dropped from the STEP assembly entirely. The
value comes from the part number. Since the keypad ceiling dropped to sit
against the switches, `CAVITY_FRONT` follows it directly too, not just the
plunger: a wrong `SWITCH_HEIGHT` moves the whole counterbore stack and how
much ceiling is left under the face, though no longer the face itself,
which reads off the wheel now. Measure a real switch before committing to a pad tool,
and before printing nine caps: the caps inherit the error one for one,
showing as a cap sitting proud of or sunk below the flat face instead of
flush with it, and that reads far more clearly on a rigid cap than it ever
did on a soft keytop. `SWITCH_TRAVEL` is hand-entered from the same
datasheet and in the same epistemic class; it is what floors `CAP_LIFT` and
`CAP_PROTRUSION`, so confirm it too.

**`J1` and `D2`-`D5` have no 3D model at all**, so the interference pass cannot see
them. The courtyard pass covers where they sit. `LED_HEIGHT` is hand-entered for the
same reason, and it sets where the light path check starts probing above each LED.

**The board support ledge is named by its breaks as well as its runs.** The ledge
down each side of the board is a row of runs, broken at every board obstacle.
`support_obstacles()` labels each keepout with a refdes rather than a loop index,
and `model/features.py` exports those breaks beside the runs. Without them a click
on the bare wall between two runs lands in no box, and the viewer can answer with a
coordinate only. One break can be wider than the obstacle that opens it, because
`SUPPORT_MIN_RUN` drops any short fragment left between two obstacles. So the
widest overlap gives the name. A break also carries its own op, `clear`: the same
volume is a relief cut in the front shell and absent material in the back.

**Booleans in this model are written defensively.** Added features overlap the body
they grow from by `MERGE` rather than meeting it at a plane, and unions go through
`_fuse` while cuts go through `_cut`. That is not style: a solid that only touches
another fuses into a compound instead of one solid, and the next boolean then
silently discards most of the shell. Two shells were lost to that before the
helpers went in.

## Files

| File | Role |
| --- | --- |
| `params.py` | Every tunable. Start here. |
| `board.py` | Board geometry from the KiCad exports. Run it for a report. |
| `case.py` | The two shells, the pad, the IR window insert and the keycaps. |
| `check.py` | Thirty-one-pass verification against the board. |
| `fonts/` | Vendored `LEGEND_FONT`, so a legend cuts the same on any machine. |
| `glyphs/` | Legend artwork for the symbols no font carries, filled outlines only. |
| `board/` | Generated by `scripts/export-case-refs.sh`. The board-only STEP and the outline DXF are tracked; the two assembly exports are not. |
| `export/` | Generated STLs. Untracked. |
