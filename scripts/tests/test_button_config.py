"""Regression checks for the /buttons web configurator component."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[2]
COMPONENT = ROOT / "components" / "button_config"
CPP = (COMPONENT / "button_config.cpp").read_text()
HEADER = (COMPONENT / "button_config.h").read_text()
PAGE = (COMPONENT / "button_config_page.h").read_text()
INIT = (COMPONENT / "__init__.py").read_text()
CONFIG = (ROOT / "c6remote.yaml").read_text()
STORE = (ROOT / "ir_learning.h").read_text()

# Slots that cannot start the voice assistant. 19 is SW2, whose press edge is
# already owned by the receiver-mode hold gesture. 17 and 18 are the wheel
# detents, which have no release edge to end push-to-talk with.
NO_VOICE = {17, 18, 19}
ALL_SLOTS = list(range(3, 21))


def section(text: str, start: str, end: str) -> str:
    """Return the text between the first start marker and the next end marker."""
    head = text.split(start, 1)
    if len(head) != 2:
        raise AssertionError(f"{start!r} not found")
    tail = head[1].split(end, 1)
    if len(tail) != 2:
        raise AssertionError(f"{end!r} not found after {start!r}")
    return tail[0]


def cpp_slots() -> list:
    """Parse the SLOTS table out of button_config.cpp as (slot, voice) pairs."""
    table = section(CPP, "static const SlotInfo SLOTS[] = {", "};")
    rows = re.findall(r"\{\s*(\d+)\s*,\s*(true|false)\s*\}", table)
    if not rows:
        raise AssertionError("SLOTS table has no rows")
    return [(int(slot), voice == "true") for slot, voice in rows]


def page_slots() -> list:
    """Parse the S array out of button_config_page.h as one dict per input."""
    array = section(PAGE, "var S=[", "];")
    rows = re.findall(
        r'\{s:(\d+),l:"([^"]+)",v:([01]),g:"(\w+)"(?:,c:"(\w+)")?\}',
        array,
    )
    if not rows:
        raise AssertionError("page S array has no rows")
    return [
        {"slot": int(slot), "label": label, "voice": voice == "1", "group": group, "cell": cell}
        for slot, label, voice, group, cell in rows
    ]


def page_group(name: str) -> list:
    return [row for row in page_slots() if row["group"] == name]


class RoutingTest(unittest.TestCase):
    def test_the_component_claims_all_three_paths(self) -> None:
        for path in ("/buttons", "/buttons/api/state", "/buttons/api/action"):
            self.assertIn(f'"{path}"', CPP)

    def test_get_serves_the_page_and_state_and_post_serves_the_action(self) -> None:
        """Catches a method change that would hide an endpoint or open a new one."""
        handler = section(CPP, "bool ButtonConfig::canHandle", "void ButtonConfig::handleRequest")
        self.assertIn(
            'if (method == HTTP_GET)\n    return url == "/buttons" || url == "/buttons/api/state";',
            handler,
        )
        self.assertIn(
            'if (method == HTTP_POST)\n    return url == "/buttons/api/action";',
            handler,
        )
        self.assertIn("return false;", handler)
        for method in ("HTTP_PUT", "HTTP_DELETE", "HTTP_PATCH", "HTTP_ANY"):
            self.assertNotIn(method, handler)

    def test_an_accepted_action_answers_200_and_never_202(self) -> None:
        """web_server_idf in ESPHome 2026.7.4 maps only 200, 204, 400, 401, 404,
        409 and 422. Any other status leaves the device as a 500."""
        self.assertIn('request->send(200, "application/json", R"({"ok":true})");', CPP)
        self.assertNotIn("202", CPP)
        self.assertNotIn("202", PAGE)

    def test_a_bad_request_answers_400_and_a_busy_device_answers_409(self) -> None:
        self.assertIn('request->send(400, "application/json", R"({"ok":false,"error":"invalid slot"})");', CPP)
        self.assertIn('request->send(400, "application/json", R"({"ok":false,"error":"unknown action"})");', CPP)
        self.assertIn('request->send(400, "application/json", R"({"ok":false,"error":"missing action"})");', CPP)
        self.assertIn('request->send(409, "application/json", R"({"ok":false,"error":"busy"})");', CPP)
        self.assertIn("if (::ir_ui.state != IrUi::OFF) {", CPP)

    def test_the_page_reports_a_busy_device_from_the_409(self) -> None:
        self.assertIn("if(r.code===409)", PAGE)
        self.assertIn("if(r.code!==200)", PAGE)


class SlotTableTest(unittest.TestCase):
    def test_the_cpp_table_holds_slots_3_to_20_once_each(self) -> None:
        slots = [slot for slot, _ in cpp_slots()]
        self.assertEqual(sorted(slots), ALL_SLOTS)
        self.assertEqual(len(slots), len(set(slots)))

    def test_the_page_array_holds_slots_3_to_20_once_each(self) -> None:
        slots = [row["slot"] for row in page_slots()]
        self.assertEqual(sorted(slots), ALL_SLOTS)
        self.assertEqual(len(slots), len(set(slots)))

    def test_the_cpp_table_and_the_page_array_agree_on_voice(self) -> None:
        """Catches a capability that moves in one table and not the other."""
        firmware = {slot: voice for slot, voice in cpp_slots()}
        page = {row["slot"]: row["voice"] for row in page_slots()}
        self.assertEqual(firmware, page)

    def test_only_slots_17_and_18_and_19_have_no_voice_action(self) -> None:
        """17 and 18 are wheel detents with no release edge to end push-to-talk.
        19 is SW2, whose press edge belongs to the receiver-mode hold."""
        firmware = {slot for slot, voice in cpp_slots() if not voice}
        self.assertEqual(firmware, NO_VOICE)


class PlacementTest(unittest.TestCase):
    def test_the_top_group_puts_sw1_on_the_right(self) -> None:
        """SW1 sits to the right of SW2 on the board."""
        rows = page_group("top")
        self.assertEqual([(row["slot"], row["label"]) for row in rows], [(19, "SW2"), (20, "SW1")])

    def test_the_wheel_sits_in_the_correct_grid_cells(self) -> None:
        """Catches a swap that would put Left on the right of the plus layout, or
        put clockwise rotation on the left of Up."""
        rows = page_group("plus")
        self.assertEqual(
            {(row["slot"], row["label"], row["cell"]) for row in rows},
            {
                (18, "Turn left", "tl"),
                (13, "Up", "u"),
                (17, "Turn right", "tr"),
                (16, "Left", "l"),
                (14, "Press", "c"),
                (12, "Right", "r"),
                (15, "Down", "d"),
            },
        )

    def test_every_plus_cell_has_a_grid_area_rule(self) -> None:
        for cell, area in (
            ("tl", "1/1"),
            ("u", "1/2"),
            ("tr", "1/3"),
            ("l", "2/1"),
            ("c", "2/2"),
            ("r", "2/3"),
            ("d", "3/2"),
        ):
            self.assertIn(f".plus .{cell}{{grid-area:{area}}}", PAGE)

    def test_both_rotation_slots_live_in_the_wheel_group(self) -> None:
        self.assertEqual({row["slot"] for row in page_group("plus")} & {17, 18}, {17, 18})
        self.assertEqual(page_group("turn"), [])

    def test_the_keypad_group_fills_column_by_column(self) -> None:
        """The 3x3 grid fills in array order, so the array order is the layout.
        The board reads 3 6 11, 4 7 10, 5 8 9 across its rows."""
        rows = page_group("pad")
        self.assertEqual([row["slot"] for row in rows], [3, 6, 11, 4, 7, 10, 5, 8, 9])
        self.assertEqual([row["label"] for row in rows], [f"SW{n}" for n in (3, 6, 11, 4, 7, 10, 5, 8, 9)])

    def test_the_page_renders_the_three_groups_it_names(self) -> None:
        for group in ("top", "plus", "pad"):
            self.assertIn(f'id="{group}"', PAGE)


class EnforcementTest(unittest.TestCase):
    def test_the_firmware_rejects_voice_on_a_slot_without_it(self) -> None:
        """Catches a page-only capability check that a direct POST would pass."""
        self.assertIn('if (action == "set_voice" && !info->voice) {', CPP)
        self.assertIn('"error":"slot has no voice action"', CPP)
        self.assertIn("bool voice;", HEADER)

    def test_every_store_and_state_mutation_runs_on_a_defer(self) -> None:
        """HTTP handlers run on the httpd task. An NVS write from there races."""
        for call in ("ir_code_store.set_voice(", "ir_code_store.clear(", "ir_ui.open_from_web("):
            total = CPP.count(call)
            self.assertEqual(total, 1, call)
            deferred = re.findall(r"defer\(\[[^\]]*\]\(\)\s*\{[^}]*" + re.escape(call), CPP)
            self.assertEqual(len(deferred), total, call)

    def test_the_cancel_action_also_closes_on_the_main_loop(self) -> None:
        self.assertIn("this->defer([]() { ::ir_ui.close(); });", CPP)
        self.assertEqual(CPP.count("ir_ui.close("), 1)

    def test_the_state_endpoint_only_reads(self) -> None:
        state = section(CPP, "void ButtonConfig::handle_state_", "void ButtonConfig::handle_action_")
        for call in ("set_voice(", ".clear(", "open_from_web(", ".save(", "defer("):
            self.assertNotIn(call, state)

    def test_an_action_is_reserved_before_its_deferred_mutation(self) -> None:
        action = section(CPP, "void ButtonConfig::handle_action_", "void ButtonConfig::complete_action_")
        reserve = action.index("compare_exchange_strong")
        self.assertLess(reserve, action.index("ir_ui.open_from_web("))
        self.assertIn("action_pending_.load", CPP)
        self.assertIn("action_pending_.store(false", CPP)

    def test_preference_results_complete_the_deferred_action(self) -> None:
        self.assertIn("complete_action_(action_id, ::ir_code_store.set_voice(button))", CPP)
        self.assertIn("complete_action_(action_id, ::ir_code_store.clear(button))", CPP)
        self.assertIn('msg="Flash write failed. The assignment was not saved."', PAGE)
        self.assertIn("waitAction(r.body.id)", PAGE)


class StorageTest(unittest.TestCase):
    def test_the_slot_range_and_record_keys_are_unchanged(self) -> None:
        """Catches a key change that would hand each button its neighbour's code."""
        self.assertIn("FIRST_BUTTON = 3;", STORE)
        self.assertIn("LAST_BUTTON = 20;", STORE)
        self.assertIn("make_preference<Record>(0x49524330U + i, true)", STORE)
        self.assertIn("VOICE_KEY = 0x49524356U;", STORE)

    def test_the_save_counter_stays_in_memory(self) -> None:
        """The diagnostic capture counter must not cause another flash write."""
        self.assertIn("uint32_t saves_ = 0;", STORE)
        self.assertNotIn("saves_pref", STORE)
        self.assertNotIn("save(&saves_", STORE)
        for line in STORE.splitlines():
            if "make_preference" in line:
                self.assertNotIn("saves", line)
        self.assertEqual(STORE.count("make_preference"), 2)

    def test_assignment_writes_report_code_and_voice_failures(self) -> None:
        self.assertIn("bool erase_code_(uint8_t button)", STORE)
        self.assertIn("return erased && written;", STORE)
        self.assertIn("if (!voice_pref_.save(&next_mask))", STORE)


class PageTest(unittest.TestCase):
    def test_the_page_loads_nothing_from_outside_the_device(self) -> None:
        """The remote often sits on a LAN with no route to the internet."""
        for marker in ("http://", "https://", "<script src", "<link", "@import", "//cdn"):
            self.assertNotIn(marker, PAGE)

    def test_the_page_only_calls_its_own_endpoints(self) -> None:
        calls = re.findall(r'fetch\("([^"]+)"', PAGE)
        self.assertEqual(sorted(set(calls)), ["/buttons/api/action", "/buttons/api/state"])

    def test_capture_success_matches_the_recorded_slot(self) -> None:
        self.assertIn('j.result==="saved"&&j.result_slot===rec', PAGE)
        self.assertNotIn("st.saves>", PAGE)
        self.assertNotIn('j.op_state==="saved"', PAGE)

    def test_reload_reuses_the_persisted_capture_result(self) -> None:
        startup = section(PAGE, "build();", "</script>")
        self.assertIn('seen=j.result==="saved"&&j.result_slot===rec', startup)


class WiringTest(unittest.TestCase):
    def test_the_config_loads_the_local_component(self) -> None:
        block = section(CONFIG, "external_components:", "\nlogger:")
        self.assertIn("type: local", block)
        self.assertIn("path: components", block)
        self.assertRegex(CONFIG, r"\nbutton_config:")
        self.assertRegex(CONFIG, r"web_server:\n  port: 80")

    def test_the_interval_opens_the_rail_and_effect_for_a_web_request(self) -> None:
        """Rail and LED work needs YAML ids, so the web open lands on this tick."""
        block = section(CONFIG, "  - interval: 250ms", "  - interval: 1s")
        self.assertIn("if (ir_ui.take_open_request()) {", block)
        self.assertIn("id(ir_rail).turn_on();", block)
        self.assertIn('set_effect("IR Receiver")', block)

    def test_the_interval_restores_idle_status_on_any_close(self) -> None:
        block = section(CONFIG, "  - interval: 250ms", "  - interval: 1s")
        self.assertIn("if (ir_ui.tick())", block)
        self.assertIn("id(show_idle_status).execute();", block)

    def test_the_hold_script_leaves_the_idle_restore_to_the_interval(self) -> None:
        """Catches a double restore once tick() reports a close from any source."""
        block = section(CONFIG, "  - id: exit_receiver_hold", "  - id: show_idle_status")
        self.assertIn("ir_ui.close();", block)
        self.assertNotIn("show_idle_status", block)


class IrUiStateTest(unittest.TestCase):
    def test_close_drops_the_web_owner_and_raises_the_closed_flag(self) -> None:
        body = section(STORE, "  void close() {", "\n  }")
        self.assertIn("web_owner_ = false;", body)
        self.assertIn("closed_ = true;", body)
        self.assertIn("state = OFF;", body)

    def test_a_web_open_arms_the_slot_with_arm_only(self) -> None:
        """A web request names its slot, so it must not run the tap cycle."""
        body = section(STORE, "  void open_from_web(uint8_t button) {", "\n  }")
        self.assertIn("web_owner_ = true;", body)
        self.assertIn("open_requested_ = true;", body)
        self.assertIn("tap(button, Tap::ARM_ONLY);", body)

    def test_capture_result_survives_ready_and_close(self) -> None:
        captured = section(STORE, "  void captured(", "\n  }")
        close = section(STORE, "  void close() {", "\n  }")
        tick = section(STORE, "  bool tick() {", "\n  }")
        self.assertIn("web_result_ = state;", captured)
        self.assertIn("web_result_slot_ = target;", captured)
        self.assertNotIn("web_result_", close)
        self.assertNotIn("web_result_", tick)


class ComponentSchemaTest(unittest.TestCase):
    def test_the_component_binds_to_the_existing_web_server(self) -> None:
        self.assertIn('AUTO_LOAD = ["web_server_base"]', INIT)
        self.assertIn("CONF_WEB_SERVER_BASE_ID", INIT)
        self.assertIn("cv.use_id(web_server_base.WebServerBase)", INIT)


if __name__ == "__main__":
    unittest.main()
