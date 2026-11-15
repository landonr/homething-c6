import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import esp32
from esphome.components.esp32 import (
    include_builtin_idf_component,
    request_bluetooth,
    request_software_coexistence,
)
from esphome.const import CONF_ID

AUTO_LOAD = ["button_slots"]
DEPENDENCIES = ["esp32"]

ble_hid_ns = cg.esphome_ns.namespace("ble_hid")
BleHid = ble_hid_ns.class_("BleHid", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(BleHid),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    request_bluetooth()
    request_software_coexistence()
    # ESPHome leaves esp_hid out of the build from 2026.10.0, because it
    # implements no HID of its own. This component is the HID.
    include_builtin_idf_component("esp_hid")
    esp32.add_idf_sdkconfig_option("CONFIG_BT_BLUEDROID_ENABLED", False)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_ENABLED", True)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_HID_SERVICE", True)
    # The GAP name is the friendly name, which holds up to 40 bytes. The default limit is 31.
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_GAP_DEVICE_NAME_MAX_LEN", 40)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_SVC_HID_MAX_INSTANCES", 1)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_SVC_HID_MAX_RPTS", 3)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_MAX_CONNECTIONS", 1)
    # The bond has to survive a reboot, and NimBLE keeps no key without this.
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_NVS_PERSIST", True)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_MAX_BONDS", 1)
    # The remote is a HID peripheral. It starts no connection and reads nothing
    # from the host, so the central role takes the GATT client out with it.
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_ROLE_CENTRAL", False)
    # Nothing scans either.
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_ROLE_OBSERVER", False)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_LOG_LEVEL_NONE", True)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_50_FEATURE_SUPPORT", False)
