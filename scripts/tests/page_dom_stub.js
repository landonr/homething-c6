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
  step("the one button posts the address and endpoint, writing nothing to the bridge", () => {
    let body = null, sent = 0;
    const realFetch = global.fetch;
    global.ws = {readyState: 1, send: () => { sent++; }};
    global.fetch = (u, o) => { body = o && o.body; return realFetch(u, o); };
    global.sel = 20;
    global.zkv = "d";
    global.zhv = "0x94deb8fffe9db81e";
    global.zpv = "1";
    assignTarget();
    global.fetch = realFetch;
    if (sent !== 0) throw new Error("the page wrote to Zigbee2MQTT");
    if (!body || body.indexOf("action=set_zigbee_device") < 0) throw new Error("wrong action: " + body);
    if (body.indexOf("ieee=0x94deb8fffe9db81e") < 0) throw new Error("no IEEE address: " + body);
    if (body.indexOf("ep=1") < 0) throw new Error("no endpoint: " + body);
    // The name comes from the device list, not from a remembered selection.
    if (body.indexOf("name=Office%20Lamp") < 0) throw new Error("no looked-up name: " + body);
  });
  step("the target box reaches a device and a group", () => {
    const realFetch = global.fetch;
    let body = null;
    global.fetch = (u, o) => { body = o && o.body; return realFetch(u, o); };
    global.sel = 20;
    global.zpv = "";
    global.zkv = "d";
    global.zhv = "94deb8fffe9db81e";  // the 0x prefix is optional
    assignTarget();
    if (!body || body.indexOf("action=set_zigbee_device") < 0)
      throw new Error("16 hex digits did not assign a device: " + body);
    if (body.indexOf("ep=1") < 0) throw new Error("an empty endpoint box must mean 1: " + body);
    body = null;
    global.zkv = "g";
    global.zgv = "0x1201";
    assignTarget();
    if (!body || body.indexOf("action=set_zigbee&") < 0)
      throw new Error("a short ID must still assign a group: " + body);
    if (body.indexOf("group=0x1201") < 0) throw new Error("no group id: " + body);
    global.fetch = realFetch;
  });
  step("a picker fills the target box and drops the other picker", () => {
    global.sel = 20;
    global.act = "zb";
    global.zsv = ""; global.zdv = ""; global.zgv = ""; global.zhv = ""; global.zpv = "";
    global.zkv = "d";
    paint();
    const ds = document.getElementById("zd");
    if (typeof ds.onchange !== "function") throw new Error("the device picker has no handler");
    ds.value = "0x94deb8fffe9db81e";
    ds.onchange.call(ds);
    if (zhv !== "0x94deb8fffe9db81e") throw new Error("the device did not fill its box: " + zhv);
    if (zpv !== "1") throw new Error("the device did not fill the endpoint: " + zpv);
    if (document.getElementById("zg")) throw new Error("the group box showed on the device kind");
    // Switching kind must drop everything the panel stopped showing.
    const kn = document.getElementById("zn");
    kn.value = "g";
    kn.onchange.call(kn);
    if (zkv !== "g") throw new Error("the kind did not switch: " + zkv);
    if (zhv !== "" || zpv !== "" || zdv !== "")
      throw new Error("device fields survived the switch: " + [zhv, zpv, zdv].join(","));
    const gs = document.getElementById("zs");
    gs.value = "9";
    gs.onchange.call(gs);
    if (zgv !== "9") throw new Error("the group did not fill its box: " + zgv);
    if (document.getElementById("zh")) throw new Error("the address box showed on the group kind");
  });

  step("a hidden field cannot be assigned", () => {
    const realFetch = global.fetch;
    let body = null, calls = 0;
    global.fetch = (u, o) => { calls++; body = o && o.body; return realFetch(u, o); };
    global.sel = 20;
    // A stale address from a device pick must not ride along on a group assign.
    global.zkv = "g";
    global.zgv = "4609";
    global.zhv = "0x94deb8fffe9db81e";
    assignTarget();
    global.fetch = realFetch;
    if (calls !== 1) throw new Error("expected exactly one request, got " + calls);
    if (body.indexOf("action=set_zigbee&") < 0) throw new Error("the hidden kind won: " + body);
    if (body.indexOf("ieee=") >= 0) throw new Error("a hidden address was sent: " + body);
  });
  step("a malformed address is refused before it reaches the remote", () => {
    const realFetch = global.fetch;
    let calls = 0;
    global.fetch = (u, o) => { calls++; return realFetch(u, o); };
    global.zkv = "d";
    global.zhv = "0x94deb8";
    assignTarget();
    global.fetch = realFetch;
    if (calls !== 0) throw new Error("a short address was still sent");
    if (!bad || msg.indexOf("16 hex digits") < 0) throw new Error("no clear refusal: " + msg);
  });

  step("the status line marks a live connection and the button offers Disconnect", () => {
    global.tg = [{id: 1, name: "all_light", members: []}];
    global.td = [{ieee: "0x94deb8fffe9db81e", name: "Office Lamp", ep: 1}];
    global.zerr = "";
    z2mStatus();
    const st = document.getElementById("zst");
    if (st.innerHTML.indexOf("class=dot") < 0) throw new Error("no green dot: " + st.innerHTML);
    if (st.innerHTML.indexOf("1 groups, 1 devices") < 0) throw new Error("no counts: " + st.innerHTML);
    const zc = document.getElementById("zc");
    if (zc.textContent !== "Disconnect") throw new Error("button stayed on Connect: " + zc.textContent);
    zc.onclick();
    if (tg !== null || td !== null) throw new Error("disconnect kept the lists");
    if (zc.textContent !== "Connect") throw new Error("button stayed on Disconnect: " + zc.textContent);
    if (st.textContent.indexOf("Not connected.") < 0) throw new Error("no idle line: " + st.textContent);
    const hp = document.getElementById("zhp");
    if (hp.textContent.indexOf("8099/tcp") < 0) throw new Error("no port hint: " + hp.textContent);
    global.tg = [{id: 1, name: "all_light", members: []}];
    z2mStatus();
    if (hp.textContent !== "") throw new Error("the hint stayed up while connected: " + hp.textContent);
    global.tg = null; global.td = null;
  });

  step("the address box prefills the default and carries the browser clear control", () => {
    const zu = document.getElementById("zu");
    if (zu.value !== Z2MDEF) throw new Error("the box did not prefill: " + zu.value);
    // The x comes from the browser, so only the input type can be checked here.
    if (document.getElementById("z2m").innerHTML.indexOf("id=zu type=search") < 0)
      throw new Error("the address box is not a search field");
  });

  setTimeout(() => process.exit(failed ? 1 : 0), 200);
}, 300);
