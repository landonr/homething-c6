"""Regression checks for local IR learning and playback."""

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[2]
CONFIG = (ROOT / "c6remote.yaml").read_text()
HEADER = (ROOT / "ir_learning.h").read_text()


class IrLearningTest(unittest.TestCase):
    def test_sw2_hold_enters_receiver_mode(self) -> None:
        self.assertIn("id: detect_receiver_hold", CONFIG)
        self.assertIn("- delay: 2s", CONFIG)
        self.assertIn('set_effect("IR Receiver")', CONFIG)

    def test_only_sw1_controls_voice_assistant(self) -> None:
        sw1 = CONFIG.split("name: Button 1", 1)[1].split("name: Button 2", 1)[0]
        sw2 = CONFIG.split("name: Button 2", 1)[1].split("name: Button 3", 1)[0]
        self.assertIn("voice_assistant.start:", sw1)
        self.assertIn("voice_assistant.stop:", sw1)
        self.assertNotIn("voice_assistant", sw2)

    def test_receiver_states_drive_all_leds(self) -> None:
        self.assertIn("name: IR Receiver", CONFIG)
        self.assertIn("id(ir_learn_state) == 1", CONFIG)
        self.assertIn("id(ir_learn_state) == 2", CONFIG)
        self.assertIn("id(ir_learn_state) == 3", CONFIG)
        self.assertIn("id(ir_learn_state) == 4", CONFIG)

    def test_successful_save_returns_to_ready_until_sw2(self) -> None:
        self.assertIn("id(ir_learn_state) == 3 && elapsed >= 1000", CONFIG)
        self.assertIn("press SW2 to leave", CONFIG)
        self.assertNotIn("elapsed >= 30000", CONFIG)
        sw2 = CONFIG.split("name: Button 2", 1)[1].split("name: Button 3", 1)[0]
        self.assertIn("lambda: return id(ir_learn_state) != 0;", sw2)
        self.assertIn("id(ir_learn_state) = 0;", sw2)

    def test_all_assignable_buttons_have_playback_paths(self) -> None:
        for button in range(3, 12):
            self.assertIn(f"ir_code_store.load({button}, id(ir_tx_code))", CONFIG)
        self.assertIn("ir_code_store.save(id(ir_target_button), x)", CONFIG)
        self.assertNotIn("remote_transmitter.transmit_samsung:", CONFIG)

    def test_capture_is_bounded_and_checksummed(self) -> None:
        self.assertIn("MAX_PULSES = 512", HEADER)
        self.assertIn("total_us > 250000", HEADER)
        self.assertIn("duration < 80", HEADER)
        self.assertIn("record.checksum == checksum_(record)", HEADER)

    def test_samsung_capture_uses_canonical_timings(self) -> None:
        self.assertIn("normalize_samsung_(raw, normalized, samsung_data)", HEADER)
        self.assertIn("normalized.push_back(4500)", HEADER)
        self.assertIn("? -1690 : -560", HEADER)
        self.assertIn("Canonicalized Samsung button", HEADER)

    def test_playback_logs_actual_output_pulses(self) -> None:
        self.assertIn("log_output_(button, raw)", HEADER)
        self.assertIn('carrier=38000 Hz, duty=50%%', HEADER)
        self.assertIn('log_pulses_("ir_tx", label, raw)', HEADER)

    def test_receiver_logs_raw_frame_details(self) -> None:
        self.assertIn("ir_code_store.log_received(x)", CONFIG)
        self.assertIn("Raw frame: pulses=%u", HEADER)
        self.assertIn('log_pulses_("ir_rx", "Raw frame", raw)', HEADER)

    def test_transmitter_reserves_shared_rmt_memory(self) -> None:
        transmitter = CONFIG.split("remote_transmitter:", 1)[1].split("i2s_audio:", 1)[0]
        self.assertIn("rmt_symbols: 48", transmitter)
        # Both TX channels are 48 symbols. A strip at the 96 default starves the
        # IR transmitter of a channel and it fails silently at boot.
        strip = CONFIG.split("id: status_light", 1)[1].split("effects:", 1)[0]
        self.assertIn("rmt_symbols: 48", strip)

    def test_receiver_rail_stays_on_for_passive_logging(self) -> None:
        entry = CONFIG.split("name: IR Rail", 1)[1].split("remote_receiver:", 1)[0]
        self.assertIn("restore_mode: ALWAYS_ON", entry)
        self.assertIn("dump: all", CONFIG)
        self.assertNotIn("id(ir_rail).turn_off();", CONFIG)


if __name__ == "__main__":
    unittest.main()
