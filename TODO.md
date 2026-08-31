# Open tasks

## Remove the leftover `homething-c6-button-*` groups

The old training flow created one private Zigbee2MQTT group for each device
target. `homething-c6-button-9`, ID `0xC606`, still contains
`Kitchen Light Switch`, IEEE `0x54ef4410003ecd4c`.

Three private groups held that member after failed training runs. The
`homething-c6-button-3` and `homething-c6-button-8` members were removed on
2026-08-30. The `homething-c6-button-9` member was not.

The firmware no longer creates, joins, or reads these groups. A button now
stores a group ID that you pick in Zigbee2MQTT, so a leftover group cannot be
reached by accident. Removal is housekeeping, not a fix.

Delete each `homething-c6-button-*` group in the Zigbee2MQTT frontend. Confirm
first that no button on the `/buttons` page reports one of their IDs, `0xC600`
through `0xC611`.
