# H3 Impeccable engine handoff — artifact, launcher and goldens

For: the iOS main owner (A1 store/install, A2 `browser.observe profile: design`
capture and file bridge) and the coordinator.
State: **artifact built and executed on riscv64 under emulation; the Floe Linux
guest run and App acceptance are still pending and stay with Main.**

Everything below is repo-relative. No private checkout path, credential or host
detail is recorded here.

## 1. The artifact

| Field | Value |
| --- | --- |
| Path | `engines/impeccable/dist/impeccable-0.1.17+floe.1.0.0/riscv64gc-unknown-linux-musl/floe-impeccable` |
| SHA-256 | `af8795bf9636e763541c58ef90ee889941e468f453ec6580c32a89a5a758b87b` |
| Size | 5,579,704 bytes |
| Format | ELF 64-bit LSB executable, machine **RISC-V** (0xF3), type **EXEC**, little-endian, RVC + double-float ABI, stripped |
| Linkage | **static** — no `PT_INTERP`, no dynamic loader, no glibc dependency (musl) |
| Engine id | `impeccable-0.1.17+floe.1.0.0` |
| Upstream | `pbakaus/impeccable` @ `4fc2f83e1c8710dba772bfd4523d0efab57737b6`, tree `1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72`, `ENGINE_VERSION 0.1.17`, skill package `4.7.1`, Apache-2.0 |
| Pin authority | `docs/UPSTREAM-PINS.json` (review baseline 2026-10-26) |
| Patches | `patches/0001-floe-context-network-and-updater-trim.patch` (sha256 in `PROVENANCE.json`) |
| Adapter | `adapter/` (12 Rust sources, sha256 per file in `PROVENANCE.json`), staged as `crates/floe-impeccable` |
| Embedded contract | the frozen 32 contract files, digest-verified at staging; `floe-impeccable contract` prints bytes identical to `contract/snapshot-contract.v1.json` |
| Toolchain | rustc 1.98.1 (`RUSTUP_TOOLCHAIN=1.98.1`), target `riscv64gc-unknown-linux-musl`, `-C target-feature=+crt-static -C link-self-contained=no` plus `--remap-path-prefix` so no private build path is embedded, zig 0.17.0 as the C compiler/linker driver, 6 jobs, `CARGO_NET_OFFLINE=1`, `SOURCE_DATE_EPOCH=1761436800` |
| Dependency graph | 130 crates; **no `ring`, `rustls`, `aws-lc-rs`, `rustls-native-certs`, `webpki-roots`** (the build fails if any is reachable) |
| Reproducibility | a cold rebuild in a fresh cargo target dir produced a **byte-identical** artifact, `af8795bf…` (`evidence/reproducibility.json`) |
| Licenses shipped | `LICENSE-impeccable-apache-2.0`, `NOTICE-impeccable.md` (upstream verbatim), `LICENSE-adapter` (MPL-2.0) |
| Receipts | `PROVENANCE.json`, `BUILD-RECEIPT.json`, `SHA256SUMS.txt` next to the binary |

Host comparison build (behavioural parity only, **not** the guest engine):
`aarch64-apple-darwin` dev, 32,791,120 bytes, `079c102abecdf5157a9ab947cb0fbdff1d37b4d3db4aff422834d375d73fd86a`.

## 2. Launcher: exact contract

Path in the skill package: `sources/impeccable/scripts/floe-impeccable`
(sha256 `b317617bb9f473a4d80b3477543d015f8d7d2645f63f0998acbce43bcbf58cc4`).
POSIX `sh`, no Node, no download path, no user cache.

Invocation:

```sh
sh <skill>/scripts/floe-impeccable <verb> [args...]
```

Required/optional environment:

| Variable | Required | Meaning |
| --- | --- | --- |
| `FLOE_IMPECCABLE_ENGINE` | no | explicit absolute path to the verified engine binary; highest priority |
| `FLOE_IMPECCABLE_ENGINE_DIR` | no | directory holding `<triple>/floe-impeccable` (or `floe-impeccable` directly) |
| `FLOE_IMPECCABLE_VERIFY_DIGEST` | no | `1` re-verifies the binary against the engine directory's `SHA256SUMS.txt` before exec; default off (install-time verification is the primary gate; hashing 5.6 MB per call is expensive on an emulated guest) |
| `IMPECCABLE_SKILL_DIR` | set by the launcher | skill directory the engine reads `reference/*.md` and `scripts/command-metadata.json` from; defaults to the launcher's parent's parent |
| `IMPECCABLE_SELF` | set by the launcher | how the engine names itself in printed commands |
| `FLOE_IMPECCABLE_LAUNCHER_PROBE` | internal | marks a probe child so a recursive launcher never loops |

Architecture mapping (`uname -s` / `uname -m` → triple): `linux`+`riscv64` →
`riscv64gc-unknown-linux-musl`; `linux`+`aarch64|arm64` →
`aarch64-unknown-linux-gnu`; `linux`+`x86_64|amd64` →
`x86_64-unknown-linux-gnu`; `darwin`+`arm64` → `aarch64-apple-darwin`.
The upstream launcher maps only `arm64`/`x64` and otherwise tries to download a
release asset — that path does not exist here.

Resolution order: `FLOE_IMPECCABLE_ENGINE` → `FLOE_IMPECCABLE_ENGINE_DIR/<triple>/`
→ `FLOE_IMPECCABLE_ENGINE_DIR/floe-impeccable` → a Hub-installed
`engines/impeccable/dist/<engineId>/<triple>/floe-impeccable` next to the skill →
`floe-impeccable` on `PATH`, accepted **only** after it answers `engine-probe`.

Exits: the engine's own exit code on success; **127** when no engine can be
resolved, when the explicit path is not executable, or when the requested digest
check fails (`digest mismatch` / missing `SHA256SUMS.txt` / no sha256 tool).
A missing binary never triggers a fetch: stderr says the Hub owns installation.

Recommended guest invocation for the App: set `FLOE_IMPECCABLE_ENGINE` to the
digest-verified binary staged in the task's resolved environment, and
`IMPECCABLE_SKILL_DIR` to the installed skill directory.

## 3. Engine CLI: exact contract

```
floe-impeccable engine-probe        -> "impeccable-engine 0.1.17+floe.1.0.0\n", exit 0
floe-impeccable --version           -> "0.1.17+floe.1.0.0\n", exit 0
floe-impeccable contract            -> the frozen contract JSON, byte-identical to the committed file, exit 0
floe-impeccable snapshot-schema     -> producer-facing capture contract (138 style columns, 23 pseudo, 31 states, limits, 4 schemas), exit 0
floe-impeccable snapshot-scan ...   -> the v1 design scan (below)
floe-impeccable detect ...          -> upstream static source/markup scan (offline), upstream exit semantics
floe-impeccable context ...         -> upstream project context brief (offline)
floe-impeccable ignores|detect-csp|palette|signals ...
floe-impeccable --help              -> Floe usage (never advertises a refused verb), exit 0
```

`snapshot-scan`:

```
floe-impeccable snapshot-scan \
  --snapshot <snapshot.v1.json> \
  --identity <identity.v1.json> \
  [--facts <facts.v1.json>]... [--config <config.v1.json>] \
  [--out <result.v1.json>] [--round N] [--max-rounds N] \
  [--max-hit-tests N] [--max-hit-tests-total N] [--max-snapshot-bytes N] \
  [--timeout-ms N] [--strict-schema|--no-strict-schema] [--allow-missing-identity]
```

* stdin is never read; no network, no CDP, no Chromium, no `evaluate`.
* `--out` is written staged-then-renamed (`*.part` → final), so a reader never
  sees a partial result. Without `--out` the result document goes to stdout.
* stderr carries exactly one summary line
  (`floe-impeccable: snapshot-scan status=… verdict=… exit=…`) and never page
  text, attribute values or finding detail.
* Exits: **0** clean · **2** findings · **3** `needs-facts` · **4** `inconclusive`
  coverage · **1** usage/invalid/identity/budget/timeout/cancel.
* A result document is written for failures too (`status: failed`,
  `error.code`, `error.detail`), so the caller always has a machine-readable reason.
* One invocation is **one round**: the engine does not drive the fixpoint itself.
  Round 1 returns `needs.hitTests` (+ `hitTestsBits`, + `scrollProbes`); the
  native side answers on the same document identity and re-invokes with `--facts`
  and `--round 2`.

Stable error codes: `usage`, `io`, `snapshot-parse`, `snapshot-version-unsupported`,
`schema-mismatch`, `identity-invalid`, `identity-mismatch`,
`identity-untrusted-producer`, `identity-redaction-not-applied`,
`identity-superseded`, `facts-parse`, `facts-binding-mismatch`,
`facts-bits-mismatch`, `budget-exceeded`, `timeout`, `cancelled`, `engine`, plus
`verb-unavailable` for refused upstream verbs.

Budgets (contract defaults, all overridable per call): 48 MiB snapshot,
30 000 elements, 4 rounds, 4096 hit tests/round and 16 384 total, 120 000 ms.
Observed on the fixtures: a 7-element page asks **169–186 hit-test points** in
round 1, so a real page's point count is the number to size the native answerer
against, and `--max-hit-tests` may need raising for large pages.

Refused verbs (exit 1, `verb-unavailable`, each naming its Floe owner):
`install`/`update`/`check`/`link`/`skills` (Hub owns installation),
`telemetry`, `generate-image`/`concept-seed`/`serve-question`,
`component-review`/`capture-server`/`font-match`/`build-phase`/`comp-spec`/`comp-diff`
(Chromium/CDP), `hook*`, `live*`, `doctor`, `pin`, `surface-brief`,
`critique-storage`, `embed-prompt`, `init`. `detect <url>` and `detect --cdp`
are refused with the native-capture alternative instead of launching a browser.

## 4. What A2 must produce (unchanged, frozen)

`contract/SNAPSHOT-CONTRACT.md` and `contract/producer/NATIVE-PRODUCER.md` are
the authority. In short: a v1 snapshot (138 style columns per element in
`styleProps` order, element id = document-order index + 1, shadow elements
appended last), a bound identity (`taskId`, `sessionId`, `tabId`, `documentId`,
`captureId`, `documentGeneration`, `url`, `hostname`, `viewport`, `scroll`,
`capturedAtMs`, `producerTrust: native-fixed-script`, `producer.scriptDigest`,
`redaction{policy,applied,…}`), and facts that echo the exact double bits and the
same binding. Navigation, reload, a generation bump, a viewport change or a
scroll fences the capture.

## 5. Goldens

* `contract/expected/riscv64-docker/` — **21 riscv64-observed result documents**
  with `MANIFEST.json` (per-case exit, status, verdict, error code, findings,
  uncovered passes, sha256, bytes) and the runner identity.
* `contract/expected/host-arm64/` — the same 21 cases observed on the host build.
* `contract/expected/README.md` — what the goldens are, the two normalized
  volatile fields, and how to regenerate them.
* `workflows/tools/compare_expected.py` re-runs the matrix with a candidate
  binary and fails on an unapproved golden difference (verified: 21/21 identical).
* `adapter/tests/data/` — the derived snapshots and reference facts the Rust
  suite uses; `adapter/tests/data/README.md` records how they were produced and
  why checking them in is a regression gate for upstream updates.

Key observed behaviours (identical on host arm64 and riscv64):

| Case | Exit | Status | Verdict |
| --- | --- | --- | --- |
| positive page, round 1 (no facts) | 3 | `needs-facts` | `none` — 183 points, findings withheld |
| positive page, round 2 (facts) | 2 | `complete` | `findings` — `tiny-text` ×1 |
| overlay page, round 1 | 3 | `needs-facts` | `none` — 169 points |
| overlay page, round 2 | 2 | `complete` | `findings` — `text-occlusion` ×1 |
| page with no findings, answered | 4 | `inconclusive` | `inconclusive` — 0 findings, 6 required passes uncovered |
| every point declared unanswerable | 4 | `inconclusive` | `inconclusive` — `hit-test-fixpoint: unanswered`, terminal |
| truncated / bad version / column mismatch | 1 | `failed` | `snapshot-parse` / `snapshot-version-unsupported` / `schema-mismatch` |
| identity mismatch / missing binding / no redaction / model trust / fenced | 1 | `failed` | `identity-mismatch` / `identity-invalid` / `identity-redaction-not-applied` / `identity-untrusted-producer` / `identity-superseded` |
| facts bits drift / stale capture / other tab | 1 | `failed` | `facts-bits-mismatch` / `facts-binding-mismatch` |
| snapshot bytes / round budget / `--timeout-ms 0` | 1 | `failed` | `budget-exceeded` / `timeout` |

**`verdict: clean` is unreachable in v1 by design**: pixel contrast, reveal
sweep, content-hidden-at-rest, script errors and iframe content are uncovered and
each blocks a clean verdict, so an empty finding list is `inconclusive` with
`coverage.uncoveredRequired` naming the gaps. Do not present that as a pass.

## 6. Verified boundaries — what is proven where

| Boundary | Status | Evidence |
| --- | --- | --- |
| Contract coherence (schemas, columns, fixtures, pin) | **verified**, 61/61 checks | `evidence/contract-validation.json` |
| Adapter suite (host arm64) | **verified**, 38 tests, 0 failed | `evidence/build-summary-host-dev.json` |
| Behaviour matrix on host arm64 | **verified**, 74/74, incl. 25/25 upstream oracle goldens byte-identical for `detect` | `evidence/verify-host.json` |
| Static artifact identity (ELF/arch/static/digest) | **verified** | `dist/.../BUILD-RECEIPT.json`, `PROVENANCE.json` |
| No TLS/crypto in the dependency graph | **verified** (build fails otherwise) | `BUILD-RECEIPT.json → dependencyAudit` |
| Reproducible rebuild | **verified**, byte-identical from a cold cache | `evidence/reproducibility.json` |
| Execution on riscv64 | **verified under Docker/qemu user-mode emulation**, `uname` = Linux riscv64, kernel 6.8.0-117-generic: 74/74 checks, 12/12 upstream goldens byte-identical, launcher 25/25 incl. a real scan returning Needs | `evidence/verify-riscv64-docker.json`, `evidence/verify-launcher.json`, `contract/expected/riscv64/MANIFEST.json` |
| Execution in the **Floe Linux guest** (Debian 13 riscv64, TinyEMU, kernel 4.15, 256 MB default RAM, no JIT) | **NOT verified — pending, Main-owned** | needs the dedicated non-shared qualification path; this lane must not boot or mutate the occupied guest |
| Guest latency/memory headroom for large captures | **NOT measured** | emulated timing (~110–130 ms for an 18 KB snapshot) is not a TinyEMU prediction |
| Native WebKit capture parity (computed styles, `checkVisibility`, pseudo-elements, keyframes, font metrics) | **NOT verified** | no real producer yet; `coverage.style-parity` + `unknownStyleProps` is the built-in diagnostic to watch |
| App integration (`profile: design`, file bridge, task-owned staging, permissions) | **NOT verified** | A2/Main own it |
| Publication (signed catalog, review record) | **not authorized here** | coordinator/release owner |

Emulated or host execution is never product-guest proof, and a static ABI check
is never runtime proof; the table above keeps those apart deliberately.

## 7. Alignment with the committed native implementation

Checked against the App source at commit
`6940f196b871c2dce15f26b45b08fadbe2e4b8c6` (`FloeAgent/FloeApp/Browser/*` and
`FloeAgent/FloeApp/Resources/Impeccable/*`), read-only via `git show`:
**86/86 alignment checks pass** (`evidence/native-alignment.json`, reproduced with
`build/verify_native_alignment.py`).

| Agreement | Result |
| --- | --- |
| The 9 contract files vendored into the App bundle | **byte-identical** to the frozen hub files (contract `baf24531…`, snapshot schema `a0463585…`, facts `b681b550…`, identity `56893390…`, result `8a9db66d…`, style-props `6bcf54a6…`, pseudo-props `a8893e75…`, state-pseudos `537fff1d…`, capture-limits `9d87ebb7…`) |
| Pin hardcoded in `ImpeccableContract` | commit `4fc2f83e…`, tree `1363fadf…`, engine `0.1.17`, package `4.7.1` — the same single pin |
| Budgets | 48 MiB / 30 000 elements / 4 rounds / 4096 per round / 16 384 total / 120 000 ms — identical |
| Exit codes | `clean=0, failure=1, findings=2, needsFacts=3, inconclusive=4` — identical |
| `needs` keys | `hitTests`, `hitTestsBits` (decimal u64 strings), `scrollProbes`, `round` — identical |
| `facts` keys | `taskId, sessionId, tabId, documentId, captureId, documentGeneration, fenced, hits, shownOnScroll`; per hit `x, y, xBits, yBits, top, stack, unanswerable, reason` — identical (the engine accepts `xBits`/`yBits` as a decimal string or a number) |
| `result` keys | `contract, contractVersion, status, verdict, identityCheck{state,mismatches}, budget{exceeded}, coverage{passes[],uncoveredRequired,unknownStyleProps}, needs, findings.counts.total, error{code,message}, identity` — the native parser reads exactly the paths the engine writes |
| Coverage rule | v1 never certifies clean; `uncoveredRequired` drives the verdict on both sides |
| Producer | `impeccable-producer.v1.js` = 55 565 bytes, sha256 `5bfbcee7…`; its first 40 590 bytes are the **verbatim** pinned upstream `browser-bundle/15-snapshot.js` minus the trailing newline (sha256 `99801a23…`), then one separator newline, then the 14 974-byte Floe adapter (sha256 `4ce19da8…`) |

Two precise notes for the native side, neither an incompatibility:

1. `contract/provenance/pinnedSourceDigests["browser-bundle/15-snapshot.js"]` is
   `b97e055f…`, the digest of the **full 40 591-byte** upstream file. The embedded
   prefix is 40 590 bytes and hashes to `99801a23…`. `PROVENANCE.md` in the App
   bundle cites `b97e055f…` next to the "bytes 0…40590" range; the bytes are
   verbatim, only the digest/range wording needs that distinction.
2. `ImpeccableResultDocument.parse` falls back to counting `group["items"]` when
   `findings.counts.total` is absent. The upstream `CollectResult` (and therefore
   this engine) writes `groups[].findings`, not `items`, so the fallback would
   undercount. This engine always writes `findings.counts.total`, so the primary
   path is used; the fallback key is worth aligning if it is ever relied on.

### End-to-end invocation as the native surface actually shapes it

Capture (native, no engine involved):

```
browser.observe(profile: "design", designAction: "capture", tabID: <tab>)
-> { "profile": "design", "state": "captured",
     "capture": { captureId, binding{taskId,sessionId,tabId,documentId,documentGeneration,captureId},
                  bridgeRootIsTaskWorkspace, relativeDirectory,
                  relativeSnapshotFile,   // Impeccable/<owner>/<captureId>/snapshot.v1.json
                  relativeIdentityFile,   // Impeccable/<owner>/<captureId>/identity.v1.json
                  documentGeneration, elementCount, snapshotBytes,
                  viewport{width,height}, scroll{x,y}, redaction{…}, scriptDigest } }
```

Round 1, in the resolved Linux environment through `exec.shell` (paths are the
task workspace's own; the engine never chooses a directory):

```
floe-impeccable snapshot-scan \
  --snapshot "<ws>/Impeccable/<owner>/<captureId>/snapshot.v1.json" \
  --identity "<ws>/Impeccable/<owner>/<captureId>/identity.v1.json" \
  --out      "<ws>/Impeccable/<owner>/<captureId>/result.round1.v1.json" \
  --round 1
# exit 3 = needs-facts; the result document carries needs.hitTests / hitTestsBits
```

Facts (native answers the points on the same capture):

```
browser.observe(profile: "design", designAction: "facts",
                captureID: <captureId>,
                needsFile: "Impeccable/<owner>/<captureId>/result.round1.v1.json")
-> { "state": "factsReady", "captureID": …,
     "relativeFactsFile": "Impeccable/<owner>/<captureId>/facts.round1.v1.json" }
```

`needsFile` may be a pure Needs document or a full engine result; a full result
first goes through the native identity/current-view assessment. The engine's
`--out` document is the full result, so that assessment path is the one used.

Round 2:

```
floe-impeccable snapshot-scan \
  --snapshot "<ws>/…/snapshot.v1.json" --identity "<ws>/…/identity.v1.json" \
  --facts    "<ws>/…/facts.round1.v1.json" \
  --out      "<ws>/…/result.round2.v1.json" --round 2
# exit 2 = findings, exit 4 = inconclusive (0 findings, uncovered passes),
# exit 3 = still needs facts (a new round, up to --max-rounds 4)
```

Release:

```
browser.observe(profile: "design", designAction: "release", captureID: <captureId>)
-> "Design capture released"
```

Every step is bound to the actual run/task/session/workspace root/environment and
tab; a capture is not reusable across another task or another run, and a fenced
capture is refused by both sides.

### Catalog metadata for the engine dependency

The engine is a separate digest-bound Linux execution dependency, not skill-ZIP
content. For the `profile: design` capability the catalog entry needs
`minimumAppVersion` **>= 1.7.59** (the first build carrying the native design
capture and file bridge), plus the execution OS/architecture pair
(`linux` / `riscv64`) and the artifact digest
`af8795bf9636e763541c58ef90ee889941e468f453ec6580c32a89a5a758b87b`. Main rechecks
real version occupancy before archiving; this lane does not set versions.

## 8. Pending, with the exact next step

1. **Guest execution (Main).** Stage `dist/impeccable-0.1.17+floe.1.0.0/riscv64gc-unknown-linux-musl/floe-impeccable`
   into a task's resolved Linux environment and run, in this order:
   `./floe-impeccable engine-probe`;
   `./floe-impeccable contract | sha256sum` (expect
   `baf2453164be6162703af9d671be16da152fa874db53ce95ad5b3516d40de4a3`);
   then `snapshot-scan` with `contract/fixtures/snapshot-needs-hit-tests.v1.json`
   + `contract/fixtures/identity-needs.v1.json` (expect exit 3, `needs-facts`,
   169 points) and again with
   `adapter/tests/data/facts-overlay-round2.v1.json --round 2` (expect exit 2,
   `text-occlusion` ×1). Record wall time and peak RSS for the guest latency
   question; a 5k–30k-element capture is the real sizing test.
2. **Native producer (A2).** Implement the fixed WebKit measurement against
   `contract/producer/snapshot.schema.v1.json`, with redaction and binding, and
   answer `needs.hitTests` via `elementFromPoint`/`elementsFromPoint` mapped to
   snapshot ids. `contract/tools/observe_and_complete.py` is an executable
   reference for the answer shape and the fixpoint loop.
3. **Skill packaging (H1/coordinator).** `sources/impeccable/skill/` is the
   package source; the engine is a separate digest-bound Linux dependency and
   must not go into the skill ZIP.
