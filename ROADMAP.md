# Roadmap — c6remote

Hardware findings from schematic + PCB audit (2026-05-25), reconciled against the live design (2026-07-17). Ordered by severity.

## Critical

- [x] **Add IR LED current-limit resistor (D1).** ~~No series R between +3.3V and D1 — only base R1 (470Ω) on Q1. Will destroy IR LED or transistor.~~ Added R3 22Ω 0603 in series between +3.3V and D1 anode; placed on PCB at (55, 33.258) F.Cu with trace to D1 anode and via to B.Cu +3.3V pour. DRC clean for this change.

## High

- [x] **Add I²C pull-ups.** ~~SDA/SCL had no external pull-ups; ESP32-C6 internal pulls too weak for PCF8575 + 16 keys + rotary.~~ R4 4.7k SDA→+3.3V, R5 4.7k SCL→+3.3V added and placed on F.Cu near U1/U3.
- [x] **Decide D2 SK6812 power rail.** ~~`VCC = U1/14 (VBUS)` would leave LED dead on battery-only.~~ Rewired D2/4 and C2/1 to +3.3V — LED works on battery. (VCC label on U1.14/VBUS is a dangling single-node net; rename to `VBUS` for clarity someday.)
- [x] **Add TSOP IR receiver supply filter.** ~~U2 TSOP45xx missing datasheet filter.~~ R6 100Ω 0603 inline +3.3V→U2/3, C3 100nF 0603 U2/3↔U2/2. Both placed on PCB (R6 @38.5,33 / C3 @40.5,35.5) and routed — 0 unconnected items.

## Medium

- [x] **Decide PCF8575 INT (U3/1) handling.** Wired to net `exp_int` → XIAO pin24, with R9 100k pull-up to +3.3V. Interrupt-driven path in place.
- [ ] **Add 100nF decoupling at U3 PCF8575 VDD.** U3/24 currently sees only bulk 1µF (C1/C2) on +3.3V. Add 100nF 0603 directly between U3/24 (VDD) and U3/12 (GND); keep C1 as bulk.
- [ ] **Add rotary encoder pull-ups (optional).** `ano_enc1/2` go straight ENC1→XIAO (ENC1/7→U1/10, ENC1/3→U1/9) with no external pulls, relying on MCU internal. Add 10kΩ 0603 to +3.3V on each channel for robustness; optional 10nF to GND for hardware debounce.
- [x] **Fix SW1-11 button footprint / 3D model to match sourced part.** ~~Board carries E-Switch `SW_TL3315NF160Q` but assumed assembled part was a generic 6mm tactile.~~ Resolved 2026-07-17: PCBWay confirmed by email (Freya, 2026-07-16) they purchased the exact TL3315NF160Q from the BOM, and the assembly photo shows the matching SMD part. Footprint and BOM were already correct. 3D model was wrong part entirely: `SW_SPST_PTS647Sx50_black.step` (5.0mm tall plunger) replaced with generated `3dmodels/TL3315NF160Q.wrl` built from the TL3315 datasheet drawing (4.5x4.5x0.55 ultra low profile, dark gray housing, 4.0 dia gold snap dome, silver gull wings at 4.75 span) in the lib footprint and all 11 board instances; old step deleted; readme board renders regenerated. Manufacturer STEP was rejected: it is a flat uncolored slab with no dome. Note: WRL renders in KiCad but is excluded from board STEP exports for MCAD - at 0.55mm tall the switches are negligible for enclosure work. The two `SW_PUSH_6mm` THT swap stashes ("SW1-11 footprint swap TL3315->SW_PUSH_6mm" and "WIP button THT swap") are obsolete and can be dropped; a THT swap would also have required ~20 track reroutes around new drill holes and a 90-degree contact-orientation fix, all moot now.

## Low (cosmetic / config)

- [ ] **Fix ERC label-style collisions.** "Local and global labels have same name" near XIAO (+3.3V, GND, BAT, sw*). Pick one label style per net. (ERC now 14 violations, down from 23 baseline.)
- [ ] **Re-sync ENC1 symbol from library.** ERC: "Symbol '_1' doesn't match copy in library 'ano rotary'".
- [ ] **Fix silkscreen clipping and silk-over-copper.** `silk_edge_clearance` + `silk_over_copper` warnings around XIAO module. Move ref designators inboard and off pads. (DRC 42 violations total.)
- [ ] **Re-sync JST PH footprint.** `lib_footprint_mismatch` on J1 — pull latest from `Connector_JST`.
- [ ] **Enable Seeed XIAO + Library footprint libs.** Map `Library` → `kicad lib/Library.pretty` (per CLAUDE.md) and add Seeed lib to `fp-lib-table` to silence library-config warnings.

## Added since audit (not in original findings)

- Battery-sense divider: R7 (BAT→bat_sense) + R8 (bat_sense→GND) → XIAO pin28 for ADC battery monitoring.
- Full sourcing in BOM: Manufacturer, MPN, and Digikey/Mouser/Adafruit product URLs on every line.

## Verified clean

- All 11 pushbuttons + 5 rotary switches → PCF8575 P0_0…P1_7, pin1=GND / pin2=expander.
- MK1 I²S mic mapped: SCK/WS/L-R(GND)/SD/VDD/GND.
- XIAO power pins 12/31 (3V3), 13/27/33 (GND), 32 (BAT→J1), 14 (VBUS→VCC).
- BAT rail J1/1 ↔ U1/32 (charging via XIAO BMS), plus R7/R8 sense tap.
- No orphaned wires, no floating labels, no electrical DRC errors, 0 unconnected items.

## BOM additions (reference)

| Part | Value | Pkg | Where | Status |
|---|---|---|---|---|
| R3 | 22 Ω | 0603 | Series with D1 IR LED | done |
| R4/R5 | 4.7 kΩ | 0603 | SDA→+3.3V, SCL→+3.3V | done |
| R6 | 100 Ω | 0603 | +3.3V → U2/3 | done |
| C3 | 100 nF | 0603 | U2/3 ↔ U2/2 | done |
| R9 | 100 kΩ | 0603 | exp_int pull-up | done |
| R7/R8 | 100 kΩ | 0603 | BAT sense divider → U1/28 | done |
| C (new) | 100 nF | 0603 | U3/24 ↔ U3/12 | open |
| R ×2 (opt) | 10 kΩ | 0603 | ano_enc1/2 → +3.3V | open |
| C ×2 (opt) | 10 nF | 0603 | ano_enc1/2 → GND | open |
