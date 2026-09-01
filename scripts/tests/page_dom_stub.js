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
for (const id of ["top", "plus", "pad", "ed", "z2m", "cfg", "cfgb", "cfgio", "cxo", "cxs", "cxz"])
  els[id] = mk("section");

const STATE = {
  busy: false, owner: "none", saves: 0, op_slot: 0, op_state: "off",
  result_slot: 0, result: "none", action_id: 0, action_ok: false,
  slots: [
    {slot: 3, action: "none", pulses: 0, us: 0, code: "", fields: "", group: 0, name: ""},
    {slot: 6, action: "ir", pulses: 68, us: 61780, code: "0xE0E09E61", fields: "07 79", group: 0, name: "Home"},
    {slot: 4, action: "voice", pulses: 0, us: 0, code: "", fields: "", group: 0, name: ""},
    {slot: 5, action: "zigbee", pulses: 0, us: 0, code: "", fields: "", group: 0, ieee: "0x94deb8fffe9db81e", ep: 1, name: ""},
    {slot: 20, action: "zigbee", pulses: 0, us: 0, code: "", fields: "", group: 4609, ieee: "", ep: 0, name: "Office Lamp"},
  ],
};

global.document = { getElementById: (id) => els[id] || null, createElement: (t) => mk(t) };
global.localStorage = { getItem: () => null, setItem: () => {} };
global.navigator = {};
global.WebSocket = function () { this.readyState = 0; this.close = () => {}; this.send = () => {}; };
const CODE = {slot: 6, present: true, text: "name: Home\ntype: raw\nfrequency: 38000\ndata: 100 200 300 400"};

global.fetch = (url) => Promise.resolve({
  status: 200,
  json: () => Promise.resolve(String(url).indexOf("/api/code") >= 0 ? CODE : STATE),
  text: () => Promise.resolve('{"ok":true,"id":1}'),
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
    for (const slot of [3, 4, 5, 6, 20]) if (!words(slot)) throw new Error("slot " + slot + " has no words");
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
    if (st.innerHTML.indexOf("1 group, 1 device") < 0) throw new Error("no counts: " + st.innerHTML);
    // The heading repeats the link, so a collapsed card still reports it.
    const zt = document.getElementById("cxz");
    if (zt.innerHTML.indexOf("class=dot></span>Zigbee2MQTT: 1 group, 1 device") < 0)
      throw new Error("no title status: " + zt.innerHTML);
    const zc = document.getElementById("zc");
    if (zc.textContent !== "Disconnect") throw new Error("button stayed on Connect: " + zc.textContent);
    zc.onclick();
    if (tg !== null || td !== null) throw new Error("disconnect kept the lists");
    if (zc.textContent !== "Connect") throw new Error("button stayed on Disconnect: " + zc.textContent);
    if (st.textContent.indexOf("Not connected.") < 0) throw new Error("no idle line: " + st.textContent);
    if (zt.innerHTML.indexOf("dot off") < 0 || zt.innerHTML.indexOf("not connected") < 0)
      throw new Error("the title kept a live status: " + zt.innerHTML);
    global.zerr = "Could not reach Zigbee2MQTT at that address.";
    z2mStatus();
    if (zt.innerHTML.indexOf("dot bad") < 0 || zt.innerHTML.indexOf("unreachable") < 0)
      throw new Error("a failure did not reach the title: " + zt.innerHTML);
    global.zerr = "";
    const hp = document.getElementById("zhp");
    if (hp.textContent.indexOf("8099/tcp") < 0) throw new Error("no port hint: " + hp.textContent);
    global.tg = [{id: 1, name: "all_light", members: []}];
    z2mStatus();
    if (hp.textContent !== "") throw new Error("the hint stayed up while connected: " + hp.textContent);
    global.tg = null; global.td = null;
  });

  global.cfgOpen = true;

  step("plural drops the s on one", () => {
    if (plural(1, "group") !== "1 group") throw new Error(plural(1, "group"));
    if (plural(0, "device") !== "0 devices") throw new Error(plural(0, "device"));
    if (plural(2, "group") !== "2 groups") throw new Error(plural(2, "group"));
  });
  step("the export box holds one entry per input and the IR code with it", () => {
    global.cfgAll = {6: CODE.text};
    const blob = JSON.parse(cfgBlob());
    if (blob.slots.length !== S.length) throw new Error("wrong entry count: " + blob.slots.length);
    const by = {};
    for (const e of blob.slots) by[e.slot] = e;
    if (by[3].action !== "none") throw new Error("an empty input is not none: " + by[3].action);
    if (by[4].action !== "voice") throw new Error("a voice input is not voice: " + by[4].action);
    if (by[6].action !== "ir" || by[6].code !== CODE.text)
      throw new Error("an IR input lost its code: " + JSON.stringify(by[6]));
    if (by[5].kind !== "device" || by[5].ieee !== "0x94deb8fffe9db81e" || by[5].ep !== 1)
      throw new Error("a device target did not survive: " + JSON.stringify(by[5]));
    if (by[20].kind !== "group" || by[20].group !== 4609 || by[20].name !== "Office Lamp")
      throw new Error("a group target did not survive: " + JSON.stringify(by[20]));
  });
  step("an export reads back in without a change", () => {
    global.cfgAll = {6: CODE.text};
    for (const e of JSON.parse(cfgBlob()).slots) {
      const why = cfgCheck(e);
      if (why) throw new Error("slot " + e.slot + ": " + why);
    }
  });
  step("a bad entry is refused before any write", () => {
    if (!cfgCheck({slot: 99, action: "none"})) throw new Error("an unknown slot passed");
    if (cfgCheck({slot: 4, action: "voice"})) throw new Error("voice was refused on slot 4");
    if (!cfgCheck({slot: 17, action: "voice"})) throw new Error("voice passed on slot 17");
    if (!cfgCheck({slot: 6, action: "ir", code: "  "})) throw new Error("an empty code passed");
    if (!cfgCheck({slot: 6, action: "zigbee", kind: "device", ieee: "0x94deb8"}))
      throw new Error("a short address passed");
    if (!cfgCheck({slot: 6, action: "zigbee", kind: "device", ieee: "0x94deb8fffe9db81e", ep: 0}))
      throw new Error("endpoint 0 passed");
    if (!cfgCheck({slot: 6, action: "zigbee", kind: "group", group: 0}))
      throw new Error("group 0 passed");
    if (!cfgCheck({slot: 6, action: "wipe"})) throw new Error("an unknown action passed");
    if (cfgCheck({slot: 6, action: "zigbee", kind: "device", ieee: "94deb8fffe9db81e"}))
      throw new Error("a bare hex address was refused");
  });
  step("an import posts one action per entry and skips a clear that changes nothing", () => {
    const realFetch = global.fetch;
    const bodies = [];
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    global.cfgIn = JSON.stringify({c6remote: 1, slots: [
      {slot: 3, action: "none"},
      {slot: 6, action: "ir", code: CODE.text},
      {slot: 4, action: "voice"},
      {slot: 5, action: "zigbee", kind: "device", ieee: "94DEB8FFFE9DB81E", ep: 2, name: "Lamp"},
      {slot: 20, action: "zigbee", kind: "group", group: 4609, name: "Office Lamp"},
    ]});
    cfgApply();
    global.fetch = realFetch;
    if (cfgBad) throw new Error("a valid config was refused: " + cfgMsg);
    // Slot 3 already holds nothing, so its clear is dropped.
    if (bodies.length !== 1) throw new Error("expected one first post, got " + bodies.length);
    if (bodies[0].indexOf("action=set_ir_code&slot=6") < 0)
      throw new Error("the import started on the wrong entry: " + bodies[0]);
    const dev = cfgSend({slot: 5, action: "zigbee", kind: "device", ieee: "94DEB8FFFE9DB81E", ep: 2, name: "Lamp"});
    if (!dev) throw new Error("a device entry sent nothing");
  });
  step("an invalid paste never reaches the remote", () => {
    const realFetch = global.fetch;
    let calls = 0;
    global.fetch = (u, o) => { calls++; return realFetch(u, o); };
    global.cfgIn = "{not json";
    cfgApply();
    global.cfgIn = JSON.stringify({c6remote: 1});
    cfgApply();
    global.fetch = realFetch;
    if (calls !== 0) throw new Error("a bad paste was still sent");
    if (!cfgBad) throw new Error("no refusal was reported");
  });
  step("the card starts closed and reads no code until it is opened", () => {
    let codeReads = 0;
    const realFetch = global.fetch;
    global.fetch = (u, o) => { if (String(u).indexOf("/api/code") >= 0) codeReads++; return realFetch(u, o); };
    global.cfgOpen = false;
    global.cfgBusy = false;
    global.cfgAll = {};
    cfgPaint();
    if (!document.getElementById("cxo")) throw new Error("no toggle on a closed card");
    if (document.getElementById("cx")) throw new Error("the box showed on a closed card");
    if (els.cfgb.hidden !== true) throw new Error("the closed card left its body on screen");
    if (els.cxs.textContent !== "Show") throw new Error("the closed heading says " + els.cxs.textContent);
    if (codeReads !== 0) throw new Error("a closed card still read a code");
    document.getElementById("cxo").onclick();
    global.fetch = realFetch;
    if (!cfgOpen) throw new Error("the card did not open");
    if (!document.getElementById("cx")) throw new Error("the open card has no box");
    // The reads run off a promise, so the flag is the synchronous evidence that
    // opening on the export side starts them.
    if (!cfgBusy) throw new Error("opening the card started no read");
    if (els.cxs.textContent !== "Hide") throw new Error("the open heading says " + els.cxs.textContent);
    if (els.cfgb.hidden !== false) throw new Error("the open card kept its body hidden");
    global.cfgBusy = false;
    cfgPaint();
    document.getElementById("cxo").onclick();
    if (cfgOpen) throw new Error("the heading did not close the card");
    if (document.getElementById("cx")) throw new Error("the box survived the close");
    if (els.cxs.textContent !== "Show") throw new Error("the closed heading says " + els.cxs.textContent);
    global.cfgOpen = true;
  });
  step("the direction selector switches the box and its buttons", () => {
    global.cfgBusy = false;
    global.cfgMode = "ex";
    global.cfgOpen = true;
    cfgPaint();
    if (!document.getElementById("cxc")) throw new Error("export has no copy button");
    if (document.getElementById("cxa")) throw new Error("apply showed on the export side");
    const cs = document.getElementById("cs");
    cs.value = "im";
    cs.onchange.call(cs);
    if (cfgMode !== "im") throw new Error("the direction did not follow the selector");
    if (!document.getElementById("cxa")) throw new Error("import has no apply button");
    if (document.getElementById("cxr")) throw new Error("read showed on the import side");
    const box = document.getElementById("cx");
    box.value = "typed";
    box.oninput.call(box);
    if (cfgIn !== "typed") throw new Error("the box did not keep the paste: " + cfgIn);
    cfgPaint();
    if (cfgIn !== "typed") throw new Error("a repaint lost the paste: " + cfgIn);
  });

  step("the address box prefills the default and carries the browser clear control", () => {
    const zu = document.getElementById("zu");
    if (zu.value !== Z2MDEF) throw new Error("the box did not prefill: " + zu.value);
    // The x comes from the browser, so only the input type can be checked here.
    if (document.getElementById("z2m").innerHTML.indexOf("id=zu type=search") < 0)
      throw new Error("the address box is not a search field");
  });

  step("the connection block sits in the card and survives a repaint", () => {
    const before = document.getElementById("z2m").innerHTML;
    document.getElementById("zu").value = "ws://typed.local:8099/api";
    global.cfgOpen = true;
    paint();
    if (document.getElementById("z2m").innerHTML !== before)
      throw new Error("a repaint rebuilt the connection block");
    if (document.getElementById("zu").value !== "ws://typed.local:8099/api")
      throw new Error("a repaint dropped a typed address");
  });

  setTimeout(() => process.exit(failed ? 1 : 0), 200);
}, 300);
