"""Regression checks for production remote input and status-light wiring."""

from pathlib import Path
import re
import unittest


CONFIG = Path(__file__).parents[2] / "c6remote.yaml"
IR_LEARNING = Path(__file__).parents[2] / "ir_learning.h"
ZIGBEE_LEARNING = Path(__file__).parents[2] / "zigbee_learning.h"


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
        # Zigbee and Wi-Fi share the C6 radio. Coexistence needs modem power
        # save, or the STA misses beacons and the association flaps.
        self.assertRegex(config, r"wifi:[\s\S]*?\n  power_save_mode: light")
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

    def test_zigbee_dependency_and_client_endpoint_are_pinned(self) -> None:
        config = CONFIG.read_text()
        self.assertIn(
            "github://luar123/zigbee_esphome@6cb5480cd2499faf9afb825754fa46b084296cb8",
            config,
        )
        self.assertRegex(
            config,
            r"zigbee:\n  id: zigbee_radio[\s\S]*?router: false"
            r"[\s\S]*?sleepy: false[\s\S]*?num: 1"
            r"[\s\S]*?device_type: ON_OFF_SWITCH[\s\S]*?id: ON_OFF"
            r"\n          role: CLIENT",
        )

    def test_the_device_cycle_has_no_zigbee_stage(self) -> None:
        """A Zigbee target is resolved against Zigbee2MQTT by the browser, so the
        remote has nothing to train and the cycle skips straight to voice."""
        header = IR_LEARNING.read_text()
        self.assertIn("FULL cycles IR, voice, clear", header)
        self.assertRegex(
            header,
            r"if \(stage == 1 && mode == Tap::FULL\)[\s\S]*?ir_code_store\.set_voice",
        )
        for gone in ("ZIGBEE_WAIT", "ZIGBEE_SAVED", "zigbee_result", "zigbee_learn_callback_"):
            self.assertNotIn(gone, header)
        self.assertIn("ir_ui.tap(19, IrUi::Tap::NO_VOICE);", CONFIG.read_text())
        self.assertIn("ir_ui.tap(17, IrUi::Tap::ARM_ONLY);", CONFIG.read_text())
        self.assertIn("ir_ui.tap(18, IrUi::Tap::ARM_ONLY);", CONFIG.read_text())

    def test_nvs_v4_stores_kind_address_name_mask_and_checksum(self) -> None:
        """Version 4 carries a target kind, so a group entry and a device entry
        share one record."""
        header = ZIGBEE_LEARNING.read_text()
        self.assertIn("static constexpr uint16_t VERSION = 4;", header)
        self.assertIn("enum Kind : uint8_t { KIND_GROUP = 0, KIND_DEVICE = 1 };", header)
        self.assertRegex(
            header,
            r"struct Entry \{\n"
            r"    uint8_t kind;\n"
            r"    uint8_t endpoint;\n"
            r"    uint16_t group_id;\n"
            r"    uint8_t ieee\[8\];\n"
            r"    char friendly_name\[TARGET_SIZE\];",
        )
        self.assertRegex(
            header,
            r"struct Record \{[\s\S]*?uint32_t mask;[\s\S]*?"
            r"Entry entries\[SLOT_COUNT\];[\s\S]*?uint32_t checksum;",
        )

    def test_a_version_4_entry_validates_only_the_fields_of_its_kind(self) -> None:
        """A group entry with an IEEE address, or a device entry with a group id,
        is a half written record and must not load."""
        header = ZIGBEE_LEARNING.read_text()
        valid = re.search(
            r"static bool valid_\(const Record &record\) \{(?P<body>[\s\S]*?)\n  \}\n",
            header,
        )
        if valid is None:
            raise AssertionError("Zigbee valid_ method not found")
        body = valid.group("body")
        self.assertRegex(
            body,
            r"if \(entry\.kind == KIND_GROUP\) \{[\s\S]*?entry\.endpoint != 0[\s\S]*?"
            r"!ieee_all_zero_\(entry\.ieee\)",
        )
        self.assertRegex(
            body,
            r"\} else if \(entry\.kind == KIND_DEVICE\) \{[\s\S]*?entry\.group_id != 0[\s\S]*?"
            r"entry\.endpoint < MIN_ENDPOINT[\s\S]*?entry\.endpoint > MAX_ENDPOINT[\s\S]*?"
            r"!ieee_valid_\(entry\.ieee\)",
        )
        # An unknown kind is a future format, not a group.
        self.assertRegex(body, r"\} else \{\n        return false;")

    def test_a_version_3_record_migrates_instead_of_clearing_the_slots(self) -> None:
        """The blob lengths differ, so the version 4 load fails first and the old
        group assignments survive the update."""
        header = ZIGBEE_LEARNING.read_text()
        self.assertRegex(
            header,
            r"if \(preference_\.load\(&loaded\) && valid_\(loaded\)\)[\s\S]*?"
            r"\} else if \(load_version_3_\(record_\)\) \{[\s\S]*?preference_\.save\(&record_\)"
            r"[\s\S]*?\} else \{[\s\S]*?reset_record_\(record_\);",
        )
        self.assertIn(
            'static_assert(sizeof(Record) != sizeof(RecordV3),',
            header,
        )
        migrate = re.search(
            r"static bool load_version_3_\(Record &out\) \{(?P<body>[\s\S]*?)\n  \}\n",
            header,
        )
        if migrate is None:
            raise AssertionError("Zigbee load_version_3_ method not found")
        body = migrate.group("body")
        self.assertIn("make_preference<RecordV3>(PREFERENCE_KEY, true)", body)
        self.assertIn("!valid_v3_(old)", body)
        self.assertIn("entry.kind = KIND_GROUP;", body)
        self.assertIn("out.checksum = checksum_(out);", body)

    def test_clear_only_drops_the_local_record(self) -> None:
        """Group membership lives in the light, so the remote cannot and must not
        try to undo it."""
        header = ZIGBEE_LEARNING.read_text()
        clear = re.search(
            r"void clear\(uint8_t slot\) \{(?P<body>[\s\S]*?)\n  \}\n\n private:",
            header,
        )
        if clear is None:
            raise AssertionError("Zigbee clear method not found")
        body = clear.group("body")
        self.assertLess(body.index("record_ = next;"), body.index("preference_.save(&record_)"))
        self.assertNotIn("publish", body)

    def test_the_firmware_carries_no_mqtt_client(self) -> None:
        """The browser reads Zigbee2MQTT over the frontend websocket. An MQTT
        client on the remote buffered whole retained payloads and exhausted the
        heap, and it made playback depend on a broker that a groupcast does not
        need."""
        config = CONFIG.read_text()
        self.assertNotRegex(config, r"(?m)^mqtt:")
        self.assertNotIn("mqtt::global_mqtt_client", config)
        self.assertNotIn("mqtt_broker", config)
        header = ZIGBEE_LEARNING.read_text()
        self.assertNotIn("mqtt", header)
        self.assertNotIn("ArduinoJson", header)
        self.assertNotIn("subscribe(", header)
        # Nothing is left to time out, so the training clocks went with it.
        for gone in ("TRAINING_TIMEOUT_MS", "REQUEST_TIMEOUT_MS", "allowed_targets_", "tick()"):
            self.assertNotIn(gone, header)

    def test_playback_is_a_groupcast_that_needs_no_broker(self) -> None:
        """Membership lives in the light's group table, so a button keeps working
        with Zigbee2MQTT and Home Assistant both down."""
        header = ZIGBEE_LEARNING.read_text()
        toggle = header.split("bool toggle(uint8_t slot) const {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("request.cmd_ctrl.dst_addr.addr_mode = EZB_ADDR_MODE_GROUP;", toggle)
        self.assertIn("ezb_zcl_on_off_toggle_cmd_req(&request)", toggle)
        self.assertIn("entry.group_id", toggle)

    def test_a_stored_group_id_is_bounded_below_the_broadcast_range(self) -> None:
        """0xFFF8 and above are the reserved Zigbee broadcast addresses."""
        header = ZIGBEE_LEARNING.read_text()
        self.assertIn("static constexpr uint16_t MAX_GROUP_ID = 0xFFF7;", header)
        assign = header.split("bool assign_from_web(", 1)[1].split("\n  }", 1)[0]
        self.assertIn("group_id == 0 || group_id > MAX_GROUP_ID", assign)
        self.assertIn("ir_code_store.clear_for_zigbee(slot)", assign)

    def test_d5_is_reserved_for_zigbee_status_alone(self) -> None:
        # Zigbee training used to pulse D5, which hid the radio state for the
        # whole training window. It now pulses D3 and D4 instead.
        entry = status_light_entry(CONFIG.read_text())
        self.assertIn("if (!id(zigbee_radio).is_started())", entry)
        self.assertIn("else if (id(zigbee_radio).is_connected())", entry)
        self.assertIn("it[3] = Color(0, 128, 0);", entry)
        before_d5 = entry.split("// D5 is Zigbee status", 1)[0]
        self.assertNotIn("it[3]", before_d5.split("// D3 and D4", 1)[1])


if __name__ == "__main__":
    unittest.main()
