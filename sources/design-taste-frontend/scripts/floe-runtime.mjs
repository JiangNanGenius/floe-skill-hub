// This library only adjusts the process-local WebSocket startup on tested Debian Node20.
import { spawn } from 'node:child_process';

export function runtimeFacts() {
  const [major, minor, patch] = process.versions.node.split('.').map(Number);
  const disabled = process.execArgv.includes('--no-experimental-websocket') || /(?:^|\s)--no-experimental-websocket(?:\s|$)/.test(process.env.NODE_OPTIONS || '');
  const node20 = major === 20 && (minor > 19 || (minor === 19 && patch >= 2));
  const compatibility = node20 && process.allowedNodeEnvironmentFlags.has('--experimental-websocket');
  const websocketAvailable = typeof globalThis.WebSocket === 'function';
  return {
    target: { os: process.platform, arch: process.arch === 'arm64' ? 'aarch64' : process.arch },
    node: { version: process.versions.node, preferredMajor: 22, minimumDebianCompatibility: '20.19.2',
      mode: compatibility ? 'node20-websocket-compat' : 'native', websocketAvailable,
      bootstrapRequired: compatibility && !websocketAvailable, explicitlyDisabled: disabled },
    targetSupported: process.platform === 'linux' && process.arch === 'arm64',
    nodeSupported: !disabled && ((major >= 22 && websocketAvailable) || compatibility),
  };
}

export async function ensureFloeRuntime() {
  const facts = runtimeFacts();
  if (!facts.targetSupported || !facts.nodeSupported) {
    console.error(JSON.stringify({ schemaVersion: 1, state: facts.targetSupported ? 'requires-runtime' : 'unsupported-target', ...facts }));
    process.exit(3);
  }
  if (!facts.node.bootstrapRequired) return;
  const previousOptions = process.env.NODE_OPTIONS || '';
  const env = { ...process.env, NODE_OPTIONS: (previousOptions + ' --experimental-websocket').trim() };
  const child = spawn(process.execPath, [...process.execArgv, process.argv[1], ...process.argv.slice(2)], { env, stdio: 'inherit' });
  const interrupt = () => child.kill('SIGINT');
  const terminate = () => child.kill('SIGTERM');
  process.on('SIGINT', interrupt);
  process.on('SIGTERM', terminate);
  await new Promise(() => {
    child.once('error', error => {
      console.error(JSON.stringify({ schemaVersion: 1, state: 'requires-runtime', error: error.message }));
      process.exit(3);
    });
    child.once('close', (code, signal) => {
      process.off('SIGINT', interrupt);
      process.off('SIGTERM', terminate);
      if (signal) {
        process.kill(process.pid, signal);
        return;
      }
      process.exit(Number.isInteger(code) ? code : 1);
    });
  });
}
