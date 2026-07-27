# MK1 microphone bring-up

Status as of 2026-07-27: **FAIL on this build, root cause found.** The fault
is the schematic symbol's pin numbering, not firmware and not assembly. Every
mic signal lands on the wrong physical pin, and the mic's data output is
soldered into the ground pour, so no firmware change can recover this board.
Rev-B fix is in progress (symbol renumbered, PCB being updated by hand). This
was the first time the mic was actually exercised on hardware; `ROADMAP.md`
only ever recorded that its nets were mapped in the schematic.

Test firmware: `c6remote-test-mic.yaml` (repo root, alongside
`c6remote-test-v1.yaml` and `c6remote-test-v2.yaml`).

## Result

```
193536 B/s, 63 blocks, peak -100.0 dBFS, rms -100.0 dBFS,
zero 100.0%, dc 0, min 0 max 0
Verdict: clocked but all zeros: check SD, L/R pin, channel
```

Expected byte rate is 192000 (48kHz x 32-bit x one channel), and the measured
190464 to 193536 B/s is that rate inside the 1s sampling jitter. So the I2S
read path is alive and the ESP is generating clocks. What comes back is 100%
zero samples, min 0 and max 0, sustained over 60+ blocks per second.

Reflashed with `channel: right` as a separate build: identical 100% zeros. Slot
selection is therefore ruled out.

## Root cause

The `ICS_43434` schematic symbol has wrong pin numbers. Verified against the
TDK DS-000069-ICS-43434 v1.2 datasheet (Table 8, Fig 3, Fig 15):

| Physical pin | Datasheet function | Symbol had |
|---|---|---|
| 1 | WS | SCK |
| 2 | LR | WS |
| 3 | GND | L/R |
| 4 | SCK | SD |
| 5 | VDD | VDD |
| 6 | SD | GND |

The stock KiCad footprint `Sensor_Audio:InvenSense_ICS-43434-6_3.5x2.65mm` is
correct: pad N is physical pin N (checked against Fig 3 and Fig 15, the board's
embedded copy is just the stock footprint flipped to B.Cu). So the netlist
routes every signal to the wrong physical pin on the fabbed board:

- Mic WS (pin 1) receives the 3.072MHz SCK.
- Mic LR (pin 2) receives the 48kHz WS.
- Mic SCK (pin 4) hangs on the undriven `sd` net and floats.
- Mic SD output (pin 6) is soldered straight into the GND pour.

Why the symptom matched exactly: with SCK below about 200kHz the mic enters
standby and tristates SD, so the grounded output causes no contention and no
damage. The ESP generates its own clocks and samples GPIO0, which connects
only to the mic's high-Z SCK input, hence exact zeros at the correct byte rate
on both channel settings.

Firmware cannot recover this board: the mic SD pad has no path to any GPIO, it
is tied into the ground pour. The mic is dead on this build without impractical
rework (LGA bottom-terminal part).

Fix in progress for rev-B: schematic symbol pins renumbered to the datasheet,
PCB nets and routing being updated to match (Landon is doing the PCB side by
hand).

## Ruled out in firmware

Pins were checked against the exported schematic netlist, not against the
comments in the yaml:

| Net | Mic pin | XIAO pin |
|---|---|---|
| `sd` | MK1.4 SD | U1.1 GPIO0 |
| `sck` | MK1.1 SCK | U1.3 GPIO2 |
| `ws` | MK1.2 WS | U1.4 GPIO21 |
| GND | MK1.3 L/R, MK1.6 GND | |
| +3.3V | MK1.5 VDD | |

MK1.3 L/R sits on GND, so the part transmits in the left half of the frame and
`channel: left` is the correct setting. That is what the firmware ships with.
(Note: the mic pin numbers above are the symbol's, which the root cause shows
are wrong. The firmware conclusions stand, the netlist itself was the fault.)

Sample decode is also correct for an ICS-43434 class part: 24-bit sample, MSB
aligned in a 32-bit slot, so the firmware shifts each raw word right by 8 and
treats 2^23 as full scale. A wrong shift or slot width would produce garbage or
a large DC offset, not exact zeros.

## Hardware checks (superseded by root cause)

These were the planned next steps before the root cause was found. They are
superseded: checks 1 to 3 (population, 3.3V, continuity) would all PASS,
because the fault is netlist-level, not assembly. Only check 4, a scope on the
mic pads, would have caught it, by showing the clocks present but at the wrong
pins (SCK on pin 1, WS on pin 2).

1. MK1 populated, correctly oriented, all six pads wetted.
2. 3.3V present at MK1.5.
3. Continuity MK1.4 to XIAO D0, MK1.1 to D2, MK1.2 to D3.
4. Scope or logic probe at the MK1 pads: with capture on, SCK should show
   3.072MHz (48000 x 32 x 2) and WS 48kHz. If they are absent at the mic pad
   but present at the XIAO pad, the break is in the trace.

## Firmware bugs found while building the test

Both are fixed in the shipped file, recorded here because they are easy to
reintroduce.

- `Mic Capture` was declared `restore_mode: ALWAYS_ON`. A restored switch state
  runs its `turn_on_action` during `setup()`, which called
  `microphone.capture` before the I2S component had created its queue, giving
  `assert failed: xQueueSemaphoreTake queue.c:1709` and an immediate panic. Ten
  reboots later ESPHome latched safe mode, which runs no components at all, so
  the board looked bricked and silent. Capture now starts from `on_boot` at
  priority -100, after every component setup, and the switch is `ALWAYS_OFF`.
- Serial logs appeared to be dead when read with a raw port reader or with
  `esphome logs` started separately. They were not: the board was in the panic
  loop above. Use `esphome run`, which resets the board and attaches to the
  console in one step. Logger default on ESP32-C6 is already `USB_SERIAL_JTAG`,
  so no `hardware_uart` override is needed, and UART0 must not be used here
  anyway since its default pins collide with the board's GPIO16/17.

## Using the test firmware

```bash
esphome run c6remote-test-mic.yaml                    # flash and watch logs
esphome -s mic_channel right run c6remote-test-mic.yaml   # other I2S slot
```

Unlike v1 and v2, which are deliberately network-free factory-station
firmwares, this one joins wifi and the Home Assistant API so every measurement
is a graphable entity, and serves a web server on port 80 for use without HA.
Capture starts automatically at boot.

Entities:

| Entity | Reading |
|---|---|
| Mic Verdict | plain-language pass/fail, start here |
| Mic Data Rate | 192000 B/s expected |
| Mic Peak Level, Mic RMS Level | dBFS. quiet room RMS -70 to -50, speech peaks past -30 |
| Mic Zero Samples | 100% while clocked means data line dead or wrong channel |
| Mic DC Offset | large fixed offset means wrong shift or slot |
| Mic Sample Min, Mic Sample Max | raw 24-bit extremes seen in the last window |
| Mic Peak Fraction | peak as a 0..1 fraction of full scale |
| Mic Signal Detected | binary, peak above -40 dBFS |
| Mic Capture | switch, turn off to confirm the rate really falls to zero |

The four WS2812s run a VU bar so the mic can be read with no client open: dim
blue when capture is off, a green bar rising with level, top LED red near clip.
Output is capped at 40%, same as v1 and v2, because the 2020 LEDs are specified
from 3.5V on a 3.3V rail.

All statistics are accumulated in the `on_data` lambda and drained once a
second by an interval, so nothing is missed between publishes: peak is a max
hold, rate is a true byte count, and RMS covers every sample seen.
