import gzip
from pathlib import Path
import re
from urllib.parse import quote_from_bytes

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import idle_sleep, web_server_base
from esphome.components.web_server_base import CONF_WEB_SERVER_BASE_ID
from esphome.const import CONF_ID, CONF_RAW_DATA_ID
from esphome.core import HexInt

AUTO_LOAD = ["web_server_base"]
DEPENDENCIES = ["network"]

CONF_IDLE_SLEEP_ID = "idle_sleep_id"

button_config_ns = cg.esphome_ns.namespace("button_config")
ButtonConfig = button_config_ns.class_("ButtonConfig", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(ButtonConfig),
        cv.GenerateID(CONF_WEB_SERVER_BASE_ID): cv.use_id(web_server_base.WebServerBase),
        cv.GenerateID(CONF_RAW_DATA_ID): cv.declare_id(cg.uint8),
        # The import alone does not load idle_sleep, so production builds without it.
        cv.Optional(CONF_IDLE_SLEEP_ID): cv.use_id(idle_sleep.IdleSleep),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    paren = await cg.get_variable(config[CONF_WEB_SERVER_BASE_ID])
    var = cg.new_Pvariable(config[CONF_ID], paren)
    await cg.register_component(var, config)

    # A build without idle_sleep has no idle_sleep.h, so the C++ side is behind this define.
    if CONF_IDLE_SLEEP_ID in config:
        sleep = await cg.get_variable(config[CONF_IDLE_SLEEP_ID])
        cg.add(var.set_idle_sleep(sleep))
        cg.add_define("USE_BUTTON_CONFIG_IDLE_SLEEP")

    source = (Path(__file__).parent / "button_config_page.h").read_text()
    match = re.search(r'R"=====\((.*)\)=====";', source, re.DOTALL)
    if match is None:
        raise cv.Invalid("button_config_page.h has no PAGE_HTML value")
    svg_path = Path(__file__).parents[2] / "docs" / "readme-assets" / "case-front-face.svg"
    svg = quote_from_bytes(svg_path.read_bytes(), safe="/,:;=(){}@.-_")
    html = match.group(1).replace("__CASE_FRONT_FACE_SVG__", svg)
    page = gzip.compress(html.encode(), compresslevel=9, mtime=0)
    data = cg.progmem_array(config[CONF_RAW_DATA_ID], [HexInt(value) for value in page])
    cg.add(var.set_page(data, len(page)))
