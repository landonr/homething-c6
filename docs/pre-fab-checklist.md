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
  Result (2026-07-28): 0 violations.

- [x] Full board DRC with schematic parity and zone refill:
  `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations`
  Result (2026-07-28): 0 errors, 43 pre-existing warnings (24 `silk_over_copper`,
  14 `lib_footprint_mismatch`, 4 `silk_edge_clearance`, 1 `silk_overlap`), 0
  unconnected. Parity 13 issues, all `extra_footprint` for board-only `TP_*`
  test points (known, not a defect).

- [x] STEP export succeeds (catches broken 3D model references before they
  show up as a mechanical surprise):
  `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export step c6remote.kicad_pcb --subst-models -o /tmp/c6remote-check.step`
  Result (2026-07-28): export succeeds, 3.0 MB. `Q2` (SOT-23), `R10` (0603) and
  `C4` (0805) all resolve their models, so the LED rail parts added nothing to
  the gap list. The same two missing 3D models as the 07-27 run remain:
  `D2`-`D5` footprint reference `LED_SMD.3dshapes/LED_WS2812B-2020_PLCC4_2.0x2.0mm.step`
  (file does not exist) and `J1` references
  `Connector_JST.3dshapes/JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal.step`
  (also missing). Cosmetic only: STEP substitutes/omits the model, the board
  and pad geometry driving fab are unaffected. Several VRML-only models are
  also skipped for STEP, which is expected since STEP export only takes
  STEP/IGES sources.

- [x] Interactive HTML BOM generated for the manual pin-1 walk below:
  `scripts/gen-ibom.sh`
  Result (2026-07-28): generates `c6remote-kicad/ibom.html` (not committed,
  see below), 282KB, includes `Q2`, `R10` and `C4`. Clones
  `openscopeproject/InteractiveHtmlBom` into `~/.cache/InteractiveHtmlBom` on
  first run and invokes it with KiCad's bundled Python (has `pcbnew`).

`ibom.html` is a generated review artifact, not design source: it is
gitignored (`c6remote-kicad/ibom.html` in `.gitignore`) and must never be
committed. The pre-commit hook reruns `scripts/gen-ibom.sh` whenever
`c6remote.kicad_pcb` is staged, so it tracks the board automatically; that
step is non-fatal, and a `WARNING: gen-ibom.sh failed` line during a commit
means the file is stale and needs a manual rerun before any pin-1 walk. It had
gone a day stale before the hook existed, dated 07-27 against an 07-28 board,
which is exactly the failure mode the hook removes: the walk is only worth
anything against current geometry.

## Manual checks before ordering

- [ ] JLCPCB DFM analysis: upload `export/` gerbers through the JLCPCB order
  flow and review its DFM report. Catches acid traps, soldermask slivers, and
  annular ring issues against their actual process, the authoritative
  capability check.

- [ ] JLCPCB assembly rotation preview: compare against
  `export/c6remote-pos.csv`. JLC does not place parts at the footprint's own
  0 degree orientation, it uses the orientation stored for that LCSC part in
  JLC's component library, and the `Rot` column in the CPL is KiCad-relative,
  so whole package families disagree by 90 or 180 degrees. `SOT-23` is the
  worst offender, and two- and three-pin diodes, some SSOP and LGA parts, and
  JST connectors all drift too. The failure is silent: assembly completes, the
  part sits on the correct pads, rotated.

  Mechanics: after uploading gerbers, BOM and CPL, the order flow renders the
  board with every component at the rotation it will actually be placed and
  pin 1 / polarity marked. Step through each oriented part and confirm pin 1
  points where the datasheet says. Fix a mismatch by editing that ref's `Rot`
  value in the CPL, NOT by rotating the board footprint: the board is correct
  and the CPL is only a translation layer into JLC's library.

  Parts to walk, worst first:

  | Ref | Package | CPL Rot | Why |
  | --- | --- | --- | --- |
  | `Q2` | SOT-23 | 90, top | Pin 1 is the gate. A rotation lands `+3.3V` on it, the P-FET never conducts and `led_vdd` is dead with no complaint from anything. |
  | `Q1` | SOT-23 | 90, top | Same family, same offset risk. Kills IR emit. |
  | `MK1` | ICS-43434 LGA | 0, bottom | Bottom-terminal, pin 1 invisible after assembly, and this part already cost one revision on pin numbering. |
  | `D2`-`D5` | custom 2020 PLCC4 | -45, -135, 135, -135, top | Non-orthogonal, and the footprint is project-local so JLC has no matching library entry to key from. A rotation permutes DIN/DOUT/VDD/GND. |
  | `U3` | SSOP-24 | 0, top | A 180 error puts the supply pins on signal pads. |
  | `J1` | JST PH horizontal | 0, bottom | Bottom side and polarized: a reversed battery. |
  | `U2` | Vishay MOLD-3 | 0, bottom | Swaps Vs, GND and OUT on the IR receiver. |
  | `U1` | XIAO module | 180, top | Only if JLC places it rather than hand-soldering. |
  | `ENC1` | Ano Rotary | THT, not in CPL | Hand-soldered, so it is a paper check against the footprint, not the preview. |

  `PosY` is negative for every row because the CPL uses Y-up with the origin
  at the board's bottom-left corner. That is normal, not a fault. Bottom-side
  rotation uses the mirrored convention, so check `C4`, `J1`, `MK1`, `R3`,
  `R6`-`R8`, `R10` and `U2` for side placement independently of the top-side
  walk.

- [ ] IBOM pin-1 walk: open `c6remote-kicad/ibom.html` and verify pin-1
  orientation of `U1`, `U2`, `U3`, `D2`-`D5`, `Q1`, `Q2`, `ENC1` against their
  datasheets. `Q2` is worth the extra care: it is SOT-23 and pin 1 is the gate,
  so a mis-rotation lands `+3.3V` on the gate, the P-FET never turns on and the
  LED rail stays dead with no DRC or assembly complaint, a silent failure rather
  than an obvious one. This is the check DRC cannot do. Two documented failure
  modes make this non-optional: the `ENC1` pad 6/8 swap found and fixed on this
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

- **2026-07-28**: Status LED rail gated instead of permanently on, killing the
  ~2.4mA the dark `D2`-`D5` chain drew off `+3.3V`: `Q2` AO3401A P-FET high-side
  switch (source `+3.3V`, drain the new `led_vdd` net feeding all four VDD pads),
  `R10` 1M gate pull-up so the rail is off by default while `GPIO18` boots as a
  floating input, `C4` 1µF X7R 0805 bulk cap mid-chain on `led_vdd`, enable net
  `led_en` on `U1` pad 11 (`GPIO18`/`D10`, the last free XIAO edge pad), rail on
  means `GPIO18` driven low. Expected idle in the tens of µA, not yet measured on
  hardware. One real fault caught during layout: the first `led_vdd` routing
  severed the F.Cu GND pour neck and orphaned `D5`'s VSS pad in a 77mm² island,
  which DRC flagged as its only unconnected item. Moving that branch to B.Cu
  fixed it, leaving the pour at 2 islands with all four LED VSS pads in the main
  one. Post-change validation: ERC 0 violations, DRC 0 errors and 0 unconnected
  with 43 warnings (24 `silk_over_copper`, 14 `lib_footprint_mismatch`, 4
  `silk_edge_clearance`, 1 `silk_overlap`), parity 13 `extra_footprint` for the
  `TP_*` test points. Firmware note carried into the LED work: `GPIO17` must be
  held low or high-impedance whenever the rail is down, else DIN pushes current
  into the dead rail.
