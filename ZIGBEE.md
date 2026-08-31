# Zigbee operation

## Role

The remote is an always-on Zigbee end device. It is not a router.

The remote uses endpoint 1 as an On/Off client. Each assigned button sends a
Zigbee Toggle command to its stored group.

The firmware holds no MQTT client. The `/buttons` page reads the Zigbee2MQTT
group list in the browser and posts only the group ID to the remote.

The remote does not need MQTT, Wi-Fi, Home Assistant, or Zigbee2MQTT for button
playback. It needs Wi-Fi only while you configure it from the page.

## Requirements

Install Zigbee2MQTT and enable its frontend. The browser connects to the
frontend websocket, so the remote needs no broker credentials.

Use the pinned `luar123/zigbee_esphome` external component in `c6remote.yaml`.
Do not change its revision without validation.

ZHA does not supply the group list this page reads. Use Zigbee2MQTT.

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

Group membership lives in the group table of the light, not in the remote. Only
Zigbee2MQTT can write it.

The remote sends a groupcast and nothing else, so a button always points at a
group. To control one device, that device needs a group of its own.

The page can build that group for you. It can also use a group that you made in
Zigbee2MQTT for more than one light.

One group can serve more than one button. A button reads only the ID, so a later
membership change in Zigbee2MQTT needs no change on the remote.

## Assign a button from the web page

1. Open `http://homething-c6.local/buttons`.
2. Select an input, then select **Zigbee**.
3. The first time, enter the Zigbee2MQTT frontend websocket address, such as
   `ws://zigbee2mqtt.local:8080/api`. Enter the frontend token if one is set.
4. Select **Connect**.
5. Select one of these three routes:
   - Select a group, then select **Assign group**.
   - Select a device, then select **Assign device**.
   - Type a group ID, then select **Assign typed ID**.

The browser keeps the address and the token in `localStorage`. Neither value
reaches the remote, so each browser enters them once.

The page accepts a decimal group ID, such as `4609`, or a hex group ID, such as
`0x1201`. The remote refuses `0` and every value above `0xFFF7`, because
`0xFFF8` and above are the reserved Zigbee broadcast addresses.

A typed ID wins over the list selection. Use a typed ID when the browser cannot
reach the frontend.

The remote stores the group ID and the name. It writes the record to flash at
once, because a group target needs no network confirmation.

### Assign device

**Assign device** makes a group that holds only the selected device.

1. The browser looks for a group whose only member is that device. If it finds
   one, it uses that group and creates nothing.
2. If it finds none, it publishes `bridge/request/group/add` with the name
   `c6 <device name>` and reads the new ID from the response.
3. It publishes `bridge/request/group/members/add` for the device.
4. It sends the group ID to the remote.

Step 1 keeps a repeated assignment from leaving a new group behind each time.

If the group is created but the member add fails, the page reports the new group
ID and assigns nothing. Remove that group in Zigbee2MQTT, or add the member by
hand and assign the ID with **Assign typed ID**.

Each request carries a transaction, because the bridge answers all requests on a
shared response topic. A request that gets no answer in ten seconds fails.

The assignment replaces any IR code or voice action on that input.

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

An assigned input sends an On/Off Toggle command to its group. The command
leaves endpoint 1 and uses group broadcast delivery.

The command does not wait for a coordinator, a broker, or a target state report.
The mesh routes it, so the button works while Zigbee2MQTT and Home Assistant are
both down.

Toggle does not mean "set on" or "set off." Each target changes its current
On/Off state. Assign one button only to lights that must toggle together.

## Clear a button

Clear a button from the `/buttons` page, or with the last tap of the assignment
cycle on the remote.

Clearing removes the local record only. The group and its membership stay in
Zigbee2MQTT, so another button can still use that group.

## Storage

The remote stores one record for each of the 18 assignable slots. A record holds
the group ID and the target name.

The record format is version 3. Version 2 held a target kind for the private
device groups, so an older record does not load and the slots start clear.

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
