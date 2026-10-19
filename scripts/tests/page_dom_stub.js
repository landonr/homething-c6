// Runs the web page script outside a browser.
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
    value: "", className: "", disabled: false, hidden: false, onclick: null, oninput: null,
    set innerHTML(v) {
      this._html = v;
      this.children = [];
      // Drop the ids the previous markup declared before registering the new
      // ones. Without this a field that a repaint stopped rendering is still
      // found by getElementById, and a panel that hides a field looks the same
      // as one that still shows it.
      for (const id of this._ids) if (els[id] && els[id]._owner === this) delete els[id];
      this._ids = [];
      const re = /<[^>]*\bid=['"]?([A-Za-z0-9_-]+)['"]?[^>]*>/g;
      let m;
      while ((m = re.exec(v))) {
        const child = mk("stub");
        child._owner = this;
        child.disabled = /\sdisabled(?:\s|=|>)/.test(m[0]);
        const ap = /\saria-pressed=['"]?(true|false)['"]?/.exec(m[0]);
        if (ap) child.attrs["aria-pressed"] = ap[1];
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
for (const id of ["lnk", "lnb", "remote", "ed", "edpanel", "z2m", "bst", "bfr", "cfg", "cfgio",
                  "zsum", "zrs", "zrb", "zrw", "zpj", "zpjs", "zcs", "bhs", "brb", "brw",
                  "hab", "haw", "scb", "scw", "tabb", "tabc", "buttonstab", "configtab", "wfb", "wfd", "wfs", "has",
                  "wip", "dip", "wmac", "fwv", "bat", "devcfg", "slpcfg", "slw", "slb", "sls", "sla", "slr", "slap", "srw", "srb", "lgw", "lgb", "lgs", "blw", "blb", "bls", "rss", "rsb",
                  "dn", "dnr", "dnv", "dne", "dni", "dns", "dnc", "dnm"])
  els[id] = mk("section");
els.scb.checked = true;

const STATE = {
  busy: false, owner: "none", saves: 0, op_slot: 0, op_state: "off",
  status_leds: true, boot_leds: true,
  network: {wifi: true, wifi_enabled: true, wifi_always_on: false,
            home_assistant: true, api_gated: false, ip: "192.168.1.86", mac: "A4:CF:12:34:56:78"},
  sleep: {available: true, enabled: true, after_s: 300, replay: false},
  battery: {available: true, percent: 72, volts: 3.87},
  result_slot: 0, result: "none", action_id: 0, action_ok: false,
  radios: {zigbee: true, ble: true, home_assistant: true},
  zigbee: {started: true, paired: true, "new": false, gated: false,
           pairing: false, pair_left: 0, pair_failed: false, reach: "ok"},
  ble: {connected: true, bonded: true, pairing: false, host: "Landon's Mac"},
  name: "homeThing C6 13f498", default_name: "homeThing C6 13f498",
  slots: [
    {slot: 3, action: "none", pulses: 0, us: 0, code: "", fields: "", group: 0, name: ""},
    {slot: 6, action: "ir", pulses: 68, us: 61780, code: "0xE0E09E61", fields: "07 79", group: 0, name: "Home"},
    {slot: 4, action: "voice", pulses: 0, us: 0, code: "", fields: "", group: 0, name: ""},
    {slot: 5, action: "zigbee", pulses: 0, us: 0, code: "", fields: "", group: 0, ieee: "0x94deb8fffe9db81e", ep: 1, act: 3, val: 32, name: ""},
    {slot: 7, action: "hid", pulses: 0, us: 0, code: "", fields: "", group: 0, hid_kind: "keyboard", hid_usage: 4, hid_mod: 2, name: ""},
    {slot: 8, action: "ha", pulses: 0, us: 0, code: "", fields: "", group: 0, ha_kind: "light", ha_act: "brightness_up", ha_val: 10, ha_entity: "light.kitchen", name: ""},
    {slot: 20, action: "zigbee", pulses: 0, us: 0, code: "", fields: "", group: 4609, ieee: "", ep: 0, act: 0, val: 0, name: "Office Lamp"},
  ],
};

// The firmware always serves the four ha_ fields, empty when nothing is assigned.
for (const row of STATE.slots) {
  if (row.action !== "ha") Object.assign(row, {ha_kind: "", ha_act: "", ha_val: 0, ha_entity: ""});
}
STATE.ha = {pending: 0, last_slot: 0, last: "none", error: ""};

const body = mk("body");
const events = {};
body.classList = {
  _on: false,
  toggle(name, on) { this._on = !!on; body.className = on ? name : ""; },
  contains(name) { return this._on && name === "set-colors"; },
};
global.document = {
  body,
  getElementById: (id) => els[id] || null,
  createElement: (t) => mk(t),
  addEventListener: (type, callback) => { events[type] = callback; },
};
const windowEvents = {};
global.window = { addEventListener: (type, callback) => { windowEvents[type] = callback; } };
global.localStorage = {
  store: {},
  getItem(k) { return Object.prototype.hasOwnProperty.call(this.store, k) ? this.store[k] : null; },
  setItem(k, v) { this.store[k] = String(v); },
};
let confirmAsked = 0, confirmAnswer = true;
global.confirm = (text) => { confirmAsked++; confirmText = text; return confirmAnswer; };
let confirmText = "";
global.navigator = {};
let wsSent = [];
global.WebSocket = function () {
  this.readyState = 0;
  this.close = () => {};
  this.send = (text) => { wsSent.push(text); };
};
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

let activityCalls = 0;
global.fetch = (url) => {
  if (String(url).includes("/api/activity")) activityCalls++;
  return Promise.resolve({
  status: 200,
  ok: true,
  json: () => Promise.resolve(String(url).indexOf("/api/code") >= 0 ? CODE : STATE),
  text: () => Promise.resolve('{"ok":true,"id":1}'),
  });
};

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
  step("page open reports activity and state polls do not", () => {
    if (activityCalls !== 1) throw new Error("page open sent " + activityCalls + " activity requests");
    stateRefresh();
    if (activityCalls !== 1) throw new Error("state poll counted as activity");
  });
  step("click, touch, typing, and input changes report activity", () => {
    for (const type of ["click", "touchstart", "keydown", "input", "change"]) {
      if (!events[type]) throw new Error(type + " listener is missing");
      const before = activityCalls;
      global.activitySent = 0;
      events[type]();
      if (activityCalls !== before + 1) throw new Error(type + " did not report activity");
    }
  });
  step("startup preloads the IR code and current config", () => {
    if (cfgAll[6] !== CODE.text || !cfgReady) throw new Error("startup cache is incomplete");
    if (JSON.parse(cfgIn).slots.find(e => e.slot === 6).code !== CODE.text)
      throw new Error("current config did not include the code");
  });
  step("selecting cached IR makes no code request", () => {
    const realFetch = global.fetch;
    let reads = 0;
    global.fetch = (u, o) => { if (String(u).includes("/api/code")) reads++; return realFetch(u, o); };
    pick(6);
    if (cd !== CODE.text || reads) throw new Error("cached selection requested a code");
    global.fetch = realFetch;
  });
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
  step("assignment collection is gone and color switch remains", () => {
    if (document.getElementById("assignmentList") || document.getElementById("assignmentSummary"))
      throw new Error("assignment collection still present");
    if (!document.getElementById("scb") || !document.getElementById("scw"))
      throw new Error("assignment color switch was removed");
  });
   step("assignment color overlay switch toggles body class and storage", () => {
    if (!document.body.classList.contains("set-colors"))
      throw new Error("assignment colors start off");
    const box = document.getElementById("scb");
    box.checked = false;
    setColorsToggle();
    if (document.body.classList.contains("set-colors"))
      throw new Error("assignment colors stayed on");
    if (localStorage.getItem("c6.set-colors") !== "0")
      throw new Error("off choice was not stored");
    box.checked = true;
    setColorsToggle();
    if (!document.body.classList.contains("set-colors"))
      throw new Error("assignment colors stayed off");
    if (localStorage.getItem("c6.set-colors") !== "1")
       throw new Error("on choice was not stored");
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
    const html = document.getElementById("edpanel").innerHTML;
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
    delete cfgAll[6];
    global.cd = "";
    global.cdSlot = 3;
    global.act = "ir";
    paint();
    pick(6);
    const html = document.getElementById("edpanel").innerHTML;
    const status = html.indexOf("Loading the stored code.");
    const actions = html.indexOf('<div class=act><button type=button id=ca');
    const actionsEnd = html.indexOf("</div>", actions);
    if (actions < 0 || actionsEnd < 0 || status <= actionsEnd)
      throw new Error("the loading state is not below the code actions");
    global.fetch = realFetch;
    cfgAll[6] = CODE.text;
  });
  step("empty IR code disables Apply until text arrives", () => {
    global.sel = 3;
    global.cd = " \t\n";
    global.cdSlot = 3;
    global.act = "ir";
    paint();
    const box = document.getElementById("ct");
    const apply = document.getElementById("ca");
    if (!apply.disabled)
      throw new Error("empty code enabled a code action");
    box.value = " \t\n";
    box.oninput();
    if (!apply.disabled)
      throw new Error("whitespace enabled a code action");
    box.value = "name: Home";
    box.oninput();
    if (apply.disabled)
      throw new Error("typed code did not enable its actions");
    box.value = "";
    box.oninput();
    if (!apply.disabled)
      throw new Error("cleared code left an action enabled");
  });
  step("IR details precede code actions without a Now summary", () => {
    global.sel = 6;
    global.cd = CODE.text;
    global.cdSlot = 6;
    global.act = "ir";
    paint();
    const html = document.getElementById("edpanel").innerHTML;
    const details = html.indexOf("<dl class=info>");
    const actions = html.indexOf('<div class=act><button type=button id=ca');
    if (html.indexOf("Now:") >= 0) throw new Error("the current assignment summary remains");
    if (details < 0 || actions < 0 || details >= actions)
      throw new Error("IR details do not precede Apply");
  });
  step("accepted Paste immediately assigns a Zigbee device", () => {
    global.sel = 5;
    global.clip = null;
    global.clipBusy = false;
    paint();
    const copy = document.getElementById("bcopy");
    if (typeof copy.onclick !== "function") throw new Error("a Zigbee input has no Copy handler");
    copy.onclick();
    if (!clip || clip.kind !== "zigbee" || !clip.device || clip.act !== 3 || clip.val !== 32)
      throw new Error("the Zigbee assignment was not copied: " + JSON.stringify(clip));
    if (msg) throw new Error("Zigbee Copy showed a success notice: " + msg);
    pick(3);
    const paste = document.getElementById("bpaste");
    if (typeof paste.onclick !== "function")
      throw new Error("a cleared input has no Paste handler");
    const bodies = [];
    const realFetch = global.fetch;
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    confirmAnswer = true; confirmAsked = 0;
    paste.onclick();
    if (confirmAsked !== 1 || confirmText.indexOf("Button 5 to Button 3") < 0)
      throw new Error("Paste did not identify source and target: " + confirmText);
    if (bodies.length !== 1) throw new Error("accepted Paste did not write once");
    if (act !== "zb" || zkv !== "d" || zhv !== "0x94deb8fffe9db81e" ||
        zpv !== "1" || zav !== 3 || zvv !== "32")
      throw new Error("Paste did not fill the device form");
    if (bodies.length !== 1 || bodies[0].indexOf("action=set_zigbee_device&slot=3") < 0 ||
        bodies[0].indexOf("ieee=0x94deb8fffe9db81e") < 0 || bodies[0].indexOf("act=3") < 0 ||
        bodies[0].indexOf("val=32") < 0)
      throw new Error("Assign sent the wrong device payload: " + bodies[0]);
    global.fetch = realFetch;
    global.zbusy = false;
  });
  step("cancelled Paste changes nothing and sends nothing", () => {
    const realFetch = global.fetch;
    const bodies = [];
    global.tg = [{id: 4609, name: "Office Lamp", members: []}];
    global.clip = clipConfig(row(20));
    pick(3);
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    const before = {act, zkv, zsv, zgv, zav, zvv, msg, bad};
    confirmAnswer = false; confirmAsked = 0;
    document.getElementById("bpaste").onclick();
    if (confirmAsked !== 1) throw new Error("Paste did not ask for confirmation");
    if (bodies.length) throw new Error("cancelled Paste wrote: " + bodies[0]);
    for (const k of Object.keys(before)) if (global[k] !== before[k])
      throw new Error("cancelled Paste changed " + k);
    confirmAnswer = true;
    global.fetch = realFetch;
    global.zbusy = false;
  });
  step("accepted Paste immediately assigns BLE HID", () => {
    global.sel = 7;
    global.clip = null;
    global.clipBusy = false;
    paint();
    document.getElementById("bcopy").onclick();
    if (!clip || clip.kind !== "hid")
      throw new Error("the BLE HID assignment was not copied: " + JSON.stringify(clip));
    if (msg) throw new Error("BLE HID Copy showed a success notice: " + msg);
    pick(3);
    const bodies = [];
    const realFetch = global.fetch;
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    confirmAnswer = true; confirmAsked = 0;
    document.getElementById("bpaste").onclick();
    global.fetch = realFetch;
    if (confirmAsked !== 1) throw new Error("BLE HID Paste did not ask for confirmation");
    if (bodies.length !== 1 || bodies[0].indexOf("action=set_hid&slot=3") < 0 ||
        bodies[0].indexOf("kind=keyboard") < 0 || bodies[0].indexOf("usage=4") < 0 ||
        bodies[0].indexOf("mod=2") < 0)
      throw new Error("accepted BLE HID Paste sent the wrong payload: " + bodies[0]);
  });
  step("the Home Assistant panel offers the entity, kind, action and step fields", () => {
    pick(8);
    if (act !== "ha") throw new Error("a Home Assistant slot opened the " + act + " panel");
    if (hek !== "light.kitchen" || hkd !== "light" || hac !== "brightness_up" || hvl !== "10")
      throw new Error("pick did not load the saved action");
    const html = document.getElementById("edpanel").innerHTML;
    for (const id of ["he", "hd", "hc", "hs", "hg", "ht"])
      if (!document.getElementById(id)) throw new Error("the panel has no " + id);
    for (const text of ["placeholder=light.living_room", "autocapitalize=off", "autocorrect=off",
                        "spellcheck=false", "Any entity", "Input boolean", "Media player", "Brighten",
                        "Allow the device to perform Home Assistant actions", "first press after sleep"])
      if (html.indexOf(text) < 0) throw new Error("the panel lacks " + text);
    if (/id=hsw hidden/.test(html)) throw new Error("the step is hidden for Brighten");
    if (html.indexOf("value=brightness_down") < 0) throw new Error("light lost its Dim action");
    if (typeof document.getElementById("ht").onclick !== "function")
      throw new Error("a saved Home Assistant slot has no Test handler");
    pick(3); act = "ha"; paint();
    if (document.getElementById("ht")) throw new Error("an empty slot offers Test");
  });
  step("the action list follows the kind and the step shows only for Brighten and Dim", () => {
    pick(3); act = "ha"; hkd = "scene"; haFix(); paint();
    if (hac !== "turn_on" || haOpts().indexOf(">Activate<") < 0) throw new Error("scene reads " + haOpts());
    hkd = "script"; haFix(); hac = "turn_on";
    if (haOpts().indexOf(">Run<") < 0) throw new Error("script reads " + haOpts());
    hkd = "media_player"; haFix();
    if (haOpts().indexOf(">Previous track<") < 0 || haOpts().indexOf(">Toggle<") >= 0)
      throw new Error("media player reads " + haOpts());
    hkd = "light"; hac = "toggle"; paint();
    if (!/id=hsw hidden/.test(document.getElementById("edpanel").innerHTML))
      throw new Error("the step shows for Toggle");
    hac = "brightness_down"; paint();
    if (/id=hsw hidden/.test(document.getElementById("edpanel").innerHTML))
      throw new Error("the step is hidden for Dim");
  });
  step("typing an entity id lowercases it and selects the kind", () => {
    pick(3); act = "ha"; paint();
    const he = document.getElementById("he");
    he.value = "Switch.Porch"; he.oninput.call(he);
    if (hek !== "switch.porch" || he.value !== "switch.porch") throw new Error("the id was not lowercased: " + hek);
    if (hkd !== "switch") throw new Error("a switch id left the kind on " + hkd);
    hkd = "light"; hac = "brightness_up";
    he.value = "fan.bedroom"; he.oninput.call(he);
    if (hkd !== "fan" || haActs("fan").indexOf(hac) < 0)
      throw new Error("kind and action did not follow: " + hkd + " " + hac);
    he.value = "light.x"; he.oninput.call(he); hac = "brightness_up";
    he.value = "switch.x"; he.oninput.call(he);
    if (hac !== "toggle") throw new Error("an action the kind lacks stayed: " + hac);
    he.value = "vacuum.robot"; he.oninput.call(he);
    if (hkd !== "homeassistant") throw new Error("an unknown domain gave " + hkd);
    he.value = "vacuum"; he.oninput.call(he);
    if (hkd !== "homeassistant") throw new Error("a half typed id changed the kind to " + hkd);
  });
  step("the slot summary names the action, the step and the entity", () => {
    if (words(8) !== "HA: Brighten 10% light.kitchen") throw new Error("slot 8 reads " + words(8));
    const r = row(8), prev = Object.assign({}, r);
    Object.assign(r, {ha_kind: "light", ha_act: "toggle", ha_val: 0, ha_entity: "light.kitchen"});
    if (words(8) !== "HA: Toggle light.kitchen") throw new Error("a toggle reads " + words(8));
    Object.assign(r, {ha_kind: "scene", ha_act: "turn_on", ha_entity: "scene.movie"});
    if (words(8) !== "HA: Activate scene.movie") throw new Error("a scene reads " + words(8));
    Object.assign(r, prev);
    paint();
    if (keys[8].className.indexOf("set-ha") < 0) throw new Error("the tile has no HA colour class");
  });
  step("Assign checks the firmware rules before it posts", () => {
    const realFetch = global.fetch, bodies = [];
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    pick(3); act = "ha";
    hek = "switch.x"; hkd = "light"; hac = "toggle"; assignHa();
    if (!bad || msg.indexOf("its domain must match the kind") < 0) throw new Error("a kind mismatch gave: " + msg);
    hek = "light"; assignHa();
    if (msg.indexOf("an entity id is domain.object_id") < 0) throw new Error("a bare name gave: " + msg);
    hek = "light." + "a".repeat(60); assignHa();
    if (msg.indexOf("up to 64 characters") < 0) throw new Error("a long id gave: " + msg);
    hek = "light.kitchen"; hac = "brightness_up"; hvl = "0"; assignHa();
    if (msg !== "a brightness step is 1 to 100") throw new Error("step 0 gave: " + msg);
    hvl = "101"; assignHa();
    if (msg !== "a brightness step is 1 to 100") throw new Error("step 101 gave: " + msg);
    hvl = "abc"; assignHa();
    if (msg !== "a brightness step is 1 to 100") throw new Error("a letter step gave: " + msg);
    if (bodies.length) throw new Error("a bad entry was posted: " + bodies[0]);
    hvl = "25"; assignHa();
    if (bodies.length !== 1 || bodies[0] !== "action=set_ha&slot=3&kind=light&act=brightness_up&val=25&entity=light.kitchen")
      throw new Error("Assign sent: " + bodies[0]);
    hac = "toggle"; hvl = "25"; hek = " Light.Kitchen "; assignHa();
    if (bodies[1] !== "action=set_ha&slot=3&kind=light&act=toggle&val=0&entity=light.kitchen")
      throw new Error("a toggle did not send val 0 and a trimmed id: " + bodies[1]);
    global.fetch = realFetch;
  });
  step("accepted Paste immediately assigns a Home Assistant action", () => {
    global.sel = 8; global.clip = null; global.clipBusy = false;
    paint();
    document.getElementById("bcopy").onclick();
    if (!clip || clip.kind !== "ha" || clip.entity !== "light.kitchen" || clip.act !== "brightness_up")
      throw new Error("the Home Assistant assignment was not copied: " + JSON.stringify(clip));
    pick(3);
    const bodies = [], realFetch = global.fetch;
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    confirmAnswer = true; confirmAsked = 0;
    document.getElementById("bpaste").onclick();
    global.fetch = realFetch;
    if (confirmAsked !== 1 || confirmText.indexOf("Home Assistant config from Button 8") < 0)
      throw new Error("Paste did not name the config: " + confirmText);
    if (act !== "ha" || hek !== "light.kitchen") throw new Error("Paste did not fill the panel");
    if (bodies.length !== 1 || bodies[0] !== "action=set_ha&slot=3&kind=light&act=brightness_up&val=10&entity=light.kitchen")
      throw new Error("Paste sent: " + bodies[0]);
  });
  step("a backup carries Home Assistant actions out and back in", () => {
    global.cfgAll = {6: CODE.text};
    const e = JSON.parse(cfgBlob()).slots.find(x => x.slot === 8);
    if (e.action !== "ha" || e.kind !== "light" || e.act !== "brightness_up" || e.val !== 10 || e.entity !== "light.kitchen")
      throw new Error("the export holds " + JSON.stringify(e));
    if (cfgCheck(e)) throw new Error("the export did not read back: " + cfgCheck(e));
    const toggle = {slot: 8, action: "ha", kind: "switch", act: "toggle", entity: "switch.porch"};
    if (cfgCheck(toggle)) throw new Error("a toggle was refused: " + cfgCheck(toggle));
    for (const bad of [{entity: "light"}, {entity: "switch.x"}, {act: "open_cover"}, {kind: "tv"}, {val: 0}])
      if (!cfgCheck(Object.assign({}, e, bad))) throw new Error("a bad entry passed: " + JSON.stringify(bad));
    if (cfgParse(JSON.stringify({c6remote: 1, slots: [e]})).error) throw new Error("the parser refused an HA entry");
    const realFetch = global.fetch, bodies = [];
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    cfgSend(e); cfgSend(toggle);
    global.fetch = realFetch;
    if (bodies[0] !== "action=set_ha&slot=8&kind=light&act=brightness_up&val=10&entity=light.kitchen")
      throw new Error("the restore sent: " + bodies[0]);
    if (bodies[1] !== "action=set_ha&slot=8&kind=switch&act=toggle&val=0&entity=switch.porch")
      throw new Error("a toggle restore sent: " + bodies[1]);
  });
  step("the title starts a full IR config copy", () => {
    global.sel = 6;
    global.clip = null;
    global.clipBusy = false;
    paint();
    const copy = document.getElementById("bcopy");
    if (typeof copy.onclick !== "function") throw new Error("an IR input has no Copy handler");
    const realFetch = global.fetch;
    let reads = 0;
    global.fetch = (u, o) => { if (String(u).includes("/api/code")) reads++; return realFetch(u, o); };
    copy.onclick();
    global.fetch = realFetch;
    if (clipBusy || reads || !clip || clip.code !== CODE.text)
      throw new Error("IR Copy did not use cached code");
  });
  setTimeout(() => step("accepted Paste immediately applies an IR code", () => {
    if (!clip || clip.kind !== "ir" || clip.code !== CODE.text)
      throw new Error("the full IR code was not copied: " + JSON.stringify(clip));
    if (msg) throw new Error("IR Copy showed a success notice: " + msg);
    pick(3);
    const paste = document.getElementById("bpaste");
    if (typeof paste.onclick !== "function")
      throw new Error("an IR copy did not enable Paste on a cleared input");
    const bodies = [];
    const realFetch = global.fetch;
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    confirmAnswer = true; confirmAsked = 0;
    paste.onclick();
    if (confirmAsked !== 1) throw new Error("IR Paste did not ask for confirmation");
    if (bodies.length !== 1) throw new Error("accepted IR Paste did not write once");
    if (act !== "ir" || cd !== CODE.text || cdSlot !== 3)
      throw new Error("Paste did not fill the IR code box");
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
    global.sel = 19;
    for (const a of ["ir", "zb", "va", "cl"]) {
      global.act = a;
      paint();
      if (!document.getElementById("as")) throw new Error(a + " painted no selector");
    }
  });
  step("the voice panel is not offered on a slot without it", () => {
    global.sel = 20;  // SW1 owns the hold gesture, so it has no voice action.
    global.act = "va";
    paint();
    if (act === "va") throw new Error("voice stayed selected on a slot without it");
  });
  step("switching the selector repaints", () => {
    global.sel = 19;
    global.act = "ir";
    global.clipBusy = false;
    paint();
    const zb = document.getElementById("as-zb");
    if (!zb || typeof zb.onclick !== "function") throw new Error("no Zigbee option");
    zb.onclick.call(zb);
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
    if (els.edpanel.innerHTML.indexOf("<option value=0x04 selected>A</option>") < 0)
      throw new Error("the stored key was not selected: " + els.edpanel.innerHTML);
    hp.value = "custom";
    hp.onchange.call(hp);
    if (!hcust || !document.getElementById("hu")) throw new Error("Custom opened no usage box");
    const back = document.getElementById("hp");
    back.value = "0x28";
    back.onchange.call(back);
    if (hcust || huv !== "0x28") throw new Error("the named key did not win: " + huv);
    if (document.getElementById("hu")) throw new Error("the box survived the named key");
  });
  step("modifier checkboxes prefill from either hand and post the left bits", () => {
    const html = () => els.edpanel.innerHTML;
    global.sel = 7; global.act = "hid"; global.hkv = "keyboard"; global.huv = "0x04";
    global.hcust = false;
    // 0x80 is right GUI.
    global.hmv = "128";
    paint();
    for (const [id, v] of [["hmc", 1], ["hms", 2], ["hma", 4], ["hmg", 8]])
      if (html().indexOf("<label for=" + id + "><input type=checkbox id=" + id + " value=" + v) < 0)
        throw new Error("missing checkbox " + id + ": " + html());
    if (html().indexOf("id=hmg value=8 checked") < 0 || /id=hm[csa] value=\d checked/.test(html()))
      throw new Error("a right-hand GUI bit did not check only Cmd: " + html());
    if (document.getElementById("hm")) throw new Error("the free-text mask is back");
    global.hmv = "0";
    paint();
    if (/id=hm[csag] value=\d+ checked/.test(html())) throw new Error("a zero mask checked a box");
    for (const [id, v] of [["hmc", 1], ["hms", 2], ["hma", 4], ["hmg", 8]]) {
      const b = document.getElementById(id); b.value = String(v); b.checked = false;
    }
    document.getElementById("hmc").checked = true;
    document.getElementById("hmg").checked = true;
    document.getElementById("hmc").onchange();
    if (hmv !== "9") throw new Error("Ctrl and Cmd built " + hmv);
    paint();
    if (html().indexOf("id=hmc value=1 checked") < 0 || html().indexOf("id=hmg value=8 checked") < 0)
      throw new Error("the repaint dropped the checked boxes: " + html());
    const bodies = [];
    const realFetch = global.fetch;
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    global.hmv = "153";
    assignHid();
    global.fetch = realFetch;
    if (bodies.length !== 1 || bodies[0].indexOf("mod=9") < 0)
      throw new Error("the posted mask was not the left bits 9: " + bodies[0]);
  });
  step("hidWords names the modifiers", () => {
    const w = hidWords("keyboard", 4, 0x13);
    if (w !== "keyboard A, Ctrl+Shift") throw new Error("wrong words: " + w);
    if (hidWords("keyboard", 4, 0x88) !== "keyboard A, Cmd") throw new Error("right bit unnamed");
    if (hidWords("keyboard", 4, 0) !== "keyboard A") throw new Error("empty mask added text");
    if (hidWords("keyboard", 0, 4) !== "keyboard Alt") throw new Error("modifier-only wrong");
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
    // One line under the inputs carries the whole link state.
    const zt = document.getElementById("zsum");
    if (zt.innerHTML.indexOf("class=dot></span>This browser is connected to Zigbee2MQTT. 1 group, 1 device.") < 0)
      throw new Error("no live status: " + zt.innerHTML);
    const zc = document.getElementById("zc");
    if (zc.textContent !== "Disconnect") throw new Error("button stayed on Connect: " + zc.textContent);
    zc.onclick();
    if (tg !== null || td !== null) throw new Error("disconnect kept the lists");
    if (zc.textContent !== "Connect") throw new Error("button stayed on Disconnect: " + zc.textContent);
    if (zt.innerHTML.indexOf("dot off") < 0 ||
        zt.innerHTML.indexOf("This browser is not connected") < 0)
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
  step("the export names the firmware only when the state carries one", () => {
    const prevSt = global.st;
    global.cfgAll = {6: CODE.text};
    global.st = Object.assign({}, prevSt, {firmware: "2026.10.0"});
    const withFw = cfgBlob();
    if (withFw.indexOf('{"c6remote":1,"firmware":"2026.10.0","settings":') !== 0)
      throw new Error("firmware missing from the export: " + withFw.slice(0, 80));
    if (JSON.parse(withFw).firmware !== "2026.10.0") throw new Error("firmware did not parse");
    global.st = Object.assign({}, prevSt);
    delete global.st.firmware;
    if (cfgBlob().indexOf("firmware") >= 0) throw new Error("firmware shown with no state value");
    global.st = Object.assign({}, prevSt, {firmware: ""});
    if (cfgBlob().indexOf("firmware") >= 0) throw new Error("an empty firmware was exported");
    global.st = prevSt;
  });
  step("an import ignores the firmware key", () => {
    const text = JSON.stringify({c6remote: 1, firmware: "2026.10.1-dirty", slots: [{slot: 4, action: "voice"}]});
    const r = cfgParse(text);
    if (r.error) throw new Error("a file with firmware was refused: " + r.error);
    const plain = cfgParse(JSON.stringify({c6remote: 1, slots: [{slot: 4, action: "voice"}]}));
    if (plain.error) throw new Error("a file without firmware was refused: " + plain.error);
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
  step("the card keeps one config box and all actions", () => {
    global.cfgBusy = false;
    global.cfgOpen = true;
    global.cfgIn = "";
    cfgPaint();
    if (document.getElementById("cs")) throw new Error("the direction selector stayed");
    if (document.getElementById("cxr")) throw new Error("the Read button stayed");
    for (const id of ["cxfp", "cxf", "cxc", "cxd", "cxa"])
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
  step("a radio switch marks its inputs and keeps their assignment", () => {
    global.st.radios = {zigbee: false, ble: true};
    paint();
    // Slot 20 sends Zigbee, slot 7 sends HID, and slot 6 is an IR code.
    if (keys[20].className.indexOf("rf") < 0) throw new Error("a held Zigbee input is not marked");
    if (keys[7].className.indexOf("rf") >= 0) throw new Error("a live HID input was marked");
    if (keys[6].className.indexOf("rf") >= 0) throw new Error("an IR input was marked");
    if (keys[20].lastChild.textContent.indexOf("Office Lamp") < 0)
      throw new Error("a held input lost its assignment text");
    if (document.getElementById("zrs").innerHTML.indexOf("Zigbee radio is off") < 0)
      throw new Error("the Zigbee card does not report the switch");
    if (document.getElementById("zrb").checked !== false)
      throw new Error("the Zigbee switch is in the wrong position");
    if (document.getElementById("brb").checked !== true)
      throw new Error("the Bluetooth switch is in the wrong position");
    // A live radio still writes its own line, so nothing on the page moves.
    if (document.getElementById("bst").innerHTML.indexOf("BLE HID: radio on.") < 0)
      throw new Error("a live radio wrote no status line");
    global.sel = 20;
    paint();
    if (document.getElementById("ed").innerHTML.indexOf("radio is off, so this input is disabled") < 0)
      throw new Error("the editor gives no reason for a held input");
    global.sel = null;
  });
  // The stub keeps the disabled flag of an element but not its title, so this
  // reads one Action option out of the editor markup.
  const actionTag = id => {
    const m = new RegExp("<button[^>]*\\sid=as-" + id + "\\s[^>]*>").exec(document.getElementById("ed").innerHTML);
    if (!m) throw new Error("the Action list has no " + id + " option");
    return m[0];
  };
  step("an off Config switch grays out only its own actions and names the switch", () => {
    const saved = global.st.radios;
    global.zbusy = false; global.clipBusy = false;
    // Voice runs over the Home Assistant API, so that switch grays out two actions.
    for (const [radio, ids, tip] of [["zigbee", ["zb"], "Turn on Zigbee in Config"],
                                     ["ble", ["hid"], "Turn on Bluetooth in Config"],
                                     ["home_assistant", ["ha", "va"], "Turn on Home Assistant in Config"]]) {
      global.st.radios = {zigbee: true, ble: true, home_assistant: true};
      global.st.radios[radio] = false;
      global.sel = 19; global.act = "ir";
      paint();
      for (const other of ["ir", "zb", "hid", "ha", "va", "cl"]) {
        const off = ids.includes(other), tag = actionTag(other);
        if (document.getElementById("as-" + other).disabled !== off)
          throw new Error(radio + " off left " + other + (off ? " enabled" : " disabled"));
        if (off && tag.indexOf(" title='" + tip + "'") < 0)
          throw new Error(radio + " off gave " + other + " no reason: " + tag);
        if (!off && tag.indexOf("title=") >= 0)
          throw new Error(radio + " off put a reason on " + other + ": " + tag);
      }
    }
    global.st.radios = saved;
    global.sel = null;
    paint();
  });
  step("an input whose action needs an off switch opens on IR and recovers when it is on", () => {
    const saved = global.st.radios;
    global.zbusy = false; global.clipBusy = false;
    for (const [radio, slot, id] of [["zigbee", 5, "zb"], ["ble", 7, "hid"], ["home_assistant", 8, "ha"],
                                     ["home_assistant", 4, "va"]]) {
      global.st.radios = {zigbee: true, ble: true, home_assistant: true};
      pick(slot);
      if (act !== id) throw new Error("slot " + slot + " opened " + act + " with every switch on");
      global.st.radios[radio] = false;
      paint();
      if (act !== "ir") throw new Error("a repaint left slot " + slot + " on " + act + " with " + radio + " off");
      if (actionTag("ir").indexOf("aria-checked=true") < 0 ||
          document.getElementById("edpanel").innerHTML.indexOf("<h2>IR code</h2>") !== 0)
        throw new Error("slot " + slot + " did not show the IR panel with " + radio + " off");
      pick(slot);
      if (act !== "ir") throw new Error("slot " + slot + " opened on " + act + " with " + radio + " off");
      global.st.radios[radio] = true;
      paint();
      if (document.getElementById("as-" + id).disabled || actionTag(id).indexOf("title=") >= 0)
        throw new Error("switching " + radio + " back on left " + id + " grayed out");
    }
    global.st.radios = saved;
    global.sel = null;
    paint();
  });
  step("a radio switch posts the new state to the remote", () => {
    global.st.radios = {zigbee: true, ble: true};
    paint();
    const realFetch = global.fetch;
    let body = "";
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    document.getElementById("zrb").onchange();
    global.fetch = realFetch;
    if (body.indexOf("action=set_radio") < 0 || body.indexOf("radio=zigbee") < 0 ||
        body.indexOf("on=0") < 0) throw new Error("the switch posted " + body);
    if (!document.getElementById("zrb").disabled)
      throw new Error("the switch stayed live while the remote answered");
    // The write is still open, so the switch holds where the user left it.
    if (document.getElementById("zrb").checked !== false)
      throw new Error("the switch snapped back during the write");
    global.radioBusy = {zigbee: false, ble: false};
  });
  step("WiFi Always On shows saved default and current Wi-Fi separately", () => {
    global.st = STATE;
    STATE.network.wifi_always_on = false;
    STATE.network.wifi_enabled = true;
    STATE.network.wifi = false;
    networkStatus();
    if (document.getElementById("wfb").checked) throw new Error("saved default showed on");
    if (!document.getElementById("wfs").innerHTML.includes("on but disconnected"))
      throw new Error("enabled Wi-Fi showed as off");
    STATE.network.wifi_always_on = true;
    STATE.network.wifi_enabled = false;
    networkStatus();
    if (!document.getElementById("wfb").checked) throw new Error("saved default showed off");
    if (!document.getElementById("wfs").innerHTML.includes("Wi-Fi is off"))
      throw new Error("disabled Wi-Fi showed as connected");
    STATE.network.wifi_always_on = false;
    STATE.network.wifi_enabled = true;
    STATE.network.wifi = true;
    networkStatus();
  });
  step("the Home Assistant line names a switch that this boot does not follow yet", () => {
    const prevSt = global.st, prevRadios = STATE.radios;
    global.st = STATE;
    const line = () => document.getElementById("has").innerHTML;
    const show = (on, gated, connected) => {
      STATE.radios = {zigbee: true, ble: true, home_assistant: on};
      STATE.network.api_gated = gated;
      STATE.network.home_assistant = connected;
      networkStatus();
      return line();
    };
    // On, but the switch was off at boot, so the API server never started.
    let text = show(true, true, false);
    if (text.indexOf("The API is off. Restart the remote to start it.") < 0)
      throw new Error("a gated API reads " + text);
    if (text.indexOf("dot bad") < 0) throw new Error("a gated API has no fault dot: " + text);
    // Off, but the API server started this boot and runs until the next one.
    text = show(false, false, true);
    if (text.indexOf("Home Assistant is off.") < 0 || text.indexOf("The API stops at the next restart.") < 0)
      throw new Error("a running API with the switch off reads " + text);
    if (text.indexOf("dot warn") < 0) throw new Error("a pending stop has no warn dot: " + text);
    // The two agree, so neither restart note shows.
    text = show(false, true, false);
    if (text.indexOf("Home Assistant is off.") < 0 || text.indexOf("restart") >= 0)
      throw new Error("an off switch and a stopped API read " + text);
    text = show(true, false, true);
    if (text.indexOf("Home Assistant API is connected.") < 0 || text.indexOf("estart") >= 0)
      throw new Error("an on switch and a running API read " + text);
    STATE.radios = prevRadios;
    STATE.network.api_gated = false;
    STATE.network.home_assistant = true;
    global.st = prevSt;
    networkStatus();
  });
  step("an off Home Assistant switch marks its inputs and keeps their assignment", () => {
    const prevRadios = global.st.radios;
    global.st.radios = {zigbee: true, ble: true, home_assistant: false};
    global.sel = null;
    paint();
    // Slot 8 sends a Home Assistant action, slot 20 Zigbee, and slot 6 IR.
    if (keys[8].className.indexOf("rf") < 0) throw new Error("a held Home Assistant input is not marked");
    if (keys[20].className.indexOf("rf") >= 0) throw new Error("a live Zigbee input was marked");
    if (keys[6].className.indexOf("rf") >= 0) throw new Error("an IR input was marked");
    global.sel = 8;
    paint();
    if (document.getElementById("ed").innerHTML.indexOf(
        "Home Assistant is off, so this input is disabled. The assignment is kept.") < 0)
      throw new Error("the editor gives no reason for a held Home Assistant input");
    global.st.radios = prevRadios;
    global.sel = null;
    paint();
  });
  step("an off Home Assistant switch holds a voice input and grays out Voice assistant", () => {
    const prevRadios = global.st.radios;
    global.zbusy = false; global.clipBusy = false;
    global.st.radios = {zigbee: true, ble: true, home_assistant: false};
    global.sel = null;
    paint();
    // Slot 4 holds the voice assistant, and slot 6 an IR code.
    if (keys[4].className.indexOf("rf") < 0) throw new Error("a held voice input is not marked");
    if (keys[4].lastChild.textContent !== "Voice assistant")
      throw new Error("a held voice input lost its assignment text: " + keys[4].lastChild.textContent);
    if (keys[6].className.indexOf("rf") >= 0) throw new Error("an IR input was marked");
    pick(4);
    if (act !== "ir") throw new Error("a held voice input opened on " + act);
    if (document.getElementById("ed").innerHTML.indexOf(
        "Home Assistant is off, so this input is disabled. The assignment is kept.") < 0)
      throw new Error("the editor gives no reason for a held voice input");
    if (!document.getElementById("as-va").disabled ||
        actionTag("va").indexOf(" title='Turn on Home Assistant in Config'") < 0)
      throw new Error("Voice assistant is live with Home Assistant off: " + actionTag("va"));
    global.st.radios = {zigbee: true, ble: true, home_assistant: true};
    paint();
    if (keys[4].className.indexOf("rf") >= 0) throw new Error("a live voice input stayed marked");
    if (document.getElementById("as-va").disabled) throw new Error("Voice assistant stayed grayed out");
    global.st.radios = prevRadios;
    global.sel = null;
    paint();
  });
  step("the Firmware row shows the served version or Unknown", () => {
    const prevSt = global.st;
    global.st = STATE;
    STATE.firmware = "2026.10.1-dirty";
    networkStatus();
    if (document.getElementById("fwv").textContent !== "2026.10.1-dirty")
      throw new Error("firmware row showed " + document.getElementById("fwv").textContent);
    delete STATE.firmware;
    networkStatus();
    if (document.getElementById("fwv").textContent !== "Unknown")
      throw new Error("missing firmware showed " + document.getElementById("fwv").textContent);
    global.st = prevSt;
  });
  step("WiFi Always On switch posts the next boot preference", () => {
    global.st = STATE;
    const realFetch = global.fetch;
    let body = "";
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    document.getElementById("wfb").checked = true;
    document.getElementById("wfb").onchange();
    global.fetch = realFetch;
    if (!body.includes("action=set_wifi_always_on") || !body.includes("enabled=1"))
      throw new Error("switch posted " + body);
    if (!document.getElementById("wfb").disabled || !document.getElementById("wfb").checked)
      throw new Error("switch lost pending preference");
    global.wifiBusy = false;
  });
  step("Status LEDs switch shows the stored state and posts the change", () => {
    const prevSt = global.st;
    global.st = STATE;
    STATE.status_leds = false;
    ledStatus();
    if (document.getElementById("lgb").checked) throw new Error("off showed on");
    if (!document.getElementById("lgs").innerHTML.includes("stay dark") ||
        !document.getElementById("lgs").innerHTML.includes("A radio switch still gives one pulse.") ||
        !document.getElementById("lgs").innerHTML.includes("Hold Button 8 for one second to see the status."))
      throw new Error("off line is wrong: " + document.getElementById("lgs").innerHTML);
    STATE.status_leds = true;
    ledStatus();
    if (!document.getElementById("lgb").checked) throw new Error("on showed off");
    const realFetch = global.fetch;
    let body = "";
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    document.getElementById("lgb").checked = false;
    document.getElementById("lgb").onchange();
    global.fetch = realFetch;
    if (!body.includes("action=set_status_leds") || !body.includes("enabled=0"))
      throw new Error("switch posted " + body);
    if (!document.getElementById("lgb").disabled || document.getElementById("lgb").checked)
      throw new Error("switch lost pending state");
    global.ledBusy = false;
    global.st = prevSt;
  });
  step("Boot and wake LEDs switch shows the stored state and posts the change", () => {
    const prevSt = global.st;
    global.st = STATE;
    STATE.boot_leds = false;
    bootLedStatus();
    if (document.getElementById("blb").checked) throw new Error("off showed on");
    if (!document.getElementById("bls").innerHTML.includes("do not play"))
      throw new Error("off line is wrong: " + document.getElementById("bls").innerHTML);
    STATE.boot_leds = true;
    bootLedStatus();
    if (!document.getElementById("blb").checked) throw new Error("on showed off");
    const realFetch = global.fetch;
    let body = "";
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    document.getElementById("blb").checked = false;
    document.getElementById("blb").onchange();
    global.fetch = realFetch;
    if (!body.includes("action=set_boot_leds") || !body.includes("enabled=0"))
      throw new Error("switch posted " + body);
    if (!document.getElementById("blb").disabled || document.getElementById("blb").checked)
      throw new Error("switch lost pending state");
    global.bootBusy = false;
    global.st = prevSt;
  });
  step("the sleep block shows only with idle_sleep and names its state", () => {
    global.st = STATE;
    const block = document.getElementById("slpcfg");
    const box = document.getElementById("slb");
    const minutes = document.getElementById("sla");
    const line = document.getElementById("sls");
    STATE.sleep = {available: false, enabled: false, after_s: 0};
    sleepStatus();
    if (!block.hidden) throw new Error("the block showed without idle_sleep");
    STATE.sleep = {available: true, enabled: true, after_s: 300};
    paint();
    if (block.hidden) throw new Error("the block stayed hidden");
    if (!box.checked || box.disabled) throw new Error("the switch does not show sleep on");
    if (minutes.value !== "5" || minutes.disabled) throw new Error("minutes showed " + minutes.value);
    if (document.getElementById("slap").disabled) throw new Error("Apply stayed disabled");
    if (!line.innerHTML.includes("Sleep is on. The remote sleeps after 5 minutes without a press."))
      throw new Error("the on line reads " + line.innerHTML);
    STATE.sleep = {available: true, enabled: false, after_s: 90};
    sleepStatus();
    if (box.checked) throw new Error("the switch does not show sleep off");
    if (!line.innerHTML.includes("Sleep is off. The remote stays awake."))
      throw new Error("the off line reads " + line.innerHTML);
    STATE.sleep.enabled = true;
    sleepStatus();
    if (!line.innerHTML.includes("after 90 seconds") || minutes.value !== "2")
      throw new Error("a YAML default in seconds reads " + line.innerHTML + " / " + minutes.value);
    STATE.sleep = {available: true, enabled: true, after_s: 300};
    sleepStatus();
  });
  step("the battery line shows percent and volts and names a missing reading", () => {
    global.st = STATE;
    const line = document.getElementById("bat");
    paint();
    if (line.textContent !== "Battery 72 % (3.87 V)") throw new Error("the battery line reads " + line.textContent);
    STATE.battery = {available: false, percent: 0, volts: 0};
    batteryStatus();
    if (line.textContent !== "Battery reading is not available.")
      throw new Error("the battery line did not name a missing reading: " + line.textContent);
    delete STATE.battery;
    batteryStatus();
    if (line.textContent !== "Battery reading is not available.")
      throw new Error("the battery line did not name a missing battery block: " + line.textContent);
    if (line.hidden) throw new Error("the battery line hid");
    STATE.battery = {available: true, percent: 72, volts: 3.87};
    batteryStatus();
    if (line.textContent !== "Battery 72 % (3.87 V)") throw new Error("the battery line did not return");
  });
  step("the Settings card shows the IP address", () => {
    const saved = global.st;
    const dip = document.getElementById("dip");
    global.st = {network: {ip: "192.168.1.50"}};
    networkStatus();
    if (dip.textContent !== "192.168.1.50") throw new Error("dip reads " + dip.textContent);
    global.st = {network: {ip: ""}};
    networkStatus();
    if (dip.textContent !== "Unavailable") throw new Error("dip empty reads " + dip.textContent);
    global.st = saved;
  });
  step("the sleep switch posts the new state and holds it during the write", () => {
    global.st = STATE;
    const realFetch = global.fetch;
    let body = "";
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    document.getElementById("slb").checked = false;
    document.getElementById("slb").onchange();
    global.fetch = realFetch;
    if (!body.includes("action=set_sleep_enabled") || !body.includes("enabled=0"))
      throw new Error("switch posted " + body);
    if (!document.getElementById("slb").disabled || document.getElementById("slb").checked)
      throw new Error("switch lost the pending state");
    if (!document.getElementById("sla").disabled) throw new Error("minutes stayed live during the write");
    if (!document.getElementById("slap").disabled) throw new Error("Apply stayed live during the write");
    global.sleepBusy = false;
    sleepStatus();
  });
  step("the wake press switch reflects the state and posts the new value", () => {
    global.st = STATE;
    global.sleepBusy = false;
    sleepStatus();
    const box = document.getElementById("srb");
    if (box.checked || box.disabled) throw new Error("the wake press switch did not start off and live");
    STATE.sleep.replay = true;
    sleepStatus();
    if (!box.checked) throw new Error("the wake press switch ignored replay true");
    const realFetch = global.fetch;
    let body = "";
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    box.checked = false;
    box.onchange();
    global.fetch = realFetch;
    if (!body.includes("action=set_sleep_replay") || !body.includes("enabled=0"))
      throw new Error("wake press switch posted " + body);
    if (!box.disabled || box.checked) throw new Error("wake press switch lost the pending state");
    if (!document.getElementById("slb").checked) throw new Error("the sleep switch lost its value");
    global.sleepBusy = false;
    STATE.sleep.replay = false;
    sleepStatus();
  });
  step("the minutes box posts seconds and refuses a value outside 1 to 60", () => {
    global.st = STATE;
    const realFetch = global.fetch;
    const bodies = [];
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    const minutes = document.getElementById("sla");
    for (const bad of ["0", "61", "2.5", "", "5m"]) {
      minutes.value = bad;
      document.getElementById("slap").onclick();
      if (bodies.length) throw new Error(JSON.stringify(bad) + " posted " + bodies[0]);
      if (!document.getElementById("sls").className.includes("bad") ||
          !document.getElementById("sls").innerHTML.includes("Enter whole minutes from 1 to 60."))
        throw new Error(JSON.stringify(bad) + " gave no reason");
    }
    minutes.value = "12";
    document.getElementById("slap").onclick();
    global.fetch = realFetch;
    if (bodies.length !== 1 || !bodies[0].includes("action=set_sleep_after") ||
        !bodies[0].includes("seconds=720"))
      throw new Error("minutes posted " + bodies.join(" | "));
    if (document.getElementById("sls").className.includes("bad"))
      throw new Error("a good value kept the old error");
    global.sleepBusy = false;
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    minutes.value = "7";
    minutes.onkeydown({key: "a"});
    if (bodies.length !== 1) throw new Error("another key posted " + bodies[1]);
    minutes.onkeydown({key: "Enter"});
    global.fetch = realFetch;
    if (bodies.length !== 2 || !bodies[1].includes("action=set_sleep_after") ||
        !bodies[1].includes("seconds=420"))
      throw new Error("Enter posted " + bodies.join(" | "));
    global.sleepBusy = false;
    sleepStatus();
  });
  step("Restart asks first, and a refusal sends nothing", () => {
    global.st = STATE;
    const realFetch = global.fetch;
    let body = null;
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    confirmAsked = 0; confirmAnswer = false;
    document.getElementById("rsb").onclick();
    global.fetch = realFetch;
    confirmAnswer = true;
    if (confirmAsked !== 1) throw new Error("the restart did not ask");
    if (confirmText.indexOf("Restart the remote?") < 0) throw new Error("the question reads " + confirmText);
    if (body !== null) throw new Error("a refused confirm still posted: " + body);
    if (document.getElementById("rsb").disabled) throw new Error("a refused confirm locked the button");
    if (document.getElementById("rss").hidden !== true || document.getElementById("rss").innerHTML !== "")
      throw new Error("the idle line shows " + document.getElementById("rss").innerHTML);
  });
  step("an accepted restart posts restart and locks the button", () => {
    global.st = STATE;
    const realFetch = global.fetch;
    let body = null;
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    confirmAsked = 0; confirmAnswer = true;
    const button = document.getElementById("rsb");
    button.onclick();
    if (confirmAsked !== 1) throw new Error("the restart did not ask");
    if (body !== "action=restart") throw new Error("the restart posted " + body);
    if (!button.disabled || button.textContent !== "Restarting...")
      throw new Error("the button stayed live during the restart");
    if (document.getElementById("rss").hidden || document.getElementById("rss").innerHTML.indexOf("The page asked the remote to restart.") < 0)
      throw new Error("the open press reads " + document.getElementById("rss").innerHTML);
    // A second press while the first is open sends nothing and asks nothing.
    body = null; confirmAsked = 0;
    button.onclick();
    global.fetch = realFetch;
    if (body !== null || confirmAsked !== 0) throw new Error("a second press posted " + body);
  });
  step("Forget asks first, and a refusal sends nothing", () => {
    global.st = STATE;
    paint();
    const realFetch = global.fetch;
    let body = null;
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    confirmAsked = 0; confirmAnswer = false;
    document.getElementById("bfr").onclick();
    global.fetch = realFetch;
    confirmAnswer = true;
    if (confirmAsked !== 1) throw new Error("Forget did not ask");
    if (confirmText.indexOf("Forget ") !== 0 || confirmText.indexOf("Landon's Mac") < 0)
      throw new Error("the Forget question reads " + confirmText);
    if (body !== null) throw new Error("a refused Forget still posted: " + body);
    if (document.getElementById("bfr").disabled) throw new Error("a refused Forget locked the button");
    if (global.bleError !== "") throw new Error("a refused Forget showed " + global.bleError);
  });
  step("an accepted Forget asks once and posts forget_ble", () => {
    global.st = STATE;
    paint();
    const realFetch = global.fetch;
    let body = null;
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    confirmAsked = 0; confirmAnswer = true;
    document.getElementById("bfr").onclick();
    global.fetch = realFetch;
    if (confirmAsked !== 1) throw new Error("Forget did not ask once");
    if (body !== "action=forget_ble") throw new Error("Forget posted " + body);
    global.bleForgetBusy = false;
    paint();
  });
  step("an off Bluetooth radio names its bond and never reads as connected", () => {
    global.st = STATE;
    STATE.radios = {zigbee: true, ble: false};
    STATE.ble.connected = true;
    paint();
    const line = document.getElementById("bst").innerHTML;
    const host = document.getElementById("bhs").innerHTML;
    if (line.indexOf("radio off.") < 0 || line.indexOf("BLE buttons are disabled.") < 0)
      throw new Error("the off radio does not report itself: " + line);
    // The host has its own line, above the Forget text.
    if (host.indexOf("Bonded to Landon") < 0)
      throw new Error("the host line does not name the bond: " + host);
    // The stack is down, so a stale connected flag must not reach either line.
    if (line.indexOf("Connected to") >= 0 || host.indexOf("Connected to") >= 0)
      throw new Error("an off radio still read as connected: " + line + host);
    if (document.getElementById("bfr").disabled)
      throw new Error("an off radio blocked Forget while a bond exists");
    STATE.ble.bonded = false;
    paint();
    if (document.getElementById("bhs").innerHTML.indexOf("No host bond.") < 0)
      throw new Error("an off radio with no bond says nothing about it");
    if (document.getElementById("bhs").innerHTML.indexOf("Ready to pair") >= 0)
      throw new Error("an off radio offered pairing");
    if (!document.getElementById("bfr").disabled)
      throw new Error("Forget stayed live with no bond");
    STATE.ble.bonded = true;
    STATE.radios = {zigbee: true, ble: true};
    paint();
  });
  step("every line and control keeps its place", () => {
    global.st = STATE;
    STATE.radios = {zigbee: false, ble: false};
    paint();
    for (const id of ["zrs", "zsum", "bst", "bhs", "bfr", "zrw", "brw"]) {
      const e = document.getElementById(id);
      if (e.hidden) throw new Error(id + " left the page");
      if (id !== "bfr" && id !== "zrw" && id !== "brw" && !e.innerHTML)
        throw new Error(id + " has no line while the radios are off");
    }
    if (document.getElementById("zrs").innerHTML.indexOf("Zigbee radio is off.") < 0)
      throw new Error("the Zigbee line does not name the radio");
    if (document.getElementById("zsum").innerHTML.indexOf("This browser is") < 0)
      throw new Error("the Zigbee2MQTT line does not name the browser");
    STATE.radios = {zigbee: true, ble: true};
    paint();
    if (document.getElementById("zrs").innerHTML.indexOf("Zigbee radio is on.") < 0)
      throw new Error("a live radio does not say so");
  });
  step("the Zigbee line names the network state the stack reports", () => {
    global.st = STATE;
    STATE.radios = {zigbee: true, ble: true};
    STATE.zigbee = {started: true, paired: false, "new": true};
    paint();
    let line = document.getElementById("zrs").innerHTML;
    if (line.indexOf("Zigbee radio is on.") < 0 || line.indexOf("Not paired.") < 0)
      throw new Error("an unpaired stack does not say so: " + line);
    STATE.zigbee = {started: true, paired: false, "new": false};
    paint();
    line = document.getElementById("zrs").innerHTML;
    if (line.indexOf("rejoining") < 0)
      throw new Error("a rejoining stack does not say so: " + line);
    STATE.zigbee = {started: false, paired: false, "new": false};
    paint();
    if (document.getElementById("zrs").innerHTML.indexOf("stack has not started") < 0)
      throw new Error("a stack that never started does not say so");
    // The radio switch owns the line first, so an off radio hides none of this.
    STATE.radios = {zigbee: false, ble: true};
    paint();
    line = document.getElementById("zrs").innerHTML;
    if (line.indexOf("Zigbee buttons are disabled.") < 0 || line.indexOf("stack") >= 0)
      throw new Error("an off radio reported the stack: " + line);
    STATE.radios = {zigbee: true, ble: true};
    STATE.zigbee = {started: true, paired: true, "new": false};
    paint();
    if (document.getElementById("zrs").innerHTML.indexOf("Paired to a Zigbee network.") < 0)
      throw new Error("a paired stack does not say so");
  });
  step("the pairing button pairs the remote and never writes to the bridge", () => {
    global.st = STATE;
    STATE.zigbee = {started: true, paired: false, "new": true, gated: false,
                    pairing: false, pair_left: 0, reach: "unknown"};
    zpjSync();
    if (document.getElementById("zpj").disabled)
      throw new Error("pairing stayed locked with a known state");
    if (document.getElementById("zpj").textContent !== "Pair this remote for 3 minutes")
      throw new Error("the button does not offer a pair");
    // An unpaired remote has no network to lose, but the press still restarts it.
    const realFetch = global.fetch;
    let body = null;
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    wsSent = []; confirmAsked = 0; confirmAnswer = false;
    document.getElementById("zpj").onclick();
    if (confirmAsked !== 1) throw new Error("an unpaired start did not ask");
    if (confirmText.indexOf("restarts to start pairing") < 0 ||
        confirmText.indexOf("This page reconnects when the remote is back.") < 0)
      throw new Error("the unpaired question is wrong: " + confirmText);
    if (confirmText.indexOf("erases") >= 0)
      throw new Error("an unpaired remote was told about an erase: " + confirmText);
    if (body !== null) throw new Error("a refused start still posted: " + body);
    if (document.getElementById("zpj").disabled)
      throw new Error("a refused start locked the button");
    confirmAsked = 0; confirmAnswer = true;
    document.getElementById("zpj").onclick();
    global.fetch = realFetch;
    if (confirmAsked !== 1) throw new Error("an unpaired start did not ask");
    if (wsSent.length !== 0) throw new Error("the button wrote to Zigbee2MQTT");
    if (body !== "action=pair&on=1") throw new Error("wrong request: " + body);
    if (!document.getElementById("zpj").disabled)
      throw new Error("the button stayed live across the restart");
    if (document.getElementById("zpj").textContent !== "Restarting...")
      throw new Error("the button does not name the restart");
    // The restart drops the poll, and the line says so instead of a dead remote.
    zpjLost();
    if (document.getElementById("zpjs").innerHTML.indexOf("The remote is restarting.") < 0)
      throw new Error("the restart never reached the line");
    // The remote comes back pairing, which is what clears the press.
    STATE.zigbee.pairing = true; STATE.zigbee.pair_left = 174;
    zpjSync();
    const open = document.getElementById("zpjs").innerHTML;
    if (open.indexOf("The remote is pairing for 2:54.") < 0)
      throw new Error("the countdown is wrong: " + open);
    if (document.getElementById("zpj").disabled)
      throw new Error("the button stayed locked after the remote came back");
    if (document.getElementById("zpj").textContent !== "Stop pairing")
      throw new Error("the button does not offer a stop");
    // The link line names pairing before it names a join state.
    paint();
    if (document.getElementById("zrs").innerHTML.indexOf("Pairing.") < 0)
      throw new Error("the link line does not name the window");
    // A stop restarts the remote too. Without WiFi Always On the page cannot
    // follow it back, so the question names the SW9 hold.
    body = null;
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    STATE.network.wifi_always_on = false;
    confirmAsked = 0; confirmAnswer = false;
    document.getElementById("zpj").onclick();
    if (confirmAsked !== 1) throw new Error("a stop did not ask");
    if (confirmText.indexOf("The remote restarts with the Zigbee radio off.") < 0)
      throw new Error("the stop question does not name the restart: " + confirmText);
    if (confirmText.indexOf("Wi-Fi stays off after the restart.") < 0 ||
        confirmText.indexOf("Hold Button 9 for two seconds") < 0)
      throw new Error("the stop question does not name the SW9 hold: " + confirmText);
    if (body !== null) throw new Error("a refused stop still posted: " + body);
    if (document.getElementById("zpj").disabled)
      throw new Error("a refused stop locked the button");
    STATE.network.wifi_always_on = true;
    confirmAsked = 0; confirmAnswer = true;
    document.getElementById("zpj").onclick();
    global.fetch = realFetch;
    STATE.network.wifi_always_on = false;
    if (confirmAsked !== 1) throw new Error("a stop did not ask");
    if (confirmText.indexOf("Button 9") >= 0 || confirmText.indexOf("Wi-Fi stays off") >= 0)
      throw new Error("an always-on remote was told Wi-Fi stays off: " + confirmText);
    if (body !== "action=pair&on=0") throw new Error("stop did not close the window: " + body);
    STATE.zigbee.pairing = false; STATE.zigbee.pair_left = 0;
    zpjSync();
    if (document.getElementById("zpjs").innerHTML.indexOf("The remote is not pairing.") < 0)
      throw new Error("the closed window is not reported");
  });
  step("a paired remote is asked before it loses its network", () => {
    global.st = STATE;
    STATE.zigbee = {started: true, paired: true, "new": false, gated: false,
                    pairing: false, pair_left: 0, reach: "ok"};
    zpjSync();
    const realFetch = global.fetch;
    let body = null;
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    confirmAsked = 0; confirmAnswer = false;
    document.getElementById("zpj").onclick();
    global.fetch = realFetch;
    if (confirmAsked !== 1) throw new Error("a paired remote was not asked");
    if (confirmText.indexOf("erases the Zigbee network credentials") < 0)
      throw new Error("the question does not say what is erased: " + confirmText);
    if (confirmText.indexOf("button assignments are kept") < 0)
      throw new Error("the question does not say what is kept: " + confirmText);
    if (body !== null) throw new Error("a refused confirm still posted: " + body);
    if (document.getElementById("zpj").disabled)
      throw new Error("a refused confirm locked the button");
    confirmAnswer = true;
    global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
    document.getElementById("zpj").onclick();
    global.fetch = realFetch;
    if (body !== "action=pair&on=1") throw new Error("an accepted confirm did not post: " + body);
    STATE.zigbee.pairing = true; zpjSync(); STATE.zigbee.pairing = false; zpjSync();
  });
  step("an off radio names a pairing window as the cause", () => {
    global.st = STATE;
    STATE.radios = {zigbee: false, ble: true};
    STATE.zigbee = {started: false, paired: false, "new": true, gated: true,
                    pairing: false, pair_left: 0, pair_failed: true, reach: "unknown"};
    paint();
    let line = document.getElementById("zrs").innerHTML;
    if (line.indexOf("Zigbee radio is off.") < 0)
      throw new Error("the off radio is not named: " + line);
    if (line.indexOf("The last pairing attempt found no coordinator") < 0)
      throw new Error("the off radio does not say why: " + line);
    // A radio the user switched off has no such cause to report.
    STATE.zigbee.pair_failed = false;
    paint();
    line = document.getElementById("zrs").innerHTML;
    if (line.indexOf("pairing attempt") >= 0)
      throw new Error("a hand-switched radio invented a cause: " + line);
    STATE.radios = {zigbee: true, ble: true};
    STATE.zigbee = {started: true, paired: true, "new": false, gated: false,
                    pairing: false, pair_left: 0, pair_failed: false, reach: "ok"};
  });
  step("an unacknowledged device command reaches the link line", () => {
    global.st = STATE;
    STATE.zigbee = {started: true, paired: true, "new": false, gated: false,
                    pairing: false, pair_left: 0, reach: "failed"};
    paint();
    if (document.getElementById("zrs").innerHTML.indexOf("was not acknowledged") < 0)
      throw new Error("a failed send never reached the line");
    // A groupcast-only remote learns nothing, so unknown still reads as paired.
    STATE.zigbee.reach = "unknown";
    paint();
    if (document.getElementById("zrs").innerHTML.indexOf("Paired to a Zigbee network.") < 0)
      throw new Error("an unknown reach did not read as paired");
    STATE.zigbee.reach = "ok";
  });
  step("the coordinator window is reported and never asked for", () => {
    global.ws = null; global.tg = null; global.td = null;
    zcPaint();
    if (document.getElementById("zcs").innerHTML.indexOf("needs the Zigbee2MQTT link") < 0)
      throw new Error("the coordinator line does not say why it is blank");
    z2mConnect("ws://bridge/api", "");
    ws.onmessage({data: JSON.stringify({topic: "bridge/groups",
                                        payload: [{id: 1, friendly_name: "all_light", members: []}]})});
    wsSent = [];
    ws.onmessage({data: JSON.stringify({topic: "bridge/info",
                                        payload: {permit_join: true, permit_join_timeout: 174}})});
    const open = document.getElementById("zcs").innerHTML;
    if (open.indexOf("Pairing is open on the coordinator for 2:54.") < 0)
      throw new Error("the countdown is wrong: " + open);
    ws.onmessage({data: JSON.stringify({topic: "bridge/info", payload: {permit_join: false}})});
    if (document.getElementById("zcs").innerHTML.indexOf("Permit joining in Zigbee2MQTT") < 0)
      throw new Error("the closed window does not say where to open it");
    if (wsSent.length !== 0) throw new Error("the page wrote to Zigbee2MQTT");
    z2mDisconnect();
    global.ws = null; global.tg = null; global.td = null;
  });
  step("an old remote with no radio block leaves every input live", () => {
    const saved = global.st.radios;
    delete global.st.radios;
    paint();
    if (keys[20].className.indexOf("rf") >= 0) throw new Error("a missing radio block held an input");
    // The switch keeps its place, so it is only locked while the state is unknown.
    if (document.getElementById("zrb").disabled !== true)
      throw new Error("a missing radio block left the switch live");
    if (document.getElementById("zrw").hidden)
      throw new Error("a missing radio block hid the switch");
    global.st.radios = saved;
    paint();
  });
  step("copy and download need text in the box", () => {
    global.cfgBusy = false;
    global.cfgOpen = true;
    global.cfgIn = "";
    cfgPaint();
    if (!document.getElementById("cxc").disabled ||
        !document.getElementById("cxd").disabled)
      throw new Error("an empty box left copy or download enabled");
    const box = document.getElementById("cx");
    box.value = cfgBlob();
    box.oninput.call(box);
    if (document.getElementById("cxc").disabled ||
        document.getElementById("cxd").disabled)
      throw new Error("typed text did not enable copy or download");
    box.value = "   ";
    box.oninput.call(box);
    if (!document.getElementById("cxc").disabled ||
        !document.getElementById("cxd").disabled)
      throw new Error("blank text left copy or download enabled");
    global.cfgIn = "";
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
    if (!lastDownload || lastDownload.download !== "homething-c6-13f498-config.json" ||
        lastDownload.href !== "blob:config") throw new Error("download link is wrong");
    if (!downloadedBlob || downloadedBlob.type !== "application/json" ||
        downloadedBlob.parts[0] !== cfgIn) throw new Error("download body is wrong");
  });
  step("export falls back to the fixed file name without a friendly name", () => {
    const prevSt = global.st;
    global.st = {};
    lastDownload = null;
    document.getElementById("cxd").onclick();
    global.st = prevSt;
    if (!lastDownload || lastDownload.download !== "c6remote-config.json")
      throw new Error("fallback download name is wrong");
  });
  step("the export carries the device settings and leaves the name out", () => {
    const j = JSON.parse(cfgBlob());
    const want = {zigbee: true, ble: true, home_assistant: true, wifi_always_on: false,
                  status_leds: true, boot_leds: true, sleep: true, sleep_after_s: 300, wake_replay: false};
    if (JSON.stringify(j.settings) !== JSON.stringify(want))
      throw new Error("settings are wrong: " + JSON.stringify(j.settings));
    if ("name" in j.settings) throw new Error("the name was exported");
    const prev = global.st.sleep;
    global.st.sleep = {available: false, enabled: false, after_s: 0, replay: false};
    const bare = JSON.parse(cfgBlob()).settings;
    global.st.sleep = prev;
    if ("sleep" in bare || "sleep_after_s" in bare || "wake_replay" in bare)
      throw new Error("a remote without sleep exported sleep keys: " + JSON.stringify(bare));
    if (bare.zigbee !== true) throw new Error("the radio keys went missing");
  });
  step("an import refuses a bad settings entry before any write", () => {
    const base = {c6remote: 1, slots: []};
    const bad = (settings, word) => {
      const r = cfgParse(JSON.stringify(Object.assign({}, base, {settings: settings})));
      if (!r.error || r.error.indexOf(word) < 0)
        throw new Error("not refused with " + word + ": " + JSON.stringify(r));
    };
    bad({zigbe: true}, "zigbe");
    bad({sleep_after_s: 5}, "sleep_after_s");
    bad({sleep_after_s: 3601}, "sleep_after_s");
    bad({sleep_after_s: 30.5}, "sleep_after_s");
    bad({sleep_after_s: "300"}, "sleep_after_s");
    bad({ble: "yes"}, "ble");
    bad({wake_replay: 1}, "wake_replay");
    bad([true], "object");
    bad(null, "object");
    const ok = cfgParse(JSON.stringify(Object.assign({}, base, {settings: {sleep_after_s: 10, ble: false}})));
    if (ok.error) throw new Error("a valid settings entry was refused: " + ok.error);
    if (cfgParse(JSON.stringify(base)).error) throw new Error("a file without settings was refused");
  });
  step("an import sends only the settings that differ", () => {
    const l = cfgSetList({zigbee: true, ble: false, home_assistant: true, wifi_always_on: true,
                          sleep: false, sleep_after_s: 600, wake_replay: false});
    const got = l.list.map(e => e.action + e.args);
    const want = ["set_radio&radio=ble&on=0", "set_wifi_always_on&enabled=1",
                  "set_sleep_enabled&enabled=0", "set_sleep_after&seconds=600"];
    if (JSON.stringify(got) !== JSON.stringify(want))
      throw new Error("wrong settings list: " + JSON.stringify(got));
    if (l.skipped) throw new Error("a sleep remote skipped a key");
    if (cfgSetList({zigbee: true, sleep_after_s: 300}).list.length)
      throw new Error("a matching setting was sent");
    if (cfgSetList({wake_replay: true}).list[0].args !== "&enabled=1")
      throw new Error("the wake press argument is wrong");
    if (cfgSetList({home_assistant: false}).list[0].args !== "&radio=home_assistant&on=0")
      throw new Error("the Home Assistant argument is wrong");
  });
  step("an import sends status_leds only when it differs", () => {
    if (cfgSetList({status_leds: true}).list.length) throw new Error("a matching setting was sent");
    const l = cfgSetList({status_leds: false}).list;
    if (l.length !== 1 || l[0].action !== "set_status_leds" || l[0].args !== "&enabled=0")
      throw new Error("wrong status_leds entry: " + JSON.stringify(l));
    const r = cfgParse(JSON.stringify({c6remote: 1, slots: [], settings: {status_leds: 1}}));
    if (!r.error || r.error.indexOf("status_leds") < 0) throw new Error("a number was accepted");
  });
  step("an import sends boot_leds only when it differs", () => {
    if (cfgSetList({boot_leds: true}).list.length) throw new Error("a matching setting was sent");
    const l = cfgSetList({boot_leds: false}).list;
    if (l.length !== 1 || l[0].action !== "set_boot_leds" || l[0].args !== "&enabled=0")
      throw new Error("wrong boot_leds entry: " + JSON.stringify(l));
    const r = cfgParse(JSON.stringify({c6remote: 1, slots: [], settings: {boot_leds: 1}}));
    if (!r.error || r.error.indexOf("boot_leds") < 0) throw new Error("a number was accepted");
  });
  step("an import skips the sleep keys on a remote without sleep", () => {
    const prev = global.st.sleep;
    global.st.sleep = {available: false, enabled: false, after_s: 0, replay: false};
    const l = cfgSetList({ble: false, sleep: true, sleep_after_s: 600, wake_replay: true});
    global.st.sleep = prev;
    if (l.skipped !== 3 || l.list.length !== 1 || l.list[0].action !== "set_radio")
      throw new Error("sleep keys were not skipped: " + JSON.stringify(l));
  });
  step("an import with only settings posts the first setting and a matching file says so", () => {
    const realFetch = global.fetch;
    const bodies = [];
    global.fetch = (u, o) => { if (o && o.body) bodies.push(o.body); return realFetch(u, o); };
    global.cfgIn = JSON.stringify({c6remote: 1, settings: {ble: false}, slots: []});
    cfgApply();
    global.fetch = realFetch;
    if (cfgBad) throw new Error("a valid config was refused: " + cfgMsg);
    if (bodies.length !== 1 || bodies[0].indexOf("action=set_radio") < 0 ||
        bodies[0].indexOf("radio=ble") < 0 || bodies[0].indexOf("on=0") < 0)
      throw new Error("the setting was not posted: " + JSON.stringify(bodies));
    global.cfgBusy = false;
    global.cfgIn = JSON.stringify({c6remote: 1, settings: {ble: true}, slots: []});
    cfgApply();
    if (cfgMsg !== "The remote already matches this config.")
      throw new Error("wrong nothing to do note: " + cfgMsg);
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
    STATE.radios = {zigbee: true, ble: true};
    STATE.ble.connected = true;
    bleStatus();
    STATE.ble.connected = true;
    const named = document.getElementById("bhs").innerHTML;
    if (named.indexOf("Connected to Landon&#39;s Mac") < 0 &&
        named.indexOf("Connected to Landon's Mac") < 0)
      throw new Error("the host name is missing: " + named);
    if (document.getElementById("bst").innerHTML.indexOf("BLE HID: radio on.") < 0)
      throw new Error("the radio line lost its own state");
    STATE.ble.host = "";
    bleStatus();
    const plain = document.getElementById("bhs").innerHTML;
    if (plain.indexOf("Connected to a saved host.") < 0)
      throw new Error("an unread host name broke the line: " + plain);
    STATE.ble.host = "Landon's Mac";
  });

  (async () => {
    const realFetch = global.fetch;
    if (cfgTask) await cfgTask;
    await new Promise(done => setTimeout(done, 20));
    step("recording refreshes its slot only after a saved code", () => {
      const realChanged = global.cfgChanged;
      const slots = [];
      global.cfgChanged = s => { slots.push(s); return Promise.resolve(); };
      global.sel = 3; global.rec = 6; global.mode = "rec"; global.seen = true;
      finish();
      global.mode = "cancel"; global.seen = false;
      finish();
      global.cfgChanged = realChanged;
      if (slots.length !== 1 || slots[0] !== 6)
        throw new Error("capture refreshed the selected or cancelled slot: " + slots);
    });
    global.cfgAll = {}; global.cfgReady = false; global.cfgDirty = false; global.cfgIn = "";
    global.fetch = (u, o) => String(u).includes("/api/code")
      ? Promise.resolve({ok: false, status: 503}) : realFetch(u, o);
    await cfgRefresh();
    step("failed code read keeps current export incomplete", () => {
      if (cfgReady || cfgAll[6] !== undefined || !cfgBad)
        throw new Error("failed IR read was accepted: " + JSON.stringify({ready: cfgReady, code: cfgAll[6], bad: cfgBad, action: row(6) && row(6).action}));
      if (!document.getElementById("cxd").disabled)
        throw new Error("incomplete current config can download");
    });
    global.fetch = realFetch;
    document.getElementById("tabc").onclick();
    await cfgTask;
    step("opening Config retries a failed code read", () => {
      if (!cfgReady || cfgAll[6] !== CODE.text) throw new Error("retry did not complete cache");
    });
    {
      const realF = global.fetch, posts = [];
      let haIds = 1000;
      const haSettle = () => new Promise(done => setTimeout(done, 30));
      const answer = last => { STATE.ha = {pending: 0, last_slot: 8, last, error: last === "error" ? "service not found" : ""}; };
      global.fetch = (u, o) => {
        if (o && /action=set_ha/.test(o.body || "") && global.haSetStatus)
          return Promise.resolve({status: 400, ok: false, text: () => Promise.resolve('{"ok":false,"error":"Home Assistant actions are not configured"}')});
        if (o && /action=test_ha/.test(o.body || "")) {
          posts.push(o.body);
          if (global.haTestStatus) return Promise.resolve({status: 400, ok: false, text: () => Promise.resolve('{"ok":false,"error":"slot has no Home Assistant action"}')});
          const id = ++haIds;
          global.haLastId = id;
          if (global.haNext) global.haNext();
          if (!global.haHold) { STATE.action_id = id; STATE.action_ok = !global.haFailQueue; }
          return Promise.resolve({status: 200, ok: true, text: () => Promise.resolve('{"ok":true,"id":' + id + '}')});
        }
        return realF(u, o);
      };
      const expected = {
        ok: "Home Assistant ran the action.",
        error: "Home Assistant reported an error: service not found",
        unconfirmed: "Sent. Home Assistant did not confirm. If nothing happened, turn on \"Allow the device to perform Home Assistant actions\" in the ESPHome integration options.",
        timeout: "Home Assistant did not connect within 20 s.",
        dropped: "Too many presses are queued.",
      };
      global.haSetStatus = true;
      pick(3); global.act = "ha"; global.hek = "light.kitchen"; global.hkd = "light"; global.hac = "toggle";
      assignHa();
      await haSettle();
      step("a 400 from set_ha shows the firmware text", () => {
        if (msg !== "Home Assistant actions are not configured" || !bad) throw new Error("the 400 showed: " + msg);
      });
      global.haSetStatus = false;
      for (const last of Object.keys(expected)) {
        pick(8);
        global.haNext = () => answer(last);
        testHa();
        await haSettle();
        step("Test shows the " + last + " outcome", () => {
          if (posts[posts.length - 1] !== "action=test_ha&slot=8") throw new Error("Test posted " + posts[posts.length - 1]);
          if (haMsg !== expected[last]) throw new Error("the outcome reads " + haMsg);
          if (haBad !== (last !== "ok")) throw new Error("the tone is wrong for " + last);
          if (haBusy) throw new Error("Test stayed busy");
          if (document.getElementById("edpanel").innerHTML.indexOf("Waiting for Home Assistant") >= 0)
            throw new Error("the panel still waits");
        });
      }
      pick(8);
      global.haNext = () => { STATE.ha = {pending: 1, last_slot: 8, last: "queued", error: ""}; };
      testHa();
      await haSettle();
      step("Test waits while the action is queued and ignores another slot", () => {
        if (haMsg !== "Waiting for Home Assistant..." || !haBusy) throw new Error("the wait reads " + haMsg);
        if (!document.getElementById("ht").disabled) throw new Error("Test is not disabled while it waits");
        STATE.ha = {pending: 0, last_slot: 5, last: "ok", error: ""};
      });
      await new Promise(done => setTimeout(done, 800));
      step("a result for another slot does not end the wait", () => {
        if (!haBusy || haMsg !== "Waiting for Home Assistant...") throw new Error("the wait ended: " + haMsg);
        answer("ok");
      });
      await new Promise(done => setTimeout(done, 800));
      step("the outcome shows once the slot reports it", () => {
        if (haBusy || haMsg !== expected.ok) throw new Error("the outcome reads " + haMsg);
      });
      pick(8);
      global.haHold = true;
      global.haNext = () => { STATE.ha = {pending: 0, last_slot: 8, last: "ok", error: ""}; };
      STATE.ha = {pending: 0, last_slot: 8, last: "ok", error: ""};
      testHa();
      await haSettle();
      step("a stale result for the slot is ignored until the action id completes", () => {
        if (!haBusy || haMsg !== "Waiting for Home Assistant...") throw new Error("the stale ok was shown: " + haMsg);
        STATE.ha = {pending: 0, last_slot: 8, last: "error", error: "late"};
        STATE.action_id = global.haLastId; STATE.action_ok = true;
      });
      await new Promise(done => setTimeout(done, 800));
      step("the result counts once the action id completes", () => {
        if (haBusy || haMsg !== "Home Assistant reported an error: late") throw new Error("the outcome reads " + haMsg);
      });
      global.haHold = false;
      global.haNext = null;
      global.haFailQueue = true;
      pick(8);
      testHa();
      await haSettle();
      step("a failed action id reports that the action was not queued", () => {
        if (haMsg !== "The remote could not queue the action." || haBusy || !haBad) throw new Error("it reads " + haMsg);
      });
      global.haFailQueue = false;
      pick(8);
      global.haNext = null; global.haTestStatus = true;
      testHa();
      await haSettle();
      step("a 400 from test_ha shows the firmware text", () => {
        if (haMsg !== "slot has no Home Assistant action" || !haBad || haBusy) throw new Error("the 400 showed " + haMsg);
      });
      global.haTestStatus = false;
      pick(8);
      global.haNext = () => { STATE.ha = {pending: 1, last_slot: 8, last: "queued", error: ""}; };
      testHa();
      pick(5);
      await new Promise(done => setTimeout(done, 800));
      step("a new selection drops a poll in flight", () => {
        if (haMsg !== "" || haBusy) throw new Error("the old poll wrote " + haMsg);
      });
      STATE.ha = {pending: 0, last_slot: 0, last: "none", error: ""};
      STATE.action_id = 0; STATE.action_ok = false;
      global.fetch = realF;
    }
    {
      const prevRadios = STATE.radios, prevDirty = global.cfgDirty;
      STATE.radios = {zigbee: true, ble: false, home_assistant: true};
      global.cfgDirty = false;
      await load();
      const fresh = JSON.parse(cfgIn).settings.ble;
      global.cfgDirty = true; global.cfgIn = "edited";
      STATE.radios = {zigbee: true, ble: true, home_assistant: true};
      await load();
      const kept = cfgIn;
      global.cfgDirty = prevDirty; STATE.radios = prevRadios;
      await load();
      step("a state reload refreshes the export box unless the user edited it", () => {
        if (fresh !== false) throw new Error("the box kept the old setting: " + fresh);
        if (kept !== "edited") throw new Error("a reload replaced the edited text");
      });
    }
    global.cfgDirty = true; global.cfgIn = "unsaved text";
    await cfgChanged(6);
    step("cache refresh preserves unsaved Config text", () => {
      if (cfgIn !== "unsaved text" || cfgAll[6] !== CODE.text)
        throw new Error("refresh replaced manual text or missed the code");
    });
    // The restart pressed above has its reply by now, and the stub answers id 1.
    const restartLine = () => document.getElementById("rss");
    step("the accepted restart names the Wi-Fi it comes back with", () => {
      STATE.network.wifi_always_on = false;
      restartPaint();
      const off = restartLine().innerHTML;
      if (off.indexOf("The remote is restarting.") < 0 || off.indexOf("Wi-Fi stays off after the restart.") < 0 ||
          off.indexOf("Hold Button 9 for two seconds") < 0)
        throw new Error("the Wi-Fi off line reads " + off);
      STATE.network.wifi_always_on = true;
      restartPaint();
      const on = restartLine().innerHTML;
      if (on.indexOf("reconnects") < 0 || on.indexOf("Wi-Fi stays off") >= 0)
        throw new Error("the Wi-Fi on line reads " + on);
      STATE.network.wifi_always_on = false;
      restartPaint();
    });
    global.fetch = () => Promise.reject(new Error("offline"));
    global.stBusy = false;
    stateRefresh();
    await new Promise(done => setTimeout(done, 20));
    global.fetch = realFetch;
    step("a failed poll during the restart keeps the restart line", () => {
      const line = restartLine();
      if (line.className.indexOf("bad") >= 0 || line.innerHTML.indexOf("The remote is restarting.") < 0)
        throw new Error("the lost poll reads " + line.className + " / " + line.innerHTML);
      if (!document.getElementById("rsb").disabled) throw new Error("the button unlocked while the remote was away");
    });
    // A boot starts the action ids from zero, and the stub serves 0.
    STATE.action_id = 0;
    global.stBusy = false;
    stateRefresh();
    await new Promise(done => setTimeout(done, 20));
    step("the first poll after the boot unlocks the button", () => {
      const button = document.getElementById("rsb");
      if (restartLine().hidden || restartLine().innerHTML.indexOf("The remote restarted.") < 0)
        throw new Error("the return reads " + restartLine().innerHTML);
      if (button.disabled || button.textContent !== "Restart remote")
        throw new Error("the button stayed locked after the return");
    });
    const nameBox = () => document.getElementById("dni");
    const title = () => document.getElementById("dn");
    step("the title shows the remote name and Rename opens a prefilled box", () => {
      global.st = STATE;
      paint();
      if (title().textContent !== "homeThing C6 13f498") throw new Error("the title reads " + title().textContent);
      if (document.title !== "homeThing C6 13f498 config") throw new Error("the tab reads " + document.title);
      if (document.getElementById("dnr").disabled) throw new Error("Rename stayed locked with a known name");
      document.getElementById("dnr").onclick();
      if (!document.getElementById("dnv").hidden || document.getElementById("dne").hidden)
        throw new Error("Rename did not swap the title for the box");
      if (nameBox().value !== "homeThing C6 13f498") throw new Error("the box holds " + nameBox().value);
      if (nameBox().placeholder !== STATE.default_name) throw new Error("the box has no default placeholder");
    });
    nameBox().value = "Den remote typed";
    STATE.name = "Renamed elsewhere";
    global.stBusy = false;
    stateRefresh();
    await new Promise(done => setTimeout(done, 20));
    step("a poll repaints the title but never the open box", () => {
      if (title().textContent !== "Renamed elsewhere") throw new Error("the poll left the title at " + title().textContent);
      if (nameBox().value !== "Den remote typed" || document.getElementById("dne").hidden)
        throw new Error("the poll overwrote or closed the box");
    });
    step("Escape closes the box and sends nothing", () => {
      let body = null, prevented = false;
      global.fetch = (u, o) => { if (o && o.body) body = o.body; return realFetch(u, o); };
      nameBox().onkeydown({key: "Escape", preventDefault() { prevented = true; }});
      global.fetch = realFetch;
      if (body !== null) throw new Error("Escape posted " + body);
      if (!prevented || !document.getElementById("dne").hidden || document.getElementById("dnv").hidden)
        throw new Error("Escape did not bring the title back");
    });
    // The stub remote applies set_name as the firmware does. Empty means the default.
    const nameBodies = [];
    global.fetch = (u, o) => {
      const m = o && o.body && /^action=set_name&name=(.*)$/.exec(o.body);
      if (m) {
        nameBodies.push(o.body);
        STATE.name = decodeURIComponent(m[1]) || STATE.default_name;
        STATE.action_id = 1; STATE.action_ok = true;
      }
      return realFetch(u, o);
    };
    step("Enter saves the trimmed name and locks the box during the write", () => {
      document.getElementById("dnr").onclick();
      nameBox().value = "  Den remote  ";
      nameBox().onkeydown({key: "Enter", preventDefault() {}});
      if (nameBodies.length !== 1 || nameBodies[0] !== "action=set_name&name=Den%20remote")
        throw new Error("Save posted " + nameBodies.join(" | "));
      if (!document.getElementById("dns").disabled || !nameBox().disabled)
        throw new Error("the box stayed live during the write");
    });
    await new Promise(done => setTimeout(done, 50));
    step("a saved name reaches the title and names the Home Assistant delay", () => {
      if (title().textContent !== "Den remote") throw new Error("the title reads " + title().textContent);
      if (document.title !== "Den remote config") throw new Error("the tab reads " + document.title);
      if (!document.getElementById("dne").hidden || document.getElementById("dnv").hidden)
        throw new Error("the box stayed open after the save");
      const line = document.getElementById("dnm");
      if (line.hidden || line.className.indexOf("bad") >= 0 ||
          line.textContent !== "Home Assistant shows the new name when it next connects. " +
            "A paired Bluetooth host can show the old name until it pairs again.")
        throw new Error("the save line reads " + line.textContent);
    });
    step("a blank box posts an empty name", () => {
      document.getElementById("dnr").onclick();
      nameBox().value = "   ";
      document.getElementById("dns").onclick();
      if (nameBodies.length !== 2 || nameBodies[1] !== "action=set_name&name=")
        throw new Error("an empty save posted " + nameBodies[1]);
    });
    await new Promise(done => setTimeout(done, 50));
    step("an empty name restores the default title", () => {
      if (title().textContent !== STATE.default_name) throw new Error("the title reads " + title().textContent);
    });
    step("a name over 40 bytes or with a slash never reaches the remote", () => {
      document.getElementById("dnr").onclick();
      // 21 characters fit maxlength, but they are 42 bytes of UTF-8.
      nameBox().value = "é".repeat(21);
      document.getElementById("dns").onclick();
      if (nameBodies.length !== 2) throw new Error("a long name was posted: " + nameBodies[2]);
      const line = document.getElementById("dnm");
      if (line.hidden || line.className.indexOf("bad") < 0 || line.textContent.indexOf("40 bytes") < 0)
        throw new Error("no refusal: " + line.textContent);
      if (document.getElementById("dne").hidden) throw new Error("a refusal closed the box");
      nameBox().value = "a/b";
      document.getElementById("dns").onclick();
      if (nameBodies.length !== 2) throw new Error("a slash was posted: " + nameBodies[2]);
      document.getElementById("dnc").onclick();
      if (!document.getElementById("dne").hidden || !document.getElementById("dnm").hidden)
        throw new Error("Cancel left the box or the error up");
    });
    global.fetch = realFetch;

    {
      const realPaint = global.paint, prevRadios = STATE.radios;
      const poll = async radios => {
        STATE.radios = radios;
        global.stBusy = false;
        stateRefresh();
        await new Promise(done => setTimeout(done, 20));
      };
      let paints = 0;
      global.zbusy = false; global.clipBusy = false;
      STATE.radios = {zigbee: true, ble: true, home_assistant: true};
      pick(5);
      global.paint = () => { paints++; realPaint(); };
      await poll({zigbee: true, ble: true, home_assistant: true});
      const steady = paints;
      await poll({zigbee: false, ble: true, home_assistant: true});
      const offPaints = paints, offAct = act, offGray = document.getElementById("as-zb").disabled,
            offTag = actionTag("zb");
      await poll({zigbee: true, ble: true, home_assistant: true});
      const onPaints = paints, onGray = document.getElementById("as-zb").disabled;
      global.paint = realPaint;
      STATE.radios = prevRadios;
      global.sel = null;
      paint();
      step("a state poll repaints the Action list only when a Config switch changed", () => {
        if (steady !== 0) throw new Error("a poll with no switch change repainted " + steady + " times");
        if (offPaints !== 1 || !offGray || offTag.indexOf("title='Turn on Zigbee in Config'") < 0)
          throw new Error("a poll that turned Zigbee off did not gray out its action: " + offTag);
        if (offAct !== "ir") throw new Error("a poll that turned Zigbee off left the panel on " + offAct);
        if (onPaints !== 2 || onGray) throw new Error("a poll that turned Zigbee back on left its action grayed out");
      });
    }

    // The link tracker. The poll timer would add reads of its own, so stop it.
    clearInterval(stTimer);
    const baseFetch = global.fetch;
    const link = () => document.getElementById("lnk").innerHTML;
    const banner = () => document.getElementById("lnb");
    const settle = () => new Promise(done => setTimeout(done, 30));
    let stateReads = 0, dead = false, signals = [];
    let deadError = () => new Error("network");
    const counting = (u, o) => {
      if (String(u).includes("/api/state")) {
        stateReads++;
        signals.push(o && o.signal);
        if (dead) return Promise.reject(deadError());
      }
      return baseFetch(u, o);
    };
    global.fetch = counting;
    step("a connected page says so and hides the banner", () => {
      if (link().indexOf("Connected to the remote.") < 0) throw new Error("the line reads " + link());
      if (!banner().hidden) throw new Error("the banner shows on a good link");
    });
    dead = true;
    stateRefresh();
    await settle();
    step("one failed read shows no banner", () => {
      if (!banner().hidden) throw new Error("one failure raised the banner");
      if (link().indexOf("Not connected") >= 0) throw new Error("one failure changed the line");
    });
    stateRefresh();
    await settle();
    step("two failed reads show the banner and the header line", () => {
      if (banner().hidden) throw new Error("the banner stayed hidden");
      if (banner().textContent.indexOf("The page is not connected to the remote.") !== 0)
        throw new Error("the banner reads " + banner().textContent);
      if (banner().textContent.indexOf("Hold Button 9 for two seconds to open a temporary session.") < 0)
        throw new Error("no recovery hint with WiFi Always On off: " + banner().textContent);
      if (link().indexOf("Not connected to the remote. Last answer ") < 0 || link().indexOf(" s ago.") < 0)
        throw new Error("the line reads " + link());
      if (link().indexOf("dot bad") < 0) throw new Error("the dot is not bad");
    });
    step("a restart in progress gets the warn banner", () => {
      restartBusy = true;
      lnkPaint();
      const text = banner().textContent, cls = banner().className;
      restartBusy = false;
      lnkPaint();
      if (text !== "Waiting for the remote to restart." || cls.indexOf("warn") < 0)
        throw new Error("the restart banner reads " + text + " (" + cls + ")");
    });
    dead = false;
    const before = stateReads;
    stateRefresh();
    await settle();
    step("a good read hides the banner and reloads the state in full", () => {
      if (!banner().hidden) throw new Error("the banner stayed up");
      if (link().indexOf("Connected to the remote.") < 0) throw new Error("the line reads " + link());
      // One read is the poll and one is the full load after the return.
      if (stateReads - before < 2) throw new Error("no full load after the return");
    });
    step("every state read and every post passes an abort signal", () => {
      if (!signals.length || signals.some(x => !x || typeof x.aborted !== "boolean"))
        throw new Error("a state read had no abort signal");
      let sig;
      global.fetch = (u, o) => { sig = o.signal; return baseFetch(u, o); };
      post("restart");
      global.fetch = baseFetch;
      if (!sig || typeof sig.aborted !== "boolean") throw new Error("post had no abort signal");
    });
    await settle();
    let aborted = false;
    global.fetch = (u, o) => new Promise((ok, no) => {
      o.signal.addEventListener("abort", () => no(new Error("aborted")));
    });
    await tfetch("/x", {}, 20).then(() => {}, () => { aborted = true; });
    step("the fetch wrapper aborts a request that never answers", () => {
      if (!aborted) throw new Error("the wrapper never aborted");
    });
    global.fetch = () => Promise.reject(new Error("network"));
    await post("restart").then(() => {}, () => {});
    step("a network failure from post counts as one failed read", () => {
      if (lnkFails !== 1) throw new Error("the count is " + lnkFails);
    });
    dead = false;
    global.fetch = counting;
    stateRefresh();
    await settle();
    step("an offline event raises the browser banner at once", () => {
      if (!windowEvents.offline || !windowEvents.online) throw new Error("the page listens for neither event");
      windowEvents.offline();
      if (banner().hidden || banner().textContent.indexOf("This browser is offline.") !== 0)
        throw new Error("the banner reads " + banner().textContent);
      if (link().indexOf("Not connected") < 0) throw new Error("the line reads " + link());
    });
    step("the online event reads the state and clears the banner", () => {
      const n = stateReads;
      windowEvents.online();
      if (stateReads !== n + 1) throw new Error("online did not read the state");
    });
    await settle();
    step("the banner is gone after the read that follows online", () => {
      if (!banner().hidden) throw new Error("the banner stayed up");
    });
    dead = true;
    deadError = () => { const e = new Error("aborted"); e.name = "AbortError"; return e; };
    stateRefresh();
    await settle();
    step("one aborted state read raises the banner", () => {
      if (banner().hidden) throw new Error("the banner stayed hidden after a timeout");
      if (link().indexOf("Not connected") < 0) throw new Error("the line reads " + link());
    });
    global.fetch = baseFetch;
  })().then(() => process.exit(failed ? 1 : 0), e => {
    console.log("FAIL async checks: " + e.message); process.exit(1);
  });
}, 300);
