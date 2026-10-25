# Local service lifecycle for pages under test

Audited 2026-10-26 against the current native runtime (`FloeApp/Execution/LocalServiceTool.swift`,
`Sources/FloeExecution/Linux/LinuxGuestLocalService.swift`, `Sources/FloeExecution/Tools/BackgroundJobTools.swift`).

## exec.localService (via jobs.submit — never call the target directly)

```jsonc
jobs.submit(
  tool: "exec.localService",
  wait: true,                       // stays in this run until the service is ready
  purpose: "…",
  arguments: "{\"runtime\":\"static|python|node|shell\",\"entry\":\"<workspace-relative file>\",\"arguments\":[…],\"cwd\":\"<workspace-relative dir>\",\"port\":<1024..65535>}"
)
```

- `entry` must be an existing workspace-relative regular file the run is authorized to use;
  `cwd` defaults to the workspace root. `static` accepts no arguments; its document root is the
  HTML file's directory and the preview URL ends with the HTML file name.
- The service is one detached process **inside the task's resolved Linux guest**
  (lazy-activated; a missing/unprepared environment fails with preparation guidance and never
  falls back to the host interpreter). `static` runs the guest's own
  `python3 -m http.server --bind 10.0.2.15 --directory <parent>`; `python` runs
  `python3 -u <entry> [args]` through the environment's interpreter selection (shared venv when
  present — no implicit pip/venv creation).
- Environment given to the service: `PORT` and `FLOE_SERVICE_PORT` = requested port,
  `FLOE_ENVIRONMENT_ID`, unbuffered output. Guest logs live in the environment layer and are
  readable back through bounded job progress (stdout/stderr tails capped ~4 KiB each, secret-
  redacted).
- Readiness is real: the host probes `http://127.0.0.1:<port>/` (HEAD; `static` additionally
  requires success on the HTML path) and only then exposes `previewURL` in `jobs.status` and
  authorizes exactly that loopback origin for the browser. An already-answering port aborts the
  start ("choose another port"); one managed service owns one port at a time.
- Bridging: the guest binds 10.0.2.15; slirp forwards the same port number to host 127.0.0.1
  only. The browser never sees a general private network: while the job reports running-ready the
  service origin is allowed, and cancelling/losing readiness revokes it.
- Lifecycle honesty: closing a tool turn or the browser tab does not stop the server; stopping
  the environment or the app does. `jobs.status(jobID)` reads state + bounded logs;
  `jobs.result(jobID)` pages output; `jobs.cancel(jobID)` waits for actual guest process exit.
  `wait:false` detaches the submit; the service still belongs to the run's task.

## floe-service (from exec.shell inside the guest)

`floe-service start node|python|shell|static ENTRY PORT [-- ARGS...]` ·
`list` · `status JOB_ID` · `logs JOB_ID` · `stop JOB_ID` · `restart JOB_ID`

It funnels into the same managed job store (workspace-validated entry, attached task +
environment required) and prints JSON `{jobID, state, previewURL, detail}`. Use it when the
work is already inside a guest script; use `jobs.submit` when the agent decides directly.

## Job tools used by this skill

| Tool | Parameters |
| --- | --- |
| `jobs.submit` | `{tool, arguments(JSON string), purpose ≤240, wait?}` |
| `jobs.status` | `{jobID}` |
| `jobs.result` | `{jobID, offset?, maxBytes 256..32000?}` |
| `jobs.cancel` | `{jobID}` |

## Port picks for the fixture

The runbook uses 8641 (static site) and 8642 (fixture server). Any 1024–65535 port works as long
as no other managed service owns it; the submit fails closed instead of stealing an existing
listener.
