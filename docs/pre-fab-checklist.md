# Pre-fab checklist

Run this before every board order, in addition to routine ERC/DRC. It covers
checks that catch fabrication and assembly problems ERC/DRC cannot see: real
manufacturer capability limits, 3D/mechanical fit, and pin-1 orientation.

For current board status and open findings, see `ROADMAP.md`.

Commands assume `cd c6remote-kicad` first, matching the conventions in
`AGENTS.md`.

## Automated checks

- [x] Schematic ERC clean:
  `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc c6remote.kicad_sch --exit-code-violations`
  Result (2026-07-27): 0 violations.

- [x] Full board DRC with schematic parity and zone refill:
  `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations`
  Result (2026-07-27): 0 errors, 46 pre-existing warnings (24 `silk_over_copper`,
  14 `lib_footprint_mismatch`, 7 `silk_edge_clearance`, 1 `silk_overlap`), 0
  unconnected. Parity 13 issues, all `extra_footprint` for board-only `TP_*`
  test points (known, not a defect).

- [x] STEP export succeeds (catches broken 3D model references before they
  show up as a mechanical surprise):
  `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export step c6remote.kicad_pcb --subst-models -o /tmp/c6remote-check.step`
  Result (2026-07-27): export succeeds, 3.0 MB. Two missing 3D models noted:
  `D2`-`D5` footprint reference `LED_SMD.3dshapes/LED_WS2812B-2020_PLCC4_2.0x2.0mm.step`
  (file does not exist) and `J1` references
  `Connector_JST.3dshapes/JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal.step`
  (also missing). Cosmetic only: STEP substitutes/omits the model, the board
  and pad geometry driving fab are unaffected. Several VRML-only models are
  also skipped for STEP, which is expected since STEP export only takes
  STEP/IGES sources.

- [x] Interactive HTML BOM generated for the manual pin-1 walk below:
  `scripts/gen-ibom.sh`
  Result (2026-07-27): generates `c6remote-kicad/ibom.html` (not committed,
  see below). Clones `openscopeproject/InteractiveHtmlBom` into
  `~/.cache/InteractiveHtmlBom` on first run and invokes it with KiCad's
  bundled Python (has `pcbnew`).

`ibom.html` is a generated review artifact, not design source: it is
gitignored (`c6remote-kicad/ibom.html` in `.gitignore`) and must never be
committed. Regenerate it with `scripts/gen-ibom.sh` whenever you need a fresh
pin-1 walk.

## Manual checks before ordering

- [ ] JLCPCB DFM analysis: upload `export/` gerbers through the JLCPCB order
  flow and review its DFM report. Catches acid traps, soldermask slivers, and
  annular ring issues against their actual process, the authoritative
  capability check.

- [ ] JLCPCB assembly rotation preview: compare against
  `export/c6remote-pos.csv`. KiCad's rotation convention differs from JLC's
  for many footprint families, so eyeball every polarized/oriented part in
  the preview: `D2`-`D5`, `U1`, `U2`, `U3`, `Q1`, `ENC1`, `J1`.

- [ ] IBOM pin-1 walk: open `c6remote-kicad/ibom.html` and verify pin-1
  orientation of `U1`, `U2`, `U3`, `D2`-`D5`, `Q1`, `ENC1` against their
  datasheets. This is the check DRC cannot do. Two documented failure modes
  make this non-optional: the `ENC1` pad 6/8 swap found and fixed on this
  board (a real pinout error that shipped once), and the `XL-2020RGBC-WS2812B`
  datasheet pin-table-vs-diagram contradiction recorded in `AGENTS.md` (one
  hosted revision's table disagrees with its own diagram). Datasheets and
  stock symbol/footprint pairings both lie about pinout often enough that a
  visual walk against the primary datasheet diagram is required, not
  optional.

- [ ] Independent gerber review: open `export/` in GerbView. Check layer
  completeness, silkscreen readability, and drill alignment.

- [ ] Zone refill in the KiCad GUI, then save, before committing any board
  change (repo rule, see `AGENTS.md`): `kicad-cli --refill-zones` only fills
  in memory and never writes the refill back to `c6remote.kicad_pcb`.

- [ ] 1:1 paper print of the board outline: mechanical/ergonomic check of
  switch and wheel spacing against a real hand.

## Findings log

- **2026-07-27**: One-shot check against JLCPCB 2-layer capability limits
  (trace/space 0.127mm, via 0.3/0.45mm, hole-to-hole 0.5mm different nets,
  PTH annular 0.25mm, copper-to-edge 0.3mm, per-type hole-to-copper
  clearances) as a temporary `.kicad_dru`: zero new violations, board passes
  JLC limits with margin (project constraints are stricter for track width
  and clearance). Rules file removed after the pass; the JLC DFM upload above
  is the live capability check going forward. STEP export succeeds but is
  missing 3D models for `D2`-`D5` (`LED_WS2812B-2020_PLCC4_2.0x2.0mm.step`)
  and `J1` (`JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal.step`); both are
  cosmetic gaps in the local 3D model cache, not fab-blocking. Generated
  first IBOM review artifact via `scripts/gen-ibom.sh`. Q1/R1 moved and
  `IR EMIT` rerouted after review; DRC re-run clean at the same baseline.
