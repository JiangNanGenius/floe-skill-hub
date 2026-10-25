import type { Server } from 'node:http';
import { pathToFileURL } from 'node:url';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { createMcpExpressApp } from '@modelcontextprotocol/sdk/server/express.js';
import * as z from 'zod/v4';
import { registerTaskTools } from './tools.js';

export type AdditionalToolRegistrar = (server: McpServer) => void;

export interface McpServiceOptions {
  /**
   * Additive qualification hook for an isolated real HTTP fixture. Task-owned
   * production tools belong in `src/tools.ts`; this hook never replaces the
   * fixed service_status registration and is optional for existing callers.
   */
  additionalTools?: AdditionalToolRegistrar;
}

export interface ServiceConfiguration {
  host: '127.0.0.1' | 'localhost' | '::1' | '0.0.0.0';
  port: number;
  allowedHosts: string[];
}

export function readConfiguration(env: NodeJS.ProcessEnv): ServiceConfiguration {
  const host = env.HOST ?? '127.0.0.1';
  if (!['127.0.0.1', 'localhost', '::1', '0.0.0.0'].includes(host)) {
    throw new Error('HOST must be an explicit local service binding');
  }
  const rawPort = env.PORT ?? '8080';
  const port = Number(rawPort);
  if (!/^\d{1,5}$/.test(rawPort) || !Number.isSafeInteger(port) || port < 1024 || port > 65535) {
    throw new Error('PORT must be the assigned integer between 1024 and 65535');
  }
  const allowedHosts = (env.FLOE_MCP_ALLOWED_HOSTS ?? '127.0.0.1,localhost,[::1]')
    .split(',').map(value => value.trim());
  if (allowedHosts.some(value => !value || value.includes('*') || /[\s/@?#\\]/.test(value))) {
    throw new Error('FLOE_MCP_ALLOWED_HOSTS must contain explicit host names');
  }
  return { host: host as ServiceConfiguration['host'], port, allowedHosts };
}

export function createMcpService(options: McpServiceOptions = {}) {
  const server = new McpServer({ name: 'floe-mcp-service', version: '0.1.0' });
  server.registerTool('service_status', {
    title: 'Service status',
    description: 'Read the service readiness. Does not access files, accounts or external services.',
    inputSchema: { label: z.string().max(80).optional() },
    outputSchema: { status: z.literal('ready'), service: z.string(), label: z.string().optional() },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false
    }
  }, async ({ label }) => {
    const result = { status: 'ready' as const, service: 'floe-mcp-service', ...(label === undefined ? {} : { label }) };
    return { content: [{ type: 'text' as const, text: JSON.stringify(result) }], structuredContent: result };
  });
  registerTaskTools(server);
  options.additionalTools?.(server);
  return server;
}

export function createServiceApp(configuration: ServiceConfiguration, options: McpServiceOptions = {}) {
  const app = createMcpExpressApp({ host: configuration.host, allowedHosts: configuration.allowedHosts });
  const active = new Set<() => Promise<void>>();
  let closing = false;

  app.get('/healthz', (_request, response) => response.json({ status: 'ready' }));
  app.post('/mcp', async (request, response) => {
    if (closing) {
      response.status(503).json({ error: 'Service is stopping' });
      return;
    }
    // A stateless transport belongs to one HTTP request. A shared transport
    // would mix concurrent callers or retain an expired response stream.
    const server = createMcpService(options);
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true
    });
    let released = false;
    const release = async () => {
      if (released) return;
      released = true;
      active.delete(release);
      await Promise.allSettled([transport.close(), server.close()]);
    };
    active.add(release);
    response.once('close', () => { void release(); });
    try {
      await server.connect(transport);
      if (response.destroyed || response.writableEnded) {
        await release();
        return;
      }
      await transport.handleRequest(request, response, request.body);
    } catch {
      if (!response.headersSent && !response.destroyed) {
        response.status(500).json({
          jsonrpc: '2.0', id: null,
          error: { code: -32603, message: 'The MCP request could not be completed' }
        });
      }
      await release();
    }
  });
  app.all('/mcp', (_request, response) => {
    response.setHeader('Allow', 'POST');
    response.status(405).json({
      jsonrpc: '2.0', id: null,
      error: { code: -32000, message: 'This stateless MCP endpoint accepts POST only' }
    });
  });
  return {
    app,
    async stop() {
      closing = true;
      await Promise.allSettled([...active].map(release => release()));
    }
  };
}

export async function startService(
  configuration: ServiceConfiguration,
  options: McpServiceOptions = {}
): Promise<{
  listener: Server; endpoint: string; stop: () => Promise<void>;
}> {
  const service = createServiceApp(configuration, options);
  const listener = await new Promise<Server>((resolve, reject) => {
    const candidate = service.app.listen(configuration.port, configuration.host, () => resolve(candidate));
    candidate.once('error', reject);
  });
  const address = listener.address();
  if (!address || typeof address === 'string') {
    await service.stop();
    listener.close();
    throw new Error('The assigned MCP listener did not start');
  }
  const endpointHost = configuration.host === '::1' ? '[::1]' :
    configuration.host === '0.0.0.0' ? '127.0.0.1' : configuration.host;
  let stopPromise: Promise<void> | undefined;
  return {
    listener,
    endpoint: `http://${endpointHost}:${address.port}/mcp`,
    stop: () => stopPromise ??= (async () => {
      await service.stop();
      await new Promise<void>((resolve, reject) => {
        listener.close(error => error ? reject(error) : resolve());
        listener.closeIdleConnections();
      });
    })()
  };
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  try {
    const service = await startService(readConfiguration(process.env));
    console.log(JSON.stringify({ event: 'ready', transport: 'streamable-http', endpoint: service.endpoint }));
    const shutdown = () => {
      void service.stop().then(() => { process.exitCode = 0; }, () => { process.exitCode = 1; });
    };
    process.once('SIGINT', shutdown);
    process.once('SIGTERM', shutdown);
  } catch {
    console.error('The MCP service could not start. Check the assigned host, port and dependencies.');
    process.exitCode = 1;
  }
}
