# Hardware TODO — c6remote

Findings from schematic + PCB audit (2026-05-25). Ordered by severity.

## Critical

- [x] **Add IR LED current-limit resistor (D1).** ~~No series R between +3.3V and D1 — only base R1 (470Ω) on Q1. Will destroy IR LED or transistor. Add ~22Ω 0603 between +3.3V and D1 anode, OR between D1 cathode and Q1 collector. Value: `(3.3 − Vf_LED − Vce_sat) / I_target` → (3.3 − 1.3 − 0.2)/0.1A ≈ 18Ω → use 22Ω 1/4W.~~ Added R3 22Ω 0603 in series between +3.3V and D1 anode in schematic, placed on PCB at (55, 33.258) on F.Cu with horizontal trace to D1 anode and via to B.Cu +3.3V pour. DRC clean for this change (48 total violations, baseline 50, no R3-related errors).

## High

- [x] **Add I²C pull-ups.** ~~SDA and SCL have no external pull-ups. ESP32-C6 internal pulls (~45kΩ) are too weak for PCF8575 + 16 keys + rotary. Add 4.7kΩ 0603 each: `SDA → +3.3V`, `SCL → +3.3V`.~~ R4 4.7k SDA→+3.3V, R5 4.7k SCL→+3.3V added; placed on F.Cu near U1/U3 (R4 at 60,121 / R5 at 61.325,125). DRC: 0 errors, 42 warnings (all baseline cosmetic).
- [x] **Decide D2 SK6812 power rail.** ~~Currently `VCC = U1/14 (VBUS)` → LED dead on battery-only. If LED must work on battery, re-wire D2/4 and C2/1 to +3.3V (SK6812MINI runs dimmer at 3.3V but functional).~~ Rewired D2/4 and C2/1 to +3.3V — LED now works on battery. VCC label remains on U1.14 (VBUS) as dangling single-node net `/VCC`; consider renaming to `VBUS` for clarity.
- [~] **Add TSOP IR receiver supply filter.** ~~U2 TSOP45xx missing datasheet-recommended filter. Add 100Ω 0603 inline on `+3.3V → U2/3 (Vs)` and 100nF 0603 from `U2/3 → U2/2 (GND)`, placed close to U2.~~ R6 100Ω 0603 inline +3.3V→U2/3 + C3 100nF 0603 from U2/3↔U2/2 added to schematic; PWR_FLAG02 on filtered Vs net (resistor breaks power chain otherwise); VCC label converted to global to stop /VCC slash-prefix on PCB sync. PCB placement + routing pending.

## Medium

- [ ] **Add 100nF decoupling at U3 PCF8575 VDD.** C1 (1µF) is too far away. Add 100nF 0603 directly between U3/24 (VDD) and U3/12 (GND). Keep C1 as bulk.
- [ ] **Add rotary encoder pull-ups (optional).** `ano_enc1/2` rely on MCU internal pulls. Add 10kΩ 0603 to +3.3V on each channel for robustness. Optional 10nF to GND for hardware debounce.
- [ ] **Decide PCF8575 INT (U3/1) handling.** Floating today. OK if firmware polls. If interrupt-driven, wire to a spare XIAO GPIO with 10kΩ pull-up to +3.3V.

## Low (cosmetic / config)

- [ ] **Fix ERC label-style collisions.** 10 warnings "Local and global labels have same name" near XIAO (+3.3V, GND, BAT, sw*). Pick one label style per net.
- [ ] **Re-sync ENC1 symbol from library.** ERC: "Symbol '_1' doesn't match copy in library 'ano rotary'".
- [ ] **Fix silkscreen clipping and silk-over-copper.** 8 `silk_edge_clearance` + 18 `silk_over_copper` warnings around XIAO module and near (34.84, 158.21), (40.84, 30.71). Move ref designators inboard and off pads.
- [ ] **Re-sync JST PH footprint.** `lib_footprint_mismatch` on J1 — pull latest from `Connector_JST`.
- [ ] **Enable Seeed XIAO + Library footprint libs.** Map `Library` → `kicad lib/Library.pretty` (per CLAUDE.md) and add Seeed lib in `fp-lib-table` to silence library-config DRC warnings.

## BOM additions

| Part | Value | Pkg | Where |
|---|---|---|---|
| R | 22 Ω | 0603 | Series with D1 IR LED |
| R ×2 | 4.7 kΩ | 0603 | SDA→+3.3V, SCL→+3.3V |
| R | 100 Ω | 0603 | +3.3V → U2/3 |
| C | 100 nF | 0603 | U2/3 ↔ U2/2 |
| C | 100 nF | 0603 | U3/24 ↔ U3/12 |
| R ×2 (opt) | 10 kΩ | 0603 | ano_enc1/2 → +3.3V |
| C ×2 (opt) | 10 nF | 0603 | ano_enc1/2 → GND |

## Verified clean

- All 11 pushbuttons + 5 rotary switches → PCF8575 P0_0…P1_7, pin1=GND / pin2=expander.
- MK1 I²S mic correctly mapped: SCK/WS/L-R(GND)/SD/VDD/GND.
- XIAO power pins 12/31 (3V3), 13/27/33 (GND), 32 (BAT→J1), 14 (VBUS→VCC).
- BAT rail J1/1 ↔ U1/32 only (charging via XIAO BMS).
- No orphaned wires, no floating labels, no electrical DRC errors.
