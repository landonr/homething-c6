# Case model map

build123d enclosure for the c6remote board. Everything geometric is read from the board (`board.py` readers over `c6remote.kicad_pcb`, `export/c6remote-pos.csv`, and the STEP assembly from `scripts/export-case-refs.sh`); never hand-transcribe a board coordinate, add a reader instead. Tunables live in `params.py` only, one file, each with a rationale docstring; change values there, nowhere else. `README.md` is the design log: constraints and param names, no numbers.

## Commands

```bash
case/.venv/bin/python case/case.py            # build + export STLs and caps JSON
case/.venv/bin/python case/check.py           # full validation, every check
case/.venv/bin/python case/check.py --only ir # one feature (comma list OK)
CASE_NO_CACHE=1 ...                           # bypass the solid cache both ways
```

Both entry points are thin; the code lives in the packages. After a rebuild that changes exports, run `~/dev/c6remote-explode/refresh-assets.sh` so the viewer follows.

## Layout

- `params.py` tunables with rationale. `board.py` board readers (`wheel_profile`, `part_envelope`, `mounting_holes`, `usb_envelope`, `keepouts`). `cache.py` disk cache: BREP blobs plus cached STLs in `case/.cache/`, keyed on a sha256 over every geometry input including the board files; prints a hit or miss line every run.
- `model/stack.py` the z-stack, single source: `BOARD_TOP`, `CAVITY_FRONT`, `SHELL_FRONT`, `COUNTERBORE_TOP`, `CAVITY_BACK`, `SHELL_BACK`, wheel constants read from the board. Everything imports it; nothing imports the entry points.
- `model/shape.py` shared primitives (`_fuse`, `_cut`, `_isect`, `_slab`, `_hole`, `_rounded_prism`). Touching solids must merge; a cut across a compound fails.
- `model/backform.py` back outer surface: `contour_depth`, `end_depth`, tip roll, the loft. `model/cell.py` cell bay and cradle (split from hardware to break an import cycle; keep it below both). `model/hardware.py` bosses, closure. `model/shells.py` front and back shells, skirt, rails, catches. `model/keypad.py` the front face's one merged recess: three superellipse basins on a single centreline joined by two Hermite bridges into one C1 depth field (`keypad_recesses`, `keypad_necks`, `recess_spine`, `face_depth_at`; join roundness is `KEYPAD_JOIN_REACH`, per basin, and `neck_radius` measures what it buys; the wheel basin carries its own lower `WHEEL_SQUIRCLE_N` so its flanks read round) and cut as one loft along y (`recess_stations`, `keypad_recess`); plus the pad's two lobes and stems. `model/caps.py` keycap chain (`cap_body` through `cap_counterbore`), all four widths the same superellipse via `_key_prism`, on the caps' own `KEY_SQUIRCLE_N` rather than the recesses' `KEYPAD_SQUIRCLE_N` so their flanks bow out further, plus `cap_flat` for what a legend can occupy (it tracks that exponent, so lowering it tightens the legend ink pass). `model/legends.py` deboss text and SVG glyphs (fonts in `case/fonts/`, glyphs in `case/glyphs/`). `model/wheel_ring.py` the clearance band the pad's lobes stay out of around the wheel (uncovering the LEDs; the moulded ring is gone, and so is the cut that used to sever the pad), the shell's flush wheel opening (the face sits at the wheel's own measured top), and the LED ring channel, an annular void in the ceiling that carries the four LEDs' light around the wheel under a translucent roof. `model/ir.py` U2's rounded -Z back-floor aperture and conformal stepped inside-fit insert, plus D1's unchanged +Y emitter bore. `model/mic.py` funnel inlet, tapering cone up from the board port into a tangent fillet at the mouth. `model/usb.py` slot and pocket. `model/cli.py` `main()`: export set and summary. The `export/c6remote-caps.json` export feeds the viewer; never remove it.
- `checks/` mirrors the features, one module each, `checks/cli.py` owns the registry, solid demand-loading, and `--only`. Cross-feature checks (`interference`, `feature_clashes`) live in the `assembly` feature; a scoped run prints which features it skipped and exits nonzero on failure.

## Disciplines

- A check must probe the BUILT solid, not restate the formula that built it. This model shipped several vacuous passes before that rule; assume any new check is vacuous until proven otherwise.
- The solid is not the artifact either: STLs are, and a valid solid can still mesh to a torn surface. `parts_are_sound` in `checks/shells.py` is the only pass that reads a mesh, and it exists because a keypad recess once lofted to something BRepCheck called valid whose STL was ripped open across the whole front face, with every other pass green. After any change to a lofted or swept surface, look at the exported STL, not just the check output.
- Geometry stays on build123d's public API. No `import OCP`, no `.wrapped`: build123d already covers booleans, `.volume`, STEP/BREP IO, and STL tessellation (`export_stl`). If an operation is genuinely mesh-native (mesh boolean, point sampling, repair), `trimesh` is installed in the venv; declare it in `requirements.txt` on first real use. Raw OCP through `.wrapped` is the last resort, confined to one small helper with a comment saying what build123d lacks.
- Perturb-test every new check: break the param, watch it fail with a sensible message, restore.
- Refactors gate on byte-identical exports (md5 over `case/export/`) and identical check output. STL export is deterministic enough to gate on, except one known flake in the back shell tessellation that the STL cache absorbs.
- A green scoped run is not a green full run; the skip line exists so nobody mistakes one.
- `SWITCH_HEIGHT` and `SWITCH_TRAVEL` are hand-entered, unmeasured; measure a real TL3315 before printing.
