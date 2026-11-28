"""Improv over BLE on the NimBLE server that ble_hid runs.

The ESPHome component of this name needs Bluedroid, and the remote cannot have
it, because the BLE keyboard needs NimBLE and only one host can run at a time.
This component takes the same key, so the configuration reads as the Made for
ESPHome checklist asks.
"""

import esphome.codegen as cg
from esphome.components import binary_sensor, improv_base
import esphome.config_validation as cv
from esphome.const import CONF_ID

AUTO_LOAD = ["improv_base"]
DEPENDENCIES = ["ble_hid", "wifi"]

CONF_AUTHORIZER = "authorizer"
CONF_AUTHORIZED_DURATION = "authorized_duration"
CONF_WIFI_TIMEOUT = "wifi_timeout"

improv_ble_ns = cg.esphome_ns.namespace("improv_ble")
ImprovBle = improv_ble_ns.class_("ImprovBle", cg.Component)

CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(ImprovBle),
            cv.Optional(CONF_AUTHORIZER): cv.Any(
                cv.none, cv.use_id(binary_sensor.BinarySensor)
            ),
            cv.Optional(
                CONF_AUTHORIZED_DURATION, default="1min"
            ): cv.positive_time_period_milliseconds,
            cv.Optional(
                CONF_WIFI_TIMEOUT, default="30s"
            ): cv.positive_time_period_milliseconds,
        }
    )
    .extend(improv_base.IMPROV_SCHEMA)
    .extend(cv.COMPONENT_SCHEMA)
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    if authorizer := config.get(CONF_AUTHORIZER):
        sensor = await cg.get_variable(authorizer)
        cg.add(var.set_authorizer(sensor))
    cg.add(var.set_authorized_duration(config[CONF_AUTHORIZED_DURATION]))
    cg.add(var.set_wifi_timeout(config[CONF_WIFI_TIMEOUT]))

    await improv_base.setup_improv_core(var, config)
