"""Static checks for the idle deep-sleep spike and its bench config."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[2]
COMPONENT = ROOT / "components" / "idle_sleep"
STUB = (COMPONENT / "wake_stub.c").read_text()
CPP = (COMPONENT / "idle_sleep.cpp").read_text()
HEADER = (COMPONENT / "idle_sleep.h").read_text()
INIT = (COMPONENT / "__init__.py").read_text()
BENCH = (ROOT / "c6remote-test-sleep.yaml").read_text()
PRODUCTION = (ROOT / "c6remote.yaml").read_text()


def function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    open_brace = source.index("{", start)
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace + 1:index]
    raise AssertionError(f"{signature} has no closing brace")


def statements(body: str) -> list[str]:
    lines = []
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            lines.append(line)
    return lines


def expander_bit_to_slot(config: str) -> dict[int, int]:
    section = config[config.index("\nbinary_sensor:\n"):config.index("\nsensor:\n")]
    mapping = {}
    for entry in section.split("  - platform: gpio\n")[1:]:
        if "pcf8574: button_expander" not in entry and "<<: *button_1" not in entry:
            continue
        bit = int(re.search(r"number: (\d+)", entry).group(1))
        slot = int(re.search(r"ir_ui\.tap\((\d+),", entry).group(1))
        mapping[bit] = slot
    return mapping


class WakeStubTest(unittest.TestCase):
    def test_stub_is_in_rtc_iram_and_calls_the_default_stub_first(self) -> None:
        self.assertIn("void RTC_IRAM_ATTR esp_wake_deep_sleep(void)", STUB)
        body = statements(function_body(STUB, "void RTC_IRAM_ATTR esp_wake_deep_sleep(void)"))
        self.assertEqual(body[0], "esp_default_wake_deep_sleep();")

    def test_every_stub_helper_lives_in_rtc_iram(self) -> None:
        helpers = re.findall(r"^static [^\n(]*\(", STUB, re.MULTILINE)
        self.assertTrue(helpers)
        for helper in helpers:
            self.assertIn("RTC_IRAM_ATTR", helper)

    def test_latch_is_rtc_data_and_the_stub_is_behind_the_define(self) -> None:
        self.assertIn("RTC_DATA_ATTR idle_sleep_latch_t idle_sleep_latch;", STUB)
        self.assertLess(STUB.index("RTC_DATA_ATTR idle_sleep_latch_t"),
                        STUB.index("#ifdef USE_IDLE_SLEEP_WAKE_STUB"))
        self.assertLess(STUB.index("#ifdef USE_IDLE_SLEEP_WAKE_STUB"),
                        STUB.index("esp_wake_deep_sleep(void)"))
        self.assertIn('cg.add_define("USE_IDLE_SLEEP_WAKE_STUB")', INIT)
        self.assertIn("if config[CONF_WAKE_STUB]:", INIT)

    def test_stub_reads_the_expander_open_drain_on_the_i2c_pins(self) -> None:
        self.assertIn("#define STUB_SDA 22", STUB)
        self.assertIn("#define STUB_SCL 23", STUB)
        self.assertIn("#define STUB_ADDR_READ ((0x20u << 1) | 1u)", STUB)
        self.assertIn("REG_WRITE(GPIO_OUT_W1TC_REG, both);", STUB)
        self.assertIn("SIG_GPIO_OUT_IDX", STUB)
        self.assertNotIn("GPIO_OUT_W1TS_REG", STUB)
        half = int(re.search(r"#define STUB_HALF_US (\d+)", STUB).group(1))
        self.assertGreaterEqual(half, 10)
        self.assertIn("stub_read_byte(1)", STUB)
        self.assertIn("stub_read_byte(0)", STUB)

    def test_stub_calls_only_rom_or_rtc_functions(self) -> None:
        body = STUB[STUB.index("#ifdef USE_IDLE_SLEEP_WAKE_STUB"):]
        defined = set(re.findall(r"RTC_IRAM_ATTR \w+ (\w+)\(", body))
        allowed = defined | {
            "esp_default_wake_deep_sleep",
            "esp_wake_stub_get_wakeup_cause",
            "esp_rom_delay_us",
            "esp_rom_get_cpu_ticks_per_us",
            "esp_cpu_get_cycle_count",
            "esp_wake_deep_sleep",
        }
        code = re.sub(r"#include[^\n]*|//[^\n]*", "", body)
        calls = set(re.findall(r"\b([a-z_][a-z0-9_]*)\s*\(", code))
        keywords = {"if", "for", "while", "return", "sizeof"}
        self.assertEqual(calls - allowed - keywords, set())


class IdleSleepComponentTest(unittest.TestCase):
    def test_wakes_on_gpio5_any_low(self) -> None:
        self.assertIn("WAKE_PIN = GPIO_NUM_5;", CPP)
        self.assertIn("esp_sleep_enable_ext1_wakeup_io(BIT64(WAKE_PIN), ESP_EXT1_WAKEUP_ANY_LOW);", CPP)
        self.assertIn("rtc_gpio_pullup_dis(WAKE_PIN);", CPP)
        self.assertIn("gpio_pullup_dis(WAKE_PIN);", CPP)

    def test_setup_releases_holds_before_anything_else(self) -> None:
        body = statements(function_body(CPP, "void IdleSleep::setup()"))
        first_other = next(i for i, line in enumerate(body)
                           if "gpio_hold_dis" not in line and not line.startswith("for "))
        releases = [i for i, line in enumerate(body) if "gpio_hold_dis" in line]
        self.assertEqual(len(releases), 3)
        self.assertLess(max(releases), first_other)

    def test_sleep_holds_the_same_pins_that_setup_releases(self) -> None:
        setup = function_body(CPP, "void IdleSleep::setup()")
        sleep = function_body(CPP, "void IdleSleep::enter_sleep_()")
        for name in ("HELD_FLOATING", "HELD_PULLDOWN", "HELD_LOW"):
            self.assertIn(name, setup)
            self.assertIn(name, sleep)
        self.assertIn("HELD_FLOATING[] = {GPIO_NUM_6, GPIO_NUM_15, GPIO_NUM_16, GPIO_NUM_18};", CPP)
        self.assertIn("HELD_PULLDOWN = GPIO_NUM_17;", CPP)
        self.assertIn("HELD_LOW[] = {GPIO_NUM_0, GPIO_NUM_2};", CPP)

    def test_shutdown_hooks_run_before_the_holds_and_the_sleep(self) -> None:
        body = function_body(CPP, "void IdleSleep::enter_sleep_()")
        order = [
            "App.run_safe_shutdown_hooks();",
            "App.teardown_components(",
            "App.run_powerdown_hooks();",
            "gpio_hold_en(",
            "this->read_port_(&port);",
            "esp_sleep_enable_ext1_wakeup_io(",
            "esp_deep_sleep_start();",
        ]
        positions = [body.index(item) for item in order]
        self.assertEqual(positions, sorted(positions))

    def test_sleep_waits_for_int_high_and_no_pressed_bit(self) -> None:
        body = function_body(CPP, "void IdleSleep::try_sleep_()")
        self.assertIn("gpio_get_level(WAKE_PIN) == 0", body)
        self.assertIn("this->pressed_ != 0", body)
        self.assertIn("this->cold_boot_grace_ms_", body)
        self.assertLess(body.index("gpio_get_level(WAKE_PIN)"), body.index("this->enter_sleep_();"))

    def test_forced_sleep_waits_for_release_and_int_high(self) -> None:
        body = function_body(CPP, "void IdleSleep::try_sleep_()")
        forced = body[body.index("if (this->forced_sleep_) {"):body.index("} else {")]
        self.assertLess(forced.index("if (this->pressed_ != 0)"), forced.index("return;"))
        self.assertLess(forced.index("return;"), forced.index("this->replay_pending_ = false;"))
        self.assertNotIn("block_probe_", forced)
        self.assertNotIn("cold_boot_grace_ms_", forced)
        self.assertNotIn("sleep_after_ms_", forced)
        tail = body[body.index("// The read releases INT."):]
        self.assertLess(tail.index("this->read_port_(&port)"), tail.index("gpio_get_level(WAKE_PIN) == 0"))
        int_low = tail[tail.index("gpio_get_level(WAKE_PIN) == 0"):tail.index("this->enter_sleep_();")]
        self.assertIn("if (this->forced_sleep_) {", int_low)
        self.assertIn("return;", int_low[int_low.index("if (this->forced_sleep_) {"):])

    def test_hold_arms_forced_sleep_from_the_poll(self) -> None:
        hold = function_body(CPP, "void IdleSleep::track_hold_(uint16_t pressed, uint32_t now)")
        self.assertIn("this->sleep_hold_bit_ == NO_BIT", hold)
        self.assertIn("now - this->hold_since_ms_ >= this->sleep_hold_time_ms_", hold)
        self.assertIn("this->forced_sleep_ = true;", hold)
        self.assertIn("this->track_hold_(pressed, now);", function_body(CPP, "void IdleSleep::loop()"))
        self.assertIn("uint8_t sleep_hold_bit_{0xFF};", HEADER)
        self.assertIn("cv.Optional(CONF_SLEEP_HOLD_BIT): cv.int_range(min=0, max=15)", INIT)
        self.assertIn('CONF_SLEEP_HOLD_TIME, default="2s"', INIT)

    def test_the_loop_logs_nothing_and_sleep_entry_logs_the_record(self) -> None:
        loop = function_body(CPP, "void IdleSleep::loop()")
        self.assertNotIn("log_record(", loop)
        self.assertNotIn("log_timing_", loop)
        self.assertNotIn("log_timing_", HEADER)
        sleep = function_body(CPP, "void IdleSleep::enter_sleep_()")
        self.assertIn('log_record("WAKE_TIMING", *s_current);', sleep)

    def test_setup_runs_just_after_the_i2c_bus(self) -> None:
        self.assertIn("return setup_priority::BUS - 1.0f;", HEADER)

    def test_defaults_match_the_plan(self) -> None:
        self.assertIn('CONF_SLEEP_AFTER, default="5min"', INIT)
        self.assertIn('CONF_COLD_BOOT_GRACE, default="60s"', INIT)
        self.assertIn("CONF_WAKE_STUB, default=True", INIT)
        self.assertIn("i2c.i2c_device_schema(0x20)", INIT)


class InterruptTest(unittest.TestCase):
    def test_the_isr_only_sets_a_flag_and_lives_in_iram(self) -> None:
        self.assertIn("static volatile bool s_int_edge = false;", CPP)
        self.assertIn("static void IRAM_ATTR int_edge_isr(void * /*arg*/) { s_int_edge = true; }", CPP)

    def test_the_isr_is_a_gpio5_falling_edge_added_after_every_setup(self) -> None:
        attach = function_body(CPP, "void IdleSleep::attach_int_isr_()")
        self.assertIn("gpio_install_isr_service(ESP_INTR_FLAG_LEVEL3)", attach)
        self.assertIn("service != ESP_OK && service != ESP_ERR_INVALID_STATE", attach)
        self.assertLess(attach.index("gpio_set_intr_type(WAKE_PIN, GPIO_INTR_NEGEDGE);"),
                        attach.index("gpio_isr_handler_add(WAKE_PIN, int_edge_isr, nullptr)"))
        self.assertIn("this->int_isr_attached_ = true;", attach)
        # ESPHome fails its own attach_interrupt() when the service already
        # exists, so setup() must not install it.
        setup = function_body(CPP, "void IdleSleep::setup()")
        self.assertNotIn("gpio_install_isr_service", setup)
        self.assertNotIn("gpio_isr_handler_add", setup)
        loop = function_body(CPP, "void IdleSleep::loop()")
        self.assertIn("if (!this->int_isr_tried_)\n    this->attach_int_isr_();", loop)

    def test_loop_turns_an_edge_into_activity_and_keeps_the_poll(self) -> None:
        loop = function_body(CPP, "void IdleSleep::loop()")
        edge = function_body(loop, "if (s_int_edge)")
        self.assertEqual(statements(edge)[0], "s_int_edge = false;")
        self.assertIn("ESP_LOGD(TAG,", edge)
        self.assertNotIn("ESP_LOGI", edge)
        self.assertIn("this->last_activity_ms_ = now;", edge)
        self.assertLess(loop.index("if (s_int_edge)"), loop.index("this->try_sleep_();"))
        self.assertIn("now - this->last_poll_ms_ >= POLL_MS", loop)
        self.assertIn("this->set_pressed_(pressed, now);", loop)
        self.assertIn("this->track_hold_(pressed, now);", loop)
        self.assertIn("static constexpr uint32_t POLL_MS = 100;", CPP)

    def test_the_isr_goes_before_ext1_takes_the_pad(self) -> None:
        sleep = function_body(CPP, "void IdleSleep::enter_sleep_()")
        detach_at = sleep.index("this->detach_int_isr_();")
        self.assertLess(sleep.index("App.run_powerdown_hooks();"), detach_at)
        self.assertLess(detach_at, sleep.index("esp_sleep_enable_ext1_wakeup_io("))
        detach = function_body(CPP, "void IdleSleep::detach_int_isr_()")
        self.assertIn("gpio_isr_handler_remove(WAKE_PIN);", detach)
        self.assertIn("gpio_set_intr_type(WAKE_PIN, GPIO_INTR_DISABLE);", detach)
        # Both INT checks read the pad level, so they need no ISR.
        self.assertLess(detach_at, sleep.index("gpio_get_level(WAKE_PIN) == 0"))
        self.assertIn("gpio_get_level(WAKE_PIN) == 0", function_body(CPP, "void IdleSleep::try_sleep_()"))

    def test_an_interrupt_mode_gpio5_sensor_is_refused(self) -> None:
        """IDF keeps one ISR handler for each pin, so the sensor and IdleSleep
        would replace each other."""
        self.assertIn("FINAL_VALIDATE_SCHEMA = _final_validate", INIT)
        self.assertIn("WAKE_PIN = 5\n", INIT)
        self.assertIn('sensor.get("use_interrupt", False)', INIT)
        self.assertIn("pins.PIN_SCHEMA_REGISTRY.get_key(pin) == CORE.target_platform", INIT)
        self.assertIn("pin.get(CONF_NUMBER) == WAKE_PIN", INIT)
        # Production polls the sensor because IdleSleep owns the GPIO5 ISR.
        entry = PRODUCTION.split("name: Expander INT\n", 1)[1].split("\n\n", 1)[0]
        self.assertIn("number: GPIO5\n", entry)
        self.assertIn("use_interrupt: false\n", entry)
        self.assertNotIn("expander_int", BENCH)
        self.assertNotIn("use_interrupt", BENCH)


class SettingsTest(unittest.TestCase):
    def test_the_public_api(self) -> None:
        for line in (
            "bool enabled() const { return this->enabled_.load(std::memory_order_relaxed); }",
            "uint32_t sleep_after_s() const { return this->sleep_after_s_.load(std::memory_order_relaxed); }",
            "bool set_enabled(bool enabled);",
            "bool set_sleep_after_s(uint32_t seconds);",
            "static constexpr uint32_t MIN_SLEEP_AFTER_S = 10;",
            "static constexpr uint32_t MAX_SLEEP_AFTER_S = 3600;",
            "std::atomic<bool> enabled_{true};",
            "std::atomic<uint32_t> sleep_after_s_{300};",
        ):
            self.assertIn(line, HEADER)

    def test_an_out_of_range_value_is_refused_before_a_save(self) -> None:
        body = function_body(CPP, "bool IdleSleep::set_sleep_after_s(uint32_t seconds)")
        check = body.index("if (seconds < MIN_SLEEP_AFTER_S || seconds > MAX_SLEEP_AFTER_S)\n    return false;")
        self.assertLess(check, body.index("this->save_settings_("))

    def test_each_set_saves_then_restarts_the_idle_window(self) -> None:
        for signature, store in (
            ("bool IdleSleep::set_enabled(bool enabled)", "this->enabled_.store(enabled"),
            ("bool IdleSleep::set_sleep_after_s(uint32_t seconds)", "this->sleep_after_s_.store(seconds"),
        ):
            body = function_body(CPP, signature)
            save = body.index("if (!this->save_settings_(")
            self.assertLess(save, body.index(store))
            self.assertLess(save, body.index("this->last_activity_ms_ = millis();"))
            self.assertIn("return true;", body)
        save = function_body(CPP, "bool IdleSleep::save_settings_(bool enabled, uint32_t stored_after_s)")
        self.assertIn("this->settings_pref_.save(&next)", save)

    def test_settings_load_from_a_fixed_key_and_fall_back_to_yaml(self) -> None:
        self.assertIn("SETTINGS_KEY = 0x534C4346U;", HEADER)
        self.assertIn("SETTINGS_MAGIC = 0x534C4331U;", HEADER)
        load = function_body(CPP, "void IdleSleep::load_settings_()")
        self.assertIn("make_preference<SettingsPref>(SETTINGS_KEY, true)", load)
        self.assertIn("loaded.magic == SETTINGS_MAGIC", load)
        self.assertIn("this->enabled_.store(!valid || loaded.enabled == 1", load)
        self.assertIn("this->stored_after_s_ != 0 ? this->stored_after_s_ : this->default_sleep_after_s_", load)
        self.assertIn("this->load_settings_();", function_body(CPP, "void IdleSleep::setup()"))
        self.assertIn("cg.add(var.set_default_sleep_after_s(config[CONF_SLEEP_AFTER].total_seconds))", INIT)
        self.assertIn("cv.positive_time_period_seconds,", INIT)
        self.assertIn("cv.Range(min=MIN_SLEEP_AFTER, max=MAX_SLEEP_AFTER)", INIT)
        self.assertIn("MIN_SLEEP_AFTER = cv.TimePeriod(seconds=10)", INIT)
        self.assertIn("MAX_SLEEP_AFTER = cv.TimePeriod(seconds=3600)", INIT)

    def test_off_stops_only_the_idle_path(self) -> None:
        body = function_body(CPP, "void IdleSleep::try_sleep_()")
        forced = body[body.index("if (this->forced_sleep_) {"):body.index("} else {")]
        idle = body[body.index("} else {"):body.index("// The read releases INT.")]
        self.assertNotIn("enabled()", forced)
        self.assertEqual(statements(idle)[1:3], ["if (!this->enabled())", "return;"])
        self.assertIn("now - this->last_activity_ms_ < this->sleep_after_s() * 1000U", idle)

    def test_dump_config_logs_both_settings(self) -> None:
        dump = function_body(CPP, "void IdleSleep::dump_config()")
        self.assertIn("YESNO(this->enabled())", dump)
        self.assertIn("this->sleep_after_s()", dump)
        self.assertIn("this->default_sleep_after_s_", dump)


class ProductionSleepConfigTest(unittest.TestCase):
    def test_production_has_idle_sleep_and_the_replay_hooks(self) -> None:
        self.assertIn("\nidle_sleep:\n", PRODUCTION)
        self.assertIn("return id(zigbee_radio).is_connected();", PRODUCTION)
        self.assertIn("zigbee_assignments.play(SLOT_OF_BIT[bit])", PRODUCTION)

    def test_the_sw5_hold_flashes_the_awake_led_once_when_armed(self) -> None:
        self.assertIn("bool sleep_armed() const { return this->forced_sleep_; }", HEADER)
        interval = PRODUCTION.split("  - interval: 50ms\n", 1)[1].split("\n\n", 1)[0]
        for text in (
            "id(idle).sleep_armed()",
            "if (armed && !was_armed) {",
            "id(awake_led).turn_on()",
            "call.set_brightness(1.0f);",
            "call.set_flash_length(250);",
        ):
            self.assertIn(text, interval)
        self.assertLess(
            interval.index("id(idle).sleep_armed()"),
            interval.index("if (!id(idle).woke_from_sleep())"),
        )

    def test_wake_pulse_is_the_last_d3_d4_state_and_production_drives_it(self) -> None:
        self.assertIn("bool woke_from_sleep() const { return !this->cold_boot_; }", HEADER)
        self.assertIn("bool wake_pending() const { return this->replay_pending_; }", HEADER)
        self.assertIn("  - id: wake_pulse_until_ms\n    type: uint32_t\n", PRODUCTION)
        effect = PRODUCTION.split("name: Status Indicators", 1)[1].split("// D5 is Zigbee status", 1)[0]
        wake = effect.index("} else if (millis() < id(wake_pulse_until_ms)) {")
        self.assertLess(effect.index("} else if (id(voice_led_state) == 4) {"), wake)
        pulse = effect[wake:]
        self.assertIn("(millis() % 800) / 800.0f", pulse)
        self.assertIn("it[1] = Color(level, level, level);", pulse)
        self.assertIn("it[2] = Color(level, level, level);", pulse)
        drive = PRODUCTION.split("  - interval: 50ms\n", 1)[1]
        self.assertIn("if (!id(idle).woke_from_sleep())", drive)
        self.assertIn("id(idle).wake_pending() ||", drive)
        self.assertIn("id(wake_pulse_until_ms) = millis() + 100;", drive)

    def test_production_starts_the_sw9_hold_for_a_bit_held_at_wake(self) -> None:
        self.assertIn("uint16_t held_at_wake() const { return this->held_mask_; }", HEADER)
        setup = function_body(CPP, "void IdleSleep::setup()")
        self.assertIn("this->held_mask_ = rec.stub_down & first_down;", setup)
        self.assertIn("if (latched) {", setup)
        drive = PRODUCTION.split("  - interval: 50ms\n", 1)[1].split("\n\n", 1)[0]
        once = drive.index("static bool held_checked = false;")
        self.assertLess(drive.index("if (!id(idle).woke_from_sleep())"), once)
        self.assertLess(once, drive.index("id(idle).held_at_wake()"))
        self.assertIn("if ((held & (1u << 9)) && !id(button_expander)->digital_read(9)) {", drive)
        sw9 = statements(function_body(drive, "if ((held & (1u << 9))"))
        self.assertEqual(sw9, ["id(sw9_hold_consumed) = false;", "id(detect_wifi_hold).execute();"])
        self.assertNotIn("(held & (1u << 0))", drive)
        self.assertNotIn("detect_receiver_hold", drive)
        self.assertNotIn("exit_receiver_hold", drive)
        # The wake handling mirrors the on_press of each button.
        for name, bit, lines in (
            ("Button 9", 9, ["id(sw9_hold_consumed) = false;", "script.execute: detect_wifi_hold"]),
        ):
            entry = PRODUCTION.split(f"name: {name}\n", 1)[1].split("  - platform:", 1)[0]
            self.assertIn(f"number: {bit}\n", entry)
            on_press = entry[entry.index("on_press:"):entry.index("on_release:")]
            for line in lines:
                self.assertIn(line, on_press, name)

    def test_production_sleeps_on_a_sw5_hold(self) -> None:
        section = PRODUCTION.split("\nidle_sleep:\n", 1)[1].split("\n\n", 1)[0]
        self.assertIn("  sleep_hold_bit: 4\n", section)
        self.assertIn("  sleep_hold_time: 2s\n", section)
        button = PRODUCTION.split("name: Button 5\n", 1)[1].split("  - platform:", 1)[0]
        self.assertIn("number: 4\n", button)

    def test_production_defaults_to_five_minutes_and_links_the_page(self) -> None:
        section = PRODUCTION.split("\nidle_sleep:\n", 1)[1].split("\n\n", 1)[0]
        self.assertIn("  id: idle\n", section)
        self.assertIn("  sleep_after: 5min\n", section)
        self.assertIn("\nbutton_config:\n  id: button_cfg\n  idle_sleep_id: idle\n", PRODUCTION)
        self.assertNotIn("button_config", BENCH)

    def test_production_uses_idle_sleep_not_the_stock_deep_sleep(self) -> None:
        self.assertIn("\nidle_sleep:\n", PRODUCTION)
        # The stock component would fight IdleSleep.
        self.assertNotIn("\ndeep_sleep:", PRODUCTION)

    def test_replay_table_matches_the_binary_sensors(self) -> None:
        table = re.search(r"SLOT_OF_BIT\[16\] = \{([^}]*)\}", PRODUCTION).group(1)
        slots = [int(value) for value in table.split(",")]
        mapping = expander_bit_to_slot(PRODUCTION)
        self.assertEqual(sorted(mapping), list(range(16)))
        self.assertEqual(slots, [mapping[bit] for bit in range(16)])

    def test_only_the_release_tap_inputs_skip_a_held_replay(self) -> None:
        self.assertIn("if (held && (bit == 0 || bit == 9))", PRODUCTION)
        section = PRODUCTION[PRODUCTION.index("\nbinary_sensor:\n"):PRODUCTION.index("\nsensor:\n")]
        for entry in section.split("  - platform: gpio\n")[1:]:
            if "pcf8574: button_expander" not in entry and "<<: *button_1" not in entry:
                continue
            bit = int(re.search(r"number: (\d+)", entry).group(1))
            on_release = entry[entry.index("on_release:"):]
            taps_on_release = "ir_ui.tap(" in on_release
            self.assertEqual(taps_on_release, bit in (0, 9), f"expander bit {bit}")

    def test_production_awake_led_is_the_inverted_gpio15_output(self) -> None:
        output = PRODUCTION[PRODUCTION.index("    id: awake_led_pwm\n") - len("  - platform: ledc\n"):]
        output = output.split("\n\n", 1)[0]
        self.assertIn("  - platform: ledc\n    id: awake_led_pwm\n", output)
        self.assertIn("      number: GPIO15\n", output)
        self.assertIn("    inverted: true\n", output)
        light = PRODUCTION[PRODUCTION.index("  - platform: monochromatic\n    id: awake_led\n"):]
        light = light.split("\n\n", 1)[0]
        self.assertIn("  - platform: monochromatic\n    id: awake_led\n", light)
        self.assertIn("    output: awake_led_pwm\n", light)
        self.assertIn("    restore_mode: ALWAYS_ON\n", light)
        self.assertIn("      color_mode: brightness\n", light)
        self.assertNotIn("gamma_correct", light)
        self.assertNotIn("awake_led).turn_off", PRODUCTION)
        self.assertIn("GPIO_NUM_15", CPP.split("HELD_FLOATING[] = ", 1)[1].split(";", 1)[0])


class BenchConfigTest(unittest.TestCase):
    def test_bench_overlays_production_and_only_sets_the_wake_stub_and_trim(self) -> None:
        self.assertRegex(BENCH, r"packages:\n  base: !include c6remote\.yaml\n")
        section = BENCH.split("\nidle_sleep:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(section.splitlines(), [
            "  wake_stub: ${sleep_wake_stub}",
            "  boot_trim: ${sleep_boot_trim}",
        ])

    def test_bench_defines_no_led_and_logs_the_production_awake_led(self) -> None:
        self.assertNotIn("GPIO15", BENCH)
        self.assertNotIn("platform: ledc", BENCH)
        self.assertIn("  - interval: 5s\n", BENCH)
        self.assertIn('ESP_LOGI("awake_led"', BENCH)


if __name__ == "__main__":
    unittest.main()
