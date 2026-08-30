# Pre-fab checklist

Run before every board order, on top of routine ERC/DRC. Covers what ERC/DRC cannot see: real manufacturer capability limits, mechanical fit, pin-1 orientation.

Open findings: `ROADMAP.md`. Board status and history: `docs/timeline.md`. Commands assume `cd c6remote-kicad` and `KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`.

## Automated

- [x] **ERC** `$KC sch erc c6remote.kicad_sch --exit-code-violations`
  2026-08-01: 0 violations.

- [x] **DRC, parity, refill** `$KC pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations`
  2026-08-01: 0 errors, 0 unconnected, 1 warning (`lib_footprint_mismatch` on `U1`). Parity 0. Known, not a defect.

- [x] **STEP export** catches broken 3D model refs before they become mechanical surprises.
  `$KC pcb export step c6remote.kicad_pcb --subst-models -o /tmp/c6remote-check.step`
  2026-07-28: succeeds, 3.0MB. Two models still missing, both cosmetic since STEP substitutes or omits and fab geometry is unaffected: `D2`-`D5` want `LED_SMD.3dshapes/LED_WS2812B-2020_PLCC4_2.0x2.0mm.step`, `J1` wants `Connector_JST.3dshapes/JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal.step`. VRML-only models skip too, expected.

- [x] **IBOM** `scripts/gen-ibom.sh`, feeds the pin-1 walk below.
  2026-07-28: `c6remote-kicad/ibom.html`, 282KB. First run clones `openscopeproject/InteractiveHtmlBom` into `~/.cache/InteractiveHtmlBom`, runs under KiCad's bundled Python (needs `pcbnew`).

`ibom.html` is a review artifact, gitignored, never commit it. Pre-commit hook regenerates it whenever `c6remote.kicad_pcb` is staged, so it tracks the board. That step is non-fatal: a `WARNING: gen-ibom.sh failed` line means the file is stale, rerun by hand before any pin-1 walk. A walk against stale geometry is worth nothing.

## Manual, before ordering

- [ ] **PCBWay DFM.** Upload `export/` gerbers through the order flow, read the DFM report. Authoritative capability check: acid traps, mask slivers, annular rings against their real process.

- [ ] **Declare `MK1` as a no-wash part in the order notes.** Not optional, and not something the fab will infer. `MK1` is a bottom-port MEMS microphone whose acoustic port opens into a 0.5mm NPTH, and `AN-100` page 2 says the package "can be damaged if subjected to cleaning processes. The cleaning solvents can enter through the port hole and damage the device", plus "Do not clean MEMS sensors in ultrasonic baths" and no vapor phase soldering. `DS-000069` page 18 adds "Do not use blow-off procedures or ultrasonic cleaning". PCBWay publishes ten assembly stages but no cleaning policy, and its own blog says the factory "primarily uses rosin-based flux", which implies a solvent clean. State in the notes: no ultrasonic cleaning, no aqueous wash or DI rinse, no compressed-air blow-off, and hand-place `MK1` after any wash step if one is unavoidable. Ask for the reflow profile and confirm peak stays under the 260°C limit for a sub-1.6mm part. Also ask the MSL rating and bake procedure used, since neither `AN-100` Table 2 nor `DS-000069` gives this part an MSL. Reason this exists: the mic on the current board reads about 21dB deaf while its digital path works, and assembly-stage port contamination is the leading explanation, see `docs/mic-v2-debugging.md`.

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

- **2026-08-25:** Traced the deaf `MK1` to a probable assembly cause and added the no-wash order item above. Read `AN-100`, the handling guide `DS-000069` defers to, now in `localdatasheets/`; it forbids cleaning processes, ultrasonic baths and vapor phase soldering outright, because "cleaning solvents can enter through the port hole and damage the device". Cross-checked against what PCBWay publishes: ten assembly stages, no cleaning policy, no MSL or bake procedure, no reflow profile, and no order field for special handling, while their own cleaning article describes an ultrasonic bath, a DI water rinse and compressed-air drying, and states the factory "primarily uses rosin-based flux". So every prohibition in `AN-100` maps onto a step PCBWay describes, and nothing published says whether this order got them. Corroboration, not proof: two people on the ESPHome Discord independently built ICS-43434 boards with the same symptom, data and clocks fine and no acoustic response, one across three PCBWay boards, and both had the 0.1uF decoupling cap this board lacks. Also unchecked to date: this board's reflow peak against the 260°C limit for a sub-1.6mm part. No board change from this entry.

- **2026-08-01:** PCBWay reported vias in pad again against the newer files. Not reproducible: a geometric sweep of every via against every pad (via centre plus annular ring versus each pad rectangle, layer-agnostic) finds the four originals at `1693423^` sitting dead centre in R9.1, R9.2, SW11.2 and U3.1 at -0.300mm, and zero hits on both `2026.7.1` and the current board. Closest approach now is 0.305mm of clear copper at U3 pin 1. Either their review ran against the `2026.7.0` package or their DFM means something else by the term, so their marked-up file is needed to close it. Reusable check: `scripts/check-via-in-pad.py`.
