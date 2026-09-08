# Power budget

This file is datasheet arithmetic as of 2026-09-07. No bench measurement exists. The measurement task is in [`ROADMAP.md`](../ROADMAP.md).

Every figure below is a typical value at 25 °C unless noted. `U1` figures are Seeed's for the module, so they already include its LDO and power-path quiescent.

Three loads are zero in the sleep column: `D2`-`D5` sit behind `Q2` on `led_vdd`, `U2` sits behind `Q3` on `ir_vdd` as of 2026-08-04, and `MK1` drops to sleep on its own whenever the I²S clock stops, which ESPHome does whenever nothing is streaming. Rev-B is the `2026.8.0` board and has no `Q3`. On that build `U2` draws its 350 µA in sleep, so the floor is the pre-gate ~0.41 mA quoted at the end of this file.

| Part | Deep sleep | Awake | Source |
| --- | --- | --- | --- |
| U1 XIAO ESP32-C6 | 15 µA | 30 mA modem-sleep, 3.1 mA light-sleep | Seeed wiki |
| U2 TSOP6136 via `ir_vdd` | 0 gated off | 350 µA | Vishay 82457 rev 2.0, ISD typ at Vs = 3.3 V, Ev = 0; 450 µA max, and ISH 450 µA typ under 40 klx sun. Unchanged by the 2026-08-17 swap off the TSOP4136, which had the same figures. Q3 gates it |
| MK1 DMM-4026-B-I2S-R | 5 µA | 1000 µA streaming | PUI `specs-DMM-4026-B-I2S-R` page 1. Sleep mode with the clock off is 5 µA; normal mode is 820 to 1000 µA, and the table gives no typical value. Rated at VDD 1.8 V over a 1.5 to 3.6 V range, so expect more on the 3.3 V rail. The ICS-43434 this replaced on 2026-09-07 was 12 µA asleep and 490 µA streaming |
| U3 PCF8575 | ~10 µA standby | ~30 µA at 100 kHz SCL | TI SCPS121I figures 6-1 and 6-2, Vcc 3.3 V |
| R7/R8 divider | 21 µA | 21 µA | 100k + 100k across BAT at 4.2 V. Sits on the battery, not the LDO output, so it is never switched |
| D2-D5 via `led_vdd` | 0 | 0 gated off, 2.0 mA powered but dark, 60 mA full white | 4 × 3 ch × 5 mA. Q2 gates it |
| R10 / R11 gate pull-ups | 0 | 3.3 µA each, only while the matching enable is driven low | |
| R4/R5 I²C pull-ups | 0 | ~700 µA per line while low | duty-cycled, negligible averaged |
| D1 + Q1 IR emit | 0 | ~80 mA through D1 plus 5.5 mA base | (3.3 - 1.35 - 0.2) / 22, burst only. `R3` went to 10R at `1b5c4d1` on 2026-08-17, which that commit estimates at 130 to 150 mA. Burst only, so the sleep and awake totals do not change |
| R9 on `exp_int` | 0 | 0 while nINT idles high | |

**Deep sleep: ~51 µA**, since `Q3` now takes `U2`'s 350 µA out of the sleep column. Before gating it was ~0.41 mA. The largest remaining static load is the R7/R8 divider at 21 µA, which sits on the battery and cannot be switched.

**Awake and Wi-Fi connected: ~31 mA**, or ~85 mA with power save off. Board silicon contributes 1.4 mA of that, under 5%, so the radio is the entire awake budget and no passive component choice moves it. Gating buys nothing while awake, and is not meant to: the `IR Rail` switch defaults on.

Battery life at 80% usable capacity. No cell is specified anywhere in the design, `J1` is only the connector, so 1000 mAh is an assumption to make the numbers concrete; scale linearly for any other capacity.

| Duty | Average | Life |
| --- | --- | --- |
| Deep sleep only | 51 µA | 653 days |
| Always connected | 31 mA | 26 hours |
| 30-day target | 1.11 mA | 3.4% awake, about 49 min/day |

For comparison, before `Q3` the floor was 0.41 mA, which was 82 days of standby and only 33 min/day awake against the same 30-day target.
