#!/usr/bin/env node
// Detection only. Provisioning belongs to the resolved environment's existing package service.
import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { runtimeFacts } from './floe-runtime.mjs';

const facts = runtimeFacts();
const result = {
  schemaVersion: 1,
  state: 'requires-runtime',
  target: facts.target,
  node: facts.node,
  browser: null,
  missing: [],
};
if (!facts.targetSupported) {
  result.state = 'unsupported-target';
  result.missing.push('An ARM64 Linux execution environment');
  console.log(JSON.stringify(result));
  process.exit(2);
}
if (!facts.nodeSupported) result.missing.push(facts.node.explicitlyDisabled ? 'WebSocket is explicitly disabled in the selected environment' : 'Node.js 22+ or the tested Debian Node.js 20.19.2+ compatibility runtime');
const candidates = [process.env.CHROME_PATH, process.env.CHROME, '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome']
  .filter(Boolean);
for (const binary of [...new Set(candidates)]) {
  try { fs.accessSync(binary, fs.constants.X_OK); } catch { continue; }
  const probe = spawnSync(binary, ['--version'], { encoding: 'utf8', timeout: 10000, maxBuffer: 32768 });
  const version = String(probe.stdout || '').trim();
  if (probe.status === 0 && /Chrom(?:e|ium)|Microsoft Edge/.test(version)) {
    result.browser = { path: binary, version };
    break;
  }
}
if (!result.browser) result.missing.push('Chrome, Chromium or Edge in the same Linux environment');
if (!result.missing.length) result.state = 'ready';
console.log(JSON.stringify(result));
process.exit(result.state === 'ready' ? 0 : 3);
