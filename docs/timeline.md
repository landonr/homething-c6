# Timeline and hardware revisions

Fabrication and bring-up history for c6remote. Design status and open work live in [`ROADMAP.md`](../ROADMAP.md), which also carries the microphone root cause and the corrected MK1 wiring.

The first assembled prototype arrived from PCBWay on Monday 2026-07-20 (order YT1753739, PCB plus SMD assembly). Bring-up found three wiring faults, all fixed in the design: ANO encoder pad 6/8 swap, TL3315 switch terminal short, ICS-43434 microphone pin numbering. Switches and encoder are reworkable on unit 1, the microphone is not, so a rev-B board is needed for the first working mic.

## Milestones

| Date | Milestone |
| --- | --- |
| 2026-06-16 | Quotation received for PCB and assembly, replied with updates; fab package finalized at `70ab9b0` (D1 and U2 swapped for PCBWay stock), tagged [2026.6.0](https://github.com/landonr/homething-c6/releases/tag/2026.6.0) |
| 2026-06-17 | Updated quotation approved; assembly order passed review |
| 2026-06-18 | Order confirmed, production queued |
| 2026-07-10 | Component engineering questions received from PCBWay |
| 2026-07-12 | Answers returned; PCBWay confirmed production is proceeding |
| 2026-07-14 | Assembled sample board photos received; PCBWay asked to confirm D1/U2 orientation before completing solder |
| 2026-07-15 | PCBWay adjusted D1 (90° lead bend firing through top-edge notch) and requested recheck |
| 2026-07-16 | D1 and full board orientation confirmed correct; assembly proceeding |
| 2026-07-20 to 2026-07-27 | First prototype delivered and brought up: PCF8575 found, TL3315 terminal short and ENC1 pad 6/8 swap root-caused and fixed in schematic and board, microphone found dead from an ICS-43434 pin-numbering fault, ANO directions measured (no 90° rotation after all), status lighting moved to a 4-LED XL-2020RGBC chain, back-silkscreen artwork added |
| 2026-07-29 | Release numbering moved to ESPHome-style CalVer (`YYYY.M.PATCH`); the `v0.1` tag and release were renamed `2026.6.0`, mapped from the 2026-06-16 fab date, and its asset renamed `c6remote-2026.6.0-fab.zip` |
| 2026-07-30 | Second fab package released: [2026.7.0](https://github.com/landonr/homething-c6/releases/tag/2026.7.0) at `f884350`, the first push to `main` under the new release workflow. PCBWay's review of it flagged four vias sitting inside SMD pads as a solder-paste leakage risk; all four cleared at `1693423`, and the front silk revision went to `2026.7.1` because a copper change makes it a different board. `silk_over_copper` and `silk_edge_clearance` were muted in DRC the same day, artwork unchanged |
| 2026-07-31 | No design change. `c6remote.kicad_pro` rule and severity drift root-caused to eeschema rewriting the file on save or close, now blocked by a pre-commit checker; the 13 stale `TP_*` footprint instances resynced to their library, taking DRC from 15 warnings to 2. Released as [2026.7.1](https://github.com/landonr/homething-c6/releases/tag/2026.7.1) at `76e4f44`, matching the front silk string the 07-30 copper fix had already bumped to |
| 2026-08-01 | PCBWay reported vias in pad against the newer files and asked whether the BOM had changed. Not reproducible: `scripts/check-via-in-pad.py` finds the four originals at `1693423^` but zero on `2026.7.1` or later, closest approach 0.305mm at U3 pin 1. Board reworked anyway: vias moved clear of pads, tracks tidied, all 14 `TP_*` test points deleted, `VCC` retired with `U1`/14 VBUS now a no-connect, R8 moved. Front silk bumped to `2026.8.0`, DRC down to 1 warning and parity to 0. BOM output byte-identical to `2026.7.1`, position file changed by one line (R8). Released as [2026.8.0](https://github.com/landonr/homething-c6/releases/tag/2026.8.0) at `d0a2c2e`, the current head of `main` |
| 2026-08-03 | Silkscreen wording only, no copper. The back-silk origin line went from `made in Vancouver\nCanada` to `designed in\nVancouver Canada`, and the front silk revision to `2026.8.1` since `2026.8.0` is already released. Still bottom-justified at y 105.5, so the stack above the flag is unchanged; the wider second line measures 20.286mm, 8.2mm clear of the left board edge and 8.5mm of the right. ERC 0, DRC 1 warning, parity 0. Unreleased, sitting on `develop`; the silk already reads `2026.8.1` so the next push to `main` tags what the artwork shows |
| 2026-08-04 | First power budget for the board, and the IR receiver rail gated on the back of it. `U2` was drawing 350uA continuously, 88% of a ~0.41mA deep-sleep floor, to listen for something that cannot wake the board: `IR REC` is on `GPIO16`, outside the C6's `GPIO0`-`GPIO7` wake range. `Q3` (`AO3401A`) plus `R11` (1M) now gate it as `ir_vdd`, enable `ir_en` on `GPIO6`, which was the last-but-one free pad, taking the sleep floor to ~58uA and standby on a 1000mAh cell from 82 days to 575. Placement is beside `U1` rather than `U2` so the 1M gate node stays short, with `ir_vdd` making the ~110mm run instead. First routing attempt pinched the F.Cu GND pour into unreachable pieces, the same trap `led_vdd` hit; fixed with stitching vias, pour now 3 regions all mutually reachable. ERC 0, DRC 1 warning, 0 unconnected, parity 0. Silk unchanged at `2026.8.1`, still unreleased, so it already matches the version this will ship as |

## Unit 1 (2026.6.0) versus the current design

Unit 1 is the only board that exists, and the design has moved on since it was fabbed. Everything below is a difference, so a photo or measurement from unit 1 does not describe what the next order will build. The 2026.6.0 fab package is attached to the [2026.6.0 release](https://github.com/landonr/homething-c6/releases/tag/2026.6.0).

Quickest way to tell the two apart in a photo: the front silkscreen under the logo reads **V0.1** on unit 1 and **2026.8.1** on the current design. The two strings differ in format, not just value, because the release numbering scheme changed from ad hoc `vX.Y` to CalVer between the two boards: unit 1 was fabbed under the old scheme and keeps its printed `V0.1` forever, the current design carries the new scheme's format. That mismatch in format is expected, not an inconsistency.

| Unit 1, as fabbed (`70ab9b0`) | Current design (`develop`) |
| --- | --- |
| <img src="https://raw.githubusercontent.com/landonr/homething-c6/70ab9b0be579d5dc36652c1610cfae01774bdac0/docs/readme-assets/board-flat-top.svg" width="240" alt="Front copper as fabbed, U2 on the front and one LED by the XIAO"> | <img src="https://raw.githubusercontent.com/landonr/homething-c6/develop/docs/readme-assets/board-flat-top.svg" width="240" alt="Front copper of the current design, four LEDs around the wheel and no front U2"> |
| <img src="https://raw.githubusercontent.com/landonr/homething-c6/70ab9b0be579d5dc36652c1610cfae01774bdac0/docs/readme-assets/board-flat-bottom.svg" width="240" alt="Back copper as fabbed"> | <img src="https://raw.githubusercontent.com/landonr/homething-c6/develop/docs/readme-assets/board-flat-bottom.svg" width="240" alt="Back copper of the current design, U2 moved to the back plus silkscreen artwork"> |

Both columns are the flat copper SVGs, which KiCad exports tight to the 36.98 x 130mm board outline, so the two scale alike with no cropping and no copied files. The right column is pinned to `develop` by branch name, so it always shows the current design no matter which branch you are reading this file on. It deliberately is not a relative path: relative paths resolve against the branch being viewed, and since `main` is the default branch, a visitor would otherwise get the last released snapshot under a column labelled `develop`. The left column is pinned to the fab commit by full sha and keeps showing the board PCBWay built regardless of what lands on either branch. Those renders were generated at `0df2483` and the 06-16 fab commit only touched a symbol value and the BOM, so they match the delivered copper.

| Block | Unit 1, as fabbed (`70ab9b0`) | Current design |
| --- | --- | --- |
| Status lighting | One `SK6812MINI` (3.5x3.5) as D2, with R2 330Ω in series on the data line and C2 1µF decoupling | Four `XL-2020RGBC-WS2812B` (2.0x2.0) as D2-D5 in a cascade around the wheel, no series R, and the VDD rail gated by a high-side load switch: Q2 AO3401A P-FET from `+3.3V` onto `led_vdd`, R10 1M gate pull-up holding it off by default, C4 1µF bulk cap mid-chain, enable net `led_en` on GPIO18 (drive low for on) |
| IR receiver | U2 `TSOP4136` on the front (F.Cu), two receiver cutouts in the top board edge | U2 on the back (B.Cu), both top-edge cutouts dropped |
| Discrete switches | TL3315 terminals 1/2 on `sw*` and 3/4 on GND, which shorts every populated switch input to GND | Terminals 1/2 on GND, 3/4 on `sw*` |
| ANO encoder | ENC1 pads 6 and 8 swapped, so COM_A sits on `ano_sw2` and the up switch common sits on GND | Pad 6 GND, pad 8 `ano_sw2` |
| Microphone | MK1 wired to INMP441 pin numbers, so the ICS-43434 gets the bit clock on WS and its SD pad buried in the GND pour | MK1 on the ICS-43434 numbering, `sck`/`ws`/`sd` on GPIO2/GPIO0/GPIO21 |
| Battery sense | Absent, no `bat_sense` net and no R7/R8 divider | R7/R8 100k divider to GPIO4 |
| Expander interrupt | Absent, no `exp_int` net and no R9 pull-up | R9 100k pull-up, nINT to GPIO5 |
| Battery connector | J1 through-hole `S2B-PH-K` | J1 SMD `S2B-PH-SM4-TB` |
| Board edge | Square corners, four square encoder cutouts | 3mm filleted corners, real Adafruit ANO cutout shapes |
| Mounting | No fixing points | Three 2.9mm holes for loose M2.5 screws into a case |
| IR emitter | D1 on a plain 3mm LED footprint, leads bent 90° by PCBWay at assembly | Forked horizontal footprint with + and - silk glyphs, so the bend is designed in |
| Via in pad | Four vias inside SMD pads, which PCBWay flagged 2026-07-30 as a solder-paste leakage risk | All four cleared |
| Silkscreen | Front homeThing logo only | Plus back artwork (flag, OSHW gear, made-in text) and a front mic-port mark |

Unit 1 hand rework so far: `sw*` traces cut and jumpered to the free terminal on all 11 switches, and ENC1 pad 6 severed from `ano_sw2` and jumpered to GND. Left, right, down, centre and both encoder channels work. Up cannot work until pad 8 is freed from the GND pour. The microphone is unreachable by rework because its SD pad is under a bottom-terminal LGA.
