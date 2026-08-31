"""Regression checks for local IR learning and playback."""

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[2]
CONFIG = (ROOT / "c6remote.yaml").read_text()
HEADER = (ROOT / "ir_learning.h").read_text()


def section(text: str, start: str, end: str) -> str:
    """Return the text between the first start marker and the next end marker."""
    head = text.split(start, 1)
    if len(head) != 2:
        raise AssertionError(f"{start!r} not found")
    tail = head[1].split(end, 1)
    if len(tail) != 2:
        raise AssertionError(f"{end!r} not found after {start!r}")
    return tail[0]


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
        """IrUi owns the state, so the effect reads the singleton, not a global."""
        effect = CONFIG.split("name: IR Receiver", 1)[1].split("on_turn_on:", 1)[0]
        for state in ("READY", "READING", "SAVED", "ERROR", "VOICE", "CLEARED"):
            self.assertIn(f"ir_ui.state == IrUi::{state}", effect)
        self.assertNotIn("ir_learn_state", CONFIG)

    def test_a_result_holds_briefly_and_idle_closes_the_mode(self) -> None:
        """A save must stay visible, and an abandoned mode must not hold the
        LEDs and the rail for ever."""
        tick = HEADER.split("bool tick() {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("if (elapsed < 3000)", tick)
        self.assertIn("close();", tick)
        self.assertIn("const uint32_t hold = (state == READING || state == VOICE) ? 10000 : 1000;", tick)
        self.assertIn("if (elapsed >= hold) {", tick)
        self.assertIn("state = READY;", tick)
        self.assertIn("if (state == READY)", tick)
        # SW2 still leaves the mode on a hold, without waiting for the timeout.
        self.assertIn("id: exit_receiver_hold", CONFIG)
        exit_hold = CONFIG.split("id: exit_receiver_hold", 1)[1].split("- id: ", 1)[0]
        self.assertIn("ir_ui.close();", exit_hold)
        self.assertIn("ir_ui.sw2_consumed = true;", exit_hold)

    def test_all_assignable_buttons_have_playback_paths(self) -> None:
        """Playback rides the tap, so every input needs its own slot number."""
        for button in range(3, 12):
            self.assertIn(f"ir_ui.tap({button}, IrUi::Tap::FULL)", CONFIG)
        # 12..16 are the wheel directions. 17 and 18 are the rotation detents,
        # which have no release edge and so never reach the voice stage.
        for button in range(12, 17):
            self.assertIn(f"ir_ui.tap({button}, IrUi::Tap::FULL)", CONFIG)
        for button in (17, 18):
            self.assertIn(f"ir_ui.tap({button}, IrUi::Tap::ARM_ONLY)", CONFIG)
        self.assertIn("ir_ui.tap(19, IrUi::Tap::NO_VOICE)", CONFIG)
        self.assertIn("ir_ui.tap(20, IrUi::Tap::FULL)", CONFIG)
        send = CONFIG.split("- if: &send_learned_code", 1)[1].split("- if:", 1)[0]
        self.assertIn("lambda: return ir_ui.take_transmit();", send)
        self.assertIn("code: !lambda return ir_ui.code();", send)
        self.assertIn("ir_code_store.save(target, raw)", HEADER)
        self.assertIn("pending_transmit_ = ir_code_store.load(button, code_);", HEADER)
        self.assertEqual(17, CONFIG.count("- if: *send_learned_code"))
        for button in range(3, 12):
            entry = CONFIG.split(f"name: Button {button}", 1)[1].split(f"name: Button {button + 1}", 1)[0]
            self.assertIn("- if: *send_learned_code", entry)
        self.assertIn("FIRST_BUTTON = 3", HEADER)
        self.assertNotIn("remote_transmitter.transmit_samsung:", CONFIG)

    def test_capture_is_bounded_and_checksummed(self) -> None:
        self.assertIn("MAX_PULSES = 512", HEADER)
        self.assertIn("total_us > 250000", HEADER)
        self.assertIn("duration < 80", HEADER)
        self.assertIn("record.checksum == checksum_(record)", HEADER)

    def test_samsung_capture_uses_canonical_timings(self) -> None:
        self.assertIn("normalize_samsung_(raw, normalized, samsung_data)", HEADER)
        self.assertIn("samsung_frame_(data, normalized)", HEADER)
        self.assertIn("frame.push_back(4500)", HEADER)
        self.assertIn("? -1690 : -560", HEADER)
        self.assertIn("Canonicalized Samsung button", HEADER)

    def test_a_samsung_word_reads_back_as_an_address_and_a_command(self) -> None:
        """Samsung32 sends the address twice and the command with its inverse,
        each byte least significant bit first."""
        fields = section(
            HEADER,
            "bool code_samsung_fields(uint8_t button, uint8_t &address, uint8_t &command) const {",
            "\n  }",
        )
        self.assertIn("reverse_bits_((data >> 24) & 0xFFU)", fields)
        self.assertIn("reverse_bits_((data >> 8) & 0xFFU)", fields)
        self.assertIn("if (first != second || value != static_cast<uint8_t>(~inverse))", fields)
        builder = section(
            HEADER,
            "static void samsung_timings(uint8_t address, uint8_t command, std::vector<int32_t> &raw) {",
            "\n  }",
        )
        self.assertIn("reverse_bits_(static_cast<uint8_t>(~command))", builder)
        self.assertIn("samsung_frame_(data, raw)", builder)

    def test_a_code_name_persists_beside_the_frame(self) -> None:
        """The name has its own record, so it cannot shift the Record layout that
        every stored code is read back with."""
        self.assertIn("static constexpr uint32_t NAME_KEY = 0x4952434EU;", HEADER)
        self.assertIn("make_preference<NameBook>(NAME_KEY, true)", HEADER)
        self.assertIn("char names[SLOT_COUNT][NAME_LEN];", HEADER)
        clean = section(HEADER, "bool set_name(uint8_t button, const char *text) {", "\n  }")
        self.assertIn("value < 0x20 || value > 0x7E", clean)
        self.assertIn("value == '\"' || value == '\\\\'", clean)
        # A cleared slot must not keep the name of the code it held.
        self.assertEqual(HEADER.count('erase_code_(button) && write_name_(button, "")'), 2)
        # Nor may a slot keep the old name after a capture writes a new code.
        save = section(HEADER, "bool save(uint8_t button, const std::vector<int32_t> &raw) {", "\n  }")
        self.assertIn("if (names_.names[slot][0] != '\\0')\n      write_name_(button, \"\");", save)

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
