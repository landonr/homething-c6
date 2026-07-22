# Roadmap — c6remote

Hardware findings from schematic + PCB audit (2026-05-25), reconciled against the live design (2026-07-17). Ordered by severity.

## Critical

- [ ] **ENC1 pad 6/8 function swap (root cause of dead up, center press, and rotation).** Confirmed 2026-07-21 by geometric match of `Library.pretty/Ano Rotary.kicad_mod` against Adafruit's own `ENCODER_ANO` Eagle footprint (all 9 pad radii match to 2 decimals, single 45 degree rotation, no mirror; sources: learn.adafruit.com/ano-rotary-encoder/pinouts, github.com/adafruit/Adafruit-ANO-Rotary-Navigation-Encoder-Breakout-PCB). Pad 6 (was wired to `ano_sw2`, U3 P14) is physically COM_A, the shared return for center push S1 and both encoder channels; pad 8 (was wired to GND as a second common) is physically S4, a switch contact. COM_A floating on a GPIO net killed center press and rotation; the pad 8 switch was hard-tied to GND. Netlist fault, identical on both units. Field-confirmed 2026-07-21: jumper pad 6 to pad 1 (GND) restored center press and rotation on unit 1.
  - [x] Design fix for next rev: symbol pins renamed to datasheet functions (COM_A, COM_B, S1_CENTER, S2_DOWN, S3_RIGHT, S4_UP, S5_LEFT, ENCA, ENCB) with pin numbers 6/8 swapped so existing schematic GND symbol and `ano_sw2` label land on correct pads; library and embedded schematic copies synced (clears old ERC symbol-mismatch item); board pads resynced (pad 6 GND, pad 8 `ano_sw2`); old pad 6 stub deleted, new F.Cu route from `ano_sw2` trace at (52.0, 61.2) to pad 8; zones refilled. ERC 0, DRC 0 errors 41 pre-existing warnings, 0 unconnected, parity 45 (baseline). NOTE: MCP `sync_schematic_to_board` also bogusly reassigned 5 pads and 4 segments to virtual net PWR_FLAG (U1 BAT, MK1 VDD, U2-Vs rail); hand-reverted, do not trust that tool's net resolution near PWR_FLAG symbols.
  - [x] Firmware direction remap: ENC1 mounts rotated 90 CW vs part-relative names (device-up = S5, device-down = S3, confirmed by two field observations). Yaml ports 11-15 renamed: P13 Down, P14 Right, P15 Press, P16 Left, P17 Up. P14/P16 inferred from rotation, verify after pad 8 rework.
  - [ ] Prototype unit 1: cut pad 6 trace to `ano_sw2` (jumper is on but trace uncut, so P14 "Encoder Right" reads stuck-pressed); then stage 2 for Up: cut pad 8 free of GND pour both layers, jumper pad 8 to the cut `ano_sw2` stub.
  - [ ] Prototype unit 2: full rework (cut pad 6 trace, jumper pad 6 to pad 1, cut pad 8 from pour, jumper pad 8 to stub).
  - [ ] Regenerate fab outputs after rework validation confirms mapping.
  - [ ] Optional: `ano_enc1`/`ano_enc2` land on ENCB/ENCA respectively (names crossed); only affects scroll count direction, swap yaml `pin_a`/`pin_b` if scrolling feels reversed.
- [ ] **Fix SW1-11 TL3315 terminal mapping short.** First prototype bring-up on 2026-07-20 confirmed PCF8575 communication, but SW1-8 and SW10-11 read permanently pressed while all five ANO encoder switches read released. TL3315NF160Q terminals 1 and 2 are internally common, as are terminals 3 and 4. Current footprint assigns GND to pad 1 and `sw*` to pad 2, shorting each populated switch input directly to GND. SW9 reads released, likely from an open or incomplete joint, and does not invalidate the mapping fault. Prototype rework: cut each `sw*` F.Cu trace immediately before pad 2, then jumper trace side to unused pad 4. Verify released input is open to GND and pressed input is near 0 ohms on one switch before repeating. Next revision: assign GND to pads 1 and 2, and `sw*` to pads 3 and 4 in schematic symbol, footprint, and PCB.
  - [x] Schematic done (2026-07-21): replaced generic 2-pin `Switch:SW_Push` with 4-pin `Local:SW_TL3315NF160Q` (new `Local.kicad_sym`, registered in sym-lib-table). Pins 1,2 stacked on GND node, pins 3,4 stacked on `sw*` node. Netlist verified all 11 SW: pads 1,2 GND, pads 3,4 `sw*`. ERC 0. Board copper unchanged (still old mapping) so schematic-vs-board parity now diverges by design until PCB is reworked/regenerated.
  - [ ] Board still carries old copper (GND pad 1, `sw*` pad 2). Prototype hand-rework per above, then regenerate fab. Do NOT sync_schematic_to_board blindly (would reroute copper).
- [x] **Add IR LED current-limit resistor (D1).** ~~No series R between +3.3V and D1 — only base R1 (470Ω) on Q1. Will destroy IR LED or transistor.~~ Added R3 22Ω 0603 in series between +3.3V and D1 anode; placed on PCB at (55, 33.258) F.Cu with trace to D1 anode and via to B.Cu +3.3V pour. DRC clean for this change.

## High

- [x] **Add I²C pull-ups.** ~~SDA/SCL had no external pull-ups; ESP32-C6 internal pulls too weak for PCF8575 + 16 keys + rotary.~~ R4 4.7k SDA→+3.3V, R5 4.7k SCL→+3.3V added and placed on F.Cu near U1/U3.
- [x] **Decide D2 SK6812 power rail.** ~~`VCC = U1/14 (VBUS)` would leave LED dead on battery-only.~~ Rewired D2/4 and C2/1 to +3.3V — LED works on battery. (VCC label on U1.14/VBUS is a dangling single-node net; rename to `VBUS` for clarity someday.)
- [x] **Add TSOP IR receiver supply filter.** ~~U2 TSOP45xx missing datasheet filter.~~ R6 100Ω 0603 inline +3.3V→U2/3, C3 100nF 0603 U2/3↔U2/2. Both placed on PCB (R6 @38.5,33 / C3 @40.5,35.5) and routed — 0 unconnected items.

## Medium

- [x] **Decide PCF8575 INT (U3/1) handling.** Wired to net `exp_int` → XIAO pin24, with R9 100k pull-up to +3.3V. Interrupt-driven path in place.
- [x] **Add 100nF decoupling at U3 PCF8575 VDD.** Evaluated 2026-07-17, decided NOT to add. C1 (1µF 0805) already sits ~2mm from U3/24 on F.Cu with a short loop. PCF8575 is a slow I2C GPIO expander (400kHz bus, static outputs) with negligible HF supply demand, so C1 alone is sufficient. A 100nF would only help at HF, and the F.Cu corner around pin24 is fully routed (SDA/SCL fanout to R4/R5), so the only free spot was B.Cu-through-vias, whose via inductance negates the low-ESL HF benefit. Not worth the redundancy. Prototype C4 addition was reverted.
- [ ] **Add rotary encoder pull-ups (optional).** `ano_enc1/2` go straight ENC1→XIAO (ENC1/7→U1/10, ENC1/3→U1/9) with no external pulls, relying on MCU internal. Add 10kΩ 0603 to +3.3V on each channel for robustness; optional 10nF to GND for hardware debounce.
- [x] **Fix SW1-11 button footprint / 3D model to match sourced part.** ~~Board carries E-Switch `SW_TL3315NF160Q` but assumed assembled part was a generic 6mm tactile.~~ Resolved 2026-07-17: PCBWay confirmed by email (Freya, 2026-07-16) they purchased the exact TL3315NF160Q from the BOM, and the assembly photo shows the matching SMD part. Footprint and BOM were already correct. 3D model was wrong part entirely: `SW_SPST_PTS647Sx50_black.step` (5.0mm tall plunger) replaced with generated `3dmodels/TL3315NF160Q.wrl` built from the TL3315 datasheet drawing (4.5x4.5x0.55 ultra low profile, dark gray housing, 4.0 dia gold snap dome, silver gull wings at 4.75 span) in the lib footprint and all 11 board instances; old step deleted; readme board renders regenerated. Manufacturer STEP was rejected: it is a flat uncolored slab with no dome. Note: WRL renders in KiCad but is excluded from board STEP exports for MCAD - at 0.55mm tall the switches are negligible for enclosure work. The two `SW_PUSH_6mm` THT swap stashes ("SW1-11 footprint swap TL3315->SW_PUSH_6mm" and "WIP button THT swap") are obsolete and can be dropped; a THT swap would also have required ~20 track reroutes around new drill holes and a 90-degree contact-orientation fix, all moot now.

## Low (cosmetic / config)

- [ ] **Fix ERC label-style collisions.** "Local and global labels have same name" near XIAO (+3.3V, GND, BAT, sw*). Pick one label style per net. (ERC now 14 violations, down from 23 baseline.)
- [x] **Re-sync ENC1 symbol from library.** ~~ERC: "Symbol '_1' doesn't match copy in library 'ano rotary'".~~ Library and embedded copies rewritten identically during 2026-07-21 pad 6/8 fix; ERC 0.
- [ ] **Fix silkscreen clipping and silk-over-copper.** `silk_edge_clearance` + `silk_over_copper` warnings around XIAO module. Move ref designators inboard and off pads. (DRC 42 violations total.)
- [ ] **Re-sync JST PH footprint.** `lib_footprint_mismatch` on J1 — pull latest from `Connector_JST`.
- [ ] **Enable Seeed XIAO + Library footprint libs.** Map `Library` → `kicad lib/Library.pretty` (per CLAUDE.md) and add Seeed lib to `fp-lib-table` to silence library-config warnings.

## Added since audit (not in original findings)

- Battery-sense divider: R7 (BAT→bat_sense) + R8 (bat_sense→GND) → XIAO pin28 for ADC battery monitoring.
- Full sourcing in BOM: Manufacturer, MPN, and Digikey/Mouser/Adafruit product URLs on every line.

## Verified clean

- PCF8575 communication verified during prototype bring-up. SW1-11 logical net mapping reaches P0_0 through P1_2, but populated TL3315 terminal pairing shorts the discrete button inputs and requires rework. ANO switch reads from bring-up predate the pad 6/8 swap finding above: only Left, Right, Down land on true switch contacts.
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
| ~~C~~ | ~~100 nF~~ | ~~0603~~ | ~~U3/24 ↔ U3/12~~ | declined (C1 sufficient) |
| R ×2 (opt) | 10 kΩ | 0603 | ano_enc1/2 → +3.3V | open |
| C ×2 (opt) | 10 nF | 0603 | ano_enc1/2 → GND | open |
