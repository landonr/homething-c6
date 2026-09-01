# Zigbee operation

## Role

The remote is an always-on Zigbee end device. It is not a router.

The remote uses endpoint 1 as an On/Off client. Each assigned button sends a
Zigbee Toggle command to its stored target, which is a group or one device.

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
7. Select **Assign**.

The device list holds only a device with an On/Off input cluster, because On/Off
Toggle is the one command the remote sends.

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

**Assign** sends the IEEE address and the endpoint of the device to the remote.
The browser publishes nothing to Zigbee2MQTT.

The page picks the lowest endpoint that has a `genOnOff` input cluster. If the
bridge publishes no endpoint list, the page uses endpoint 1.

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
3. It sends the Toggle to the cached address.

The APS confirm reports whether the device received the unicast. If the confirm
fails, the remote drops the cached address, resolves it again, and resends the
Toggle one time. A second failure stops there, and the next press starts again.

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
the `bridge/groups` message and ignores the rest.

A websocket needs no CORS grant. A `fetch` to the same host would need one,
because the page comes from the remote.

The remote never subscribes to `bridge/devices`. ESPHome buffers a whole MQTT
payload before it delivers the message, and the retained device inventory of a
real network is larger than the free heap.

## Toggle playback

An assigned input sends an On/Off Toggle command to its target. The command
leaves endpoint 1. A group target uses group broadcast delivery, and a device
target uses unicast delivery to the endpoint the page found.

The command does not wait for a coordinator, a broker, or a target state report.
The mesh routes it, so the button works while Zigbee2MQTT and Home Assistant are
both down.

Toggle does not mean "set on" or "set off." Each target changes its current
On/Off state. Assign one button only to lights that must toggle together.

## Clear a button

Clear a button from the `/buttons` page, or with the last tap of the assignment
cycle on the remote.

Clearing removes the local record only. A group and its membership stay in
Zigbee2MQTT, so another button can still use that group. A device target leaves
nothing behind, because the assignment wrote nothing to Zigbee2MQTT.

## Storage

The remote stores one record for each of the 18 assignable slots. A record holds
a target kind, the target name, and the address for that kind.

A group record holds the group ID. A device record holds the IEEE address and
the endpoint of one device.

The record format is version 4. The remote reads a version 3 record and writes
it back as version 4, so the group assignments survive the update.

The two formats have different lengths, so the version 4 load fails first and
the migration runs. Version 2 and earlier do not load, and those slots start
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
