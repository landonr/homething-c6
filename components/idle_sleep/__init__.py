import esphome.codegen as cg
from esphome import pins
from esphome.components import i2c
from esphome.components.esp32 import add_idf_sdkconfig_option
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_NUMBER, CONF_PIN, CONF_PLATFORM
from esphome.core import CORE
import esphome.final_validate as fv

DEPENDENCIES = ["esp32", "i2c"]

CONF_SLEEP_AFTER = "sleep_after"
CONF_COLD_BOOT_GRACE = "cold_boot_grace"
CONF_SLEEP_HOLD_BIT = "sleep_hold_bit"
CONF_SLEEP_HOLD_TIME = "sleep_hold_time"
CONF_WAKE_STUB = "wake_stub"
CONF_BOOT_TRIM = "boot_trim"
CONF_LINK_PROBE = "link_probe"
CONF_BLOCK_PROBE = "block_probe"
CONF_REPLAY = "replay"

WAKE_PIN = 5
# Same range as IdleSleep::set_sleep_after_s().
MIN_SLEEP_AFTER = cv.TimePeriod(seconds=10)
MAX_SLEEP_AFTER = cv.TimePeriod(seconds=3600)

idle_sleep_ns = cg.esphome_ns.namespace("idle_sleep")
IdleSleep = idle_sleep_ns.class_("IdleSleep", cg.Component, i2c.I2CDevice)

CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(IdleSleep),
            cv.Optional(CONF_SLEEP_AFTER, default="5min"): cv.All(
                cv.positive_time_period_seconds,
                cv.Range(min=MIN_SLEEP_AFTER, max=MAX_SLEEP_AFTER),
            ),
            cv.Optional(
                CONF_COLD_BOOT_GRACE, default="60s"
            ): cv.positive_time_period_milliseconds,
            cv.Optional(CONF_SLEEP_HOLD_BIT): cv.int_range(min=0, max=15),
            cv.Optional(
                CONF_SLEEP_HOLD_TIME, default="2s"
            ): cv.positive_time_period_milliseconds,
            cv.Optional(CONF_WAKE_STUB, default=True): cv.boolean,
            cv.Optional(CONF_BOOT_TRIM, default=False): cv.boolean,
            cv.Optional(CONF_LINK_PROBE): cv.returning_lambda,
            cv.Optional(CONF_BLOCK_PROBE): cv.returning_lambda,
            cv.Optional(CONF_REPLAY): cv.returning_lambda,
        }
    )
    .extend(cv.COMPONENT_SCHEMA)
    .extend(i2c.i2c_device_schema(0x20)),
    cv.only_on_esp32,
)


def _final_validate(config):
    # IDF keeps one ISR handler for each pin, so an interrupt-mode GPIO5 binary
    # sensor and the IdleSleep edge ISR would replace each other.
    for sensor in fv.full_config.get().get("binary_sensor", []):
        pin = sensor.get(CONF_PIN)
        if (
            sensor.get(CONF_PLATFORM) == "gpio"
            and sensor.get("use_interrupt", False)
            and isinstance(pin, dict)
            and pins.PIN_SCHEMA_REGISTRY.get_key(pin) == CORE.target_platform
            and pin.get(CONF_NUMBER) == WAKE_PIN
        ):
            raise cv.Invalid(
                f"idle_sleep owns the GPIO{WAKE_PIN} interrupt. "
                f"Set use_interrupt: false on binary_sensor {sensor.get(CONF_ID)}."
            )
    return config


FINAL_VALIDATE_SCHEMA = _final_validate


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await i2c.register_i2c_device(var, config)

    cg.add(var.set_default_sleep_after_s(config[CONF_SLEEP_AFTER].total_seconds))
    cg.add(var.set_cold_boot_grace(config[CONF_COLD_BOOT_GRACE]))
    if CONF_SLEEP_HOLD_BIT in config:
        cg.add(var.set_sleep_hold_bit(config[CONF_SLEEP_HOLD_BIT]))
    cg.add(var.set_sleep_hold_time(config[CONF_SLEEP_HOLD_TIME]))

    if config[CONF_WAKE_STUB]:
        cg.add_define("USE_IDLE_SLEEP_WAKE_STUB")

    if config[CONF_BOOT_TRIM]:
        add_idf_sdkconfig_option("CONFIG_BOOTLOADER_SKIP_VALIDATE_IN_DEEP_SLEEP", True)
        add_idf_sdkconfig_option("CONFIG_BOOTLOADER_LOG_LEVEL_WARN", True)

    if CONF_LINK_PROBE in config:
        probe = await cg.process_lambda(
            config[CONF_LINK_PROBE], [], return_type=cg.bool_
        )
        cg.add(var.set_link_probe(probe))
    if CONF_BLOCK_PROBE in config:
        probe = await cg.process_lambda(
            config[CONF_BLOCK_PROBE], [], return_type=cg.bool_
        )
        cg.add(var.set_block_probe(probe))
    if CONF_REPLAY in config:
        replay = await cg.process_lambda(
            config[CONF_REPLAY],
            [(cg.uint8, "bit"), (cg.bool_, "held")],
            return_type=cg.bool_,
        )
        cg.add(var.set_replay(replay))
