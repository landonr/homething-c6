"""Regression checks for local IR learning and playback."""

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[2]
CONFIG = (ROOT / "c6remote.yaml").read_text()
HEADER = (ROOT / "ir_learning.h").read_text()


def hold_tick_step() -> str:
    steps = CONFIG.split("  - interval: 50ms\n", 1)[1].split("\n\n", 1)[0].split("\n      - lambda: |-\n")
    return next(step for step in steps if "hold_actions.tick(" in step)


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
    def test_the_assignment_hold_opens_receiver_mode(self) -> None:
        assign = hold_tick_step().split("if (fired & (1u << HoldActions::ASSIGN)) {", 1)[1]
        opened = assign.split("} else {", 1)[0]
        self.assertIn("if (ir_ui.state == IrUi::OFF) {", opened)
        self.assertIn("ir_ui.open();", opened)
        self.assertIn('set_effect("Status Indicators")', opened)
        self.assertNotIn("IR Receiver", CONFIG)

    def test_voice_starts_in_one_shared_step_and_stops_on_a_plain_release(self) -> None:
        """Every expander input reaches Assist through the shared paths, so no
        input carries voice actions of its own."""
        inputs = CONFIG[CONFIG.index("\nbinary_sensor:\n"):CONFIG.index("\nsensor:\n")]
        self.assertNotIn("voice_assistant", inputs)
        self.assertEqual(CONFIG.count("voice_assistant.start:"), 1)
        press = CONFIG.split("  - id: button_press\n", 1)[1].split("\n  - id:", 1)[0]
        self.assertIn("voice_assistant.start:", press)
        release = CONFIG.split("  - id: release_assignment\n", 1)[1].split("\n  - id:", 1)[0]
        self.assertIn("voice_assistant.stop:", release)

    def test_receiver_states_drive_only_d3_and_d4(self) -> None:
        for state in ("READY", "READING", "SAVED", "ERROR", "VOICE", "CLEARED"):
            self.assertIn(f"ir_ui.state == IrUi::{state}", CONFIG)
        # D2 is Wi-Fi and D5 is Zigbee. Assignment mode must not hide either, so
        # its branch writes no it[0], no it[3], and no whole-strip colour.
        mode = CONFIG.split("if (ir_ui.state != IrUi::OFF) {", 1)[1]
        mode = mode.split("} else if (id(voice_led_state) == 1)", 1)[0]
        for forbidden in ("it[0]", "it[3]", "it.all()"):
            self.assertNotIn(forbidden, mode)
        self.assertIn("it[1]", mode)
        self.assertIn("it[2]", mode)

    def test_wifi_and_zigbee_leds_render_outside_the_mode_branch(self) -> None:
        status = CONFIG.split("name: Status Indicators", 1)[1].split("on_turn_on:", 1)[0]
        self.assertIn("it[0] = Color(0, 96, 24);", status)
        self.assertIn("id(zigbee_radio).is_connected()", status)
        self.assertIn("it[3] = Color(0, 128, 0);", status)

    def test_d2_reports_wifi_and_api_only(self) -> None:
        # A Home Assistant press turns Wi-Fi on itself, so a dark D2 must not
        # read as a dead button.
        status = CONFIG.split("name: Status Indicators", 1)[1].split("// D3 and D4", 1)[0]
        self.assertNotIn("mqtt", status)
        self.assertIn("const bool wifi_enabled = !wifi::global_wifi_component->is_disabled();", status)
        self.assertIn("if (wifi_enabled && api_connected) {", status)
        self.assertIn("else if (wifi_enabled && !wifi_connected) {", status)
        self.assertIn("else if (wifi_enabled && ha_expected) {", status)
        self.assertIn("else if (wifi_enabled) {", status)
        self.assertIn("it[0] = Color(level, level / 2, 0);", status)
        green = status.index("it[0] = Color(0, 96, 24);")
        self.assertLess(status.index("if (wifi_enabled && api_connected) {"), green)

    def test_d2_and_d5_pulse_periods_are_slow(self) -> None:
        status = CONFIG.split("name: Status Indicators", 1)[1].split("on_turn_on:", 1)[0]
        d2 = status.split("// D2 stays dark", 1)[1].split("// D3 and D4", 1)[0]
        d5 = status.split("// D5 is Zigbee status", 1)[1]
        self.assertIn("else if (wifi_enabled && !wifi_connected) {", d2)
        self.assertIn("else if (wifi_enabled && ha_expected) {", d2)
        self.assertEqual(2, d2.count("(millis() % 4800) / 4800.0f"))
        for period in (1600, 3200, 4000):
            self.assertIn(f"(millis() % {period}) / {period}.0f", d5)

    def test_successful_save_returns_to_ready_until_the_assignment_hold(self) -> None:
        self.assertIn("const uint32_t hold = (state == READING || state == VOICE) ? 10000 : 1000", HEADER)
        self.assertIn("state = READY", HEADER)
        self.assertIn("elapsed < 5000", HEADER)
        tick = HEADER.split("bool tick() {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("if (state == READY)", tick)
        self.assertIn("close();", tick)
        # The hold closes the mode from any learn state. HoldActions makes the
        # release silent, so IrUi keeps no consumed flag of its own.
        assign = hold_tick_step().split("if (fired & (1u << HoldActions::ASSIGN)) {", 1)[1]
        self.assertIn("ir_ui.close();", assign.split("} else {", 1)[1])
        self.assertNotIn("hold_consumed", HEADER)
        self.assertIn('"Receiver mode READY. Hold the assignment mode button or wait 5 s to leave"', HEADER)
        self.assertNotIn("SW1", HEADER.split("void open() {", 1)[1].split("\n  }", 1)[0])

    def test_all_assignable_buttons_have_playback_paths(self) -> None:
        """Playback rides the tap, so every input needs its own slot number."""
        # 3..11 are SW3..SW11, 12..16 the wheel directions, 19 SW2 and 20 SW1.
        for button in list(range(3, 17)) + [19, 20]:
            self.assertEqual(1, CONFIG.count(f"{{id: button_press, slot: {button}}}"), button)
            self.assertEqual(1, CONFIG.count(f"{{id: button_release, slot: {button}}}"), button)
        # 17 and 18 are the rotation detents, which have no release edge and so
        # never reach the voice stage.
        for button in (17, 18):
            self.assertIn(f"ir_ui.tap({button}, IrUi::Tap::ARM_ONLY)", CONFIG)
        send = CONFIG.split("- if: &send_learned_code", 1)[1].split("- if:", 1)[0]
        self.assertIn("lambda: return ir_ui.take_transmit();", send)
        self.assertIn("code: !lambda return ir_ui.code();", send)
        self.assertIn("ir_code_store.save(target, raw)", HEADER)
        self.assertIn("pending_transmit_ = ir_code_store.load(button, code_);", HEADER)
        # The anticlockwise detent, the press path and the release path.
        self.assertEqual(3, CONFIG.count("- if: *send_learned_code"))
        self.assertLess(CONFIG.index("- if: &send_learned_code"), CONFIG.index("\nscript:\n"))
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
        # One rule for the store, the page check, and the set_ir_name check.
        self.assertIn("if (!ir_name::keeps(value))\n        continue;", clean)
        rule = (ROOT / "ir_name.h").read_text()
        self.assertIn("inline bool keeps(char value) { return value >= 0x20 && value <= 0x7E && value != '\"' "
                      "&& value != '\\\\'; }", rule)
        self.assertIn('#include "ir_name.h"', HEADER)
        self.assertIn("static_assert(ir_name::MAX + 1 == NAME_LEN,", HEADER)
        # A cleared slot must not keep the name of the code it held.
        self.assertEqual(HEADER.count('erase_code_(button) && write_name_(button, "")'), 2)
        # Nor may a slot keep the old name after a capture writes a new code.
        save = section(HEADER, "bool save(uint8_t button, const std::vector<int32_t> &raw) {", "\n  }")
        self.assertIn("if (names_.names[slot][0] != '\\0')\n      write_name_(button, \"\");", save)

    def test_a_rename_keeps_the_timings(self) -> None:
        """A rename writes only the name record, and only for a slot with a stored code."""
        rename = section(HEADER, "bool rename(uint8_t button, const char *text) {", "\n  }")
        self.assertLess(rename.index("if (!has_code(button))\n      return false;"),
                        rename.index("set_name(button, text)"))
        for gone in ("prefs_[", "records_[", "erase_code_(", "voice_pref_"):
            self.assertNotIn(gone, rename)

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
        self.assertNotIn("id(ir_rail).turn_off();", CONFIG)

    def test_production_receiver_links_no_protocol_dumpers(self) -> None:
        """Learning and playback use raw timings only, and the dumpers cost flash.
        The raw frame log is INFO, so it survives the production logger level."""
        receiver = section(CONFIG, "\nremote_receiver:\n", "\nremote_transmitter:")
        self.assertNotIn("dump:", receiver)
        self.assertIn("on_raw:", receiver)
        self.assertIn("\nlogger:\n  level: INFO\n", CONFIG)
        received = HEADER.split("void log_received(", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn('ESP_LOGI("ir_rx",\n             "Raw frame: pulses=%u', received)
        pulses = HEADER.split("static void log_pulses_(", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("ESP_LOGI(tag,", pulses)



class AssignmentOwnershipTest(unittest.TestCase):
    def test_the_clear_hook_is_a_listener_list_that_names_the_new_owner(self) -> None:
        self.assertIn("std::vector<std::function<void(uint8_t, Owner)>> assignment_clear_callbacks_{};", HEADER)
        self.assertIn("void add_assignment_clear_callback(std::function<void(uint8_t, Owner)> callback) {", HEADER)
        self.assertIn("assignment_clear_callbacks_.push_back(std::move(callback));", HEADER)
        self.assertNotIn("set_assignment_clear_callback", HEADER)

    def test_capture_voice_and_clear_all_release_the_other_kinds(self) -> None:
        self.assertEqual(HEADER.count("release_others(button, OWNER_IR);"), 2)
        self.assertEqual(HEADER.count("release_others(button, OWNER_NONE);"), 1)

    def test_a_press_tries_voice_hid_zigbee_home_assistant_then_ir(self) -> None:
        play = section(HEADER, "void play_(uint8_t button) {", "\n  }")
        order = ["is_voice(button)", "hid_play_callback_(button, true)", "zigbee_play_callback_(button)",
                 "ha_play_callback_(button)", "ir_code_store.load(button, code_)"]
        positions = [play.index(item) for item in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("void set_ha_play_callback(std::function<bool(uint8_t)> play) {", HEADER)


if __name__ == "__main__":
    unittest.main()
