# IR receiver mode plan

## Goal

Add a local mode that learns IR codes from another remote.

Store each learned code in flash. Send the stored code when the user presses its assigned button.

Keep the current short-press action for `SW2`. Enter receiver mode when the user holds `SW2` for two seconds.

## Assumptions

- Use `SW3` through `SW11` as assignable buttons.
- Preserve the current voice action on `SW1`.
- Reserve `SW2` for push-to-talk and receiver mode control.
- Store one IR code for each assignable button.
- Replace the old code when the user learns a new code for the same button.
- Learn common decoded protocols when ESPHome identifies them.
- Store raw pulse timings when ESPHome cannot identify the protocol.
- Keep all learning and playback functions local. Home Assistant must not be necessary.

## User sequence

1. Hold `SW2` for two seconds.
2. Release `SW2` when all four LEDs show the ready state.
3. Press one assignable button.
4. Point the source remote at `U2`.
5. Press the source remote button once.
6. Wait for the read state.
7. Press another assignable button to learn another code.
8. Press `SW2` to leave receiver mode.

The mode will close after 30 seconds without input. A successful read will restart this timeout.

Outside receiver mode, an assignable button will send its stored code. A button without a code will give an error indication.

## State model

Use one `IrLearnState` value as the source of truth.

| State | Meaning | `D2`-`D5` indication | Exit |
| --- | --- | --- | --- |
| `OFF` | Normal remote operation | Existing status behavior | Hold `SW2` |
| `READY` | Receiver is on and waits for a target button | Four solid blue LEDs | Press a target button |
| `READING` | Receiver waits for the source remote | Blue chase toward `D5` | Receive a frame or reach ten seconds |
| `READ` | Code passed validation and reached flash | Four solid green LEDs for one second | Return to `READY` |
| `ERROR` | Read, validation, or storage failed | Four red flashes | Return to `READY` |

Turn on `ir_rail` before the `READY` indication. Wait 10 ms before the receiver accepts frames.

Turn off `ir_rail` when the mode closes. Keep it on during playback only for receiver-mode diagnostics.

The current configuration uses `restore_mode: ALWAYS_ON` for `ir_rail`. Change it to `ALWAYS_OFF` with this feature.

## Button behavior

Add click and hold handling to `SW2`.

- A release before two seconds keeps the current push-to-talk action.
- A hold of two seconds enters receiver mode and suppresses push-to-talk.
- A short press in receiver mode closes receiver mode.

Do not start voice capture on the initial `SW2` edge. Start it only after the hold window closes.

This change adds a two-second delay to push-to-talk. If that delay is unacceptable, use a different entry gesture.

In `READY`, the next assignable button becomes the target. Do not transmit its existing code in this state.

In `READING`, ignore assignable button presses. Let `SW2` cancel the operation and close the mode.

In `OFF`, send the stored code on the assignable button press. Ignore button release for IR playback.

## Capture rules

Disable the current unrestricted `dump: all` log in production. Route received frames to one learning handler.

Accept only the first complete frame after the target selection. Ignore repeat-only frames and receiver noise.

For decoded frames, store these fields:

- Format version
- Target button number
- Protocol identifier
- Address and command data
- Protocol bit count or required protocol metadata
- Carrier frequency when the protocol requires it
- Checksum for the record

For unknown protocols, store normalized mark and space durations. Store the carrier frequency as `38 kHz` by default.

Set explicit limits for raw captures:

- Maximum pulse count: 512
- Maximum frame duration: 250 ms
- Minimum pulse duration: 80 microseconds
- Capture timeout: 10 seconds

Reject an empty, truncated, oversized, or repeat-only capture. Keep the previous code after any rejected capture.

## Storage design

Use one ESPHome flash preference record for each assignable button.

Each record contains a magic value, schema version, pulse count, pulse data, and checksum.

Write the new record before you replace the active in-memory record.

Load and validate each record during boot. Ignore a damaged record and keep that button unassigned.

Limit writes to successful learning events. Do not write during playback, boot, timeout, or cancellation.

Add an exposed action that erases one assignment. Add a separate action that erases all assignments.

## Firmware structure

Keep YAML automations small. Put capture, serialization, validation, and playback logic in a C++ include.

Add these parts:

- `IrCodeStore` for LittleFS load and atomic replacement
- `IrLearner` for state, timeout, target selection, and capture
- `IrCode` as the decoded-or-raw record type
- One playback method that selects the correct ESPHome transmitter call
- One LED renderer that owns `D2`-`D5` while receiver mode is active

The receiver-mode renderer must override `Status Indicators` and `Voice Listening`. Restore idle status after mode exit.

Guard learning state with one execution context. Copy a completed capture before any file operation starts.

Log state changes, target buttons, protocol names, pulse counts, and storage results. Do not log every pulse by default.

## Implementation order

1. Add tests for `SW2` hold detection and push-to-talk suppression.
2. Add the state model and receiver-mode LED effect.
3. Change `ir_rail` to default off and control it from mode entry and exit.
4. Add target-button selection without storage or playback.
5. Add decoded protocol capture and playback for the protocols ESPHome supports.
6. Add bounded raw capture and raw playback.
7. Add LittleFS serialization, CRC validation, and atomic replacement.
8. Load assignments during boot and connect normal button presses to playback.
9. Add erase actions, timeouts, cancellation, and error indications.
10. Run automated configuration tests and complete hardware validation.

## Automated checks

Extend `scripts/tests/test_c6remote_config.py` with these checks:

- `SW2` short press still starts push-to-talk.
- `SW2` hold enters receiver mode only once.
- Receiver mode suppresses voice capture.
- Each assignable button selects a target in `READY`.
- Each assignable button transmits only in `OFF`.
- `ir_rail` defaults off and follows receiver-mode transitions.
- The receiver-mode LED effect controls all four LEDs.
- Every capture limit has a fixed constant.
- A failed write preserves the previous assignment.

Add tests for the C++ storage format. Cover valid records, bad checksums, invalid lengths, and unknown schema versions.

Run `esphome config c6remote.yaml`. Compile the firmware after configuration validation passes.

## Hardware validation

Test one decoded NEC remote and one remote that requires raw storage.

For each test, power-cycle the board after learning. Confirm that the assigned button still controls the target device.

Verify these cases:

- A short `SW2` press still controls push-to-talk.
- A two-second `SW2` hold does not start voice capture.
- `D2`-`D5` show `READY`, `READING`, `READ`, and `ERROR` correctly.
- Noise does not overwrite a stored code.
- A repeat frame does not become a stored code.
- A failed capture preserves the previous code.
- Relearning a button replaces only that button.
- Mode timeout turns off `ir_rail` and restores idle LEDs.
- Playback does not leave the transmitter or LED rail active.
- Fifty repeated learning operations do not corrupt the file.

Measure idle current before and after the `ir_rail` default changes. Confirm that `GPIO16` does not partially power an inactive receiver.

## Completion criteria

Complete the feature when all assignable buttons can learn, retain, and replay both test remotes.

The feature must recover safely from invalid storage, capture timeout, cancellation, and power loss during a write.

The existing voice assistant, status LEDs, Wi-Fi status, and IR test action must continue to work.
