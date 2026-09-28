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
BLE = (ROOT / "components" / "ble_hid" / "ble_hid.cpp").read_text()
BLE_HEADER = (ROOT / "components" / "ble_hid" / "ble_hid.h").read_text()

# Slots that cannot start the voice assistant. 20 is SW1, whose press edge is
# already owned by the receiver-mode hold gesture. 17 and 18 are the wheel
# detents, which have no release edge to end push-to-talk with.
NO_VOICE = {17, 18, 20}
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
        r'\{s:(\d+),l:"([^"]+)",v:([01]),x:([\d.]+),y:([\d.]+)(?:,c:"([^"]+)")?\}',
        array,
    )
    if not rows:
        raise AssertionError("page S array has no rows")
    return [
        {"slot": int(slot), "label": label, "voice": voice == "1", "x": float(x),
         "y": float(y), "class": css_class}
        for slot, label, voice, x, y, css_class in rows
    ]


class RoutingTest(unittest.TestCase):
    def test_the_component_claims_all_four_paths(self) -> None:
        for path in ("/buttons", "/buttons/api/state", "/buttons/api/code",
                     "/buttons/api/action", "/buttons/api/activity"):
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
            'if (method == HTTP_POST)\n    return url == "/buttons/api/action" || '
            'url == "/buttons/api/activity";',
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


class WifiSessionTest(unittest.TestCase):
    def test_missing_or_invalid_preference_keeps_wifi_off(self) -> None:
        load = section(CPP, "void ButtonConfig::load_wifi_pref_() {", "\n}")
        self.assertIn("WifiPref loaded{};", load)
        self.assertIn("this->wifi_pref_.load(&loaded) && loaded.magic == WIFI_PREF_MAGIC", load)
        self.assertIn("loaded.enabled <= 1", load)
        self.assertIn("loaded.enabled == 1", load)
        self.assertIn("this->wifi_always_on_.store(enabled", load)

    def test_saved_default_only_changes_wifi_at_boot(self) -> None:
        setup = section(CPP, "void ButtonConfig::setup() {", "\n}")
        self.assertLess(setup.index("this->load_wifi_pref_();"),
                        setup.index("wifi::global_wifi_component->enable();"))
        self.assertIn("this->boot_wifi_always_on_ = this->wifi_always_on();", setup)
        setter = section(CPP, "bool ButtonConfig::set_wifi_always_on_(bool enabled) {", "\n}")
        self.assertIn("this->wifi_pref_.save(&next)", setter)
        self.assertNotIn("global_wifi_component->enable()", setter)
        self.assertNotIn("global_wifi_component->disable()", setter)
        toggle = section(CPP, "void ButtonConfig::toggle_temporary_wifi() {", "\n}")
        self.assertIn("if (this->boot_wifi_always_on_)\n    return;", toggle)
        self.assertIn('this->open_temporary_wifi_("by SW9");', toggle)
        self.assertIn("this->temporary_wifi_ = false;", toggle)
        opener = section(CPP, "void ButtonConfig::open_temporary_wifi_(const char *reason) {", "\n}")
        self.assertIn("this->note_activity_();", opener)
        self.assertIn("this->temporary_wifi_ = true;", opener)
        self.assertIn("wifi::global_wifi_component->enable();", opener)

    def test_only_temporary_sessions_expire_after_page_inactivity(self) -> None:
        self.assertIn("WIFI_IDLE_MS = 10U * 60U * 1000U", HEADER)
        loop = section(CPP, "void ButtonConfig::loop() {", "\n}")
        self.assertIn("if (!this->temporary_wifi_)\n    return;", loop)
        self.assertIn("millis() - this->last_activity_ms_", loop)
        self.assertIn("if (idle_ms < WIFI_IDLE_MS)\n    return;", loop)
        self.assertIn("wifi::global_wifi_component->disable();", loop)
        page = section(CPP, "void ButtonConfig::handle_page_", "\n}")
        activity = section(CPP, "void ButtonConfig::handle_activity_", "\n}")
        action = section(CPP, "void ButtonConfig::handle_action_", "\n}")
        state = section(CPP, "void ButtonConfig::handle_state_", "\n}")
        for handler in (page, activity, action):
            self.assertIn("this->note_activity_();", handler)
        self.assertNotIn("note_activity_", state)
        self.assertIn('request->send(200, "application/json", R"({"ok":true})");', activity)

    def test_a_pairing_boot_opens_a_temporary_session(self) -> None:
        setup = section(CPP, "void ButtonConfig::setup() {", "\n}")
        load = setup.index("this->load_wifi_pref_();")
        gate = setup.index("if (this->boot_wifi_always_on_)\n    wifi::global_wifi_component->enable();")
        pair = setup.index("if (!this->boot_wifi_always_on_ && ::zigbee_assignments.pairing())\n"
                           '    this->open_temporary_wifi_("for Zigbee pairing");')
        self.assertLess(load, gate)
        self.assertLess(gate, pair)
        # The boot decides, so a window that never opens cannot keep Wi-Fi off.
        loop = section(CPP, "void ButtonConfig::loop() {", "\n}")
        self.assertNotIn("pairing_window_open", loop)
        self.assertNotIn("zigbee_assignments", loop)
        self.assertNotIn("pairing_wifi_checked_", CPP + HEADER)

    def test_page_switch_and_real_interactions_refresh_the_idle_clock(self) -> None:
        self.assertIn('aria-label="WiFi Always On"', PAGE)
        self.assertIn('id="wfd"', PAGE)
        self.assertIn('id="wfs"', PAGE)
        status = section(PAGE, "function networkStatus(){", "\n\nfunction ")
        self.assertIn("st.network.wifi_enabled===true", status)
        self.assertIn("st.network.wifi_always_on===true", status)
        switch = section(PAGE, "function setWifiAlwaysOn(){", "\n\nfunction ")
        self.assertIn('post("set_wifi_always_on"', switch)
        self.assertIn('"&enabled="+(wifiWant?"1":"0")', switch)
        self.assertIn('fetch("/buttons/api/activity",{method:"POST"', PAGE)
        self.assertIn('sendActivity();', PAGE)
        self.assertIn('["click","touchstart","keydown","input","change"]', PAGE)
        self.assertIn('document.addEventListener(type,pageActivity,true)', PAGE)
        self.assertNotIn("pageActivity()", section(PAGE, "function stateWatch(){", "\n\nfunction "))


class SleepSettingsTest(unittest.TestCase):
    """Production links idle_sleep, but the component must still build without it."""

    def test_the_idle_sleep_link_is_optional_and_behind_a_define(self) -> None:
        self.assertIn("from esphome.components import idle_sleep, web_server_base", INIT)
        self.assertIn("cv.Optional(CONF_IDLE_SLEEP_ID): cv.use_id(idle_sleep.IdleSleep)", INIT)
        guarded = section(INIT, "    if CONF_IDLE_SLEEP_ID in config:\n", "\n\n")
        self.assertIn("sleep = await cg.get_variable(config[CONF_IDLE_SLEEP_ID])", guarded)
        self.assertIn("cg.add(var.set_idle_sleep(sleep))", guarded)
        self.assertIn('cg.add_define("USE_BUTTON_CONFIG_IDLE_SLEEP")', guarded)
        self.assertEqual(INIT.count("USE_BUTTON_CONFIG_IDLE_SLEEP"), 1)
        self.assertNotIn("idle_sleep", INIT.split("AUTO_LOAD", 1)[1].split("\n", 1)[0])
        self.assertIn('#include "esphome/core/defines.h"', HEADER)
        # Every idle_sleep symbol in the C++ sits inside the define.
        for text in (HEADER, CPP):
            outside = re.sub(r"#ifdef USE_BUTTON_CONFIG_IDLE_SLEEP\n.*?#(?:else|endif)", "", text,
                             flags=re.DOTALL)
            outside = re.sub(r"//[^\n]*", "", outside)
            for symbol in ("idle_sleep::", "idle_sleep_", "idle_sleep/"):
                self.assertNotIn(symbol, outside)
        self.assertIn('#ifdef USE_BUTTON_CONFIG_IDLE_SLEEP\n#include "esphome/components/idle_sleep/idle_sleep.h"\n'
                      '#endif', HEADER)

    def test_the_state_reports_sleep_with_zeros_when_absent(self) -> None:
        state = section(CPP, "void ButtonConfig::handle_state_", "void ButtonConfig::handle_code_")
        self.assertIn('"mac":"%s"},"sleep":{"available":%s,"enabled":%s,"after_s":%u},"radios":', state)
        self.assertIn("const SleepState sleep = this->sleep_state_();", state)
        self.assertIn('sleep.available ? "true" : "false", sleep.enabled ? "true" : "false",', state)
        body = section(CPP, "ButtonConfig::SleepState ButtonConfig::sleep_state_() const {", "\n}")
        self.assertIn("return {true, this->idle_sleep_->enabled(), this->idle_sleep_->sleep_after_s()};", body)
        self.assertTrue(body.rstrip().endswith("return {false, false, 0};"))

    def test_both_sleep_actions_follow_the_wifi_action_pattern(self) -> None:
        action = section(CPP, "void ButtonConfig::handle_action_", "\nvoid ButtonConfig::complete_action_")
        known = section(action, "const bool known = ", ";")
        self.assertIn('action == "set_sleep_enabled"', known)
        self.assertIn('action == "set_sleep_after"', known)
        # Every refusal comes before the busy claim, so none holds action_pending_.
        claim = action.index("compare_exchange_strong(expected, true")
        for error in ("sleep is not configured", "invalid sleep switch", "sleep after is 10 to 3600 seconds"):
            self.assertIn(f'R"({{"ok":false,"error":"{error}"}})"', action)
            self.assertLess(action.index(error), claim)
        self.assertIn('if (sleep_action && !this->sleep_state_().available) {', action)
        self.assertIn('const std::string enabled = request->arg("enabled");', section(
            action, 'if (action == "set_sleep_enabled") {', "\n  }"))
        self.assertIn('parse_sleep_after(request->arg("seconds"), sleep_after_s)', action)
        self.assertIn('action != "set_wifi_always_on" && !sleep_action && action != "pair" &&', action)
        for name, call in (("set_sleep_enabled", "this->set_sleep_enabled_(sleep_on)"),
                           ("set_sleep_after", "this->set_sleep_after_(sleep_after_s)")):
            branch = section(action, f'}} else if (action == "{name}") {{', "\n  } else")
            self.assertIn("this->defer([this, action_id, ", branch)
            self.assertIn(f"this->complete_action_(action_id, {call});", branch)

    def test_the_setters_pass_through_and_the_range_matches_idle_sleep(self) -> None:
        enabled = section(CPP, "bool ButtonConfig::set_sleep_enabled_(bool enabled) {", "\n}")
        self.assertIn("return this->idle_sleep_ != nullptr && this->idle_sleep_->set_enabled(enabled);", enabled)
        self.assertIn("return false;", enabled.split("#else", 1)[1])
        after = section(CPP, "bool ButtonConfig::set_sleep_after_(uint32_t seconds) {", "\n}")
        self.assertIn("return this->idle_sleep_ != nullptr && this->idle_sleep_->set_sleep_after_s(seconds);",
                      after)
        self.assertIn("return false;", after.split("#else", 1)[1])
        parse = section(CPP, "static bool parse_sleep_after(const std::string &text, uint32_t &seconds) {", "\n}")
        self.assertIn("std::isdigit(static_cast<unsigned char>(text[0])) == 0", parse)
        self.assertIn("value < SLEEP_AFTER_MIN_S || value > SLEEP_AFTER_MAX_S", parse)
        self.assertIn("static constexpr uint32_t SLEEP_AFTER_MIN_S = 10;", CPP)
        self.assertIn("static constexpr uint32_t SLEEP_AFTER_MAX_S = 3600;", CPP)
        self.assertIn("static_assert(SLEEP_AFTER_MIN_S == idle_sleep::IdleSleep::MIN_SLEEP_AFTER_S &&", CPP)

    def test_the_page_block_shows_only_with_idle_sleep(self) -> None:
        wifi = section(PAGE, '<section class="card full conn" id="wificfg">', "</section>")
        block = section(wifi, '<div id="slpcfg" hidden>', "</div>")
        self.assertLess(wifi.index('id="wfb"'), wifi.index('id="slpcfg"'))
        self.assertLess(wifi.index('id="slpcfg"'), wifi.index('id="hab"'))
        self.assertIn('<h2 class="ttl">Sleep<label class="sw" id="slw"><input type="checkbox" id="slb"\n'
                      'aria-label="Sleep" disabled>', block)
        self.assertIn('<input type="number" id="sla" min="1" max="60" step="1"', block)
        status = section(PAGE, "function sleepStatus(){", "\n\nfunction ")
        self.assertIn("if(blk)blk.hidden=!(z&&z.available);", status)
        self.assertIn("box.checked=sleepBusy?sleepWant:on;box.disabled=sleepBusy", status)
        self.assertIn("document.activeElement!==num", status)
        switch = section(PAGE, "function setSleepEnabled(){", "\n\nfunction ")
        self.assertIn('sleepSave("set_sleep_enabled","&enabled="+(sleepWant?"1":"0")', switch)
        after = section(PAGE, "function setSleepAfter(){", "\n\nfunction ")
        self.assertIn("m<1||m>60", after)
        self.assertIn('sleepSave("set_sleep_after","&seconds="+(m*60)', after)
        save = section(PAGE, "function sleepSave(a,x,why){", "\n\nfunction ")
        self.assertIn("return waitAction(r.body.id)", save)
        self.assertIn("sleepBusy=false;return load().then(paint)", save)
        self.assertIn('document.getElementById("slb").onchange=setSleepEnabled;', PAGE)
        self.assertIn('document.getElementById("sla").onchange=setSleepAfter;', PAGE)

    def test_the_preview_serves_the_sleep_block(self) -> None:
        preview = (ROOT / "scripts" / "preview-buttons-page.py").read_text()
        self.assertIn('"sleep": {"available": True, "enabled": True, "after_s": 300}', preview)
        self.assertIn('elif action == "set_sleep_enabled":', preview)
        self.assertIn('elif action == "set_sleep_after":', preview)
        self.assertIn("10 <= int(seconds) <= 3600", preview)


class RestartTest(unittest.TestCase):
    """The page loses its socket to the reboot, so the reply has to leave first."""

    def test_the_restart_action_follows_the_wifi_action_pattern(self) -> None:
        action = section(CPP, "void ButtonConfig::handle_action_", "\nvoid ButtonConfig::complete_action_")
        self.assertIn('action == "restart"', section(action, "const bool known = ", ";"))
        self.assertIn('action != "restart"', section(action, "const bool needs_slot = ", ";"))
        branch = section(action, '} else if (action == "restart") {', "\n  } else")
        self.assertIn("this->defer([this, action_id]() {", branch)
        self.assertIn('ESP_LOGI(TAG, "Restart requested from the page");', branch)
        # The busy claim comes first, so a restart during a capture answers 409.
        self.assertLess(action.index("compare_exchange_strong(expected, true"),
                        action.index('} else if (action == "restart") {'))

    def test_the_reply_leaves_before_a_delayed_safe_reboot(self) -> None:
        action = section(CPP, "void ButtonConfig::handle_action_", "\nvoid ButtonConfig::complete_action_")
        branch = section(action, '} else if (action == "restart") {', "\n  } else")
        complete = branch.index("this->complete_action_(action_id, true);")
        timer = branch.index('this->set_timeout("restart", RESTART_DELAY_MS, []() { App.safe_reboot(); });')
        self.assertLess(complete, timer)
        # The httpd task sends the reply after it queues the defer, and the
        # reboot waits on the main loop timer.
        self.assertLess(action.index('} else if (action == "restart") {'),
                        action.index('R"({"ok":true,"id":%u})"'))
        self.assertIn("static constexpr uint32_t RESTART_DELAY_MS = 500;", CPP)
        self.assertEqual(CPP.count("safe_reboot("), 1)
        for bare in ("esp_restart(", "App.reboot(", "arch_restart("):
            self.assertNotIn(bare, CPP)
        self.assertIn('#include "esphome/core/application.h"', CPP)

    def test_the_page_confirms_and_posts_the_restart(self) -> None:
        wifi = section(PAGE, '<section class="card full conn" id="wificfg">', "</section>")
        self.assertLess(wifi.index('id="slpcfg"'), wifi.index('id="rsb"'))
        self.assertLess(wifi.index('id="rsb"'), wifi.index('id="hab"'))
        self.assertIn('<div class="act"><button type="button" id="rsb">Restart remote</button></div>',
                      wifi)
        self.assertIn('<p class="sub st" id="rss">The remote is not restarting.</p>', wifi)
        self.assertNotIn('id="rsb"', section(PAGE, '<section class="card full conn" id="zbcfg">', "</section>"))
        self.assertIn('document.getElementById("rsb").onclick=restartRemote;', PAGE)
        send = section(PAGE, "function restartRemote(){", "\n\n")
        self.assertIn("if(restartBusy)return;", send)
        self.assertIn('if(!confirm("Restart the remote? The settings and the button assignments are kept."))return;',
                      send)
        self.assertIn('post("restart")', send)
        # The reboot drops the socket, so the poll that comes back confirms it.
        self.assertNotIn("waitAction(", send)
        paint = section(PAGE, "function restartPaint(){", "\n\n")
        self.assertIn('b.disabled=restartBusy;b.textContent=restartBusy?"Restarting...":"Restart remote"', paint)
        self.assertIn("st.network.wifi_always_on===true", paint)
        self.assertIn('" Wi-Fi stays off after the restart. Hold Button 9 for two seconds to open a temporary session."',
                      paint)
        self.assertIn('"The remote is restarting."', paint)
        self.assertIn("function restartLost(){if(restartBusy&&restartId)restartDown=true}", PAGE)
        sync = section(PAGE, "function restartSync(j){", "\n\n")
        self.assertIn("restartBusy&&restartDown&&Number(j.action_id)<restartId", sync)
        # The page says restart everywhere, as the Zigbee pairing text does.
        self.assertNotIn("reboot", re.sub(r"//[^\n]*", "", section(PAGE, "<body>", "</html>")).lower())

    def test_the_preview_fakes_a_restart(self) -> None:
        preview = (ROOT / "scripts" / "preview-buttons-page.py").read_text()
        self.assertIn('elif action == "restart":', preview)
        self.assertIn('RESTART["until"] = time.monotonic() + RESTART_SECONDS', preview)
        self.assertIn('STATE["action_id"] = 0', preview)


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

    def test_only_slots_17_and_18_and_20_have_no_voice_action(self) -> None:
        """17 and 18 are wheel detents with no release edge to end push-to-talk.
        20 is SW1, whose press edge belongs to the receiver-mode hold."""
        firmware = {slot for slot, voice in cpp_slots() if not voice}
        self.assertEqual(firmware, NO_VOICE)


class PlacementTest(unittest.TestCase):
    def test_the_top_group_puts_button_1_on_the_right(self) -> None:
        """Button 1 sits to the right of Button 2 on the board."""
        rows = page_slots()[:2]
        self.assertEqual(
            [(row["slot"], row["label"]) for row in rows],
            [(19, "Button 2"), (20, "Button 1")],
        )
        self.assertLess(rows[0]["x"], rows[1]["x"])

    def test_the_wheel_hotspots_match_the_physical_directions(self) -> None:
        rows = {row["slot"]: row for row in page_slots()[2:9]}
        self.assertEqual(rows[18]["class"], "rot left")
        self.assertEqual(rows[17]["class"], "rot right")
        self.assertLess(rows[16]["x"], rows[14]["x"])
        self.assertGreater(rows[12]["x"], rows[14]["x"])
        self.assertLess(rows[13]["y"], rows[14]["y"])
        self.assertGreater(rows[15]["y"], rows[14]["y"])

    def test_both_rotation_slots_flank_the_wheel_up_hotspot(self) -> None:
        rows = {row["slot"]: row for row in page_slots()}
        self.assertEqual((rows[18]["x"], rows[18]["y"]), (50, 31.7))
        self.assertEqual((rows[17]["x"], rows[17]["y"]), (50, 31.7))
        self.assertIn(".remote .k.rot.left{clip-path:inset(0 50% 0 0)}", PAGE)
        self.assertIn(".remote .k.rot.right{clip-path:inset(0 0 0 50%)}", PAGE)

    def test_the_keypad_group_fills_column_by_column(self) -> None:
        """The 3x3 grid fills in array order, so the array order is the layout.
        The board reads 3 6 11, 4 7 10, 5 8 9 across its rows."""
        rows = page_slots()[9:]
        self.assertEqual([row["slot"] for row in rows], [3, 6, 11, 4, 7, 10, 5, 8, 9])
        self.assertEqual(
            [row["label"] for row in rows],
            [f"Button {n}" for n in (3, 6, 11, 4, 7, 10, 5, 8, 9)],
        )

    def test_the_page_renders_the_full_front_face_selector(self) -> None:
        self.assertIn('<div class="remote" id="remote">', PAGE)
        self.assertIn('data:image/svg+xml,__CASE_FRONT_FACE_SVG__', PAGE)
        self.assertIn('"case-front-face.svg"', INIT)

    def test_the_front_face_image_is_not_draggable(self) -> None:
        self.assertIn('alt="Front face of the homeThing c6 remote" draggable="false">', PAGE)
        self.assertIn('user-select:none;-webkit-user-drag:none', PAGE)


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
            "BleHid::instance()->assign(",
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

    def test_the_state_endpoint_reports_wifi_and_home_assistant(self) -> None:
        state = section(CPP, "void ButtonConfig::handle_state_", "void ButtonConfig::handle_code_")
        self.assertIn('"network":{"wifi":%s,"wifi_enabled":%s,"wifi_always_on":%s,'
                      '"home_assistant":%s,"ip":"%s","mac":"%s"}', state)
        self.assertIn("wifi::global_wifi_component->is_connected()", state)
        self.assertIn("api::global_api_server->is_connected()", state)
        self.assertIn("wifi::global_wifi_component->get_ip_addresses()", state)
        self.assertIn("get_mac_address_pretty_into_buffer(mac)", state)

    def test_the_state_row_reports_the_zigbee_target_first(self) -> None:
        """A slot holds one action, and a Zigbee target hides an old IR code."""
        state = section(CPP, "void ButtonConfig::handle_state_", "void ButtonConfig::handle_code_")
        self.assertRegex(
            state,
            r'hid\.assigned\s+\? "hid"[\s\S]*?zigbee\.assigned\s+\? "zigbee"'
            r'[\s\S]*?is_voice\(info\.slot\)\s+\? "voice"[\s\S]*?has_code\(info\.slot\) \? "ir"',
        )
        self.assertIn('"val":%d,"hid_kind":"%s","hid_usage":%u,"hid_mod":%u,"name":"', state)
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
        self.assertIn("complete_action_(action_id, esphome::ble_hid::BleHid::instance()->forget_bond())", CPP)
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
        for marker in ("<script src", "@import", "//cdn", 'src="http'):
            self.assertNotIn(marker, PAGE)
        # The one <link> is the favicon, and it carries the whole image inline.
        # Its only http:// is the SVG namespace, which no browser fetches.
        self.assertEqual(PAGE.count("<link"), 1)
        self.assertIn('<link rel=icon href="data:image/svg+xml,', PAGE)
        self.assertEqual(re.findall(r"http://[^\s\"'>%]*", PAGE),
                         ["http://www.w3.org/2000/svg"])
        # Outbound anchors load nothing until the reader follows them, so they
        # cannot stall the page on an offline LAN.
        self.assertEqual(
            re.findall(r"https://[^\s\"'>]+", PAGE),
            [
                "https://github.com/landonr/homething-c6",
                "https://github.com/Lucaslhm/Flipper-IRDB",
            ],
        )

    def test_the_page_only_calls_its_own_endpoints(self) -> None:
        calls = re.findall(r'fetch\("([^"?]+)', PAGE)
        self.assertEqual(
            sorted(set(calls)),
            ["/buttons/api/action", "/buttons/api/activity", "/buttons/api/code",
             "/buttons/api/state"],
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
        self.assertNotIn("<details", body)
        self.assertIn('function ms(u){return (u/1000).toFixed(1)+" ms"}', PAGE)
        # The IR detail sits in its code box immediately before its actions.
        box = section(PAGE, "function codeBox(lock){", "\n\nfunction loadCode")
        self.assertIn('h+=detail(sel)+"<div class=act>', box)
        self.assertNotIn("Now:", PAGE)

    def test_the_state_row_reports_the_frame_length_and_the_code(self) -> None:
        """Nine slots hold 68 pulses of the same length, so only the data word
        separates them."""
        state = section(CPP, "void ButtonConfig::handle_state_", "\n}")
        self.assertIn(
            '"pulses":%u,"us":%u,"code":"%s","fields":"%s","group":%u,"ieee":"%s","ep":%u,"act":%u,"val":%d,"hid_kind":"%s","hid_usage":%u,"hid_mod":%u,"name":"',
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

    def test_the_page_can_apply_a_code_and_copy_an_assignment(self) -> None:
        box = section(PAGE, "function codeBox(lock){", 'return h}')
        self.assertIn("<textarea id=ct", box)
        # The box carries the only copy of a code, so it never hides behind a toggle.
        self.assertNotIn("<details", box)
        self.assertIn('function hasCode(text){return !!String(text||"").replace(/\\s+/g,"")}', PAGE)
        self.assertIn('var codeDis=lock||!hasCode(cd)?" disabled":"";', box)
        self.assertNotIn('id=cc', box)
        self.assertIn('id=ca"+codeDis+">Apply to this input</button>', box)
        # Loading follows the code actions, so it cannot move them.
        self.assertIn(".code .load{color:var(--mut);font-size:13px;margin:8px 0 0}", PAGE)
        self.assertIn('"<div class=act><button type=button id=ca"+codeDis+">Apply to this input</button></div>"+', box)
        self.assertIn('"<p class=load>Loading the stored code.</p>"', box)
        self.assertIn('var disabled=lock||!hasCode(cd);', PAGE)
        # Assignment and config copies use one fallback for plain HTTP.
        copy = section(PAGE, "function copyBox(t){", "return ok}")
        self.assertIn('document.execCommand("copy")', copy)
        self.assertIn("if(!ok&&navigator.clipboard)", copy)
        self.assertNotIn("function copyCode()", PAGE)
        self.assertIn('go("set_ir_code",text)', PAGE)
        self.assertIn('fetch("/buttons/api/code?slot="+s', PAGE)
        self.assertIn('cd=code;cdSlot=s', PAGE)
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
    def test_one_selector_carries_all_actions(self) -> None:
        """A slot holds one action, so the panel shows one action at a time and
        the IR code box cannot sit under a Zigbee assignment."""
        editor = section(PAGE, "function editor(){", "\nfunction actFor(")
        self.assertIn('var opts=[["ir","IR code"],["zb","Zigbee target"],["hid","BLE HID"]];', editor)
        self.assertIn('if(d.v)opts.push(["va","Voice assistant"]);', editor)
        self.assertIn('opts.push(["cl","Clear"]);', editor)
        # Zigbee is offered everywhere, so it must sit outside the d.v branch.
        self.assertLess(editor.index('"Zigbee target"'), editor.index("if(d.v)opts.push"))
        # A slot that lost its voice action must not stay on a voice panel.
        self.assertIn('if(!d.v&&act==="va")act="ir";', editor)
        # The action list stays open, and the panel beside it repeats the selected
        # action as a heading so the fields under it are never read out of context.
        self.assertIn('class=aslist role=radiogroup', editor)
        self.assertIn('if(on)title=opts[i][1]}', editor)
        self.assertIn('var panel="<h2>"+esc(title)+"</h2>"+', editor)
        self.assertNotIn('var panel="<h2 class=hd2>', editor)
        self.assertIn('p.innerHTML="<h2>IR code</h2><p class=sub>', editor)
        self.assertIn('p.innerHTML=panel;', editor)
        self.assertIn('act=v;msg="";bad=false;paint()', editor)
        self.assertNotIn("<select id=as", editor)
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
        self.assertIn("h2.hd2,label.hd2{display:block;", PAGE)
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

    def test_the_page_never_publishes_to_zigbee2mqtt(self) -> None:
        """The websocket is read only. Assignment never published, because a
        group per device left one behind on every repeat assign, and pairing is
        now the remote's own window, so nothing is left that writes."""
        for gone in ("zpub", "zreq", "transaction", "bridge/request/group",
                     "bridge/request/device", "bridge/request/permit_join",
                     "bridge/response/permit_join"):
            self.assertNotIn(gone, PAGE)
        self.assertEqual(PAGE.count("ws.send("), 0)

    def test_the_pairing_button_pairs_the_remote_for_three_minutes(self) -> None:
        """The window belongs to the remote, so the button posts to the remote
        and the countdown follows the state endpoint."""
        self.assertIn("var ZPJ_SECONDS=180;", PAGE)
        # The radio and its pairing window sit above the rule. The browser link
        # to Zigbee2MQTT is a different subject and sits below it.
        self.assertIn('<hr class="rule">\n<h3>Zigbee2MQTT</h3>', PAGE)
        self.assertIn("hr.rule{border:0;border-top:1px solid var(--line);margin:16px 0}", PAGE)
        self.assertIn('<div class="act"><button type="button" class="sec" id="zpj">'
                      'Pair this remote for 3 minutes</button></div>', PAGE)
        # The control outlives the browser block, so build() wires it.
        self.assertNotIn("id=zpj>", PAGE)
        self.assertIn('document.getElementById("zpj").onclick=function(){zpjSet(!zpjOn)};', PAGE)
        send = section(PAGE, "function zpjSet(open){", "\n\n")
        self.assertIn('post("pair",null,undefined,undefined,"&on="+(open?"1":"0"))', send)
        # The remote restarts, so the press is never confirmed by an action id.
        self.assertNotIn("waitAction(", send)
        # A call that never restarts still has to release the action id, or every
        # later action answers 409.
        pair = section(CPP, 'else if (action == "pair") {', "  } else if")
        self.assertIn("::zigbee_assignments.begin_pairing()", pair)
        self.assertIn("::zigbee_assignments.cancel_pairing();", pair)
        self.assertIn("this->complete_action_(action_id, ok);", pair)
        # Both directions restart the remote, so every press asks first. A joined
        # remote also loses its network to a pairing press.
        self.assertIn("if(!confirm(open?(zbPaired()?", send)
        self.assertLess(send.index("if(!confirm("), send.index("zpjBusy=true;"))
        self.assertIn("erases the Zigbee network credentials of this remote", send)
        self.assertIn("The button assignments are kept.", send)
        self.assertIn('"The remote restarts to start pairing. This page reconnects when the remote '
                      'is back. Continue?"', send)
        self.assertIn('"The remote restarts with the Zigbee radio off."', send)
        self.assertIn("var always=!!(st.network&&st.network.wifi_always_on===true);", send)
        self.assertIn('(always?"":" Wi-Fi stays off after the restart. Hold Button 9 for two seconds '
                      'to open a temporary session.")', send)
        paint = section(PAGE, "function zpjPaint(){", "\n\n// The state poll")
        self.assertIn("b.disabled=zpjBusy||!known;", paint)
        self.assertIn('b.textContent=zpjBusy?"Restarting...":zpjOn?"Stop pairing":'
                      '"Pair this remote for 3 minutes"}', paint)
        self.assertIn('zpjDown?"The remote is restarting.":', paint)
        self.assertIn('zpjOn?"The remote is pairing for "+mmss(zpjLeft)+".":', paint)
        self.assertIn('"The remote is not pairing."', paint)
        # A window that runs out turns the radio off, so the off line names the
        # cause. Otherwise the page reports a radio nobody switched off.
        why = section(PAGE, "function zbOffWhy(){", "\n\n")
        self.assertIn("st.zigbee.pair_failed", why)
        self.assertIn('" The last pairing attempt found no coordinator, '
                      'so the radio went off."', why)
        self.assertIn('"off. Zigbee buttons are disabled."+zbOffWhy()', PAGE)

    def test_the_coordinator_window_is_reported_and_never_asked_for(self) -> None:
        """A join needs both sides open, so the page still names the coordinator
        state. bridge/info is retained, so it arrives on connect and on change."""
        self.assertIn('<p class="sub st" id="zcs">Coordinator pairing state is loading.</p>', PAGE)
        self.assertIn('if(m.topic==="bridge/info"&&m.payload){', PAGE)
        self.assertIn("zcOn=!!m.payload.permit_join;", PAGE)
        self.assertIn("end>0?Math.max(0,Math.round((end-Date.now())/1000)):ZPJ_SECONDS;", PAGE)
        paint = section(PAGE, "function zcPaint(){", "\n\n// bridge/info reports")
        self.assertIn('"The coordinator pairing state needs the Zigbee2MQTT link.":', paint)
        self.assertIn('zcOn?"Pairing is open on the coordinator for "+mmss(zcLeft)+".":', paint)
        self.assertIn('"Pairing is closed on the coordinator. Permit joining in Zigbee2MQTT."',
                      paint)
        # A closed socket only means this browser stopped watching the window.
        self.assertIn("zcOn=false;zcLeft=0;zcTick();", PAGE)

    def test_the_state_poll_carries_the_zigbee_half(self) -> None:
        """One 1.5s poll drives every live line. It used to drop j.zigbee, which
        froze the link line at whatever the first load put there."""
        body = section(PAGE, "function stateRefresh(){", "\n\nfunction stateWatch")
        self.assertIn("st.network=j.network;st.ble=j.ble;st.radios=j.radios;st.zigbee=j.zigbee;", body)
        self.assertIn("st.sleep=j.sleep;zpjSync();networkStatus();sleepStatus();restartSync(j);"
                      "radioStatus();bleStatus()}},\nfunction(){zpjLost();restartLost()})", body)
        self.assertIn("function stateWatch(){if(!stTimer)stTimer=setInterval(stateRefresh,1500)}",
                      PAGE)
        # A failed poll while a press is open is the restart, not a dead remote.
        self.assertIn("function zpjLost(){if(zpjBusy)zpjDown=true;zpjPaint()}", PAGE)
        sync = section(PAGE, "function zpjSync(){", "\n\n")
        self.assertIn("if(zpjBusy&&on===zpjWant)zpjBusy=false;", sync)
        self.assertIn("zpjOn=on;zpjLeft=on?(Number(z.pair_left)||0):0;", sync)

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
        """Paste asks before it writes the copied config to the selected input."""
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
        self.assertIn('if(cfgAll[source]!==undefined){c.code=cfgAll[source]', copy)
        self.assertIn('fetch("/buttons/api/code?slot="+source', copy)
        self.assertIn('if(j.slot!==source||!j.present||!j.text)throw new Error();', copy)
        self.assertIn('clip=c;', copy)
        paste = section(PAGE, "function pasteAssignment(){", "\n\nfunction applyCode(")
        self.assertIn('if(!confirm("Apply the "+', paste)
        self.assertIn('if(c.kind==="ir"){act="ir";codeLoad++;cd=c.code;cdSlot=target}', paste)
        self.assertIn('act="zb";zkv=c.device?"d":"g";', paste)
        self.assertIn('zsv=c.device?"":String(c.group);zdv=c.device?c.ieee:"";', paste)
        self.assertIn('zpv=c.device?String(c.ep||1):"";zav=Number(c.act)||0;', paste)
        self.assertIn('zvv=za(zav)&&za(zav).p?String(c.val):""}', paste)
        self.assertIn('go("set_ir_code",c.code)', paste)
        self.assertIn('go("set_hid",null,"&kind="+hkv', paste)
        self.assertIn('sendDevice(c.ieee,String(c.ep||1),c.name||"",String(c.val||0))', paste)
        self.assertIn('sendGroup(String(c.group),c.name||"",String(c.val||0))', paste)
        load = section(PAGE, "function loadCode(s){", "\n\n// The page")
        self.assertIn("var loadId=++codeLoad", load)
        self.assertIn("if(loadId!==codeLoad)return;", load)
        self.assertIn("if(cfgAll[s]!==undefined)return cfgAll[s]", load)

    def test_the_page_carries_one_import_and_export_card(self) -> None:
        """The whole assignment set moves as one block of text, so a remote can
        be restored without a source remote in hand."""
        # All radio types use vertical sections above import and export.
        self.assertIn('<nav class="tabs full" aria-label="Setup sections">', PAGE)
        self.assertIn('<div class="tabgrid" id="buttonstab">', PAGE)
        self.assertIn('<p class="sub full">Select a button to assign an action.</p>', PAGE)
        self.assertIn('<div class="tabgrid" id="configtab" hidden>', PAGE)
        self.assertIn('<h1 class="full secttl">Connections</h1>', PAGE)
        self.assertIn('<section class="card full conn" id="wificfg">', PAGE)
        self.assertIn('<p class="sub st" id="wfs">Wi-Fi state is loading.</p>', PAGE)
        self.assertIn('<p class="sub st" id="has">Home Assistant API state is loading.</p>', PAGE)
        self.assertIn('<section class="card full conn" id="zbcfg">\n'
                      '<h2 class="ttl">Zigbee<label class="sw" id="zrw">'
                      '<input type="checkbox" id="zrb"\naria-label="Zigbee radio">'
                      '<span></span></label></h2>\n'
                      '<p class="sub st" id="zrs">Zigbee radio state is loading.</p>\n'
                      '<p class="sub st" id="zpjs">Pairing state is loading.</p>\n'
                      '<p class="sub">Pairing erases the Zigbee network credentials of '
                      'this remote and restarts it.\n'
                      'The button assignments are kept. If WiFi Always On is off, the '
                      'remote opens a temporary Wi-Fi\n'
                      'session when it restarts to pair, so this page reconnects. '
                      'Permit joining in Zigbee2MQTT as\n'
                      'well, because a join needs both sides.</p>\n'
                      '<div class="act"><button type="button" class="sec" id="zpj">'
                      'Pair this remote for 3 minutes</button></div>\n'
                      '<hr class="rule">\n'
                      '<h3>Zigbee2MQTT</h3>\n'
                      '<p class="sub st" id="zsum">Zigbee2MQTT status is loading.</p>\n'
                      '<p class="sub st" id="zcs">Coordinator pairing state is loading.</p>\n'
                      '<div id="z2m"></div>', PAGE)
        self.assertIn('<section class="card full conn" id="blecfg">\n'
                      '<h2 class="ttl">Bluetooth<label class="sw" id="brw">'
                      '<input type="checkbox" id="brb"\naria-label="Bluetooth radio">'
                      '<span></span></label></h2>\n'
                      '<p class="sub st" id="bst">BLE HID state is loading.</p>', PAGE)
        self.assertIn('<section class="card full" id="cfg">', PAGE.split('id="configtab"', 1)[1])
        self.assertIn('<h1 class="full secttl">Import Export</h1>\n'
                      '<section class="card full" id="cfg">\n<div id="cfgio"></div>', PAGE)
        self.assertNotIn("saveWifi", PAGE)
        self.assertIn('aria-label="WiFi Always On"', PAGE)
        # A connection card cannot sit inside the collapsed import card.
        self.assertNotIn('id="cfgb" hidden><div id="z2m">', PAGE)
        self.assertNotIn('class="sep"', PAGE)
        self.assertNotIn("cfg-status", PAGE)
        self.assertNotIn('id="cxz"', PAGE)
        # The page title leads, so neither radio card pushes it down.
        self.assertIn('<div>\n<h1>homeThing c6</h1>\n'
                      '<p class="sub"><a href="https://github.com/landonr/homething-c6">'
                      'github.com/landonr/homething-c6</a></p>\n'
                      '</div>\n</header>', PAGE)
        # The logo is inline and uncoloured, so one copy follows the theme text
        # colour instead of shipping a light file and a dark file.
        self.assertIn('<header class="full">\n<svg class=logo viewBox="0 0 805.333 795.107" '
                      'fill=currentColor aria-hidden=true><path ', PAGE)
        self.assertIn(".logo{width:34px;height:34px;flex:none}", PAGE)
        # The tab icon is the same mark as a data URI. It carries its own
        # colour rule, because a standalone favicon has no page to inherit from.
        self.assertIn('<link rel=icon href="data:image/svg+xml,%3Csvg%20'
                      'xmlns=%22http://www.w3.org/2000/svg%22%20'
                      'viewBox=%220%200%20805.333%20795.107%22%3E', PAGE)
        self.assertIn("%3Cstyle%3Epath%7Bfill:%2316181d%7D"
                      "@media(prefers-color-scheme:dark)%7Bpath%7Bfill:%23e7eaef%7D%7D"
                      "%3C/style%3E", PAGE)
        self.assertIn("header.full{display:flex;align-items:center;gap:12px}", PAGE)
        card = section(PAGE, "function cfgPaint(){", "\n\nfunction editor(){")
        self.assertIn('<h1 class="full secttl">Import Export</h1>', PAGE)
        self.assertNotIn('id="cxo"', PAGE)
        self.assertNotIn('id="cxs"', PAGE)
        # The button keeps its place and locks instead, so no line moves.
        self.assertIn('id="bfr">Forget Bluetooth host</button>', PAGE)
        self.assertIn('post("forget_ble")', PAGE)
        # The host name is free text from the peer, so it is escaped both ways.
        self.assertIn('"pairing":%s,"host":"', CPP)
        self.assertIn("print_json_text(stream, esphome::ble_hid::BleHid::instance()->host_name()", CPP)
        self.assertIn('function bleHost(){return st.ble.host?esc(st.ble.host):"a saved host"}', PAGE)
        # One line under the heading reports the link, so no second line can
        # disagree with it.
        status = section(PAGE, "function z2mLine(){", "\n\n// The pairing control")
        self.assertIn('var e=document.getElementById("zsum");', status)
        self.assertIn('if(z2mUp()){e.innerHTML="<span class=dot></span>This browser is connected to "+\n'
                      '"Zigbee2MQTT. "+z2mCounts()+".";return}', status)
        self.assertIn('if(zerr){e.innerHTML="<span class=\'dot bad\'></span>This browser is not '
                      'connected to "+\n"Zigbee2MQTT. "+esc(zerr);return}', status)
        self.assertIn('e.innerHTML="<span class=\'dot off\'></span>This browser is not connected to "+',
                      status)
        self.assertNotIn("z2mTitle", PAGE)
        self.assertNotIn("id=zst", PAGE)
        self.assertIn(".dot.off{background:var(--line)}.dot.warn{background:var(--warn)}\n"
                      ".dot.bad{background:var(--bad)}", PAGE)
        self.assertIn("function stateWatch(){if(!stTimer)stTimer=setInterval(stateRefresh,1500)}",
                      PAGE)
        refresh = section(PAGE, "function stateRefresh(){", "\n\nfunction stateWatch()")
        self.assertIn('fetch("/buttons/api/state",{cache:"no-store"})', refresh)
        self.assertIn("st.ble=j.ble;st.radios=j.radios;st.zigbee=j.zigbee;", refresh)
        self.assertIn("radioStatus();bleStatus()", refresh)
        self.assertNotIn("paint()", refresh)
        # The connection inputs are built once, so the repaint owns cfgio alone.
        self.assertIn('var e=document.getElementById("cfgio")', card)
        # The startup path reads state, then preloads every stored IR code.
        start = section(PAGE, "load().then(function(j){", "document.getElementById(\"ed\")")
        self.assertIn("return cfgRefresh()", start)
        self.assertIn('<textarea id=cx', card)
        # The card heading names the block, so the body repeats no title.
        self.assertNotIn('Import and export</p>', card)
        self.assertNotIn("cfgMode", PAGE)
        self.assertNotIn("cfgOut", PAGE)
        self.assertNotIn('id=cs', card)
        self.assertNotIn('id=cxr', card)
        self.assertIn('id=cxfp"+rd+">Choose File</button>', card)
        self.assertIn('id=cxd"+em+">Download JSON</button>', card)
        self.assertIn("id=cxf type=file accept='.json,application/json'", card)
        self.assertIn('id=cxc"+em+">Copy</button>', card)
        self.assertIn('id=cxa"+wr+">Apply to the remote</button>', card)
        # Copy and download need text, so an empty box disables both.
        self.assertIn('var em=rd||(!cfgReady&&!cfgDirty?" disabled":String(cfgIn).trim()?"":" disabled")', card)
        # One buffer keeps a pasted file and manual edits through a repaint.
        self.assertIn('esc(cfgIn)', card)
        self.assertIn("box.oninput=function(){cfgIn=box.value;", card)
        self.assertIn('var off=cfgBusy||!String(cfgIn).trim()', card)
        self.assertIn('document.getElementById("cxd").onclick=cfgDownload', card)
        self.assertIn('cfgDirty=true', card)
        self.assertIn('document.getElementById("cxfp").onclick=', card)
        self.assertIn('document.getElementById("cxf").onchange=cfgLoadFile', card)
        # An import writes flash, so it stays disabled while the remote is busy.
        self.assertIn('wr=(cfgBusy||(st&&st.busy)||(!cfgReady&&!cfgDirty))?" disabled":""', card)
        self.assertIn("editor();cfgPaint()}", PAGE)

    def test_the_config_card_can_download_and_load_a_local_json_file(self) -> None:
        download = section(PAGE, "function cfgDownload(){", "\n\nfunction cfgJsonFile")
        self.assertIn('new Blob([cfgIn],{type:"application/json"})', download)
        self.assertIn('a.download="c6remote-config.json"', download)
        self.assertIn("URL.createObjectURL", download)
        self.assertIn("URL.revokeObjectURL", download)
        load = section(PAGE, "function cfgLoadFile(){", "\n\n// A repaint")
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
        self.assertIn('cfgAll[s]=j.text', PAGE)
        refresh = section(PAGE, "function cfgRefresh(){", "\n\n")
        self.assertIn('fetch("/buttons/api/code?slot="+slot', refresh)
        self.assertIn("cfgTask=need.reduce(function(p,slot){", refresh)
        self.assertIn("cfgIn=cfgBlob()", refresh)

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


class RadioSwitchTest(unittest.TestCase):
    """One switch for each radio, held on the remote and shown on the page."""

    def test_each_radio_keeps_its_switch_in_its_own_record(self) -> None:
        # The flag replaces a reserved field, so an old record loads unchanged
        # and reads as on.
        self.assertIn("static constexpr uint16_t FLAG_RADIO_OFF = 0x0001;", ZIGBEE)
        self.assertIn("uint16_t flags;", ZIGBEE)
        self.assertIn("static constexpr uint8_t FLAG_RADIO_OFF = 0x01;", BLE_HEADER)
        self.assertIn("uint8_t flags;", BLE_HEADER)
        self.assertIn("uint8_t reserved[2];", BLE_HEADER)
        self.assertIn("const uint16_t boot_flags = record_.flags;", ZIGBEE)
        self.assertIn("radio_on_.store((boot_flags & FLAG_RADIO_OFF) == 0", ZIGBEE)
        self.assertIn("this->radio_on_.store((this->record_.flags & FLAG_RADIO_OFF) == 0", BLE)

    def test_an_off_radio_sends_nothing(self) -> None:
        play = section(ZIGBEE, "  bool play(uint8_t slot) {", "\n  }")
        self.assertIn("!radio_enabled()", play)
        tick = section(ZIGBEE, "  void tick() {", "const uint32_t now")
        self.assertIn("if (!radio_enabled())\n      return;", tick)
        pressed = section(BLE, "bool BleHid::set_pressed(uint8_t slot, bool pressed) {", "\n}")
        self.assertIn("!this->radio_enabled()", pressed)
        self.assertIn("if (!this->radio_enabled() || !this->hid_started_", BLE)

    def test_the_bluetooth_stack_stays_down_while_the_switch_is_off(self) -> None:
        setup = section(BLE, "void BleHid::setup() {", "\n}")
        self.assertIn("if (!this->radio_enabled()) {", setup)
        self.assertNotIn("mark_failed", section(setup, "radio_enabled()) {", "  }"))
        # The first turn-on starts the stack, because setup skipped it.
        switch = section(BLE, "bool BleHid::set_radio_enabled(bool enabled) {", "\n}")
        self.assertIn("if (!this->stack_ready_) {", switch)
        self.assertIn("this->release_all_();", switch)
        self.assertIn("ble_gap_adv_stop();", switch)
        self.assertIn("ble_gap_terminate(connection, BLE_ERR_REM_USER_CONN_TERM);", switch)

    def test_the_state_and_action_endpoints_carry_both_switches(self) -> None:
        self.assertIn('"radios":{"zigbee":%s,"ble":%s,"home_assistant":%s}', CPP)
        self.assertIn('"zigbee":{"started":%s,"paired":%s,"new":%s,"gated":%s,'
                      '"pairing":%s,"pair_left":%u,"pair_failed":%s,"reach":"%s"}', CPP)
        self.assertIn("::zigbee_assignments.link_started() ? \"true\" : \"false\"", CPP)
        self.assertIn("::zigbee_assignments.link_factory_new() ? \"true\" : \"false\"", CPP)
        self.assertIn("::zigbee_assignments.radio_enabled() ? \"true\" : \"false\"", CPP)
        self.assertIn('action == "set_radio"', CPP)
        self.assertIn('R"({"ok":false,"error":"invalid radio switch"})"', CPP)
        self.assertIn('const bool needs_slot = action != "forget_ble" && action != "set_radio" &&'
                      '\n                          action != "set_wifi_always_on" && !sleep_action && '
                      'action != "pair" &&\n                          action != "restart";', CPP)
        # A switch writes flash, so it runs on the loop like every other write.
        switch = section(CPP, 'else if (action == "set_radio") {', "  } else {")
        self.assertIn("this->defer(", switch)
        self.assertIn("::zigbee_assignments.set_radio_enabled(radio_on)", switch)
        self.assertIn("set_radio_enabled(radio_on)", switch)
        self.assertIn("this->set_ha_api_expected(radio_on)", switch)
        self.assertIn('radio != "home_assistant"', CPP)

    def test_an_off_zigbee_radio_keeps_the_stack_down_after_a_boot(self) -> None:
        """The ESP-Zigbee stack has no stop and no restart, so the only way to
        keep the radio off is to hold the component down before its setup."""
        gate = section(CONFIG, "    - priority: 800", "    - priority: 600")
        self.assertIn("if (!ZigbeeAssignmentManager::radio_enabled_from_flash()) {", gate)
        self.assertIn("id(zigbee_radio)->mark_failed();", gate)
        self.assertIn("zigbee_assignments.set_boot_gated(true);", gate)
        # The rest of the boot work keeps its own priority behind that gate.
        self.assertIn("    - priority: 600\n      then:\n"
                      "        - lambda: ir_code_store.setup();", CONFIG)
        # Preferences open in app_main, so a flash read works at any priority.
        self.assertIn("static bool radio_enabled_from_flash() {", ZIGBEE)
        # A remote with no record has never paired, so it boots with the radio
        # off and waits for the pairing button.
        self.assertIn("if (!preference.load(&record) || !valid_(record))\n      return false;",
                      ZIGBEE)
        setup = section(ZIGBEE, "  void setup() {", "\n  }")
        self.assertIn("record_.flags = FLAG_RADIO_OFF;", setup)
        # A migrated record keeps the radio its owner already had, so the bit is
        # set in that branch alone and never in reset_record_.
        self.assertNotIn("FLAG_RADIO_OFF",
                         section(ZIGBEE, "static void reset_record_(Record &record) {", "\n  }"))
        # The switch cannot lift the gate, so the page asks for the one cure.
        self.assertIn('if(z.gated)return "The stack is down. Restart the remote to start it.";', PAGE)
        self.assertIn('"zigbee":{"started":%s,"paired":%s,"new":%s,"gated":%s,'
                      '"pairing":%s,"pair_left":%u,"pair_failed":%s,"reach":"%s"}', CPP)
        self.assertIn("::zigbee_assignments.boot_gated() ? \"true\" : \"false\"", CPP)
        # Home Assistant offers the same restart as the page.
        self.assertIn("  - platform: restart\n    name: Restart", CONFIG)

    def test_neither_radio_switch_acts_on_its_own_state_at_boot(self) -> None:
        """A template switch defaults to ALWAYS_OFF, and its setup fires
        turn_off_action. That switched both radios off on every boot before the
        stored flag was even read."""
        block = section(CONFIG, "  - platform: template\n    name: Zigbee Radio", "\nremote_receiver:")
        self.assertEqual(block.count("restore_mode: DISABLED"), 3)
        self.assertNotIn("restore_mode: ALWAYS", block)

    def test_the_yaml_exposes_one_switch_for_each_radio(self) -> None:
        block = section(CONFIG, "  - platform: template\n    name: Zigbee Radio", "\nremote_receiver:")
        self.assertIn("lambda: return zigbee_assignments.radio_enabled();", block)
        self.assertIn("lambda: zigbee_assignments.set_radio_enabled(true);", block)
        self.assertIn("lambda: zigbee_assignments.set_radio_enabled(false);", block)
        self.assertIn("lambda: return id(ble_hid_remote).radio_enabled();", block)
        self.assertIn("lambda: id(ble_hid_remote).set_radio_enabled(true);", block)
        self.assertIn("lambda: id(ble_hid_remote).set_radio_enabled(false);", block)
        self.assertIn("lambda: return id(button_cfg).ha_api_expected();", block)
        self.assertIn("lambda: id(button_cfg).set_ha_api_expected(true);", block)
        self.assertIn("lambda: id(button_cfg).set_ha_api_expected(false);", block)
        # The component keeps no global instance, so the YAML pushes the link
        # state to the manager the page reads.
        self.assertIn("zigbee_assignments.set_link_state(id(zigbee_radio).is_started(),", CONFIG)
        self.assertIn("id(zigbee_radio)->factory_new_.load());", CONFIG)
        # D5 must not report a healthy Zigbee link that sends nothing.
        self.assertIn("if (!zigbee_assignments.radio_enabled() || !id(zigbee_radio).is_started())",
                      CONFIG)
        self.assertIn("const bool ha_expected = id(button_cfg).ha_api_expected();", CONFIG)
        self.assertIn("it[0] = Color(130, 65, 0);", CONFIG)

    def test_the_page_marks_a_held_input_and_keeps_its_assignment(self) -> None:
        self.assertIn('function radioOn(kind){return !st||!st.radios||st.radios[kind]!==false}', PAGE)
        self.assertIn('function slotRadio(r){return !r?"":r.action==="zigbee"?"zigbee":'
                      'r.action==="hid"?"ble":""}', PAGE)
        self.assertIn('b.className=["k",d.c,setClass(r),slotRadioOff(d.s)?"rf":""]', PAGE)
        # The label stays, so the tile still says what the input is assigned to.
        self.assertIn(".k.rf span{opacity:.55}", PAGE)
        self.assertIn("background:var(--bad);margin-left:6px;vertical-align:middle}", PAGE)
        self.assertIn('" radio is off, so this input is disabled. The assignment is kept.</div>"',
                      PAGE)
        self.assertIn('b.checked=radioBusy[kind]?radioWant[kind]:radioOn(kind);', PAGE)
        self.assertIn('.sw input:checked+span{background:var(--acc)}', PAGE)
        self.assertIn("h2.ttl{display:flex;align-items:center;justify-content:space-between", PAGE)
        self.assertIn('document.getElementById("zrb").onchange=function(){setRadio("zigbee")};', PAGE)
        self.assertIn('document.getElementById("hab").onchange=function(){setRadio("home_assistant")}', PAGE)
        self.assertIn('post("set_radio",null,undefined,undefined,"&radio="+kind+"&on="+next)', PAGE)
        self.assertIn('radioSwitch("home_assistant","hab");', PAGE)
        self.assertIn("Home Assistant is not required. D2 stays solid orange while Wi-Fi is up.", PAGE)

    def test_set_inputs_have_action_background_colors(self) -> None:
        self.assertIn('.set-ble{--set-bg:#2f80ed}', PAGE)
        self.assertIn('.set-zigbee{--set-bg:#38a169}', PAGE)
        self.assertIn('.set-ir{--set-bg:#e5b700}', PAGE)
        self.assertIn('.set-voice{--set-bg:#8b5cf6}', PAGE)
        self.assertIn('function setClass(r){var a=r&&r.action;', PAGE)
        self.assertIn('a==="hid"?"set-ble"', PAGE)
        self.assertIn('a==="zigbee"||a==="ir"||a==="voice"', PAGE)
        self.assertIn('body.set-colors .remote .k[class*=set-]', PAGE)
        self.assertNotIn('body.set-colors .assignment-list button[class*=set-]', PAGE)
        self.assertIn('localStorage.getItem("c6.set-colors")', PAGE)
        self.assertIn('document.getElementById("scb").onchange=setColorsToggle;', PAGE)
        self.assertIn('aria-label="Assignment colors"', PAGE)

    def test_assignment_collection_is_removed_and_color_switch_stays(self) -> None:
        self.assertNotIn('<section class="card assignments">', PAGE)
        self.assertNotIn('id="assignmentList"', PAGE)
        self.assertNotIn('id="assignmentSummary"', PAGE)
        self.assertNotIn("function assignmentPaint(){", PAGE)
        self.assertIn('<label class="sw" id="scw">', PAGE)
        self.assertIn('<div class="colorbar"><h2>Assignment colors</h2>', PAGE)
        self.assertIn('id="scb"', PAGE)
        self.assertIn('.colorbar{display:flex;align-items:center;justify-content:center;gap:8px;', PAGE)
        self.assertIn('.remote-pane{background:transparent;border:0;border-radius:0;padding:0;\n'
                      'display:flex;flex-direction:column;align-items:center;gap:8px;width:fit-content;max-width:100%}', PAGE)

    def test_every_radio_line_states_what_is_on_or_off(self) -> None:
        """A line that hides moves the text and the buttons under it, so each one
        is always rendered and always names its own subject."""
        # Only the sleep block hides, because the build and not a state fixes it.
        for card_id in ("wificfg", "zbcfg", "blecfg"):
            card = section(PAGE, f'<section class="card full conn" id="{card_id}">', "</section>")
            card = card.replace('<div id="slpcfg" hidden>', "", 1)
            self.assertNotIn("hidden", card)
        # The switch locks instead of leaving the page while the state is unknown.
        self.assertIn("b.disabled=radioBusy[kind]||!(st&&st.radios)}", PAGE)
        self.assertIn('bf.disabled=bleForgetBusy||!st.ble.bonded;', PAGE)
        line = section(PAGE, "function radioStatus(){", "\n\nfunction setRadio(")
        self.assertIn('e.innerHTML=!known?"<span class=\'dot off\'></span>'
                      'Zigbee radio state is loading.":', line)
        # A radio that is on with no network is neither healthy nor failed, so
        # the dot uses the warning colour instead of the idle grey.
        self.assertIn('"<span class=\'dot "+(on?(zbPaired()?"":"warn"):"bad")+"\'></span>'
                      'Zigbee radio is "+', line)
        self.assertIn(".dot.warn{background:var(--warn)}", PAGE)
        self.assertIn("--warn:#8a5300;", PAGE)
        self.assertIn("--warn:#e0a44a;", PAGE)
        # The remote can be on with no network, so the line names which it is.
        self.assertIn('if(!z.started)return "The stack has not started.";', PAGE)
        self.assertIn('if(z.pairing)return "Pairing.";', PAGE)
        self.assertIn('if(z.paired)return z.reach==="failed"?\n'
                      '"Paired, but the last command to a device was not acknowledged.":\n'
                      '"Paired to a Zigbee network.";', PAGE)
        self.assertIn('return z["new"]?"Not paired.":', PAGE)
        self.assertIn('"Not on the network yet. The remote is rejoining."}', PAGE)
        self.assertIn('(on?"on. "+zbLink():"off. Zigbee buttons are disabled."+zbOffWhy())', PAGE)
        # The remote radio and the browser link are separate subjects.
        self.assertIn('This browser is connected to "+\n"Zigbee2MQTT. "', PAGE)
        # The Bluetooth radio and its host each own a line, and the host line
        # sits above the Forget text. A live flag never survives an off radio.
        self.assertIn('<p class="sub st" id="bst">BLE HID state is loading.</p>\n'
                      '<p class="sub st" id="bhs">Bluetooth host state is loading.</p>\n'
                      '<p class="sub">Forget the saved host', PAGE)
        ble = section(PAGE, "function bleStatus(){", "\n\nfunction forgetBle(")
        self.assertIn('var off=!radioOn("ble"),live=!off&&st.ble.connected;', ble)
        self.assertIn('(off?"off. BLE buttons are disabled.":"on.")', ble)
        self.assertIn('(!st.ble.bonded?("No host bond."+(off?"":st.ble.pairing?" Pairing.":'
                      '" Ready to pair.")):', ble)
        self.assertIn('live?"Connected to "+bleHost()+".":', ble)
        self.assertIn('"Bonded to "+bleHost()+"."+(off?"":" Waiting for the host."))', ble)

    def test_a_forget_works_while_the_bluetooth_radio_is_off(self) -> None:
        """The NimBLE keys are their own NVS namespace, so the stack is not
        needed to read the bond or to drop it."""
        self.assertIn('static const char *const BOND_NAMESPACE = "nimble_bond";', BLE)
        present = section(BLE, "static bool stored_bond_present() {", "\n}")
        self.assertIn("nvs_entry_find(NVS_DEFAULT_PART_NAME, BOND_NAMESPACE, NVS_TYPE_ANY", present)
        self.assertIn("nvs_release_iterator(iterator);", present)
        erase = section(BLE, "static bool erase_stored_bonds() {", "\n}")
        self.assertIn("nvs_open(BOND_NAMESPACE, NVS_READWRITE, &handle)", erase)
        self.assertIn("nvs_erase_all(handle)", erase)
        self.assertIn("nvs_commit(handle)", erase)
        self.assertIn("nvs_close(handle);", erase)
        setup = section(BLE, "void BleHid::setup() {", "\n}")
        self.assertIn("this->bonded_.store(stored_bond_present(), std::memory_order_release);", setup)
        forget = section(BLE, "bool BleHid::forget_bond() {", "\n}")
        self.assertIn("if (!this->stack_ready_) {", forget)
        self.assertIn("const bool erased = erase_stored_bonds();", forget)


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

    def test_the_page_is_stored_as_gzip_data(self) -> None:
        self.assertIn("gzip.compress", INIT)
        self.assertIn("cg.progmem_array", INIT)
        self.assertIn('response->addHeader("Content-Encoding", "gzip")', CPP)
        self.assertNotIn('#include "button_config_page.h"', CPP)


if __name__ == "__main__":
    unittest.main()
