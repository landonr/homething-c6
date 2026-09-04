#!/usr/bin/env python3
"""Serves the /buttons page from the source header with a fake remote behind it.

The page is a raw string in components/button_config/button_config_page.h, so a
browser can run it without an ESPHome build and without hardware. This server
answers the three page endpoints from a small in-memory state, so the layout,
the radio switches, and the assignment tiles can be checked in a browser.

Usage: python3 scripts/preview-buttons-page.py [--port 8123]
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "components" / "button_config" / "button_config_page.h"

# One example of each action, so every tile style is on screen at once.
SLOTS = {
    3: {"action": "hid", "hid_kind": "keyboard", "hid_usage": 0x4F, "hid_mod": 0},
    4: {"action": "hid", "hid_kind": "consumer", "hid_usage": 0xE9, "hid_mod": 0},
    5: {"action": "zigbee", "act": 0, "group": 12, "name": "Kitchen lights"},
    6: {"action": "zigbee", "act": 3, "group": 12, "name": "Kitchen lights"},
    7: {"action": "ir", "pulses": 67, "us": 62000, "fields": "07 02", "name": "TV power"},
    13: {"action": "voice"},
}

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
    "radios": {"zigbee": True, "ble": True},
    "zigbee": {"started": True, "paired": True, "new": False, "gated": False},
    "ble": {"connected": True, "bonded": True, "pairing": False, "host": "bench-mac"},
}

CODE_TEXT = (
    "name: TV power\\n"
    "type: parsed\\n"
    "protocol: Samsung32\\n"
    "address: 07 00 00 00\\n"
    "command: 02 00 00 00\\n"
)


def page_html() -> bytes:
    source = PAGE.read_text()
    match = re.search(r'R"=====\((.*)\)=====";', source, re.DOTALL)
    if match is None:
        raise SystemExit("button_config_page.h has no PAGE_HTML value")
    return match.group(1).encode()


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
            state = dict(STATE)
            state["slots"] = [slot_json(slot) for slot in range(3, 21)]
            self.send_json(state)
            return
        if path == "/buttons/api/code":
            slot = int(parse_qs(urlparse(self.path).query).get("slot", ["0"])[0])
            present = SLOTS.get(slot, {}).get("action") == "ir"
            self.send_json({"slot": slot, "present": present,
                            "text": CODE_TEXT if present else ""})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/buttons/api/action":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode())
        action = form.get("action", [""])[0]
        STATE["action_id"] += 1
        STATE["action_ok"] = True

        if action == "set_radio":
            radio = form.get("radio", [""])[0]
            if radio in STATE["radios"]:
                STATE["radios"][radio] = form.get("on", ["1"])[0] == "1"
        elif action == "forget_ble":
            STATE["ble"]["bonded"] = False
            STATE["ble"]["host"] = ""
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
