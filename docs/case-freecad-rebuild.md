# Plan: rebuild front_shell as a native FreeCAD parametric part

## Context

The case model (`case/`, build123d) exports STL only. Goal: the enclosure editable in a GUI CAD app with a real feature timeline, where minor edits happen by mouse and larger edits go through AI. FreeCAD chosen over Fusion 360 and Onshape: a working MCP server lets Claude drive the live GUI session (same loop as KiCad MCP), the PartDesign tree is a real editable timeline, it shares the OCCT kernel with build123d so geometry converts faithfully, and the generator can run headless for regeneration. Scope: **front_shell only** to start, full native rebuild (real sketches, pads, pockets, revolutions, lofts, fillets), not imported BREP booleans.

The build stays scripted so the FreeCAD file regenerates from the board and never drifts from `board.py`/`params.py` (repo rule: never hand-transcribe board coordinates). The `.FCStd` file is a generated artifact; the manifest exporter is the source of truth.

**Requires FreeCAD 1.0 or newer.** 1.0 shipped the topological naming fix; without it, editing an upstream sketch scrambles downstream edge references (fillets, datum attachments) and the tree breaks on the first GUI edit, defeating the point.

Known fidelity caveat, accepted: the keypad recess is a smooth loft through roughly 90 stations of 65-point polylines (`case/model/keypad.py:432 dish_cut()`). FreeCAD rebuilds it as a Subtractive Loft through B-spline sections, so its floor is smoother than the polyline original by a few hundredths of a mm. Everything else maps exactly.

## Architecture: two stages

**Stage A, manifest exporter (runs in `case/.venv`, build123d available)**

- `case/model/freecad_manifest.py`: the exporter. Imports `board`, `params`, `model.stack`, `model.shape`, `model.keypad`, `model.mic`. Walks the same geometry the model is built from and emits an ordered JSON build manifest.
- `case/export_freecad_manifest.py`: thin CLI wrapper. Writes `case/export/freecad/front_shell.manifest.json`.
- Nothing hand-transcribed: profiles come from `shape._offset_face()` wires (walk each build123d Edge through its public API, `geom_type`, `arc_center`, `radius`, `position_at`; Line/Circle become exact line and arc segments, anything else becomes sampled spline points). Positions from `board.components()`, `board.refs("SW")`, `mount_points()`, `board.wheel_center()`. Z planes from `model/stack.py`. The existing outline DXF is not used; emitting the already-offset wires is strictly better.

**Stage B, FreeCAD generator (runs in FreeCAD's Python)**

- `case/freecad/build_front_shell.py`: reads the manifest, builds a PartDesign Body feature by feature, saves `front_shell.FCStd`, exports `front_shell_freecad.step`. Runs three ways: headless via the app bundle's `FreeCADCmd`, pasted into the GUI Python console, or driven live through the FreeCAD MCP server.
- `case/freecad/README.md`: run instructions for all three, plus MCP server setup.
- Case coordinate frame maps 1:1 to the document's global frame, units are mm on both sides, no conversion.

## Manifest schema (sketch)

```json
{ "version": 1, "units": "mm", "part": "front_shell",
  "params": {"SHELL_FRONT": ..., "CAVITY_FRONT": ..., "BOARD_TOP": ..., ...},
  "features": [
    {"name": "body", "type": "pad", "op": "join",
     "plane": {"z": {"value": ..., "expr": "SKIRT_BOTTOM"}},
     "profiles": [[{"line": [[x,y],[x,y]]}, {"arc": {...}}, {"spline": [[x,y],...]}]],
     "distance": {"value": ..., "expr": "SHELL_FRONT - SKIRT_BOTTOM"}},
    {"name": "top_fillet", "type": "fillet", "radius": {"expr": "EDGE_R_FRONT"},
     "edges": {"select": "top_face_perimeter", "z": "SHELL_FRONT"}},
    {"name": "mic_bore", "type": "revolution", "op": "cut", "axis": {...}, "profile": [...]},
    {"name": "keypad_recess", "type": "loft", "op": "cut",
     "sections": [{"plane": {"y": ...}, "floor_spline": [[x,z],...], "top_z": ...}, ...]},
    {"name": "led_ring_channel", "type": "tool_body", "op": "cut", "steps": [...]}
  ]}
```

Convenience primitives Stage B expands into sketch geometry: `circle`, `rect`, `rounded_rect`, `polyline`, `spline`. Every scalar carries `value` plus optional `expr` (spreadsheet expression, see parameters below).

## Feature mapping (ordered, mirrors `case/model/shells.py:271 front_shell()`)

| # | Source | FreeCAD feature |
|---|---|---|
| 1 | body slab, `shells.py:278`, profile from `shape.py` | Sketch on datum plane at SKIRT_BOTTOM, Pad to SHELL_FRONT |
| 2 | top perimeter fillet, `shells.py:279` | Fillet on the perimeter edge loop of the single upward planar face at z = SHELL_FRONT |
| 3 | inner cavity, `shells.py:283` | Pocket, BOARD_TOP - 0.01 to CAVITY_FRONT |
| 4 | `skirt_cuts()`, `shells.py:71` | 2 Pockets; annular profile is one sketch with two nested loops |
| 5 | `mic_duct()`, `mic.py:152` | Pad (circle), BOARD_TOP to SHELL_FRONT |
| 6 | `deep_skirt()`, `shells.py:160` (ring intersect box) | Stage A clips the annulus by the box in 2D at export time, single Pad; fallback tool_body (separate Body plus PartDesign Boolean) if the clip is not reducible |
| 7 | 2 `rails()`, `shells.py:94` (ruled 3-section loft) | Additive Loft for the lead-in plus Pad for the straight run (sections 2 and 3 identical) |
| 8 | 3 bosses, `shells.py:297` | one sketch, 3 circles, Pad BOARD_TOP to SHELL_FRONT |
| 9 | `usb_pocket()`, `usb.py:49` | Pocket (rect) |
| 10 | 3 pilots, `shells.py:332` | one sketch, Pocket (plain pocket, not Hole feature: multi-position, blind both ends) |
| 11 | 2 `catch_windows()`, `shells.py:168` | Sketch on Y-normal datum plane, Pocket |
| 12 | `wheel_opening()`, `wheel_ring.py:205` | Pocket circle CAVITY_FRONT - 1 to SHELL_FRONT + 1; exporter asserts the opening clip is idle at the current radius, tool_body fallback if not |
| 13 | `led_ring_channel()`, `wheel_ring.py:161` (revolve intersect live clip) | tool_body: separate Body holding a Revolution (trapezoid about the wheel axis) intersected with a padded clip region, then PartDesign Boolean cut into the main Body |
| 14 | `mic_bore()`, profile `mic.py:124` | one Groove (subtractive revolution) of the exact half-profile: throat line, taper, tangent arc at `mic_fillet_r()`, mouth line. Replaces the fuse-of-3-solids boolean, exact |
| 15 | 22 key prisms, `shells.py:323` (11 switches, counterbore plus face hole each) | 2 sketches of 11 rounded rects each, 2 Pockets (to COUNTERBORE_TOP, to SHELL_FRONT + 1) |
| 16 | `keypad_recess()`, `keypad.py:432,615` | Subtractive Loft through per-station sketches on Y-offset datum planes: B-spline floor plus verticals plus top line. `--stations N` decimation flag on the exporter (default all stations, practical around half); identical point count per section so loft correspondences behave |
| 17 | `shared_cuts()`, `shells.py:231`: `usb_slot`, `ir_window_opening`, `emitter_bore` | 3 Pockets from Y-normal datum planes |

MERGE overshoots kept verbatim (harmless in pads and pockets, keeps the manifest a faithful transcription).

## Key decisions

- **Fillet edge selection.** Replay order guarantees that at feature 2 exactly one upward planar face exists at z near SHELL_FRONT. The generator selects it geometrically (normal dot Z above 0.99, z within 1e-3), fillets all its edges (the single perimeter loop; no aperture edges exist yet, mirroring the by-construction argument in `shells.py:272-276`). Assert exactly one such face, abort loudly otherwise. Post-generation edits rely on FreeCAD 1.0 toponaming to keep the reference stable.
- **Parameters.** A `params` Spreadsheet object in the document holds the Z stack and thicknesses (SHELL_FRONT, CAVITY_FRONT, BOARD_TOP, SKIRT_BOTTOM, COUNTERBORE_TOP, SKIRT_H, WALL, BOARD_FIT, EDGE_R_FRONT, MIC_DUCT_OD, BOSS_OD, BOSS_PILOT_D). Pad and pocket lengths, datum plane offsets, and the fillet radius bind to spreadsheet expressions from the manifest's `expr` strings. All XY geometry (outline, switch positions, dish sections, key sizes) is baked numeric: it derives from the board and is not usefully editable in CAD.
- **Intersections.** Prefer 2D clipping at export time (deep_skirt). Use a separate Body plus PartDesign Boolean only where the clip is genuinely 3D (led_ring_channel).
- **Sketch capacity.** The dish sections and the board outline are large sketches (dozens of spline poles). Sketches are created unconstrained (geometry only, no constraint solving), which keeps document rebuild fast and avoids solver blowups. Constraints are not needed: the geometry is exact from the manifest, and GUI edits of these sketches are not the expected workflow.

## Verification

`case/freecad/verify_front_shell.py` (runs in the repo venv):

1. Stage B exports `front_shell_freecad.step`.
2. The verifier imports it with build123d and loads the reference front_shell BREP from `case/.cache` (rebuilding via `model.shells.front_shell()` on a cache miss).
3. Checks: bounding box extents within 0.05 mm each; volume within 0.3 percent; boolean symmetric-difference volume under 150 mm3 total AND under 10 mm3 outside a box around the keypad recess span (the dish alone absorbs the spline-vs-polyline tolerance).
4. Nonzero exit on failure, per-check numbers printed.

Regeneration loop after any board change: `scripts/export-case-refs.sh`, then `case/export_freecad_manifest.py`, then rerun the generator, then the verifier.

## Files to create

- `case/model/freecad_manifest.py` (exporter)
- `case/export_freecad_manifest.py` (CLI)
- `case/freecad/build_front_shell.py` (generator, runs in FreeCAD Python)
- `case/freecad/verify_front_shell.py` (verifier)
- `case/freecad/README.md` (run instructions: FreeCADCmd headless, GUI console, MCP)

## Implementation order

1. Stage A: wire-to-segments walker, then feature emitters in table order; manifest written and eyeball-checked.
2. Stage B: primitive expanders, datum plane and sketch helpers, feature replayers (pad, pocket, revolution, groove, loft, fillet, tool_body), spreadsheet creation, STEP export. Test headless first via FreeCADCmd.
3. Iterate: generate, verify, fix per-feature until thresholds pass.
4. MCP server setup and README last.

## Follow-ups out of scope

- back_shell, button_pad, ir_window, keycaps (same pipeline once front_shell proves it; back_shell's lofted form is the next hard case).
- An Assembly document placing all parts (FreeCAD 1.0 built-in Assembly workbench) once more than one part exists.
