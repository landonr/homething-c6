# Open tasks

## Remove the stale `homething-c6-button-9` group member

Zigbee2MQTT group `homething-c6-button-9`, ID `0xC606`, still contains
`Kitchen Light Switch`, IEEE `0x54ef4410003ecd4c`. No button uses that group.

The remote reported the Zigbee assignment mask `0x00024` at boot on 2026-08-30.
Bit 2 is slot 5 and bit 5 is slot 8, so only `SW5` and `SW8` hold an assignment.
Slot 9 has no assignment, so the member is a leftover.

Three private groups held this member after failed training runs. The
`homething-c6-button-3` and `homething-c6-button-8` members were removed on
2026-08-30. The `homething-c6-button-9` member was not.

Remove it with this MQTT request:

```json
{"group": "homething-c6-button-9", "device": "Kitchen Light Switch", "transaction": 1}
```

Publish the request to `zigbee2mqtt/bridge/request/group/members/remove`. Then
read `zigbee2mqtt/bridge/response/group/members/remove` for `"status": "ok"`.

If a later training run assigns slot 9 to a device, do not remove the member
first. Read the assignment mask again before you remove it.

A stale member is not dangerous today, because the remote sends a Toggle command
only to the group in its own record. It becomes dangerous if slot 9 is trained
to a different device. That new device joins a group that already contains the
kitchen switch, so one button then toggles both.
