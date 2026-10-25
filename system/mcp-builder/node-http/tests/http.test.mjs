import assert from 'node:assert/strict';
import { request } from 'node:http';
import { createServer } from 'node:net';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import * as z from 'zod/v4';
import { createMcpService, startService, readConfiguration } from '../dist/server.js';
import { assertQualifiedDiscovery, qualifyToolDiscovery } from './discovery.mjs';

const headers = {
  'Content-Type': 'application/json',
  Accept: 'application/json, text/event-stream'
};

const PROBE_TOOL = 'template_read_only_probe_7f3c';

async function withService(t, options = {}) {
  const service = await startService(
    { host: '127.0.0.1', port: 0, allowedHosts: ['127.0.0.1', 'localhost'] },
    options
  );
  t.after(() => service.stop());
  return service;
}

function registerReadOnlyProbe(server) {
  server.registerTool(PROBE_TOOL, {
    title: 'Template read-only probe',
    description: 'Deterministic read-only fixture for template qualification. Does not access files, accounts or external services.',
    inputSchema: { value: z.string().max(40).optional() },
    outputSchema: { echo: z.string(), readOnly: z.literal(true) },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false
    }
  }, async ({ value }) => {
    const result = { echo: value ?? 'template', readOnly: true };
    return { content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result };
  });
}

async function initializeAndList(endpoint, firstId) {
  const init = await rpc(endpoint, firstId, 'initialize', {
    protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'floe-template-test', version: '1.0.0' }
  });
  const version = init.result.protocolVersion;
  const initialized = await fetch(endpoint, {
    method: 'POST', headers: { ...headers, 'MCP-Protocol-Version': version },
    body: JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }),
    signal: AbortSignal.timeout(5000)
  });
  assert.equal(initialized.status, 202);
  const list = await rpc(endpoint, firstId + 1, 'tools/list', {}, version);
  return { version, tools: list.result.tools };
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
  assertQualifiedDiscovery(list.result.tools);
  const call = await rpc(endpoint, 3, 'tools/call', { name: 'service_status', arguments: { label: 'verified' } }, version);
  assert.deepEqual(call.result.structuredContent, { status: 'ready', service: 'floe-mcp-service', label: 'verified' });
  const withoutLabel = await rpc(endpoint, 4, 'tools/call', { name: 'service_status', arguments: {} }, version);
  assert.deepEqual(withoutLabel.result.structuredContent, { status: 'ready', service: 'floe-mcp-service' });
  assert.equal('label' in withoutLabel.result.structuredContent, false);
});

test('a legitimate additional read-only tool passes real HTTP discovery and the fixed status contract', async t => {
  const { endpoint } = await withService(t, { additionalTools: registerReadOnlyProbe });
  const { version, tools } = await initializeAndList(endpoint, 40);
  assertQualifiedDiscovery(tools, 'extra-tool discovery');
  assert.deepEqual(qualifyToolDiscovery([...tools].reverse()), [], 'service_status must be found by name, not position');

  const probe = tools.find(tool => tool.name === PROBE_TOOL);
  assert.ok(probe, 'the additional read-only tool must be discovered');
  assert.equal(probe.inputSchema.type, 'object');
  for (const [key, expected] of Object.entries({
    readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false
  })) {
    assert.equal(probe.annotations[key], expected, `probe annotation ${key}`);
  }

  const status = await rpc(endpoint, 43, 'tools/call', {
    name: 'service_status', arguments: { label: 'extension-verified' }
  }, version);
  assert.deepEqual(status.result.structuredContent, {
    status: 'ready', service: 'floe-mcp-service', label: 'extension-verified'
  });
  const probeCall = await rpc(endpoint, 44, 'tools/call', {
    name: PROBE_TOOL, arguments: { value: 'extension-ok' }
  }, version);
  assert.deepEqual(probeCall.result.structuredContent, { echo: 'extension-ok', readOnly: true });
});

test('qualification rejects missing or malformed service_status and duplicate or invalid names', async t => {
  const { endpoint } = await withService(t);
  const { tools } = await initializeAndList(endpoint, 50);
  assert.deepEqual(qualifyToolDiscovery(tools), []);
  const status = tools.find(tool => tool.name === 'service_status');
  assert.ok(status, 'the baseline status tool must exist for this regression');

  const clone = () => structuredClone(tools);
  const cases = [];
  cases.push([
    'missing service_status',
    tools.filter(tool => tool.name !== 'service_status'),
    /service_status is required/
  ]);
  cases.push([
    'duplicate service_status',
    [...clone(), structuredClone(status)],
    /duplicates an earlier tool name/
  ]);
  cases.push([
    'empty tool name',
    [...clone(), { ...structuredClone(status), name: '' }],
    /non-empty string/
  ]);
  cases.push([
    'whitespace tool name',
    [...clone(), { ...structuredClone(status), name: '   ' }],
    /non-empty string/
  ]);
  cases.push([
    'duplicate business tool name',
    [...clone(), { name: 'business_echo', inputSchema: { type: 'object' } },
      { name: 'business_echo', inputSchema: { type: 'object' } }],
    /duplicates an earlier tool name/
  ]);

  const badInput = clone();
  badInput.find(tool => tool.name === 'service_status').inputSchema.properties.label.maxLength = 81;
  cases.push(['label maxLength', badInput, /maxLength must be 80/]);

  const requiredLabel = clone();
  requiredLabel.find(tool => tool.name === 'service_status').inputSchema.required = ['label'];
  cases.push(['required label', requiredLabel, /must stay optional/]);

  const badOutputLiteral = clone();
  delete badOutputLiteral.find(tool => tool.name === 'service_status').outputSchema.properties.status.const;
  cases.push(['status literal', badOutputLiteral, /literal "ready"/]);

  const missingRequired = clone();
  missingRequired.find(tool => tool.name === 'service_status').outputSchema.required = ['service'];
  cases.push(['required status field', missingRequired, /required must include status/]);

  const requiredOutputLabel = clone();
  requiredOutputLabel.find(tool => tool.name === 'service_status').outputSchema.required = ['status', 'service', 'label'];
  cases.push(['required output label', requiredOutputLabel, /label must stay optional/]);

  for (const [key, value] of Object.entries({
    readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true
  })) {
    const badAnnotation = clone();
    badAnnotation.find(tool => tool.name === 'service_status').annotations[key] = value;
    cases.push([`annotation ${key}`, badAnnotation, new RegExp(`annotations\\.${key}`)]);
  }

  for (const [label, candidate, expected] of cases) {
    const issues = qualifyToolDiscovery(candidate);
    assert.ok(
      issues.some(issue => expected.test(issue)),
      `${label} did not fail discovery qualification: ${issues.join('; ') || 'no issues'}`
    );
  }
});

test('duplicate status registration is refused before discovery', () => {
  assert.throws(() => createMcpService({
    additionalTools: server => {
      server.registerTool('service_status', {
        description: 'must not replace the fixed status tool',
        inputSchema: {}
      }, async () => ({ content: [] }));
    }
  }), /Tool service_status is already registered/);
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
  assertQualifiedDiscovery(list.result.tools, 'CLI discovery');
  child.kill('SIGTERM');
  const [code, signal] = await exited;
  assert.equal(code, 0);
  assert.equal(signal, null);
  await assert.rejects(fetch(ready.endpoint, { signal: AbortSignal.timeout(1000) }));
});
