#!/usr/bin/env python3
"""Serves the web page from the source header with a fake remote behind it.

The page is a raw string in components/button_config/button_config_page.h, so a
browser can run it without an ESPHome build and without hardware. This server
answers the page endpoints from a small in-memory state, so the layout,
the radio switches, and the assignment tiles can be checked in a browser.

Slot assignments come from preview-c6remote-config.json, an export from the
Import Export card of the web page.

Usage: python3 scripts/preview-buttons-page.py [--port 8123]

Open http://127.0.0.1:8123/preview/offline to toggle offline mode. Each call
flips the mode and prints the new state. While the mode is on, every
/buttons/api request waits 8 s and then closes the connection with no answer,
as a dead remote does. The page itself still loads. Use it to check the link
line and the banner on the web page.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.parse import quote_from_bytes

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "components" / "button_config" / "button_config_page.h"
CASE_FRONT_FACE = ROOT / "docs" / "readme-assets" / "case-front-face.svg"
CONFIG = Path(__file__).resolve().parent / "preview-c6remote-config.json"

STATE = {
    "firmware": "2026.10.0",
    "busy": False,
    "owner": "none",
    "saves": 12,
    "op_slot": 0,
    "op_state": "off",
    "result_slot": 0,
    "result": "none",
    "action_id": 0,
    "action_ok": True,
    "status_leds": "on",
    "boot_leds": True,
    # Slot of each hold, 0 for none. These are the firmware defaults.
    "holds": {"wifi": 5, "status": 7, "sleep": 20, "assign": 9},
    "network": {
        "wifi": True,
        "wifi_enabled": True,
        "wifi_always_on": False,
        "home_assistant": True,
        # True when the Home Assistant switch was off at boot, so the API server did not start.
        "api_gated": False,
        "ip": "192.168.1.86",
        "mac": "A4:CF:12:34:56:78",
    },
    # Production links idle_sleep. A build without it serves available false and zeros.
    "sleep": {"available": True, "enabled": True, "after_s": 300, "replay": False},
    # Production links the battery sensors. A build without them serves available false and zeros.
    "battery": {"available": True, "percent": 72, "volts": 3.87},
    "radios": {"zigbee": True, "ble": True, "home_assistant": True},
    "zigbee": {
        "started": True,
        "paired": True,
        "new": False,
        "gated": False,
        "pairing": False,
        "pair_left": 0,
        "pair_failed": False,
        "reach": "ok",
    },
    "ble": {"connected": True, "bonded": True, "pairing": False, "host": "bench-mac"},
    "name": "homeThing C6 13f498",
    "default_name": "homeThing C6 13f498",
    "ha": {"pending": 0, "last_slot": 0, "last": "none", "error": ""},
}

FRIENDLY_NAME_MAX = 40

# Mirrors the kind and action table of the firmware.
_T3 = ["toggle", "turn_on", "turn_off"]
HA_ACTIONS = {
    "light": _T3 + ["brightness_up", "brightness_down"],
    "switch": _T3,
    "input_boolean": _T3,
    "fan": _T3 + ["increase_speed", "decrease_speed"],
    "cover": ["toggle", "open_cover", "close_cover", "stop_cover"],
    "lock": ["lock", "unlock"],
    "scene": ["turn_on"],
    "script": ["turn_on", "toggle"],
    "automation": ["trigger", "toggle"],
    "button": ["press"],
    "input_button": ["press"],
    "media_player": ["media_play_pause", "volume_up", "volume_down",
                     "media_next_track", "media_previous_track"],
    "homeassistant": _T3,
}
HA_ENTITY = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
# A test shows queued, then ok this long after the press.
HA_TEST_SECONDS = 2.0
HA_TEST = {"slot": 0, "at": 0.0}


def ha_error(kind: str, act: str, val: str, entity: str) -> str | None:
    """Mirrors the validation of set_ha in button_config.cpp."""
    if act not in HA_ACTIONS.get(kind, []):
        return "unknown Home Assistant kind or action"
    if (len(entity) > 64 or not HA_ENTITY.match(entity)
            or (kind != "homeassistant" and entity.split(".")[0] != kind)):
        return "an entity id is domain.object_id, up to 64 characters, and its domain must match the kind"
    step = act in ("brightness_up", "brightness_down")
    if not val.isdigit() or int(val) > 100 or (step and int(val) < 1):
        return "a brightness step is 1 to 100"
    return None
# Mirrors HoldActions::valid_slot(): the sixteen expander inputs, no wheel rotation.
HOLD_SLOTS = {3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 19, 20}

# A fake restart fails the state poll for a short time. Then the action ids
# start again from zero, as they do after a real boot. The preview always comes
# back, even when the remote would keep Wi-Fi off after the restart.
RESTART_SECONDS = 4.0
RESTART = {"until": 0.0}

# Longer than the page's 5 s read timeout, so the page sees a dead host.
OFFLINE = {"on": False}
OFFLINE_HOLD_SECONDS = 8.0


def reverse_bits(value: int) -> int:
    out = 0
    for bit in range(8):
        out = (out << 1) | ((value >> bit) & 1)
    return out


def samsung_code(address: int, command: int) -> str:
    data = (
        (reverse_bits(address) << 24)
        | (reverse_bits(address) << 16)
        | (reverse_bits(command) << 8)
        | reverse_bits((~command) & 0xFF)
    )
    return f"0x{data:08X}"


def parse_ir_code(text: str) -> dict:
    name = "IR"
    address = 0
    command = 0
    for line in text.splitlines():
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "name" and value:
            name = value
        elif key == "address" and value:
            address = int(value.split()[0], 16)
        elif key == "command" and value:
            command = int(value.split()[0], 16)
    return {
        "action": "ir",
        "pulses": 68,
        "us": 61780,
        "fields": f"{address:02X} {command:02X}",
        "code": samsung_code(address, command),
        "name": name,
    }


def clean_name(text: str) -> str | None:
    """Mirrors parse_friendly_name() in button_config.cpp. Empty means the default."""
    name = text.strip(" ")
    if len(name.encode()) > FRIENDLY_NAME_MAX:
        return None
    if any(ord(c) < 0x20 or ord(c) == 0x7F or c == "/" for c in name):
        return None
    return name


def load_config(path: Path) -> tuple[dict, dict]:
    # Export JSON from the web page uses a shorter shape than /buttons/api/state.
    data = json.loads(path.read_text())
    slots: dict[int, dict] = {}
    codes: dict[int, str] = {}
    for entry in data.get("slots", []):
        slot = int(entry["slot"])
        action = entry.get("action", "none")
        if action == "voice":
            slots[slot] = {"action": "voice"}
        elif action == "hid":
            slots[slot] = {
                "action": "hid",
                "hid_kind": entry.get("kind", "keyboard"),
                "hid_usage": int(entry.get("usage", 0)),
                "hid_mod": int(entry.get("mod", 0)),
            }
        elif action == "ha":
            slots[slot] = {
                "action": "ha",
                "ha_kind": entry.get("kind", "light"),
                "ha_act": entry.get("act", "toggle"),
                "ha_val": int(entry.get("val", 0)),
                "ha_entity": entry.get("entity", ""),
            }
        elif action == "zigbee":
            row = {
                "action": "zigbee",
                "act": int(entry.get("act", 0)),
                "val": int(entry.get("val", 0)),
                "name": entry.get("name", ""),
            }
            if entry.get("kind") == "device":
                row["ieee"] = entry.get("ieee", "")
                row["ep"] = int(entry.get("ep", 1))
            else:
                row["group"] = int(entry.get("group", 0))
            slots[slot] = row
        elif action == "ir":
            text = entry.get("code", "")
            codes[slot] = text
            slots[slot] = parse_ir_code(text)
    return slots, codes


SLOTS, IR_CODES = load_config(CONFIG)
SLOTS.setdefault(8, {"action": "ha", "ha_kind": "light", "ha_act": "brightness_up",
                     "ha_val": 10, "ha_entity": "light.kitchen"})


def page_html() -> bytes:
    source = PAGE.read_text()
    match = re.search(r'R"=====\((.*)\)=====";', source, re.DOTALL)
    if match is None:
        raise SystemExit("button_config_page.h has no PAGE_HTML value")
    svg = quote_from_bytes(CASE_FRONT_FACE.read_bytes(), safe="/,:;=(){}@.-_")
    return match.group(1).replace("__CASE_FRONT_FACE_SVG__", svg).encode()


def slot_json(slot: int) -> dict:
    entry = SLOTS.get(slot, {})
    return {
        "slot": slot,
        "action": entry.get("action", "none"),
        "pulses": entry.get("pulses", 0),
        "us": entry.get("us", 0),
        "code": entry.get("code", ""),
        "fields": entry.get("fields", ""),
        "group": entry.get("group", 0),
        "ieee": entry.get("ieee", ""),
        "ep": entry.get("ep", 0),
        "act": entry.get("act", 0),
        "val": entry.get("val", 0),
        "hid_kind": entry.get("hid_kind", "none"),
        "hid_usage": entry.get("hid_usage", 0),
        "hid_mod": entry.get("hid_mod", 0),
        "name": entry.get("name", ""),
        "ha_kind": entry.get("ha_kind", ""),
        "ha_act": entry.get("ha_act", ""),
        "ha_val": entry.get("ha_val", 0),
        "ha_entity": entry.get("ha_entity", ""),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter console
        pass

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def drop_if_offline(self, path: str) -> bool:
        """Holds the request, then closes it with no response, like a dead host."""
        if not (OFFLINE["on"] and path.startswith("/buttons/api/")):
            return False
        time.sleep(OFFLINE_HOLD_SECONDS)
        self.close_connection = True
        return True

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/preview/offline":
            OFFLINE["on"] = not OFFLINE["on"]
            body = f"offline mode is {'on' if OFFLINE['on'] else 'off'}\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.drop_if_offline(path):
            return
        if path in ("/", "/buttons"):
            body = page_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/buttons/api/state":
            if RESTART["until"]:
                if time.monotonic() < RESTART["until"]:
                    self.send_error(503)
                    return
                RESTART["until"] = 0.0
                STATE["action_id"] = 0
                # The boot gate reads the switch, so the API follows it after a restart.
                STATE["network"]["api_gated"] = not STATE["radios"]["home_assistant"]
                STATE["network"]["home_assistant"] = STATE["radios"]["home_assistant"]
            if HA_TEST["slot"] and time.monotonic() >= HA_TEST["at"]:
                STATE["ha"].update({"pending": 0, "last_slot": HA_TEST["slot"], "last": "ok"})
                HA_TEST["slot"] = 0
            state = dict(STATE)
            state["slots"] = [slot_json(slot) for slot in range(3, 21)]
            self.send_json(state)
            return
        if path == "/buttons/api/code":
            slot = int(parse_qs(urlparse(self.path).query).get("slot", ["0"])[0])
            text = IR_CODES.get(slot, "")
            present = SLOTS.get(slot, {}).get("action") == "ir" and bool(text)
            self.send_json({"slot": slot, "present": present, "text": text})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if self.drop_if_offline(path):
            return
        if path == "/buttons/api/activity":
            self.send_json({"ok": True})
            return
        if path != "/buttons/api/action":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode())
        action = form.get("action", [""])[0]
        seconds = form.get("seconds", [""])[0]
        if action == "set_sleep_after" and not (seconds.isdigit() and 10 <= int(seconds) <= 3600):
            self.send_json({"ok": False, "error": "sleep after is 10 to 3600 seconds"}, 400)
            return
        # parse_qs drops a blank value, so an empty box arrives as a missing name.
        name = clean_name(form.get("name", [""])[0]) if action == "set_name" else None
        if action == "set_name" and name is None:
            self.send_json(
                {"ok": False, "error": "a name is up to 40 bytes, with no slash or control character"}, 400)
            return
        slot_text = form.get("slot", ["0"])[0]
        slot = int(slot_text) if slot_text.isdigit() else 0
        if action == "set_ha":
            why = ha_error(form.get("kind", [""])[0], form.get("act", [""])[0],
                           form.get("val", [""])[0], form.get("entity", [""])[0])
            if why:
                self.send_json({"ok": False, "error": why}, 400)
                return
        if action == "test_ha":
            if SLOTS.get(slot, {}).get("action") != "ha":
                self.send_json({"ok": False, "error": "slot has no Home Assistant action"}, 400)
                return
            if not STATE["radios"]["home_assistant"]:
                self.send_json({"ok": False, "error": "Home Assistant is off in Config"}, 400)
                return
            if STATE["network"]["api_gated"]:
                self.send_json(
                    {"ok": False, "error": "Home Assistant API is off until the remote restarts"}, 400)
                return
            # The firmware sets queued, then completes the action id.
            STATE["ha"].update({"pending": 1, "last_slot": slot, "last": "queued", "error": ""})
            HA_TEST.update({"slot": slot, "at": time.monotonic() + HA_TEST_SECONDS})
            STATE["action_id"] += 1
            STATE["action_ok"] = True
            self.send_json({"ok": True, "id": STATE["action_id"]})
            return
        mode = form.get("mode", [""])[0]
        if action == "set_status_leds" and mode not in ("off", "hold", "on"):
            self.send_json({"ok": False, "error": "a status LED mode is off, hold, or on"}, 400)
            return
        # The same three refusals as handle_action_() in button_config.cpp.
        hold = form.get("hold", [""])[0]
        hold_slot = form.get("slot", [""])[0]
        if action == "set_hold":
            if hold not in STATE["holds"]:
                self.send_json({"ok": False, "error": "a hold is wifi, status, sleep, or assign"}, 400)
                return
            if not (hold_slot.isdigit() and len(hold_slot) <= 2
                    and (int(hold_slot) == 0 or int(hold_slot) in HOLD_SLOTS)):
                self.send_json({"ok": False, "error": "a hold button is 0 or a button slot"}, 400)
                return
            if int(hold_slot) and any(
                    key != hold and value == int(hold_slot) for key, value in STATE["holds"].items()):
                self.send_json({"ok": False, "error": "another hold already uses that button"}, 400)
                return
        STATE["action_id"] += 1
        STATE["action_ok"] = True

        if action == "set_radio":
            radio = form.get("radio", [""])[0]
            if radio in STATE["radios"]:
                STATE["radios"][radio] = form.get("on", ["1"])[0] == "1"
        elif action == "set_wifi_always_on":
            STATE["network"]["wifi_always_on"] = form.get("enabled", ["0"])[0] == "1"
        elif action == "set_status_leds":
            STATE["status_leds"] = mode
        elif action == "set_hold":
            STATE["holds"][hold] = int(hold_slot)
        elif action == "set_boot_leds":
            STATE["boot_leds"] = form.get("enabled", ["0"])[0] == "1"
        elif action == "set_sleep_enabled":
            STATE["sleep"]["enabled"] = form.get("enabled", ["0"])[0] == "1"
        elif action == "set_sleep_replay":
            STATE["sleep"]["replay"] = form.get("enabled", ["0"])[0] == "1"
        elif action == "set_sleep_after":
            STATE["sleep"]["after_s"] = int(seconds)
        elif action == "set_name":
            STATE["name"] = name or STATE["default_name"]
        elif action == "pair":
            # The real remote restarts here, so the preview only flips the flag
            # and lets the page's own countdown run against it.
            on = form.get("on", ["1"])[0] == "1"
            STATE["zigbee"]["pairing"] = on
            STATE["zigbee"]["pair_left"] = 180 if on else 0
            STATE["zigbee"]["pair_failed"] = False
            STATE["radios"]["zigbee"] = on
            if on:
                STATE["zigbee"]["paired"] = False
                STATE["zigbee"]["new"] = True
        elif action == "set_ha":
            SLOTS[slot] = {
                "action": "ha",
                "ha_kind": form["kind"][0],
                "ha_act": form["act"][0],
                "ha_val": int(form["val"][0]),
                "ha_entity": form["entity"][0],
            }
        elif action == "clear" and SLOTS.get(slot, {}).get("action") == "ha":
            del SLOTS[slot]
        elif action == "forget_ble":
            STATE["ble"]["bonded"] = False
            STATE["ble"]["host"] = ""
        elif action == "restart":
            RESTART["until"] = time.monotonic() + RESTART_SECONDS
        self.send_json({"ok": True, "id": STATE["action_id"]})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8123)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Preview at http://127.0.0.1:{args.port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
