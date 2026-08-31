"""Regression checks for production remote input and status-light wiring."""

from pathlib import Path
import re
import unittest


CONFIG = Path(__file__).parents[2] / "c6remote.yaml"


def button_pin(config: str, button: int) -> int:
    match = re.search(
        rf"name: Button {button}\n    pin:\n      <<: \*button_1\n      number: (\d+)",
        config,
    )
    if match is None:
        raise AssertionError(f"Button {button} pin not found")
    return int(match.group(1))


def status_light_entry(config: str) -> str:
    match = re.search(
        r"  - platform: esp32_rmt_led_strip\n    id: status_light(?P<entry>[\s\S]*?)\n\nswitch:",
        config,
    )
    if match is None:
        raise AssertionError("Status Light entry not found")
    return match.group("entry")


class ProductionConfigTest(unittest.TestCase):
    def test_sw9_and_sw10_follow_silkscreen_wiring(self) -> None:
        """Catches swapping PCF8575 P8 and P9 under Button 9 and Button 10."""
        config = CONFIG.read_text()
        self.assertEqual(button_pin(config, 9), 9)
        self.assertEqual(button_pin(config, 10), 8)

    def test_every_assignable_input_runs_the_tap_cycle(self) -> None:
        """Catches an input that lost its slot or took a neighbour's slot."""
        config = CONFIG.read_text()
        expected = {f"Button {number}": number for number in range(3, 12)}
        expected["Button 1"] = 20
        expected.update(
            {
                "Encoder Right": 12,
                "Encoder Up": 13,
                "Encoder Press": 14,
                "Encoder Down": 15,
                "Encoder Left": 16,
            }
        )
        for name, slot in expected.items():
            match = re.search(rf"name: {name}\n[\s\S]*?ir_ui\.tap\((\d+), IrUi::Tap::(\w+)\)", config)
            if match is None:
                raise AssertionError(f"{name} does not call ir_ui.tap")
            self.assertEqual(int(match.group(1)), slot, name)
            self.assertEqual(match.group(2), "FULL", name)

        self.assertIn("ir_ui.tap(19, IrUi::Tap::NO_VOICE);", config)
        self.assertIn("ir_ui.tap(17, IrUi::Tap::ARM_ONLY);", config)
        self.assertIn("ir_ui.tap(18, IrUi::Tap::ARM_ONLY);", config)

    def test_status_light_drives_all_four_cascaded_leds(self) -> None:
        config = CONFIG.read_text()
        self.assertRegex(
            config,
            r"platform: esp32_rmt_led_strip\n    id: status_light[\s\S]*?num_leds: 4",
        )

    def test_sw1_is_push_to_talk_for_home_assistant_assist(self) -> None:
        """SW2 owns the receiver-mode hold, so SW1 carries push to talk."""
        config = CONFIG.read_text()
        self.assertRegex(config, r"wifi:[\s\S]*?\n  power_save_mode: none")
        self.assertRegex(
            config,
            r"esphome:[\s\S]*?\n  on_boot:[\s\S]*?\n    - script.execute: show_idle_status"
            r"[\s\S]*?wifi:[\s\S]*?\n  on_connect:\n    - script.execute: show_idle_status"
            r"[\s\S]*?\n  on_disconnect:\n    - script.execute: show_idle_status",
        )
        self.assertRegex(
            config,
            r"voice_assistant:",
        )
        self.assertRegex(
            config,
            r"id: board_microphone[\s\S]*?sample_rate: 16000",
        )
        # The voice stage is a shared anchor, so it is defined on Button 1.
        self.assertRegex(
            config,
            r"name: Button 1\n    pin: &button_1[\s\S]*?"
            r"\n      - lambda: ir_ui\.tap\(20, IrUi::Tap::FULL\);[\s\S]*?"
            r"\n      - if: &start_learned_voice",
        )
        start_voice = config.split("- if: &start_learned_voice", 1)[1].split("on_release:", 1)[0]
        self.assertRegex(
            start_voice,
            r"lambda: return ir_ui\.take_voice_start\(\);[\s\S]*?"
            r"id\(voice_led_state\) = 1;[\s\S]*?"
            r"id\(mic_meter_active\) = true;[\s\S]*?"
            r"effect: Status Indicators[\s\S]*?"
            r"voice_assistant\.start:",
        )
        release = config.split("on_release: &assignable_release", 1)[1].split("- platform:", 1)[0]
        self.assertRegex(
            release,
            r"lambda: return ir_ui\.release\(\);[\s\S]*?voice_assistant\.stop:",
        )

    def test_voice_state_reaches_the_top_leds_and_cleans_up(self) -> None:
        """Catches missing PTT feedback or LEDs left powered after Assist ends."""
        config = CONFIG.read_text()
        # D3 and D4 are the top pair. D2 and D5 keep Wi-Fi and API state, so the
        # voice stages cannot take the whole strip.
        effect = status_light_entry(config).split("name: Status Indicators", 1)[1]
        effect = effect.split("- addressable_lambda:", 1)[0]
        for value in (1, 2, 3, 4):
            self.assertIn(f"id(voice_led_state) == {value}", effect)
        self.assertIn("it[1] =", effect)
        self.assertIn("it[2] =", effect)
        self.assertIn("wifi::global_wifi_component->is_connected()", effect)
        self.assertIn("api::global_api_server->is_connected()", effect)
        self.assertIn("id(mic_level) = 0.0f;", effect)
        for value, color in ((1, "Color(192, 48, 0)"), (2, "Color(0, 48, 255)"),
                             (3, "Color(96, 0, 96)"), (4, "Color(255, 0, 0)")):
            state = effect.split(f"id(voice_led_state) == {value}", 1)[1]
            self.assertIn(color, state)
        # The stages are set by the pipeline callbacks, not by the button.
        for trigger, value in (("on_listening", 2), ("on_stt_vad_end", 3), ("on_error", 4)):
            block = config.split(f"  {trigger}:", 1)[1].split("\n  on_", 1)[0]
            self.assertIn(f"id(voice_led_state) = {value};", block)
        self.assertRegex(
            config,
            r"voice_assistant:[\s\S]*?\n  on_end:\n    - script.execute: stop_voice_listening",
        )
        self.assertRegex(
            config,
            r"voice_assistant:[\s\S]*?\n  on_error:[\s\S]*?"
            r"\n    - script.execute: stop_voice_listening",
        )
        self.assertRegex(
            config,
            r"voice_assistant:[\s\S]*?\n  on_client_disconnected:[\s\S]*?"
            r"\n    - script.execute: stop_voice_listening",
        )
        self.assertRegex(
            config,
            r"id: stop_voice_listening[\s\S]*?"
            r"lambda: id\(mic_meter_active\) = false;[\s\S]*?"
            r"script.execute: show_idle_status",
        )

    def test_only_the_stop_microphone_button_remains(self) -> None:
        """The bench buttons were dropped: the microphone now runs from Assist,
        and the IR burst duplicated a learned slot."""
        config = CONFIG.read_text()
        self.assertNotIn("name: Start Microphone Test", config)
        self.assertNotIn("name: Send Short IR Test Burst", config)
        self.assertNotIn("microphone.capture:", config)
        self.assertRegex(
            config,
            r"name: Stop Microphone Test\n    on_press:"
            r"\n      - microphone.stop_capture:[\s\S]*?"
            r"\n      - script.execute: stop_voice_listening",
        )

    def test_idle_status_defers_to_the_microphone_meter(self) -> None:
        """A meter run must survive a Wi-Fi event, which also calls this script."""
        config = CONFIG.read_text()
        idle = config.split("- id: show_idle_status", 1)[1].split("\n  - id: ", 1)[0]
        self.assertIn("lambda: return !id(mic_meter_active);", idle)
        self.assertIn("id(voice_led_state) = 0;", idle)
        self.assertIn("effect: Status Indicators", idle)
        self.assertIn("brightness: 50%", idle)
        # One effect now carries the Wi-Fi state, so there is no second effect to
        # switch to and no colour choice left in the script.
        self.assertNotIn("effect: WiFi Connecting", config)
        self.assertNotIn("name: WiFi Connecting", config)
        self.assertRegex(
            config,
            r"id: stop_voice_listening[\s\S]*?"
            r"lambda: id\(mic_meter_active\) = false;[\s\S]*?"
            r"script.execute: show_idle_status",
        )

    def test_microphone_interval_reports_and_resets_raw_peak(self) -> None:
        config = CONFIG.read_text()
        self.assertRegex(
            config,
            r"const float level = std::min\(1\.0f, std::max\(0\.0f,\s*"
            r"\(static_cast<float>\(peak\) - 24\.0f\) / \(512\.0f - 24\.0f\)\)\);",
        )
        self.assertRegex(
            config,
            r"if \(peak > id\(mic_peak\)\)"
            r"\n            id\(mic_peak\) = peak;",
        )
        self.assertRegex(
            config,
            r'ESP_LOGI\("microphone", "Captured %u bytes/s, level %.3f, peak %u",'
            r"[\s\S]*?id\(mic_bytes\) = 0;"
            r"\n                id\(mic_peak\) = 0;",
        )


if __name__ == "__main__":
    unittest.main()
