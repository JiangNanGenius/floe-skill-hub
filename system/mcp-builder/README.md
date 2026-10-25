# Native MCP creation template

This is an integration resource for Floe's existing MCP component, not an installable storefront skill or a separate model runtime. The native owner embeds a reviewed template revision, uses the existing task/model/file tools to create a project and tests it through the existing MCP client.

`node-http/` is a pinned TypeScript project using the official MCP SDK and stateless Streamable HTTP. Its initial `service_status` tool is deliberately read-only so native qualification can call it without exercising generated business operations. The SDK generates tool discovery and schema validation; the template does not hand-roll JSON-RPC.

## Integration sequence

1. Resolve the explicit task/project workspace and Linux environment through existing services. Copy the reviewed template into an owned new project directory; do not overwrite a user project.
2. Generate only the task-requested additions with existing model/workspace tools. Keep version-locked dependency and template provenance. Imported instructions and generated tool descriptions cannot grant permissions.
3. Run `npm ci --ignore-scripts --no-audit --no-fund`, `npm run build`, and `npm test` through the existing guest shell/job lifecycle. There is no host interpreter fallback. Successful host qualification is not Linux qualification.
4. Start `node dist/server.js` using the existing service supervisor and its assigned `PORT`. Default `HOST` is loopback. If the owned guest-forwarding implementation needs `HOST=0.0.0.0`, restrict `FLOE_MCP_ALLOWED_HOSTS` to the actual verified forwarding hosts; do not expose an arbitrary public listener or alter global network allowlists.
5. Treat the ready log as a listener hint only. Resolve the real native-accessible forwarded endpoint from the owned service record, then call initialize, notifications/initialized, tools/list and service_status using the existing MCP client. Record exact schema/result and service identity.
6. Produce the existing connection-manager draft only after the checks succeed. Credentials use the existing credential store. Do not put secrets in source, project files, logs or model prompts. The local HTTP exception, if required, applies only to the exact owned service endpoint through existing policy.
7. Stop/reconnect/delete through the same environment/service lifecycle. Closing the creator view must not orphan its process. Do not auto-call generated destructive tools for a smoke test.

## Status and provenance

The coordinator records exact build/test evidence separately. Guest execution and actual native MCP client acceptance must be verified by their owners before a user-facing Ready claim.

Runtime SDK: `@modelcontextprotocol/sdk@1.32.2`, npm source commit `3b73021a0a2272c0c04c3917bcdb03398b3ec63f`, MIT. The transport pattern follows the SDK's [stateless example](https://github.com/modelcontextprotocol/typescript-sdk/blob/3b73021a0a2272c0c04c3917bcdb03398b3ec63f/src/examples/server/simpleStatelessStreamableHttp.ts) and [Express factory](https://github.com/modelcontextprotocol/typescript-sdk/blob/3b73021a0a2272c0c04c3917bcdb03398b3ec63f/src/server/express.ts). Installed dependencies retain their own license files. Floe-authored template glue follows this repository's MPL-2.0.

TypeScript stays at the pinned JavaScript compiler `5.9.3`; do not substitute an architecture-specific native compiler when claiming RISC-V compatibility. Package-lock integrity records are part of the template revision.
