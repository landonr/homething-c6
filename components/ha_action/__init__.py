import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

DEPENDENCIES = ["api", "wifi"]

ha_action_ns = cg.esphome_ns.namespace("ha_action")
HaAction = ha_action_ns.class_("HaAction", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(HaAction),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    # The API sends an action request only when these are defined. Nothing else
    # in the API codegen reads them.
    cg.add_define("USE_API_HOMEASSISTANT_SERVICES")
    cg.add_define("USE_API_HOMEASSISTANT_ACTION_RESPONSES")
