# Preserved upstream methodology, mapped to Floe

Source: `anthropics/skills` @ `dbd4588f9e1033efb41dad4bef2f7947c8993d44`, `skills/webapp-testing`
(subtree tree `5ffb7dc66b9fd4c25c3e400a4c00da99a349b714`), Apache-2.0. The upstream *approach* is
kept intact; only the unsupported execution stack (Playwright + headless Chromium + a subprocess
server wrapper + `file://` navigation) is rebound to Floe surfaces. Full upstream file hashes and
keep/exclude decisions: PROVENANCE.md.

## Decision tree (upstream → Floe)

```
User task → Static HTML?
    ├─ Yes → Read the HTML directly (workspace read) to identify element IDs/roles
    │         ├─ Success → drive the page with browser.observe refs
    │         └─ Fails/incomplete → treat as dynamic (below)
    └─ No (dynamic webapp) → Is a managed service already running for this task?
        ├─ No → jobs.submit exec.localService (runtime static|python|node|shell)
        │        then read previewURL from jobs.status once the probe responds
        └─ Yes → Reconnaissance-then-action:
            1. Navigate + wait for readiness (browser.wait load → idle/text/selector)
            2. browser.screenshot / browser.observe the rendered state
            3. Identify refs from the rendered document (never from assumptions)
            4. Act with those refs, verifying the returned post-action state
```

## Upstream practices → Floe equivalents

| Upstream (Playwright) | Floe |
| --- | --- |
| `page.goto(url); page.wait_for_load_state('networkidle')` before ANY inspection | `browser.navigate` → `browser.wait(condition:"load")` → `browser.wait(condition:"idle", quietMilliseconds:…)` or a concrete `text`/`selector` wait. "networkidle" is intentionally approximate in public WebKit: prefer concrete markers over long blind idles. |
| Inspecting `page.content()` / `page.locator('button').all()` (element discovery example) | `browser.observe` (+`cursor` pagination): nodes carry `ref, role, name, text, value, state, bounds`. This is strictly less context than a DOM dump. |
| `page.fill('#name', …)`, `page.click('text=…')`, `button[type=submit]` | `browser.type(ref, documentID, text, submit?)`, `browser.click(ref, documentID)`; visible-text-only targets fall back to `browser.screenshot` → `browser.clickVisualText`. |
| `page.screenshot(path=…, full_page=True)` | `browser.screenshot` (viewport; artifact with `relativePath` + `sha256` retained by the task; there is no arbitrary file path write from the tool). |
| `file://` URLs for local HTML | Not navigable in the product browser (http/https + authorized loopback services only). Serve the directory: `exec.localService runtime:"static"`. |
| Console log capture via `page.on("console")` | No arbitrary JS/console domain by design. Supported boundaries: `browser.events` (bounded lifecycle/DOM trail, sequence-numbered), the page's own observable state, and server-side request logs via `jobs.status`/`jobs.result`. Pages *you control* can mirror diagnostics into visible DOM text; a real console-log channel would be a native interface request, not this skill's job. |
| `scripts/with_server.py` (subprocess server + port poll + cleanup) | Replaced entirely by `jobs.submit → exec.localService` (+ guest `floe-service`): supervisor-owned process, probe-gated previewURL, `jobs.cancel` real-exit cleanup. Excluded from the package on purpose (see PROVENANCE). |
| "Always run scripts with `--help` first; don't pollute the context window with unread sources" | Kept: these scripts are small and audited — read each module docstring once (`--help` works on `record_case.py` and `check_fixture.py`; `fixture_server.py` is configured by `PORT`/`FLOE_SERVICE_PORT`), then call them as black boxes. |

## Fidelity notes

- Upstream's core value — *wait, observe, identify selectors from rendered state, act, capture
  screenshots* — is preserved verbatim in the workflow; the tool names changed, the discipline
  did not.
- Upstream text "Always launch chromium headless" and its Playwright example bodies are NOT
  reproduced as runnable guidance (unsupported stack); they are documented here as history and
  hashed upstream bytes remain available at the pinned commit.
- Upstream added one requirement Floe enforces harder: success attestation. Page-rendered
  "success" is treated as untrusted; every pass case in the runbook pairs a UI signal with an
  independent readback (server state, artifact digest, or fresh observation).
