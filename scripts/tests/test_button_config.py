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
ZIGBEE = (ROOT / "zigbee_learning.h").read_text()

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
    def test_the_component_claims_all_four_paths(self) -> None:
        for path in ("/buttons", "/buttons/api/state", "/buttons/api/code", "/buttons/api/action"):
            self.assertIn(f'"{path}"', CPP)

    def test_get_serves_the_page_and_state_and_post_serves_the_action(self) -> None:
        """Catches a method change that would hide an endpoint or open a new one."""
        handler = section(CPP, "bool ButtonConfig::canHandle", "void ButtonConfig::handleRequest")
        self.assertIn(
            'if (method == HTTP_GET)\n    return url == "/buttons" || url == "/buttons/api/state"'
            ' || url == "/buttons/api/code";',
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

    def test_the_firmware_accepts_a_zigbee_target_on_every_slot(self) -> None:
        """Zigbee playback rides the IR path, so the wheel detents accept it too."""
        self.assertIn('action == "set_zigbee"', CPP)
        self.assertIn('"error":"a group is 1 to 65527, in decimal or 0x hex"', CPP)
        action = section(CPP, "void ButtonConfig::handle_action_", "void ButtonConfig::complete_action_")
        self.assertNotIn('set_zigbee" && !info->', action)

    def test_every_store_and_state_mutation_runs_on_a_defer(self) -> None:
        """HTTP handlers run on the httpd task. An NVS write from there races."""
        for call in (
            "ir_code_store.set_voice(",
            "ir_code_store.clear(",
            "ir_ui.open_from_web(",
            "zigbee_assignments.assign_from_web(",
        ):
            total = CPP.count(call)
            self.assertEqual(total, 1, call)
            deferred = re.findall(r"defer\(\[[^\]]*\]\(\)\s*\{[^}]*" + re.escape(call), CPP)
            self.assertEqual(len(deferred), total, call)

    def test_the_cancel_action_also_closes_on_the_main_loop(self) -> None:
        self.assertIn("this->defer([]() { ::ir_ui.close(); });", CPP)
        self.assertEqual(CPP.count("ir_ui.close("), 1)

    def test_the_state_endpoint_only_reads(self) -> None:
        state = section(CPP, "void ButtonConfig::handle_state_", "void ButtonConfig::handle_code_")
        for call in (
            "set_voice(",
            ".clear(",
            "open_from_web(",
            ".save(",
            "defer(",
            "assign_from_web(",
        ):
            self.assertNotIn(call, state)
        self.assertIn("::zigbee_assignments.assignment(info.slot)", state)

    def test_the_state_row_reports_the_zigbee_target_first(self) -> None:
        """A slot holds one action, and a Zigbee target hides an old IR code."""
        state = section(CPP, "void ButtonConfig::handle_state_", "void ButtonConfig::handle_code_")
        self.assertRegex(
            state,
            r'zigbee\.assigned\s+\? "zigbee"[\s\S]*?is_voice\(info\.slot\)\s+\? "voice"'
            r'[\s\S]*?has_code\(info\.slot\) \? "ir"',
        )
        self.assertIn('"fields":"%s","group":%u,"ieee":"%s","ep":%u,"act":%u,"val":%d,"name":"', state)
        self.assertIn(
            "print_json_text(stream, zigbee.assigned ? zigbee.name.c_str() "
            ": ::ir_code_store.name(info.slot));",
            state,
        )

    def test_an_action_is_reserved_before_its_deferred_mutation(self) -> None:
        action = section(CPP, "void ButtonConfig::handle_action_", "void ButtonConfig::complete_action_")
        reserve = action.index("compare_exchange_strong")
        self.assertLess(reserve, action.index("ir_ui.open_from_web("))
        self.assertIn("action_pending_.load", CPP)
        self.assertIn("action_pending_.store(false", CPP)

    def test_preference_results_complete_the_deferred_action(self) -> None:
        self.assertIn("complete_action_(action_id, ::ir_code_store.set_voice(button))", CPP)
        self.assertIn("complete_action_(action_id, ::ir_code_store.clear(button))", CPP)
        self.assertIn('"Flash write failed. The assignment was not saved."', PAGE)
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
        self.assertEqual(STORE.count("make_preference"), 3)

    def test_assignment_writes_report_code_and_voice_failures(self) -> None:
        self.assertIn("bool erase_code_(uint8_t button)", STORE)
        self.assertIn("return erased && written;", STORE)
        self.assertIn("if (!voice_pref_.save(&next_mask))", STORE)


class ZigbeeTargetTest(unittest.TestCase):
    def test_the_manager_holds_no_mqtt_client_at_all(self) -> None:
        """The retained device inventory is larger than the C6 heap, and ESPHome
        buffers a whole MQTT payload into a std::string before it delivers the
        message. The browser reads the inventory over the Zigbee2MQTT frontend
        websocket instead, so the remote stores only the resolved group id."""
        for gone in ("mqtt", "subscribe(", "ArduinoJson", "JsonDocument", "base_topic_",
                     "bridge/", "allowed_targets_", "target_states_", "Operation",
                     "start_training", "cancel_training", "TargetKind"):
            self.assertNotIn(gone, ZIGBEE)

    def test_the_record_and_its_reader_use_one_lock(self) -> None:
        """The httpd task reads the record while the main loop writes it."""
        self.assertIn("mutable std::mutex cache_mutex_;", ZIGBEE)
        reader = section(ZIGBEE, "Assignment assignment(uint8_t slot) const {", "\n  }")
        self.assertIn("const std::lock_guard<std::mutex> lock(cache_mutex_);", reader)
        for writer in ("bool store_(uint8_t slot, const Entry &entry) {",
                       "void clear(uint8_t slot) {"):
            self.assertIn("const std::lock_guard<std::mutex> lock(cache_mutex_);",
                          section(ZIGBEE, writer, "\n  }"))

    def test_a_web_assignment_lands_in_flash_without_a_round_trip(self) -> None:
        """A group target needs no network confirmation, so the action result is
        known before assign_from_web returns and nothing has to stay open."""
        body = section(ZIGBEE, "bool assign_from_web(uint8_t slot, uint16_t group_id,", "\n  }")
        self.assertIn("if (!slot_valid_(slot) || group_id == 0 || group_id > MAX_GROUP_ID)", body)
        self.assertIn("if (!store_(slot, entry))", body)
        self.assertIn("preference_.save(&record_)",
                      section(ZIGBEE, "bool store_(uint8_t slot, const Entry &entry) {", "\n  }"))
        self.assertNotIn("deadline_", body)
        self.assertNotIn("web_result_callback_", ZIGBEE)

    def test_an_assignment_replaces_the_old_action_on_the_slot(self) -> None:
        """A slot holds one action, so a stale IR code must not survive."""
        body = section(ZIGBEE, "bool store_(uint8_t slot, const Entry &entry) {", "\n  }")
        self.assertIn("ir_code_store.clear_for_zigbee(slot)", body)
        # Both kinds of target commit through store_, so neither can skip it.
        for assign in ("bool assign_from_web(uint8_t slot, uint16_t group_id,",
                       "bool assign_device_from_web("):
            self.assertIn("store_(slot, entry)", section(ZIGBEE, assign, "\n  }"))
        # The name belongs to the erased code, so it goes with it.
        clear = section(STORE, "bool clear_for_zigbee(uint8_t button) {", "\n  }")
        self.assertIn('write_name_(button, "")', clear)
        # The reverse direction is the store's callback, set up in setup().
        self.assertIn("ir_code_store.set_assignment_clear_callback(", ZIGBEE)


class PageTest(unittest.TestCase):
    def test_the_page_loads_nothing_from_outside_the_device(self) -> None:
        """The remote often sits on a LAN with no route to the internet."""
        for marker in ("http://", "<script src", "<link", "@import", "//cdn", 'src="http'):
            self.assertNotIn(marker, PAGE)
        # One outbound anchor names the code library. A link loads nothing until
        # the reader follows it, so it cannot stall the page on an offline LAN.
        self.assertEqual(
            re.findall(r"https://[^\s\"'>]+", PAGE),
            ["https://github.com/Lucaslhm/Flipper-IRDB"],
        )

    def test_the_page_only_calls_its_own_endpoints(self) -> None:
        calls = re.findall(r'fetch\("([^"?]+)', PAGE)
        self.assertEqual(
            sorted(set(calls)),
            ["/buttons/api/action", "/buttons/api/code", "/buttons/api/state"],
        )

    def test_the_tile_shows_the_code_name(self) -> None:
        """A tile holds one line, and the name says more than the protocol does."""
        label = section(PAGE, "function words(s){", "return \"Clear\"}")
        self.assertIn('return "IR: "+codeName(r)', label)
        self.assertIn('function codeName(r){return r.name?r.name:"Slot"+r.slot}', PAGE)
        self.assertNotIn("Samsung32", label)
        # The code endpoint prints the same fallback into the name line.
        self.assertIn(R'stream->printf("name: Slot%u\\n"', CPP)

    def test_the_page_details_the_action_of_a_slot(self) -> None:
        """A pulse count alone does not say what the button sends. Only the rows
        that separate one code from another belong here, because the heading
        already names the action."""
        body = section(PAGE, "function detail(s){", 'return h+"</dl>"}')
        self.assertIn('if(!r||r.action!=="ir")return ""', body)
        self.assertIn('k.push(["Protocol","Samsung32"])', body)
        self.assertIn('k.push(["Address",r.fields.split(" ")[0]])', body)
        self.assertIn('k.push(["Command",r.fields.split(" ")[1]])', body)
        self.assertIn('k.push(["Protocol","Raw capture"])', body)
        self.assertIn('k.push(["Pulses",String(r.pulses)])', body)
        self.assertIn('if(r.us)k.push(["Frame",ms(r.us)])', body)
        # A constant row says nothing. Every frame goes out at 38 kHz.
        self.assertNotIn("Carrier", body)
        self.assertNotIn('"Type"', body)
        self.assertIn('function ms(u){return (u/1000).toFixed(1)+" ms"}', PAGE)
        self.assertIn('esc(words(sel))+"</p>"+detail(sel)', PAGE)

    def test_the_state_row_reports_the_frame_length_and_the_code(self) -> None:
        """Nine slots hold 68 pulses of the same length, so only the data word
        separates them."""
        state = section(CPP, "void ButtonConfig::handle_state_", "\n}")
        self.assertIn(
            '"pulses":%u,"us":%u,"code":"%s","fields":"%s","group":%u,"ieee":"%s","ep":%u,"act":%u,"val":%d,"name":"',
            state,
        )
        self.assertIn("::ir_code_store.name(info.slot)", state)
        self.assertIn("::ir_code_store.code_duration_us(info.slot)", state)
        self.assertIn("::ir_code_store.code_samsung_data(info.slot, samsung)", state)
        self.assertIn("::ir_code_store.code_samsung_fields(info.slot, address, command)", state)
        self.assertIn(R'std::snprintf(code, sizeof(code), "0x%08X"', state)
        self.assertIn(R'std::snprintf(fields, sizeof(fields), "%02X %02X"', state)
        length = section(STORE, "uint32_t code_duration_us(uint8_t button) const {", "\n  }")
        self.assertIn("* 10U", length)
        decode = section(STORE, "bool code_samsung_data(uint8_t button, uint32_t &data) const {", "\n  }")
        self.assertIn("if (record.count != 68)", decode)
        self.assertIn("const int16_t space = record.pulses[3 + 2 * bit];", decode)
        self.assertIn("value = (value << 1) | (-space > 100 ? 1U : 0U);", decode)

    def test_the_page_can_copy_a_code_out_and_paste_one_in(self) -> None:
        """Plain HTTP is not a secure context, so navigator.clipboard is often
        missing and execCommand has to carry the copy."""
        box = section(PAGE, "function codeBox(lock){", 'return h}')
        self.assertIn("<textarea id=ct", box)
        # The box carries the only copy of a code, so it never hides behind a toggle.
        self.assertNotIn("<details", PAGE)
        self.assertIn('function hasCode(text){return !!String(text||"").replace(/\\s+/g,"")}', PAGE)
        self.assertIn('var dis=lock?" disabled":"",codeDis=dis||(!hasCode(cd)?" disabled":"");', box)
        self.assertIn('id=cc"+codeDis+">Copy</button>', box)
        self.assertIn('id=ca"+codeDis+">Apply to this input</button>', box)
        # Loading follows the code actions, so it cannot move them.
        self.assertIn(".code .load{color:var(--mut);font-size:13px;margin:8px 0 0}", PAGE)
        self.assertIn('"<button type=button id=ca"+codeDis+">Apply to this input</button></div>"+', box)
        self.assertIn('"<p class=load>Loading the stored code.</p>"', box)
        self.assertIn('var disabled=lock||!hasCode(cd);', PAGE)
        # One helper carries both boxes, so the code box and the config box
        # cannot drift apart on the browsers that lack navigator.clipboard.
        copy = section(PAGE, "function copyBox(t){", "return ok}")
        self.assertIn('document.execCommand("copy")', copy)
        self.assertIn("if(!ok&&navigator.clipboard)", copy)
        self.assertIn("var ok=copyBox(t);", section(PAGE, "function copyCode(){", "bad=!ok;paint()}"))
        self.assertIn('go("set_ir_code",text)', PAGE)
        self.assertIn('fetch("/buttons/api/code?slot="+s', PAGE)
        self.assertIn('cd=j.text||""', PAGE)
        # The block is line based, so the newlines have to survive the encode.
        self.assertIn('"&code=")+encodeURIComponent(v)', PAGE)
        self.assertNotIn(R'c.replace(/[^0-9+\-]+/g,",")', PAGE)

    def test_the_code_endpoint_prints_a_flipper_signal_block(self) -> None:
        """The .ir syntax moves a code between this board, a Flipper, and the
        Flipper-IRDB files without a converter."""
        body = section(CPP, "void ButtonConfig::handle_code_", "\n}")
        self.assertIn("::ir_code_store.code_timings(info->slot, raw)", body)
        self.assertIn(R'"present":%s,"text":"', body)
        self.assertIn(R'stream->printf("name: %s\\n", name)', body)
        self.assertIn(R'stream->print("type: parsed\\nprotocol: Samsung32\\n")', body)
        self.assertIn(R'"address: %02X 00 00 00\\ncommand: %02X 00 00 00"', body)
        self.assertIn(R'"type: raw\\nfrequency: 38000\\nduty_cycle: 0.500000\\ndata:"', body)
        self.assertIn("::ir_code_store.code_samsung_fields(info->slot, address, command)", body)
        self.assertIn('url == "/buttons/api/code"', CPP)
        self.assertIn("void handle_code_(AsyncWebServerRequest *request);", HEADER)
        # code_timings() exists because load() logs the whole frame.
        reader = section(STORE, "bool code_timings(uint8_t button, std::vector<int32_t> &raw) const {", "\n  }")
        self.assertIn("* 10)", reader)

    def test_a_pasted_code_is_validated_before_the_flash_write(self) -> None:
        """A truncated paste would otherwise reach the store as a valid frame."""
        parser = section(CPP, "static bool parse_timings", "\n}")
        self.assertIn("value < -327670 || value > 327670", parser)
        self.assertIn("raw.size() >= IrCodeStore::MAX_PULSES", parser)
        self.assertIn("if ((raw.size() % 2 == 0) != (value > 0))", parser)
        self.assertIn("return raw.size() >= 4 && raw.size() % 2 == 0;", parser)
        action = section(CPP, "void ButtonConfig::handle_action_", "\n}")
        self.assertIn('action == "set_ir_code"', action)
        self.assertIn('!parse_ir_text(request->arg("code"), name, timings)', action)
        self.assertIn("::ir_code_store.save(button, timings)", action)
        self.assertIn("::ir_code_store.set_name(button, name.c_str())", action)

    def test_a_pasted_flipper_block_is_read_a_line_at_a_time(self) -> None:
        """A Flipper-IRDB file holds many signals, and only the first one lands."""
        parser = section(CPP, "static bool parse_ir_text", "\n}")
        self.assertIn('lower_equals(key, "filetype") || lower_equals(key, "version")', parser)
        self.assertIn("if (named)\n        break;", parser)
        self.assertIn('lower_equals(type, "parsed")', parser)
        self.assertIn('!lower_equals(protocol, "samsung32") || !have_address || !have_command', parser)
        self.assertIn("IrCodeStore::samsung_timings(address, command, raw)", parser)
        self.assertIn('lower_equals(type, "raw")', parser)
        self.assertIn("return parse_raw_data(data, raw);", parser)
        # A code copied out of an older build is a bare list of signed values.
        self.assertIn("if (!keyed)\n    return parse_timings(text, raw);", parser)
        raw = section(CPP, "static bool parse_raw_data", "\n}")
        self.assertIn("if (value < 1 || value > 327670)", raw)
        self.assertIn("raw.size() % 2 == 0 ? static_cast<int32_t>(value) : -static_cast<int32_t>(value)", raw)
        # A Flipper raw frame ends on a mark, so its value count is odd.
        self.assertIn("return raw.size() >= 4;", raw)
        byte = section(CPP, "static bool parse_leading_byte", "\n}")
        self.assertIn('field.substr(0, 2).c_str(), &end, 16', byte)
        # The default 1024 byte cap truncates a long frame.
        self.assertRegex(CONFIG, r'CONFIG_HTTPD_MAX_REQ_HDR_LEN: "8192"')
    def test_one_selector_carries_the_four_actions(self) -> None:
        """A slot holds one action, so the panel shows one action at a time and
        the IR code box cannot sit under a Zigbee assignment."""
        editor = section(PAGE, "function editor(){", "\nfunction actFor(")
        self.assertIn('var opts=[["ir","IR code"],["zb","Zigbee target"]];', editor)
        self.assertIn('if(d.v)opts.push(["va","Voice assistant"]);', editor)
        self.assertIn('opts.push(["cl","Clear"]);', editor)
        # Zigbee is offered everywhere, so it must sit outside the d.v branch.
        self.assertLess(editor.index('"Zigbee target"'), editor.index("if(d.v)opts.push"))
        # A slot that lost its voice action must not stay on a voice panel.
        self.assertIn('if(!d.v&&act==="va")act="ir";', editor)
        # The panel below the selector repeats the selected action as a heading,
        # so the fields under it are never read out of context.
        self.assertIn('if(act===opts[i][0])title=opts[i][1]}', editor)
        self.assertIn('h+="</select><h2>"+esc(title)+"</h2>";', editor)
        self.assertIn('document.getElementById("as").onchange=', editor)
        # Record IR and the code box belong to the IR panel alone.
        ir = section(PAGE, "function irPanel(lock){", "\n\nfunction ")
        self.assertIn('id=b1', ir)
        self.assertIn("codeBox(lock)", ir)
        self.assertNotIn("codeBox(", editor)

    def test_the_kind_selector_shows_one_target_at_a_time(self) -> None:
        """Holding a group ID and an IEEE address on screen at once let the panel
        describe two targets, which Assign then had to choose between. The kind
        selector removes the choice instead of resolving it."""
        form = section(PAGE, "function zbForm(lock){", "\nreturn h}")
        self.assertIn("<label class=hd2 for=zn>Target kind</label>", form)
        device = form.split('if(zkv==="d"){', 1)[1].split("\nelse{", 1)[0]
        group = form.split("\nelse{", 1)[1]
        # Each branch renders its own picker and its own fields, and no others.
        self.assertIn("<label class=hd2 for=zh>IEEE address</label>", device)
        self.assertIn("<label class=hd2 for=zp>Endpoint</label>", device)
        self.assertIn("<select id=zd", device)
        self.assertNotIn("id=zg", device)
        self.assertNotIn("id=zs", device)
        self.assertIn("<label class=hd2 for=zg>Group ID</label>", group)
        self.assertIn("<select id=zs", group)
        self.assertNotIn("id=zh", group)
        self.assertNotIn("id=zp", group)
        # A label must render like the other headings and take its own line.
        self.assertIn("p.hd2,label.hd2{display:block;", PAGE)
        # One box per kind, so nothing has to guess from the digit count.
        self.assertNotIn("ztv", PAGE)

    def test_switching_kind_drops_the_other_kind_of_target(self) -> None:
        """A hidden field must not still be assignable, and a slot that holds a
        device should open on the device fields rather than on an empty group."""
        wiring = section(PAGE, 'if(act==="zb"){', '\nif(act==="va"')
        self.assertIn('document.getElementById("zn").onchange=function(){zkv=this.value;\n'
                      'zsv="";zdv="";zgv="";zhv="";zpv="";', wiring)
        self.assertIn('var pr=row(s);zkv=(pr&&pr.action==="zigbee"&&pr.ieee)?"d":"g";', PAGE)

    def test_the_open_panel_follows_the_stored_action(self) -> None:
        """Opening a slot on its own action saves a hunt through the selector."""
        body = section(PAGE, "function actFor(s){", "\n\nfunction pick(")
        self.assertIn('if(r.action==="zigbee")return "zb";', body)
        self.assertIn('if(r.action==="voice")return "va";', body)
        self.assertIn('if(!r||r.action==="none")return "ir";', body)
        self.assertIn("act=actFor(s);", PAGE)

    def test_only_an_ir_assignment_loads_stored_code_on_selection(self) -> None:
        """An empty slot has no IR code, so its ready code box must not show a
        loading state while the endpoint returns an empty response."""
        pick = section(PAGE, "function pick(s){", "\n\nfunction load()")
        self.assertIn('if(!pr||pr.action!=="ir")cdSlot=s;', pick)
        self.assertIn('if(pr&&pr.action==="ir"&&cdSlot!==s)loadCode(s)', pick)

    def test_the_zigbee_fields_survive_a_repaint(self) -> None:
        """A late bridge/devices message repaints the panel, and a half typed
        group ID must not vanish with it."""
        self.assertIn("var act=", PAGE)
        self.assertIn("zgv=gi.value", PAGE)
        self.assertIn("zhv=hi.value", PAGE)
        self.assertIn("zpv=pi.value", PAGE)
        self.assertIn("zsv=this.value", PAGE)
        self.assertIn("zdv=this.value", PAGE)
        # The panel is rebuilt from these vars, so each field re-renders its value.
        for field in ("value='\"+att(zgv)+\"'", "value='\"+att(zhv)+\"'",
                      "value='\"+att(zpv)+\"'"):
            self.assertIn(field, PAGE)
        # None of it may follow the selection to the next slot.
        self.assertIn('act=actFor(s);zsv="";zdv="";zgv="";zhv="";zpv="";', PAGE)
        self.assertIn("(zsv===String(tg[i].id)?\" selected\":\"\")", PAGE)
        self.assertIn("(zdv===td[i].ieee?\" selected\":\"\")", PAGE)

    def test_the_page_offers_a_zigbee_target_picker_on_every_slot(self) -> None:
        self.assertIn("<select id=zs", PAGE)
        self.assertIn("<select id=zd", PAGE)
        self.assertIn("<input id=zg type=text", PAGE)
        self.assertIn("<input id=zh type=text", PAGE)
        self.assertIn("<input id=zp type=text", PAGE)
        self.assertIn("<select id=zt", PAGE)
        self.assertIn('post("set_zigbee",s,v,name,', PAGE)

    def test_one_button_assigns_whatever_the_target_box_holds(self) -> None:
        """The page once had three assign buttons and claimed a typed ID won over
        the pickers, which nothing implemented. A picker now fills the box and
        one button sends it, so there is no second route to disagree."""
        self.assertNotIn("wins over", PAGE)
        for gone in ('id=za', 'id=zw', 'assignGroup', 'assignDevice', 'assignTyped',
                     'Assign group', 'Assign device', 'Assign typed'):
            self.assertNotIn(gone, PAGE)
        wiring = section(PAGE, 'if(act==="zb"){', '\nif(act==="va"')
        self.assertIn('document.getElementById("zi").onclick=assignTarget', wiring)
        # A picker only fills the fields of the kind already on screen.
        self.assertIn('if(gs)gs.onchange=function(){zsv=this.value;if(zsv)zgv=zsv;paint()};',
                      wiring)
        self.assertIn('if(zdv){zhv=zdv;zpv=String(deviceEp(zdv,zav))}', wiring)

    def test_the_one_button_reaches_a_device_and_a_group(self) -> None:
        """Neither picker renders without the bridge lists, so the box is the only
        disconnected route and it has to carry both kinds of target."""
        body = section(PAGE, "function assignTarget(){", "\nfunction ")
        self.assertIn("sendDevice(ieee,ep||\"1\",name,val)", body)
        self.assertIn("sendGroup(g,name,val)", body)
        # The kind selector already decided, so nothing reads the digit count.
        self.assertIn('if(zkv==="d"){', body)
        # A malformed address is caught here rather than by the remote.
        self.assertIn("if(!/^[0-9a-fA-F]{16}$/.test(hex)){", body)
        # 0x1201 and 4609 are the same group, so the name lookup reads the value.
        self.assertIn('parseInt(g,g.slice(0,2).toLowerCase()==="0x"?16:10)', body)
        # The name is re-derived, so an edited box cannot keep the old label.
        self.assertIn('var name="",i,val=actionValue();', body)

    def test_a_device_target_is_assigned_without_writing_to_the_bridge(self) -> None:
        """The remote unicasts to the device now, so the page sends the IEEE
        address and the endpoint and creates no group. A group per device left
        one behind on every repeat assign."""
        body = section(PAGE, "function sendDevice(ieee,ep,name,val){", "\n\nfunction sendGroup(")
        self.assertIn('post("set_zigbee_device",s,null,name,', body)
        self.assertIn('"&ieee="+encodeURIComponent(ieee)', body)
        self.assertIn('"&ep="+encodeURIComponent(ep)', body)

    def test_the_page_writes_nothing_to_zigbee2mqtt(self) -> None:
        """The websocket is read only now. Nothing is published, so the request
        transaction, its response topic and its timeout are all gone."""
        for gone in ("zpub", "zreq", "bridge/request/", "bridge/response/", "transaction"):
            self.assertNotIn(gone, PAGE)
        self.assertNotIn("ws.send(", PAGE)

    def test_a_device_target_carries_the_endpoint_of_its_action(self) -> None:
        """A groupcast needs no endpoint but a unicast does, and the endpoint that
        answers depends on the action. A thermostat cluster and an On/Off cluster
        on one device do not have to share an endpoint."""
        body = section(PAGE, "function epForCluster(eps,cluster){", "\n\nfunction ")
        self.assertIn("if(eps[k].indexOf(cluster)<0)continue;", body)
        self.assertIn("if(!best||n<best)best=n", body)
        pick = section(PAGE, "function deviceEp(ieee,action){", "\n\n")
        self.assertIn('epForCluster(td[i].eps,A?A.c:"genOnOff")||1', pick)
        # An older bridge publishes no endpoint list, so the picker still works.
        self.assertIn("return 1}", pick)
        # A device that answers none of the actions is dropped from the picker.
        self.assertIn("if(eps&&!commandable(eps))continue;", PAGE)

    def test_the_action_list_follows_the_clusters_of_the_target(self) -> None:
        """Zigbee2MQTT publishes the cluster list of every device, so the page can
        offer only the commands the target accepts. A group accepts what every
        member accepts, and a typed address describes nothing, so it offers all."""
        catalogue = section(PAGE, "var ZA=[", "];")
        for cluster in ("genOnOff", "genLevelCtrl", "lightingColorCtrl", "genScenes",
                        "closuresWindowCovering", "hvacThermostat", "closuresDoorLock",
                        "ssIasWd"):
            self.assertIn(f'c:"{cluster}"', catalogue)
        offer = section(PAGE, "function zActions(){", "\n\n")
        self.assertIn("if(!have)return ZA.slice(0);", offer)
        self.assertIn("if(have[ZA[i].c])out.push(ZA[i]);", offer)
        # A group only accepts what every member accepts.
        group = section(PAGE, "function grpClusters(g){", "\n\nfunction ")
        self.assertIn("if(Object.prototype.hasOwnProperty.call(have,j))keep[j]=true;", group)
        # An action the target dropped cannot stay selected, or Assign sends it.
        form = section(PAGE, "function actionForm(dis){", "\n\n")
        self.assertIn('if(!found){zav=list[0].a;zvv=""}', form)

    def test_the_browser_reads_the_group_list_from_zigbee2mqtt(self) -> None:
        """The remote holds no MQTT client, so the picker is filled by this
        browser over the Zigbee2MQTT frontend websocket. A websocket needs no
        CORS grant, which a fetch to the same host would."""
        self.assertIn("new WebSocket(full)", PAGE)
        self.assertIn('m.topic==="bridge/groups"&&Array.isArray(m.payload)', PAGE)
        self.assertIn('m.topic==="bridge/devices"&&Array.isArray(m.payload)', PAGE)
        # The frontend relays MQTT with the base topic already stripped.
        self.assertNotIn("zigbee2mqtt/", PAGE)
        self.assertIn('g.id<1||g.id>65527', PAGE)
        # The coordinator cannot be a toggle target.
        self.assertIn('d.type==="Coordinator"', PAGE)

    def test_the_broker_address_and_token_stay_in_the_browser(self) -> None:
        """They are this browser's credentials, so they must not reach the flash
        of a remote that has no use for them."""
        self.assertIn('localStorage.setItem("c6.z2m.url",u)', PAGE)
        self.assertIn('localStorage.setItem("c6.z2m.token",k)', PAGE)
        self.assertNotIn("token", section(PAGE, "function post(", "\nfunction fail("))
        # A private window throws on the accessor itself.
        save = section(PAGE, "function z2mSave(){", "\n\nfunction ")
        self.assertIn("try{localStorage.setItem", save)

    def test_the_page_explains_that_membership_lives_in_the_light(self) -> None:
        """A group id alone does nothing until the light joins the group, and
        only Zigbee2MQTT can write that."""
        self.assertIn("Membership lives in the", PAGE)
        self.assertIn("light, so a group only works once the light has joined it.", PAGE)

    def test_the_page_reports_a_zigbee_assignment_and_its_target_name(self) -> None:
        """An unnamed group still has to say which group it is."""
        self.assertIn(
            'return "Zigbee "+(A?A.n:"action "+r.act)+": "+\n'
            '(r.name?r.name:(r.ieee?r.ieee:"group "+r.group))',
            PAGE,
        )

    def test_the_selected_input_title_copies_and_pastes_ir_and_zigbee_configs(self) -> None:
        """Paste opens the matching editor and fills it. Apply or Assign writes
        the copied config to the selected input."""
        self.assertIn(".edtitle .clip{display:flex", PAGE)
        editor = section(PAGE, "function editor(){", "\n\nfunction actFor(")
        self.assertIn('<h2 class=edtitle><span>', editor)
        self.assertIn('id=bcopy', editor)
        self.assertIn('id=bpaste', editor)
        self.assertIn('document.getElementById("bcopy").onclick=copyAssignment', editor)
        self.assertIn('document.getElementById("bpaste").onclick=pasteAssignment', editor)
        self.assertIn('!clip||locked', editor)
        self.assertNotIn('clip.source===sel', editor)
        clip = section(PAGE, "function clipConfig(r){", "\n\nfunction clipName(")
        self.assertIn('if(r.action==="ir")return {kind:"ir",source:r.slot}', clip)
        self.assertIn('if(r.action!=="zigbee")return null;', clip)
        copy = section(PAGE, "function copyAssignment(){", "\n\nfunction pasteAssignment(")
        self.assertIn('fetch("/buttons/api/code?slot="+source', copy)
        self.assertIn('if(j.slot!==source||!j.present||!j.text)throw new Error();', copy)
        self.assertIn('clip=c;', copy)
        paste = section(PAGE, "function pasteAssignment(){", "\n\nfunction applyCode(")
        self.assertIn('if(c.kind==="ir"){act="ir";codeLoad++;cd=c.code;cdSlot=target}', paste)
        self.assertIn('act="zb";zkv=c.device?"d":"g";', paste)
        self.assertIn('zsv=c.device?"":String(c.group);zdv=c.device?c.ieee:"";', paste)
        self.assertIn('zpv=c.device?String(c.ep||1):"";zav=Number(c.act)||0;', paste)
        self.assertIn('zvv=za(zav)&&za(zav).p?String(c.val):""}', paste)
        self.assertIn('Select "+(c.kind==="ir"?"Apply to this input":"Assign")+" to save it."', paste)
        self.assertNotIn('post("set_', paste)
        self.assertNotIn('waitAction(', paste)
        load = section(PAGE, "function loadCode(s){", "\n\n// The page")
        self.assertIn("var loadId=++codeLoad", load)
        self.assertIn("if(loadId!==codeLoad||j.slot!==s)return;", load)

    def test_the_page_carries_one_import_and_export_card(self) -> None:
        """The whole assignment set moves as one block of text, so a remote can
        be restored without a source remote in hand."""
        # The Zigbee2MQTT block and the import block share the card, so the
        # markup is static and only the block below the rule is rebuilt.
        self.assertIn('<section class="card full" id="cfg">', PAGE)
        self.assertIn('<div id="cfgb" hidden><div id="z2m"></div>'
                      '<div class="sep" id="cfgio"></div></div>', PAGE)
        self.assertIn(".sep{margin-top:16px;border-top:1px solid var(--line)", PAGE)
        self.assertNotIn('id="z2m"></section>', PAGE)
        card = section(PAGE, "function cfgPaint(){", "\n\nfunction editor(){")
        # Closed on arrival, because an export reads the code of every IR input.
        self.assertIn("var cfgOpen=false;", PAGE)
        # The heading is the toggle, so a closed card is one row and no separate
        # control competes with it.
        self.assertIn('<h2><button type="button" class="tog" id="cxo" aria-expanded="false">'
                      'Config<span\nid="cxz"></span><span id="cxs">Show</span></button></h2>', PAGE)
        # A collapsed card still reports the Zigbee2MQTT link, so the heading
        # carries the same dot as the status line inside it.
        title = section(PAGE, "function z2mTitle(){", "\n\n")
        self.assertIn('if(z2mUp()){e.innerHTML="<span class=dot></span>Zigbee2MQTT: "+z2mCounts()', title)
        self.assertIn('e.innerHTML="<span class=\'dot "+(zerr?"bad":"off")+"\'></span>', title)
        self.assertIn('(zerr?"unreachable":"not connected")}', title)
        self.assertIn("z2mStatus(){\nz2mTitle();", PAGE)
        self.assertIn(".dot.off{background:var(--line)}.dot.bad{background:var(--bad)}", PAGE)
        self.assertIn("h2>button.tog span#cxz{color:var(--mut)", PAGE)
        # One counts helper, so the heading and the line cannot disagree.
        self.assertIn('e.innerHTML="<span class=dot></span>Connected. "+z2mCounts()+"."}', PAGE)
        self.assertIn('if(s)s.textContent=cfgOpen?"Hide":"Show";', card)
        self.assertIn("b.hidden=!cfgOpen;", card)
        self.assertIn('o.onclick=cfgToggle}', card)
        self.assertIn("h2>button.tog{", PAGE)
        # The connection inputs are built once, so the repaint owns cfgio alone.
        self.assertIn('var e=document.getElementById("cfgio")', card)
        toggle = section(PAGE, "function cfgToggle(){", "\n\n")
        self.assertIn("cfgOpen=!cfgOpen", toggle)
        self.assertIn('if(cfgOpen&&cfgMode==="ex")cfgRefresh()}', toggle)
        # The startup path reads the state and the open code box, nothing more.
        start = section(PAGE, "load().then(function(j){", "document.getElementById(\"ed\")")
        self.assertNotIn("cfgRefresh", start)
        self.assertIn('<option value=ex', card)
        self.assertIn('<option value=im', card)
        self.assertIn('<textarea id=cx', card)
        self.assertIn('<p class=hd>Import and export</p>', card)
        # The export box is read only, because the remote is the source of it.
        self.assertIn('(cfgMode==="ex"?" readonly":"")', card)
        self.assertIn('id=cxc>Copy</button>', card)
        self.assertIn('id=cxd"+rd+">Download JSON</button>', card)
        self.assertIn('id=cxr"+rd+">Read Current Config</button>', card)
        self.assertIn("id=cxf type=file accept='.json,application/json'", card)
        self.assertIn('id=cxa"+wr+">Apply to the remote</button>', card)
        # The two directions keep separate text, so a repaint cannot drop a
        # paste and cannot show an export beside it.
        self.assertIn('esc(cfgMode==="ex"?cfgOut:cfgIn)', card)
        self.assertIn("box.oninput=function(){cfgIn=box.value}", card)
        self.assertIn('document.getElementById("cxd").onclick=cfgDownload', card)
        self.assertIn('document.getElementById("cxf").onchange=cfgLoadFile', card)
        # An import writes flash, so it stays disabled while the remote is busy.
        self.assertIn('wr=(cfgBusy||(st&&st.busy))?" disabled":""', card)
        self.assertIn("editor();cfgPaint()}", PAGE)

    def test_the_config_card_can_download_and_load_a_local_json_file(self) -> None:
        download = section(PAGE, "function cfgDownload(){", "\n\nfunction cfgJsonFile")
        self.assertIn('new Blob([cfgOut],{type:"application/json"})', download)
        self.assertIn('a.download="c6remote-config.json"', download)
        self.assertIn("URL.createObjectURL", download)
        self.assertIn("URL.revokeObjectURL", download)
        load = section(PAGE, "function cfgLoadFile(){", "\n\n// The box")
        self.assertIn('document.getElementById("cxf")', load)
        self.assertIn("cfgJsonFile(file)", load)
        self.assertIn("file.size>262144", load)
        self.assertIn("new FileReader()", load)
        self.assertIn("cfgParse(text)", load)
        self.assertIn('cfgMsg="Loaded "+name+"."', load)

    def test_an_export_holds_the_action_and_the_payload_of_every_input(self) -> None:
        """An export that named the action alone would restore nothing, because
        the group ID, the address, and the code are the assignment."""
        blob = section(PAGE, "function cfgBlob(){", "\n\n")
        self.assertIn("""return '{"c6remote":1,"slots":[""", blob)
        # One line for each input, so an entry stays readable in the box.
        self.assertIn(R'lines.join(",\n")', blob)
        self.assertIn("for(i=0;i<S.length;i++){", blob)
        self.assertIn('e={slot:s,label:S[i].l,action:"none"}', blob)
        self.assertIn('e.kind="device";e.ieee=r.ieee;e.ep=r.ep||1', blob)
        self.assertIn('e.kind="group";e.group=r.group', blob)
        self.assertIn('e.action="ir";e.code=cfgAll[s]||""', blob)
        # The codes come from the endpoint that already serves the editor box,
        # one request at a time, and the editor read fills the same cache.
        self.assertIn('cfgAll[s]=cd;cdSlot=s', PAGE)
        refresh = section(PAGE, "function cfgRefresh(){", "\n\n")
        self.assertIn('fetch("/buttons/api/code?slot="+slot', refresh)
        self.assertIn("return need.reduce(function(p,slot){", refresh)

    def test_an_import_is_read_in_full_before_the_first_flash_write(self) -> None:
        """A refusal in the middle would leave half of the inputs on the old
        config, so every entry is checked before any of them is sent."""
        check = section(PAGE, "function cfgCheck(e){", '\nreturn ""}')
        self.assertIn('return "A slot number is missing or unknown."', check)
        self.assertIn('if(a==="voice"&&!info(e.slot).v)', check)
        self.assertIn('/^[0-9a-fA-F]{16}$/.test(cfgHex(e.ieee))', check)
        self.assertIn("if(!(ep>=1&&ep<=240))", check)
        self.assertIn("if(!(g>=1&&g<=65527))", check)
        apply_ = section(PAGE, "function cfgApply(){", "\n\nfunction cfgCopy")
        self.assertIn("var parsed=cfgParse(cfgIn),j,i,list=[];", apply_)
        self.assertIn("if(parsed.error){cfgNote(parsed.error,true);return}", apply_)
        self.assertLess(apply_.index("cfgParse"), apply_.index("cfgRun("))
        parse = section(PAGE, "function cfgParse(text){", "\n\n// An action")
        self.assertIn("why=cfgCheck(j.slots[i]);", parse)
        self.assertIn('j.c6remote!==1', parse)
        # A clear on an input that holds nothing is the one skipped write.
        self.assertIn("for(i=0;i<j.slots.length;i++)if(cfgNeeded(j.slots[i]))list.push(j.slots[i]);", apply_)
        needed = section(PAGE, "function cfgNeeded(e){", "\n\n")
        self.assertIn('if(e.action!=="none")return true', needed)

    def test_an_import_reuses_the_action_endpoint_one_input_at_a_time(self) -> None:
        """The remote reserves one action at a time, so a burst would take the
        409. Nothing new is added to the firmware for an import."""
        send = section(PAGE, "function cfgSend(e){", '\nreturn post("clear",e.slot)}')
        self.assertIn('return post("set_voice",e.slot)', send)
        self.assertIn('return post("set_ir_code",e.slot,e.code)', send)
        self.assertIn('return post("set_zigbee_device",e.slot,null,e.name||""', send)
        self.assertIn('return post("set_zigbee",e.slot,String(parseInt(e.group,10))', send)
        run = section(PAGE, "function cfgRun(list,i){", "return cfgRun(list,i+1)})}")
        self.assertIn("return waitAction(r.body.id)", run)
        self.assertIn('throw new Error("Slot "+list[i].slot+": "+fail(r))', run)
        # The import adds no endpoint, so canHandle still claims four paths.
        self.assertNotIn("/buttons/api/export", PAGE)
        self.assertNotIn("/buttons/api/import", PAGE)
        self.assertNotIn("api/export", CPP)
        self.assertNotIn("api/import", CPP)

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
        # Assignment mode shares the one effect, so a web open selects it too.
        self.assertIn('set_brightness(0.5f).set_effect("Status Indicators")', block)

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
