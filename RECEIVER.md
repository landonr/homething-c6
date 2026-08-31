# Assignment mode

## Goal

Assignment mode gives each supported input one active action. An action can be
an IR code, a Zigbee Toggle group, the voice assistant, or no action.

Store assignments in flash. Outside assignment mode, an input replays its active
action.

## Enter and leave the mode

Hold `SW2` for two seconds to enter assignment mode. Hold `SW2` for two seconds
again to leave it.

The ready state closes after five seconds without an input. The Zigbee training
state waits for 60 seconds.

A tap during Zigbee training stops that wait. The tap then moves the cycle
forward. You do not need to wait out the full training timeout.

The release that ends an `SW2` hold does not count as a tap.

## Assignment cycle

For `SW1`, `SW3` through `SW11`, and the five wheel directions, tap the same
input in this order:

1. First tap: train an IR code.
2. Second tap: train a Zigbee Toggle group.
3. Third tap: assign the voice assistant.
4. Fourth tap: clear the input.

For `SW2`, tap the same input in this order:

1. First tap: train an IR code.
2. Second tap: train a Zigbee Toggle group.
3. Third tap: clear the input.

`SW2` has no voice stage because its hold gesture controls assignment mode.

Clockwise and anticlockwise wheel rotation are IR-only. Each detent starts IR
training. Rotation has no Zigbee, voice, or clear stage because it has no release
edge.

A tap on a different supported input always starts at the IR stage for that
input.

## IR training

After the first tap, point the source remote at `U2` and press its button once.
The remote accepts the first complete frame and stores it as raw pulse data.

The remote rejects empty, truncated, oversized, and repeat-only frames. A failed
capture does not replace the old assignment.

## Zigbee training

After the second tap, the input waits for an allowed Zigbee2MQTT target
transition. Change the target from `ON` to `OFF`, or from `OFF` to `ON`, within
60 seconds.

A wall switch target needs a walk to the switch, so the window is 60 seconds.

Read [ZIGBEE.md](ZIGBEE.md) before Zigbee training. Zigbee2MQTT, its MQTT broker,
and working Wi-Fi are required only for this step.

The remote uses an existing target group directly. For an individual device, it
creates a reserved group and adds the device. It stores the assignment after
Zigbee2MQTT confirms all required requests.

Outside assignment mode, a trained input sends a direct Zigbee Toggle command.
It does not need MQTT or Wi-Fi for playback.

## Clear and replace an assignment

An IR, Zigbee, or voice assignment replaces the previous action for that input.
The remote never keeps two active actions on one input.

The clear tap removes the local assignment. For a device assignment, it also
asks Zigbee2MQTT to remove the old member when MQTT is connected. It does not
change an existing target group.

If training fails, the old assignment remains. If the old group member was
removed, the remote requests a rollback. A failed rollback leaves the mode in
the error state and needs Zigbee2MQTT repair.

A failed Zigbee training keeps the cycle position. The next tap moves to the
voice stage or the clear stage. A failure does not start a second training wait.

## Web configurator

The device serves a button page at `http://homething-c6.local/buttons`. It uses
the same `web_server` as the ESPHome dashboard on port 80.

The page draws the remote layout: the two top buttons, the wheel, and the nine
keypad buttons.

Select an input. The page shows the current assignment and the actions that the
input accepts.

The page is an alternative to the tap cycle, not a replacement. Both routes write
the same flash records.

### Assign a Zigbee target from the page

The page can assign a Zigbee Toggle target. It does not need a state transition,
because you name the target instead.

1. Select an input, then select **Zigbee**.
2. Select a group in the list.
3. Or type a group ID, an IEEE address, or a friendly name.
4. Select **Assign**.

The list shows groups only. You must type a device target as an IEEE address or
a friendly name.

The retained `bridge/devices` payload is too large for the device memory, so the
remote does not subscribe to it.

A typed target wins over the list selection. The list comes from
`GET /buttons/api/zigbee_targets`.

The remote fills that list from the retained `bridge/groups` topic.

If the list reports that it is not ready, the page shows "Waiting for
Zigbee2MQTT". Wait for MQTT and for the retained group topic.

A group target is stored at once. A device target needs the same Zigbee2MQTT
group requests as the tap cycle, so the page shows a progress bar.

Select **Cancel** during that wait. The remote then rolls the group membership
back, as it does for a cancelled tap-cycle training.

Read [ZIGBEE.md](ZIGBEE.md) for the accepted target formats.

### Capability matrix

| Input | Slots | Record IR | Zigbee target | Voice assistant | Clear |
| --- | --- | --- | --- | --- | --- |
| `SW1` | 20 | Yes | Yes | Yes | Yes |
| `SW2` | 19 | Yes | Yes | No | Yes |
| `SW3` to `SW11` | 3 to 11 | Yes | Yes | Yes | Yes |
| Wheel directions | 12 to 16 | Yes | Yes | Yes | Yes |
| Wheel rotation | 17 and 18 | Yes | Yes | No | Yes |

Every slot accepts a Zigbee target. Toggle playback uses the same press handler
as IR playback, so a wheel detent can send it.

`SW2` has no voice action because the hold gesture owns its press edge.

Wheel rotation has no voice action because a detent has no release edge to end
push-to-talk.

The page hides the voice button on those three slots. The firmware checks the
same rule again on each request.

A voice request for slot 17, 18, or 19 gets HTTP 400 and changes nothing.

### One operation at a time

The remote runs one assignment operation at a time. The page polls
`/buttons/api/state` for the current owner.

If the remote owns the operation, the page disables its action buttons. The
notice reads "Assignment in progress on the remote."

If a second browser owns the operation, the notice reads "Another assignment is
already running."

A request that arrives during an operation gets HTTP 409. The remote keeps its
current operation.

A Zigbee assignment holds the same lock. The tap cycle refuses a Zigbee training
while a page assignment runs, and the page refuses the reverse.

A web operation looks like a local one on the remote. `D3` and `D4` show the same
ready state and IR training state.

The remote gesture stays active during a web operation. A tap on the remote can
move the capture to another input.

### A failed or cancelled capture

The store keeps the previous assignment after a failed capture. A rejected frame
writes nothing to flash.

Cancel gives the same result. The page sends the `cancel` action and the remote
closes assignment mode.

If no frame arrives, the capture times out. The page then reports "No code
received" and the old assignment remains.

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

The `/buttons` page and its three endpoints have no authentication. The
`web_server`, `api`, and `ota` components on this device have none either.

This is a deliberate choice for a trusted home network. Any device on that
network can change an assignment.

Do not expose port 80 of the remote to the internet. If the network is not
trusted, add `web_server` authentication.

## LED meanings

Assignment mode uses `D3` and `D4` only. `D2` keeps the connection state, and
`D5` keeps the Zigbee state. A connection fault stays visible during training.

`D2` shows the transports that Zigbee training needs:

| `D2` | Meaning |
| --- | --- |
| Red pulse | Wi-Fi is down. Training is not possible. |
| Orange pulse | Wi-Fi is up, but the API is down. |
| Cyan pulse | The API is up, but MQTT is down. Training is not possible. |
| Solid green | Wi-Fi, the API, and MQTT are all up. Training is possible. |

Green means that training can run. Train only on solid green.

| State | `D3` and `D4` indication | Next action |
| --- | --- | --- |
| Ready | Solid blue | Select an input. |
| IR training | Blue chase | Send one IR frame. |
| Zigbee training | Yellow pulse | Change one target state. |
| Saved | Solid green for one second | Continue or leave. |
| Error | Red flashes | Retry or leave. |
| Voice | Blue pulse | Tap again to clear. |
| Cleared | Amber for one second | Select an input. |

`D3` and `D4` show voice-assistant state when assignment mode is closed. See
[ZIGBEE.md](ZIGBEE.md) for the `D5` Zigbee meanings.

## Normal playback

Outside assignment mode, an input uses its one active assignment in this order:

1. Voice assistant, if assigned.
2. Zigbee Toggle, if assigned.
3. IR playback, if assigned.

An input without an assignment does not transmit a command.
