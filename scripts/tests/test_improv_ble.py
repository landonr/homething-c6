"""Static checks for Improv over BLE on the NimBLE server."""

from pathlib import Path
import re
import unittest

from scripts.tests.yaml_blocks import top_level_block


ROOT = Path(__file__).parents[2]
COMPONENT = ROOT / "components" / "improv_ble"
CPP = (COMPONENT / "improv_ble.cpp").read_text()
HEADER = (COMPONENT / "improv_ble.h").read_text()
INIT = (COMPONENT / "__init__.py").read_text()
CONFIG = (ROOT / "c6remote.yaml").read_text()
HID_CPP = (ROOT / "components" / "ble_hid" / "ble_hid.cpp").read_text()

# The Improv BLE standard. Every characteristic shares it but the last byte.
SERVICE_UUID = "00467768-6228-2272-4663-277478268000"


def little_endian(uuid: str) -> list[int]:
    """A 128-bit UUID goes on air in reverse byte order."""
    return list(reversed(bytes.fromhex(uuid.replace("-", ""))))


def macro_tail() -> list[int]:
    """The fixed bytes of the IMPROV_UUID macro, after its one argument."""
    match = re.search(r"BLE_UUID128_INIT\(\(last\),([^)]*)\)", CPP)
    if match is None:
        raise AssertionError("no IMPROV_UUID macro")
    return [int(byte, 16) for byte in match.group(1).split(",")]


class UuidTest(unittest.TestCase):
    """A wrong byte order still builds, and no installer ever finds the remote."""

    def test_the_macro_holds_the_service_uuid_in_reverse(self) -> None:
        self.assertEqual(macro_tail(), little_endian(SERVICE_UUID)[1:])

    def test_each_characteristic_takes_its_own_last_byte(self) -> None:
        # The argument is the first byte on air, which is the last of the UUID.
        for name, last in (("SERVICE", 0x00), ("STATE", 0x01), ("ERROR", 0x02),
                           ("RPC_COMMAND", 0x03), ("RPC_RESULT", 0x04), ("CAPABILITIES", 0x05)):
            with self.subTest(uuid=name):
                self.assertIn(f"{name}_UUID = IMPROV_UUID(0x{last:02X})", CPP)
        self.assertEqual(little_endian(SERVICE_UUID)[0], 0x00)


class ServiceTest(unittest.TestCase):
    def test_the_service_registers_before_any_setup(self) -> None:
        """NimBLE closes the database before the host task starts, so the
        constructor is the only place early enough."""
        constructor = CPP.split("ImprovBle::ImprovBle() {", 1)[1].split("}", 1)[0]
        self.assertIn("ble_hid::BleHid::add_gatt_services(IMPROV_SERVICES)", constructor)
        self.assertNotIn("add_gatt_services", CPP.split("void ImprovBle::setup()", 1)[1][:400])

    def test_the_host_adds_the_services_while_the_database_is_open(self) -> None:
        init = HID_CPP.split("bool BleHid::init_stack_() {", 1)[1].split("\nvoid BleHid::", 1)[0]
        self.assertLess(init.index("this->init_hid_();"), init.index("ble_gatts_add_svcs"))
        self.assertLess(init.index("ble_gatts_add_svcs"), init.index("esp_nimble_enable"))

    def test_the_characteristics_carry_the_improv_flags(self) -> None:
        for uuid, flags in (("STATE", "BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY"),
                            ("ERROR", "BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY"),
                            ("RPC_RESULT", "BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY"),
                            ("RPC_COMMAND", "BLE_GATT_CHR_F_WRITE"),
                            ("CAPABILITIES", "BLE_GATT_CHR_F_READ")):
            entry = CPP.split(f"&{uuid}_UUID.u,", 1)[1].split("},", 1)[0]
            with self.subTest(uuid=uuid):
                self.assertIn(f".flags = {flags},", entry)

    def test_only_the_notifying_characteristics_keep_a_handle(self) -> None:
        for uuid in ("STATE", "ERROR", "RPC_RESULT"):
            entry = CPP.split(f"&{uuid}_UUID.u,", 1)[1].split("},", 1)[0]
            with self.subTest(uuid=uuid):
                self.assertIn(".val_handle = &", entry)


class ConfigTest(unittest.TestCase):
    def test_the_config_uses_the_key_the_checklist_names(self) -> None:
        """Made for ESPHome asks that the configuration contains improv_ble."""
        self.assertRegex(CONFIG, r"(?m)^improv_ble:$")
        self.assertRegex(top_level_block(CONFIG, "improv_ble"), r"(?m)^  id: \w+$")

    def test_the_component_takes_the_esphome_key(self) -> None:
        self.assertEqual(COMPONENT.name, "improv_ble")
        self.assertIn('AUTO_LOAD = ["improv_base"]', INIT)
        self.assertIn('DEPENDENCIES = ["ble_hid", "wifi"]', INIT)

    def test_the_remote_keeps_serial_improv_as_well(self) -> None:
        """The checklist asks for both when the device has a USB port."""
        self.assertRegex(CONFIG, r"(?m)^improv_serial:$")


class StateTest(unittest.TestCase):
    def test_settings_need_authorization_first(self) -> None:
        settings = CPP.split("case improv::WIFI_SETTINGS: {", 1)[1].split("case improv::", 1)[0]
        self.assertIn("if (this->state_ != improv::STATE_AUTHORIZED)", settings)
        self.assertIn("improv::ERROR_NOT_AUTHORIZED", settings)

    def test_a_network_that_never_answers_ends_the_attempt(self) -> None:
        self.assertIn("now - this->provisioning_start_ > this->wifi_timeout_", CPP)
        timeout = CPP.split("void ImprovBle::on_wifi_timeout_() {", 1)[1].split("\n}", 1)[0]
        self.assertIn("improv::ERROR_UNABLE_TO_CONNECT", timeout)
        self.assertIn("clear_sta()", timeout)

    def test_the_uuid_leaves_the_advert_once_the_remote_has_a_network(self) -> None:
        stop = CPP.split("void ImprovBle::stop_() {", 1)[1].split("\n}", 1)[0]
        self.assertIn("set_extra_service_uuid(nullptr)", stop)
        self.assertIn("refresh_advertising()", stop)
