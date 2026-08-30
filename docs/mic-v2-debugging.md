# Rev B / V2 microphone debugging

This runbook covers Rev B/V2 boards with MK1, the ICS-43434 bottom-ported I2S microphone. It is a relative sound meter, not a calibrated SPL instrument.

**Read this first, 2026-08-26.** The build has five Rev B remotes. One mic works. One works with distortion. Three do not work, measured 2026-08-26. All five boards share one design, one firmware and one fab batch, so no design cause can explain the spread. If a mic is deaf, compare it against the working unit and do not repeat the ruled-out ladder below. Read "Assembly damage is the leading suspect" first.

## Confirm hardware mapping

| Function | XIAO ESP32-C6 | MK1 / ICS-43434 |
| --- | --- | --- |
| BCLK / SCK | GPIO2 | pin 4 |
| WS / LRCLK | GPIO0 | pin 1 |
| DIN / SD | GPIO21 | pin 6 |
| L/R select | left channel | pin 2 tied to GND |
| Ground |  | pins 2 and 3 |
| Supply | 3.3 V | pin 5 |

The mic hears through its bottom acoustic port and the PCB NPTH. The port is at `(53.350, 31.582)` and is 0.5 mm in the current footprint. Apply sound at the front-side PCB hole and mic marking. A tap on the opposite-side package is not a valid acoustic test.

Rev A had a different, known ICS-43434 pin-numbering fault. Do not use that diagnosis for Rev B. The table above is the corrected netlist and firmware mapping.

## Understand I2S format

The ICS-43434 carries a 24-bit audio payload in 32-bit I2S slots. Keep the bus at 32-bit slots. The standalone test extracts the payload with `sample >> 8`. The ESPHome meter shifts to 16-bit with `sample >> 16`.

### Sample rate and clock are not suspects

Checked against `localdatasheets/DS-000069-ICS-43434-v1.2.pdf` on 2026-08-24. `c6remote.yaml` runs the mic at 16 kHz and the test configs use 48 kHz. Table 5 explains why that gap does not matter.

- Table 5 lists three sample rate bands: sleep under 3.125 kHz, Low-Power 6.25 to 18.75 kHz, High-Performance 23 to 51.6 kHz. 16 kHz is a supported mode, not an out-of-spec corner.
- Table 3 gives Low-Power the same sensitivity as High-Performance, -26 dB FS typical at 94 dB SPL. A move from 48 kHz to 16 kHz costs SNR (64 dBA against 65 dBA) and nothing else. It does not explain a quiet mic.
- Page 12 requires 64 SCK cycles per WS frame. So 16 kHz gives SCK 1.024 MHz, tSCP 977 ns, and 48 kHz gives 3.072 MHz, tSCP 326 ns. Table 5 allows 303 to 2500 ns. Both are legal.

Do not spend time on the sample rate. If capture runs at all, the clock is legal.

The band that fs falls in is the only control over the mic mode, and 18.75 to 23 kHz belongs to no band. Never set a rate there.

## First ESPHome check

`c6remote.yaml` has a `Start Microphone Test` button that calls `microphone.capture`. The log line

```text
Captured 64512 bytes/s
```

proves that capture runs and DMA delivers data. `passive: false` is needed only for an ESPHome `sound_level` sensor, and this config does not use that platform. It does not explain low peaks.

The logged `level` is not reliable. `mic_level` is multiplied by `0.82` on every `on_data` callback, about every 16 ms, then printed once per second. It decays near zero between lines. Use `peak`, or the standalone test.

Convert `peak` to dB FS with `20 * log10(peak / 32768)`, because the meter is in the 16-bit domain. Landmarks:

| `peak` | dB FS | What it is |
| --- | --- | --- |
| 9 to 15 | -71 to -67 | Quiet room tone on a healthy mic |
| 50 | -56 | Best speech seen on the blocked-port board, 2026-08-24 |
| 550 | -35 | Close speech target, and what a button press produces |
| 32767 | 0 | Full scale |

`gain_factor` on the `voice_assistant` microphone source does **not** appear in this meter. The `on_data` trigger fires on the `Microphone`, upstream of the `MicrophoneSource` that applies gain. So `gain_factor` changes what Home Assistant receives and leaves the logged `peak` the same. The meter is not proof that a gain change did nothing.

## Use the button press as a positive control

Every capture that starts from a physical button shows a large peak in the first log line, 446 to 575, then drops to room tone. That is the press through the PCB into the diaphragm as structure-borne shock, not sound.

It is the most useful number in the log, because 550 is about -35 dB FS, the exact level close speech must produce. If the first line reads 446 to 575 and later lines read 9 to 15 while you talk into the port, this is proof:

- The diaphragm moves and the ADC responds.
- The 24-in-32 decode, the `>> 16` shift, DMA, and the ESPHome meter all carry -35 dB FS intact.
- So the digital path carries a large signal, and the loss is in front of the diaphragm.

That one comparison separates "deaf" from "broken" with no test equipment and no reflash. Do this first. It appears only on button-initiated captures, so a capture from Home Assistant or an automation will not show it.

One limit on this proof. A press has no known SPL, so the test shows that the path carries a large signal. It does not show that the path carries the correct absolute level. A uniform digital attenuation scales the press down with everything else and so hides inside this test. A 4-bit slot misalignment, for one, costs exactly -24 dB against a measured deficit of about 21 dB. Only a known-good microphone separates those two cases.

## Substitute a known-good microphone

This is the one test that splits every remaining hypothesis, and it needs no code change. Wire an INMP441 or ICS-43434 breakout module to GPIO2, GPIO0, and GPIO21, then run the standalone firmware without edits.

- The breakout reads correct levels: firmware, slot alignment, clocks, and mic mode are all exonerated. The fault is the soldered `MK1` or its port.
- The breakout is also about 21 dB down: the fault is in firmware after all, and slot alignment is the first thing to examine.

An INMP441 is a valid substitute even though the board carries an ICS-43434. Both parts use the same 24-in-32 Philips framing, so identical firmware drives either one.

## Expected levels from the datasheet

The baselines that follow are empirical. This is the absolute expectation, so one utterance can judge a board.

Sensitivity is -26 dB FS at 94 dB SPL and the scale is linear (Figure 7). Subtract the SPL shortfall:

| Stimulus | Approx SPL | Expected peak, dB FS | Expected `peak` |
| --- | --- | --- | --- |
| Talking into the port, a few cm | 85 | -35 | ~550 |
| Normal speech at 30 cm | 70 | -50 | ~100 |
| Normal speech at 1 m | 60 | -60 | ~33 |
| Datasheet noise floor, RMS A-weighted | | -90 | ~1 |

A level more than 15 dB under the matching row is an acoustic fault, not a config fault. On 2026-08-24 the board read -56 dB FS with a voice at the port, about 21 dB short. That held across every combination of sample rate, `gain_factor`, and pull-down. Firmware cannot recover that.

## What is already ruled out

Do not test these again. All are measured, and all are negative.

| Suspect | Verdict | Why |
| --- | --- | --- |
| Bit depth | Not a fault | `MicrophoneSource::process_audio_` converts 32 to 16 by itself |
| Sample rate and mic mode | Not a fault | Both modes are -26 dB FS, Table 3. The modes differ by 1 dBA of SNR |
| `gain_factor` | Cannot correct it | It applies after the mic, so it scales signal and floor together |
| Missing 100k `sd` pull-down | Real defect, not the cause | Bench A/B on 2026-08-24 read 9 to 53 either way. The tristate window lands in the low 8 bits that `>> 16` discards. See `ROADMAP.md` |
| Missing `MK1` 0.1uF decoupling | Real defect, not the cause | Raised 2026-08-25. The nearest `+3.3V` cap is `C1`, 92.75 mm away. It explains about 10 dB of excess floor. It cannot subtract 21 dB of signal. See `ROADMAP.md` |
| Absent acoustic port drill | Ruled out | The drill is in the fab output, checked 2026-08-24. See the inspection section |

No supply fault can be the cause, for three reasons. Sensitivity is flat from 1.65 to 3.63 V. The part is digital, so its output is a fixed-point sample and not an analog level. The button-press transient reads a full -35 dB FS through this same undecoupled supply. Supply noise raises the floor, but it cannot subtract signal.

## Assembly damage is the leading suspect

Three facts support this. The first is our own, and it is the strongest.

First, the fault selects between identical boards. Of five Rev B remotes, one mic works, one works with distortion, and three do not work, measured 2026-08-26. One design, one firmware and one fab batch produced all five results. So the cause is per unit and it is a process or a handling step. This also confirms the two verdicts in the table above rather than reopening them. Every board carries the same missing `sd` pull-down and the same missing 0.1uF cap. So neither defect can separate a working unit from a dead one. The spread also reproduces in-house the graded range the PCBWay report describes below, from excessive noise to no response.

Second, the part has a public failure record with exactly our symptoms. Two people on the ESPHome Discord built their own ICS-43434 boards and got data, correct clocks, and no acoustic response. The first report is from Dwains of SmartHomeShop.io, [in the ESPHome Discord](https://discord.com/channels/429907082951524364/1195816357523103885/1195834560567578644). All three of their boards were PCBWay-assembled, and all three were dead.

They ran a known-good Arduino sketch and ESPHome, measured 3.3 V clean at the pin, and confirmed the PCB port hole was open. After three boards and a week of work they gave up and respun with a different microphone. They also proved the ESP32 and the pins were good by wiring an external INMP441 breakout to the same pins, where it worked. A second person then reported the same failure on a different schematic with different pins.

Both had the 0.1uF decoupling cap that our board lacks, so a missing cap does not separate a working board from a broken one. Note the link needs ESPHome Discord membership to open.

A third report sits on [PCBWay's own site](https://www.pcbway.com/project/question/Noisy_audio_from_ICS_43434.html), and it is the strongest of the three. That builder put several ICS-43434 parts on one ESP32-S3 board, 75 mm apart, and 6 boards out of 10 failed. The symptom is "one of the microphones either produces excessive noise or does not respond at all". The question is still open.

Two details there carry more weight than the raw count. Some microphones fail while others on the same board work. Those parts share one schematic, one firmware, one reflow pass and identical nets, so a design fault cannot select between them. Random failure across identical circuits points at handling or process instead.

The other detail is the shape of the fault. "Excessive noise or no response" describes a range, and electrical faults are binary. Contamination is graded. This board sits in the middle of that range at 21 dB down, and the three Discord boards sat at the dead end. That builder saw both ends inside one batch.

Third, TDK forbids the cleaning steps that a contract assembler runs by default. `AN-100`, the handling guide our datasheet defers to, is blunt on page 2:

> The MEMS microphone package has a port hole opening that is sensitive to solder flux. Do not use a vapor phase soldering process. The MEMS microphone can be damaged if subjected to cleaning processes. The cleaning solvents can enter through the port hole and damage the device.

`AN-100` also says "Do not clean MEMS sensors in ultrasonic baths". Page 18 of `DS-000069` repeats the rule for the board level: "When washing the PCB, ensure that water does not make contact with the microphone port. Do not use blow-off procedures or ultrasonic cleaning."

Every one of those prohibitions maps onto a step that PCBWay describes in its own cleaning article: an ultrasonic bath, a multi-stage deionized water rinse, and compressed air drying. PCBWay also states that its factory "primarily uses rosin-based flux", which is not a no-clean flux and so implies a cleaning step. PCBWay publishes ten assembly stages, but no cleaning policy, no MSL or bake procedure, and no reflow profile. So what happened to this board is unknown rather than documented.

This board is the worst case for that mechanism. The 0.5 mm NPTH is a channel, not an incidental hole. `MK1` sits on `B.Cu` with its port facing up into the board. So the hole runs from the exposed top face straight into the acoustic port, and the package seals the far end. The result is a blind cavity. Liquid that enters from the top cannot drain and cannot air-dry, and dried residue leaves a permanent acoustic restriction. That fits a mic 21 dB down better than it fits a dead one. The Discord boards that were fully dead fit the same mechanism at a larger dose.

Two gaps worth closing. `AN-100` Table 2 predates the ICS-43434, and neither that table nor `DS-000069` gives this part an MSL rating, so the correct bake procedure is unknown. And the peak reflow limit is 260°C for a part under 1.6 mm thick. Nothing in this repo has checked that against a real vendor profile.

## Next-revision microphone candidates

| Candidate | Interface and ESPHome | Package and process | Decision |
| --- | --- | --- | --- |
| `ICS-43434` | I²S works on ESP32-C6 at 16 or 48 kHz | Bottom port, 3.5 x 2.65 mm, no wash | Keep only with controlled assembly and acoustic testing |
| `DMM-4026-B-I2S-R` | I²S works on ESP32-C6 at 48 kHz | Bottom port, 4.0 x 3.0 mm, seven pads, MSL1 | Electrical candidate, but it keeps the blind cavity |
| `SPH0645LM4H-B` | I²S works on ESP32-C6 | Bottom port, 3.5 x 2.65 mm, MSL1 | Reject because the part is obsolete |
| Top-port PDM microphone | ESPHome supports PDM only on ESP32 and ESP32-S3 | Top port removes the PCB acoustic hole | Requires a move from ESP32-C6 to ESP32-S3 |

The `DMM-4026-B-I2S-R` requires 24-bit data in 32-bit words. Its 18-bit precision does not change the ESPHome configuration.

Set ESPHome to `sample_rate: 48000`, `bits_per_sample: 32bit`, and `pdm: false`. This setting produces the required 3.072 MHz bit clock.

Tie `CONFIG` and `LR` to ground for left-channel operation. Fit 0.1 uF from VDD to ground and 100 kOhm from SD to ground.

Do not reuse the ICS-43434 footprint. The `DMM-4026-B-I2S-R` uses a different body, land pattern, pin count, and acoustic-port position.

## Firmware-independent test

The standalone ESP-IDF test removes ESPHome, Wi-Fi, voice assistant, LED, and meter logic. Source and wiring are in [`firmware/mic-test-idf/README.md`](../firmware/mic-test-idf/README.md).

From the repository root, with the managed PlatformIO Core:

```sh
cd firmware/mic-test-idf
~/.platformio/penv/bin/pio run
~/.platformio/penv/bin/pio run -t upload --upload-port /dev/cu.usbmodem2101
~/.platformio/penv/bin/pio device monitor --port /dev/cu.usbmodem2101 --baud 115200
```

Replace the serial device after you run `ls /dev/cu.usbmodem*`. The test reports one line per second:

```text
bytes=65536 samples=16384 peak24=18420 rms=1260.4 dbfs=-76.46 zeros=3 min=-17211 max=18420
```

Each line reports `4 * fs` bytes and `fs` samples, with nonzero noise and few zero samples. On the tested Rev B board, idle was `peak24` 2,000 to 5,000, RMS 600 to 900, and `dbfs` -80 to -81. This is a baseline, not a pass/fail spec.

The firmware runs 48 kHz, High-Performance mode, by default. The boot line reports the active mode. Set `MIC_SAMPLE_RATE_HZ` to 16000 to match what `c6remote.yaml` ships, because the ESPHome voice assistant needs 16 kHz and so always runs Low-Power.

That idle floor of -80 sits about 10 dB over the datasheet -90. The missing decoupling cap and a 92 mm unfiltered supply run account for it. This is excess noise, and it is separate from the 21 dB signal deficit.

### Listen to it

The same firmware dumps a 2 second WAV every cycle. That settles what a meter cannot: speech, hum, clipping, or one settling ramp. Run the host reader while the firmware loops, per [`../scripts/mic-capture.md`](../scripts/mic-capture.md):

```sh
python3 scripts/capture_usb_pcm.py /dev/cu.usbmodem2101 mic.wav
```

Read the level from the device `capture done: peak24=... dbfs true` line, not from the WAV. The file is scaled 24 dB above unity so a quiet board is audible, so the WAV overstates the mic by that much.

The C6 has only the fixed-function USB Serial/JTAG, no USB-OTG, and this board has no SD slot. So it cannot present a USB drive or a USB audio device. Audio leaves over the serial link or through `esptool read_flash`, and no other way.

## Apply stimulus and interpret result

1. Start the monitor. Let idle values settle for several lines.
2. Speak close to, or gently blow across, the front-side acoustic hole.
3. Tap the PCB near the hole, not the mic package backside.
4. Compare `peak24` and `rms` under stimulus against idle.

Interpretation:

- Bytes and samples near target, `zeros` far under `samples`: clocks, DMA, and SD are active.
- `zeros == samples`: examine power, GPIO mapping, I2S mode, and SD continuity. The mic can be in standby without a valid clock.
- A clear rise above idle: the digital path works. Remaining work is calibration, placement, or enclosure acoustics.
- Readings near idle, under `peak24` 5,000 and about -80 dBFS: suspect a blocked port, assembly residue, a damaged port, or a dead mic. A close tap or voice must cause a large relative change, even though absolute values depend on distance and enclosure.
- A slow monotonic climb, in place of a spike per word, does not track your voice. Speech is bursty: peaks jump on syllables and drop between them. A smooth ramp over ten or more seconds is a leakage or settling path, not a poor port. It appeared twice on 2026-08-24, from 11 to 53.

Do not read sound level from `bytes/s`. It measures transport rate, not acoustic amplitude.

## Safe physical inspection

Inspect the front NPTH with magnification and backlight. Make sure it is open through the board, and not covered by solder, flux, adhesive, case material, or debris. Use only gentle air across the opening.

CAUTION: Do not put probes or wire into the mic port. Do not use high-pressure air or solvent on the mic. Each of these destroys the diaphragm.

Rule out two things before you blame the hole. The port is a through-hole and `MK1` sits on `B.Cu`, so the package seals the bottom end. The only open face is the top, and sound must enter there. A board on a desk, foam, or a misaligned case floor seals that face, so hold it in free air.

The drill is in the fab output, checked 2026-08-24: `export/c6remote.drl` tool `T5C0.500`, tagged `NonPlated,NPTH,ComponentDrill`, one hit at `X53.35 Y-31.582`. So a blocked port on an assembled board is residue, not a missing hole.

## Restore ESPHome

After a test, from the repository root, reflash the normal config:

```sh
esphome run c6remote.yaml --device /dev/cu.usbmodem2101
```

Then press `Start Microphone Test` before you judge ESPHome capture logs. Recheck the serial device if reset changes it.
