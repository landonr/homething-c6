# Assignment mode

## Goal

Assignment mode gives each supported input one active action. An action can be
an IR code, a Zigbee command, a BLE HID control, a Home Assistant action, the voice assistant, or no action.

Store assignments in flash. Outside assignment mode, an input replays its active
action.

## Enter and leave the mode

Hold the assignment mode button for two seconds to enter assignment mode. Hold
it for two seconds again to leave the mode.

The default assignment mode button is `SW9`. To use a different button, see
[Hold buttons](#hold-buttons).

The ready state closes after five seconds without an input.

The release that ends an assignment mode hold does not count as a tap.

## Assignment cycle

For `SW1` to `SW11` and the five wheel directions, tap the same input in this
order:

1. First tap: train an IR code.
2. Second tap: assign the voice assistant.
3. Third tap: clear the input.

A button with an active hold taps when you release it, not when you press it.
See [Hold buttons](#hold-buttons).

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

The **Home Assistant** switch on the Config tab controls the Home Assistant actions, the voice assistant, and the API server.

If you turn the switch off, the Home Assistant buttons stop at once.
A press sends nothing, does not turn on Wi-Fi, and does not blink `D2`. The log shows one line for each press.
The remote also drops the actions in the queue and ends the [Wi-Fi lease](#wi-fi-lease).
The remote also refuses a voice press at once. See [The voice assistant](#the-voice-assistant).

The API server starts only at boot and has no stop. As a result, it runs until the next restart.
After that restart, the API server does not start, and Home Assistant cannot connect to the remote.
The ESPHome network log also uses the API server. While it is off, read the log over USB. OTA updates do not use it.

Home Assistant shows the switch as the **Home Assistant API** entity. Home Assistant can turn the switch off.
After the next restart, Home Assistant cannot reach the remote, so it cannot turn the switch on again.
To turn the switch on, use the web page. Then select **Restart**.

If you turn the switch on in a boot that started with the switch off, the buttons stay off.
They start after the next restart, together with the API server.

The Home Assistant line on the Config tab tells you when the switch and the API server do not agree:

| Line | Cause |
| --- | --- |
| **Home Assistant is off. Home Assistant and voice buttons are disabled. The API stops at the next restart.** | The switch is off, but the API server runs until the next restart. |
| **Home Assistant is on. The API is off. Restart the remote to start it.** | The switch is on, but it was off at boot. |

An input that holds a Home Assistant action or the voice assistant keeps it while the switch is off.
The tile shows the assignment in grey with a red circle, and the editor gives the reason.

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
4. Select **Save** in the button card.
5. To test the action, select **Test saved action**.

The test queues the saved action and shows the result: ok, error with the Home Assistant message, unconfirmed, timeout, or dropped.
If the Home Assistant switch is off, or the API server is off for this boot, the test fails and shows the reason.
Copy, Paste, export, and import carry Home Assistant assignments.

### Press flow

If the Home Assistant switch is off, a press sends nothing. See [The Home Assistant switch](#the-home-assistant-switch).

A press queues the action. The queue holds a maximum of 8 actions. The remote drops extra presses.
A button with an active hold queues its action when you release it. See [Hold buttons](#hold-buttons).

If Wi-Fi is off, the press turns it on. The remote sends the action when Home Assistant has connected and subscribed to actions.
If no client subscribes within 20 seconds, the remote drops the press as a timeout.

The remote waits 5 seconds for a reply. Old Home Assistant versions send no reply.
An integration that does not allow actions also sends no reply. In this case the result is unconfirmed.
After 8 unanswered calls, the remote stops asking for replies until late replies arrive.

The first press after sleep takes a few seconds, because Wi-Fi must connect and Home Assistant must reconnect to the remote.
Presses during the Wi-Fi lease are faster.

### Wi-Fi lease

Wi-Fi stays on while an action waits and for 60 seconds after the last action finished.
Then Wi-Fi turns off, unless a session from the Wi-Fi hold, a page session, or Wi-Fi Always On keeps it on.

If you use the Wi-Fi hold while only the lease holds Wi-Fi, the hold opens a page session.
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

The device serves a web page at `http://homething-c6-xxxxxx.local/`.
`xxxxxx` is the last six hex digits of the remote MAC address. The page uses
the `web_server_base` server on port 80. The production config has no ESPHome `web_server` entity page.
Home Assistant shows the web page address as the diagnostic **Web Page** entity.
The address uses the hostname, so a new IP address does not change it.

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
If the **Home Assistant** switch is off, the selector also grays out **Voice assistant**, because the voice assistant uses the API.
To assign that action, turn on its switch first. Until then, the selector opens on IR code for an input that holds that action.

The right side of the selected-input title has **Copy** and **Paste** buttons.
Use them to copy an IR code, Zigbee target, BLE HID, or Home Assistant configuration between inputs.

Select the source input and select **Copy**. Then select the target input and
select **Paste**. Paste asks you to confirm. Then it opens the panel of the copied action and fills its fields.
Paste writes the configuration to the remote at once. It does not wait for **Save**.

Paste stays available for a Clear or empty input when copied configuration exists.

One panel shows at a time, because an input holds one action. The IR panel owns
the **Record IR** button and the code box.

The page is an alternative to the tap cycle, not a replacement. Both routes write
the same flash records.

The page also has a **Sleep** block for the deep-sleep settings. See [Deep sleep](#deep-sleep).
The **Hold** list on the card of a button sets the hold of that button. **Save** writes it. See [Hold buttons](#hold-buttons).

The header of the page has a connection line. It shows if the page can read
the remote. If two reads in a row fail, or one read gets no answer in time, the
line turns red and a banner stays at the top of the page. Changes on the page do
not get to the remote while the banner shows. The banner goes away when the
remote answers again.

### Save and Discard

The middle card holds the input title, **Copy** and **Paste**, the **Action** list, and the **Hold** list.
**Save** and **Discard** are at the bottom of that card. The panels have no write buttons of their own.

A change stays on the page until you select **Save**. These changes count:

- A different action in the **Action** list. **Clear** on an empty input is no change.
- A different hold in the **Hold** list.
- An edit in a panel field: the IR code, the code name, a Zigbee field, a BLE HID field, or a Home Assistant field.

While a change is not saved, the card shows **Unsaved changes.** If nothing changed, **Save** is not available.

**Save** first checks every field. If a field is not correct, the card shows the reason and the page sends nothing.
Then **Save** writes the action, and after it the hold. It sends one write at a time and waits for each one to complete.
If a write fails, the page stops. The card shows the error and keeps your changes, so you can select **Save** again.
When all writes are complete, the card shows **Saved.**

**Discard** puts the card and the panel back to the stored action and hold.

If you select a different input or the **Config** tab while a change is not saved, the page asks first.
If you select **Cancel**, the page keeps the change and the current input.

**Record IR**, **Test saved action**, **Copy**, and **Paste** do not wait for **Save**.

### Assign a Zigbee target from the page

The page can assign a Zigbee target and the command that goes to it. It does
not need a state transition, because you name both instead.

1. Select an input, then select **Zigbee target** in the Action selector.
2. On the first use, enter the Zigbee2MQTT frontend websocket address in the
   connection card at the top of the page.
3. Select **Group** or **Device**, then pick a target or type its address.
4. Select the command in the **Action** selector, then fill its value box if it
   shows one.
5. Select **Save** in the button card.

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
7. Select **Save** in the button card.

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
| `SW1` | 20 | Yes | Page only | Page only | Page only | Yes | Yes |
| `SW2` | 19 | Yes | Page only | Page only | Page only | Yes | Yes |
| `SW3` to `SW11` | 3 to 11 | Yes | Page only | Page only | Page only | Yes | Yes |
| Wheel directions | 12 to 16 | Yes | Page only | Page only | Page only | Yes | Yes |
| Wheel rotation | 17 and 18 | Yes | Page only | Page only | Page only | No | Yes |

Every slot accepts a Zigbee target from the page. Zigbee playback uses the same
press handler as IR playback, so a wheel detent can send it. A command that only
makes sense as a pair, such as brighter and dimmer, costs two slots, and the
wheel directions are the natural home for one.

Wheel rotation has no voice action because a detent has no release edge to end
push-to-talk.

The page hides the voice button on those two slots. The firmware checks the
same rule again on each request.

A voice request for slot 17 or 18 gets HTTP 400 and changes nothing.

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

### Name a code

The IR panel of an input that holds an IR code has a **Code name** box. The box shows the stored name.
Type a name, then select **Save** in the button card or press Enter. To remove the name, empty the box and select **Save**.
A rename changes only the name. The remote keeps the IR timings.

A name has a maximum of 23 bytes of printable ASCII. A name cannot contain a quote or a backslash.
The page removes a space at the start or the end before it saves the name.
`Slot3` to `Slot20` cannot be names, because they mark a code with no name.
If a name breaks a rule, the page shows the reason and sends nothing. The remote also refuses that name with HTTP 400.

The editor title shows the name next to the input label. On the remote layout, the name is in the tooltip
and the screen-reader label of the input. The layout shows no name text.

A capture stores the new code with no name, so the box is empty after a capture.
A paste uses the `name` line of the pasted block.

### Copy a code by text

Each input has an "IR code" box on the page. The box holds one Flipper `.ir` signal block.

`GET /buttons/api/code?slot=<n>` returns that block. **Save** in the button card posts the text of the box back as the `code` field.

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

A code with no name prints `name: Slot<n>`, with the slot number of the input, because a Flipper signal needs a name line.
`Slot3` to `Slot20` mean no name. If a pasted block uses one of them, the remote stores the code with no name.
This rule also applies to a block that you copy from a different input.

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
Assistant or voice input with the Home Assistant switch off shows the same marks.

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
remote without a source remote. The `name` line of the block carries the code name.
An import keeps that name exactly.
For a code with no name, the block has the `Slot<n>` placeholder. The import removes that line, so the code stays unnamed.
An older export file uses the same placeholder, so it imports the same way.

A Zigbee entry carries `kind`, which is `group` or `device`. A group entry holds
`group`. A device entry holds `ieee` and `ep`.

The entry of a button or a wheel direction also carries `hold`. The value is `none`, `wifi`, `status`, `sleep`, or `assign`.
Wheel rotation entries carry no `hold`.

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
{"c6remote":1,"settings":{"zigbee":true,"ble":true,"home_assistant":true,"wifi_always_on":false,
"status_leds":"on","boot_leds":true,"sleep":true,"sleep_after_s":300,"wake_replay":false},"slots":[
```

These keys are valid:

- `zigbee`, `ble`, and `home_assistant` turn each radio on or off.
- `wifi_always_on` keeps Wi-Fi on. It takes effect at the next boot.
- `status_leds` sets the **Status LEDs** mode for `D2` to `D5` and the XIAO user LED. The value is `off`, `hold`, or `on`. See [The LED settings](#the-led-settings).
- `boot_leds` turns the cold-boot chase and the wake battery pulses on or off.
- `hold_wifi`, `hold_status`, `hold_sleep`, and `hold_assign` come from an older page. Each one gives the slot of one button for that hold, or `0` for no button. See [Hold buttons](#hold-buttons).
- `sleep` turns idle sleep on or off.
- `sleep_after_s` is the idle time before sleep, from 10 to 3600 seconds.
- `wake_replay` makes the press that wakes the remote replay its stored setting.

Each key is optional. If a key is absent, the import leaves that setting as it is.
A file from an older page has no `settings` object, and it still imports.
A file from an older page can give `status_leds` as `true` or `false`. The import reads `true` as `on` and `false` as `off`.

The export puts the holds in the slot entries, not in `settings`. Several entries can carry the same hold.
The import sets the hold of each entry that differs from the remote. It writes the holds after the inputs and the settings.
An older file has no `hold` in its slot entries. It gives one button for each hold in the four `hold_` keys instead.
The import puts each of these holds on the named button and takes it off every other button.
Two of these keys cannot give the same slot. If they do, the import refuses the file before it writes.
A `hold` in a slot entry comes after the four keys.
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

The web page and its four API endpoints have no authentication. The
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

Wi-Fi serves the web page and carries Home Assistant actions and the voice assistant.
A dark `D2` does not stop an IR or Zigbee button, because IR and Zigbee playback need neither Wi-Fi nor the API.
If the Home Assistant switch is on, a Home Assistant action turns Wi-Fi on when you press its button.
See [Home Assistant actions](#home-assistant-actions).
A voice press does not turn on Wi-Fi, so the remote refuses it while Wi-Fi is off.

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
[Deep sleep](#deep-sleep)). A refused voice press shows solid red for 2 seconds.
See [The voice assistant](#the-voice-assistant).

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

Two settings in the **Config** tab control the LEDs. The remote stores each one in flash.

The **Status LEDs** setting has three modes: **Off**, **Hold button**, and **Always on**. The default is **Always on**.
The setting covers all status light. This includes `D2` to `D5` in normal use,
assignment mode, voice, and pairing feedback. It also covers the amber XIAO user LED.

| Mode | Result |
| --- | --- |
| Always on | The LEDs show the status at all times. |
| Hold button | The LEDs stay dark. Hold the status hold button for 1 s to see the status. |
| Off | The LEDs stay dark. The status hold does nothing. |

In the **Off** and **Hold button** modes, these LEDs stay dark. As a result, pairing gives no light feedback.
After an update from the older on and off switch, a stored on reads as **Always on** and a stored off reads as **Off**.

Four exceptions apply in the **Off** and **Hold button** modes.

The radio switch pulse is the first exception. When a radio turns on or off, the LED of that radio gives one radio switch pulse.
The radio switch pulse is 800 ms long. It is green when the radio turns on and red when the radio turns off.
`D2` pulses for Wi-Fi, `D4` pulses for Bluetooth, and `D5` pulses for Zigbee. `D3` does not pulse.
If two or more radios change at the same time, each LED gives its own pulse.
Each source of the change gives the pulse. For example, a Wi-Fi session that closes when idle gives a red pulse on `D2`.
In the **Always on** mode, no pulse plays. The status colour of the LED shows the new radio state.

The `D5` pulse shows the Zigbee switch, not the stack. If the Zigbee switch was off at boot and you turn it on, `D5` gives a green pulse.
But the stack starts only after a reboot. See [The radio switches](#the-radio-switches).

The status peek is the second exception. It works only in the **Hold button** mode.
Hold the status hold button for 1 s. The default status hold button is `SW7`.
`D2` to `D5` then show the same status as in the **Always on** mode. When you release the button, the LEDs go dark again.
The XIAO user LED stays dark during a status peek. No radio switch pulse plays during a status peek.
If you change the mode during a status peek, the status peek stops.

The sleep lap is the third exception. When the sleep hold arms sleep, `D2` to `D5` give one sleep lap.
The sleep lap plays in all three modes. See [Enter sleep](#enter-sleep).

Assignment mode is the fourth exception. While assignment mode is open, `D2` to `D5` show the full status in all three modes.
`D3` and `D4` show the assignment mode state. The XIAO user LED stays dark unless the mode is **Always on**.
No radio switch pulse plays while assignment mode is open. When assignment mode closes, the LEDs go dark again.

In the **Hold button** mode, the status hold button sends its assignment when you release it.
As a result, a status peek does not send the assignment of that button. See [Hold buttons](#hold-buttons).

The **Boot and wake LEDs** switch covers only two animations. These are the rainbow chase on a cold boot
and the battery pulses after a deep-sleep wake. If this switch is off, the status LEDs show at once.

The two settings work together in this way:

| Status LEDs | Boot and wake LEDs | Result |
| --- | --- | --- |
| Always on | on | The animation plays, then the status LEDs show. |
| Always on | off | The status LEDs show at once. |
| Off or Hold button | on | The animation plays on `D2` to `D5`, then the LEDs stay dark except for a radio switch pulse, a status peek, a sleep lap, or assignment mode. |
| Off or Hold button | off | The LEDs stay dark except for a radio switch pulse, a status peek, a sleep lap, or assignment mode. |

A status peek occurs only in the **Hold button** mode.
In the **Off** and **Hold button** modes, the LEDs do not show voice state. They show assignment mode state while the mode is open.
The `led_vdd` rail is on only during an animation, a radio switch pulse, a status peek, a sleep lap, or assignment mode.
A change applies at once. If you set **Status LEDs** to **Always on**, the LEDs show the current state again.
If you set **Off** or **Hold button** during an animation, the animation finishes and then the LEDs go dark.
Assume that **Status LEDs** is not **Always on** and **Boot and wake LEDs** is off.
Then the Home Assistant **Status Light** entity is on only for a radio switch pulse, a status peek, a sleep lap, or assignment mode.
The XIAO charge LED is hardware driven. These settings cannot turn it off.

## Normal playback

Outside assignment mode, an input uses its one active assignment in this order:

1. Voice assistant, if assigned.
2. BLE HID, if assigned.
3. The Zigbee command, if assigned.
4. IR playback, if assigned.

An input without an assignment does not transmit a command.

### The voice assistant

A voice press starts the Home Assistant Assist pipeline over the native API.
The remote starts it only when these conditions are true:

- The **Home Assistant** switch on the Config tab is on.
- Home Assistant is connected to the API and subscribed to voice.

If a condition is false, the remote refuses the press. The log shows one line with the reason.
`D3` and `D4` then show solid red for 2 seconds, the same as a voice-assistant error.

The switch rule applies at once. If you turn the switch off, the API server runs until the next restart.
The remote still refuses the press.

A voice press does not turn on Wi-Fi. If Wi-Fi is off, the API is not connected, so the remote refuses the press.

A refused press does not make the mic meter active, so it does not block idle sleep.

## Hold buttons

A hold runs a device action when you keep a button down for a set time. The remote has four holds:

| Hold | Default button | Hold time | Action |
| --- | --- | --- | --- |
| Wi-Fi | `SW5` | 2 s | Opens or closes a temporary Wi-Fi session. |
| Status LEDs | `SW7` | 1 s | Shows the status until you release the button. See [The LED settings](#the-led-settings). |
| Sleep | `SW1` | 2 s | Arms sleep. The remote sleeps when you release all buttons. See [Enter sleep](#enter-sleep). |
| Assignment mode | `SW9` | 2 s | Opens assignment mode, or closes it from any state. |

To set the hold of a button, select the button on the **Buttons** tab.
The **Hold** list under the action list shows **None**, the four holds, and the hold time of each hold.
The line under the list tells what the hold does.
Select **Save** to write the hold. See [Save and Discard](#save-and-discard).
A hold can use `SW1` to `SW11` or one of the five wheel directions.
Wheel rotation cannot carry a hold, because a detent has no release edge. As a result, the card of a wheel rotation input has no **Hold** list.
To turn off the hold of a button, select **None** and then **Save**.

Each button carries one hold or no hold. Several buttons can carry the same hold.
For example, `SW3` and `SW5` can both open a temporary Wi-Fi session.
The `set_hold` action takes `slot` and `hold`. The value of `hold` is `none`, `wifi`, `status`, `sleep`, or `assign`.
The firmware refuses a wheel rotation slot or an unknown hold with HTTP 400 and changes nothing.
The state JSON gives the `hold` of each slot.

The remote stores one hold for each button in flash. If the stored record is missing, each button takes its default hold.
If one entry of the record is bad, only that button takes its default hold.
An older firmware stores one button for each hold. At the first boot after the update, the remote moves that record to the new form.

The status hold is active only when **Status LEDs** is set to **Hold button**. The other holds are always active.
If two buttons carry the status hold, the status shows until you release the last of them.
The tooltip of each button on the map names its active hold.

A button with an active hold sends its own assignment when you release it before the hold time.
If the hold time passes, the hold runs and the release sends nothing.
A button without an active hold sends its assignment when you press it.
The remote decides at the press if the button has an active hold. A settings change during the hold does not change that press.

A voice assignment on a button with an active hold starts Assist at the release. Home Assistant ends it when your speech stops.
A BLE HID assignment on a button with an active hold sends the key press and the key release together at the release.
A Home Assistant action on a button with an active hold runs at the release. It asks for Wi-Fi at that moment.

If **WiFi Always On** is off, a button with the Wi-Fi hold is the only way to open a temporary session.
In that case, the page asks you to confirm before a save takes the Wi-Fi hold off the last button that has it.
If another button keeps the Wi-Fi hold, the page does not ask.

## Deep sleep

The remote enters deep sleep to save battery. The `idle_sleep` component in
`c6remote.yaml` controls it. The `sleep_after` and `cold_boot_grace` keys set
the default times. The sleep hold is one of the [hold buttons](#hold-buttons),
and its hold time is 2 s.

### Enter sleep

Two events start deep sleep: the sleep hold, and an idle period.

To sleep at once, hold the sleep hold button for 2 s. The default sleep hold button is `SW1`.
When the hold time passes, the remote arms sleep. Then release the button.
When the remote arms sleep, `D2` to `D5` give one sleep lap. The sleep lap is one anticlockwise lap of blue-white light, from `D5` to `D2`.
The sleep lap plays in all LED settings. If **Status LEDs** is set to **Always on**, the amber XIAO user LED also flashes once.
After the sleep lap, `D2` to `D5` stay dark until the remote sleeps.
The remote sleeps when you release all buttons. If you release all buttons during the sleep lap, the remote sleeps at once.
The sleep hold button sends nothing when the hold runs. A shorter press sends its assignment at the release.
The sleep hold ignores the blocks that follow.

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
- Wi-Fi is on and Wi-Fi Always On is off, as in a session from the Wi-Fi hold or the page. The Home Assistant Wi-Fi lease also blocks sleep.
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
If you still hold the button at wake, its release does not tap.

When the setting is on, the remote sends the wake press when the Zigbee link comes up.
The wake press is the Zigbee assignment of that button.
If no link comes within 3 s after setup, the remote drops the wake press.
A Home Assistant assignment does not wait for the Zigbee link. The wake press queues its action at once.
If the Home Assistant switch is off, the remote drops that wake press at once.
[ZIGBEE.md](ZIGBEE.md) describes the send path.

If you still hold a button with an active hold at wake, the remote does not replay its wake press.
This rule also applies to a Home Assistant assignment.
When the setting is on, the remote sends the assignment of that button when you release it before the hold time.

If you still hold a button with an active hold at wake, its hold starts. This occurs when the setting is on or off.
The assignment mode hold is the exception. It does not start from a wake.
When the setting is on, the release of the assignment mode hold button always sends its assignment.

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

The web page has a **Sleep** block. It shows only on a build with `idle_sleep`.

- The **Sleep** switch turns idle sleep on or off.
- The **Sleep after, in minutes** box sets the idle time from 1 to 60 minutes.
- The **Send the wake press** switch turns the wake press replay on or off. It is off by default.

The remote stores all three settings in flash. A change restarts the idle window.
The sleep hold works when **Sleep** is off.

### Flash over USB

USB serial disconnects while the remote sleeps. To flash the remote, do these steps:

1. If this is the first build after the `idle_sleep` change, run `esphome clean c6remote.yaml`.
2. Run `esphome compile c6remote.yaml`.
3. Press a button to wake the remote.
4. Run `esphome upload c6remote.yaml --device /dev/cu.usbmodem2101`.

The cold boot grace after the flash reset keeps the remote awake for a while.
A stale incremental build after a component-count change can cause a boot loop.
