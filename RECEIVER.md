# Assignment mode

## Goal

Assignment mode gives each supported input one active action. An action can be
an IR code, a Zigbee command, a BLE HID control, a Home Assistant action, the voice assistant, or no action.

Store assignments in flash. Outside assignment mode, an input replays its active
action.

## Enter and leave the mode

Hold `SW1` for two seconds to enter assignment mode. Hold `SW1` for two seconds
again to leave it.

The ready state closes after five seconds without an input.

The release that ends an `SW1` hold does not count as a tap.

## Assignment cycle

For `SW2`, `SW3` through `SW11`, and the five wheel directions, tap the same
input in this order:

1. First tap: train an IR code.
2. Second tap: assign the voice assistant.
3. Third tap: clear the input.

For `SW1`, tap the same input in this order:

1. First tap: train an IR code.
2. Second tap: clear the input.

`SW1` has no voice stage because its hold gesture controls assignment mode.

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

## Home Assistant actions

A slot can hold one Home Assistant action. The action has an entity ID, a kind, and an action.
You assign it from the web page. The tap cycle cannot assign it.

The remote sends the action over the ESPHome native API. The remote stores no Home Assistant token.

In Home Assistant, open the ESPHome integration options for this device.
Turn on **Allow the device to perform Home Assistant actions**. If this option is off, Home Assistant ignores the request.

### The Home Assistant switch

The **Home Assistant** switch on the Config tab controls the Home Assistant actions and the API server.

If you turn the switch off, the Home Assistant buttons stop at once.
A press sends nothing, does not turn on Wi-Fi, and does not blink `D2`. The log shows one line for each press.
The remote also drops the actions in the queue and ends the [Wi-Fi lease](#wi-fi-lease).

The API server starts only at boot and has no stop. As a result, it runs until the next restart.
After that restart, the API server does not start, and Home Assistant cannot connect to the remote.
The ESPHome network log also uses the API server. While it is off, read the log over USB. OTA updates do not use it.

Home Assistant shows the switch as the **Home Assistant API** entity. Home Assistant can turn the switch off.
After the next restart, Home Assistant cannot reach the remote, so it cannot turn the switch on again.
To turn the switch on, use the `/buttons` page. Then select **Restart**.

If you turn the switch on in a boot that started with the switch off, the buttons stay off.
They start after the next restart, together with the API server.

The Home Assistant line on the Config tab tells you when the switch and the API server do not agree:

| Line | Cause |
| --- | --- |
| **Home Assistant is off. Home Assistant buttons are disabled. The API stops at the next restart.** | The switch is off, but the API server runs until the next restart. |
| **Home Assistant is on. The API is off. Restart the remote to start it.** | The switch is on, but it was off at boot. |

An input that holds a Home Assistant action keeps the action while the switch is off.
The tile shows the action in grey with a red circle, and the editor gives the reason.

### Kinds and actions

The action tokens are Home Assistant service names.

| Kind | Actions |
| --- | --- |
| Light | `toggle`, `turn_on`, `turn_off`, `brightness_up`, `brightness_down` |
| Switch, Input boolean | `toggle`, `turn_on`, `turn_off` |
| Fan | The switch actions, `increase_speed`, `decrease_speed` |
| Cover | `toggle`, `open_cover`, `close_cover`, `stop_cover` |
| Lock | `lock`, `unlock` |
| Scene | `turn_on` |
| Script | `turn_on`, `toggle` |
| Automation | `trigger`, `toggle` |
| Button, Input button | `press` |
| Media player | `media_play_pause`, `volume_up`, `volume_down`, `media_next_track`, `media_previous_track` |
| Any entity | `homeassistant.toggle`, `homeassistant.turn_on`, `homeassistant.turn_off` |

The Light actions `brightness_up` and `brightness_down` take a step of 1 to 100 percent.
The remote sends them as `light.turn_on` with `brightness_step_pct`.

The entity ID has a maximum of 64 characters. It has lower case letters, digits, underscores, and one dot.
The domain of the entity must match the kind. The kind Any entity accepts an entity of any domain.

### Assign an action from the page

1. Select an input, then select **Home Assistant** in the Action selector.
2. Type the entity ID. The page selects the kind from the domain of the entity.
3. Select the action. For Brighten and Dim, enter the **Step, in percent**.
4. Select **Assign Home Assistant action**.
5. To test the action, select **Test saved action**.

The test queues the saved action and shows the result: ok, error with the Home Assistant message, unconfirmed, timeout, or dropped.
If the Home Assistant switch is off, or the API server is off for this boot, the test fails and shows the reason.
Copy, Paste, export, and import carry Home Assistant assignments.

### Press flow

If the Home Assistant switch is off, a press sends nothing. See [The Home Assistant switch](#the-home-assistant-switch).

A press queues the action. The queue holds a maximum of 8 actions. The remote drops extra presses.

If Wi-Fi is off, the press turns it on. The remote sends the action when Home Assistant has connected and subscribed to actions.
If no client subscribes within 20 seconds, the remote drops the press as a timeout.

The remote waits 5 seconds for a reply. Old Home Assistant versions send no reply.
An integration that does not allow actions also sends no reply. In this case the result is unconfirmed.
After 8 unanswered calls, the remote stops asking for replies until late replies arrive.

The first press after sleep takes a few seconds, because Wi-Fi must connect and Home Assistant must reconnect to the remote.
Presses during the Wi-Fi lease are faster.

### Wi-Fi lease

Wi-Fi stays on while an action waits and for 60 seconds after the last action finished.
Then Wi-Fi turns off, unless the SW9 session, a page session, or Wi-Fi Always On keeps it on.

If you hold SW9 while only the lease holds Wi-Fi, the hold opens a page session.
A page that you use during the lease continues as a page session.

### Failure indication

An error reply or a timeout blinks `D2` red for 2 seconds. The status LED switch still applies.

### Web API

`POST /buttons/api/action` accepts `action=set_ha` with `slot`, `kind`, `act`, `val`, and `entity`.
It also accepts `action=test_ha` with `slot`.

The state has `ha_kind`, `ha_act`, `ha_val`, and `ha_entity` for each slot.
It also has a top-level `ha` object with `pending`, `last_slot`, `last`, and `error`.
`radios.home_assistant` is the switch. `network.api_gated` is true if the switch was off at boot, so the API server did not start.

## Clear and replace an assignment

An IR, Zigbee, BLE HID, Home Assistant, or voice assignment replaces the previous action for that input.
The remote never keeps two active actions on one input.

The clear tap removes the local assignment. Group membership stays in
Zigbee2MQTT, because the group belongs to the network, not to the button.

If an IR capture fails, the old assignment remains.

## Web configurator

The device serves a button page at `http://homething-c6-xxxxxx.local/`. The page also answers at `/buttons`.
`xxxxxx` is the last six hex digits of the remote MAC address. The page uses
the `web_server_base` server on port 80. The production config has no ESPHome `web_server` entity page.

The page title shows the friendly name of the remote, for example `homeThing C6 xxxxxx`.
To change the name, select **Rename** beside the title. Type the name, then select **Save** or press Enter.
To close the box without a change, press Escape or select **Cancel**.

A name can have a maximum of 40 bytes. A character that is not ASCII uses more than one byte.
A name cannot contain a slash or a control character.

Rename changes only the friendly name. The hostname and the page address stay the same.
As a result, the mDNS link and the Home Assistant connection continue to operate.
Home Assistant shows the new name when it next connects. The mDNS record shows it after the next restart.
If you save an empty name, the remote uses its default name again.

The Bluetooth device name is also the friendly name. If no host is connected, the advertisement shows the new name at once.
A paired Bluetooth host can show the old name until it pairs again.
The GAP device name always holds the complete name. The advertisement and the scan response can hold a shortened name.

The page draws the remote layout: the two top buttons, the wheel, and the nine
keypad buttons.

Select an input. The page shows the current assignment, then an **Action**
selector with the actions that the input accepts.

The selector holds IR code, Zigbee target, BLE HID, Home Assistant, Voice assistant, and Clear. It opens
on the action that the input already holds.

If the **Zigbee**, **Bluetooth**, or **Home Assistant** switch on the Config tab is off, the selector grays out the related action.
To assign that action, turn on its switch first. Until then, the selector opens on IR code for an input that holds that action.

The right side of the selected-input title has **Copy** and **Paste** buttons.
Use them to copy an IR code, Zigbee target, BLE HID, or Home Assistant configuration between inputs.

Select the source input and select **Copy**. Then select the target input and
select **Paste**. Paste opens the IR or Zigbee panel and fills its configuration
form. Paste does not write an assignment to the remote.

Paste stays available for a Clear or empty input when copied configuration exists.
Select **Apply** for IR or **Assign** for Zigbee and BLE HID to write the configuration.

One panel shows at a time, because an input holds one action. The IR panel owns
the **Record IR** button and the code box.

The page is an alternative to the tap cycle, not a replacement. Both routes write
the same flash records.

The page also has a **Sleep** block for the deep-sleep settings. See [Deep sleep](#deep-sleep).

The header of the page has a connection line. It shows if the page can read
the remote. If two reads in a row fail, or one read gets no answer in time, the
line turns red and a banner stays at the top of the page. Changes on the page do
not get to the remote while the banner shows. The banner goes away when the
remote answers again.

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

1. Pair the host with the remote in its Bluetooth settings. The remote uses its friendly name, for example `homeThing C6 xxxxxx`.
   While the remote waits for a host, `D4` pulses blue. After the host pairs, `D4` is solid green.
2. Select an input, then select **BLE HID** in the Action selector.
3. Select Keyboard, Consumer, Gamepad button, or Gamepad D-pad.
4. Select the key from the list. Keyboard and Consumer list the common usages by name.
5. If the usage is not in the list, select **Custom usage** and enter the number.
6. Select the modifier keys to hold with the key, when applicable.
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

| Input | Slots | Record IR | Zigbee target | BLE HID | Home Assistant | Voice assistant | Clear |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `SW1` | 20 | Yes | Page only | Page only | Page only | No | Yes |
| `SW2` | 19 | Yes | Page only | Page only | Page only | Yes | Yes |
| `SW3` to `SW11` | 3 to 11 | Yes | Page only | Page only | Page only | Yes | Yes |
| Wheel directions | 12 to 16 | Yes | Page only | Page only | Page only | Yes | Yes |
| Wheel rotation | 17 and 18 | Yes | Page only | Page only | Page only | No | Yes |

Every slot accepts a Zigbee target from the page. Zigbee playback uses the same
press handler as IR playback, so a wheel detent can send it. A command that only
makes sense as a pair, such as brighter and dimmer, costs two slots, and the
wheel directions are the natural home for one.

`SW1` has no voice action because the hold gesture owns its press edge.

Wheel rotation has no voice action because a detent has no release edge to end
push-to-talk.

The page hides the voice button on those three slots. The firmware checks the
same rule again on each request.

A voice request for slot 17, 18, or 20 gets HTTP 400 and changes nothing.

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

Each block keeps every line and every control on the page at all times. A line
that hides moves the text and the buttons under it, so a state is written out
instead. A control that does not apply is disabled, not removed.

The **Zigbee** block starts with the radio switch and its line. The pairing text
and the pairing button come next, with the pairing line to the right of the
button. A rule then separates that from the **Zigbee2MQTT** heading, because the
link below it belongs to this browser.

The **Zigbee2MQTT** part holds the address, the token, the **Connect** button,
and its own line below them.

The line below the address and the token reports the link of this browser, with
a circle:

- A green circle and the group and device counts mean a live link.
- A grey circle means no connection.
- A red circle means that the last connection failed.

The two are independent. This browser can hold a live link while the radio of the
remote is off, so each line says which one it describes.

The Zigbee2MQTT block also reports the coordinator pairing window. The line
reads "Pairing is closed on the coordinator. Permit joining in Zigbee2MQTT." or
"Pairing is open on the coordinator for 2:54." with a live countdown from the
retained `bridge/info` message.

That line is read only. The page publishes nothing to Zigbee2MQTT.

If the socket is down, the line reads "The coordinator pairing state needs the
Zigbee2MQTT link."

The pairing button belongs to the remote and sits above the rule, under the
radio line. It reads **Pair this remote for 3 minutes** and posts to the remote,
which turns its radio on and restarts to open the window. While the window is
open the button reads **Stop pairing** and the line counts the window down.

A join needs both sides. Open the coordinator in Zigbee2MQTT and the remote with
this button. See `ZIGBEE.md` for what a pairing press erases.

The **Bluetooth** block holds two lines. The first names the radio and starts
with **BLE HID: radio on.** or **BLE HID: radio off.** The second names the host
and sits above the Forget text.

An off radio can never read as connected, because the host line drops the link
state with the radio.

The block holds the **Forget Bluetooth host** button. The button is always on the
page and is disabled when no bond exists.

The Zigbee2MQTT inputs are built one time, so a repaint keeps an address that is
still being typed.

### The radio switches

Each block carries an on/off switch on the same line as its heading. The switch
turns that radio off and on for the whole remote.

The Zigbee line reads **Zigbee radio is on.** or **Zigbee radio is off. Zigbee
buttons are disabled.** with a circle. A green circle means that the radio is on
and the remote is on a network. An amber circle means that the radio is on but
the remote is not on a network. A red circle means that the radio is off.

The Bluetooth radio line reads **BLE HID: radio on.** or **BLE HID: radio off.
BLE buttons are disabled.**

The host line below it reads **Connected to bench-mac.**, **Bonded to bench-mac.
Waiting for the host.**, **Bonded to bench-mac.** with the radio off, or **No host
bond.** with **Ready to pair.** while the radio is on.

The remote holds the state, so a reload and a second browser both show what the
remote runs with. The switch is disabled until the remote answers with the state.
Home Assistant holds the same two switches, **Zigbee Radio** and **Bluetooth
Radio**. It also holds the **Home Assistant API** switch. See
[The Home Assistant switch](#the-home-assistant-switch).

An input that is assigned to a radio that is off keeps its assignment. The tile
shows the assignment in grey with a red circle after the label, and the editor
gives the reason. The input sends again when the switch goes back on. A Home
Assistant input with the Home Assistant switch off shows the same marks.

If the Bluetooth switch is off, the remote does not start the NimBLE stack at
boot, and the first turn-on starts it.

The remote stores the host name that it reads from the host, so the line names
the bonded host with the radio off and after a reboot. If the remote never read
the name, the line reads **a saved host**.

**Forget Bluetooth host** works with the radio off. The keys live in flash, in
the `nimble_bond` NVS namespace, so the remote erases them without the stack. A
forget also drops the stored host name. The host must then pair again.

If the Zigbee switch is off, the remote sends no commands. The stack itself keeps
its place on the network only until the next reboot. Read `ZIGBEE.md` for the
reason.

If the switch was off at boot, the remote gates the stack so it never starts.
While the gate holds, the Zigbee line reads **Zigbee radio is on. The stack is
down. Reboot the remote to start it.** Turning the switch back on cannot start
the stack, because the ESP-Zigbee stack has no restart.

Select **Restart** in Home Assistant or on the page to reboot the remote and
lift the gate. Nothing else on the device offers a reboot.

### The Import and export card

The **Import and export** card at the bottom of the page moves every assignment
as one block of text.

The card is closed on arrival. The heading is the toggle. It reads **Show** when
the card is closed and **Hide** when the card is open.

### Copy the whole config

The Config tab shows the current configuration after the page loads.
The Config tab has three sections.
Settings shows the firmware, the battery, the IP address, sleep, the LED settings, and restart.
Connections shows Wi-Fi, Home Assistant, Zigbee, and Bluetooth.
Import Export is the third section.
The page reads each stored IR code in sequence and puts it in the configuration text.
It uses the stored code when you select an input.

The block holds one entry for each input, with its slot number, its label, and
its action.

An IR entry carries the Flipper `.ir` block itself, so an export restores a
remote without a source remote.

A Zigbee entry carries `kind`, which is `group` or `device`. A group entry holds
`group`. A device entry holds `ieee` and `ep`.

A BLE HID entry carries `kind`, `usage`, and `mod`. Only keyboard entries use `mod`.

The block also holds a `firmware` string. It records the firmware build that wrote the file.
The value has the form `YYYY.M.PATCH`. The build computes it at compile time from git.
`YYYY.M` is the month of the latest commit. `PATCH` counts the commits in that month from `VERSION_BASE`.
`VERSION_BASE` is in `components/button_config/__init__.py`. The first commit of a month is `.0`.
A build with uncommitted tracked changes adds `-dirty`.
The value `unknown` means that git is not available or the history does not hold the base commit.
This version is not the board release tag. The release workflow numbers releases separately.
The import ignores `firmware`.

The block also holds a `settings` object with the device settings of the remote:

```json
{"c6remote":1,"settings":{"zigbee":true,"ble":true,"home_assistant":true,
"wifi_always_on":false,"status_leds":true,"boot_leds":true,"sleep":true,"sleep_after_s":300,"wake_replay":false},"slots":[
```

These keys are valid:

- `zigbee`, `ble`, and `home_assistant` turn each radio on or off.
- `wifi_always_on` keeps Wi-Fi on. It takes effect at the next boot.
- `status_leds` turns `D2` to `D5` and the XIAO user LED on or off.
- `boot_leds` turns the cold-boot chase and the wake battery pulses on or off.
- `sleep` turns idle sleep on or off.
- `sleep_after_s` is the idle time before sleep, from 10 to 3600 seconds.
- `wake_replay` makes the press that wakes the remote replay its stored setting.

Each key is optional. If a key is absent, the import leaves that setting as it is.
A file from an older page has no `settings` object, and it still imports.
A remote without sleep does not export the three sleep keys.
If a file holds them, the import skips them and says so in the result note.

The export does not include the friendly name. The name identifies one remote.
If an import copied it, two remotes would have the same name.

The page updates the configuration text after each successful assignment or setting.
If a code read fails, open the Config tab to retry it.
The page does not offer an incomplete current configuration for download.
Your edits and text from a file stay in the box until you apply or replace them.

Import checks every entry and every setting before the first write. If one is
bad, the page names the slot or the key and writes nothing. An unknown key in
`settings` is an error, so a typing mistake cannot pass.

A valid block writes one change at a time through `POST /buttons/api/action`. The
remote reserves one action at a time, so a burst would take the 409.

The import writes the inputs first and then the settings. It sends a setting only
if the remote holds a different value. No setting restarts the remote.

An import leaves an input that the block does not name alone. A `none` entry
clears an input, but only if the input holds an action.

The import needs no new endpoint. Both directions use the same three endpoints as
the rest of the page.

### Trusted-LAN warning

The `/buttons` page and its three endpoints have no authentication. The
`api` and `ota` components on this device have none either.

This is a deliberate choice for a trusted home network. Any device on that
network can change an assignment.

Do not expose port 80 of the remote to the internet. If the network is not
trusted, add authentication to the page.

## LED meanings

After a boot that is not a deep-sleep wake, rainbow pulses go clockwise round
the wheel two times, from `D2` to `D5`. Each pulse overlaps the next. The status
indications then start.

Assignment mode uses `D3` and `D4` only. `D2` keeps the connection state, and
`D5` keeps the Zigbee state. A connection fault stays visible during a capture.
When `D3` and `D4` are idle, `D4` shows the Bluetooth state.

`D2` shows Wi-Fi and the API:

| `D2` | Meaning |
| --- | --- |
| Off | Wi-Fi is disabled. |
| Red pulse | Wi-Fi is enabled but disconnected. |
| Orange pulse | Wi-Fi is up, the Home Assistant switch is on, and the API is down. |
| Solid orange | Wi-Fi is up and the Home Assistant switch on the Config tab is off. |
| Solid green | The API is connected. |
| Red blink, 2 s | A Home Assistant action failed with an error reply or a timeout. |

The Home Assistant switch also stops the Home Assistant actions at once and the API server at the next restart.
If the switch is on but was off at boot, the API server is off, so `D2` pulses orange until a restart.
See [The Home Assistant switch](#the-home-assistant-switch).

Wi-Fi serves the `/buttons` page and carries Home Assistant actions. A dark `D2` does not stop a button,
because IR and Zigbee playback need neither Wi-Fi nor the API.
If the Home Assistant switch is on, a Home Assistant action turns Wi-Fi on when you press its button.
See [Home Assistant actions](#home-assistant-actions).

| State | `D3` and `D4` indication | Next action |
| --- | --- | --- |
| Ready | Solid blue | Select an input. |
| IR training | Blue chase | Send one IR frame. |
| Saved | Solid green for one second | Continue or leave. |
| Error | Red flashes | Retry or leave. |
| Voice | Blue pulse | Tap again to clear. |
| Cleared | Amber for one second | Select an input. |

`D3` and `D4` show voice-assistant state when assignment mode is closed. After
a deep-sleep wake, all four LEDs pulse in the battery colour (see
[Deep sleep](#deep-sleep)).

`D4` shows the Bluetooth state when assignment mode and voice state are both
idle. `D3` stays dark then.

| `D4` | Meaning |
| --- | --- |
| Off | The Bluetooth radio is off. |
| Blue pulse | No host bond exists. The remote is ready to pair or is pairing. |
| Solid yellow | A host bond exists but the host is not connected. |
| Solid green | The bonded host is connected and the link is encrypted. |
| Red flashes for 3 seconds | Pairing or encryption failed, or the remote rejected a second host. |
| Solid red | The Bluetooth stack did not start. |

The amber XIAO user LED shows that the remote is awake (see
[Deep sleep](#deep-sleep)). See [ZIGBEE.md](ZIGBEE.md) for the `D5` Zigbee meanings.

### The LED settings

Two switches in the **Config** tab control the LEDs. Both are on by default. The remote stores each one in flash.

The **Status LEDs** switch covers all status light. This includes `D2` to `D5` in normal use,
assignment mode, voice, and pairing feedback. It also covers the amber XIAO user LED.
If **Status LEDs** is off, these LEDs stay dark. As a result, assignment and pairing give no light feedback.

The **Boot and wake LEDs** switch covers only two animations. These are the rainbow chase on a cold boot
and the battery pulses after a deep-sleep wake. If this switch is off, the status LEDs show at once.

The two switches work together in this way:

| Status LEDs | Boot and wake LEDs | Result |
| --- | --- | --- |
| on | on | The animation plays, then the status LEDs show. |
| on | off | The status LEDs show at once. |
| off | on | The animation plays on `D2` to `D5`, then all LEDs go dark. |
| off | off | No LED lights. |

If **Status LEDs** is off, the animation does not show assignment or voice state.
The `led_vdd` rail is on only while the animation plays.
A change applies at once. If you turn **Status LEDs** on, the LEDs show the current state again.
If you turn it off during an animation, the animation finishes and then the LEDs go dark.
The Home Assistant **Status Light** entity also stays dark while both switches are off.
The XIAO charge LED is hardware driven. These settings cannot turn it off.

## Normal playback

Outside assignment mode, an input uses its one active assignment in this order:

1. Voice assistant, if assigned.
2. BLE HID, if assigned.
3. The Zigbee command, if assigned.
4. IR playback, if assigned.

An input without an assignment does not transmit a command.

## Deep sleep

The remote enters deep sleep to save battery. The `idle_sleep` component in
`c6remote.yaml` controls it. The `sleep_after`, `sleep_hold_time`, and
`cold_boot_grace` keys set the default times.

### Enter sleep

Two events start deep sleep: a hold on SW5, and an idle period.

To sleep at once, hold SW5 for the `sleep_hold_time` value. When the hold time passes, the amber XIAO user LED flashes once. Then release SW5.
The remote sleeps when you release all buttons. SW5 still sends its own assignment when you press it.
The hold ignores the blocks that follow.

If no activity occurs for the `sleep_after` time, the remote enters deep sleep.
A stored page value replaces this default.
A button press, or an edge on the expander INT line (`GPIO5`), counts as activity.

After a cold boot, the remote does not use idle sleep for the `cold_boot_grace`
time. A cold boot is a power-on, a flash, or a reset. A deep-sleep wake is not a cold boot.

### What blocks idle sleep

Idle sleep does not start while one of these is true:

- Assignment mode is open.
- The microphone runs, or the mic meter is active.
- The voice assistant runs.
- A Zigbee pairing request is active, or the pairing window is open.
- Wi-Fi is on and Wi-Fi Always On is off, as in the SW9 or page session. The Home Assistant Wi-Fi lease also blocks sleep.
- A Home Assistant action waits to send or to get a reply. The log shows this as `ha=` (bit 7 of `block_probe`).

A blocked remote counts as active. When the block ends, the full idle time starts again.

### Wake

The amber XIAO user LED is on while the remote is awake. It goes dark in deep
sleep.

Any button pulls the expander INT line (`GPIO5`) low and wakes the chip.
Before the firmware boots, a wake stub reads the expander. As a result, the
firmware knows which button woke it.

The wake press replay is a setting. It is off by default.
When it is off, the press that wakes the remote only wakes it. Press the button again to send its command.
A held SW1 or SW9 does not tap when you release it.

When the setting is on, the remote sends the wake press when the Zigbee link comes up.
The wake press is the Zigbee assignment of that button.
If no link comes within 3 s after setup, the remote drops the wake press.
A Home Assistant assignment does not wait for the Zigbee link. The wake press queues its action at once.
If the Home Assistant switch is off, the remote drops that wake press at once.
[ZIGBEE.md](ZIGBEE.md) describes the send path.

SW9 acts when you release it. If you still hold SW9 at wake, the remote runs the
Wi-Fi hold whether the setting is on or off. When the setting is on, the remote sends the assignment
of SW9 when you release SW9 before the 2 s hold ends.

If you still hold SW1 at wake, the remote does not start the assignment mode
hold. When the setting is on, the remote sends the assignment of SW1 when you release SW1.

After a wake, all four LEDs pulse two times in the battery colour. Each pulse
is 800 ms. The colour shows the battery level at the first moment after the wake:

| Battery | Colour |
| --- | --- |
| 60 % or more | Green |
| 30 % to 59 % | Orange |
| Less than 30 % | Red |
| No reading | White |

The pulse covers the Wi-Fi, Bluetooth, and Zigbee status LEDs for 1.6 seconds.
The status colours return when the pulse ends. Assignment mode and voice states
have priority on `D3` and `D4`, so they stay visible during the pulse.

While the remote sleeps, these conditions apply:

- The `led_vdd` and `ir_vdd` rails are off, because `GPIO18` and `GPIO6` float and `R10` and `R11` pull the gates up.
- `GPIO16` floats and `GPIO17` has a pull-down.
- `GPIO0` and `GPIO2` stay low, so `MK1` sees no clock.
- `GPIO15` floats, so the XIAO user LED is dark.

### Sleep settings on the page

The `/buttons` page has a **Sleep** block. It shows only on a build with `idle_sleep`.

- The **Sleep** switch turns idle sleep on or off.
- The **Sleep after, in minutes** box sets the idle time from 1 to 60 minutes.
- The **Send the wake press** switch turns the wake press replay on or off. It is off by default.

The remote stores all three settings in flash. A change restarts the idle window.
The SW5 hold works when **Sleep** is off.

### Flash over USB

USB serial disconnects while the remote sleeps. To flash the remote, do these steps:

1. If this is the first build after the `idle_sleep` change, run `esphome clean c6remote.yaml`.
2. Run `esphome compile c6remote.yaml`.
3. Press a button to wake the remote.
4. Run `esphome upload c6remote.yaml --device /dev/cu.usbmodem2101`.

The cold boot grace after the flash reset keeps the remote awake for a while.
A stale incremental build after a component-count change can cause a boot loop.
