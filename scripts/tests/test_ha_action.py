"""Regression checks for the Home Assistant action assignment kind."""

from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).parents[2]
COMPONENT = ROOT / "components" / "ha_action"
CPP = (COMPONENT / "ha_action.cpp").read_text()
HEADER = (COMPONENT / "ha_action.h").read_text()
INIT = (COMPONENT / "__init__.py").read_text()
CONFIG = (ROOT / "c6remote.yaml").read_text()
STORE = (ROOT / "ir_learning.h").read_text()
ZIGBEE = (ROOT / "zigbee_learning.h").read_text()
BLE = (ROOT / "components" / "ble_hid" / "ble_hid.cpp").read_text()
BUTTON_CPP = (ROOT / "components" / "button_config" / "button_config.cpp").read_text()
BUTTON_HEADER = (ROOT / "components" / "button_config" / "button_config.h").read_text()
BUTTON_INIT = (ROOT / "components" / "button_config" / "__init__.py").read_text()
IDLE_CPP = (ROOT / "components" / "idle_sleep" / "idle_sleep.cpp").read_text()
IDLE_INIT = (ROOT / "components" / "idle_sleep" / "__init__.py").read_text()
BENCH = (ROOT / "c6remote-test-sleep.yaml").read_text()

KINDS = {
    "light": ["toggle", "turn_on", "turn_off", "brightness_up", "brightness_down"],
    "switch": ["toggle", "turn_on", "turn_off"],
    "input_boolean": ["toggle", "turn_on", "turn_off"],
    "fan": ["toggle", "turn_on", "turn_off", "increase_speed", "decrease_speed"],
    "cover": ["toggle", "open_cover", "close_cover", "stop_cover"],
    "lock": ["lock", "unlock"],
    "scene": ["turn_on"],
    "script": ["turn_on", "toggle"],
    "automation": ["trigger", "toggle"],
    "button": ["press"],
    "input_button": ["press"],
    "media_player": ["media_play_pause", "volume_up", "volume_down", "media_next_track",
                     "media_previous_track"],
    "homeassistant": ["toggle", "turn_on", "turn_off"],
}


def section(text: str, start: str, end: str) -> str:
    """Return the text between the first start marker and the next end marker."""
    head = text.split(start, 1)
    if len(head) != 2:
        raise AssertionError(f"{start!r} not found")
    tail = head[1].split(end, 1)
    if len(tail) != 2:
        raise AssertionError(f"{end!r} not found after {start!r}")
    return tail[0]


def kind_table() -> dict:
    table = section(CPP, "const KindDef KINDS[] = {", "\n};")
    rows = re.findall(r'\{"(\w+)",\s*(\d+),\s*\{([^}]*)\}\}', table)
    return {name: (int(count), re.findall(r'"(\w+)"', acts)) for name, count, acts in rows}


class ComponentWiringTest(unittest.TestCase):
    def test_the_component_enables_the_api_action_defines_and_needs_api_and_wifi(self) -> None:
        self.assertIn('DEPENDENCIES = ["api", "wifi"]', INIT)
        self.assertIn('cg.add_define("USE_API_HOMEASSISTANT_SERVICES")', INIT)
        self.assertIn('cg.add_define("USE_API_HOMEASSISTANT_ACTION_RESPONSES")', INIT)
        self.assertIn('ha_action_ns = cg.esphome_ns.namespace("ha_action")', INIT)
        self.assertIn("namespace esphome::ha_action {", HEADER)

    def test_production_declares_the_component_and_links_the_page(self) -> None:
        self.assertIn("\nha_action:\n  id: ha_actions\n", CONFIG)
        self.assertIn("\nbutton_config:\n  id: button_cfg\n  idle_sleep_id: idle\n  ha_action_id: ha_actions\n",
                      CONFIG)

    def test_the_bench_config_keeps_the_page_without_the_component(self) -> None:
        self.assertNotIn("ha_action", BENCH)

    def test_the_link_is_optional_and_behind_a_define(self) -> None:
        self.assertIn("cv.Optional(CONF_HA_ACTION_ID): cv.use_id(ha_action.HaAction)", BUTTON_INIT)
        guarded = section(BUTTON_INIT, "    if CONF_HA_ACTION_ID in config:\n", "\n\n")
        self.assertIn("cg.add(var.set_ha_action(actions))", guarded)
        self.assertIn('cg.add_define("USE_BUTTON_CONFIG_HA_ACTION")', guarded)
        self.assertIn('#ifdef USE_BUTTON_CONFIG_HA_ACTION\n#include "esphome/components/ha_action/ha_action.h"\n'
                      "#endif", BUTTON_HEADER)
        for text in (BUTTON_HEADER, BUTTON_CPP):
            outside = re.sub(r"#ifdef USE_BUTTON_CONFIG_HA_ACTION\n.*?#(?:else|endif)", "", text,
                             flags=re.DOTALL)
            outside = re.sub(r"//[^\n]*", "", outside)
            for symbol in ("ha_action::", "ha_action_->"):
                self.assertNotIn(symbol, outside)


class StoreTest(unittest.TestCase):
    def test_the_record_has_its_own_unused_key_and_a_checksum(self) -> None:
        self.assertIn("static constexpr uint32_t PREFERENCE_KEY = 0x48414143U;", HEADER)
        self.assertIn("make_preference<Record>(PREFERENCE_KEY, true)", CPP)
        self.assertIn("static constexpr uint32_t MAGIC = 0x48414131U;", HEADER)
        self.assertIn("static constexpr uint16_t VERSION = 1;", HEADER)
        self.assertIn("static_assert(sizeof(Record) == 12 + SLOT_COUNT * sizeof(Entry) + 4,", HEADER)
        valid = section(CPP, "bool HaAction::valid_(const Record &record) {", "\n}")
        self.assertIn("record.magic != MAGIC || record.version != VERSION || "
                      "record.checksum != checksum_(record)", valid)
        self.assertIn("entry.val > 100", valid)
        self.assertIn("entry.act >= KINDS[entry.kind].count", valid)

    def test_no_other_record_uses_the_key(self) -> None:
        listed = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                                check=True).stdout.splitlines()
        sources = [ROOT / name for name in listed
                   if name.endswith((".h", ".cpp", ".yaml")) and "button_config_page" not in name]
        sources = [p for p in sources if p.exists()]
        sources.append(COMPONENT / "ha_action.h")
        sources = sorted(set(sources))
        users = [p.name for p in sources if "0x48414143" in p.read_text()]
        self.assertEqual(users, ["ha_action.h"])

    def test_the_slot_range_matches_the_ir_store(self) -> None:
        self.assertIn("FIRST_SLOT = 3;", HEADER)
        self.assertIn("LAST_SLOT = 20;", HEADER)
        self.assertIn("FIRST_BUTTON = 3;", STORE)
        self.assertIn("LAST_BUTTON = 20;", STORE)

    def test_the_token_tables_match_the_page_contract(self) -> None:
        table = kind_table()
        self.assertEqual(sorted(table), sorted(KINDS))
        for kind, acts in KINDS.items():
            self.assertEqual(table[kind], (len(acts), acts), kind)

    def test_validation_follows_the_contract(self) -> None:
        validate = section(CPP, "HaAction::Check HaAction::validate(", "\n}")
        self.assertIn("return Check::BAD_ACTION;", validate)
        self.assertIn("return Check::BAD_ENTITY;", validate)
        self.assertIn("return Check::BAD_STEP;", validate)
        self.assertLess(validate.index("BAD_ACTION"), validate.index("BAD_ENTITY"))
        self.assertLess(validate.index("BAD_ENTITY"), validate.index("BAD_STEP"))
        self.assertIn('const bool any_domain = kind == ANY_DOMAIN_KIND;', validate)
        self.assertIn("val < 0 || val > 100 || (is_step(kind_index, act_index) && val < 1)", validate)
        entity = section(CPP, "bool entity_valid(", "\n}")
        self.assertIn("length < 3 || length > HaAction::ENTITY_MAX", entity)
        self.assertIn("dot == length || dot == 0 || dot == length - 1", entity)
        self.assertIn("std::strncmp(text, domain_must_be, dot) == 0", entity)
        chars = section(CPP, "bool object_char(char value) {", "\n}")
        self.assertIn("(value >= 'a' && value <= 'z') || (value >= '0' && value <= '9') || value == '_'", chars)
        self.assertIn("ENTITY_MAX = 64;", HEADER)

    def test_every_write_runs_on_the_main_loop_and_every_read_takes_the_lock(self) -> None:
        self.assertIn("mutable std::mutex record_mutex_;", HEADER)
        for reader in ("bool HaAction::has_assignment(uint8_t slot) const {",
                       "HaAction::Assignment HaAction::assignment(uint8_t slot) const {",
                       "bool HaAction::store_(const Record &next) {"):
            self.assertIn("std::lock_guard<std::mutex> lock(this->record_mutex_)",
                          section(CPP, reader, "\n}"))
        self.assertIn("this->pref_.save(&this->record_)", section(CPP, "bool HaAction::store_(", "\n}"))
        self.assertIn("std::memset(&entry, 0, sizeof(entry));",
                      section(CPP, "bool HaAction::assign(", "\n}"))


class SendTest(unittest.TestCase):
    def test_the_limits(self) -> None:
        for text in ("QUEUE_MAX = 8;", "ERROR_MAX = 96;", "QUEUE_TIMEOUT_MS = 20000;",
                     "REPLY_TIMEOUT_MS = 5000;", "FAIL_SHOW_MS = 2000;"):
            self.assertIn(text, HEADER)

    def test_a_press_queues_requests_wifi_and_drops_past_the_cap(self) -> None:
        play = section(CPP, "bool HaAction::play(uint8_t slot) {", "\n}")
        self.assertTrue(play.lstrip().startswith("if (!this->has_assignment(slot))\n    return false;"))
        self.assertIn("if (this->count_ >= QUEUE_MAX) {", play)
        self.assertIn("this->set_result_(slot, RESULT_DROPPED, \"\");", play)
        self.assertIn("this->set_result_(slot, RESULT_QUEUED, \"\");", play)
        self.assertIn("this->request_wifi_();", play)
        self.assertLess(play.index("RESULT_DROPPED"), play.index("RESULT_QUEUED"))
        self.assertTrue(play.rstrip().endswith("return true;"))

    def test_the_service_is_kind_dot_action_and_a_step_is_light_turn_on(self) -> None:
        send = section(CPP, "bool HaAction::send_(Pending &entry) {", "\n}")
        self.assertIn('std::snprintf(service, sizeof(service), "%s.%s", def.name, step ? "turn_on" : act);', send)
        self.assertIn('std::strcmp(act, "brightness_down") == 0 ? "-" : ""', send)
        self.assertIn('StringRef::from_lit("entity_id")', send)
        self.assertIn('StringRef::from_lit("brightness_step_pct")', send)
        self.assertIn("request.data.init(step ? 2 : 1);", send)
        step = section(CPP, "bool is_step(", "\n}")
        self.assertIn('"light"', step)
        self.assertIn('"brightness_"', step)

    def test_the_reply_callback_exists_only_for_a_call_a_client_took(self) -> None:
        send = section(CPP, "bool HaAction::send_(Pending &entry) {", "\n}")
        sent = send.index("sent |= client->send_homeassistant_action(request);")
        gate = send.index("if (!sent)\n    return false;")
        register = send.index("server->register_action_response_callback(call_id,")
        mark = send.rindex("entry.sent = true;")
        self.assertLess(sent, gate)
        self.assertLess(gate, register)
        self.assertLess(register, mark)
        self.assertIn("for (auto &client : server->active_clients())", send)
        self.assertIn("request.call_id = call_id;", send)
        # The id advances only once a client took the call.
        self.assertGreater(send.index("this->next_call_id_++;"), gate)
        self.assertIn("static constexpr uint32_t CALL_ID_BASE = 0x48410000U;", HEADER)
        # The request strings live on this stack until the send returns.
        self.assertIn("char service[48];", send)
        self.assertIn("char amount[8]", send)

    def test_the_reply_and_the_timeouts_set_the_result(self) -> None:
        response = section(CPP, "void HaAction::on_response_(", "\n}")
        self.assertIn("success ? RESULT_OK : RESULT_ERROR", response)
        self.assertIn("this->queue_[i].sent && this->queue_[i].call_id == call_id", response)
        loop = section(CPP, "void HaAction::loop() {", "\n}")
        self.assertIn("!entry.sent && now - entry.queued_ms >= QUEUE_TIMEOUT_MS", loop)
        self.assertIn("this->finish_(i, RESULT_TIMEOUT, \"\");", loop)
        self.assertIn("entry.sent && now - entry.sent_ms >= REPLY_TIMEOUT_MS", loop)
        self.assertIn("this->finish_(i, RESULT_UNCONFIRMED, \"\");", loop)
        # One entry that cannot go blocks the later ones, so press order holds.
        self.assertIn("if (!this->send_(this->queue_[i]))\n      break;", loop)

    def test_the_error_text_is_cut_on_a_character_boundary(self) -> None:
        result = section(CPP, "void HaAction::set_result_(", "\n}")
        self.assertIn("std::min(std::strlen(error), ERROR_MAX)", result)
        self.assertIn("(static_cast<uint8_t>(error[length]) & 0xC0) == 0x80", result)
        self.assertIn("RESULT_ERROR || result == RESULT_TIMEOUT", result)
        self.assertIn("mutable std::mutex error_mutex_;", HEADER)

    def test_the_result_names_are_the_page_contract(self) -> None:
        names = section(CPP, "const char *HaAction::result_name(uint8_t result) {", "\n}")
        found = re.findall(r'return "(\w+)";', names)
        self.assertEqual(found, ["queued", "sent", "ok", "error", "unconfirmed", "timeout", "dropped",
                                 "none"])

    def test_the_busy_and_recent_failure_probes(self) -> None:
        self.assertIn("bool busy() const { return this->pending() != 0; }", HEADER)
        recent = section(CPP, "bool HaAction::failed_recently() const {", "\n}")
        self.assertIn("< FAIL_SHOW_MS", recent)

    def test_every_finish_renews_the_wifi_lease_after_it_removes_the_entry(self) -> None:
        finish = section(CPP, "void HaAction::finish_(", "\n}")
        self.assertLess(finish.index("this->count_--;"), finish.index("this->request_wifi_();"))
        self.assertIn("this->wifi_hold_()", section(CPP, "void HaAction::request_wifi_() {", "\n}"))


class StaleCallbackTest(unittest.TestCase):
    def test_an_unconfirmed_call_counts_as_a_stale_callback(self) -> None:
        self.assertIn("STALE_MAX = 8;", HEADER)
        finish = section(CPP, "void HaAction::finish_(", "\n}")
        self.assertIn("if (result == RESULT_UNCONFIRMED && this->queue_[index].call_id != 0)\n"
                      "    this->stale_callbacks_++;", finish)
        response = section(CPP, "void HaAction::on_response_(", "\n}")
        self.assertIn("if (this->stale_callbacks_ > 0)\n    this->stale_callbacks_--;", response)
        self.assertGreater(response.index("this->stale_callbacks_--;"), response.index("return;"))

    def test_past_the_limit_a_send_uses_call_id_zero_registers_nothing_and_finishes_at_once(self) -> None:
        send = section(CPP, "bool HaAction::send_(Pending &entry) {", "\n}")
        self.assertIn("const bool untracked = this->stale_callbacks_ >= STALE_MAX;", send)
        self.assertIn("const uint32_t call_id = untracked ? 0 : this->next_call_id_;", send)
        branch = section(send, "  if (untracked) {", "\n  }")
        self.assertNotIn("register_action_response_callback", branch)
        self.assertIn("return true;", branch)
        self.assertLess(send.index("if (untracked) {"), send.index("register_action_response_callback"))
        loop = section(CPP, "void HaAction::loop() {", "\n}")
        self.assertIn("if (this->queue_[i].call_id == 0)\n      this->finish_(i, RESULT_UNCONFIRMED, \"\");", loop)


class ExclusivityTest(unittest.TestCase):
    """A slot holds one of IR code, voice, Zigbee, BLE HID or Home Assistant."""

    def test_the_store_keeps_a_listener_list_and_names_the_owner(self) -> None:
        self.assertIn("enum Owner : uint8_t { OWNER_NONE = 0, OWNER_IR, OWNER_ZIGBEE, OWNER_BLE, OWNER_HA };", STORE)
        self.assertIn("std::vector<std::function<void(uint8_t, Owner)>> assignment_clear_callbacks_{};", STORE)
        self.assertNotIn("set_assignment_clear_callback", STORE + ZIGBEE + BLE + CPP)
        release = section(STORE, "void release_others(uint8_t button, Owner keep) const {", "\n  }")
        self.assertIn("callback(button, keep);", release)

    def test_ir_voice_and_clear_release_every_other_kind(self) -> None:
        voice = section(STORE, "bool set_voice(uint8_t button) {", "\n  }")
        self.assertIn("release_others(button, OWNER_IR);", voice)
        clear = section(STORE, "bool clear(uint8_t button) {", "\n  }")
        self.assertIn("release_others(button, OWNER_NONE);", clear)
        save = section(STORE, "bool save(uint8_t button, const std::vector<int32_t> &raw) {", "\n  }")
        self.assertIn("release_others(button, OWNER_IR);", save)

    def test_each_kind_registers_its_own_listener_and_skips_itself(self) -> None:
        zigbee = section(ZIGBEE, "ir_code_store.add_assignment_clear_callback(", "});")
        self.assertIn("keep != IrCodeStore::OWNER_ZIGBEE", zigbee)
        self.assertIn("this->clear(slot);", zigbee)
        ble = section(BLE, "::ir_code_store.add_assignment_clear_callback(", "});")
        self.assertIn("keep != IrCodeStore::OWNER_BLE", ble)
        self.assertIn("BleHid::instance()->clear(slot);", ble)
        ha = section(CPP, "::ir_code_store.add_assignment_clear_callback(", "});")
        self.assertIn("keep != IrCodeStore::OWNER_HA", ha)
        self.assertIn("this->clear(slot);", ha)

    def test_zigbee_and_ble_assigns_release_the_others_with_their_own_owner(self) -> None:
        store = section(ZIGBEE, "bool store_(uint8_t slot, const Entry &entry) {", "\n  }")
        self.assertIn("ir_code_store.clear_for_zigbee(slot)", store)
        self.assertIn("ir_code_store.release_others(slot, IrCodeStore::OWNER_ZIGBEE);", store)
        assign = section(BLE, "bool BleHid::assign(", "\n}")
        self.assertIn("::ir_code_store.clear_for_zigbee(slot)", assign)
        self.assertIn("::ir_code_store.release_others(slot, IrCodeStore::OWNER_BLE);", assign)

    def test_ha_assign_clears_ir_and_voice_then_releases_the_others(self) -> None:
        assign = section(CPP, "bool HaAction::assign(", "\n}")
        self.assertIn("::ir_code_store.clear_for_zigbee(slot)", assign)
        self.assertIn("::ir_code_store.release_others(slot, IrCodeStore::OWNER_HA);", assign)
        self.assertLess(assign.index("clear_for_zigbee"), assign.index("release_others"))

    def test_the_ble_module_knows_nothing_about_home_assistant(self) -> None:
        self.assertNotIn("ha_action", BLE)
        self.assertNotIn("HaAction", BLE)

    def test_playback_order_adds_ha_after_zigbee_and_before_ir(self) -> None:
        play = section(STORE, "void play_(uint8_t button) {", "\n  }")
        self.assertLess(play.index("hid_play_callback_(button, true)"), play.index("zigbee_play_callback_(button)"))
        self.assertLess(play.index("zigbee_play_callback_(button)"), play.index("ha_play_callback_(button)"))
        self.assertLess(play.index("ha_play_callback_(button)"), play.index("ir_code_store.load(button, code_)"))
        self.assertIn("::ir_ui.set_ha_play_callback([this](uint8_t slot) { return this->play(slot); });", CPP)

    def test_every_tap_path_reaches_play(self) -> None:
        tap = section(STORE, "void tap(uint8_t button, Tap mode) {", "\n  }")
        self.assertIn("play_(button);", tap)


class ReplayTest(unittest.TestCase):
    def test_the_replay_hook_takes_the_link_state(self) -> None:
        self.assertIn('[(cg.uint8, "bit"), (cg.bool_, "held"), (cg.bool_, "link")]', IDLE_INIT)
        header = (ROOT / "components" / "idle_sleep" / "idle_sleep.h").read_text()
        self.assertIn("std::function<bool(uint8_t, bool, bool)> replay_{};", header)
        self.assertIn("uint16_t replay_left_{0};", header)

    def test_production_sends_an_ha_slot_without_the_link_and_zigbee_with_it(self) -> None:
        replay = section(CONFIG, "  replay: !lambda |-\n", "\n\ni2c:")
        ha = replay.index("if (id(ha_actions).play(SLOT_OF_BIT[bit]))")
        zigbee = replay.index("return link && zigbee_assignments.play(SLOT_OF_BIT[bit]);")
        self.assertLess(ha, zigbee)
        self.assertNotIn("return zigbee_assignments.play(", replay)

    def test_a_bit_settles_when_it_sends_or_when_the_link_is_up(self) -> None:
        loop = section(IDLE_CPP, "void IdleSleep::loop() {", "\n}")
        replay = section(loop, "  if (this->replay_pending_) {", "  if (now - this->last_poll_ms_")
        self.assertIn("this->replay_(bit, held, this->link_seen_)", replay)
        self.assertIn("if (!this_sent && !this->link_seen_)\n        continue;", replay)
        self.assertIn("this->replay_left_ &= static_cast<uint16_t>(~(1u << bit));", replay)
        self.assertIn("if (this->replay_left_ == 0) {", replay)
        self.assertIn("Replay dropped: no link 3 s after setup", replay)
        # The stub mask is what the log and the held logic read, so it stays whole.
        self.assertIn("this->replay_left_ = rec.stub_down;", IDLE_CPP)
        self.assertIn("this->replay_mask_ = rec.stub_down;", IDLE_CPP)


class WifiLeaseTest(unittest.TestCase):
    def test_one_public_method_owns_the_lease(self) -> None:
        self.assertIn("void hold_wifi_for_action();", BUTTON_HEADER)
        self.assertIn("ACTION_WIFI_LEASE_MS = 60U * 1000U;", BUTTON_HEADER)
        hold = section(BUTTON_CPP, "void ButtonConfig::hold_wifi_for_action() {", "\n}")
        self.assertIn("this->action_wifi_ = true;", hold)
        self.assertIn("this->action_wifi_until_ms_ = millis() + ACTION_WIFI_LEASE_MS;", hold)
        self.assertIn("if (wifi::global_wifi_component->is_disabled()) {", hold)
        self.assertIn("wifi::global_wifi_component->enable();", hold)
        link = section(BUTTON_CPP, "void ButtonConfig::set_ha_action(", "\n}")
        self.assertIn("action->set_wifi_hold([this]() { this->hold_wifi_for_action(); });", link)

    def test_wifi_closes_only_when_the_page_session_and_the_lease_are_both_over(self) -> None:
        loop = section(BUTTON_CPP, "void ButtonConfig::loop() {", "\n}")
        self.assertIn("static_cast<int32_t>(now - this->action_wifi_until_ms_) >= 0", loop)
        guard = loop.index("if (!ended || this->temporary_wifi_ || this->action_wifi_ || "
                           "this->boot_wifi_always_on_)\n    return;")
        self.assertLess(guard, loop.index("wifi::global_wifi_component->disable();"))

    def test_sw9_does_not_cut_a_running_action(self) -> None:
        toggle = section(BUTTON_CPP, "void ButtonConfig::toggle_temporary_wifi() {", "\n}")
        self.assertIn("if (this->boot_wifi_always_on_)\n    return;", toggle)
        self.assertLess(toggle.index("if (this->action_wifi_) {"),
                        toggle.index("wifi::global_wifi_component->disable();"))

    def test_sw9_opens_a_page_session_when_only_the_lease_holds_wifi(self) -> None:
        toggle = section(BUTTON_CPP, "void ButtonConfig::toggle_temporary_wifi() {", "\n}")
        self.assertIn("wifi::global_wifi_component->is_disabled() || (this->action_wifi_ && !this->temporary_wifi_)",
                      toggle)
        self.assertLess(toggle.index("this->action_wifi_ && !this->temporary_wifi_"),
                        toggle.index('this->open_temporary_wifi_("by SW9");'))
        self.assertLess(toggle.index('this->open_temporary_wifi_("by SW9");'), toggle.index("} else {"))

    def test_a_page_used_during_the_lease_becomes_a_temporary_session(self) -> None:
        loop = section(BUTTON_CPP, "void ButtonConfig::loop() {", "\n}")
        convert = loop.index("this->last_activity_ms_.load(std::memory_order_acquire) <= ACTION_WIFI_LEASE_MS)")
        self.assertLess(loop.index("this->action_wifi_ = false;"), convert)
        self.assertLess(convert, loop.index("this->temporary_wifi_ = true;"))
        self.assertLess(loop.index("this->temporary_wifi_ = true;"), loop.index("if (!ended ||"))

    def test_the_sleep_gate_counts_the_lease_and_the_busy_queue(self) -> None:
        probe = section(CONFIG, "  block_probe: !lambda |-\n", "  replay: !lambda")
        self.assertIn("or the\n    // lease that a Home Assistant action holds.", probe)
        self.assertIn("const bool ha_busy = id(ha_actions).busy();", probe)
        self.assertIn("wifi_session << 6 | ha_busy << 7;", probe)
        self.assertIn("wifi=%d ha=%d at", probe)
        self.assertIn("window, wifi_session, ha_busy, millis());", probe)


class WebContractTest(unittest.TestCase):
    ACTION = section(BUTTON_CPP, "void ButtonConfig::handle_action_", "\nvoid ButtonConfig::complete_action_")

    def test_both_actions_are_known_and_need_a_slot(self) -> None:
        known = section(self.ACTION, "const bool known = ", ";")
        self.assertIn('action == "set_ha"', known)
        self.assertIn('action == "test_ha"', known)
        needs_slot = section(self.ACTION, "const bool needs_slot = ", ";")
        self.assertNotIn("set_ha", needs_slot)
        self.assertNotIn("test_ha", needs_slot)

    def test_an_unlinked_build_refuses_both_before_anything_else(self) -> None:
        refuse = 'R"({"ok":false,"error":"Home Assistant actions are not configured"})"'
        self.assertIn(refuse, self.ACTION)
        self.assertIn("if (ha_action_call && !ha_linked) {", self.ACTION)
        self.assertLess(self.ACTION.index("ha_action_call && !ha_linked"),
                        self.ACTION.index("const SlotInfo *info = needs_slot"))
        self.assertLess(self.ACTION.index("ha_action_call && !ha_linked"),
                        self.ACTION.index("compare_exchange_strong"))

    def test_the_three_validation_errors_are_exact_and_precede_the_busy_claim(self) -> None:
        claim = self.ACTION.index("compare_exchange_strong")
        for check, text in (
            ("BAD_ACTION", "unknown Home Assistant kind or action"),
            ("BAD_ENTITY", "an entity id is domain.object_id, up to 64 characters, and its domain must "
                           "match the kind"),
            ("BAD_STEP", "a brightness step is 1 to 100"),
        ):
            self.assertIn(f'R"({{"ok":false,"error":"{text}"}})"', self.ACTION)
            self.assertLess(self.ACTION.index(f"case ha_action::HaAction::Check::{check}:"), claim)
        self.assertIn("slot has no Home Assistant action", self.ACTION)
        self.assertLess(self.ACTION.index("slot has no Home Assistant action"), claim)

    def test_the_fields_are_copied_in_the_handler_and_the_flash_write_is_deferred(self) -> None:
        self.assertIn('ha_kind = request->arg("kind");', self.ACTION)
        self.assertIn('ha_act = request->arg("act");', self.ACTION)
        self.assertIn('ha_entity = request->arg("entity");', self.ACTION)
        self.assertIn('request->arg("val")', self.ACTION)
        branch = section(self.ACTION, '} else if (action == "set_ha") {', "  } else if")
        self.assertIn("this->defer([this, button, action_id, ha_kind, ha_act, ha_val, ha_entity]() {", branch)
        self.assertIn("this->complete_action_(action_id, this->ha_action_->assign(button, ha_kind, ha_act, "
                      "ha_val, ha_entity));", branch)
        test = section(self.ACTION, '} else if (action == "test_ha") {', "  } else if")
        self.assertIn("this->defer([this, button, action_id]() {", test)
        self.assertIn("this->complete_action_(action_id, this->ha_action_->play(button));", test)

    def test_the_value_parser_takes_three_digits_or_nothing(self) -> None:
        parse = section(BUTTON_CPP, "static int parse_ha_value(const std::string &text) {", "\n}")
        self.assertIn("if (text.empty())\n    return 0;", parse)
        self.assertIn("if (text.size() > 3)\n    return -1;", parse)
        self.assertIn("digit < '0' || digit > '9'", parse)

    def test_clear_reaches_ha_through_the_store(self) -> None:
        self.assertIn("complete_action_(action_id, ::ir_code_store.clear(button))", BUTTON_CPP)

    def test_the_state_carries_the_ha_fields_in_every_build(self) -> None:
        state = section(BUTTON_CPP, "void ButtonConfig::handle_state_", "\n}")
        self.assertIn('"hid_mod":%u,"ha_kind":"%s","ha_act":"%s","ha_val":%u,"ha_entity":"', state)
        self.assertRegex(state, r'ha\.assigned\s+\? "ha"')
        self.assertIn('R"("},"ha":{"pending":%u,"last_slot":%u,"last":"%s","error":")"', state)
        self.assertIn("print_json_text(stream, ha_error.c_str());", state)
        self.assertIn("print_json_text(stream, ha.entity.c_str());", state)
        # The unlinked defaults print the empty tokens, zero, and "none".
        unlinked = section(BUTTON_CPP, "#else\nstruct HaAssignment {", "#endif")
        self.assertIn('const char *kind{""};', unlinked)
        self.assertIn("uint8_t val{0};", unlinked)
        self.assertIn('return "none";', unlinked)

    def test_the_state_copies_the_assignment_under_the_store_lock(self) -> None:
        state = section(BUTTON_CPP, "void ButtonConfig::handle_state_", "\n}")
        self.assertIn("ha = this->ha_action_->assignment(info.slot);", state)
        self.assertIn("this->ha_action_->last_error(ha_error);", state)


class LedTest(unittest.TestCase):
    def test_d2_blinks_red_for_a_failure_after_the_wifi_logic_and_under_the_led_switch(self) -> None:
        effect = section(CONFIG, "name: Status Indicators", "on_turn_on:")
        blink = re.search(r"if \(id\(ha_actions\)\.failed_recently\(\)\)\s+it\[0\] = \(\(millis\(\) / 150\) % 2\) == 0 "
                          r"\? Color\(200, 0, 0\) : Color::BLACK;", effect)
        self.assertIsNotNone(blink)
        mask = re.search(r"if \(!status_on\)\s+it\.all\(\) = Color::BLACK;", effect)
        self.assertIsNotNone(mask)
        self.assertGreater(blink.start(), effect.index("it[0] = Color(140, 70, 0);"))
        self.assertLess(blink.start(), mask.start())


if __name__ == "__main__":
    unittest.main()
