import gzip
from pathlib import Path
import re
import subprocess
from urllib.parse import quote_from_bytes

from esphome import automation
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import ha_action, idle_sleep, sensor, web_server_base
from esphome.components.web_server_base import CONF_WEB_SERVER_BASE_ID
from esphome.const import CONF_ID, CONF_RAW_DATA_ID, CONF_TRIGGER_ID
from esphome.core import HexInt

AUTO_LOAD = ["web_server_base"]
DEPENDENCIES = ["network"]

CONF_IDLE_SLEEP_ID = "idle_sleep_id"
CONF_HA_ACTION_ID = "ha_action_id"
CONF_BATTERY_LEVEL_ID = "battery_level_id"
CONF_BATTERY_VOLTAGE_ID = "battery_voltage_id"
CONF_ON_STATUS_LEDS = "on_status_leds"

button_config_ns = cg.esphome_ns.namespace("button_config")
ButtonConfig = button_config_ns.class_("ButtonConfig", cg.Component)
StatusLedsTrigger = button_config_ns.class_("StatusLedsTrigger", automation.Trigger.template(bool))


def _consume_page_sockets(config):
    from esphome.components import socket

    # No web_server reserves page sockets. 7 is httpd max_open_sockets, so LRU purge beats ENFILE.
    socket.consume_sockets(7, "button_config")(config)
    # httpd's UDP control socket pair, which web_server_base does not register.
    socket.consume_sockets(2, "button_config", socket.SocketType.UDP)(config)
    return config


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(ButtonConfig),
            cv.GenerateID(CONF_WEB_SERVER_BASE_ID): cv.use_id(web_server_base.WebServerBase),
            cv.GenerateID(CONF_RAW_DATA_ID): cv.declare_id(cg.uint8),
            # The import alone does not load idle_sleep, so production builds without it.
            cv.Optional(CONF_IDLE_SLEEP_ID): cv.use_id(idle_sleep.IdleSleep),
            cv.Optional(CONF_HA_ACTION_ID): cv.use_id(ha_action.HaAction),
            cv.Inclusive(CONF_BATTERY_LEVEL_ID, "battery"): cv.use_id(sensor.Sensor),
            cv.Inclusive(CONF_BATTERY_VOLTAGE_ID, "battery"): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_ON_STATUS_LEDS): automation.validate_automation(
                {cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(StatusLedsTrigger)}
            ),
        }
    ).extend(cv.COMPONENT_SCHEMA),
    _consume_page_sockets,
)


# PATCH counts commits from this commit on, so this commit is 2026.10.0.
VERSION_BASE = "dc560eec464c05707991582992bff0d27b0d960b"


def firmware_version():
    """Return YYYY.M.PATCH, plus -dirty for uncommitted tracked changes."""
    root = Path(__file__).parents[2]
    base = VERSION_BASE

    def git(*args):
        out = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=10, check=True
        )
        return out.stdout.strip()

    try:
        git("merge-base", "--is-ancestor", base, "HEAD")
        head = git("log", "-1", "--format=%cI", "HEAD")
        # --not base^@ also works when the base is a root commit.
        dates = git("log", "--format=%cI", "HEAD", "--not", base + "^@").splitlines()
        dirty = git("status", "--porcelain", "--untracked-files=no")
        year, month = (int(part) for part in head[:7].split("-"))
    except (OSError, ValueError, subprocess.SubprocessError):
        return "unknown"
    patch = sum(1 for date in dates if date[:7] == head[:7]) - 1
    if patch < 0:
        return "unknown"
    return f"{year}.{month}.{patch}" + ("-dirty" if dirty else "")


async def to_code(config):
    paren = await cg.get_variable(config[CONF_WEB_SERVER_BASE_ID])
    var = cg.new_Pvariable(config[CONF_ID], paren)
    await cg.register_component(var, config)
    # A setter, not a define, so a new commit rebuilds only the generated main.cpp.
    cg.add(var.set_firmware_version(firmware_version()))

    # A build without idle_sleep has no idle_sleep.h, so the C++ side is behind this define.
    if CONF_IDLE_SLEEP_ID in config:
        sleep = await cg.get_variable(config[CONF_IDLE_SLEEP_ID])
        cg.add(var.set_idle_sleep(sleep))
        cg.add_define("USE_BUTTON_CONFIG_IDLE_SLEEP")

    # A build without ha_action has no ha_action.h, so the C++ side is behind this define.
    if CONF_HA_ACTION_ID in config:
        actions = await cg.get_variable(config[CONF_HA_ACTION_ID])
        cg.add(var.set_ha_action(actions))
        cg.add_define("USE_BUTTON_CONFIG_HA_ACTION")

    # Bench configs have no battery sensors, so the C++ side is behind this define.
    if CONF_BATTERY_LEVEL_ID in config:
        level = await cg.get_variable(config[CONF_BATTERY_LEVEL_ID])
        volts = await cg.get_variable(config[CONF_BATTERY_VOLTAGE_ID])
        cg.add(var.set_battery(level, volts))
        cg.add_define("USE_BUTTON_CONFIG_BATTERY")

    for conf in config.get(CONF_ON_STATUS_LEDS, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        await automation.build_automation(trigger, [(bool, "enabled")], conf)

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
