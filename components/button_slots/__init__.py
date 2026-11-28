import esphome.codegen as cg
import esphome.config_validation as cv

CODEOWNERS = ["@landonr"]

CONFIG_SCHEMA = cv.Schema({})

# Config lambdas call these singletons by name, so main.cpp needs the
# declarations before the first lambda body. ESPHome copies the headers with the
# component, so a config that this repository serves over github:// carries them.
HEADERS = (
    "ir_name.h",
    "ir_learning.h",
    "zigbee_learning.h",
    "hold_actions.h",
)


async def to_code(config):
    for header in HEADERS:
        cg.add_global(
            cg.RawStatement(f'#include "esphome/components/button_slots/{header}"')
        )
