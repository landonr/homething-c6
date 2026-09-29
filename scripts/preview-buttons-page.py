#!/usr/bin/env python3
"""Serves the /buttons page from the source header with a fake remote behind it.

The page is a raw string in components/button_config/button_config_page.h, so a
browser can run it without an ESPHome build and without hardware. This server
answers the page endpoints from a small in-memory state, so the layout,
the radio switches, and the assignment tiles can be checked in a browser.

Slot assignments come from preview-c6remote-config.json, an export from the
/buttons config card.

Usage: python3 scripts/preview-buttons-page.py [--port 8123]
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
    "busy": False,
    "owner": "none",
    "saves": 12,
    "op_slot": 0,
    "op_state": "off",
    "result_slot": 0,
    "result": "none",
    "action_id": 0,
    "action_ok": True,
    "network": {
        "wifi": True,
        "wifi_enabled": True,
        "wifi_always_on": False,
        "home_assistant": True,
        "ip": "192.168.1.86",
        "mac": "A4:CF:12:34:56:78",
    },
    # Production links idle_sleep. A build without it serves available false and zeros.
    "sleep": {"available": True, "enabled": True, "after_s": 300},
    "radios": {"zigbee": True, "ble": True},
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
}

FRIENDLY_NAME_MAX = 40

# A fake restart fails the state poll for a short time. Then the action ids
# start again from zero, as they do after a real boot. The preview always comes
# back, even when the remote would keep Wi-Fi off after the restart.
RESTART_SECONDS = 4.0
RESTART = {"until": 0.0}


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
    # Export JSON from /buttons uses a shorter shape than /api/state.
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

    def do_GET(self) -> None:
        path = urlparse(self.path).path
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
        STATE["action_id"] += 1
        STATE["action_ok"] = True

        if action == "set_radio":
            radio = form.get("radio", [""])[0]
            if radio in STATE["radios"]:
                STATE["radios"][radio] = form.get("on", ["1"])[0] == "1"
        elif action == "set_wifi_always_on":
            STATE["network"]["wifi_always_on"] = form.get("enabled", ["0"])[0] == "1"
        elif action == "set_sleep_enabled":
            STATE["sleep"]["enabled"] = form.get("enabled", ["0"])[0] == "1"
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
    print(f"Preview at http://127.0.0.1:{args.port}/buttons")
    server.serve_forever()


if __name__ == "__main__":
    main()
