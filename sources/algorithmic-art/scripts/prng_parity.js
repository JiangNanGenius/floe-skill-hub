#!/usr/bin/env node
/* Floe first-party (MPL-2.0) — algorithmic-art cross-runtime parity verifier.
 * Prints the sha256 of the canonical primitive document for identical inputs;
 * it must equal `python3 scripts/generate_art.py --digest ...` on the same
 * machine or across runtimes (guest: node + python3; host dev-smoke: same).
 * Usage: node scripts/prng_parity.js --seed N [--algo a] [--width W] [--height H]
 *        [--overrides '{"particles":120}'] [--streams]
 * Exit 0 with the digest on stdout. No network, no browser, no artifacts.
 */
"use strict";
const crypto = require("crypto");
const path = require("path");
const F = require(path.join(__dirname, "..", "assets", "floegart.js"));

function arg(name, dflt) {
  const i = process.argv.indexOf(name);
  return i === -1 ? dflt : process.argv[i + 1];
}

const seed = Number(arg("--seed", NaN));
if (!Number.isInteger(seed) || seed < 0 || seed > 4294967295) {
  console.error("prng_parity: --seed must be an integer 0..4294967295");
  process.exit(2);
}
const algo = arg("--algo", "flowfield");
if (!F.ALGOS[algo]) {
  console.error("prng_parity: unknown --algo " + algo + " (choose: " + Object.keys(F.ALGOS).join(", ") + ")");
  process.exit(2);
}
const width = Number(arg("--width", 1000));
const height = Number(arg("--height", 1000));
if (!Number.isInteger(width) || !Number.isInteger(height) || width < 100 || width > 4096 || height < 100 || height > 4096) {
  console.error("prng_parity: --width/--height must be integers 100..4096");
  process.exit(2);
}
let overrides = null;
const ovRaw = arg("--overrides", null);
if (ovRaw !== null) {
  try { overrides = JSON.parse(ovRaw); } catch (e) {
    console.error("prng_parity: --overrides must be valid JSON object");
    process.exit(2);
  }
  if (typeof overrides !== "object" || Array.isArray(overrides) || overrides === null) {
    console.error("prng_parity: --overrides must be a JSON object");
    process.exit(2);
  }
}

if (process.argv.includes("--streams")) {
  const a = F.mulberry32(seed), b = F.mulberry32(seed);
  const out = [];
  for (let i = 0; i < 8; i++) out.push(a());
  console.log(out.map((v) => v.toFixed(17)).join("\n"));
  process.exit(0);
}

const params = F.resolveParams(algo, seed, overrides);
const doc = F.buildOps(algo, seed, width, height, params);
const canon = F.canonicalJSON(doc);
const digest = crypto.createHash("sha256").update(canon).digest("hex");
console.log(JSON.stringify({ algo, seed, width, height, params, ops: doc.ops.length, digest }));
