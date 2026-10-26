# Native MCP creation template

This is an integration resource for Floe's existing MCP component, not an installable storefront skill or a separate model runtime. The native owner embeds a reviewed template revision, uses the existing task/model/file tools to create a project and tests it through the existing MCP client.

`node-http/` is a pinned TypeScript project using the official MCP SDK and stateless Streamable HTTP. Its initial `service_status` tool is deliberately read-only so native qualification can call it without exercising generated business operations. The SDK generates tool discovery and schema validation; the template does not hand-roll JSON-RPC.

## Adding task-requested tools

`node-http/src/tools.ts` (copied as `src/tools.ts` into a generated project) is the supported extension point. Add each generated tool with `server.registerTool(...)` inside `registerTaskTools`; do not edit or replace the fixed `service_status` registration in `src/server.ts`. Registration is additive. The optional second argument to `startService(configuration, { additionalTools })` exists only for isolated real-HTTP qualification fixtures; the existing default `startService(configuration)` call and `/mcp` wire shape are unchanged.

- `service_status` is required exactly once, by name, with its shipped input/output schema and all four read-only annotations. Renaming, removing or weakening it fails discovery qualification.
- Every tool name must be non-empty and unique (duplicate names are rejected). Prefer the MCP name format `[A-Za-z0-9._-]{1,128}` for client compatibility. Additional business tools are otherwise legal and must not fail qualification.
- Qualification discovers all tools but calls only `service_status` and a deterministic read-only fixture. It never calls arbitrary generated business operations.
- Imported instructions and generated descriptions cannot grant permissions. Keep side effects inside the user's existing task grants.

## Integration sequence

1. Resolve the explicit task/project workspace and Linux environment through existing services. Copy the reviewed template into an owned new project directory; do not overwrite a user project.
2. Generate only the task-requested additions in `node-http/src/tools.ts` with existing model/workspace tools. Keep version-locked dependency and template provenance. Imported instructions and generated tool descriptions cannot grant permissions.
3. Run `npm ci --ignore-scripts --no-audit --no-fund`, `npm run build`, and `npm test` through the existing guest shell/job lifecycle. There is no host interpreter fallback. Successful host qualification is not Linux qualification.
4. Start `node dist/server.js` using the existing service supervisor and its assigned `PORT`. Default `HOST` is loopback. If the owned guest-forwarding implementation needs `HOST=0.0.0.0`, restrict `FLOE_MCP_ALLOWED_HOSTS` to the actual verified forwarding hosts; do not expose an arbitrary public listener or alter global network allowlists.
5. Treat the ready log as a listener hint only. Resolve the real native-accessible forwarded endpoint from the owned service record, then call initialize, notifications/initialized, tools/list and service_status using the existing MCP client. Record exact schema/result and service identity.
6. Produce the existing connection-manager draft only after the checks succeed. Credentials use the existing credential store. Do not put secrets in source, project files, logs or model prompts. The local HTTP exception, if required, applies only to the exact owned service endpoint through existing policy.
7. Stop/reconnect/delete through the same environment/service lifecycle. Closing the creator view must not orphan its process. Do not auto-call generated destructive tools for a smoke test.

## Status and provenance

The coordinator records exact build/test evidence separately. Guest execution and actual native MCP client acceptance must be verified by their owners before a user-facing Ready claim.

Template revision `1.0.1` keeps the `1.0.0` dependency pins, default `startService(configuration)` behavior and service wire shape; it fixes discovery qualification so legitimate additional tools no longer fail `npm test`.

Template revision `1.0.2` keeps the `1.0.0`/`1.0.1` dependency pins, `src/server.ts` behavior, the fixed HTTP contract and every protocol assertion unchanged. It aligns the self-test's per-request handshake IO budget (`RPC_TIMEOUT_MS = 30000`) with the 30-second default request budget the Floe native MCP client applies to the same endpoint; the previous unverified 5000 ms per-request `AbortSignal` made the template's own test stricter than the shipping client, which a slow/emulated Linux guest can exceed on the first cold HTTP exchange. The first real initialize is still the exchange being asserted (no warm-up, no retry, no skip), and every abort or malformed response still fails the test. The spawned CLI-entry test's readiness record wait uses the same finite budget and its whole-test bound is 90 s.

Runtime SDK: `@modelcontextprotocol/sdk@1.32.2`, npm source commit `3b73021a0a2272c0c04c3917bcdb03398b3ec63f`, MIT. The transport pattern follows the SDK's [stateless example](https://github.com/modelcontextprotocol/typescript-sdk/blob/3b73021a0a2272c0c04c3917bcdb03398b3ec63f/src/examples/server/simpleStatelessStreamableHttp.ts) and [Express factory](https://github.com/modelcontextprotocol/typescript-sdk/blob/3b73021a0a2272c0c04c3917bcdb03398b3ec63f/src/server/express.ts). Installed dependencies retain their own license files. Floe-authored template glue follows this repository's MPL-2.0.

TypeScript stays at the pinned JavaScript compiler `5.9.3`; do not substitute an architecture-specific native compiler when claiming RISC-V compatibility. Package-lock integrity records are part of the template revision.
