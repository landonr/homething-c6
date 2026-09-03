import gzip
from pathlib import Path
import re

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import web_server_base
from esphome.components.web_server_base import CONF_WEB_SERVER_BASE_ID
from esphome.const import CONF_ID, CONF_RAW_DATA_ID
from esphome.core import HexInt

AUTO_LOAD = ["web_server_base"]
DEPENDENCIES = ["network"]

button_config_ns = cg.esphome_ns.namespace("button_config")
ButtonConfig = button_config_ns.class_("ButtonConfig", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(ButtonConfig),
        cv.GenerateID(CONF_WEB_SERVER_BASE_ID): cv.use_id(web_server_base.WebServerBase),
        cv.GenerateID(CONF_RAW_DATA_ID): cv.declare_id(cg.uint8),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    paren = await cg.get_variable(config[CONF_WEB_SERVER_BASE_ID])
    var = cg.new_Pvariable(config[CONF_ID], paren)
    await cg.register_component(var, config)

    source = (Path(__file__).parent / "button_config_page.h").read_text()
    match = re.search(r'R"=====\((.*)\)=====";', source, re.DOTALL)
    if match is None:
        raise cv.Invalid("button_config_page.h has no PAGE_HTML value")
    page = gzip.compress(match.group(1).encode(), compresslevel=9, mtime=0)
    data = cg.progmem_array(config[CONF_RAW_DATA_ID], [HexInt(value) for value in page])
    cg.add(var.set_page(data, len(page)))
