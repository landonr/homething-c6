# Assignment mode

## Goal

Assignment mode gives each supported input one active action. An action can be
an IR code, a Zigbee command, a BLE HID control, the voice assistant, or no action.

Store assignments in flash. Outside assignment mode, an input replays its active
action.

## Enter and leave the mode

Hold `SW2` for two seconds to enter assignment mode. Hold `SW2` for two seconds
again to leave it.

The ready state closes after five seconds without an input.

The release that ends an `SW2` hold does not count as a tap.

## Assignment cycle

For `SW1`, `SW3` through `SW11`, and the five wheel directions, tap the same
input in this order:

1. First tap: train an IR code.
2. Second tap: assign the voice assistant.
3. Third tap: clear the input.

For `SW2`, tap the same input in this order:

1. First tap: train an IR code.
2. Second tap: clear the input.

`SW2` has no voice stage because its hold gesture controls assignment mode.

The cycle has no Zigbee stage. A Zigbee target comes from Zigbee2MQTT, which
the remote cannot read, so only the web page assigns one.

Clockwise and anticlockwise wheel rotation are IR-only. Each detent starts IR
training. Rotation has no voice or clear stage because it has no release edge.

A tap on a different supported input always starts at the IR stage for that
input.

## IR training

After the first tap, point the source remote at `U2` and press its button once.
The remote accepts the first complete frame and stores it as raw pulse data.

The remote rejects empty, truncated, oversized, and repeat-only frames. A failed
capture does not replace the old assignment.

## Zigbee assignment

Assign a Zigbee target from the web page. Read [ZIGBEE.md](ZIGBEE.md) first,
because you must create a group in Zigbee2MQTT before the remote can use it.

Outside assignment mode, an assigned input sends its one Zigbee command to its
target. Playback needs no MQTT and no Wi-Fi.

## Clear and replace an assignment

An IR, Zigbee, BLE HID, or voice assignment replaces the previous action for that input.
The remote never keeps two active actions on one input.

The clear tap removes the local assignment. Group membership stays in
Zigbee2MQTT, because the group belongs to the network, not to the button.

If an IR capture fails, the old assignment remains.

## Web configurator

The device serves a button page at `http://homething-c6.local/buttons`. It uses
the same `web_server` as the ESPHome dashboard on port 80.

The page draws the remote layout: the two top buttons, the wheel, and the nine
keypad buttons.

Select an input. The page shows the current assignment, then an **Action**
selector with the actions that the input accepts.

The selector holds IR code, Zigbee target, BLE HID, Voice assistant, and Clear. It opens
on the action that the input already holds.

The right side of the selected-input title has **Copy** and **Paste** buttons.
Use them to copy an IR code, Zigbee target, or BLE HID configuration between inputs.

Select the source input and select **Copy**. Then select the target input and
select **Paste**. Paste opens the IR or Zigbee panel and fills its configuration
form. Paste does not write an assignment to the remote.

Paste stays available for a Clear or empty input when copied configuration exists.
Select **Apply** for IR or **Assign** for Zigbee and BLE HID to write the configuration.

One panel shows at a time, because an input holds one action. The IR panel owns
the **Record IR** button and the code box.

The page is an alternative to the tap cycle, not a replacement. Both routes write
the same flash records.

### Assign a Zigbee target from the page

The page can assign a Zigbee target and the command that goes to it. It does
not need a state transition, because you name both instead.

1. Select an input, then select **Zigbee target** in the Action selector.
2. On the first use, enter the Zigbee2MQTT frontend websocket address in the
   connection card at the top of the page.
3. Select **Group** or **Device**, then pick a target or type its address.
4. Select the command in the **Action** selector, then fill its value box if it
   shows one.
5. Select **Assign**.

The browser reads the group and device lists from Zigbee2MQTT and sends only the
address, the action and its value to the remote. The address of the frontend and
the token stay in browser storage.

The remote holds no MQTT client, so the retained `bridge/devices` payload that
once exhausted its heap never reaches it.

The **Action** selector lists only the commands the target accepts, which the
page reads from the cluster list of the target. A typed address describes
nothing, so it offers every command.

A device target unicasts to the device, so the browser writes no group for it.

Use a typed address when the browser cannot reach the frontend.

The browser fills the list from the `bridge/groups` message on the Zigbee2MQTT
frontend websocket. If it cannot connect, the page reports the reason and keeps
the typed field usable.

The remote stores the group ID at once, because a group needs no confirmation
from the network.

Read [ZIGBEE.md](ZIGBEE.md) for the accepted group ID formats.

### Assign a BLE HID control from the page

1. Pair the host with `homeThing C6` in its Bluetooth settings.
2. Select an input, then select **BLE HID** in the Action selector.
3. Select Keyboard, Consumer, Gamepad button, or Gamepad D-pad.
4. Select the key from the list. Keyboard and Consumer list the common usages by name.
5. If the usage is not in the list, select **Custom usage** and enter the number.
6. Enter the keyboard modifier mask when applicable.
7. Select **Assign**.

A gamepad button still takes a number. A D-pad still takes a direction.

The remote supports one bonded host. Pairing uses encrypted Secure Connections with Just Works authentication.

The firmware uses the NimBLE host. After the link is encrypted, the remote reads
the host device name from the GAP service, `0x1800`, characteristic `0x2A00`.

The page then names the host. A host that hides that characteristic keeps the
plain connected state.

Flash the first BLE HID build through USB because this build changes the partition table. Later builds can use OTA.

The page shows the connection, bond, and pairing states above the input layout.

The remote sends no HID action while the host is disconnected. It does not queue missed actions.

The remote combines held keyboard keys, keyboard modifiers, and gamepad buttons in their reports.

Each wheel detent sends one short HID press and release.

### Capability matrix

| Input | Slots | Record IR | Zigbee target | BLE HID | Voice assistant | Clear |
| --- | --- | --- | --- | --- | --- | --- |
| `SW1` | 20 | Yes | Page only | Page only | Yes | Yes |
| `SW2` | 19 | Yes | Page only | Page only | No | Yes |
| `SW3` to `SW11` | 3 to 11 | Yes | Page only | Page only | Yes | Yes |
| Wheel directions | 12 to 16 | Yes | Page only | Page only | Yes | Yes |
| Wheel rotation | 17 and 18 | Yes | Page only | Page only | No | Yes |

Every slot accepts a Zigbee target from the page. Zigbee playback uses the same
press handler as IR playback, so a wheel detent can send it. A command that only
makes sense as a pair, such as brighter and dimmer, costs two slots, and the
wheel directions are the natural home for one.

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

### The connection card

The page opens with one connection card. It holds both radio links, side by side
with a rule between them. It sits above the input grid, separate from the import
block. On a narrow screen the two blocks stack.

The **Zigbee2MQTT** block holds the address, the token, and the **Connect**
button. One line under the heading reports the link with a circle:

- A green circle and the group and device counts mean a live link.
- A grey circle means no connection.
- A red circle means that the last connection failed.

The **Bluetooth** block reports the host state the same way. A connected line
reads **connected to** and the host name when the remote could read it. The
block holds the **Forget Bluetooth host** button, which shows only when a bond
exists.

The Zigbee2MQTT inputs are built one time, so a repaint keeps an address that is
still being typed.

### The Import and export card

The **Import and export** card at the bottom of the page moves every assignment
as one block of text.

The card is closed on arrival. The heading is the toggle. It reads **Show** when
the card is closed and **Hide** when the card is open.

### Copy the whole config

The **Import and export** block holds a **Direction** selector, which holds
Export and Import.

The page reads no IR code until the card opens on the Export side. Export reads
the remote and fills the box.

The block holds one entry for each input, with its slot number, its label, and
its action.

An IR entry carries the Flipper `.ir` block itself, so an export restores a
remote without a source remote.

A Zigbee entry carries `kind`, which is `group` or `device`. A group entry holds
`group`. A device entry holds `ieee` and `ep`.

A BLE HID entry carries `kind`, `usage`, and `mod`. Only keyboard entries use `mod`.

The page reads one code at a time from `GET /buttons/api/code`. Select **Read the
remote** to build the block again after a change.

Import checks every entry before the first flash write. If one entry is bad, the
page names the slot and writes nothing.

A valid block writes one input at a time through `POST /buttons/api/action`. The
remote reserves one action at a time, so a burst would take the 409.

An import leaves an input that the block does not name alone. A `none` entry
clears an input, but only if the input holds an action.

The import needs no new endpoint. Both directions use the same three endpoints as
the rest of the page.

### Trusted-LAN warning

The `/buttons` page and its three endpoints have no authentication. The
`web_server`, `api`, and `ota` components on this device have none either.

This is a deliberate choice for a trusted home network. Any device on that
network can change an assignment.

Do not expose port 80 of the remote to the internet. If the network is not
trusted, add `web_server` authentication.

## LED meanings

Assignment mode uses `D3` and `D4` only. `D2` keeps the connection state, and
`D5` keeps the Zigbee state. A connection fault stays visible during a capture.

`D2` shows Wi-Fi and the API:

| `D2` | Meaning |
| --- | --- |
| Red pulse | Wi-Fi is down. |
| Orange pulse | Wi-Fi is up, but the API is down. |
| Solid green | Wi-Fi and the API are both up. |

Wi-Fi serves the `/buttons` page only. A dark `D2` does not stop a button,
because IR and Zigbee playback need neither Wi-Fi nor the API.

| State | `D3` and `D4` indication | Next action |
| --- | --- | --- |
| Ready | Solid blue | Select an input. |
| IR training | Blue chase | Send one IR frame. |
| Saved | Solid green for one second | Continue or leave. |
| Error | Red flashes | Retry or leave. |
| Voice | Blue pulse | Tap again to clear. |
| Cleared | Amber for one second | Select an input. |

`D3` and `D4` show voice-assistant state when assignment mode is closed. See
[ZIGBEE.md](ZIGBEE.md) for the `D5` Zigbee meanings.

## Normal playback

Outside assignment mode, an input uses its one active assignment in this order:

1. Voice assistant, if assigned.
2. BLE HID, if assigned.
3. The Zigbee command, if assigned.
4. IR playback, if assigned.

An input without an assignment does not transmit a command.
