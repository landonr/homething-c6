import gzip
from pathlib import Path
import subprocess

from esphome import automation
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import ha_action, idle_sleep, sensor, web_server_base
from esphome.components.web_server_base import CONF_WEB_SERVER_BASE_ID
from esphome.const import CONF_ID, CONF_RAW_DATA_ID, CONF_TRIGGER_ID
from esphome.core import HexInt

from .shell_build import (APP, BUNDLE_DIR, CURRENT_LOADER, SIGNATURE, loader_name, page,
                          shell_html)

AUTO_LOAD = ["web_server_base", "button_slots"]
DEPENDENCIES = ["network"]

CONF_IDLE_SLEEP_ID = "idle_sleep_id"
CONF_HA_ACTION_ID = "ha_action_id"
CONF_BATTERY_LEVEL_ID = "battery_level_id"
CONF_BATTERY_VOLTAGE_ID = "battery_voltage_id"
CONF_ON_STATUS_LEDS = "on_status_leds"
CONF_PAGE = "page"
# "hosted" keeps the interface on the website, which saves about 35 KB of
# flash. "embedded" keeps it in flash, so a fork needs no website and no
# signing key. See "The device shell and the website bundle" in AGENTS.md.
PAGE_HOSTED = "hosted"
PAGE_EMBEDDED = "embedded"

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
            cv.Optional(CONF_PAGE, default=PAGE_HOSTED): cv.one_of(
                PAGE_HOSTED, PAGE_EMBEDDED, lower=True),
            cv.Optional(CONF_ON_STATUS_LEDS): automation.validate_automation(
                {cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(StatusLedsTrigger)}
            ),
        }
    ).extend(cv.COMPONENT_SCHEMA),
    _consume_page_sockets,
)


# PATCH counts commits from this commit on, so this commit is 2026.10.0.
VERSION_BASE = "dc560eec464c05707991582992bff0d27b0d960b"


def _git(root, *args):
    out = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, timeout=10, check=True
    )
    return out.stdout.strip()


def source_ref():
    """Return the ref and the commit that an adopted build was built from.

    ESPHome clones an external source with `--depth=1`, so the clone holds one
    commit and no history to count a patch in. The ref alone is the same string
    on every unit, so the short commit of the clone goes with it.
    """
    try:
        from esphome.components.external_components import get_sources
    except ImportError:
        return "unknown"
    here = Path(__file__).resolve()
    for source in get_sources():
        if not source.ref or not here.is_relative_to(Path(source.components_dir).resolve()):
            continue
        try:
            short = _git(Path(__file__).parents[2], "rev-parse", "--short", "HEAD")
        except (OSError, subprocess.SubprocessError):
            return source.ref
        return f"{source.ref}@{short}" if short else source.ref
    return "unknown"


def firmware_version():
    """Return YYYY.M.PATCH, plus -dirty for uncommitted tracked changes.

    A build that has no history to count falls back to the source ref.
    """
    root = Path(__file__).parents[2]
    base = VERSION_BASE

    def git(*args):
        return _git(root, *args)

    try:
        git("merge-base", "--is-ancestor", base, "HEAD")
        head = git("log", "-1", "--format=%cI", "HEAD")
        # --not base^@ also works when the base is a root commit.
        dates = git("log", "--format=%cI", "HEAD", "--not", base + "^@").splitlines()
        dirty = git("status", "--porcelain", "--untracked-files=no")
        year, month = (int(part) for part in head[:7].split("-"))
    except (OSError, ValueError, subprocess.SubprocessError):
        return source_ref()
    patch = sum(1 for date in dates if date[:7] == head[:7]) - 1
    if patch < 0:
        return source_ref()
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

    # "hosted" embeds only the shell, which pins the loader that checks the
    # signature of the interface bundle. "embedded" puts the whole interface
    # in flash, which costs about 35 KB and needs no website and no key.
    hosted = config[CONF_PAGE] == PAGE_HOSTED
    # Check the files before reading any of them, so a clone with no site/app
    # gets this message instead of the error from the first missing read.
    if hosted:
        missing = [path.name for path in (CURRENT_LOADER, APP, SIGNATURE)
                   if not path.exists()]
        if not missing and not (BUNDLE_DIR / loader_name()).exists():
            missing = [loader_name()]
        if missing:
            raise cv.Invalid(
                f"The website is missing {', '.join(missing)}. Run "
                "scripts/build-ui-loader.py and scripts/build-shell-bundle.py, "
                f"then commit the result. A fork can set `page: {PAGE_EMBEDDED}` instead."
            )
    try:
        html = shell_html() if hosted else page()
    except (OSError, ValueError) as err:
        raise cv.Invalid(f"Cannot build the web page: {err}") from err
    blob = gzip.compress(html.encode(), compresslevel=9, mtime=0)
    data = cg.progmem_array(config[CONF_RAW_DATA_ID], [HexInt(value) for value in blob])
    cg.add(var.set_page(data, len(blob)))
