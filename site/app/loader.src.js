// Loads the interface bundle, verifies its signature, and runs it.
//
// The device shell pins this file by its hash, so these bytes cannot change
// without a firmware build. The bundle that this file loads carries a
// signature instead, so the interface changes with no firmware build.
//
// The device serves the page over plain HTTP, so the browser gives the page no
// crypto.subtle. The bundle therefore carries its own SHA-512.
//
// scripts/build-ui-loader.py bundles this file into site/app/loader-<hash>.js.

import { hashes, verify } from "../../third_party/noble/ed25519.js";
import { sha512 } from "../../third_party/noble/sha2.js";

hashes.sha512 = sha512;

const PUBLIC_KEY = "__PUBLIC_KEY__";
const BASE = "__BASE__";
const CACHE = "htc6-app";
const VERSION = /^\/\/v=(\d+)\n/;

function message(text) {
  const box = document.getElementById("boot");
  if (box) box.textContent = text;
}

function run(source) {
  const script = document.createElement("script");
  script.textContent = source;
  document.head.appendChild(script);
}

function hexToBytes(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
  return out;
}

function versionOf(source) {
  const found = VERSION.exec(source);
  return found ? Number(found[1]) : 0;
}

function saved() {
  try {
    const held = localStorage.getItem(CACHE);
    return held ? JSON.parse(held) : null;
  } catch (err) {
    return null;
  }
}

// The cache only ever holds a bundle that this loader verified, so a bundle
// out of the cache runs without a second check.
function keep(source, version) {
  try {
    localStorage.setItem(CACHE, JSON.stringify({ v: version, app: source }));
  } catch (err) {
    /* A full or blocked store costs the offline copy, nothing else. */
  }
}

// Thrown when the bytes arrived but the project did not sign them. It is the
// one failure that a cached copy must not hide from the log.
function Unsigned(message) {
  const error = new Error(message);
  error.unsigned = true;
  return error;
}

// The signature covers the bytes, so a stale copy from the HTTP cache is safe
// and costs no round trip. GitHub Pages revalidates it soon enough.
async function fetchBundle() {
  const [appResponse, sigResponse] = await Promise.all([
    fetch(BASE + "app.js"),
    fetch(BASE + "app.js.sig"),
  ]);
  for (const [name, response] of [["app.js", appResponse], ["app.js.sig", sigResponse]]) {
    if (!response.ok) throw new Error(`${name} answered ${response.status}`);
  }
  const bytes = new Uint8Array(await appResponse.arrayBuffer());
  const signature = hexToBytes((await sigResponse.text()).trim());
  // Verify the bytes that arrived, never a decoded copy of them.
  if (!verify(signature, bytes, hexToBytes(PUBLIC_KEY))) {
    throw Unsigned("app.js is not signed by this project");
  }
  return new TextDecoder().decode(bytes);
}

async function boot() {
  const cached = saved();
  let source = null;
  let unsigned = false;
  let why = "";
  try {
    source = await fetchBundle();
    // An attacker who holds the website can serve an older signed bundle, so
    // a version that goes backwards is refused.
    if (cached && versionOf(source) < cached.v) {
      why = `refused app.js v${versionOf(source)}, older than the copy here v${cached.v}`;
      source = null;
    }
  } catch (err) {
    unsigned = !!err.unsigned;
    why = err.message;
    source = null;
  }
  // Always say why. A silent fall back to the cached copy hides a website that
  // is down, a wrong pin, and a bundle that the project did not sign.
  if (why) console.error("homeThing c6 loader: " + why);
  if (source) {
    keep(source, versionOf(source));
    run(source);
    return;
  }
  if (cached) {
    if (unsigned) {
      console.error("homeThing c6 loader: running the copy saved here instead");
    }
    run(cached.app);
    return;
  }
  message(unsigned
    ? "The configuration interface on the website is not signed by this project, so it was not loaded."
    : "This page needs the internet one time, to load the configuration interface.");
}

boot();
