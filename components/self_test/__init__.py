import esphome.codegen as cg
from esphome import pins
from esphome.components import (
    esp32_ble,
    idle_sleep,
    light,
    microphone,
    ota,
    remote_transmitter,
)
import esphome.config_validation as cv
from esphome.const import CONF_ID

DEPENDENCIES = [
    "esp32",
    "esp32_improv",
    "idle_sleep",
    "light",
    "microphone",
    "ota",
    "remote_transmitter",
    "wifi",
]

CONF_LIGHT_ID = "light_id"
CONF_MICROPHONE_ID = "microphone_id"
CONF_TRANSMITTER_ID = "transmitter_id"
CONF_USB_PRESENT_PIN = "usb_present_pin"
CONF_IDLE_SLEEP_ID = "idle_sleep_id"
CONF_SLEEP_BLOCKED_BY = "sleep_blocked_by"

self_test_ns = cg.esphome_ns.namespace("self_test")
SelfTest = self_test_ns.class_("SelfTest", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(SelfTest),
        cv.GenerateID(esp32_ble.CONF_BLE_ID): cv.use_id(esp32_ble.ESP32BLE),
        cv.Required(CONF_IDLE_SLEEP_ID): cv.use_id(idle_sleep.IdleSleep),
        cv.Required(CONF_SLEEP_BLOCKED_BY): cv.returning_lambda,
        cv.Required(CONF_LIGHT_ID): cv.use_id(light.AddressableLightState),
        cv.Required(CONF_MICROPHONE_ID): cv.use_id(microphone.Microphone),
        cv.Required(CONF_TRANSMITTER_ID): cv.use_id(
            remote_transmitter.RemoteTransmitterComponent
        ),
        # Read only when the light has six LEDs, because a V2 board leaves GPIO7 open.
        cv.Required(CONF_USB_PRESENT_PIN): pins.internal_gpio_input_pin_schema,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    ble = await cg.get_variable(config[esp32_ble.CONF_BLE_ID])
    esp32_ble.register_gap_event_handler(ble, var)
    idle = await cg.get_variable(config[CONF_IDLE_SLEEP_ID])
    cg.add(var.set_idle_sleep(idle))
    # The lambda names the blocking condition for the log, or returns nullptr.
    blocked_by = await cg.process_lambda(
        config[CONF_SLEEP_BLOCKED_BY], [], return_type=cg.const_char_ptr
    )
    cg.add(var.set_sleep_blocked_by(blocked_by))

    strip = await cg.get_variable(config[CONF_LIGHT_ID])
    cg.add(var.set_light(strip))
    mic = await cg.get_variable(config[CONF_MICROPHONE_ID])
    cg.add(var.set_microphone(mic))
    transmitter = await cg.get_variable(config[CONF_TRANSMITTER_ID])
    cg.add(var.set_transmitter(transmitter))
    pin = await cg.gpio_pin_expression(config[CONF_USB_PRESENT_PIN])
    cg.add(var.set_usb_present_pin(pin))

    # The install animation draws from the OTA progress callbacks.
    ota.request_ota_state_listeners()
