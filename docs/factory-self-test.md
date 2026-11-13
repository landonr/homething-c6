# Factory self-test

This procedure tests one assembled homeThing C6 board with the factory firmware. The test needs no computer or Wi-Fi credentials.

Each check shows its result on the status LEDs round the wheel. The procedure is for V3 boards, which have six status LEDs.

A V2 board is a bench unit with four status LEDs. It does only the checks for the parts that V2 has. The section "V3 and V2 boards" lists the differences.

## Firmware

The factory firmware file is `homething-c6-provisioning-<version>.factory.bin`. It is an asset of each firmware release on GitHub.

Write the file to the board at offset `0x0` over USB. Erase the flash first, so that the board has no saved Wi-Fi network. This example uses `esptool`:

```sh
esptool.py --chip esp32c6 erase_flash
esptool.py --chip esp32c6 write_flash 0x0 homething-c6-provisioning-<version>.factory.bin
```

The same firmware does the Wi-Fi setup for the customer. Do not give the board a Wi-Fi network during the test. If the board receives a network, it installs the full firmware. The self-test is then gone.

## Equipment

You need these items:

- A USB-C cable and a 5 V USB power supply.
- A charged 1-cell Li-ion battery with a Molex PicoBlade `51021-0200` plug for `J1`.
- An IR remote control, for example a TV remote.
- A phone with a camera.
- A nearby Wi-Fi access point or phone hotspot that sends a network name. The board does not join this network.

Some phone main cameras block infrared light. The front camera of most phones shows it.

## Board orientation

All positions in this procedure are as seen from the front of the board. The front has the wheel and the buttons `SW1` to `SW11`.

The top of the board is the end with the microphone hole and the IR LED `D1`. The bottom is the end with the USB-C connector.

## LED positions

Each diagram in this procedure shows the front face. An orange outline marks a control to press. A blue ring marks the LED that answers.

![Front face of the remote with the six status LEDs named round the wheel. D3 is at the top left for the microphone, D6 at the top center for IR transmit on V3, D4 at the top right for IR receive, D5 at the bottom right for the battery, D7 at the bottom center for USB power on V3, and D2 at the bottom left for the buttons and wheel.](readme-assets/self-test-led-map.svg)

| LED | Check | Board |
| --- | --- | --- |
| `D2` | Buttons and wheel | V2 and V3 |
| `D3` | Microphone | V2 and V3 |
| `D6` | IR transmit | V3 |
| `D4` | IR receive | V2 and V3 |
| `D5` | Battery | V2 and V3 |
| `D7` | USB power | V3 |

At power-on, the firmware shows this first overview after the boot animation. Each check LED has two states:

| Color | Meaning |
| --- | --- |
| Dim amber | The check did not pass yet |
| Green | The check passed |

Hold `SW2` for 2 s, then release it, to change between the first and second overviews. `SW2` has no other hold function.

The second overview shows the radio and sleep checks on both board versions. Only one overview is visible at a time.

| LED | Second overview |
| --- | --- |
| `D2` | Radio check |
| `D3` | Sleep and wake check |
| `D5` | Dim blue page indicator |
| All other LEDs | Off |

The dim blue `D5` identifies the second overview. It has no battery meaning on this page.

On the second overview, `D2` shows dim amber for a pending radio check, green for a pass, or red for a failure.

On this page, `D3` shows dim amber before the sleep check, cyan for a sleep request, and green after a valid wake.

The sleep request and its refusal use the whole ring, so you see both on either overview and in the VU meter.

Other patterns cover the overview for a short time:

| Ring | Cause |
| --- | --- |
| Two colors, one on the top half and one on the bottom half | You hold a button or a wheel direction |
| One white LED | You turned the wheel one step |
| One white flash | The IR receiver received a frame from a remote |
| Magenta flashes for 3 s | The IR LED transmits after the `SW1` hold |
| One cyan flash | You connected USB power (V3) |
| One orange flash | You disconnected USB power (V3) |
| Dark blue ring for 0.5 s | The `SW3` hold armed the sleep check |
| Red ring for 1.5 s | The board refused the sleep request |
| Green bar on dim blue | The VU meter is on |
| Blue ring that fills | The board installs the full firmware |

## Procedure

Do the steps in this sequence. If a step fails, continue with the next step. The board fails if any check fails.

Before a fresh test, disconnect both USB power and the battery. Then start at step 1.

The battery keeps the results if you disconnect USB power alone.

### Step 1: Power on and boot animation

![Front face of the remote with the boot animation. Arrows run clockwise round the wheel in chain order from D2 at the bottom left, through D3 at the top left, D6 at the top center, D4 at the top right and D5 at the bottom right, to D7 at the bottom center. D2 lights red, D3 azure, D6 magenta, D4 green, D5 blue and D7 cyan.](readme-assets/self-test-step-1-boot.svg)

1. Put the board front up in your hand or on a non-conductive surface.
2. Look at the ring and connect the charged battery to `J1`. The board starts.
3. Make sure that a wave of color goes clockwise round the ring two times. This is the boot animation.
4. Make sure that each LED lights with the color of its row in the table below.
5. Connect USB power.

The boot animation is the animation of the full firmware. It lights the LEDs in chain order, and it gives each LED its own color.

| LED | Boot animation color |
| --- | --- |
| `D2` | Red |
| `D3` | Azure |
| `D6` | Magenta |
| `D4` | Green |
| `D5` | Blue |
| `D7` | Cyan |

The azure of `D3` is a lighter blue than the blue of `D5`. A V2 board shows only red, azure, green, and blue.

- Pass: The wave goes clockwise two times, and each LED lights with the color of its row.
- Fail: An LED stays dark in both laps. That LED or its connection in the chain has a fault.
- Fail: A color is at the wrong position. The chain order has a fault at that LED.

The boot animation gives one color to each LED, so it cannot show that an LED makes more than one color. Step 2 lights each LED in four or more colors, so it finds an LED that makes only one color.

After the boot animation, each check LED shows dim amber. A wake from deep sleep keeps the earlier results.

If the ring stays dark when you connect the battery, connect USB power. If the board then starts, the battery is flat or `J1` has a fault.

### Step 2: Buttons and wheel (`D2`)

![Front face of the remote with every input marked for a press: the two buttons above the wheel, the nine buttons below it, the wheel direction ring and the wheel center. D2, at the bottom left of the wheel, answers.](readme-assets/self-test-step-2-inputs.svg)

1. Press and hold each button, `SW1` to `SW11`, for less than 1 s. Then release it.
2. Press each wheel direction for less than 1 s: up, down, left, right, and the wheel center.
3. Turn the wheel one step clockwise.
4. Turn the wheel one step counterclockwise.

While you hold an input, the ring shows two colors. The top half shows one color, and the bottom half shows another color. The pair of colors identifies the input.

On a V3 board, the top half is `D3`, `D6`, and `D4`. The bottom half is `D2`, `D5`, and `D7`.

On a V2 board, the top half is `D3` and `D4`. The bottom half is `D2` and `D5`.

The two colors of an input are never the same. A group of four inputs shares a top color.

| Input | Top half | Bottom half |
| --- | --- | --- |
| `SW1` | Red | Green |
| `SW2` | Red | Blue |
| `SW3` | Red | White |
| `SW4` | Red | Magenta |
| `SW5` | Green | Red |
| `SW6` | Green | Blue |
| `SW7` | Green | White |
| `SW8` | Green | Magenta |
| `SW9` | Blue | Green |
| `SW10` | Blue | Red |
| `SW11` | Blue | White |
| Wheel right | Blue | Magenta |
| Wheel up | White | Red |
| Wheel center | White | Green |
| Wheel down | White | Blue |
| Wheel left | White | Magenta |

A held input never shows one color on all LEDs. If all LEDs show magenta, the board transmits IR. Step 5 shows that function.

Each wheel step moves one white LED one position round the ring, in the direction of the turn.

- Pass: Each input changes the ring, and `D2` is green after the last input.
- Fail: An input does not change the ring, or `D2` stays dim amber.

A hold of 2 s on `SW1`, `SW2`, or the wheel center starts a different function.

A hold of 3 s on `SW3` starts the sleep check after release. This hold works on both overviews and in the VU meter.

The sleep check is 1 s longer than the other holds, so a shorter hold in this step cannot sleep the board.

### Step 3: Microphone (`D3`)

![Front face of the remote with the wheel center marked for a 2 s hold and the microphone hole marked at the top center of the face. D3, at the top left of the wheel, answers.](readme-assets/self-test-step-3-microphone.svg)

The diagram shows the microphone hole. Do not cover this hole.

1. Press and hold the wheel center for 2 s. The ring changes to the VU meter.
2. Speak toward the front of the board, at a distance of approximately 30 cm.
3. Press and hold the wheel center for 2 s again. The ring goes back to the overview.

In the VU meter, a green bar grows clockwise from `D2` with the sound level. The last LED of the bar is red. Unlit positions show dim blue.

`D3` turns green when the level crosses the threshold. This check needs no other action from you.

- Pass: The bar moves with your voice, and `D3` is green.
- Fail: The bar does not move, or `D3` stays dim amber.

If the bar does not move with a voice, the microphone or its sound hole has a fault.

### Step 4: IR receive (`D4`)

![Front face of the remote for the IR receive check. The sheet marks no button, because the receiver is on the back of the board. D4, at the top right of the wheel, answers.](readme-assets/self-test-step-4-ir-receive.svg)

The IR receiver `U2` is on the back of the board, and it receives through the back face.

1. Hold the board with its back toward the IR remote, at a distance of 0.3 m to 1 m.
2. Press a button on the IR remote.

- Pass: The ring flashes white one time, and `D4` is green.
- Fail: The ring does not flash after three presses, and `D4` stays dim amber.

The board ignores its own IR transmit, so step 5 cannot pass this step.

### Step 5: IR transmit (`D6` on V3)

![Front face of the remote with the top right button SW1 marked for a 2 s hold, and the IR LED D1 marked inside the top end. D6, at the top center of the wheel, answers on a V3 board.](readme-assets/self-test-step-5-ir-transmit.svg)

1. Start the camera of the phone. Aim it at `D1` on the top edge of the board.
2. Press and hold `SW1` for 2 s.
3. When the ring flashes magenta, release `SW1`.
4. Look at the phone screen for 3 s.

- Pass: On the phone screen, `D1` flashes 15 times at the same rate as the ring.
- Fail: The phone screen shows no light from `D1`.

On a V3 board, `D6` is green when the transmit ends. `D6` shows only that the firmware sent the bursts. Only the camera shows the light from `D1`.

The IR LED transmits only during this step. Each burst is 50 ms of 38 kHz carrier. No common IR protocol has a mark this long, so a TV near the board does not respond.

### Step 6: Battery (`D5`)

![Front face of the remote for the battery check. The sheet marks no button, because the step disconnects USB power. D5, at the bottom right of the wheel, answers.](readme-assets/self-test-step-6-battery.svg)

1. Disconnect USB power. Keep the battery connected.
2. Make sure that the board stays on. On a V3 board, the ring also flashes orange one time.
3. Wait 10 s.
4. Make sure that `D5` is green.

- Pass: The board stays on, and `D5` is green.
- Fail: The board turns off when you disconnect USB power. This shows a fault at the battery or at `J1`.
- Fail: `D5` stays dim amber.

On a V3 board, the battery check accepts only a reading on battery power. With USB power, the charger output can read in range without a battery.

On a V2 board, `D5` is green approximately 4 s after the board starts with the battery connected. The V2 check cannot tell a full battery from no battery while USB power is connected.

### Step 7: USB power (`D7`, V3 only)

![Front face of the remote for the USB power check. The sheet marks no button, because the step connects USB power again. D7, at the bottom center of the wheel, answers on a V3 board.](readme-assets/self-test-step-7-usb-power.svg)

Skip this check on a V2 board, because it has no USB detector. Connect USB power before step 8 on both board versions.

1. Connect USB power again. Keep the battery connected.
2. Make sure that the ring flashes cyan one time and `D7` is green.

- Pass: The ring flashed orange at step 6, then cyan at this step, and `D7` is green.
- Fail: A connection or disconnection gives no flash, or `D7` stays dim amber.

### Step 8: Radios (`D2`, second overview)

![Front face of the remote with the top left button SW2 marked for a 2 s hold, which changes to the second overview. D5, at the bottom right of the wheel, is then the dim blue page indicator, and D2, at the bottom left, answers the radio check.](readme-assets/self-test-step-8-radios.svg)

1. Make sure that a nearby Wi-Fi access point or phone hotspot sends a network name.
2. Hold `SW2` for 2 s, then release it. Make sure that `D5` is dim blue.
3. Wait up to 60 s for `D2` to turn green on this second overview.

The radio check needs a Wi-Fi scan with at least one access point. BLE Improv must also report a successful advertisement start.

The Wi-Fi scan needs no network connection or credentials. BLE Improv uses the existing Bluetooth controller and advertisement path.

- Pass: `D2` is green.
- Fail: `D2` is red after the wait.

The radio check turns red after 60 s from boot without a pass. Each scan has a 10 s timeout.

The board retries the scan every 15 s. A later successful check can change red to green.

This result confirms received Wi-Fi scan data and a successful BLE advertisement start. It does not measure radio range or antenna performance.

The station has no BLE receiver, so this check cannot confirm BLE reception over the air.

Do not give the board Wi-Fi credentials during this procedure.

### Step 9: Sleep and wake (`D3`, second overview)

![Front face of the remote with SW3, the top left button below the wheel, marked for the 3 s hold that sleeps the board and for the press that wakes it. D5, at the bottom right of the wheel, is the dim blue page indicator, and D3, at the top left, answers the sleep and wake check.](readme-assets/self-test-step-9-sleep-wake.svg)

Do this step last. The shutdown and restart make this the slowest operator step.

1. Keep the battery and USB power connected.
2. Hold `SW3` for 3 s, until the ring flashes dark blue. The flash shows that the board is ready to sleep.
3. Release all buttons and wheel directions at the dark blue flash.
4. After the ring goes dark, wait 5 s for the shutdown to end.
5. Press and hold `SW3` until the boot animation starts. Then release it.
6. Wait for the boot animation to end.
7. Make sure that the second overview returns, with dim blue `D5` and green `D2` and `D3`.

The `SW3` hold works on both overviews and in the VU meter. You do not have to change the page first.

The wake check uses the expander interrupt on `GPIO5`, its `R9` pull-up, the ext1 wake, and the wake stub.

`D3` passes only after the requested sleep, an ext1 wake, and the button capture in the wake stub.

The self-test keeps the earlier check results in RTC memory through deep sleep. No earlier check needs a repeat after wake.

- Pass: The ring went dark, the next button press started the board, and `D3` is green on the second overview.
- Fail: The board does not sleep, does not wake, or `D3` stays dim amber after the boot animation.

The deliberate sleep can start with V3 USB power present. It cannot interrupt Wi-Fi setup or the install of the full firmware.

If the ring flashes red for 1.5 s, the board refused sleep. Release `SW3` before another attempt.

A saved network, Wi-Fi activity, an Improv client, the install, or IR transmit can block this sleep request.

The board log names the condition that blocked the sleep. The procedure needs no log for a pass or a fail.

## Result

After step 9, use both overviews to check the final result. Keep the board in the same powered session.

1. On the second overview, make sure that `D2` and `D3` are green and `D5` is dim blue.
2. Hold `SW2` for 2 s, then release it, to show the first overview.
3. Make sure that all check LEDs on the first overview are green.

These first overview LEDs must be green at the same time:

- V3: `D2`, `D3`, `D6`, `D4`, `D5`, and `D7`.
- V2: `D2`, `D3`, `D4`, and `D5`.

The board passes only when both overviews meet these conditions. No paper or computer is necessary for the final result.

If a check LED stays dim amber or red, the board fails that check.

## Parts not covered

This procedure does not test the Qwiic connector `J2`. That check needs a known Qwiic device at the station.

This procedure does not test battery charging, because that check takes too long for the station.

An operator cannot detect faults in `J2` or the battery charge circuit with this procedure.

## Power and sleep

The status LEDs use power only while the board is awake. The board enters deep sleep after 5 minutes without input.

Automatic sleep does not start while USB power is connected to a V3 board. Step 9 can start sleep with USB power present.

The board does not sleep during Wi-Fi setup or during the install of the full firmware.

A button or a wheel input wakes the board. The self-test then starts again at the boot animation.

Both automatic and deliberate deep sleep keep the check results in RTC memory. The boot animation remains the same.

If the ring goes dark before step 9, press `SW3` to wake the board. Continue from the next incomplete step.

## Shipped state

The self-test keeps its results only in RTC memory. Deep sleep keeps these results, but a restart without deep sleep clears them.

A loss of all power also clears the results. Disconnect both USB power and the battery to start a fresh test.

To ship a board after the test, disconnect USB power. If the battery stays connected, the board sleeps after 5 minutes.

The results stay in RTC memory while the battery supplies power. The self-test writes no results to flash.

The test does not change the flash. Wi-Fi setup stores the network in flash. If a board received a Wi-Fi network or the full firmware, do these steps:

1. Erase the full flash with `esptool.py --chip esp32c6 erase_flash`.
2. Write the factory firmware at offset `0x0`, as the section "Firmware" shows.

## V3 and V2 boards

These checks and parts are on V3 boards only:

- `D6` and `D7`, the fifth and sixth status LEDs.
- The IR transmit indicator on `D6`.
- The USB power check on `D7`. It uses `usb_present_n` on `GPIO7` from `Q4`.
- The battery check on battery power only.
- The `ir_vdd` switch `Q3`, which the firmware turns on for the IR receive check.
- The `DMM-4026-B-I2S-R` microphone. A V2 board has the ICS-43434.

The diagrams show a V3 board. A V2 board has no `D6` and no `D7`, so ignore those two positions on a V2 board.

Both board versions have the radio check and the sleep and wake check on the second overview.

The firmware selects V3 when it is built with six status LEDs. The release workflow builds the factory firmware for V3.
