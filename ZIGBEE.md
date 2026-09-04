# Zigbee operation

## Role

The remote is an always-on Zigbee end device. It is not a router.

The remote uses endpoint 1 as a client of every cluster it can command. Each
assigned button sends one ZCL command to its stored target, which is a group or
one device.

The firmware holds no MQTT client. The `/buttons` page reads the Zigbee2MQTT
inventory in the browser and posts only the resolved address to the remote.

The remote does not need MQTT, Wi-Fi, Home Assistant, or Zigbee2MQTT for button
playback. It needs Wi-Fi only while you configure it from the page.

## Requirements

Install Zigbee2MQTT and enable its frontend. The browser connects to the
frontend websocket, so the remote needs no broker credentials.

Use the pinned `luar123/zigbee_esphome` external component in `c6remote.yaml`.
Do not change its revision without validation.

ZHA does not supply the group and device lists this page reads. Use
Zigbee2MQTT.

## Pair the remote

1. Permit joining in Zigbee2MQTT.
2. Power or restart the remote while joining is permitted.
3. Wait for Zigbee2MQTT to show `homething-c6` as joined.
4. Confirm that `D5` is solid green.

The remote does not sleep and does not route Zigbee traffic. Keep it powered
while the coordinator forms or repairs the network.

If `D5` pulses red, the Zigbee stack has started but has no network connection.
Permit joining again, then restart the remote.

A join needs both sides. The remote steers on its own when it is factory new,
but it can only join while the coordinator permits it.

## Permit joining from the page

The Zigbee2MQTT block on the `/buttons` page can open the pairing window on the
coordinator, so step 1 of pairing needs no separate Zigbee2MQTT session.

Select **Enable pairing for 3 minutes**. The browser sends
`{"topic":"bridge/request/permit_join","payload":{"value":true,"time":180}}`
over the Zigbee2MQTT frontend websocket that this browser already holds. This is
the only message the page ever publishes to Zigbee2MQTT. Every assignment stays
read only on that socket.

The line above the button reads "Pairing is closed on the coordinator." or
"Pairing is open on the coordinator for 2:54." with a live countdown from the
retained `bridge/info` message.

While the window is open, the button reads **Stop pairing** and sends `time: 0`.
Zigbee2MQTT closes the window itself when the time expires, so the remote runs
no timer.

If the socket is down, the button is disabled and the line reads "Pairing needs
the Zigbee2MQTT link."

## Groups and devices

A button holds one of two target kinds. A group target sends a groupcast. A
device target sends a unicast to one device.

Use a group when one button must switch more than one light together. Group
membership lives in the group table of the light, not in the remote, and only
Zigbee2MQTT can write it.

One group can serve more than one button. A button reads only the ID, so a later
membership change in Zigbee2MQTT needs no change on the remote.

Use a device target for one light. Zigbee2MQTT writes nothing for it, so a
repeated assignment leaves no group behind.

## Assign a button from the web page

1. Open `http://homething-c6.local/buttons`.
2. Select an input, then select **Zigbee target** in the Action selector.
3. The first time, enter the Zigbee2MQTT frontend websocket address, such as
   `ws://zigbee2mqtt.local:8080/api`. Enter the frontend token if one is set.
4. Select **Connect**.
5. Select **Group** or **Device** in the Target kind selector.
6. Select a group or a device. The picker fills the boxes below it.
7. Select the command in the **Action** selector, then fill its value box if it
   shows one.
8. Select **Assign**.

The device list holds only a device that accepts at least one of the actions. A
device the bridge published no endpoint list for stays in the list, because that
says nothing about what it accepts.

The Target kind selector decides which fields the panel shows. **Group** shows
the group picker and a **Group ID** box. **Device** shows the device picker, an
**IEEE address** box, and an **Endpoint** box.

The panel therefore holds one target at a time, and **Assign** sends what is on
screen. Changing the kind clears every field, so a value the panel stopped
showing can never be assigned.

Opening a slot that already holds a device target opens the panel on
**Device**.

The browser keeps the address and the token in `localStorage`. Neither value
reaches the remote, so each browser enters them once.

You can also type into a box. A picker does not appear without its bridge list,
so typing is the only route when this browser cannot reach the frontend.

A group ID is a decimal value, such as `4609`, or a hex value, such as `0x1201`.
The remote refuses `0` and every value above `0xFFF7`, because `0xFFF8` and
above are the reserved Zigbee broadcast addresses.

An IEEE address is 16 hex digits, such as `0x94deb8fffe9db81e`. The `0x` prefix
is optional. The page refuses a shorter value before it reaches the remote.

A device uses the value in the **Endpoint** box, and endpoint 1 when that box is
empty.

The page reads the target name from the bridge lists when it sends, not when you
pick. An edited box therefore cannot keep the name of the target it replaced.

The remote stores the address and the name. It writes the record to flash at
once, because no target needs a network confirmation to be stored.

### A device target

**Assign** sends the IEEE address, the endpoint, the action and its value to
the remote. The browser publishes nothing to Zigbee2MQTT.

The page picks the lowest endpoint that has the input cluster of the action. A
device can carry `genOnOff` on one endpoint and `hvacThermostat` on another, so
the endpoint follows the action. If the bridge publishes no endpoint list, the
page uses endpoint 1.

The remote stores the address and writes the record to flash at once. It looks
up the network address later, on the first press.

Use a mains device for a device target. A battery device keeps its radio off, so
the unicast waits at its parent until the device polls.

The assignment replaces any IR code or voice action on that input.

## How the remote finds a device

A Zigbee unicast needs the 16-bit network address, but the remote stores the
64-bit IEEE address. The network address is a lease that ends when the device
rejoins, so the remote never writes one to flash.

The remote resolves the address in this order:

1. It reads its own address map. This costs no radio traffic.
2. If the map has no entry, it broadcasts `NWK_addr_req` and caches the answer.
3. It sends the command to the cached address.

The APS confirm reports whether the device received the unicast. If the confirm
fails, the remote drops the cached address, resolves it again, and resends the
command one time. A second failure stops there, and the next press starts
again.

A slot broadcasts `NWK_addr_req` at most once every 10 seconds, because the
request reaches the whole mesh. A request that gets no answer in 5 seconds
fails.

After the remote joins, it warms the cache for each device slot. It reads the
address map first, and asks the mesh only for a slot the map does not hold. Each
slot is warmed at most once for each join, at one slot per second.

A warm cache only saves time on the first press. Correctness comes from the
confirm and the resend, so a cold or stale cache still works.

## How the browser reads the group list

The Zigbee2MQTT frontend relays every MQTT message on its websocket as a
`{topic, payload}` object, with the base topic already removed. The page keeps
the `bridge/groups` and `bridge/devices` messages and ignores the rest.

`bridge/devices` carries the endpoint list of each device, and each endpoint
carries its input cluster list. That list decides which actions the panel
offers and which endpoint an action goes to.

A websocket needs no CORS grant. A `fetch` to the same host would need one,
because the page comes from the remote.

The remote never subscribes to `bridge/devices`. ESPHome buffers a whole MQTT
payload before it delivers the message, and the retained device inventory of a
real network is larger than the free heap.

## Actions

A slot holds one target and one action. The action is one press, so a pair such
as brighter and dimmer costs two inputs. The wheel is the usual home for a pair,
because the up and down directions are two assignable slots.

| Action | Cluster | Value |
| --- | --- | --- |
| Toggle, On, Off | `genOnOff` | none |
| Brighter, Dimmer | `genLevelCtrl` | step size, 1 to 254 |
| Warmer white, Cooler white | `lightingColorCtrl` | step in mireds, 1 to 2000 |
| Recall scene | `genScenes` | scene ID, 0 to 255 |
| Open, Close, Stop | `closuresWindowCovering` | none |
| Warmer, Cooler | `hvacThermostat` | step in tenths of a degree, 1 to 127 |
| Lock, Unlock | `closuresDoorLock` | none |
| Alarm | `ssIasWd` | seconds, 1 to 600 |
| Squawk | `ssIasWd` | none |

The **Action** selector lists only the actions the target accepts. The page
reads the input cluster list of the device from Zigbee2MQTT, and a group offers
what every member of it accepts. A typed address describes nothing, so it offers
every action.

An action with a value shows a box for it. An empty box means the value the
placeholder names, so the panel always sends what it shows. The remote bounds
the value again, because an imported block reaches it without a picker.

The command does not wait for a coordinator, a broker, or a target state report.
The mesh routes it, so the button works while Zigbee2MQTT and Home Assistant are
both down.

Toggle does not mean "set on" or "set off." Each target changes its current
On/Off state. Use On or Off for a group whose members can fall out of step.

Brighter and Dimmer use StepWithOnOff, so a step up wakes a light that is off.

Warmer and Cooler send a relative setpoint change, which needs no attribute
read. A Tuya thermostat answers no standard command, so it needs Home Assistant.

A lock refuses a frame the remote is not bound for, so Lock and Unlock only work
on a lock that has this remote in its access list.

## Send path

`zigbee_learning.h` holds the send path. The SDK is `esp-zigbee-lib` 2.0.4, which
uses the `ezb_*` API.

A press calls `play()`. A group target goes straight to `send_command_()`. A
device target goes through `play_device_()`, which resolves the network address
first.

`send_command_()` fills one `ezb_zcl_cluster_cmd_ctrl_t` and hands it to
`dispatch_()`. Only `dispatch_()` knows the action, so it picks the payload
struct and the request function.

A group request uses `EZB_ADDR_MODE_GROUP` and the group ID. A device request
uses `EZB_ADDR_MODE_SHORT` and the resolved network address.

`src_ep` is always `CLIENT_ENDPOINT`, which is endpoint 1. A device request also
sets `dst_ep` from the record.

Every SDK call must run between `esp_zigbee_lock_acquire()` and
`esp_zigbee_lock_release()`. The main loop sends, and the Zigbee task runs the
confirm and resolve callbacks.

A device request sets `cmd_ctrl.cnf_ctx.cb` to `on_confirm_`. A group request
sets no callback, because a groupcast returns no acknowledgement.

A callback must not block on flash or on the record mutex. It parks the slot in
`pending_state_`, and the next main loop tick does the work.

`dispatch_()` reads no attribute, so a press stays one frame with no round trip.

### Where the numbers come from

The `Action` enum in `zigbee_learning.h` and the `ZA` table in
`components/button_config/button_config_page.h` hold the same numbers. A new
action needs a row in both, or the page names a command the remote does not
know.

`action_valid_()` bounds the value of each action. The page bounds it too, but
an import block reaches the manager without passing a picker.

The cluster of an action must also appear as a `role: CLIENT` cluster on
endpoint 1 in `c6remote.yaml`.

### Other commands the SDK can send

The library compiles the full ZCL client command set, and the remote uses part
of it. The headers are in
`managed_components/espressif__esp-zigbee-lib/include/ezbee/zcl/cluster/`.

These commands are compiled but unused:

| Cluster | Commands |
| --- | --- |
| On/Off `0x0006` | `off_with_effect`, `on_with_timed_off` |
| Level `0x0008` | `move_to_level_with_on_off`, `move`, `stop` |
| Color control `0x0300` | `move_to_color_temperature`, `move_to_hue_and_saturation`, `color_loop_set` |
| Scenes `0x0005` | `store_scene` |
| Identify `0x0003` | `identify` |
| Thermostat `0x0201` | the weekly schedule commands |
| Any cluster | `read_attr`, `write_attr`, `config_report`, `custom_cluster_cmd` |

`ezb_zcl_write_attr_cmd_req()` and `ezb_zcl_custom_cluster_cmd_req()` reach an
attribute or a manufacturer cluster that has no named command.

`move` and `stop` need a press edge and a release edge, so they need an input
that reports both. Every action the remote sends today is one press.

An absolute setpoint needs a write to cluster `0x0201`. Attribute `0x0012` is
the heating setpoint, and `0x0011` is the cooling setpoint. Both are `int16` in
0.01 C.

Attribute `0x001C` is the system mode. Its values include off `0x00`, auto
`0x01`, cool `0x03`, and heat `0x04`.

A Tuya thermostat does not answer cluster `0x0201`. It uses manufacturer cluster
`0xEF00` and a datapoint payload for each model.

## Clear a button

Clear a button from the `/buttons` page, or with the last tap of the assignment
cycle on the remote.

Clearing removes the local record only. A group and its membership stay in
Zigbee2MQTT, so another button can still use that group. A device target leaves
nothing behind, because the assignment wrote nothing to Zigbee2MQTT.

## The radio switch

One switch turns the Zigbee radio off for the whole remote. The switch is on the
`/buttons` page, on the heading line of the **Zigbee2MQTT** block, and in Home
Assistant as **Zigbee Radio**.

If the switch is off, every button that sends Zigbee is disabled and the remote
asks for no network address. The assignments stay in flash, so the buttons work again when
the switch goes back on.

The stack keeps its place on the network only until the next reboot, because the
ESP-Zigbee stack has no restart. A rejoin would cost the pairing that the buttons
point at.

An `on_boot` trigger at priority 800 reads the stored switch from flash with
`ZigbeeAssignmentManager::radio_enabled_from_flash()`. If the switch is off, it
calls `mark_failed()` on the Zigbee component and records the gate with
`zigbee_assignments.set_boot_gated(true)`. A failed ESPHome component never runs
its setup, so the 802.15.4 stack never starts.

While the gate holds, turning the switch back on cannot start the stack. Reboot
the remote to lift the gate. See "Network state on the page" for the line the
page shows.

Select the **Restart** button entity to reboot the remote from Home Assistant or
from the `/buttons` page. Nothing else on the device offers a reboot.

`D5` is dark while the switch is off, the same as before the stack starts.

The switch state lives in the Zigbee assignment record, so the remote restores it
after a reboot.

## Network state on the page

The stack reports three states, and the `/buttons` page names the one it is in
under the switch:

| Line | Meaning |
| --- | --- |
| `Zigbee radio is on. The stack has not started.` | The stack has not answered its start signal yet. |
| `Zigbee radio is on. Not paired.` | The stack is factory new. It has no credentials and it searches for a coordinator. |
| `Zigbee radio is on. Not on the network yet. The remote is rejoining.` | The stack holds credentials and it rejoins the network. |
| `Zigbee radio is on. Paired to a Zigbee network.` | The remote joined a network. |
| `Zigbee radio is on. The stack is down. Reboot the remote to start it.` | The switch was off at boot, so the stack never started. Reboot to lift the gate. |

The component latches its connected flag on the first join and never clears it,
so `Paired` means joined once, not reachable now.

The `zigbee` component keeps its instance file-static, so the 250 ms interval in
`c6remote.yaml` pushes `is_started()`, `is_connected()`, and `factory_new_` into
`zigbee_assignments`. The `/buttons` state endpoint reads them from there.

## Storage

The remote stores one record for each of the 18 assignable slots. A record holds
a target kind, the target name, the address for that kind, the action, and the
value of the action.

A group record holds the group ID. A device record holds the IEEE address and
the endpoint of one device.

The record format is version 5. The remote reads a version 4 or a version 3
record and writes it back as version 5, so the assignments survive the update.
An older record names no action, so the migration gives it Toggle.

Each format has a different length, so a newer load fails first and the
migration runs. Version 2 and earlier do not load, and those slots start
clear.

## LED meanings

`D5` shows Zigbee state at all times. It is off before the Zigbee stack starts,
solid green when connected, and pulsing red when disconnected.

`D2` shows Wi-Fi and the API. Wi-Fi serves the `/buttons` page only, so a dark
`D2` does not stop a button.

Assignment mode uses `D3` and `D4` only, so `D5` stays readable.

| LEDs | Meaning |
| --- | --- |
| `D3` and `D4` solid blue | Assignment mode waits for an input. |
| `D3` and `D4` blue chase | The selected input waits for an IR code. |
| `D3` and `D4` solid green | IR assignment saved. |
| `D3` and `D4` flash red | An IR or flash operation failed. |
| `D3` and `D4` pulsing blue | The selected input now starts Assist. |
| `D3` and `D4` amber | The selected input is clear. |
