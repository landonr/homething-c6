# Zigbee operation

## Role

The remote is an always-on Zigbee end device. It is not a router.

The remote uses endpoint 1 as an On/Off client. Each trained button sends a
Zigbee Toggle command to its assigned group.

The firmware uses Wi-Fi and MQTT only to train or change a Zigbee assignment.
The remote sends Toggle commands directly after training. It does not need MQTT,
Wi-Fi, Home Assistant, or Zigbee2MQTT during normal button playback.

## Requirements

Install Zigbee2MQTT and an MQTT broker. Configure the firmware secrets for the
broker, user name, and password.

Set `zigbee2mqtt_base_topic` to the Zigbee2MQTT base topic. The default is
`zigbee2mqtt`.

Use the pinned `luar123/zigbee_esphome` external component in `c6remote.yaml`.
Do not change its revision without validation.

The firmware disables MQTT discovery and MQTT log topics. MQTT is a training
transport only.

ZHA does not supply this training interface. Use Zigbee2MQTT for this firmware.

## Pair the remote

1. Permit joining in Zigbee2MQTT.
2. Power or restart the remote while joining is permitted.
3. Wait for Zigbee2MQTT to show `homething-c6` as joined.
4. Confirm that `D5` is solid green.

The remote does not sleep and does not route Zigbee traffic. Keep it powered
while the coordinator forms or repairs the network.

If `D5` pulses red, the Zigbee stack has started but has no network connection.
Permit joining again, then restart the remote.

## Train a button

Training makes one remote input control one allowed Zigbee2MQTT target. The
target must publish an `ON` or `OFF` state transition during training.

The target name must match one of these values:

- `office_lights`
- `Bedroom Lights`
- `Hallway Lights`
- `Kitchen Light Switch`
- `Downstairs Lights`

1. Confirm that `D2` is solid green. Green needs Wi-Fi, the API, and MQTT.
2. Hold `SW2` for two seconds to enter receiver mode.
3. Tap the input once. The remote waits for an IR code.
4. Tap the same input again. `D5` pulses yellow for Zigbee training.
5. Within 60 seconds, change the target lamp from `ON` to `OFF`, or from `OFF` to `ON`.
6. Wait for four green LEDs. The assignment is complete.

The remote ignores the first retained target state. It accepts only a later
root-topic state transition. A repeated state does not train a button.

If the target is a Zigbee2MQTT group, the remote stores its existing group ID.
If the target is a device, the remote adds it to a private button group.

The remote saves a device assignment only after Zigbee2MQTT confirms the group
requests. The remote does not change an existing target group.

## Groups

Individual-device assignments use one reserved group for each slot. The group
ID is deterministic. Existing Zigbee2MQTT target groups keep their configured IDs.

| Slot | Input | Group ID | Group name |
| --- | --- | --- | --- |
| 3-11 | `SW3`-`SW11` | `0xC600`-`0xC608` | `homething-c6-button-<slot>` |
| 12-16 | Wheel right, up, press, down, left | `0xC609`-`0xC60D` | `homething-c6-button-<slot>` |
| 17-18 | Reserved for IR-only rotation slots | `0xC60E`-`0xC60F` | Not created by this firmware |
| 19-20 | `SW2`, `SW1` | `0xC610`, `0xC611` | `homething-c6-button-<slot>` |

Reserve `0xC600` through `0xC611` for this remote. Do not use these group IDs
for another device. Change `zigbee_group_id_base` only before any training.

The private group name uses the configured `device_name`. The firmware does not
delete or rename legacy `homething-c6-button-*` groups.

## Toggle playback

Outside receiver mode, a trained input sends an On/Off Toggle command to its
assigned group. The command leaves endpoint 1 and uses group broadcast delivery.

The command does not wait for a coordinator, MQTT broker, or target state report.
It works when the remote and target are on the same Zigbee network but Wi-Fi is
unavailable.

Toggle does not mean "set on" or "set off." Each target changes its current
On/Off state. Train one button only with targets that must toggle together.

## Training failures and retraining

Training fails if MQTT is disconnected or the group snapshot is unavailable.
It also fails if no valid state transition arrives in 60 seconds. A failed or
timed-out Zigbee2MQTT request also stops training.

On a training failure, all LEDs flash red. The old local assignment remains.
If the remote removed the old target first, it asks Zigbee2MQTT to add it back.

A failure keeps the cycle at the Zigbee stage. The next tap moves to the voice
stage or the clear stage. A tap during training also stops the wait.

The training timeout belongs to the Zigbee manager alone. A device target needs
a group request after the transition, and that request has its own deadline.

Retraining a button removes its old target from that button group, then adds the
new target. The remote keeps the old assignment until the new group membership
and flash write succeed.

Clear a button with the fourth tap in the full assignment cycle. `SW2` uses its
third tap because it has no voice stage. Clearing disables local playback first.
For a device assignment, the remote also requests member removal when MQTT is
connected. Clearing an existing group assignment does not change that group.

If MQTT is offline during clearing, the button stays locally clear. Remove the
old target from its Zigbee2MQTT group before you reuse that group outside this
firmware.

## MQTT input filters

The remote uses QoS 1 subscriptions:

- One exact topic for each allowed target receives states for training.
- `<base topic>/bridge/groups` caches known groups.
- Exact group-add and member-add or member-remove response topics match requests.

The narrow subscriptions exclude large retained bridge inventory messages.

The remote ignores all non-allowed target topics. It also ignores subtopics,
invalid JSON, messages without `state`, and states other than `ON` or `OFF`.

## LED meanings

`D5` shows Zigbee state at all times. It is off before the Zigbee stack starts,
solid green when connected, and pulsing red when disconnected.

Receiver mode uses `D3` and `D4` only, so `D5` stays readable during training.

| LEDs | Meaning |
| --- | --- |
| `D3` and `D4` solid blue | Receiver mode waits for an input. |
| `D3` and `D4` blue chase | The selected input waits for an IR code. |
| `D3` and `D4` pulsing yellow | The selected input waits for a Zigbee2MQTT state transition. |
| `D3` and `D4` solid green | IR or Zigbee assignment saved. |
| `D3` and `D4` flash red | IR, MQTT, Zigbee2MQTT, or flash operation failed. |
| `D3` and `D4` pulsing blue | The selected input now starts Assist. |
| `D3` and `D4` amber | The selected input is clear. |
