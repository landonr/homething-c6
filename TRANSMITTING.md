# IR transmitting

## Verified functions

- GPIO1 controls the IR transmitter circuit.
- Q1 operates as the low-side switch for D1.
- The transmitter uses a 38 kHz carrier with a 50 percent duty cycle.
- One v2 board transmitted NEC test frames to another v2 board.
- The receiver decoded `0x1234/0x78AB` every two seconds.
- The receiver logs raw pulse durations and decoded protocols.
- The receiver decodes Samsung power as `0xE0E040BF` with 32 bits.
- The receiver decodes Samsung volume up as `0xE0E0E01F` with 32 bits.
- D1 and Q1 transmitted the verified NEC test frames.
- The matrix runs of 2026-08-29 verified four transmit paths: Samsung encoder, `transmit_raw`, Pronto and repeats.
- All four paths transmit from both boards. A role swap gave the same result.
- The `x3` repeat with a 40 ms `wait_time` transmits correctly. Repeats up to `x5` at 100 ms also transmit.
- U2 decodes both a 36 kHz and a 38 kHz raw carrier.

## Root cause of the 2026-08-29 transmit failure

Both remotes run `c6remote.yaml`. Board B decoded real remotes: Samsung power `0xE0E040BF`, Samsung volume up `0xE0E0E01F`, and a Roku frame that decoded as JVC, LG, NEC and Pronto.

Board B never saw a transmission from board A, not even a raw frame. The dead actions were the SW10 and SW11 `remote_transmitter.transmit_samsung` with `repeat: times: 3, wait_time: 40ms`, and the SW3 `transmit_raw` replay of the learned 68-pulse Roku frame.

Only `c6remote-ir-tx-test.yaml` ever transmitted between the boards, with `transmit_nec` `0x1234/0x78AB` and `command_repeats: 2`.

The `status_light` in the `light:` block of `c6remote.yaml` uses `esp32_rmt_led_strip` and gave no `rmt_symbols`.

The ESPHome default for the ESP32-C6 is 96 symbols. The C6 has two RMT TX channels of 48 symbols each.

So the LED strip claimed both channels, and `remote_transmitter` failed at boot. The boot log shows the failure:

```text
E (534) rmt: rmt_tx_register_to_group(152): no free tx channels
[E][remote_transmitter:072]: Configuring RMT driver failed: ESP_ERR_NOT_FOUND (out of RMT symbol memory)
[E][component:188]:   remote_transmitter is marked FAILED: unspecified
[C][esp32_rmt_led_strip:273]:   RMT Symbols: 96
```

A failed transmitter returns from `send_internal()` with no output. The action layer still logs `Sending Samsung` and `Output button 3`.

As a result, the log of a dead transmitter looks the same as the log of a healthy one.

The test firmwares `c6remote-ir-tx-test.yaml` and `c6remote-test-common.yaml` set `rmt_symbols: 48` on the strip. Both worked.

The fix adds `rmt_symbols: 48` to `status_light` in `c6remote.yaml`. `scripts/tests/test_ir_learning.py` guards it.

The test `test_transmitter_reserves_shared_rmt_memory` now checks the LED strip as well as the transmitter.

To identify this fault again, read two boot log blocks. The `Remote Transmitter:` block must not report `Configuring RMT driver failed`.

The `ESP32 RMT LED Strip:` block must report `RMT Symbols: 48`.

After the fix, the SW10 and SW11 Samsung presets were removed from `c6remote.yaml`. All buttons SW3 to SW11 are now learn slots.

## Matrix test method

A temporary test firmware ran the bisect on 2026-08-29. The files were removed after the run.

A transmitter board cycled 11 variants under 4 environments from boot, at 3 s intervals. A receiver board logged every frame. A script flashed both boards over USB, captured both serial logs, and printed a result table.

The 11 variants all used the Samsung volume up payload `0xE0E0E01F`, except variants 1, 4 and 10:

1. `nec_control`, NEC `0x1234/0x78AB` with 2 repeats.
2. `samsung_x1`.
3. `samsung_x3_40ms`, the exact factory action.
4. `nec_x3_40ms`.
5. `raw_samsung_38k`.
6. `raw_samsung_x3_40ms`.
7. `raw_samsung_36k`.
8. `pronto_samsung`.
9. `samsung_x3_46ms`.
10. `raw_roku_replay`, the learned 68-pulse frame.
11. `samsung_x5_100ms`.

The sweep used 4 environments:

- A: the LED effect was off and the mic was off.
- B: the LED effect was on.
- C: mic capture was on.
- D: both were on.

Environment B wrote to the LED RMT channel without a stop. The Wi-Fi variant connected 34 s into a 158 s sweep.

The two boards were on `/dev/cu.usbmodem101` and `/dev/cu.usbmodem2101`.

## Results

- Run 1, `usbmodem2101` transmits and `usbmodem101` receives: 44 of 44 sends reached the receiver. Every variant decoded. The Samsung variants decoded as Samsung and Pronto. The NEC variants decoded as NEC, JVC, LG and Pronto. All environments logged `A started` and `A complete`, no run logged `rmt_transmit failed`, and the sending board saw its own reflection on every send.
- Run 2, the Wi-Fi transmitter firmware on the same boards: 44 of 44.
- Run 3, the roles swapped so that `usbmodem101` transmits: 44 of 44.
- Run 4, the factory `c6remote.yaml` on `usbmodem101` and the matrix receiver on `usbmodem2101`: the receiver saw nothing after three presses of `Send Short IR Test Burst` over the API. The boot log of the sending board showed the RMT failure above. This run isolated the fault.
- Run 5, factory `c6remote.yaml` with the fix on `usbmodem101`, matrix receiver on `usbmodem2101`: the boot log shows `RMT Symbols: 48` for the strip and no transmitter error. Three `Send Short IR Test Burst` presses over the API reached the receiver as `568,-10000` raw frames.
