// Ed25519 keys and signatures for the interface bundle.
//
// The loader in the browser verifies the signature, so the website can change
// the interface with no firmware build. Node has Ed25519 built in, so this
// needs no package.
//
//   node scripts/ui-signing.mjs keygen [key.pem]        write a new secret key
//   node scripts/ui-signing.mjs pub [key.pem]           print the public key as hex
//   node scripts/ui-signing.mjs sign <file> [key.pem]   write <file>.sig
//
// The secret key never belongs in the repository. It defaults to
// ~/.config/homething-c6/ui-signing-key.pem.

import { createPrivateKey, createPublicKey, generateKeyPairSync, sign } from "node:crypto";
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

const DEFAULT_KEY = join(homedir(), ".config", "homething-c6", "ui-signing-key.pem");

// The last 32 bytes of the SPKI encoding are the raw public key.
function publicHex(pem) {
  const der = createPublicKey(createPrivateKey(pem)).export({ format: "der", type: "spki" });
  return Buffer.from(der.subarray(der.length - 32)).toString("hex");
}

function read(path) {
  if (!existsSync(path)) {
    console.error(`no secret key at ${path}. Run: node scripts/ui-signing.mjs keygen`);
    process.exit(1);
  }
  return readFileSync(path);
}

const [command, ...rest] = process.argv.slice(2);

if (command === "keygen") {
  const path = rest[0] ?? DEFAULT_KEY;
  if (existsSync(path)) {
    console.error(`refusing to overwrite ${path}`);
    process.exit(1);
  }
  const { privateKey } = generateKeyPairSync("ed25519");
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, privateKey.export({ format: "pem", type: "pkcs8" }), { mode: 0o600 });
  chmodSync(path, 0o600);
  console.error(`wrote ${path}`);
  console.log(publicHex(readFileSync(path)));
} else if (command === "pub") {
  console.log(publicHex(read(rest[0] ?? DEFAULT_KEY)));
} else if (command === "sign") {
  const file = rest[0];
  if (!file) {
    console.error("usage: node scripts/ui-signing.mjs sign <file> [key.pem]");
    process.exit(1);
  }
  const key = createPrivateKey(read(rest[1] ?? DEFAULT_KEY));
  writeFileSync(`${file}.sig`, `${sign(null, readFileSync(file), key).toString("hex")}\n`);
  console.error(`wrote ${file}.sig`);
} else {
  console.error("usage: keygen | pub | sign <file>");
  process.exit(1);
}
