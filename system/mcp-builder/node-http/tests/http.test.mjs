import assert from 'node:assert/strict';
import { request } from 'node:http';
import { createServer } from 'node:net';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { startService, readConfiguration } from '../dist/server.js';

const headers = {
  'Content-Type': 'application/json',
  Accept: 'application/json, text/event-stream'
};

async function withService(t) {
  const service = await startService({ host: '127.0.0.1', port: 0, allowedHosts: ['127.0.0.1', 'localhost'] });
  t.after(() => service.stop());
  return service;
}

async function rpc(endpoint, id, method, params = {}, protocolVersion) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { ...headers, ...(protocolVersion ? { 'MCP-Protocol-Version': protocolVersion } : {}) },
    body: JSON.stringify({ jsonrpc: '2.0', id, method, params }),
    signal: AbortSignal.timeout(5000)
  });
  assert.equal(response.status, 200);
  return response.json();
}

test('initialize, discover and call a real read-only tool over HTTP', async t => {
  const { endpoint } = await withService(t);
  const init = await rpc(endpoint, 1, 'initialize', {
    protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'floe-template-test', version: '1.0.0' }
  });
  assert.equal(init.id, 1);
  assert.equal(typeof init.result.protocolVersion, 'string');
  const version = init.result.protocolVersion;
  const initialized = await fetch(endpoint, {
    method: 'POST', headers: { ...headers, 'MCP-Protocol-Version': version },
    body: JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }),
    signal: AbortSignal.timeout(5000)
  });
  assert.equal(initialized.status, 202);
  const list = await rpc(endpoint, 2, 'tools/list', {}, version);
  assert.equal(list.result.tools.length, 1);
  assert.equal(list.result.tools[0].name, 'service_status');
  assert.equal(list.result.tools[0].annotations.readOnlyHint, true);
  assert.equal(list.result.tools[0].inputSchema.type, 'object');
  const call = await rpc(endpoint, 3, 'tools/call', { name: 'service_status', arguments: { label: 'verified' } }, version);
  assert.deepEqual(call.result.structuredContent, { status: 'ready', service: 'floe-mcp-service', label: 'verified' });
});

test('invalid tool input is rejected instead of invoking a permissive handler', async t => {
  const { endpoint } = await withService(t);
  const call = await rpc(endpoint, 4, 'tools/call', { name: 'service_status', arguments: { label: 'x'.repeat(81) } });
  assert.equal(call.result.isError, true);
  assert.equal(call.result.structuredContent, undefined);
});

test('concurrent callers keep independent request IDs and arguments', async t => {
  const { endpoint } = await withService(t);
  const results = await Promise.all(Array.from({ length: 8 }, (_, index) =>
    rpc(endpoint, index + 10, 'tools/call', { name: 'service_status', arguments: { label: String(index) } })));
  for (let index = 0; index < results.length; index++) {
    assert.equal(results[index].id, index + 10);
    assert.equal(results[index].result.structuredContent.label, String(index));
  }
});

test('stateless endpoint refuses unsupported GET and DELETE', async t => {
  const { endpoint } = await withService(t);
  for (const method of ['GET', 'DELETE']) {
    const response = await fetch(endpoint, { method, signal: AbortSignal.timeout(5000) });
    assert.equal(response.status, 405);
    assert.equal(response.headers.get('allow'), 'POST');
  }
});

test('unapproved Host is refused before request handling', async t => {
  const { endpoint } = await withService(t);
  const url = new URL(endpoint);
  const status = await new Promise((resolve, reject) => {
    const req = request({ hostname: url.hostname, port: url.port, path: '/healthz', headers: { Host: 'unapproved.example' } }, res => {
      res.resume(); resolve(res.statusCode);
    });
    req.on('error', reject);
    req.end();
  });
  assert.equal(status, 403);
});

test('configuration requires the assigned port and explicit hosts', () => {
  for (const PORT of ['0', '80', '65536', '8080junk']) {
    assert.throws(() => readConfiguration({ PORT }));
  }
  assert.throws(() => readConfiguration({ HOST: 'unowned.example' }));
  assert.throws(() => readConfiguration({ FLOE_MCP_ALLOWED_HOSTS: '*' }));
  assert.deepEqual(readConfiguration({ PORT: '8091' }), {
    host: '127.0.0.1', port: 8091, allowedHosts: ['127.0.0.1', 'localhost', '[::1]']
  });
});

test('stop is idempotent and the previous endpoint is unavailable', async () => {
  const service = await startService({ host: '127.0.0.1', port: 0, allowedHosts: ['127.0.0.1'] });
  await Promise.all([service.stop(), service.stop()]);
  await assert.rejects(fetch(service.endpoint, { signal: AbortSignal.timeout(1000) }));
});

test('actual command entry reports its listener and exits cleanly on SIGTERM', { timeout: 10000 }, async t => {
  const reservation = createServer();
  reservation.listen(0, '127.0.0.1');
  await once(reservation, 'listening');
  const port = reservation.address().port;
  await new Promise(resolve => reservation.close(resolve));
  const child = spawn(process.execPath, [fileURLToPath(new URL('../dist/server.js', import.meta.url))], {
    env: { ...process.env, HOST: '127.0.0.1', PORT: String(port), FLOE_MCP_ALLOWED_HOSTS: '127.0.0.1' },
    stdio: ['ignore', 'pipe', 'pipe']
  });
  t.after(async () => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill('SIGKILL');
      await once(child, 'exit');
    }
  });
  const exited = once(child, 'exit');
  child.stderr.resume();
  const ready = await new Promise((resolve, reject) => {
    let text = '';
    const timer = setTimeout(() => reject(new Error('CLI did not produce a ready record')), 5000);
    const fail = () => {
      clearTimeout(timer);
      reject(new Error('CLI exited before producing a ready record'));
    };
    child.once('exit', fail);
    child.once('error', fail);
    child.stdout.on('data', bytes => {
      text += bytes.toString('utf8');
      if (text.length > 8192) {
        clearTimeout(timer);
        reject(new Error('CLI output exceeded the readiness record bound'));
        return;
      }
      const firstLine = text.split('\n').find(line => line.trim());
      if (!firstLine || !text.includes('\n')) return;
      try {
        const parsed = JSON.parse(firstLine);
        if (parsed.event !== 'ready') return;
        clearTimeout(timer);
        child.removeListener('exit', fail);
        child.removeListener('error', fail);
        resolve(parsed);
      } catch { /* Wait for one complete JSON readiness line. */ }
    });
  });
  assert.equal(ready.endpoint, `http://127.0.0.1:${port}/mcp`);
  const list = await rpc(ready.endpoint, 31, 'tools/list');
  assert.equal(list.result.tools[0].name, 'service_status');
  child.kill('SIGTERM');
  const [code, signal] = await exited;
  assert.equal(code, 0);
  assert.equal(signal, null);
  await assert.rejects(fetch(ready.endpoint, { signal: AbortSignal.timeout(1000) }));
});
