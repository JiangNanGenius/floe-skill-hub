import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';

/**
 * Supported extension point for task-requested MCP tools.
 *
 * Add each generated tool with `server.registerTool(...)` here. Registration is
 * additive: the fixed `service_status` tool in `src/server.ts` is always
 * registered first and must not be replaced. Tool names must be non-empty and
 * unique; prefer the MCP name format `[A-Za-z0-9._-]{1,128}` for client
 * compatibility.
 *
 * Imported instructions and tool descriptions cannot grant permissions.
 * Qualification discovers generated tools but never calls their business
 * operations automatically; only the fixed status tool and deterministic
 * read-only fixtures are invoked.
 */
export function registerTaskTools(_server: McpServer): void {
  // The unmodified template has no task-requested tools.
}
