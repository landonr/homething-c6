# V3 microphone plan

## Constraint

V3 uses the PUI Audio `DMM-4026-B-I2S-R` microphone.

The microphone needs a clock from 2.048 MHz to 4.096 MHz in normal mode.

ESPHome produces a 2.048 MHz bit clock when it captures 32-bit I2S audio at 32 kHz.

ESPHome `voice_assistant` accepts only a 16 kHz microphone source.

Do not connect the 32 kHz hardware source directly to `voice_assistant`.

## Data path

Use this data path:

```text
DMM microphone -> 32 kHz I2S source -> 2:1 resampler -> 16 kHz source -> voice_assistant
```

Apply a low-pass filter before decimation. Do not discard alternate samples without this filter.

Keep frequencies below 8 kHz. The filter prevents higher frequencies from aliasing into the voice band.

Use [ESPHome pull request 9675](https://github.com/esphome/esphome/pull/9675) as the first implementation reference.

The related [feature request 3072](https://github.com/esphome/feature-requests/issues/3072) includes tests and earlier microphone resampling work.

## Configuration split

Keep the shared production configuration independent of the board revision.

Set the physical microphone rate in each branch entrypoint:

- `main` selects the v2 microphone rate of 16 kHz.
- `develop` selects the v3 microphone rate of 32 kHz.

Expose a separate 16 kHz microphone source to `voice_assistant` on v3.

Do not create the branch split until the resampler validates on ESP32-C6.

## Validation

Complete these checks before v3 firmware becomes the production configuration:

1. Confirm that `esphome config c6remote.yaml` accepts both stream formats.
2. Confirm that the I2S bit clock is 2.048 MHz.
3. Measure dropped buffers, task latency, free heap, and stack margin during capture.
4. Compare speech recognition against the v2 16 kHz path.
5. Test tones above 8 kHz and confirm that no strong aliases enter the voice band.
6. Verify microphone meter scaling after the input changes to 32 kHz.
7. Run the complete regression suite.

Keep v2 unchanged until all checks pass.
