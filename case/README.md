# Case

This directory contains the parametric enclosure model for the c6remote board.
The model uses [build123d](https://build123d.readthedocs.io/), so the source is Python.

<p align="center">
  <img alt="Assembled c6remote case" src="../docs/readme-assets/case-assembled.png" width="320">
</p>
<p align="center"><sub>Assembled case</sub></p>

<p align="center">
  <img alt="Exploded c6remote case" src="../docs/readme-assets/case-exploded.png" width="700">
</p>
<p align="center"><sub>Front shell, caps, button pad, board, and back shell</sub></p>

The model exports a front shell, back shell, soft button pad, IR window insert, and 11 rigid caps.
It also exports an FDM button pad with all keytops and legends fused into one STL.
It also exports a second front shell for a filament printer. Read [FDM front](#fdm-front).

## Setup

Run these commands from the repository root:

```bash
cd case
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

## Build and validate

Run these commands from the repository root:

```bash
scripts/export-case-refs.sh
case/.venv/bin/python case/board.py
case/.venv/bin/python case/case.py
case/.venv/bin/python case/check.py
```

Use a scoped check during development:

```bash
case/.venv/bin/python case/check.py --only ir
case/.venv/bin/python case/check.py --only support,shells
```

Run the full check before you accept a case change. A scoped check does not validate the full model.

Run independent feature groups in parallel when two or more groups are selected:

```bash
case/.venv/bin/python case/check.py --jobs 4
case/.venv/bin/python case/check.py --only ir,support --jobs 2
```

Use `--quiet` for failures, provenance, counts, and the scoped-run warning. Use `--timings` to print pass durations.

Every run also writes `export/c6remote-checks.json`: the same report in machine form, with each failure's own point or box in the case frame where the pass recorded one. Use `--json PATH` to write it somewhere else. The c6remote-explode viewer reads that file and draws the failures on the model, so a scoped run writes only the features it ran and marks itself scoped.

A pass says where a failure is by appending a `checks.common.Problem` instead of a plain string; a plain string still reports, it just cannot be drawn.

Use this command to preview the model:

```bash
case/.venv/bin/python case/case.py --show
```

The preview requires `ocp-vscode`:

```bash
uv pip install --python case/.venv/bin/python ocp-vscode
```

Without `ocp-vscode`, use the exploded viewer instead:

```bash
../c6remote-explode/preview-case.sh
```

That script lives in the viewer checkout. It builds the STL files, copies them into the viewer's draft geometry set, and opens the viewer.
It omits the feature map and the summary, so a draft build takes about 6 seconds on a warm cache.

## Board inputs

Do not copy a board coordinate into the case model. Add a reader to `board.py` instead.

The model reads these sources:

- `c6remote-kicad/c6remote.kicad_pcb` supplies the outline, mounting holes, courtyards, wheel center, and microphone port.
- `c6remote-kicad/export/c6remote-pos.csv` supplies component positions.
- `case/board/c6remote-board.step` supplies component bodies, keepout heights, and connector geometry.
- `case/board/c6remote-board-only.step` supplies the board solid.
- `case/board/c6remote-outline.dxf` supplies the exported outline.
- `case/board/c6remote-v2-board-only.step` supplies the fixed V2 mounting-hole reference.

Run `scripts/export-case-refs.sh` after a relevant schematic or board change. Then build and run the full check.

Do not regenerate `case/board/c6remote-v2-board-only.step`. It is a static reference from release `2026.8.0`, commit `d0a2c2e`.

## Coordinate frame

The X axis is the KiCad board X axis. The Y axis is the negative KiCad board Y axis.

The Z origin is the bottom face of the board. Positive Z points toward the front shell.

The position CSV already contains the negative Y coordinates. Do not apply a second Y transformation.

## Parameters

Put all adjustable geometry values in `params.py`. Give each value a short rationale in its docstring.

The model derives geometry from the board where possible. Manual values include switch travel, switch height, print fits, and material thicknesses.

`SWITCH_HEIGHT` and `SWITCH_TRAVEL` are not measurements. Measure a physical TL3315 before the first production print.

## Materials

Print the shells with a tinted translucent filament. The STL files contain no color or material data.

The IR window material must transmit 940 nm infrared light. Test the selected filament with a physical remote.

If the shell filament blocks too much infrared light, make the same insert from IR-pass acrylic.

Prototype the button pad in TPU. Use translucent silicone for a molded part.

Print the caps in translucent PETG. Either orientation works.

Top faces against the build plate gives the best finish. Top faces up needs support on the top faces. Trim the support marks after the print.

For a rigid FDM button set, print `c6remote-case-pad-fdm.stl`. It includes the
two pad lobes and all 11 keytops in one STL. Each keytop is flush with its lobe
web. Do not install separate caps with it.

Print the FDM pad in either orientation. The STL exports with the keytops up.

Keytops down puts the keytop faces on the plate. The pad then stands on 523 mm2.

Keytops up puts the pad on the keytop stems. The pad then stands on 26 mm2. Use a brim and a clean plate. Set the support roof density to 80 percent, or the web sags into the support. Trim the support marks after the print.

## FDM front

The export contains two front shells. Both shells have the same interior, so the caps, the pad, and the back shell fit either one.

`c6remote-case-front.stl` is the recessed front. Its face carries a shallow dish around the keys and around the wheel.

`c6remote-case-front-fdm.stl` is the FDM front. Its face is one flat plane and carries the same dish outline as a shallow groove.

Use `c6remote-case-pad-fdm.stl` with this front. The keytops have no captive
flanges, so install this pad from inside before the board. The face holes guide
the integrated keytops with `FDM_CAP_GUIDE_CLEARANCE` on each side.

Print a front shell with its face against the build plate. A filament printer cannot make the dish in this orientation.

The dish floor is a wide, almost horizontal ceiling a fraction of a millimetre above the plate. The printer must support it.

Support under the face marks the one cosmetic surface on the case. The other orientation stands the whole cavity on its ceiling.

The groove is narrow, so the layer above it bridges the gap in one span. The FDM front needs no support on its face.

The FDM front's face sits `FDM_FACE_DROP` below the recessed front's, so the part is slimmer than a flat face at the raised level.

The caps and the wheel stand proud by that much. The recessed front already stands its caps 0.47 mm to 0.80 mm proud of the dish.

The drop thins three ceilings that the dish never reaches. The USB pocket roof is the tight one, and `check.py --only fdm` holds all three.

The USB pocket roof and the USB slot roof are flush, at the connector envelope plus `USB_CLEARANCE`. Do not raise one without the other.

The groove follows the dish rim exactly. The outline on the two fronts is the same line.

The FDM front has a 0.6 mm, 45 degree top-edge chamfer. The recessed front keeps its round.

The rim runs inside the recessed front's round. The FDM front keeps its groove on flat face outside the chamfer.

`FDM_FACE_DROP`, `FDM_OUTLINE_W`, `FDM_OUTLINE_DEPTH`, `FDM_OUTLINE_EDGE_CLEAR`, and `EDGE_R_FRONT_FDM` set the face. The LED ring channel is half-depth on this front, leaving a thicker printable roof. Run `check.py --only fdm` to validate it.

## Assembly

The front shell holds the board. Three M2 screws fasten the V3 board to its bosses.

The back lap closes over the front skirt. Two detents secure the IR end.
Two hidden side catches keep the long seams closed near the board midpoint.
Their front-skirt pockets are blind, rounded, and bevelled at the mouth, with
continuous material behind them. The seam sits above the board top, leaving a
solid skirt land above each catch.
The back detents ramp on both sides so the shells can be opened for service.

One M2 x 6 screw secures the grip end. It enters horizontally through the back shell's negative Y end wall and threads into a block behind the front skirt. The case uses four M2 x 6 screws in total and no long screw.

Prepare the back shell first:

1. Insert the IR window from inside the back shell.
2. Make the pane flush with the outside surface.
3. Apply adhesive to the continuous shoulder below the interior flange.
4. Let the adhesive set.

Assemble the remaining parts with the front face down:

1. Install all caps in the front shell.
2. Install the button pad.
3. Put the board on the front-shell bosses.
4. Install the three M2 screws through the board into the front-shell bosses.
5. Engage the two IR-end detents.
6. Fold the back shell onto the front shell.
7. Install the end-wall M2 screw at the grip end.

Install the caps before the pad. The caps are captive after pad installation.

For the FDM pad, omit step 1 and install `c6remote-case-pad-fdm.stl` in step 2.

Install the IR window before shell assembly. Its flange is not accessible after shell assembly.

## V2 retention post

The back shell includes one retention post for a V2 board. The post uses the V2 upper-right mounting hole.

This post supplies retention only. It does not make the V2 board compatible with the V3 case.

The V2 IR parts and upper keys do not align with the current openings. Use this feature only as a bench aid.

For a V2 board, fasten the board to the back shell first. Drive the M2 screw from the component side without a washer.

## IR openings

`U2` receives infrared light through the back face along negative Z. Its opening includes the receiver body and lead envelope.

The IR window insert enters this opening from inside. Its exterior pane must be flush with the back shell.

`D1` emits through the positive Y end wall. The emitter uses a separate bare bore.

## Functional constraints

- Keep the button caps captive behind the front-shell ceiling.
- Keep the button pad clear of the wheel and the four wheel LEDs.
- Keep the LED ring channel open below its translucent roof.
- Keep the microphone funnel aligned with the board port.
- Keep the USB slot and pocket clear of the connector shell.
- Keep support ledges clear of board parts, screw heads, and the cell.
- Keep the IR window shoulder continuous for adhesive.
- Keep the front and back shell mating volumes separate.

The checks must probe built geometry. A check must not only repeat the formula that creates the feature.

After a loft or sweep change, inspect the exported STL. A valid BREP can still produce a damaged mesh.

## Validation

`check.py` validates these groups:

- Apertures and end ports
- Button caps, legends, pad fit, and switch contact
- Wheel clearance and the LED light path
- Microphone and USB geometry
- IR receiver clearance and window installation
- Board supports, screws, cell clearance, and V2 retention
- Shell mating and component interference
- FDM front face flatness, height, top edge round, and outline groove
- Solid validity and closed STL meshes

Run the full validation before export:

```bash
case/.venv/bin/python case/check.py
case/.venv/bin/python case/case.py
```

The model writes STLs and metadata to `case/export/`. `case.py` prints current dimensions and screw lengths.

If the exported assets change, push them into the external viewer:

```bash
../c6remote-explode/preview-case.sh --full
```

That script builds again on the warm cache and copies the result into the viewer's draft geometry set.
Its `--baseline` mode rebuilds the committed geometry that the viewer's diff view compares against.

## Development rules

Use the public build123d API. Do not use raw OCP objects unless build123d has no equivalent.

When you add a check, change a related parameter temporarily. Confirm that the new check fails with a useful message.

For a refactor, compare the full check output and exported artifact hashes before and after the change.

The STL cache absorbs one known nondeterministic tessellation result in the back shell. Use `CASE_NO_CACHE=1` only when necessary.

## Files

| Path | Purpose |
| --- | --- |
| `params.py` | All adjustable geometry values |
| `board.py` | Readers for KiCad and board export geometry |
| `case.py` | Thin build and export entry point |
| `check.py` | Thin validation entry point |
| `cache.py` | Geometry and STL cache |
| `model/` | Case feature builders and export metadata |
| `checks/` | Validation modules for built geometry |
| `fonts/` | Vendored legend font and license |
| `glyphs/` | SVG legend artwork |
| `board/` | Generated board references and the fixed V2 reference |
| `export/` | Generated STLs and JSON metadata |
