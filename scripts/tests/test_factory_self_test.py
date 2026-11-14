"""Static checks for the hardware self-test in the provisioning image."""

from pathlib import Path
import html
import math
import re
import unittest


ROOT = Path(__file__).parents[2]
FACTORY = (ROOT / "c6remote-factory.yaml").read_text()
CONFIG = (ROOT / "c6remote.yaml").read_text()
WORKFLOW = (ROOT / ".github" / "workflows" / "firmware.yml").read_text()
COMPONENT = ROOT / "components" / "self_test"
CPP = (COMPONENT / "self_test.cpp").read_text()
HEADER = (COMPONENT / "self_test.h").read_text()
INIT = (COMPONENT / "__init__.py").read_text()
IDLE_CPP = (ROOT / "components" / "idle_sleep" / "idle_sleep.cpp").read_text()
IDLE_HEADER = (ROOT / "components" / "idle_sleep" / "idle_sleep.h").read_text()
WAKE_STUB = (ROOT / "components" / "idle_sleep" / "wake_stub.h").read_text()
PAGE = (ROOT / "site" / "factory-self-test.html").read_text()


def page_text(markup: str) -> str:
    """The page with its tags gone, so a check reads what an operator reads."""
    bare = re.sub(r"<(script|style)\b.*?</\1>", " ", markup, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", bare))


# One line of running text, so a table row reads as "SW1 Red Green".
FLAT = re.sub(r"\s+", " ", page_text(PAGE))


def step_leds() -> dict:
    """The LED that each step heading names, keyed by the LED."""
    found = {}
    for heading in re.findall(r"<h3>(.*?)</h3>", PAGE, re.S):
        # Read the heading as text, so its markup can change freely.
        plain = re.sub(r"\s+", " ", page_text(heading)).strip()
        named = re.fullmatch(r"Step \d+:? (.+?) \(\s*(D\d)\s*\)", plain)
        if named:
            found[named.group(2)] = named.group(1).strip()
    return found


PROJECT_NAME = "landonr.homething-c6"
# The NEC leader mark, the longest header mark of a common IR protocol.
LONGEST_PROTOCOL_MARK_US = 9000


def top_level_block(text: str, key: str) -> str:
    """Returns the lines under one top-level key, up to the next top-level key."""
    lines = text.splitlines()
    try:
        start = lines.index(f"{key}:")
    except ValueError:
        raise AssertionError(f"no top-level {key}: block") from None
    body = []
    for line in lines[start + 1:]:
        if line and not line[0].isspace() and not line.startswith("#"):
            break
        body.append(line)
    return "\n".join(body) + "\n"


def without_comments(block: str) -> str:
    return "\n".join(line for line in block.splitlines() if not line.lstrip().startswith("#")) + "\n"


def list_entries(block: str) -> list[str]:
    """Splits a top-level list block into its entries."""
    entries = re.split(r"(?m)^  - ", without_comments(block))[1:]
    if not entries:
        raise AssertionError("the block has no list entries")
    return ["  - " + entry for entry in entries]


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


def constant(source: str, name: str) -> int:
    match = re.search(rf"\b{name} = (\d+);", source)
    if match is None:
        raise AssertionError(f"constant {name} not found")
    return int(match.group(1))


def colour_name(rgb) -> str:
    """The name of a status colour, from its channels alone."""
    red, green, blue = rgb
    lit = (red > 0, green > 0, blue > 0)
    simple = {(True, False, False): "red", (False, True, False): "green", (False, False, True): "blue",
              (True, False, True): "magenta", (True, True, True): "white"}
    if lit in simple:
        return simple[lit]
    if lit == (False, True, True):
        # Azure leans on blue, so it reads apart from cyan, which balances both.
        return "azure" if blue > green * 1.2 else "cyan"
    raise AssertionError(f"no name for {rgb}")


def named_colours(array: str, terminator: str) -> list:
    """Each (name in the comment, channels) pair of one colour array."""
    block = CPP[CPP.index(array):CPP.index(terminator)]
    return [(name, (int(r), int(g), int(b)))
            for r, g, b, name in re.findall(r"Color\((\d+), *(\d+), *(\d+)\),?\s+// (\w+)", block)]


def base_colours() -> list[str]:
    """Returns the name of each base colour, in the order of the component table."""
    block = CPP[CPP.index("BASE_COLOUR[5] = {"):CPP.index("INPUT_PAIR[16][2]")]
    return re.findall(r"(?m)^\s+Color\(\d+, \d+, \d+\),\s+// (\w+)$", block)


def input_pairs() -> list[tuple[str, str, str]]:
    """Returns the name, the top colour and the bottom colour of each expander bit."""
    bases = base_colours()
    table = CPP[CPP.index("INPUT_PAIR[16][2] = {"):]
    table = table[:table.index("};")]
    pairs = []
    for top, bottom, comment in re.findall(r"(?m)^\s+\{(\d), (\d)\},\s+// (.+)$", table):
        words = comment.lower().split()
        colours = (bases[int(top)], bases[int(bottom)])
        if tuple(words[-2:]) != colours:
            raise AssertionError(f"comment {comment!r} disagrees with the indices {top}, {bottom}")
        pairs.append((" ".join(words[:-2]), *colours))
    return pairs


def project(text: str) -> tuple[str, str]:
    match = re.search(r"\n  project:\n    name: (\S+)\n    (?:#.*\n    )*version: (\S+)\n",
                      top_level_block(text, "esphome"))
    if match is None:
        raise AssertionError("esphome: project: not found")
    return match.group(1), match.group(2)


class ProvisioningTest(unittest.TestCase):
    """The self-test rides on the provisioning image, so the update path must stay intact."""

    def test_the_factory_image_holds_no_wifi_credentials(self) -> None:
        self.assertNotIn("!secret", FACTORY)
        wifi = without_comments(top_level_block(FACTORY, "wifi"))
        self.assertNotRegex(wifi, r"(?m)^\s+(?:-\s+)?(?:ssid|password|networks)\s*:")
        self.assertNotRegex(wifi, r"(?m)^  ap\s*:")

    def test_the_factory_image_keeps_the_partition_table_and_project_name(self) -> None:
        self.assertEqual(project(FACTORY), (PROJECT_NAME, "factory"))
        self.assertEqual(project(CONFIG)[0], PROJECT_NAME)
        for name, text in (("c6remote.yaml", CONFIG), ("c6remote-factory.yaml", FACTORY)):
            with self.subTest(config=name):
                esp32 = top_level_block(text, "esp32")
                self.assertIn("  board: seeed_xiao_esp32c6\n", esp32)
                self.assertIn("  partitions: partitions.csv\n", esp32)

    def test_improv_and_the_install_stay_in_the_factory_image(self) -> None:
        self.assertIn("  authorizer: none\n", top_level_block(FACTORY, "esp32_improv"))
        self.assertIn("  id: improv_usb\n", top_level_block(FACTORY, "improv_serial"))
        self.assertIn("    - component.update: firmware_update\n", top_level_block(FACTORY, "wifi"))
        update = top_level_block(FACTORY, "update")
        self.assertIn("    on_update_available:\n      - update.perform:\n          id: firmware_update\n"
                      "          force_update: true\n", update)
        self.assertIn("update.is_available: firmware_update", top_level_block(FACTORY, "interval"))

    def test_only_the_two_needed_local_components_load(self) -> None:
        external = top_level_block(FACTORY, "external_components")
        self.assertIn("      path: components\n", external)
        self.assertIn("    components: [idle_sleep, self_test]\n", external)


class TransmitTest(unittest.TestCase):
    """A customer runs this image at home, so IR goes out only on an operator hold."""

    def test_the_config_has_no_transmit_action(self) -> None:
        self.assertNotRegex(without_comments(FACTORY), r"remote_transmitter\.transmit|transmit_\w+:")

    def test_the_component_transmits_only_from_the_sw1_hold(self) -> None:
        self.assertEqual(CPP.count("->transmit()"), 1)
        self.assertIn("->transmit()", function_body(CPP, "void SelfTest::start_transmit_(uint32_t now)"))
        calls = [m.start() for m in re.finditer(r"this->start_transmit_\(", CPP)]
        self.assertEqual(len(calls), 1)
        holds = function_body(CPP, "void SelfTest::update_long_presses_(uint32_t now)")
        self.assertIn("if (bit == TRANSMIT_BIT) {\n      this->start_transmit_(now);", holds)
        self.assertIn(
            "if (now - this->pressed_at_ms_[bit] < (bit == SLEEP_BIT ? SLEEP_HOLD_MS : LONG_PRESS_MS))\n"
            "      continue;", holds)
        self.assertEqual(constant(HEADER, "TRANSMIT_BIT"), 0)
        self.assertGreaterEqual(constant(HEADER, "LONG_PRESS_MS"), 1500)
        for name in ("void SelfTest::input(", "void SelfTest::encoder_step(", "void SelfTest::ir_frame(",
                     "void SelfTest::battery_sample(", "void SelfTest::setup()", "void SelfTest::render("):
            with self.subTest(function=name):
                body = function_body(CPP, name)
                self.assertNotIn("start_transmit_", body)
                self.assertNotIn("transmit()", body)

    def test_a_camera_sees_the_flashes(self) -> None:
        mark = constant(HEADER, "TX_MARK_US")
        space = constant(HEADER, "TX_SPACE_US")
        bursts = constant(HEADER, "TX_BURSTS")
        self.assertEqual(constant(HEADER, "TX_CARRIER_HZ"), 38000)
        total_ms = bursts * (mark + space) / 1000
        self.assertGreaterEqual(total_ms, 2500)
        self.assertLessEqual(total_ms, 3500)
        # A 30 fps camera must see each flash and each gap.
        self.assertGreaterEqual(mark, 34000)
        self.assertGreaterEqual(space, 34000)

    def test_a_flash_goes_out_as_bursts_that_a_receiver_accepts(self) -> None:
        mark = constant(HEADER, "TX_MARK_US")
        space = constant(HEADER, "TX_SPACE_US")
        chop_mark = constant(HEADER, "TX_CHOP_MARK_US")
        chop_space = constant(HEADER, "TX_CHOP_SPACE_US")
        # The AGC of U2 gives up on a mark of protocol length or longer, so no
        # burst can reach one. The 10-cycle floor at 38 kHz is 263 us.
        self.assertLess(chop_mark, LONGEST_PROTOCOL_MARK_US)
        self.assertGreater(chop_mark, 263)
        self.assertGreater(chop_space, 263)
        # The gap inside a flash must stay under the 10 ms receiver idle, so
        # one flash arrives as one frame.
        self.assertLess(chop_space, 10000)
        chops = mark // (chop_mark + chop_space)
        self.assertGreaterEqual(chops, 8)
        gap = mark + space - (chops * (chop_mark + chop_space) - chop_space)
        # The gap carries the rounding, so the flash period stays exact.
        self.assertEqual(chops * (chop_mark + chop_space) - chop_space + gap, mark + space)
        start = function_body(CPP, "void SelfTest::start_transmit_(uint32_t now)")
        self.assertIn("data->set_carrier_frequency(TX_CARRIER_HZ);", start)
        self.assertIn("data->item(TX_CHOP_MARK_US, TX_CHOP_SPACE_US);", start)
        self.assertIn("data->item(TX_CHOP_MARK_US, TX_GAP_US);", start)
        self.assertNotIn("data->item(TX_MARK_US", start)

    def test_the_receive_check_ignores_the_board_own_bursts(self) -> None:
        body = function_body(CPP, "void SelfTest::ir_frame(const std::vector<int32_t> &raw)")
        self.assertIn("now - this->tx_start_ms_ < TX_TOTAL_MS + IR_ECHO_MS", body)
        self.assertLess(body.index("IR_ECHO_MS"), body.index("this->ir_rx_passed_ = true;"))
        # The transmit window is the only self-filter, so a second board can answer this check.
        self.assertNotIn("IR_OWN_MARK_US", CPP)


class SecondPageTest(unittest.TestCase):
    def test_the_radio_check_is_gone(self) -> None:
        """The U1 module carries the antenna, so the station does not test the radios."""
        for token in ("update_radios_", "wifi_scan_event_", "wifi_scan_passed_", "ble_advertising_passed_",
                      "gap_event_handler", "RADIO_RETRY_MS", "RADIO_SCAN_TIMEOUT_MS", "RADIO_FAIL_MS",
                      "SCAN_DONE", "SCAN_SUCCESS", "esp_wifi_scan_start"):
            with self.subTest(token=token):
                self.assertNotIn(token, CPP)
                self.assertNotIn(token, HEADER)
        self.assertNotIn("register_gap_event_handler", INIT)
        self.assertNotIn("esp32_ble", INIT)
        # The component no longer reaches into those stacks, so it does not depend on them.
        for dependency in ('"wifi"', '"esp32_improv"'):
            with self.subTest(dependency=dependency):
                self.assertNotIn(dependency, INIT)

    def test_the_second_page_uses_distinct_positions_on_both_boards(self) -> None:
        page = function_body(CPP, "void SelfTest::draw_second_page_(")
        self.assertIn("it.all() = Color::BLACK;", page)
        self.assertIn("it[LED_D3] = this->sleep_wake_passed_ ? PASSED : PENDING;", page)
        self.assertIn("it[d5] = SECOND_PAGE;", page)
        mapping = re.search(r"const int32_t d5 = it.size\(\) >= (\d+) \? (\d+) : (\d+);", page)
        self.assertIsNotNone(mapping)
        threshold, v3_index, v2_index = map(int, mapping.groups())
        for count in (4, 6):
            with self.subTest(leds=count):
                positions = {"wake": constant(CPP, "LED_D3"),
                             "page": v3_index if count >= threshold else v2_index}
                self.assertEqual(positions, {"wake": 1, "page": 3 if count == 4 else 4})
                self.assertEqual(len(set(positions.values())), 2)
                self.assertTrue(all(0 <= index < count for index in positions.values()))
        render = function_body(CPP, "void SelfTest::render(light::AddressableLight &it)")
        self.assertIn("if (this->second_page_)", render)
        self.assertIn("this->draw_second_page_(it);", render)


class SleepTest(unittest.TestCase):
    # Every check of the two overviews. A wake must start each one at pending.
    CHECK_RESULTS = (
        "seen_mask_", "cw_seen_", "ccw_seen_", "mic_passed_", "ir_rx_passed_", "tx_done_",
        "battery_passed_", "usb_plugged_seen_", "usb_unplugged_seen_",
    )

    def test_no_result_snapshot_crosses_the_sleep(self) -> None:
        """A wake starts a fresh test, so an operator cannot read the previous board."""
        for token in ("RtcResults", "s_results", "results_checksum", "RESULTS_MAGIC", "RESULTS_VERSION",
                      "RESULTS_FLAGS", "RESULT_", "load_results_", "save_results_", "on_shutdown"):
            with self.subTest(token=token):
                self.assertNotIn(token, CPP)
                self.assertNotIn(token, HEADER)
        # One value stays in RTC memory, and it records only the deliberate sleep request.
        self.assertEqual(re.findall(r"RTC_DATA_ATTR (\w+) (\w+)", CPP), [("uint32_t", "s_sleep_test_armed")])
        for flash_operation in ("global_preferences", "make_preference", "nvs_set", "->save("):
            self.assertNotIn(flash_operation, CPP)

    def test_every_check_but_the_wake_starts_again_at_pending(self) -> None:
        setup = function_body(CPP, "void SelfTest::setup()")
        for member in self.CHECK_RESULTS:
            with self.subTest(result=member):
                # The member initialiser is the only starting value after a wake.
                self.assertRegex(HEADER, rf"\b{member}\{{(?:false|0)\}};")
                self.assertNotIn(f"this->{member}", setup)
        self.assertIn("bool inputs_logged_{false};", HEADER)

    def test_deliberate_sleep_waits_for_release_and_rechecks_the_guard(self) -> None:
        update = function_body(CPP, "void SelfTest::update_sleep_()")
        arm = update.index("this->idle_->arm_sleep(")
        for gate in ("!this->sleep_requested_ || this->held_mask_ != 0", "!this->allow_sleep_()"):
            self.assertLess(update.index(gate), arm)
        self.assertIn("[this]() { return this->allow_sleep_(); }", update)
        allow = function_body(CPP, "bool SelfTest::allow_sleep_()")
        self.assertIn("const char *blocked = this->sleep_block_();", allow)
        self.assertIn("if (blocked == nullptr)\n    return true;", allow)
        self.assertIn("this->sleep_requested_ = false;", allow)
        self.assertIn("s_sleep_test_armed = 0;", allow)
        self.assertIn('ESP_LOGI(TAG, "Sleep test refused: %s", blocked);', allow)
        block = function_body(CPP, "const char *SelfTest::sleep_block_()")
        self.assertIn("if (!this->sleep_blocked_by_)", block)
        self.assertIn("this->installing_", block)
        self.assertIn("this->transmitting_(millis())", block)
        self.assertIn("return this->sleep_blocked_by_();", block)
        # Each refusal names one condition, so the log says which one blocked it.
        reasons = re.findall(r'return "([^"]+)";', block)
        self.assertEqual(len(reasons), len(set(reasons)))
        self.assertGreaterEqual(len(reasons), 3)
        self.assertIn("void arm_sleep(std::function<bool()> guard);", IDLE_HEADER)
        guarded_arm = function_body(IDLE_CPP, "void IdleSleep::arm_sleep(std::function<bool()> guard)")
        self.assertIn("this->forced_sleep_guard_ = std::move(guard);", guarded_arm)
        self.assertIn("this->arm_sleep();", guarded_arm)
        forced = function_body(IDLE_CPP, "void IdleSleep::try_sleep_()").split("  } else {", 1)[0]
        self.assertIn("this->pressed_ != 0", forced)
        self.assertIn("this->forced_sleep_guard_ && !this->forced_sleep_guard_()", forced)
        self.assertIn("this->forced_sleep_ = false;", forced)
        self.assertIn("this->forced_sleep_guard_ = {};", forced)
        self.assertLess(forced.index("this->pressed_ != 0"), forced.index("!this->forced_sleep_guard_()"))

    def test_deliberate_sleep_preserves_provisioning_and_installation(self) -> None:
        probe = top_level_block(FACTORY, "self_test").split("  sleep_blocked_by: !lambda |-\n", 1)[1]
        probe = probe.split("  light_id:", 1)[0]
        for gate in ("wifi::global_wifi_component->has_sta()", "wifi::global_wifi_component->is_connected()",
                     "improv::STATE_PROVISIONING", "ble->get_client_count() > 0",
                     "update::UPDATE_STATE_INSTALLING"):
            with self.subTest(gate=gate):
                self.assertIn(gate, probe)
        self.assertNotIn("usb_present()", probe)
        # One reason for each condition, and nullptr when the sleep test can run.
        reasons = re.findall(r'return "([^"]+)";', probe)
        self.assertEqual(len(reasons), 5)
        self.assertEqual(len(reasons), len(set(reasons)))
        self.assertIn("return nullptr;", probe)
        self.assertIn("  idle_sleep_id: idle\n", top_level_block(FACTORY, "self_test"))
        self.assertIn("var.set_idle_sleep(idle)", INIT)
        self.assertIn("return_type=cg.const_char_ptr", INIT)
        self.assertIn("var.set_sleep_blocked_by(blocked_by)", INIT)

    def test_only_the_requested_ext1_wake_with_a_stub_latch_passes(self) -> None:
        self.assertIn("RTC_DATA_ATTR uint32_t s_sleep_test_armed = 0;", CPP)
        setup = function_body(CPP, "void SelfTest::setup()")
        self.assertIn("const bool requested_wake = s_sleep_test_armed == SLEEP_TEST_MAGIC;", setup)
        self.assertIn("s_sleep_test_armed = 0;", setup)
        self.assertLess(setup.index("s_sleep_test_armed = 0;"), setup.index("this->sleep_wake_passed_ ="))
        passed = setup[setup.index("this->sleep_wake_passed_ ="):setup.index("this->second_page_ =")]
        for gate in ("requested_wake", "esp_reset_reason() == ESP_RST_DEEPSLEEP",
                     "esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT1", "this->idle_->held_at_wake() != 0"):
            with self.subTest(gate=gate):
                self.assertIn(gate, passed)
        # A failed wake still opens the page that carries the result.
        self.assertIn("this->second_page_ = requested_wake && esp_reset_reason() == ESP_RST_DEEPSLEEP;", setup)
        update = function_body(CPP, "void SelfTest::update_sleep_()")
        self.assertLess(update.index("s_sleep_test_armed = SLEEP_TEST_MAGIC;"), update.index("this->idle_->arm_sleep("))
        idle_setup = function_body(IDLE_CPP, "void IdleSleep::setup()")
        self.assertIn("latch.magic == IDLE_SLEEP_LATCH_MAGIC", idle_setup)
        self.assertIn("latch.flags & IDLE_SLEEP_STUB_ACK", idle_setup)
        self.assertIn("this->held_mask_ = rec.stub_down & first_down;", idle_setup)
        self.assertIn("IDLE_SLEEP_STUB_ACK", WAKE_STUB)

    def test_idle_sleep_runs_with_the_gpio5_wake(self) -> None:
        sleep = top_level_block(FACTORY, "idle_sleep")
        self.assertIn("  id: idle\n", sleep)
        self.assertIn("  sleep_after: 5min\n", sleep)
        self.assertIn("static constexpr gpio_num_t WAKE_PIN = GPIO_NUM_5;", IDLE_CPP)
        self.assertIn("esp_sleep_enable_ext1_wakeup_io(BIT64(WAKE_PIN), ESP_EXT1_WAKEUP_ANY_LOW);", IDLE_CPP)
        # The expander INT on GPIO5 is the wake source, so the config must poll the same part.
        expander = top_level_block(FACTORY, "pcf8574")
        self.assertIn("    address: 0x20\n", expander)
        self.assertIn("    pcf8575: true\n", expander)

    def test_usb_power_provisioning_and_the_install_block_sleep(self) -> None:
        probe = top_level_block(FACTORY, "idle_sleep").split("  block_probe: !lambda |-\n", 1)[1]
        self.assertIn("id(hw_test).usb_present()", probe)
        self.assertIn("improv::STATE_PROVISIONING", probe)
        self.assertIn("get_client_count() > 0", probe)
        self.assertIn("id(hw_test).installing()", probe)
        self.assertIn("update::UPDATE_STATE_INSTALLING", probe)
        # A unit without internet access must still sleep after a failed check.
        self.assertIn("!id(firmware_update).status_has_error()", probe)
        # idle_sleep sees only the expander, so the wheel and IR frames report through the self-test.
        self.assertIn("id(hw_test).recently_active(millis())", probe)
        self.assertIn("return mask != 0 || active;", probe)
        for name in ("void SelfTest::encoder_step(", "void SelfTest::ir_frame(", "void SelfTest::update_usb_("):
            with self.subTest(function=name):
                self.assertIn("this->mark_active_(", function_body(CPP, name))
        self.assertIn("bool usb_present() const { return this->v3_ && this->usb_known_ && this->usb_present_; }",
                      HEADER)

    def test_the_rails_and_gpio17_are_safe_before_sleep(self) -> None:
        shutdown = top_level_block(FACTORY, "esphome").split("  on_shutdown:\n", 1)[1]
        self.assertIn("    - switch.turn_off: led_rail\n", shutdown)
        self.assertIn("    - switch.turn_off: ir_rail\n", shutdown)
        self.assertIn("gpio_set_pull_mode(GPIO_NUM_17, GPIO_PULLDOWN_ONLY);", shutdown)
        self.assertIn("gpio_set_direction(GPIO_NUM_18, GPIO_MODE_INPUT);", shutdown)
        held = re.search(r"HELD_FLOATING\[\] = \{([^}]*)\}", IDLE_CPP).group(1)
        for pin in ("GPIO_NUM_6", "GPIO_NUM_18"):
            self.assertIn(pin, held)
        self.assertIn("HELD_PULLDOWN = GPIO_NUM_17;", IDLE_CPP)

    def test_the_light_owns_the_led_rail(self) -> None:
        light = top_level_block(FACTORY, "light")
        on = light.split("    on_turn_on:\n", 1)[1].split("    on_turn_off:\n", 1)[0]
        self.assertIn("      - switch.turn_on: led_rail\n", on)
        self.assertIn("            - switch.turn_off: led_rail\n", light.split("    on_turn_off:\n", 1)[1])
        switches = list_entries(top_level_block(FACTORY, "switch"))
        led = next(e for e in switches if "id: led_rail" in e)
        ir = next(e for e in switches if "id: ir_rail" in e)
        self.assertIn("number: GPIO18", led)
        self.assertIn("restore_mode: ALWAYS_OFF", led)
        self.assertIn("number: GPIO6", ir)
        self.assertIn("restore_mode: ALWAYS_ON", ir)
        for entry in (led, ir):
            self.assertIn("inverted: true", entry)


class MicrophoneTest(unittest.TestCase):
    def test_the_bit_clock_is_in_the_dmm_4026_normal_range(self) -> None:
        mic = top_level_block(FACTORY, "microphone")
        rate = int(re.search(r"(?m)^    sample_rate: (\d+)$", mic).group(1))
        bits = int(re.search(r"(?m)^    bits_per_sample: (\d+)bit$", mic).group(1))
        # I2S standard mode always clocks two slots.
        bclk = rate * 2 * bits
        self.assertGreaterEqual(bclk, 2_048_000)
        self.assertLessEqual(bclk, 4_096_000)
        # The V2 ICS-43434 has no mode between its Low-Power and High-Performance bands.
        self.assertFalse(18_750 < rate < 23_000)
        self.assertIn("    channel: left\n", mic)
        self.assertIn("    pdm: false\n", mic)
        self.assertIn("    i2s_din_pin: GPIO21\n", mic)

    def test_a_key_knock_alone_cannot_pass_the_check(self) -> None:
        """A key press puts about -35 dBFS into MK1 through the board."""
        loud = constant(CPP, "MIC_LOUD")
        self.assertGreater(20 * math.log10(loud / 32768), -30)
        self.assertGreaterEqual(constant(CPP, "MIC_SWING"), 10)
        body = function_body(CPP, "void SelfTest::update_mic_(uint32_t now)")
        self.assertIn("peak >= MIC_LOUD && this->mic_floor_ != UINT32_MAX &&", body)
        self.assertIn("peak >= MIC_SWING * this->mic_floor_", body)

    def test_the_mic_starts_after_every_setup(self) -> None:
        self.assertIn("float get_setup_priority() const override { return setup_priority::LATE; }", HEADER)
        self.assertIn("this->mic_->start();", function_body(CPP, "void SelfTest::setup()"))


class BoardVariantTest(unittest.TestCase):
    def test_the_release_builds_the_factory_image_for_v3(self) -> None:
        self.assertIn("esphome -s status_led_count 6 compile c6remote-factory.yaml", WORKFLOW)
        self.assertEqual(re.search(r'(?m)^  status_led_count: (.+)$', top_level_block(FACTORY, "substitutions"))
                         .group(1), '"4"')
        self.assertIn("    num_leds: ${status_led_count}\n", top_level_block(FACTORY, "light"))
        self.assertIn("this->v3_ = this->led_count_ >= 6;", CPP)

    def test_gpio7_is_read_only_on_v3(self) -> None:
        setup = function_body(CPP, "void SelfTest::setup()")
        guard = setup.index("if (this->v3_ && this->usb_pin_ != nullptr) {")
        self.assertLess(guard, setup.index("this->usb_pin_->setup();"))
        self.assertEqual(CPP.count("this->usb_pin_->setup();"), 1)
        self.assertIn("if (!this->v3_ || this->usb_pin_ == nullptr)\n    return;",
                      function_body(CPP, "void SelfTest::update_usb_(uint32_t now)"))
        pin = top_level_block(FACTORY, "self_test").split("  usb_present_pin:\n", 1)[1]
        self.assertIn("    number: GPIO7\n", pin)
        self.assertIn("    inverted: true\n", pin)

    def test_the_strip_order_is_the_chain_order(self) -> None:
        """D2 D3 D4 D5 on V2, D2 D3 D6 D4 D5 D7 on V3."""
        self.assertEqual(constant(CPP, "LED_D2"), 0)
        self.assertEqual(constant(CPP, "LED_D3"), 1)
        self.assertEqual(constant(CPP, "LED_D6"), 2)
        self.assertEqual(constant(CPP, "LED_D7"), 5)
        overview = function_body(CPP, "void SelfTest::draw_overview_(light::AddressableLight &it) const")
        self.assertIn("const int32_t d4 = six ? 3 : 2;", overview)
        self.assertIn("const int32_t d5 = six ? 4 : 3;", overview)


class InputTest(unittest.TestCase):
    def test_the_new_holds_do_not_share_existing_functions(self) -> None:
        bits = {name: constant(HEADER, name) for name in ("TRANSMIT_BIT", "VU_BIT", "PAGE_BIT", "SLEEP_BIT")}
        self.assertEqual(len(set(bits.values())), 4)
        self.assertEqual(bits["PAGE_BIT"], 1)
        self.assertEqual(bits["SLEEP_BIT"], 2)
        self.assertEqual(constant(HEADER, "LONG_PRESS_MS"), 2000)
        # Only the sleep hold is longer, so a button held in step 2 cannot sleep the board.
        self.assertEqual(constant(HEADER, "SLEEP_HOLD_MS"), 3000)
        self.assertGreater(constant(HEADER, "SLEEP_HOLD_MS"), constant(HEADER, "LONG_PRESS_MS"))
        holds = function_body(CPP, "void SelfTest::update_long_presses_(uint32_t now)")
        for bit in bits:
            self.assertIn(bit, holds)
        # The sleep hold works on both overviews and in the VU meter.
        self.assertNotIn("bit == SLEEP_BIT &&", holds)
        self.assertNotIn("else if (this->second_page_", holds)
        self.assertIn("this->sleep_requested_ = this->allow_sleep_();", holds)
        self.assertIn("this->sleep_armed_until_ms_ = now + SLEEP_ARMED_FLASH_MS;", holds)

    def test_the_sleep_hold_answers_on_every_display_mode(self) -> None:
        """A dark blue ring flash arms, and a red ring flash refuses, on either overview."""
        self.assertIn("static const Color SLEEP_ARMED_FLASH(0, 0, 64);", CPP)
        self.assertEqual(constant(CPP, "SLEEP_ARMED_FLASH_MS"), 500)
        self.assertEqual(constant(CPP, "SLEEP_REFUSED_MS"), 1500)
        render = function_body(CPP, "void SelfTest::render(light::AddressableLight &it)")
        armed = render.index("it.all() = SLEEP_ARMED_FLASH;")
        refused = render.index("it.all() = FAILED;")
        self.assertIn("if (static_cast<int32_t>(this->sleep_armed_until_ms_ - now) > 0)", render)
        self.assertIn("if (static_cast<int32_t>(this->sleep_refused_until_ms_ - now) > 0)", render)
        # Last in the frame, so a page, the VU meter and a held input cannot cover it.
        for earlier in ("this->draw_second_page_(it);", "this->draw_vu_(it);", "this->draw_overview_(it);",
                        "this->draw_input_(it, this->shown_bit_);", "it.all() = TRANSMIT;"):
            self.assertLess(render.index(earlier), armed)
        self.assertLess(armed, refused)
        page = function_body(CPP, "void SelfTest::draw_second_page_(")
        self.assertNotIn("sleep_refused_until_ms_", page)

    def test_every_expander_bit_feeds_the_self_test(self) -> None:
        bits = []
        for entry in list_entries(top_level_block(FACTORY, "binary_sensor")):
            bit = int(re.search(r"number: (\d+)", entry).group(1))
            bits.append(bit)
            with self.subTest(bit=bit):
                self.assertIn("pcf8574: button_expander" if bit == 0 else "<<: *expander_pin", entry)
                self.assertIn(f"- lambda: id(hw_test).input({bit}, true);", entry)
                self.assertIn(f"- lambda: id(hw_test).input({bit}, false);", entry)
        self.assertEqual(sorted(bits), list(range(16)))

    def test_the_bit_order_matches_the_production_config(self) -> None:
        """SW9 is bit 9 and SW10 is bit 8 in c6remote.yaml."""
        for name, bit in (("sw9", 9), ("sw10", 8), ("wheel_press", 13), ("sw1", 0)):
            entry = next(e for e in list_entries(top_level_block(FACTORY, "binary_sensor"))
                         if re.search(rf"(?m)^    id: {name}$", e))
            self.assertIn(f"number: {bit}\n", entry)
        self.assertIn("name: Button 9\n    pin:\n      <<: *button_1\n      number: 9\n", CONFIG)
        self.assertIn("name: Button 10\n    pin:\n      <<: *button_1\n      number: 8\n", CONFIG)
        self.assertEqual(constant(HEADER, "VU_BIT"), 13)

    def test_both_encoder_directions_feed_the_self_test(self) -> None:
        encoder = next(e for e in list_entries(top_level_block(FACTORY, "sensor")) if "rotary_encoder" in e)
        self.assertIn("number: GPIO19", encoder)
        self.assertIn("number: GPIO20", encoder)
        self.assertIn("on_clockwise:\n      - lambda: id(hw_test).encoder_step(true);", encoder)
        self.assertIn("on_anticlockwise:\n      - lambda: id(hw_test).encoder_step(false);", encoder)


class ComponentIdTest(unittest.TestCase):
    LIST_BLOCKS = ("pcf8574", "binary_sensor", "sensor", "light", "switch", "microphone")
    MAP_BLOCKS = ("self_test", "idle_sleep", "i2c", "remote_receiver", "remote_transmitter", "i2s_audio")

    def test_every_self_test_component_has_an_id(self) -> None:
        for key in self.LIST_BLOCKS:
            for entry in list_entries(top_level_block(FACTORY, key)):
                with self.subTest(block=key, entry=entry.splitlines()[0]):
                    self.assertRegex(entry, r"(?m)^  (?:- |  )id: \w+$")
        for key in self.MAP_BLOCKS:
            with self.subTest(block=key):
                self.assertRegex(top_level_block(FACTORY, key), r"(?m)^  id: \w+$")

    def test_the_component_codegen_takes_each_part_by_id(self) -> None:
        for name in ("light_id", "microphone_id", "transmitter_id", "usb_present_pin"):
            self.assertIn(f'"{name}"', INIT)
        self.assertIn("ota.request_ota_state_listeners()", INIT)


class BootAnimationTest(unittest.TestCase):
    """The factory image opens with the production boot chase and nothing else."""

    @staticmethod
    def production_chase() -> str:
        """Returns the boot chase block of the Status Indicators effect."""
        block = CONFIG[CONFIG.index("// Boot chase:"):]
        return block[:block.index("id(boot_chase_done) = true;")]

    def test_the_palette_matches_the_production_config(self) -> None:
        table = CPP[CPP.index("CHASE_COLOUR[6] = {"):]
        table = table[:table.index("};")]
        colours = re.findall(r"Color\((\d+), (\d+), (\d+)\)", self.production_chase())
        self.assertEqual(len(colours), 6)
        self.assertEqual(re.findall(r"Color\((\d+), (\d+), (\d+)\)", table), colours)

    def test_the_lap_the_laps_and_the_peak_match_the_production_config(self) -> None:
        self.assertIn("const uint32_t step = 600 / it.size();", CONFIG)
        self.assertEqual(constant(CPP, "CHASE_LAP_MS"), 600)
        self.assertIn("const uint32_t pulses = 2 * it.size();", self.production_chase())
        self.assertEqual(constant(CPP, "CHASE_LAPS"), 2)
        self.assertIn("160.0f * (0.5f - 0.5f * cosf(", self.production_chase())
        self.assertIn("CHASE_PEAK = 160.0f;", CPP)

    def test_the_pulse_shape_and_the_index_mapping_match_the_production_config(self) -> None:
        body = function_body(CPP, "void SelfTest::draw_chase_(")
        self.assertIn("t >= start + 3 * step", body)
        self.assertIn("t >= start + 3 * step", self.production_chase())
        self.assertIn("0.5f - 0.5f * cosf(2.0f * static_cast<float>(M_PI) * phase)", body)
        # A four-LED chain skips magenta and cyan.
        self.assertIn("n >= 6 ? led % 6 : (led >= 2 ? led + 1 : led)", body)
        self.assertIn("it.size() >= 6 ? led % 6 : (led >= 2 ? led + 1 : led)", self.production_chase())
        self.assertIn("it.all() = Color::BLACK;", body)

    def test_the_chase_runs_for_two_laps_at_each_led_count(self) -> None:
        self.assertIn("return (CHASE_LAPS * n + 2) * (CHASE_LAP_MS / n);", CPP)
        laps, lap_ms = constant(CPP, "CHASE_LAPS"), constant(CPP, "CHASE_LAP_MS")
        duration = {n: (laps * n + 2) * (lap_ms // n) for n in (4, 6)}
        self.assertEqual(duration, {4: 1500, 6: 1400})

    def test_the_overview_follows_the_chase_with_no_gap(self) -> None:
        body = function_body(CPP, "void SelfTest::render(light::AddressableLight &it)")
        self.assertIn("const uint32_t since = now - this->intro_start_ms_;", body)
        self.assertIn("const uint32_t chase = chase_ms(static_cast<uint32_t>(n));", body)
        self.assertIn("if (since < chase) {\n    this->draw_chase_(it, since);\n    return;\n  }\n\n"
                      "  if (this->vu_mode_) {", body)
        self.assertLess(body.index("draw_chase_"), body.index("draw_overview_"))

    def test_the_boot_has_no_colour_sweep(self) -> None:
        """Bench feedback dropped the sweep, so no table, constant or branch may survive."""
        for token in ("SWEEP", "sweep"):
            with self.subTest(token=token):
                self.assertNotIn(token, CPP)
                self.assertNotIn(token, HEADER)

    def test_a_wake_from_deep_sleep_plays_the_chase_again(self) -> None:
        """A wake must keep the approved boot animation."""
        self.assertIn("bool intro_started_{false};", HEADER)
        render = function_body(CPP, "void SelfTest::render(light::AddressableLight &it)")
        intro = render[render.index("const uint32_t since ="):render.index("if (this->vu_mode_)")]
        self.assertNotIn("woke_from_sleep", intro)
        self.assertNotIn("sleep_wake_passed_", intro)

    def test_the_production_config_keeps_its_own_chase(self) -> None:
        """c6remote.yaml must not lose the chase that the factory image copies."""
        self.assertIn("static bool boot_chase = !id(idle).woke_from_sleep() && id(button_cfg).boot_leds();", CONFIG)


class DocTest(unittest.TestCase):
    CHECKS = {
        "inputs_passed_": "Buttons and wheel",
        "mic_passed_": "Microphone",
        "ir_rx_passed_": "IR receive",
        "battery_passed_": "Battery",
        "tx_done_": "IR transmit",
        "usb_passed_": "USB power",
    }
    LED_OF_INDEX = {"LED_D2": "D2", "LED_D3": "D3", "d4": "D4", "d5": "D5", "LED_D6": "D6", "LED_D7": "D7"}

    def test_each_step_heading_names_the_led_that_the_overview_lights(self) -> None:
        overview = function_body(CPP, "void SelfTest::draw_overview_(light::AddressableLight &it) const")
        code = {}
        for index, check in re.findall(r"show\((\w+), this->(\w+?)(?:\(\))?\);", overview):
            code[self.LED_OF_INDEX[index]] = self.CHECKS[check]
        self.assertEqual(len(code), 6)
        self.assertEqual(step_leds(), code)

    def test_the_input_colour_table_matches_the_component(self) -> None:
        pairs = input_pairs()
        self.assertEqual(len(pairs), 16)
        # The page says "center", and the component says "centre".
        page = FLAT.lower().replace("center", "centre")
        for name, top, bottom in pairs:
            with self.subTest(input=name):
                self.assertIn(f"{name} {top} {bottom}".lower(), page)

    def test_each_input_has_its_own_pair_of_colours(self) -> None:
        pairs = [(top, bottom) for _, top, bottom in input_pairs()]
        self.assertEqual(len(set(pairs)), 16)
        bases = base_colours()
        self.assertGreaterEqual(len(set(bases)), 5)
        self.assertEqual(len(bases), len(set(bases)))
        self.assertEqual(set(bases), {name for pair in pairs for name in pair})

    def test_no_input_uses_one_colour_on_both_halves(self) -> None:
        """A pair of the same colour lights the whole ring in one colour."""
        for name, top, bottom in input_pairs():
            with self.subTest(input=name):
                self.assertNotEqual(top, bottom)

    def test_a_held_input_splits_the_ring_into_two_halves(self) -> None:
        """The chain is D2 D3 D4 D5 on V2 and D2 D3 D6 D4 D5 D7 on V3, so 1 to n / 2 is the top."""
        body = function_body(CPP, "void SelfTest::draw_input_(light::AddressableLight &it, uint8_t bit) const")
        self.assertIn("const bool top = i >= 1 && i <= n / 2;", body)
        self.assertIn("it[i] = BASE_COLOUR[INPUT_PAIR[bit][top ? 0 : 1]];", body)
        self.assertIn("this->draw_input_(it, this->shown_bit_);",
                      function_body(CPP, "void SelfTest::render(light::AddressableLight &it)"))
        for count, top, bottom in ((4, [1, 2], [0, 3]), (6, [1, 2, 3], [0, 4, 5])):
            with self.subTest(leds=count):
                self.assertEqual([i for i in range(count) if 1 <= i <= count // 2], top)
                self.assertEqual([i for i in range(count) if not 1 <= i <= count // 2], bottom)

    def test_each_colour_name_matches_its_channels(self) -> None:
        """The page and the tables read names, so a name must match its own RGB."""
        bases = named_colours("BASE_COLOUR[5] = {", "INPUT_PAIR[16][2]")
        self.assertEqual(len(bases), 5)
        for name, rgb in bases:
            with self.subTest(colour=name):
                self.assertEqual(colour_name(rgb), name)
        chase = CPP[CPP.index("in chain order:"):CPP.index("// Green is brighter than red")]
        comment = re.findall(r"D\d (\w+)", chase)
        values = [(int(r), int(g), int(b))
                  for r, g, b in re.findall(r"Color\((\d+), *(\d+), *(\d+)\)", chase)]
        self.assertEqual(len(comment), 6)
        self.assertEqual(len(values), 6)
        for name, rgb in zip(comment, values):
            with self.subTest(colour=name):
                self.assertEqual(colour_name(rgb), name)

    def test_the_first_step_table_matches_the_chase_palette(self) -> None:
        comment = CPP[:CPP.index("static const Color CHASE_COLOUR[6]")]
        code = re.findall(r"(D\d) (\w+)", comment[comment.rindex("in chain order:"):])
        self.assertEqual(len(code), 6)
        for led, colour in code:
            with self.subTest(led=led):
                self.assertIn(f"{led} {colour}".lower(), FLAT.lower())


if __name__ == "__main__":
    unittest.main()
