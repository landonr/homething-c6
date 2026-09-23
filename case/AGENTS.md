# Case model map

build123d enclosure for the c6remote board. Everything geometric is read from the board (`board.py` readers over `c6remote.kicad_pcb`, `export/c6remote-pos.csv`, and the STEP assembly from `scripts/export-case-refs.sh`); never hand-transcribe a board coordinate, add a reader instead. Tunables live in `params.py` only, one file, each with a rationale docstring; change values there, nowhere else. Keep `README.md` concise. It contains setup, assembly, material, input, validation, and enduring design constraints. Do not use it as a chronological design log.

## Commands

```bash
case/.venv/bin/python case/case.py            # build + export STLs, caps JSON, features JSON
case/.venv/bin/python case/check.py           # full validation, every check
case/.venv/bin/python case/check.py --only ir # one feature (comma list OK)
CASE_NO_CACHE=1 ...                           # bypass the solid cache both ways
```

### Validation delegation

For case or enclosure edits, delegate every validation command to a subagent with the explicit model `gpt-5.6-luna`.

Select `gpt-5.6-luna` explicitly. Do not inherit the primary model.

Delegate case builds, scoped and full checks, hardware quick and verify loops, tests, lint, renders, and documentation checks.

The main orchestrator chooses the scope and sends exact commands and known baselines.

The Luna subagent runs commands and reports routine results.

The main orchestrator synthesizes failures and incomplete checks.

Do not rerun passed checks in the primary agent.

Keep existing user approval rules for commands that require approval.

Both entry points are thin; the code lives in the packages. After a rebuild that changes exports, run `../c6remote-explode/preview-case.sh --full` so the viewer follows. That script builds and copies into the viewer's draft geometry set; its `--baseline` mode rebuilds the committed geometry the diff view compares against.

README case renders live in the explode viewer. From the board repo root:

```bash
../c6remote-explode/scripts/render-case-exploded.sh # path-traced exploded still
../c6remote-explode/scripts/render-case-spin.sh     # path-traced assembled spin
```

Presets sit in `~/dev/c6remote-explode/presets/`. Pose a shot in the viewer, press Copy preset JSON, and overwrite the preset to lock the camera.

## Layout

- `params.py` tunables with rationale. `board.py` board readers (`wheel_profile`, `part_envelope`, `mounting_holes`, `usb_envelope`, `keepouts`). `cache.py` disk cache: BREP blobs plus cached STLs in `case/.cache/`, keyed on a sha256 over every geometry input including the board files; prints a hit or miss line every run.
- `model/stack.py` the z-stack, single source: `BOARD_TOP`, `CAVITY_FRONT`, `SHELL_FRONT`, `COUNTERBORE_TOP`, `CAVITY_BACK`, `SHELL_BACK`, wheel constants read from the board. Everything imports it; nothing imports the entry points.
- `model/shape.py` shared primitives (`_fuse`, `_cut`, `_isect`, `_slab`, `_hole`, `_rounded_prism`). Touching solids must merge; a cut across a compound fails.
- `model/backform.py` back outer surface: `contour_depth`, `end_depth`, tip roll, the loft. Its sections are the plan profile's own chord, so the bottom round lands tangent to the wall around the plan corners and not on the straight sides alone. `model/cell.py` cell bay and cradle (split from hardware to break an import cycle; keep it below both). `model/hardware.py` bosses, the end-wall closure screw and the block it threads into, and the V2 retention post. `model/shells.py` front and back shells, skirt, lap, catches. `front_shell(fdm=True)` is the same shell with the outline groove cut in place of the recess and `front_edge_round(fdm)` sizing a fillet on the recessed front and a 45 degree chamfer on the FDM front, exported as `c6remote-case-front-fdm.stl`: identical under the face, so one cap, pad and back fit either. The recess cannot print face down and face down is the only orientation that keeps support off the cosmetic face. Its face also sits `FDM_FACE_DROP` lower (`front_face`, `stack.py`), so flattening the dish does not keep the material the dish removed, and `checks/fdm.py` holds the three ceilings that drop thins. `model/features.py` keys it under `c6remote-case-front-fdm.stl`, with the front's entries but for the groove in place of the recess. `model/keypad.py` the front face's one merged recess: three superellipse basins on a single centreline joined by two Hermite bridges into one C1 depth field (`keypad_recesses`, `keypad_necks`, `recess_spine`, `face_depth_at`; join roundness is `KEYPAD_JOIN_REACH`, per basin, and `neck_radius` measures what it buys; the wheel basin carries its own lower `WHEEL_SQUIRCLE_N` so its flanks read round) and cut as one loft along y (`recess_stations`, `keypad_recess`); the same field's plan outline as a face (`recess_outline`) and as the shallow slot the FDM front's flat face carries instead of the recess (`keypad_outline_groove`, a true 2D offset either side of that outline; the outline is the rim itself, unclamped, so the line is the same on both fronts. The rim runs inside `EDGE_R_FRONT`, so the FDM front uses a tighter chamfer instead: `EDGE_R_FRONT_FDM` is a 0.64 mm chamfer leg, inside the bound `KEYPAD_EDGE_MARGIN` less half a groove width less `FDM_OUTLINE_EDGE_CLEAR`. `FDM_OUTLINE_EDGE_CLEAR` is load-bearing: at zero the groove's outer edge goes coincident with the chamfer's inner edge, and the exported STL comes back torn along the face while every other reading stays green); plus the pad's two lobes and stems. `model/caps.py` keycap chain (`cap_body` through `cap_counterbore`), all four widths the same superellipse via `_key_prism`, on the caps' own `KEY_SQUIRCLE_N` rather than the recesses' `KEYPAD_SQUIRCLE_N` so their flanks bow out further, plus `cap_flat` for what a legend can occupy (it tracks that exponent, so lowering it tightens the legend ink pass). `model/legends.py` deboss text and SVG glyphs (fonts in `case/fonts/`, glyphs in `case/glyphs/`). `model/wheel_ring.py` the clearance band the pad's lobes stay out of around the wheel (uncovering the LEDs; the moulded ring is gone, and so is the cut that used to sever the pad), the shell's flush wheel opening (the face sits at the wheel's own measured top), and the LED ring channel, an annular void in the ceiling that carries the four LEDs' light around the wheel under a translucent roof. `model/ir.py` U2's rounded -Z back-floor aperture and conformal stepped inside-fit insert, plus D1's unchanged +Y emitter bore. `model/mic.py` funnel inlet, tapering cone up from the board port into a tangent fillet at the mouth. `model/usb.py` slot and pocket. Both take their roof from `usb_roof()`, the connector envelope plus `USB_CLEARANCE`, so the two voids are flush: the pocket used to stand `MERGE` higher, which cost 0.3 of ceiling and left a ledge in the middle of one opening. `USB_POCKET_LIP_CHAMFER` is the wall's full height and `_chamfer_usb_pocket_lip()` fails if it goes past it, which is what caught that change. `model/features.py` the names behind the meshes: one table from each exported STL to the builders that add to or cut that part, each with its source, the parameters that source reads, whether it is material or void, and its bounding box in the case frame. It names the support keepouts as well as the runs: each break between two runs is exported as a `clear` box called after the obstacle that opens it, so a click on the bare wall in a break still resolves to an id. `model/cli.py` `main()`: export set and summary. The `export/c6remote-caps.json` and `export/c6remote-features.json` exports feed the viewer; never remove them.
- `model/support.py` makes the board support runs from the board profile, bottom courtyards, screw heads, and support parameters. `support_obstacles()` names each keepout after the board: a courtyard refdes, a mounting hole refdes, or a through-board solid index. Both the support checks and the feature export read those names.
- `checks/support.py` probes clearance, bearing, minimum run length, print angle, and back-shell fusion on the built geometry.
- `checks/legacy.py` probes the one back-shell post a V2 board can fasten to: its clearance to every V3 solid, its fusion into the shell, and its blind pilot. `board.legacy_mounting_holes()` reads V2's holes out of `board/c6remote-v2-board-only.step`, static geometry frozen at release `2026.8.0`, commit `d0a2c2e`. Do not regenerate that file. Retention only. Read `README.md` on what V2 compatibility does not mean.
- `checks/fdm.py` probes the FDM front: the face is material at every site `checks/keypad.py` reads the recess as dished at, the groove is cut to depth all the way round with real material left under it, and the flat the built shell has out to its own top edge chamfer is `EDGE_R_FRONT_FDM`'s with `FDM_OUTLINE_EDGE_CLEAR` of it outboard of the groove. It imports `checks/keypad.py`'s own probe sites so the two passes read the same places with opposite verdicts.
- `checks/` mirrors the features, one module each, `checks/cli.py` owns the registry, solid demand-loading, and `--only`. Cross-feature checks (`interference`, `feature_clashes`) live in the `assembly` feature; a scoped run prints which features it skipped and exits nonzero on failure.

## Board support ledges

Keep the support ledges in the back shell. Use the same full-length runs to cut matching relief from the front shell.

Keep a 0.25 mm gap below the board and a 3 mm bearing surface. Keep one straight 45 degree underside for FDM printing.

Derive all breaks from board obstacles. Remove fragments below `SUPPORT_MIN_RUN`. Do not add local end trims or separate wedges.

After a support change, run this workflow from the repository root:

```bash
case/.venv/bin/python case/check.py --only support,shells
case/.venv/bin/python case/check.py
../c6remote-explode/preview-case.sh --full
```

Inspect both shell STLs and the exploded view. Confirm that the front shell has no unwanted lower side geometry.

## Disciplines

- A check must probe the BUILT solid, not restate the formula that built it. This model shipped several vacuous passes before that rule; assume any new check is vacuous until proven otherwise.
- The solid is not the artifact either: STLs are, and a valid solid can still mesh to a torn surface. `parts_are_sound` in `checks/shells.py` is the only pass that reads a mesh, and it exists because a keypad recess once lofted to something BRepCheck called valid whose STL was ripped open across the whole front face, with every other pass green. After any change to a lofted or swept surface, look at the exported STL, not just the check output.
- Geometry stays on build123d's public API. No `import OCP`, no `.wrapped`: build123d already covers booleans, `.volume`, STEP/BREP IO, and STL tessellation (`export_stl`). If an operation is genuinely mesh-native (mesh boolean, point sampling, repair), `trimesh` is installed in the venv; declare it in `requirements.txt` on first real use. Raw OCP through `.wrapped` is the last resort, confined to one small helper with a comment saying what build123d lacks.
- Perturb-test every new check: break the param, watch it fail with a sensible message, restore.
- Refactors gate on byte-identical exports (md5 over `case/export/`) and identical check output. STL export is deterministic enough to gate on, except one known flake in the back shell tessellation that the STL cache absorbs.
- A green scoped run is not a green full run; the skip line exists so nobody mistakes one.
- `SWITCH_HEIGHT` and `SWITCH_TRAVEL` are hand-entered, unmeasured; measure a real TL3315 before printing.
