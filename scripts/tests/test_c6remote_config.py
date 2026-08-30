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

    def test_sw2_is_push_to_talk_for_home_assistant_assist(self) -> None:
        config = CONFIG.read_text()
        self.assertRegex(config, r"wifi:[\s\S]*?\n  power_save_mode: none")
        self.assertRegex(
            config,
            r"esphome:[\s\S]*?\n  on_boot:\n    - script.execute: show_idle_status"
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
        self.assertRegex(
            config,
            r"name: Button 2\n    pin:\n      <<: \*button_1\n      number: 1"
            r"\n    on_press:\n      - voice_assistant.start:[\s\S]*?"
            r"\n          silence_detection: false"
            r"\n      - lambda: id\(mic_meter_active\) = true;"
            r"\n      - light.turn_on:"
            r"\n          id: status_light"
            r"\n          effect: Voice Listening"
            r"\n    on_release:\n      - voice_assistant.stop:"
            r"\n      - script.execute: stop_voice_listening",
        )

    def test_voice_listening_meter_and_cleanup(self) -> None:
        """Catches missing PTT feedback or LEDs left powered after Assist ends."""
        config = CONFIG.read_text()
        self.assertRegex(
            status_light_entry(config),
            r"effects:"
            r"\n      - addressable_lambda:"
            r"\n          name: Voice Listening"
            r"\n          update_interval: 50ms"
            r"\n          lambda: \|-"
            r"\n            if \(initial_run\) \{"
            r"\n              id\(mic_level\) = 0\.0f;"
            r"\n            \}"
            r"\n            it\.all\(\) = Color::BLACK;"
            r"\n            const int lit = std::min\(4, std::max\(0, static_cast<int>\(ceilf\(id\(mic_level\) \* 4\.0f\)\)\)\);"
            r"\n            for \(int i = 0; i < lit; i\+\+\)"
            r"\n              it\[i\] = Color\(0, 0, 255\);",
        )
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

    def test_microphone_test_uses_voice_listening_meter(self) -> None:
        config = CONFIG.read_text()
        self.assertRegex(
            config,
            r"name: Start Microphone Test\n    on_press:"
            r"\n      - lambda: id\(mic_level\) = 0\.0f;[\s\S]*?"
            r"\n      - microphone.capture:[\s\S]*?"
            r"\n      - light.turn_on:\n          id: status_light\n          effect: Voice Listening",
        )
        self.assertRegex(
            config,
            r"name: Stop Microphone Test\n    on_press:"
            r"\n      - microphone.stop_capture:[\s\S]*?"
            r"\n      - script.execute: stop_voice_listening",
        )

    def test_idle_wifi_status_defers_to_the_microphone_meter(self) -> None:
        config = CONFIG.read_text()
        self.assertRegex(
            config,
            r"id: show_idle_status[\s\S]*?"
            r"lambda: return !id\(mic_meter_active\);[\s\S]*?"
            r"wifi.connected:[\s\S]*?"
            r"red: 100%\s+green: 35%\s+blue: 0%\s+brightness: 15%",
        )
        self.assertRegex(
            config,
            r"id: show_idle_status[\s\S]*?wifi.connected:[\s\S]*?"
            r"effect: WiFi Connecting",
        )
        self.assertRegex(
            status_light_entry(config),
            r"name: WiFi Connecting\n          update_interval: 1s",
        )
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
