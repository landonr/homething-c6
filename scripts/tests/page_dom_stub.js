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
let lastDownload = null;
function mk(tag) {
  return {
    tagName: tag, children: [], _text: "", _html: "", _ids: [], attrs: {}, style: {},
    value: "", className: "", disabled: false, onclick: null, oninput: null,
    set innerHTML(v) {
      this._html = v;
      this.children = [];
      // Drop the ids the previous markup declared before registering the new
      // ones. Without this a field that a repaint stopped rendering is still
      // found by getElementById, and a panel that hides a field looks the same
      // as one that still shows it.
      for (const id of this._ids) delete els[id];
      this._ids = [];
      const re = /<[^>]*\bid=['"]?([A-Za-z0-9_-]+)['"]?[^>]*>/g;
      let m;
      while ((m = re.exec(v))) {
        const child = mk("stub");
        child.disabled = /\sdisabled(?:\s|=|>)/.test(m[0]);
        els[m[1]] = child;
        this._ids.push(m[1]);
      }
    },
    get innerHTML() { return this._html; },
    // A browser serialises the text node back out of innerHTML, and esc() reads
    // it that way to escape a bridge or host name.
    set textContent(v) {
      this._text = String(v);
      this._html = this._text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    },
    get textContent() { return this._text; },
    get firstChild() { if (!this.children[0]) this.children[0] = mk("b"); return this.children[0]; },
    get lastChild() { if (!this.children[1]) this.children[1] = mk("span"); return this.children[1]; },
    setAttribute(k, v) { this.attrs[k] = v; },
    appendChild(c) { this.children.push(c); return c; },
    focus() {}, select() {},
    click() { this.clicked = true; if (tag === "a") lastDownload = this; },
  };
}
for (const id of ["top", "plus", "pad", "ed", "z2m", "bst", "bfr", "cfg", "cfgb", "cfgio", "cxo", "cxs", "zsum"])
  els[id] = mk("section");

const STATE = {
  busy: false, owner: "none", saves: 0, op_slot: 0, op_state: "off",
  result_slot: 0, result: "none", action_id: 0, action_ok: false,
  ble: {connected: true, bonded: true, pairing: false, host: "Landon's Mac"},
  slots: [
    {slot: 3, action: "none", pulses: 0, us: 0, code: "", fields: "", group: 0, name: ""},
    {slot: 6, action: "ir", pulses: 68, us: 61780, code: "0xE0E09E61", fields: "07 79", group: 0, name: "Home"},
    {slot: 4, action: "voice", pulses: 0, us: 0, code: "", fields: "", group: 0, name: ""},
    {slot: 5, action: "zigbee", pulses: 0, us: 0, code: "", fields: "", group: 0, ieee: "0x94deb8fffe9db81e", ep: 1, act: 3, val: 32, name: ""},
    {slot: 7, action: "hid", pulses: 0, us: 0, code: "", fields: "", group: 0, hid_kind: "keyboard", hid_usage: 4, hid_mod: 2, name: ""},
    {slot: 20, action: "zigbee", pulses: 0, us: 0, code: "", fields: "", group: 4609, ieee: "", ep: 0, act: 0, val: 0, name: "Office Lamp"},
  ],
};

global.document = { getElementById: (id) => els[id] || null, createElement: (t) => mk(t) };
global.localStorage = { getItem: () => null, setItem: () => {} };
global.navigator = {};
global.WebSocket = function () { this.readyState = 0; this.close = () => {}; this.send = () => {}; };
let downloadedBlob = null, revokedUrl = null;
global.Blob = function (parts, options) { this.parts = parts; this.type = options.type; };
global.URL = {
  createObjectURL: (blob) => { downloadedBlob = blob; return "blob:config"; },
  revokeObjectURL: (url) => { revokedUrl = url; },
};
global.FileReader = function () {
  this.result = "";
  this.readAsText = (file) => { this.result = file.text; this.onload(); };
};
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
    for (const slot of [3, 4, 5, 6, 7, 20]) if (!words(slot)) throw new Error("slot " + slot + " has no words");
    // A device slot with no friendly name still has to name its target.
    if (words(5).indexOf("0x94deb8fffe9db81e") < 0) throw new Error("a device slot lost its address");
  });
  step("switching to an empty input clears stale IR code without loading", () => {
    const realFetch = global.fetch;
    let codeRequests = 0;
    global.fetch = (u, o) => {
      if (String(u).indexOf("/api/code") >= 0) codeRequests++;
      return realFetch(u, o);
    };
    global.sel = 6;
    global.cd = CODE.text;
    global.cdSlot = 6;
    global.act = "ir";
    paint();
    pick(3);
    const html = document.getElementById("ed").innerHTML;
    if (html.indexOf(CODE.text) >= 0) throw new Error("the previous input's code stayed visible");
    if (html.indexOf("Loading the stored code.") >= 0)
      throw new Error("an empty input showed a loading state");
    if (codeRequests) throw new Error("an empty input requested stored IR code");
    if (cd !== "" || cdSlot !== 3) throw new Error("the empty code box was not ready");
    global.fetch = realFetch;
  });
  step("the IR loading state stays below the code actions", () => {
    const realFetch = global.fetch;
    global.fetch = (u, o) => {
      if (String(u).indexOf("/api/code") >= 0) return new Promise(() => {});
      return realFetch(u, o);
    };
    global.sel = 3;
    global.cd = "";
    global.cdSlot = 3;
    global.act = "ir";
    paint();
    pick(6);
    const html = document.getElementById("ed").innerHTML;
    const status = html.indexOf("Loading the stored code.");
    const actions = html.indexOf('<div class=act><button type=button class=sec id=cc');
    const actionsEnd = html.indexOf("</div>", actions);
    if (actions < 0 || actionsEnd < 0 || status <= actionsEnd)
      throw new Error("the loading state is not below the code actions");
    global.fetch = realFetch;
  });
  step("empty IR code disables Copy and Apply until text arrives", () => {
    global.sel = 3;
    global.cd = " \t\n";
    global.cdSlot = 3;
    global.act = "ir";
    paint();
    const box = document.getElementById("ct");
    const copy = document.getElementById("cc");
    const apply = document.getElementById("ca");
    if (!copy.disabled || !apply.disabled)
      throw new Error("empty code enabled a code action");
    box.value = " \t\n";
    box.oninput();
    if (!copy.disabled || !apply.disabled)
      throw new Error("whitespace enabled a code action");
    box.value = "name: Home";
    box.oninput();
    if (copy.disabled || apply.disabled)
      throw new Error("typed code did not enable its actions");
    box.value = "";
    box.oninput();
    if (!copy.disabled || !apply.disabled)
      throw new Error("cleared code left an action enabled");
  });
  step("Paste fills a cleared input before it assigns a Zigbee device", () => {
    global.sel = 5;
    global.clip = null;
    global.clipBusy = false;
    paint();
    const copy = document.getElementById("bcopy");
    if (typeof copy.onclick !== "function") throw new Error("a Zigbee input has no Copy handler");
    copy.onclick();
    if (!clip || clip.kind !== "zigbee" || !clip.device || clip.act !== 3 || clip.val !== 32)
      throw new Error("the Zigbee assignment was not copied: " + JSON.stringify(clip));
    pick(3);
    const paste = document.getElementById("bpaste");
    if (typeof paste.onclick !== "function")
      throw new Error("a cleared input has no Paste handler");
    const bodies = [];
    const realFetch = global.fetch;
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    paste.onclick();
    if (bodies.length) throw new Error("Paste wrote before Assign: " + bodies[0]);
    if (act !== "zb" || zkv !== "d" || zhv !== "0x94deb8fffe9db81e" ||
        zpv !== "1" || zav !== 3 || zvv !== "32")
      throw new Error("Paste did not fill the device form");
    if (typeof document.getElementById("zi").onclick !== "function")
      throw new Error("Paste did not open the Zigbee panel");
    document.getElementById("zi").onclick();
    if (bodies.length !== 1 || bodies[0].indexOf("action=set_zigbee_device&slot=3") < 0 ||
        bodies[0].indexOf("ieee=0x94deb8fffe9db81e") < 0 || bodies[0].indexOf("act=3") < 0 ||
        bodies[0].indexOf("val=32") < 0)
      throw new Error("Assign sent the wrong device payload: " + bodies[0]);
    global.fetch = realFetch;
    global.zbusy = false;
  });
  step("Paste fills a Zigbee group before it assigns", () => {
    const realFetch = global.fetch;
    const bodies = [];
    global.tg = [{id: 4609, name: "Office Lamp", members: []}];
    global.clip = clipConfig(row(20));
    pick(3);
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    document.getElementById("bpaste").onclick();
    if (bodies.length) throw new Error("Paste wrote before Assign: " + bodies[0]);
    if (act !== "zb" || zkv !== "g" || zsv !== "4609" || zgv !== "4609" || zav !== 0 || zvv !== "")
      throw new Error("Paste did not fill the group form");
    document.getElementById("zi").onclick();
    global.fetch = realFetch;
    if (bodies.length !== 1 || bodies[0].indexOf("action=set_zigbee&slot=3") < 0 ||
        bodies[0].indexOf("group=4609") < 0 || bodies[0].indexOf("act=0") < 0 ||
        bodies[0].indexOf("name=Office%20Lamp") < 0)
      throw new Error("Assign sent the wrong group payload: " + bodies[0]);
    global.zbusy = false;
  });
  step("the title starts a full IR config copy", () => {
    global.sel = 6;
    global.clip = null;
    global.clipBusy = false;
    paint();
    const copy = document.getElementById("bcopy");
    if (typeof copy.onclick !== "function") throw new Error("an IR input has no Copy handler");
    copy.onclick();
    if (!clipBusy) throw new Error("IR Copy did not wait for the full code");
  });
  setTimeout(() => step("Paste fills an IR box before it applies", () => {
    if (!clip || clip.kind !== "ir" || clip.code !== CODE.text)
      throw new Error("the full IR code was not copied: " + JSON.stringify(clip));
    pick(3);
    const paste = document.getElementById("bpaste");
    if (typeof paste.onclick !== "function")
      throw new Error("an IR copy did not enable Paste on a cleared input");
    const bodies = [];
    const realFetch = global.fetch;
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    paste.onclick();
    if (bodies.length) throw new Error("Paste wrote before Apply: " + bodies[0]);
    if (act !== "ir" || cd !== CODE.text || cdSlot !== 3)
      throw new Error("Paste did not fill the IR code box");
    const code = document.getElementById("ct");
    code.value = CODE.text;
    document.getElementById("ca").onclick();
    global.fetch = realFetch;
    if (bodies.length !== 1 || bodies[0].indexOf("action=set_ir_code&slot=3") < 0 ||
        bodies[0].indexOf("code=name%3A%20Home") < 0)
      throw new Error("Apply sent the wrong IR payload: " + bodies[0]);
  }), 0);
  global.tg = [
    {id: 1, name: "all_light", members: ["0xaaa", "0xbbb"]},
    {id: 9, name: "c6 Office Lamp", members: ["0x94deb8fffe9db81e"]},
  ];
  global.td = [{ieee: "0x94deb8fffe9db81e", name: "Office Lamp",
                eps: {1: ["genOnOff", "genLevelCtrl"], 3: ["hvacThermostat"]}}];
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
  step("the endpoint follows the cluster the action needs", () => {
    const d = {endpoints: {
      "3": {clusters: {input: ["genOnOff"]}},
      "1": {clusters: {input: ["genBasic"]}},
      "2": {clusters: {input: ["genOnOff", "hvacThermostat"]}},
    }};
    const eps = epMap(d);
    if (epMap({}) !== null) throw new Error("a missing endpoint list must read as unknown");
    if (epForCluster(eps, "genOnOff") !== 2) throw new Error("expected 2, got " + epForCluster(eps, "genOnOff"));
    if (epForCluster(eps, "hvacThermostat") !== 2) throw new Error("the thermostat endpoint was missed");
    if (epForCluster(eps, "genScenes") !== 0) throw new Error("a cluster the device lacks returned an endpoint");
    if (commandable(epMap({endpoints: {"1": {clusters: {input: ["genBasic"]}}}})))
      throw new Error("a device that answers nothing stayed in the list");
    if (!commandable(eps)) throw new Error("a light was dropped from the list");
    // The picked device carries genLevelCtrl on 1 and hvacThermostat on 3.
    if (deviceEp("0x94deb8fffe9db81e", 3) !== 1) throw new Error("Brighter left endpoint 1");
    if (deviceEp("0x94deb8fffe9db81e", 11) !== 3) throw new Error("Warmer did not follow the thermostat");
    if (deviceEp("0xdeadbeefdeadbeef", 0) !== 1) throw new Error("an unknown device must fall back to 1");
  });
  step("the action list is the intersection of what the target accepts", () => {
    global.zkv = "d";
    global.zhv = "0x94deb8fffe9db81e";
    const names = zActions().map((x) => x.n).join(",");
    if (names.indexOf("Brighter") < 0) throw new Error("a dimmable light lost Brighter: " + names);
    if (names.indexOf("Recall scene") >= 0) throw new Error("a device with no scenes was offered one: " + names);
    global.zhv = "";
    if (zActions().length !== ZA.length) throw new Error("a typed address must offer every action");
    global.zkv = "g";
    global.zgv = "9";
    const grp = zActions().map((x) => x.n).join(",");
    if (grp.indexOf("Brighter") < 0) throw new Error("the group lost its member's actions: " + grp);
    global.zgv = "1";
    if (zActions().length !== ZA.length)
      throw new Error("a group with no known member must offer every action");
    global.zgv = "";
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
    global.zav = 0;
    global.zvv = "";
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

  step("the action and its value ride along with the target", () => {
    let body = null;
    const realFetch = global.fetch;
    global.fetch = (u, o) => { body = o && o.body; return realFetch(u, o); };
    global.sel = 20;
    global.zkv = "d";
    global.zhv = "0x94deb8fffe9db81e";
    global.zpv = "";
    global.zav = 3;   // Brighter
    global.zvv = "48";
    assignTarget();
    if (body.indexOf("act=3") < 0 || body.indexOf("val=48") < 0)
      throw new Error("the action did not reach the remote: " + body);
    // An empty box means the placeholder the panel showed.
    global.zvv = "";
    assignTarget();
    if (body.indexOf("val=32") < 0) throw new Error("the default value was not sent: " + body);
    // An action that takes no value sends none.
    global.zav = 0;
    assignTarget();
    if (body.indexOf("act=0&val=0") < 0) throw new Error("Toggle sent a value: " + body);
    global.zkv = "g";
    global.zgv = "4609";
    global.zav = 11;  // Warmer
    global.zvv = "5";
    assignTarget();
    if (body.indexOf("action=set_zigbee&") < 0 || body.indexOf("act=11") < 0)
      throw new Error("a group assign lost its action: " + body);
    global.fetch = realFetch;
  });
  step("a value outside the range of its action never reaches the remote", () => {
    let calls = 0;
    const realFetch = global.fetch;
    global.fetch = (u, o) => { calls++; return realFetch(u, o); };
    global.zkv = "d";
    global.zhv = "0x94deb8fffe9db81e";
    global.zav = 3;
    global.zvv = "900";
    assignTarget();
    global.fetch = realFetch;
    if (calls !== 0) throw new Error("a step of 900 was still sent");
    if (!bad || msg.indexOf("1 to 254") < 0) throw new Error("no clear refusal: " + msg);
    global.zav = 0;
    global.zvv = "";
  });
  step("the action selector rewires the endpoint and clears the old value", () => {
    global.sel = 20;
    global.act = "zb";
    global.zkv = "d";
    global.zhv = "0x94deb8fffe9db81e";
    global.zav = 3;
    global.zvv = "48";
    paint();
    const sw = document.getElementById("zt");
    if (!sw) throw new Error("no action selector");
    if (!document.getElementById("zv")) throw new Error("Brighter showed no value box");
    sw.value = "11";  // Warmer, which lives on another endpoint of this device.
    sw.onchange.call(sw);
    if (zav !== 11) throw new Error("the action did not follow the selector: " + zav);
    if (zvv !== "") throw new Error("the old value survived the switch: " + zvv);
    if (zpv !== "3") throw new Error("the endpoint did not follow the cluster: " + zpv);
    global.zav = 0;
    global.zvv = "";
    global.zpv = "";
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

  step("a named keyboard usage opens the list, and Custom opens the box", () => {
    pick(7);
    if (hcust) throw new Error("a named usage opened the custom box");
    const hp = document.getElementById("hp");
    if (!hp) throw new Error("no key list");
    if (document.getElementById("hu")) throw new Error("a named usage left the box open");
    if (els.ed.innerHTML.indexOf("<option value=0x04 selected>A</option>") < 0)
      throw new Error("the stored key was not selected: " + els.ed.innerHTML);
    hp.value = "custom";
    hp.onchange.call(hp);
    if (!hcust || !document.getElementById("hu")) throw new Error("Custom opened no usage box");
    const back = document.getElementById("hp");
    back.value = "0x28";
    back.onchange.call(back);
    if (hcust || huv !== "0x28") throw new Error("the named key did not win: " + huv);
    if (document.getElementById("hu")) throw new Error("the box survived the named key");
  });
  step("an unlisted usage reopens the custom box", () => {
    global.sel = 7;
    global.act = "hid";
    global.hkv = "consumer";
    global.huv = "0x0201";
    global.hcust = hidCustom(hkv, huv);
    paint();
    if (!hcust || !document.getElementById("hu")) throw new Error("an unlisted usage lost its box");
    const hu = document.getElementById("hu");
    if (!hu) throw new Error("no usage box");
  });

  step("the status line marks a live connection and the button offers Disconnect", () => {
    global.tg = [{id: 1, name: "all_light", members: []}];
    global.td = [{ieee: "0x94deb8fffe9db81e", name: "Office Lamp", ep: 1}];
    global.zerr = "";
    z2mStatus();
    // One line under the card heading carries the whole link state.
    const zt = document.getElementById("zsum");
    if (zt.innerHTML.indexOf("class=dot></span>Connected. 1 group, 1 device.") < 0)
      throw new Error("no live status: " + zt.innerHTML);
    const zc = document.getElementById("zc");
    if (zc.textContent !== "Disconnect") throw new Error("button stayed on Connect: " + zc.textContent);
    zc.onclick();
    if (tg !== null || td !== null) throw new Error("disconnect kept the lists");
    if (zc.textContent !== "Connect") throw new Error("button stayed on Disconnect: " + zc.textContent);
    if (zt.innerHTML.indexOf("dot off") < 0 || zt.innerHTML.indexOf("Not connected.") < 0)
      throw new Error("the line kept a live status: " + zt.innerHTML);
    global.zerr = "Could not reach Zigbee2MQTT at that address.";
    z2mStatus();
    if (zt.innerHTML.indexOf("dot bad") < 0 || zt.className.indexOf("bad") < 0)
      throw new Error("a failure did not reach the line: " + zt.innerHTML);
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
    if (cfgBusy) throw new Error("opening the card read the remote");
    if (codeReads) throw new Error("opening the card requested a stored code");
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
  step("the card keeps one config box and all actions", () => {
    global.cfgBusy = false;
    global.cfgOpen = true;
    global.cfgIn = "";
    cfgPaint();
    if (document.getElementById("cs")) throw new Error("the direction selector stayed");
    for (const id of ["cxr", "cxfp", "cxf", "cxc", "cxd", "cxa"])
      if (!document.getElementById(id)) throw new Error("the card has no " + id);
    document.getElementById("cxfp").onclick();
    if (!document.getElementById("cxf").clicked) throw new Error("Choose File did not open the picker");
    const box = document.getElementById("cx");
    box.value = cfgBlob();
    box.oninput.call(box);
    if (cfgIn !== box.value) throw new Error("the box did not keep its text");
    cfgPaint();
    if (cfgIn !== box.value) throw new Error("a repaint lost the text");
  });
  step("export downloads the current JSON config", () => {
    global.cfgBusy = false;
    global.cfgOpen = true;
    global.cfgAll = {6: CODE.text};
    global.cfgIn = cfgBlob();
    lastDownload = null; downloadedBlob = null; revokedUrl = null;
    cfgPaint();
    const button = document.getElementById("cxd");
    if (typeof button.onclick !== "function") throw new Error("export has no download handler");
    button.onclick();
    if (!lastDownload || lastDownload.download !== "c6remote-config.json" ||
        lastDownload.href !== "blob:config") throw new Error("download link is wrong");
    if (!downloadedBlob || downloadedBlob.type !== "application/json" ||
        downloadedBlob.parts[0] !== cfgIn) throw new Error("download body is wrong");
  });
  step("a JSON file picker validates and fills the import box", () => {
    global.cfgAll = {6: CODE.text};
    const valid = cfgBlob();
    global.cfgBusy = false;
    global.cfgOpen = true;
    global.cfgIn = "";
    cfgPaint();
    const picker = document.getElementById("cxf");
    if (typeof picker.onchange !== "function") throw new Error("import has no file handler");
    const realFetch = global.fetch;
    let writes = 0;
    global.fetch = (u, o) => { if (o && o.body) writes++; return realFetch(u, o); };
    picker.files = [{name: "remote.json", type: "application/json", size: valid.length, text: valid}];
    picker.onchange();
    global.fetch = realFetch;
    if (cfgIn !== valid || cfgBad || cfgMsg !== "Loaded remote.json.")
      throw new Error("valid JSON file was not loaded");
    if (writes) throw new Error("loading a file applied config automatically");
    cfgPaint();
    const wrongType = document.getElementById("cxf");
    wrongType.files = [{name: "remote.txt", type: "text/plain", size: valid.length, text: valid}];
    wrongType.onchange();
    if (!cfgBad || cfgIn !== valid) throw new Error("a non-JSON file changed the import");
    cfgPaint();
    const badJson = document.getElementById("cxf");
    badJson.files = [{name: "remote.json", type: "application/json", size: 9, text: "{not json"}];
    badJson.onchange();
    if (!cfgBad || cfgIn !== valid) throw new Error("invalid JSON changed the import");
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

  step("the Bluetooth line names the host and falls back without one", () => {
    global.st = STATE;
    bleStatus();
    const named = document.getElementById("bst").innerHTML;
    if (named.indexOf("connected to Landon&#39;s Mac") < 0 &&
        named.indexOf("connected to Landon's Mac") < 0)
      throw new Error("the host name is missing: " + named);
    STATE.ble.host = "";
    bleStatus();
    const plain = document.getElementById("bst").innerHTML;
    if (plain.indexOf("BLE HID: connected") < 0 || plain.indexOf("connected to") >= 0)
      throw new Error("an unread host name broke the line: " + plain);
    STATE.ble.host = "Landon's Mac";
  });

  setTimeout(() => process.exit(failed ? 1 : 0), 200);
}, 300);
