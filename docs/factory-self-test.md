# Factory self-test

This procedure tests one assembled homeThing C6 board with the factory firmware. The test needs no computer or Wi-Fi credentials.

Each check shows its result on the status LEDs round the wheel. The board is a V3 board, which has six status LEDs.

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

## How to read the diagrams

Each diagram in this procedure shows the front face, the face with the wheel and the buttons `SW1` to `SW11`. Every position is as seen from the front. An orange outline marks a control to press. A blue ring marks the LED that answers.

![Front face of the remote with the six status LEDs named round the wheel. D3 is at the top left for the microphone, D6 at the top center for IR transmit, D4 at the top right for IR receive, D5 at the bottom right for the battery, D7 at the bottom center for USB power, and D2 at the bottom left for the buttons and wheel.](readme-assets/self-test-led-map.svg)

This map names the check that each status LED carries. Each step heading also names its LED.

## Procedure

Do the steps in this sequence. If a step fails, continue with the next step. The board fails if any check fails.

If the ring goes dark before step 9, the board went to sleep. Press `SW3` to wake it, then start again at step 1.

### Step 1: Power on and boot animation

![Front face of the remote with the boot animation. Arrows run clockwise round the wheel in chain order from D2 at the bottom left, through D3 at the top left, D6 at the top center, D4 at the top right and D5 at the bottom right, to D7 at the bottom center. D2 lights red, D3 azure, D6 magenta, D4 green, D5 blue and D7 cyan.](readme-assets/self-test-step-1-boot.svg)

1. Put the board front up in your hand or on a non-conductive surface.
2. Look at the ring and connect the charged battery to `J1`. The board starts.
3. Watch the boot animation.
4. Connect USB power.

The boot animation is the animation of the full firmware. It lights the LEDs in chain order, and it gives each LED its own color. The diagram above and the section "Color reference" give the color of each LED.

- Pass: The wave goes clockwise two times, and each LED lights with its own color.
- Fail: An LED stays dark in both laps. That LED or its connection in the chain has a fault.
- Fail: A color is at the wrong position. The chain order has a fault at that LED.

After the boot animation, the first overview appears. Each check LED has two states:

| Color | Meaning |
| --- | --- |
| Dim amber | The check did not pass yet |
| Green | The check passed |

All six check LEDs are dim amber at this point. Each later step turns its own LED green.

Other patterns cover an overview for a short time. The section "Color reference" names each pattern and its cause.

If the ring stays dark when you connect the battery, connect USB power. If the board then starts, the battery is flat or `J1` has a fault.

### Step 2: Buttons and wheel (`D2`)

![Front face of the remote with every input marked for a press: the two buttons above the wheel, the nine buttons below it, the wheel direction ring and the wheel center. D2, at the bottom left of the wheel, answers.](readme-assets/self-test-step-2-inputs.svg)

1. Press and hold each button, `SW1` to `SW11`, for less than 1 s. Then release it.
2. Press each wheel direction for less than 1 s: up, down, left, right, and the wheel center.
3. Turn the wheel one step clockwise.
4. Turn the wheel one step counterclockwise.

While you hold an input, the ring shows two colors. The top half shows one color, and the bottom half shows another color. The pair of colors identifies the input.

The top half is `D3`, `D6`, and `D4`. The bottom half is `D2`, `D5`, and `D7`.

The two colors of an input are never the same. The section "Color reference" gives the pair of each input.

A held input never shows one color on all LEDs. If all LEDs show magenta, the board transmits IR. Step 5 shows that function.

Each wheel step moves one white LED one position round the ring, in the direction of the turn.

- Pass: Each input changes the ring, and `D2` is green after the last input.
- Fail: An input does not change the ring, or `D2` stays dim amber.

A hold of 2 s on `SW1`, `SW2`, or the wheel center starts a different function.

A hold of 3 s on `SW3` starts the sleep check after release.

### Step 3: Microphone (`D3`)

![Front face of the remote with the wheel center marked for a 2 s hold and the microphone hole marked at the top center of the face. D3, at the top left of the wheel, answers.](readme-assets/self-test-step-3-microphone.svg)

The diagram shows the microphone hole. Do not cover this hole.

1. Press and hold the wheel center for 2 s. The ring changes to the VU meter.
2. Speak toward the front of the board, at a distance of approximately 30 cm.
3. Press and hold the wheel center for 2 s again. The ring goes back to the overview.

In the VU meter, a green bar grows clockwise from `D2` with the sound level. The last LED of the bar is red. Unlit positions show dim blue.

This check needs no other action from you.

- Pass: The bar moves with your voice, and `D3` is green.
- Fail: The bar does not move, or `D3` stays dim amber. The microphone or its sound hole has a fault.

### Step 4: IR receive (`D4`)

![Front face of the remote for the IR receive check. The sheet marks no button, because the receiver is on the back of the board. D4, at the top right of the wheel, answers.](readme-assets/self-test-step-4-ir-receive.svg)

The IR receiver `U2` is on the back of the board, and it receives through the back face.

1. Hold the board with its back toward the IR remote, at a distance of 0.3 m to 1 m.
2. Press a button on the IR remote.

- Pass: The ring flashes white one time, and `D4` is green.
- Fail: The ring does not flash after three presses, and `D4` stays dim amber.

### Step 5: IR transmit (`D6`)

![Front face of the remote with the top right button SW1 marked for a 2 s hold, and the IR LED D1 marked inside the top end. D6, at the top center of the wheel, answers.](readme-assets/self-test-step-5-ir-transmit.svg)

1. Start the camera of the phone. Aim it at `D1` on the top edge of the board.
2. Press and hold `SW1` for 2 s.
3. When the ring flashes magenta, release `SW1`.
4. Look at the phone screen for 3 s.

- Pass: On the phone screen, `D1` flashes 15 times at the same rate as the ring.
- Fail: The phone screen shows no light from `D1`.

`D6` turns green when the transmit ends. `D6` shows only that the firmware sent the bursts, so use the camera to see the light from `D1`.

### Step 6: Battery (`D5`)

![Front face of the remote for the battery check. The sheet marks no button, because the step disconnects USB power. D5, at the bottom right of the wheel, answers.](readme-assets/self-test-step-6-battery.svg)

1. Disconnect USB power. Keep the battery connected. The ring flashes orange one time.
2. Wait 10 s.

- Pass: The board stays on, and `D5` is green.
- Fail: The board turns off when you disconnect USB power. This shows a fault at the battery or at `J1`.
- Fail: `D5` stays dim amber.

The battery check accepts only a reading on battery power, so USB power must stay off until step 7.

### Step 7: USB power (`D7`)

![Front face of the remote for the USB power check. The sheet marks no button, because the step connects USB power again. D7, at the bottom center of the wheel, answers.](readme-assets/self-test-step-7-usb-power.svg)

1. Connect USB power again. Keep the battery connected.

- Pass: The ring flashed orange at step 6, then cyan at this step, and `D7` is green.
- Fail: A connection or disconnection gives no flash, or `D7` stays dim amber.

### Step 8: Radios (`D2`, second overview)

![Front face of the remote with the top left button SW2 marked for a 2 s hold, which changes to the second overview. D5, at the bottom right of the wheel, is then the dim blue page indicator, and D2, at the bottom left, answers the radio check.](readme-assets/self-test-step-8-radios.svg)

1. Make sure that a nearby Wi-Fi access point or phone hotspot sends a network name.
2. Hold `SW2` for 2 s, then release it. The second overview appears.
3. Wait up to 60 s for the result on `D2`.

`SW2` has no other hold function. Only one overview is visible at a time.

The second overview shows these LEDs:

| LED | Second overview |
| --- | --- |
| `D2` | Radio check |
| `D3` | Sleep and wake check |
| `D5` | Dim blue page indicator |
| All other LEDs | Off |

The dim blue `D5` identifies the second overview. It has no battery meaning on this page.

- Pass: `D2` is green.
- Fail: `D2` is red or still dim amber after the wait.

A later scan can change red to green.

### Step 9: Sleep and wake (`D3`, second overview)

![Front face of the remote with SW3, the top left button below the wheel, marked for the 3 s hold that sleeps the board and for the press that wakes it. D5, at the bottom right of the wheel, is the dim blue page indicator, and D3, at the top left, answers the sleep and wake check.](readme-assets/self-test-step-9-sleep-wake.svg)

Do this step last. The shutdown and restart make this the slowest operator step. Do the first part of the section "Result" before you start.

1. Keep the battery and USB power connected.
2. Hold `SW3` for 3 s, until the ring flashes dark blue.
3. Release all buttons and wheel directions at the dark blue flash.
4. After the ring goes dark, wait 5 s for the shutdown to end.
5. Press and hold `SW3` until the boot animation starts. Then release it.
6. Wait for the boot animation to end.

The `SW3` hold works on both overviews and in the VU meter. You do not have to change the page first.

While the sleep request waits for the release of all inputs, `D3` shows cyan on the second overview.

- Pass: The ring went dark, the next button press started the board, and the second overview returns with `D3` green.
- Fail: The board does not sleep, does not wake, or `D3` stays dim amber after the boot animation.

The deliberate sleep can start with USB power present. It cannot interrupt Wi-Fi setup or the install of the full firmware.

If the board refuses the sleep request, release `SW3`. Then hold it again.

## Result

The board passes only when every check LED is green. Make this check in two parts.

Do the first part before step 9:

1. On the second overview, make sure that `D2` is green.
2. Hold `SW2` to change to the first overview.
3. Make sure that all check LEDs on the first overview are green.

These first overview LEDs must be green at the same time: `D2`, `D3`, `D6`, `D4`, `D5`, and `D7`.

Do the second part after the wake of step 9. On the second overview, make sure that `D3` is green.

The wake starts a fresh test, so the other LEDs show dim amber again. Keep the board in the same powered session until you finish both parts.

If a check LED stays dim amber or red, the board fails that check. No paper or computer is necessary for the final result.

## Parts not covered

This procedure does not test the Qwiic connector `J2`. That check needs a known Qwiic device at the station.

This procedure does not test battery charging, because that check takes too long for the station.

An operator cannot detect faults in `J2` or the battery charge circuit with this procedure.

## Shipped state

To ship a board after the test, disconnect USB power. If the battery stays connected, the board sleeps after 5 minutes.

The test does not change the flash. Wi-Fi setup stores the network in flash. If a board received a Wi-Fi network or the full firmware, do these steps:

1. Erase the full flash with `esptool.py --chip esp32c6 erase_flash`.
2. Write the factory firmware at offset `0x0`, as the section "Firmware" shows.

## Color reference

These tables hold the colors that the steps use.

### Boot animation colors

Step 1 shows this color at each LED, in chain order.

| LED | Boot animation color |
| --- | --- |
| `D2` | Red |
| `D3` | Azure |
| `D6` | Magenta |
| `D4` | Green |
| `D5` | Blue |
| `D7` | Cyan |

The azure of `D3` is a lighter blue than the blue of `D5`.

### Held input colors

Step 2 shows this pair of colors while you hold an input. A group of four inputs shares a top color.

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

### Ring patterns

These patterns cover an overview for a short time.

| Ring | Cause |
| --- | --- |
| Two colors, one on the top half and one on the bottom half | You hold a button or a wheel direction |
| One white LED | You turned the wheel one step |
| One white flash | The IR receiver received a frame from a remote |
| Magenta flashes for 3 s | The IR LED transmits after the `SW1` hold |
| One cyan flash | You connected USB power |
| One orange flash | You disconnected USB power |
| Dark blue ring for 0.5 s | The `SW3` hold armed the sleep check |
| Red ring for 1.5 s | The board refused the sleep request |
| Green bar on dim blue | The VU meter is on |
| Blue ring that fills | The board installs the full firmware |
