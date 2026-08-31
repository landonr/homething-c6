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
    tagName: tag, children: [], _text: "", _html: "", attrs: {}, style: {},
    value: "", className: "", onclick: null, oninput: null,
    set innerHTML(v) {
      this._html = v;
      this.children = [];
      // Register ids the markup declares, so a later getElementById finds them.
      const re = /id=['"]?([A-Za-z0-9_-]+)['"]?/g;
      let m;
      while ((m = re.exec(v))) els[m[1]] = mk("stub");
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
    {slot: 20, action: "zigbee", pulses: 0, us: 0, code: "", fields: "", group: 4609, name: "Office Lamp"},
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
    for (const slot of [3, 6, 19, 20]) if (!words(slot)) throw new Error("slot " + slot + " has no words");
  });

  global.tg = [
    {id: 1, name: "all_light", members: ["0xaaa", "0xbbb"]},
    {id: 9, name: "c6 Office Lamp", members: ["0x94deb8fffe9db81e"]},
  ];
  global.td = [{ieee: "0x94deb8fffe9db81e", name: "Office Lamp"}];
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
  step("a request without a socket calls back an error", () => {
    let got = null;
    zpub("bridge/request/group/add", {}, (r) => { got = r; });
    if (!got || !got.error) throw new Error("expected an error callback");
  });

  setTimeout(() => process.exit(failed ? 1 : 0), 200);
}, 300);
