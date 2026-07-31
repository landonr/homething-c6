# Pre-fab checklist

Run before every board order, on top of routine ERC/DRC. Covers what ERC/DRC cannot see: real manufacturer capability limits, mechanical fit, pin-1 orientation.

Board status and open findings: `ROADMAP.md`. Commands assume `cd c6remote-kicad` and `KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`.

## Automated

- [x] **ERC** `$KC sch erc c6remote.kicad_sch --exit-code-violations`
  2026-07-31: 0 violations.

- [x] **DRC, parity, refill** `$KC pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations`
  2026-07-31: 0 errors, 0 unconnected, 2 warnings (`lib_footprint_mismatch` on `U1`, 1 `silk_overlap`). Parity 13, all `extra_footprint` for board-only `TP_*`. Known, not defects.

- [x] **STEP export** catches broken 3D model refs before they become mechanical surprises.
  `$KC pcb export step c6remote.kicad_pcb --subst-models -o /tmp/c6remote-check.step`
  2026-07-28: succeeds, 3.0MB. Two models still missing, both cosmetic since STEP substitutes or omits and fab geometry is unaffected: `D2`-`D5` want `LED_SMD.3dshapes/LED_WS2812B-2020_PLCC4_2.0x2.0mm.step`, `J1` wants `Connector_JST.3dshapes/JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal.step`. VRML-only models skip too, expected.

- [x] **IBOM** `scripts/gen-ibom.sh`, feeds the pin-1 walk below.
  2026-07-28: `c6remote-kicad/ibom.html`, 282KB. First run clones `openscopeproject/InteractiveHtmlBom` into `~/.cache/InteractiveHtmlBom`, runs under KiCad's bundled Python (needs `pcbnew`).

`ibom.html` is a review artifact, gitignored, never commit it. Pre-commit hook regenerates it whenever `c6remote.kicad_pcb` is staged, so it tracks the board. That step is non-fatal: a `WARNING: gen-ibom.sh failed` line means the file is stale, rerun by hand before any pin-1 walk. A walk against stale geometry is worth nothing.

## Manual, before ordering

- [ ] **JLCPCB DFM.** Upload `export/` gerbers through the order flow, read the DFM report. Authoritative capability check: acid traps, mask slivers, annular rings against their real process.

- [ ] **IBOM pin-1 walk.** Open `ibom.html`, verify pin 1 on `U1`, `U2`, `U3`, `D2`-`D5`, `Q1`, `Q2`, `ENC1` against the primary datasheet diagram. DRC cannot do this. `Q2` first: SOT-23, pin 1 is the gate, so a mis-rotation puts `+3.3V` on the gate, the P-FET never turns on, the LED rail stays dead, and nothing complains. Two documented reasons it is not optional: the `ENC1` pad 6/8 swap that shipped once, and the `XL-2020RGBC-WS2812B` datasheet whose pin table contradicts its own diagram (see `AGENTS.md`).

- [ ] **Gerber review.** Open `export/` in GerbView. Layer completeness, silk readability, drill alignment.

- [ ] **Zone refill in the GUI, then save**, before committing any board change (repo rule). `--refill-zones` fills in memory only, never writes back to `c6remote.kicad_pcb`.

- [x] **1:1 mechanical fit** against a real hand. Done as a 3D print, which also checks hole positions and thickness.
  `$KC pcb export stl --board-only -f -o /tmp/c6remote-board.stl c6remote.kicad_pcb`
  2026-07-30: printed, test fitted, switch and wheel spacing good. `export stl` emits no silk, so F.SilkS was raised 0.4mm on the printed copy by a local script (strokes the layer through `pcbnew`, extrudes it). Neither script nor STL is committed, so a rerun regenerates both. Front only, back relief would sit on the build plate. Clip silk to the board outline first: it overhangs the bottom edge 1.5mm, fine in gerbers, prints as detached floating geometry.

## Findings log

- **2026-07-27:** Checked board against JLCPCB 2-layer limits as a temporary `.kicad_dru` (trace/space 0.127mm, via 0.3/0.45mm, hole-to-hole 0.5mm different nets, PTH annular 0.25mm, copper-to-edge 0.3mm, per-type hole-to-copper): zero new violations, passes with margin since project constraints are stricter. Rules file removed after; the DFM upload is the live capability check now. First IBOM generated. Q1/R1 moved and `IR EMIT` rerouted after review, DRC clean at the same baseline.

- **2026-07-28:** LED rail gated instead of permanently on, killing the ~2.0mA the dark `D2`-`D5` chain drew: `Q2` AO3401A high-side P-FET (source `+3.3V`, drain `led_vdd` feeding all four VDD), `R10` 1M gate pull-up so the rail is off while `GPIO18` boots floating, `C4` 1µF X7R 0805 mid-chain, enable `led_en` on `U1` pad 11 (`GPIO18`/`D10`, last free edge pad), on means `GPIO18` low. Idle expected in tens of µA, not yet measured on hardware. One real fault caught in layout: the first `led_vdd` route severed the F.Cu GND pour neck and orphaned `D5` VSS in a 77mm² island, DRC's only unconnected item; moving that branch to B.Cu fixed it, pour back to 2 islands with all four VSS in the main one. Firmware carry-over: hold `GPIO17` low or high-Z whenever the rail is down.

- **2026-07-30:** Dropped the JLCPCB assembly rotation preview item, Landon's call. Recoverable from git history if a later order goes through JLC assembly. The one failure mode worth keeping, `Q2` gate on SOT-23 pin 1, is under the pin-1 walk above.

- **2026-07-30:** Mechanical check closed by 3D print. All nine holes nominal in the mesh, three mount 2.9mm, four ANO 4.0mm, two pegs 1.6mm; slab 1.51mm rather than 1.6mm because that is what the project stackup stores. No board change.

- **2026-07-30:** PCBWay flagged four vias inside SMD pads on the `2026.7.0` package, solder-paste leakage risk. All four cleared, front silk revision bumped to `2026.7.1`.
