# IR receiver mode plan

## Goal

Add a local mode that assigns each input on the board. An input can hold an IR code, the voice assistant, or nothing.

Store each assignment in flash. Replay the assignment when the user presses that input outside the mode.

Enter receiver mode when the user holds `SW2` for two seconds. Leave it on a second hold of `SW2` or after three seconds without input.

## Assumptions

- Use `SW1` through `SW11` and the five ANO wheel directions as assignable inputs.
- Use clockwise and anticlockwise wheel rotation as two more assignable inputs.
- Reserve the `SW2` hold gesture for receiver mode control.
- Store one IR code or one voice assignment for each input.
- Replace the old assignment when the user assigns the same input again.
- Learn common decoded protocols when ESPHome identifies them.
- Store raw pulse timings when ESPHome cannot identify the protocol.
- Keep all learning and playback functions local. Home Assistant must not be necessary.

## User sequence

1. Hold `SW2` for two seconds.
2. Release `SW2` when all four LEDs show the ready state.
3. Tap one input. The LEDs chase and the receiver waits for a code.
4. Point the source remote at `U2` and press the source remote button once.
5. Wait for the read state.
6. Tap the same input a second time to give it the voice assistant instead. The LEDs pulse blue.
7. Tap the same input a third time to clear it. The LEDs go amber and no input stays selected.
8. Tap another input to assign it.
9. Hold `SW2` for two seconds to leave receiver mode.

A tap on a different input always starts that input at the first stage of the cycle.

The ready state closes after three seconds without a tap. Every other state returns to the ready state and restarts this timeout.

Outside receiver mode, an assignable button will send its stored code. A button without a code will give an error indication.

## State model

Use one `IrLearnState` value as the source of truth.

| State | Meaning | `D2`-`D5` indication | Exit |
| --- | --- | --- | --- |
| `OFF` | Normal remote operation | Existing status behavior | Hold `SW2` |
| `READY` | Receiver is on and waits for a target button | Four solid blue LEDs | Press a target button, hold `SW2`, or wait three seconds |
| `READING` | Receiver waits for the source remote | Blue chase toward `D5` | Receive a frame, hold `SW2`, or reach ten seconds |
| `READ` | Code passed validation and reached flash | Four solid green LEDs for one second | Return to `READY` |
| `ERROR` | Read, validation, or storage failed | Four red flashes | Return to `READY` |
| `VOICE` | The input now starts the voice assistant | Four LEDs pulse blue | Tap again, or ten seconds |
| `CLEARED` | The input holds nothing | Four amber LEDs for one second | Return to `READY` |

Turn on `ir_rail` before the `READY` indication. Wait 10 ms before the receiver accepts frames.

Turn off `ir_rail` when the mode closes. Keep it on during playback only for receiver-mode diagnostics.

The current configuration uses `restore_mode: ALWAYS_ON` for `ir_rail`. Change it to `ALWAYS_OFF` with this feature.

## Button behavior

Add click and hold handling to `SW2`.

- A hold of two seconds from `OFF` enters receiver mode.
- A hold of two seconds in any learn state closes receiver mode.
- A release before two seconds is a short press.
- A short press in the mode runs the assignment cycle for `SW2`.
- A short press in `OFF` sends the code stored for `SW2`.

Ignore the release that ends a hold. That release must not count as a short press.

`SW2` has no voice stage. Push-to-talk needs the press edge, and the hold gesture already owns that edge.

Wheel rotation has no voice stage and no clear stage. A detent has no release edge, so each detent arms a capture.

In `READY`, the next tap selects the target. Do not transmit its existing code in this state.

In `READING`, ignore assignable button presses. Let a hold of `SW2` cancel the operation and close the mode.

In `OFF`, send the stored code on the assignable button press. Ignore button release for IR playback.

## Web configurator

The device serves a button page at `http://homething-c6.local/buttons`. It uses the same `web_server` as the ESPHome dashboard on port 80.

The page draws the remote layout: the two top buttons, the wheel, and the nine keypad buttons.

Select an input. The page shows the current assignment and the actions that the input accepts.

The page is an alternative to the three-tap gesture, not a replacement. Both routes write the same flash records.

### Capability matrix

| Input | Slots | Record IR | Voice assistant | Clear |
| --- | --- | --- | --- | --- |
| `SW1` | 20 | Yes | Yes | Yes |
| `SW2` | 19 | Yes | No | Yes |
| `SW3` to `SW11` | 3 to 11 | Yes | Yes | Yes |
| Wheel directions | 12 to 16 | Yes | Yes | Yes |
| Wheel rotation | 17 and 18 | Yes | No | Yes |

`SW2` has no voice action because the hold gesture owns its press edge.

Wheel rotation has no voice action because a detent has no release edge to end push-to-talk.

The page hides the voice button on those three slots. The firmware checks the same rule again on each request.

A voice request for slot 17, 18, or 19 gets HTTP 400 and changes nothing.

### One operation at a time

The remote runs one assignment operation at a time. The page polls `/buttons/api/state` for the current owner.

If the remote owns the operation, the page disables its action buttons. The notice reads "Assignment in progress on the remote."

If a second browser owns the operation, the notice reads "Another assignment is already running."

A request that arrives during an operation gets HTTP 409. The remote keeps its current operation.

A web operation looks like a local one on the remote. The LEDs show the same ready and read states.

The remote gesture stays active during a web operation. A tap on the remote can move the capture to another input.

### A failed or cancelled capture

The store keeps the previous assignment after a failed capture. A rejected frame writes nothing to flash.

Cancel gives the same result. The page sends the `cancel` action and the remote closes receiver mode.

If no frame arrives, the capture times out. The page then reports "No code received" and the old assignment remains.

To replace an assignment, record again or select a different action.

### Copy a code by text

Each input has an "IR code" box on the page. The box holds one Flipper `.ir` signal block.

`GET /buttons/api/code?slot=<n>` returns that block. The Apply button posts it back as the `code` field.

A Samsung32 frame prints as a parsed block:

```
name: Power
type: parsed
protocol: Samsung32
address: 07 00 00 00
command: E6 00 00 00
```

Every other frame prints as a raw block with `frequency`, `duty_cycle`, and a `data` line of durations in microseconds.

The `name` line names the code. The page shows that name on the input tile.

A paste can hold a whole Flipper-IRDB file. The parser reads the first signal and ignores the rest.

The parser also accepts a bare list of signed microsecond values, which is the format that earlier builds copied out.

The board transmits at 38 kHz with 50 percent duty, so it ignores the `frequency` and `duty_cycle` lines of a pasted block.

### Trusted-LAN warning

The `/buttons` page and its two endpoints have no authentication. The `web_server`, `api`, and `ota` components on this device have none either.

This is a deliberate choice for a trusted home network. Any device on that network can change an assignment.

Do not expose port 80 of the remote to the internet. If the network is not trusted, add `web_server` authentication.

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

The store holds 18 slots. Slots 3 to 11 are `SW3` to `SW11`. Slots 12 to 16 are the wheel directions right, up, press, down, and left. Slot 17 is clockwise rotation and slot 18 is anticlockwise rotation. Slot 19 is `SW2` and slot 20 is `SW1`.

The key of a record is `0x49524330` plus the slot offset. `SW1` and `SW2` use the top slots because a lower first slot would shift every existing key.

Store the voice assignments as one bitmask under key `0x49524356`, one bit per slot offset. Seed the `SW1` bit when the key is absent, so a new board has an Assist button before anyone opens the mode. Do not seed again once the key exists.

A voice assignment and an IR code cannot both apply. Each write clears the other.

An erase writes a zeroed record. The record then fails validation on the next boot.

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

1. Add tests for `SW2` hold detection and short-press detection.
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

- Every assignable input calls the tap handler with the correct slot.
- `SW2` hold enters receiver mode only once.
- The release that ends a hold does not count as a short press.
- `READY` closes after three seconds without a tap.
- `SW2` and wheel rotation pass a tap mode without the voice stage.
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

- A short `SW2` press learns and sends the code in slot 19.
- A two-second `SW2` hold enters and leaves receiver mode.
- The five wheel directions and both rotation directions learn and send.
- A second tap assigns the voice assistant and the LEDs pulse blue.
- A third tap clears the input and the LEDs go amber.
- A voice assignment survives a power cycle.
- `SW1` starts Assist on a board with an empty NVS.
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
