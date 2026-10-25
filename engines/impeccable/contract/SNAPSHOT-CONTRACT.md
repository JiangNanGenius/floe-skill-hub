# Floe ↔ Impeccable snapshot/facts contract v1

Status: **schema frozen v1** — native (A2) may implement against this document and the
artifacts listed below while the riscv64 engine build continues in this lane. Engine-observed
golden outputs are still pending (see `engineValidation` in the machine-readable contract).

Contract name: `floe.impeccable.snapshot`, `contractVersion: 1`.
Machine-readable twin: [`snapshot-contract.v1.json`](snapshot-contract.v1.json).

## 1. Pin and provenance (one deliberate pin, no mixed bytes)

| Field | Value |
| --- | --- |
| Upstream project | `pbakaus/impeccable` |
| Pinned commit | `4fc2f83e1c8710dba772bfd4523d0efab57737b6` |
| Pinned tree | `1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72` |
| `ENGINE_VERSION` | `0.1.17` |
| Upstream package version | `4.7.1` (skill/npm package version, distinct from the engine version) |
| Pin authority | hub `docs/UPSTREAM-PINS.json`, `reviewBaselineDate 2026-10-26` |
| License | Apache-2.0 (upstream), Floe adapter files MPL-2.0 unless stated |

Every artifact in this directory — the extracted property columns, the producer hashes, the
build recipe and the final engine receipt — names this same commit. The earlier checkpoint
clone HEAD `936867543ac2576920d663cc9803597f6044f3ac` is a verified ancestor with the same
`ENGINE_VERSION`; it is **not** the build pin and no artifact is built from it.

## 2. Stable paths

```
engines/impeccable/contract/
  SNAPSHOT-CONTRACT.md                  this document
  snapshot-contract.v1.json             machine-readable contract (verbs, budgets, coverage, provenance)
  producer/snapshot.schema.v1.json      JSON Schema 2020-12 for the capture the native side emits
  producer/facts.schema.v1.json         JSON Schema for answers to an engine Needs
  producer/identity.schema.v1.json      JSON Schema for the capture identity/binding
  producer/result.schema.v1.json        JSON Schema for the engine result document
  producer/style-props.v1.json          the 138 computed-style columns, in SnapNode.s order
  producer/pseudo-props.v1.json         the 23 ::before/::after columns
  producer/state-pseudos.v1.json        the 31 recorded pseudo-class states (+ "undefined")
  producer/capture-limits.v1.json       upstream caps and Floe budgets
  fixtures/snapshot-positive.v1.json    6-element page, no overlay: the run completes in one round
  fixtures/snapshot-needs-hit-tests.v1.json  same page with an opaque overlay: the run must return Needs
  fixtures/facts-hit-tests.v1.json      facts shape (points must come from a real Needs)
  fixtures/facts-shown-on-scroll.v1.json scroll-probe answer shape
  fixtures/config-default.v1.json       BrowserConfig with upstream defaults
  fixtures/identity-positive.v1.json    bound identity for the positive fixture
  fixtures/identity-needs.v1.json       bound identity for the Needs fixture
  fixtures/invalid/*.v1.json            11 rejection fixtures (see §7)
  tools/make_contract_fixtures.py       deterministic generator (parses the pinned source)
  tools/fill_facts_from_needs.py        observed Needs → facts skeleton with exact f64 bits
  tools/validate_fixtures.py            coherence gate; 61 checks, exit 0
```

Regenerate with:

```bash
python3 engines/impeccable/contract/tools/make_contract_fixtures.py \
  --upstream <pinned-source-dir> --out engines/impeccable/contract \
  --upstream-commit 4fc2f83e1c8710dba772bfd4523d0efab57737b6 \
  --upstream-tree 1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72
python3 engines/impeccable/contract/tools/validate_fixtures.py \
  --contract engines/impeccable/contract --upstream <pinned-source-dir>
```

The generator refuses to publish a contract when the pinned Rust `STYLE_PROPS`/`PSEUDO_PROPS`
and the JS producer's `__SNAP_STYLE_PROPS`/`__SNAP_PSEUDO_PROPS` disagree.

## 3. Transport

Files only, UTF-8 JSON, through the task-owned workspace/resolved-environment file bridge.
No network, no CDP endpoint, no `Runtime.evaluate`, no model-authored JavaScript, no Chromium.
The engine reads the paths it is given and writes one result document; it never selects another
task's workspace.

```
native fixed capture ──> snapshot.v1.json + identity.v1.json ──> engine (guest) ──> result.v1.json
                                     ▲                                              │
                                     └────────── needs ──────────────────────────────┘
                                     facts.v1.json (same binding) ──────────────────►  re-run
```

## 4. Verbs and exit codes

Binary: `floe-impeccable` (Floe adapter over the pinned engine crates).

| Verb | Purpose |
| --- | --- |
| `engine-probe` | launcher handshake; prints `impeccable-engine 0.1.17+floe.1.0.0` |
| `contract` | prints `snapshot-contract.v1.json` |
| `snapshot-schema` | prints the producer-facing capture contract (columns, limits, shapes) |
| `snapshot-scan` | runs the rule pass over a snapshot, answers Needs from supplied facts, writes the result |
| `detect`, `context`, `ignores` | upstream static source/markup scan passthrough (offline) |

`snapshot-scan` flags: `--snapshot <path>` (required), `--identity <path>`, `--facts <path>`
(repeatable), `--config <path>`, `--out <path>`, `--max-rounds <n>` (default 4),
`--max-hit-tests <n>` (4096/round, 16384 total), `--max-snapshot-bytes <n>` (48 MiB),
`--timeout-ms <n>` (120000), `--strict-schema` (on by default in v1).

Exit codes — **3 and 4 are never a clean scan**:

| Code | Meaning |
| --- | --- |
| 0 | complete and `verdict: clean` (see §8: unreachable in v1) |
| 2 | complete with findings |
| 3 | incomplete: `status: needs-facts` — the engine is asking for measurements |
| 4 | ran, but coverage is incomplete: `verdict: inconclusive` |
| 1 | usage error, invalid input, identity mismatch, budget exceeded or cancelled |

`detect`/`context`/`ignores` keep upstream semantics (0 clean, 2 findings, 1 operational failure).

## 5. Protocol fields

### 5.1 Snapshot (native → engine)

Upstream `Snapshot` v1 exactly as the pinned engine parses it: `v`, `hostname`, `quirks`,
`innerWidth`, `innerHeight`, `scrollX`, `scrollY`, `html`, `keyframes`, `keyframeKeys`,
`linkedCss`, `styleProps` (138 columns), `pseudoProps` (23), `strings` (interned values),
`els` (document order, **element id = index + 1**), `documentElement`, `body`, `bodyInnerText`,
`textLines`, `hits`, `anim`, `shadow`. Per element: `t`, `n`, `nu`, `p`, `c`, `a`, `s`
(one interned index per style column, in column order), `b`, `f`, `ph`, `r`, `m` (8 metrics),
`v` (`checkVisibility` 1/0/-1), `d`, `dl`, `lw`, `e`, `h`, `i`, `k`, `st`, `md`, `an`, `sh`,
`as`, `ts`. Open shadow-tree elements are appended **after** every light-DOM element so light
ids never move.

Optional Floe block `floe: { captureId, documentId, contractVersion, redaction }` is ignored by
the upstream parser and cross-checked by the adapter.

### 5.2 Needs (engine → native)

```json
{ "needs": {
    "hitTests": [[x, y], ...],
    "hitTestsBits": [["<u64 x bits>", "<u64 y bits>"], ...],
    "scrollProbes": [<elementId>, ...],
    "round": 1
} }
```

Needs is a real answer, not an error. Points are decided by the rules; the lookup key upstream
is the **exact IEEE-754 double bits** of `(x, y)`, so the decimal text must round-trip and
`hitTestsBits` is provided for verification.

### 5.3 Facts (native → engine)

```json
{ "taskId": "...", "sessionId": "...", "tabId": "...", "documentId": "...",
  "captureId": "...", "documentGeneration": 1, "fenced": false,
  "hits": [{ "x": 0.0, "y": 0.0, "xBits": 0, "yBits": 0, "top": 12, "stack": [12, 4, 1],
             "unanswerable": false }],
  "shownOnScroll": [{ "el": 5, "shown": true }] }
```

* `top` = `document.elementFromPoint(x, y)` as a snapshot id, `0` when nothing.
* `stack` = `document.elementsFromPoint(x, y)` as snapshot ids, front to back, zeros dropped.
* A point the native side cannot answer keeps `"unanswerable": true` + `reason`; the engine
  reports it as unanswered instead of passing it.
* Facts bound to a different `taskId/sessionId/tabId/documentId/captureId`, or marked `fenced`,
  are **rejected**, not merged.

### 5.4 Result (engine → native)

Top level: `contract`, `contractVersion`, `status`, `verdict`, `engine`, `identity`,
`identityCheck`, `budget`, `coverage`, `needs`, `findings`, `diagnostics`, `error`.
`findings` is the upstream `CollectResult` shape (`groups`, `pageLevel`) plus `counts`.

## 6. Binding, fencing and privacy (native producer obligations)

The identity document is **required** for a real capture and must bind the current
task/session/tab/document/viewport:

Required fields: `taskId`, `sessionId`, `tabId`, `documentId`, `captureId`,
`documentGeneration`, `url`, `hostname`, `viewport.{width,height}`, `scroll.{x,y}`,
`capturedAtMs`, `producerTrust`, `producer.{name,version,engine,scriptDigest}`,
`redaction.{policy,applied,passwordInputs,formValues,credentialAttributes,textRuns}`.

Fencing rules:

1. Navigation, reload, a `documentGeneration` bump, a viewport change or a scroll change
   invalidates the snapshot and every Needs/Facts pair issued for it.
2. The native side fences at the moment of the navigation/view change; a late answer for a
   fenced capture is refused (`identityCheck.state: "superseded"`).
3. The engine reports `identityCheck.state` as `verified | absent | mismatch | superseded` and
   never turns a mismatch into a scan result.
4. `hostname`, `viewport` and `scroll` in the identity must equal the snapshot's own values.

Privacy rules:

1. `producerTrust` is the constant `native-fixed-script`. A model-declared or page-declared
   trust value is rejected; only a fixed, audited native measurement script running in an
   isolated content world may produce a capture.
2. `producer.scriptDigest` is the sha256 of the exact script bytes that ran.
3. `redaction.policy` is `floe.impeccable.redaction.v1` and `redaction.applied` must be `true`:
   password input values, form control values and credential-bearing attributes are dropped
   before the snapshot leaves the device, with per-category counts recorded.
4. A standalone synthetic fixture (the files in `fixtures/`) may carry a synthetic
   `scriptDigest` of all zeros; it is isolated test data and is never accepted as a real
   capture by the native side.

## 7. Error and rejection semantics

| Fixture / condition | Engine behaviour | Exit |
| --- | --- | --- |
| `snapshot-truncated` | JSON parse failure → `status: failed`, `error.code: snapshot-parse` | 1 |
| `snapshot-bad-version` (`v != 1`) | `error.code: snapshot-version-unsupported` | 1 |
| `snapshot-style-column-mismatch` | `error.code: schema-mismatch` (style column count ≠ `styleProps`) | 1 |
| `identity-mismatch` (hostname/viewport) | `identityCheck.state: mismatch`, no findings returned | 1 |
| `identity-missing-session-binding` | identity rejected: required binding absent | 1 |
| `identity-redaction-not-applied` | identity rejected: privacy policy not applied | 1 |
| `identity-model-declared-trust` | identity rejected: untrusted producer | 1 |
| `identity-fenced` | `identityCheck.state: superseded` | 1 |
| `facts-bits-mismatch` | facts rejected: point bits differ from the Needs that asked | 1 |
| `facts-stale-capture`, `facts-other-tab` | facts rejected: binding differs | 1 |
| budget exceeded (bytes/elements/rounds/hit tests) | `status: failed`, `budget.exceeded: [...]` | 1 |
| timeout / cancellation | `status: failed`, `error.code: cancelled` or `timeout` | 1 |
| Needs still pending after `--max-rounds` | `status: needs-facts`, Needs echoed with the round | 3 |
| ran, findings empty, a required pass uncovered | `verdict: inconclusive` | 4 |

## 8. Coverage receipt and the clean-verdict rule

`coverage.passes` lists all 18 passes with `state`, `requiredForCleanVerdict`, `reason` and
`detail`. In v1 these passes are **uncovered** (not implemented) and each one blocks a clean
verdict: `pixel-contrast`, `reveal-sweep`, `content-hidden-at-rest-measure`, `script-errors`,
`cross-origin-iframe`, `same-origin-iframe`. `screenshot-diff` and `consent-overlay-hiding` are
uncovered and not required for a clean verdict.

`verdict: clean` requires **all** of:

1. `status == complete`;
2. `needs` empty (no hit tests, no scroll probes);
3. every pass with `requiredForCleanVerdict: true` is `covered`/`complete`;
4. `style-parity` complete (`coverage.unknownStyleProps` empty);
5. `identityCheck.state == verified`;
6. no budget exceeded and no cancellation.

Because condition 3 cannot hold in v1, **the v1 engine never certifies a page clean**: an empty
finding list is reported as `verdict: inconclusive` (exit 4) together with the explicit
`coverage.uncoveredRequired` list. Missing measurements are never a green light.

`style-parity` is derived from the pinned engine's own diagnostic
(`SnapshotDom::unknown_style_props`): a property the rules read but the capture did not record
makes the run `partial`, and the property names are listed in the receipt. This is the primary
WebKit-vs-Chrome parity signal for A2.

## 9. What A2 can build against today

* The snapshot/identity/facts/result schemas, the 138/23/31 column lists, the caps and budgets,
  the Needs→Facts round trip with exact-bit keys, the binding/fencing/privacy obligations and
  the rejection table above — all frozen at v1.
* The two page fixtures give a deterministic positive path and a deterministic Needs path;
  `tools/fill_facts_from_needs.py` converts an observed Needs into a facts skeleton.
* Pending from this lane (does not block native implementation): engine-observed goldens under
  `contract/expected/`, the built riscv64 binary and its receipt, and the launcher.
