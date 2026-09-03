import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import esp32
from esphome.components.esp32 import request_bluetooth, request_software_coexistence
from esphome.const import CONF_ID

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
    esp32.add_idf_sdkconfig_option("CONFIG_BT_BLUEDROID_ENABLED", False)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_ENABLED", True)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_HID_SERVICE", True)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_SVC_HID_MAX_INSTANCES", 1)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_SVC_HID_MAX_RPTS", 3)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_MAX_CONNECTIONS", 1)
    # The bond has to survive a reboot, and NimBLE keeps no key without this.
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_NVS_PERSIST", True)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_MAX_BONDS", 1)
    # The central role carries the GATT client that reads the host device name.
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_ROLE_CENTRAL", True)
    esp32.add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_50_FEATURE_SUPPORT", False)
