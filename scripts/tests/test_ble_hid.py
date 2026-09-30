"""Regression checks for BLE HID reports and input wiring."""

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[2]
CONFIG = (ROOT / "c6remote.yaml").read_text()
CPP = (ROOT / "components" / "ble_hid" / "ble_hid.cpp").read_text()
HEADER = (ROOT / "components" / "ble_hid" / "ble_hid.h").read_text()
INIT = (ROOT / "components" / "ble_hid" / "__init__.py").read_text()


class BleHidTest(unittest.TestCase):
    def test_component_uses_nimble_without_the_queued_ble_server(self) -> None:
        self.assertIn('CONFIG_BT_NIMBLE_ENABLED", True', INIT)
        self.assertIn('CONFIG_BT_BLUEDROID_ENABLED", False', INIT)
        self.assertIn('CONFIG_BT_NIMBLE_HID_SERVICE", True', INIT)
        self.assertIn("esp_nimble_init", CPP)
        self.assertIn("esp_nimble_enable", CPP)
        self.assertNotIn("bluedroid", CPP)
        self.assertNotIn("esp_ble_gap_", CPP)
        self.assertNotIn("esp_ble_gatts_", CPP)
        self.assertNotIn("esp32_ble", INIT)
        self.assertNotIn("esp32_ble", HEADER)

    def test_the_host_drops_the_observer_role_and_its_log_text(self) -> None:
        """The remote never scans. The GATT client needs only the central role."""
        self.assertIn('CONFIG_BT_NIMBLE_ROLE_OBSERVER", False', INIT)
        self.assertIn('CONFIG_BT_NIMBLE_LOG_LEVEL_NONE", True', INIT)
        self.assertNotIn("ble_gap_disc(", CPP)
        self.assertNotIn("ble_gap_ext_disc(", CPP)
        self.assertNotIn("BLE_GAP_EVENT_DISC:", CPP)
        # Wi-Fi RX on this board fails unless the BT controller is initialised.
        self.assertNotIn("CONFIG_BT_CONTROLLER", INIT)

    def test_the_host_task_starts_after_the_hid_database_is_registered(self) -> None:
        """esp_hidd_dev_init() takes the sync callback, so it must run first."""
        self.assertLess(CPP.index("this->init_hid_();"), CPP.index("esp_nimble_enable("))
        self.assertIn("nimble_port_run();", CPP)
        self.assertIn("nimble_port_freertos_deinit();", CPP)

    def test_report_map_has_keyboard_consumer_and_gamepad_reports(self) -> None:
        self.assertIn("REPORT_KEYBOARD = 1", CPP)
        self.assertIn("REPORT_CONSUMER = 2", CPP)
        self.assertIn("REPORT_GAMEPAD = 3", CPP)
        self.assertIn("0x05, 0x07", CPP)
        self.assertIn("0x05, 0x0C", CPP)
        self.assertIn("0x09, 0x05", CPP)
        self.assertIn("0x29, 0x10", CPP)
        self.assertIn("0x09, 0x39", CPP)

    def test_a_failed_pair_or_second_host_sets_the_pending_flag_for_loop(self) -> None:
        self.assertIn("std::atomic<bool> pair_failed_pending_{false};", HEADER)
        enc = CPP.split("case BLE_GAP_EVENT_ENC_CHANGE:", 1)[1].split("case BLE_GAP_EVENT_REPEAT_PAIRING:", 1)[0]
        failure = enc.split("} else {", 1)[1]
        self.assertIn("pair_failed_pending_.store(true", failure)
        reject = CPP.split('"Rejected a second HID host");', 1)[1].split("return 0;", 1)[0]
        self.assertIn("pair_failed_pending_.store(true", reject)
        loop = CPP.split("void BleHid::loop() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("pair_failed_pending_.exchange(false", loop)
        self.assertIn("this->pair_failed_at_ = millis();", loop)
        self.assertIn("PAIR_FAILED_SHOW_MS = 3000", HEADER)
        forget = CPP.split("bool BleHid::forget_bond() {", 1)[1].split("\n  //", 1)[0]
        self.assertIn("pair_failed_seen_ = false;", forget)

    def test_a_radio_enable_that_cannot_start_the_stack_sets_stack_failed(self) -> None:
        self.assertIn("bool stack_failed() const { return this->stack_failed_ || this->is_failed(); }",
                      HEADER)
        enable = CPP.split("bool BleHid::set_radio_enabled(bool enabled) {", 1)[1].split(
            "this->release_all_();", 1)[0]
        failed = enable.split('"Bluetooth radio could not start");', 1)[1].split("return false;", 1)[0]
        self.assertIn("this->stack_failed_ = true;", failed)
        setup = CPP.split("void BleHid::setup() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("this->stack_failed_ = true;", setup.split("this->mark_failed();", 1)[0])

    def test_assignments_keep_the_existing_slot_range(self) -> None:
        self.assertIn("FIRST_SLOT = 3", HEADER)
        self.assertIn("LAST_SLOT = 20", HEADER)
        self.assertIn("Entry entries[SLOT_COUNT]", HEADER)
        self.assertIn("STORE_VERSION = 1", CPP)
        self.assertIn("record_mutex_", HEADER)
        self.assertIn("lock(this->record_mutex_)", CPP)

    def test_disconnected_actions_are_dropped_and_disconnect_clears_state(self) -> None:
        self.assertIn("if (!this->connected())", CPP)
        self.assertIn("this->active_[index] = false;", CPP)
        self.assertIn("disconnect_pending_.store(true", CPP)
        self.assertIn("this->active_.fill(false);", CPP)

    def test_pressed_slots_are_aggregated(self) -> None:
        self.assertIn("keyboard[0] |= entry.modifiers", CPP)
        self.assertIn("keyboard[1 + entry.usage / 8] |=", CPP)
        self.assertIn("buttons |= static_cast<uint16_t>", CPP)
        self.assertIn("dpad_x += DX[entry.usage]", CPP)
        self.assertIn("dpad_y += DY[entry.usage]", CPP)

    def test_pairing_uses_encryption_and_one_bond(self) -> None:
        self.assertIn("ble_hs_cfg.sm_sc = 1;", CPP)
        self.assertIn("ble_hs_cfg.sm_bonding = 1;", CPP)
        self.assertIn("BLE_SM_IO_CAP_NO_IO", CPP)
        self.assertIn('CONFIG_BT_NIMBLE_MAX_BONDS", 1', INIT)
        self.assertIn('CONFIG_BT_NIMBLE_NVS_PERSIST", True', INIT)
        self.assertIn("Rejected a second HID host", CPP)
        self.assertIn("ble_gap_security_initiate", CPP)
        self.assertIn("BLE_GAP_EVENT_ENC_CHANGE", CPP)
        self.assertIn("BLE_GAP_REPEAT_PAIRING_RETRY", CPP)

    def test_the_saved_host_can_be_forgotten_without_changing_assignments(self) -> None:
        self.assertIn("bool forget_bond();", HEADER)
        self.assertIn("ble_gap_unpair", CPP)
        forget = CPP[CPP.index("bool BleHid::forget_bond()") : CPP.index("bool BleHid::init_stack_()")]
        self.assertNotIn("pref_", forget)
        self.assertNotIn("record_", forget)

    def test_advertising_carries_the_hid_service_and_starts_when_ready(self) -> None:
        self.assertIn("hid_started_.load", CPP)
        self.assertIn("HID_SERVICE_UUID = 0x1812", CPP)
        self.assertIn("fields.uuids16 = &hid_uuid;", CPP)
        self.assertIn("ESP_HID_APPEARANCE_GAMEPAD", CPP)
        self.assertIn("ble_gap_adv_start(BLE_OWN_ADDR_PUBLIC", CPP)
        self.assertIn('ESP_LOGI(TAG, "Advertising as %s", name.data())', CPP)

    def test_the_connected_host_name_comes_from_the_gap_service(self) -> None:
        self.assertIn("DEVICE_NAME_UUID = 0x2A00", CPP)
        self.assertIn("ble_gattc_read_by_uuid(connection, 1, 0xFFFF, &name_uuid.u", CPP)
        self.assertIn('CONFIG_BT_NIMBLE_ROLE_CENTRAL", True', INIT)
        self.assertNotIn('CONFIG_BT_NIMBLE_GATT_CLIENT", False', INIT)
        self.assertIn("std::string host_name() const;", HEADER)
        self.assertIn('ESP_LOGI(TAG, "Connected to %s", name)', CPP)
        # The name belongs to the bond, so it survives a dropped link and a
        # reboot. The page reads connected() to say which of the two it shows.
        disconnect = CPP[CPP.index("case BLE_GAP_EVENT_DISCONNECT:") :]
        self.assertNotIn("this->set_host_name_(nullptr);", disconnect)
        self.assertIn("self->host_save_pending_.store(true, std::memory_order_release);", CPP)
        self.assertIn("make_preference<std::array<char, HOST_NAME_SIZE>>(HOST_STORE_KEY, true)", CPP)
        # Only a forget drops the stored name, with the radio on or off.
        forget = CPP[CPP.index("bool BleHid::forget_bond() {") :]
        self.assertIn("this->set_host_name_(nullptr);", forget)

    def test_wheels_tap_and_buttons_release_by_slot(self) -> None:
        self.assertIn("ir_ui.tap(17, IrUi::Tap::ARM_ONLY);", CONFIG)
        self.assertIn("ir_ui.tap(18, IrUi::Tap::ARM_ONLY);", CONFIG)
        self.assertIn("hid_play_callback_(button, false)", (ROOT / "ir_learning.h").read_text())
        for slot in [slot for slot in range(3, 17) if slot != 9] + [19]:
            self.assertIn(f"slot: {slot}", CONFIG)
        sw9 = CONFIG.split("    name: Button 9\n", 1)[1].split("    name: Button 10\n", 1)[0]
        self.assertIn("ir_ui.tap(9, IrUi::Tap::FULL);", sw9)
        self.assertIn("ir_ui.release(9);", sw9)
        self.assertIn("set_pressed(20, true)", CONFIG)
        self.assertIn("set_pressed(20, false)", CONFIG)

    @staticmethod
    def body(start: str) -> str:
        """Return the function that opens with start, up to its closing brace."""
        text = CPP[CPP.index(start) :]
        return text[: text.index("\n}")]

    def test_the_device_name_is_the_friendly_name(self) -> None:
        """The BLE name follows the friendly name, so the source names no remote."""
        self.assertNotIn("homeThing C6", CPP)
        self.assertNotIn("DEVICE_NAME =", CPP)
        self.assertIn(".device_name = nullptr,", CPP)
        self.assertIn("static constexpr size_t DEVICE_NAME_MAX = 40;", HEADER)
        self.assertIn("void set_device_name(const char *name);", HEADER)
        # A boot without a saved name starts with the YAML friendly name.
        init = self.body("bool BleHid::init_stack_() {")
        seed = init.index("const StringRef &friendly = App.get_friendly_name();")
        self.assertIn("if (this->copy_device_name_(name) == 0) {", init)
        self.assertLess(seed, init.index("this->init_hid_();"))
        self.assertLess(seed, init.index("ble_svc_gap_device_name_set(name.data());"))
        self.assertLess(CPP.index("App.get_friendly_name()"), CPP.index("esp_hidd_dev_init("))
        hid = self.body("void BleHid::init_hid_() {")
        self.assertLess(hid.index("config.device_name = name.data();"), hid.index("esp_hidd_dev_init(&config,"))
        self.assertIn('ESP_LOGCONFIG(TAG, "  Name: %s", name.data());', CPP)

    def test_the_name_copy_is_guarded_for_the_nimble_task(self) -> None:
        self.assertIn("mutable std::mutex device_name_mutex_;", HEADER)
        self.assertIn("using DeviceName = std::array<char, DEVICE_NAME_MAX + 1>;", HEADER)
        self.assertIn("DeviceName device_name_{};", HEADER)
        lock = "const std::lock_guard<std::mutex> lock(this->device_name_mutex_);"
        for start in ("void BleHid::store_device_name_(const char *name, size_t length) {",
                      "uint32_t BleHid::copy_device_name_(DeviceName &name) const {",
                      "bool BleHid::device_name_current_(uint32_t generation) const {"):
            self.assertIn(lock, self.body(start), start)
        store = self.body("void BleHid::store_device_name_(const char *name, size_t length) {")
        self.assertIn("utf8_prefix_length(name, length, DEVICE_NAME_MAX)", store)
        self.assertIn("this->device_name_generation_++;", store)
        # The advert and the loop read the name only through the locked copy.
        for start in ("void BleHid::start_advertising_() {", "void BleHid::apply_device_name_() {"):
            self.assertIn("this->copy_device_name_(name);", self.body(start), start)
            self.assertNotIn("this->device_name_.", self.body(start), start)

    def test_a_rename_restarts_a_running_advert_from_the_loop(self) -> None:
        setter = self.body("void BleHid::set_device_name(const char *name) {")
        self.assertIn("if (this->stack_ready_)\n    this->name_update_pending_.store(true", setter)
        self.assertNotIn("ble_gap_", setter)
        loop = self.body("void BleHid::loop() {")
        self.assertIn("if (this->name_update_pending_.exchange(false, std::memory_order_acq_rel))\n"
                      "    this->apply_device_name_();", loop)
        apply = self.body("void BleHid::apply_device_name_() {")
        gap = apply.index("ble_svc_gap_device_name_set(name.data());")
        # A connected host keeps its link, and only the GAP name changes.
        self.assertLess(gap, apply.index("this->link_connected_.load("))
        self.assertLess(apply.index("this->link_connected_.load("), apply.index("ble_gap_adv_stop();"))
        self.assertIn("if (stopped != BLE_HS_EALREADY)", apply)
        self.assertLess(apply.index("ble_gap_adv_stop();"), apply.index("this->start_advertising_();"))
        self.assertNotIn("ble_gap_terminate", apply)
        start = self.body("void BleHid::start_advertising_() {")
        # One caller claims the advert at a time, and a failed start gives it back.
        self.assertIn("this->advertising_.compare_exchange_strong(idle, true, std::memory_order_acq_rel)", start)
        self.assertNotIn("this->advertising_.store(true", start)
        self.assertIn("if (result != 0 && result != BLE_HS_EALREADY) {", start)
        self.assertIn("const uint32_t generation = this->copy_device_name_(name);", start)
        self.assertIn("if (!this->device_name_current_(generation))\n"
                      "    this->name_update_pending_.store(true, std::memory_order_release);", start)

    def test_the_name_fits_the_advert_and_the_scan_response(self) -> None:
        start = self.body("void BleHid::start_advertising_() {")
        # The advert measures its other fields, then gives the name the rest.
        measure = start.index("ble_hs_adv_set_fields(&fields, encoded, &used, sizeof(encoded));")
        self.assertLess(measure, start.index("fields.name = name_bytes;"))
        self.assertIn("BLE_HS_ADV_MAX_FIELD_SZ - used", start)
        self.assertIn("fields.name_is_complete = advert_length == name_length ? 1 : 0;", start)
        self.assertLess(start.index("fields.name = name_bytes;"), start.index("ble_gap_adv_set_fields(&fields);"))
        self.assertIn("utf8_prefix_length(name.data(), name_length, BLE_HS_ADV_MAX_FIELD_SZ)", start)
        self.assertIn("response.name_is_complete = response_length == name_length ? 1 : 0;", start)
        self.assertLess(start.index("ble_gap_adv_rsp_set_fields(&response);"), start.index("ble_gap_adv_start("))
        self.assertNotIn("name_is_complete = 1;", CPP)
        cut = self.body("static size_t utf8_prefix_length(const char *text, size_t length, size_t limit) {")
        self.assertIn("while (cut > 0 && (static_cast<uint8_t>(text[cut]) & 0xC0) == 0x80)\n    cut--;", cut)

    def test_the_gap_name_limit_holds_a_whole_friendly_name(self) -> None:
        """ESP-IDF defaults the GAP name limit to 31 bytes, and a rename can take 40."""
        self.assertIn('CONFIG_BT_NIMBLE_GAP_DEVICE_NAME_MAX_LEN", 40', INIT)
        self.assertIn("static_assert(BleHid::DEVICE_NAME_MAX <= CONFIG_BT_NIMBLE_GAP_DEVICE_NAME_MAX_LEN,", CPP)


if __name__ == "__main__":
    unittest.main()
