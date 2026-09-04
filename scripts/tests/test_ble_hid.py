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
        self.assertIn('ESP_LOGI(TAG, "Advertising as homeThing C6")', CPP)

    def test_the_connected_host_name_comes_from_the_gap_service(self) -> None:
        self.assertIn("DEVICE_NAME_UUID = 0x2A00", CPP)
        self.assertIn("ble_gattc_read_by_uuid(connection, 1, 0xFFFF, &name_uuid.u", CPP)
        self.assertIn('CONFIG_BT_NIMBLE_ROLE_CENTRAL", True', INIT)
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
        for slot in list(range(3, 17)) + [20]:
            self.assertIn(f"slot: {slot}", CONFIG)
        self.assertIn("set_pressed(19, true)", CONFIG)
        self.assertIn("set_pressed(19, false)", CONFIG)


if __name__ == "__main__":
    unittest.main()
