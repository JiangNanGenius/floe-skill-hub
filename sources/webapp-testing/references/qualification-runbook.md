# Qualification runbook — webapp-testing (14 cases)

This is the runnable handoff for exercising the skill on real product surfaces. Case names and
evidence fields are the exact contract enforced by `scripts/check_fixture.py`; run records go
through `scripts/record_case.py` into `results/webapp-testing.jsonl` in the task workspace.

**Acceptance levels — never mix them up:**

| Level | What it proves | Status |
| --- | --- | --- |
| A — host reference | Package gates, script determinism, fixture self-consistency (executed on the development host by this lane; see PROVENANCE) | done here |
| B — guest verification | Staging + `exec.localService` + the guest scripts actually run in the product RISC-V Linux environment | PENDING (Main / guest) |
| C — native browser loop | The full 14-case contract through real `browser.*` tools against a live `previewURL` in the App | PENDING (Main, device) |

Only C + B make `executionVerified` true. A green `check_fixture.py` on level-A synthetic
evidence means the tooling is deterministic, not that the browser was exercised.

## 0. Prerequisites

- A durable task (temporary chats are rejected by the browser tools outright) with a local Linux
  environment and workspace; the run holds the skill's browser/tool ceiling (task grants apply;
  no separate approval system exists here).
- Stage the package bundle into the workspace **preserving layout**, e.g. copy the package to
  `webapp-testing/` so `webapp-testing/scripts/…` and `webapp-testing/assets/fixtures/site/…`
  exist (the staged skill root reported by the skill tool works identically). The fixture server
  locates its site directory relative to its own file and fails with a clear message otherwise.
- Ports: 8641 (static) and 8642 (fixture server). All `exec.shell` commands below run inside the
  guest through the task's resolved environment.

## 1. Serve the fixture (two variants)

**Dynamic (full attestation — run the contract with this server):**

```jsonc
jobs.submit(tool:"exec.localService", wait:true, purpose:"fixture server (runbook)",
  arguments:"{\"runtime\":\"python\",\"entry\":\"webapp-testing/scripts/fixture_server.py\",\"port\":8642}")
// jobs.status(jobID) → state "running" + previewURL "http://127.0.0.1:8642/" only once the probe answers
```

**Static (no POST/state routes; cases 6/8/13 attest differently — see §5):**

```jsonc
jobs.submit(tool:"exec.localService", wait:true, purpose:"fixture site static",
  arguments:"{\"runtime\":\"static\",\"entry\":\"webapp-testing/assets/fixtures/site/index.html\",\"port\":8641}")
// previewURL ends with /index.html
```

Guest-side authority reads use the guest loopback:
`exec.shell: curl -s http://127.0.0.1:8642/state`.

## 2. Case contract (dynamic server variant)

| # | case | Steps (real tools) | Expected outcome → record |
| --- | --- | --- | --- |
| 1 | `nav-index` | `browser.tab create` → `browser.navigate(previewURL, tabID)` → `browser.wait(condition:"load")` | `ok` snapshot with this run's `documentID`. PASS `--set document_id=…` |
| 2 | `wait-async-ready` | `browser.wait(condition:"text", value:"ASYNC-READY-77", timeoutMilliseconds:8000)` | Resolves after the fixture's 2.5s delayed render. PASS `--set marker=ASYNC-READY-77` |
| 3 | `observe-form-fields` | `browser.observe(tabID)` (paginate `cursor` if `nextCursor`) | Refs for `#name`, `#email`, `#plan`, `#terms`, `#submit-btn` (≥3) in the current document. PASS `--set document_id=… --set refs_found=5` |
| 4 | `input-signup-fields` | `browser.type(name-ref, documentID, "Ada")`; `browser.type(email-ref, documentID, "ada@example.invalid")` | Returned snapshot shows `value` set; no submit yet. PASS `--set document_id=…` |
| 5 | `click-submit` | `browser.click(submit-ref, documentID)` | Post-click `#status` shows `status: saved receipt=<12 hex>` (page signal only — case 6 attests). PASS `--set document_id=…` |
| 6 | `attest-submit-state` | `exec.shell: curl -s http://127.0.0.1:8642/state` | Server shows a submission whose `receipt` equals the one the page displayed. PASS `--set receipt=<12 hex>` |
| 7 | `click-counter` | fresh observe if needed → `browser.click(count-ref, documentID)` | `#count-region` increments (`count: n≥1`) in the returned state. PASS `--set document_id=…` |
| 8 | `attest-counter-state` | `exec.shell: curl -s http://127.0.0.1:8642/state` | `serverCount ≥ 1` — the click really reached the server, independent of page text. PASS `--set server_count=<n>` |
| 9 | `screenshot-evidence` | `browser.screenshot(tabID)` | Artifact `{relativePath, sha256(64 hex)}` retained; OCR regions available for fallback clicks. PASS `--set screenshot_path=… --set screenshot_sha256=…` |
| 10 | `navigate-checkout` | observe → `browser.click(checkout-link-ref, documentID)` → `browser.wait(condition:"text", value:"CHECKOUT-OK-222")` | New `documentID` (main-frame commit). PASS `--set marker=CHECKOUT-OK-222` |
| 11 | `click-confirm` | observe checkout → `browser.click(confirm-ref, new documentID)` → `browser.wait(condition:"text", value:"CONFIRMED-OK-221")` | Confirm state visible after the click. PASS `--set marker=CONFIRMED-OK-221` |
| 12 | `stale-after-reload` | `browser.click(back-link…)` → wait → `browser.observe` (capture `refR` + `documentID_R` for `#reload-btn`) → `browser.click(refR, documentID_R)` → attempt `browser.click(<pre-reload ref>, <pre-reload documentID>)` | The reload commits a new document; the pre-reload-targeted attempt must surface `stale` ("The page changed; observe it again"); re-observe then succeeds. Only PASS if BOTH halves happened: `--set stale_observed=true --set recovery_observed=true`. Do NOT replay the reloaded page's earlier mutations after the stale error. |
| 13 | `late-result-slow` | `exec.shell: curl -s --max-time 8 http://127.0.0.1:8642/slow` | Answer arrives after ~2s: `{"marker":"SLOW-DONE-45"}` — the late-but-successful result path. Pair with `browser.events(tabID, afterSequence:…)` to show stale queued events do not re-trigger GUI actions. PASS `--set marker=SLOW-DONE-45` |
| 14 | `absent-marker-fails` | `browser.wait(condition:"text", value:"MARKER-NEVER-RENDERED", timeoutMilliseconds:1500)` | Tool error (timeout) — the genuinely failing expectation. Record honestly: `--status TIMEOUT --detail "<observed tool error>" --set error=timeout`. It must NOT be recorded PASS; `check_fixture.py` exits non-zero if it is. |

Then: `python3 webapp-testing/scripts/check_fixture.py --results results/webapp-testing.jsonl`
→ exit 0 only with all 14 cases consistent; the run's own failing case must read as
`CHECK PASS absent-marker-fails status=TIMEOUT|FAIL`.

## 3. Cleanup

`browser.tab close(tabID)` per opened tab → `jobs.cancel(jobID)` per service (real guest process
exit; the port is released with it). A cancelled run cannot leave a service attached — the job
keeps ownership under the task, cancel explicitly.

## 4. Level-A reproduction (already executed by the content lane, host reference)

From the staged bundle:

```bash
python3 scripts/check_fixture.py --results references/evidence-samples/honest-run-sample.jsonl
# exit 0; 14 "CHECK PASS" lines including absent-marker-fails status=TIMEOUT
# Tamper any status to PASS / any receipt to a non-hex value / delete a case → exit 1 with the
# exact CHECK FAIL line; record_case.py rejects malformed inputs with exit 2.
python3 -m py_compile scripts/*.py        # all three compile clean
PORT=8742 python3 scripts/fixture_server.py  # host loopback reference boot (labelled host-only):
# GET / and /checkout.html 200; POST /submit returns the deterministic receipt of the JSON body;
# POST /api/click increments; GET /state echoes the authority snapshot; GET /slow answers
# SLOW-DONE-45 after ~2.0s without blocking other routes; unknown POST → 404.
```

These prove the shipped tooling is deterministic and self-consistent on the development host.
They are explicitly NOT guest (level B) or App-browser (level C) evidence.

## 5. Static-mode notes (portable fallback)

Without the python fixture server, cases 6/8/13 have no server authority: run the same contract
against previewURL on :8641, and record 6/8 from the page-visible static-mode branches
(`status: save rejected by server (static mode)` proves the fetch path executed; click count via
observations) **labelled as page-signal-only** — that is a weakened attestation, honest but not
level-C complete; it never satisfies `attest-submit-state`/`attest-counter-state` receipts.
Prefer the dynamic server for any qualification claim.

## 6. What level B/C runs must additionally capture

- Exact `jobs.status` JSON showing `previewURL` appearing only after readiness (and vanishing on
  cancel), with jobID.
- One deliberate mid-run port collision: resubmit the same port while live → the closed failure
  ("already … responding"/port owned) proves the ownership gate.
- A `needsUser` observation if the flow tests any human-takeover path (not part of this fixture;
  password fields are the supported probe elsewhere).
- Artifact bytes readable back from the task store: open the screenshot's `relativePath` with
  workspace read and re-hash to the recorded `sha256`.
- Retain results JSONL + this document's SHA; that bundle is the qualification evidence packet.
