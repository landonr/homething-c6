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

    def test_assignable_input_starts_and_stops_home_assistant_assist(self) -> None:
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
        self.assertRegex(
            config,
            r"name: Button 1[\s\S]*?"
            r"lambda: return ir_ui\.take_voice_start\(\);[\s\S]*?"
            r"id\(voice_led_state\) = 1;[\s\S]*?"
            r"id\(mic_meter_active\) = true;[\s\S]*?"
            r"effect: Status Indicators[\s\S]*?"
            r"voice_assistant\.start:",
        )
        self.assertRegex(
            config,
            r"on_release: &assignable_release[\s\S]*?"
            r"lambda: return ir_ui\.release\(\);[\s\S]*?"
            r"voice_assistant\.stop:",
        )

    def test_voice_status_indicators_and_cleanup(self) -> None:
        """Catches missing PTT feedback or LEDs left powered after Assist ends."""
        config = CONFIG.read_text()
        self.assertRegex(
            status_light_entry(config),
            r"effects:"
            r"\n      - addressable_lambda:"
            r"\n          name: Status Indicators"
            r"\n          update_interval: 250ms"
            r"\n          lambda: \|-"
            r"\n            if \(initial_run\) \{"
            r"\n              id\(mic_level\) = 0\.0f;"
            r"\n            \}"
            r"\n            it\.all\(\) = Color::BLACK;"
            r"[\s\S]*?id\(voice_led_state\) == 1[\s\S]*?Color\(192, 48, 0\)"
            r"[\s\S]*?id\(voice_led_state\) == 2[\s\S]*?Color\(0, 48, 255\)"
            r"[\s\S]*?id\(voice_led_state\) == 3[\s\S]*?Color\(96, 0, 96\)"
            r"[\s\S]*?id\(voice_led_state\) == 4[\s\S]*?Color\(255, 0, 0\)",
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

    def test_stop_microphone_test_cleans_up(self) -> None:
        config = CONFIG.read_text()
        self.assertNotIn("name: Start Microphone Test", config)
        self.assertNotIn("microphone.capture:", config)
        self.assertRegex(
            config,
            r"name: Stop Microphone Test\n    on_press:"
            r"\n      - microphone.stop_capture:[\s\S]*?"
            r"\n      - script.execute: stop_voice_listening",
        )

    def test_idle_status_does_not_interrupt_active_microphone(self) -> None:
        config = CONFIG.read_text()
        self.assertRegex(
            config,
            r"id: show_idle_status[\s\S]*?"
            r"lambda: return !id\(mic_meter_active\);[\s\S]*?"
            r"id\(voice_led_state\) = 0;[\s\S]*?"
            r"effect: Status Indicators[\s\S]*?"
            r"brightness: 50%",
        )
        self.assertNotIn("WiFi Connecting", config)
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
