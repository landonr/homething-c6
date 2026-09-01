// Runs the /buttons page script outside a browser.
//
// node --check only parses. The page is built from string concatenation and
// plain vars, so a missing declaration or a renamed helper is a runtime
// ReferenceError that parsing cannot see. One such slip left every button
// unlabelled on real hardware, because the throw happened inside paint() and
// the startup promise swallowed it.
//
// Usage: node page_dom_stub.js <page.js>

const fs = require("fs");

const els = {};
function mk(tag) {
  return {
    tagName: tag, children: [], _text: "", _html: "", _ids: [], attrs: {}, style: {},
    value: "", className: "", onclick: null, oninput: null,
    set innerHTML(v) {
      this._html = v;
      this.children = [];
      // Drop the ids the previous markup declared before registering the new
      // ones. Without this a field that a repaint stopped rendering is still
      // found by getElementById, and a panel that hides a field looks the same
      // as one that still shows it.
      for (const id of this._ids) delete els[id];
      this._ids = [];
      const re = /id=['"]?([A-Za-z0-9_-]+)['"]?/g;
      let m;
      while ((m = re.exec(v))) { els[m[1]] = mk("stub"); this._ids.push(m[1]); }
    },
    get innerHTML() { return this._html; },
    set textContent(v) { this._text = String(v); },
    get textContent() { return this._text; },
    get firstChild() { if (!this.children[0]) this.children[0] = mk("b"); return this.children[0]; },
    get lastChild() { if (!this.children[1]) this.children[1] = mk("span"); return this.children[1]; },
    setAttribute(k, v) { this.attrs[k] = v; },
    appendChild(c) { this.children.push(c); return c; },
    focus() {}, select() {},
  };
}
for (const id of ["top", "plus", "pad", "ed", "z2m"]) els[id] = mk("section");

const STATE = {
  busy: false, owner: "none", saves: 0, op_slot: 0, op_state: "off",
  result_slot: 0, result: "none", action_id: 0, action_ok: false,
  slots: [
    {slot: 3, action: "none", pulses: 0, us: 0, code: "", fields: "", group: 0, name: ""},
    {slot: 6, action: "ir", pulses: 68, us: 61780, code: "0xE0E09E61", fields: "07 79", group: 0, name: "Home"},
    {slot: 19, action: "voice", pulses: 0, us: 0, code: "", fields: "", group: 0, name: ""},
    {slot: 5, action: "zigbee", pulses: 0, us: 0, code: "", fields: "", group: 0, ieee: "0x94deb8fffe9db81e", ep: 1, name: ""},
    {slot: 20, action: "zigbee", pulses: 0, us: 0, code: "", fields: "", group: 4609, ieee: "", ep: 0, name: "Office Lamp"},
  ],
};

global.document = { getElementById: (id) => els[id] || null, createElement: (t) => mk(t) };
global.localStorage = { getItem: () => null, setItem: () => {} };
global.navigator = {};
global.WebSocket = function () { this.readyState = 0; this.close = () => {}; this.send = () => {}; };
global.fetch = () => Promise.resolve({
  status: 200,
  json: () => Promise.resolve(STATE),
  text: () => Promise.resolve("{}"),
});

let failed = 0;
function step(name, fn) {
  try { fn(); console.log("OK   " + name); }
  catch (e) { console.log("FAIL " + name + ": " + e.message); failed++; }
}

const source = fs.readFileSync(process.argv[2], "utf8");
try {
  (0, eval)(source);
} catch (e) {
  console.log("FAIL script load: " + e.message);
  process.exit(1);
}

// The startup path runs through a promise, so the checks wait for it.
setTimeout(() => {
  step("startup labelled every button", () => {
    for (const d of S) {
      const b = keys[d.s];
      if (!b) throw new Error("slot " + d.s + " has no button");
      if (!b.firstChild.textContent) throw new Error("slot " + d.s + " has no label");
    }
  });
  step("words covers every action", () => {
    for (const slot of [3, 5, 6, 19, 20]) if (!words(slot)) throw new Error("slot " + slot + " has no words");
    // A device slot with no friendly name still has to name its target.
    if (words(5).indexOf("0x94deb8fffe9db81e") < 0) throw new Error("a device slot lost its address");
  });

  global.tg = [
    {id: 1, name: "all_light", members: ["0xaaa", "0xbbb"]},
    {id: 9, name: "c6 Office Lamp", members: ["0x94deb8fffe9db81e"]},
  ];
  global.td = [{ieee: "0x94deb8fffe9db81e", name: "Office Lamp", ep: 1}];
  global.sel = 20;

  step("paint with both lists", () => paint());
  step("zbForm with both lists", () => { if (!zbForm()) throw new Error("empty form"); });
  step("zbForm with no lists", () => {
    const g = global.tg, d = global.td;
    global.tg = null; global.td = null;
    const h = zbForm();
    global.tg = g; global.td = d;
    if (!h) throw new Error("empty form");
  });
  step("every action panel paints on a voice capable slot", () => {
    global.sel = 20;
    for (const a of ["ir", "zb", "va", "cl"]) {
      global.act = a;
      paint();
      if (!document.getElementById("as")) throw new Error(a + " painted no selector");
    }
  });
  step("the voice panel is not offered on a slot without it", () => {
    global.sel = 19;  // SW2 owns the hold gesture, so it has no voice action.
    global.act = "va";
    paint();
    if (act === "va") throw new Error("voice stayed selected on a slot without it");
  });
  step("switching the selector repaints", () => {
    global.sel = 20;
    global.act = "ir";
    paint();
    const sw = document.getElementById("as");
    if (typeof sw.onchange !== "function") throw new Error("no onchange handler");
    sw.value = "zb";
    sw.onchange.call(sw);
    if (act !== "zb") throw new Error("act did not follow the selector");
  });
  step("onOffEndpoint picks the lowest On/Off endpoint", () => {
    if (onOffEndpoint({endpoints: {}}) !== 0) throw new Error("a device with no On/Off must be dropped");
    if (onOffEndpoint({}) !== 1) throw new Error("a missing endpoint list must fall back to 1");
    const d = {endpoints: {
      "3": {clusters: {input: ["genOnOff"]}},
      "1": {clusters: {input: ["genBasic"]}},
      "2": {clusters: {input: ["genOnOff"]}},
    }};
    if (onOffEndpoint(d) !== 2) throw new Error("expected endpoint 2, got " + onOffEndpoint(d));
  });
  step("assignDevice posts the address and endpoint and writes nothing to the bridge", () => {
    let body = null, sent = 0;
    const realFetch = global.fetch;
    global.ws = {readyState: 1, send: () => { sent++; }};
    global.fetch = (u, o) => { body = o && o.body; return realFetch(u, o); };
    global.sel = 20;
    global.zdv = "0x94deb8fffe9db81e";
    assignDevice();
    global.fetch = realFetch;
    if (sent !== 0) throw new Error("the page wrote to Zigbee2MQTT");
    if (!body || body.indexOf("action=set_zigbee_device") < 0) throw new Error("wrong action: " + body);
    if (body.indexOf("ieee=0x94deb8fffe9db81e") < 0) throw new Error("no IEEE address: " + body);
    if (body.indexOf("ep=1") < 0) throw new Error("no endpoint: " + body);
  });

  setTimeout(() => process.exit(failed ? 1 : 0), 200);
}, 300);
