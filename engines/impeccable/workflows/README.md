# Updater and PR-recovery workflows

The installed `.github/workflows/impeccable-engine-updater.yml` mirrors the
reviewed `engines/impeccable/workflows/impeccable-engine-updater.yml` template.
Both copies are checked together. The updater implements the follow-up rule
from the implementation plan (§3.2): a daily upstream check plus a manual
trigger, a pinned-source build, the rule and snapshot-contract regressions, and
a review-only pull request.

The separate `.github/workflows/impeccable-engine-review.yml` is the PR-only
recovery path. It never rebuilds the engine: given one already completed,
successful updater run, it re-proves that run's candidate against the engine
inputs checked out now and opens (or reports) the same draft `ENGINE-LOCK.json`
proposal. Root dispatches it explicitly; it is not scheduled.

## Update policy

The automatic (scheduled) path only ever proposes **forward** updates:

* only non-draft, non-prerelease releases tagged exactly `engine-v<semver>`
  are considered, and the tag must agree with the `ENGINE_VERSION` in its own
  tree — a mismatch fails closed;
* `changed` is true only when the candidate engine version is **strictly
  newer** (semver) than the pinned one;
* a same-version release tag retargeted at a different commit, or an older
  version, is reported unchanged with the reason in the step summary: the pin
  is retained, nothing is rebuilt, no same-version/downgrade PR is proposed;
* a manually dispatched `--requested-ref` may stage an intentional
  different-commit/same-version candidate, marked `manual-review`, for a human
  to review — never an automatic install. An identical pin is a no-op.

The real upstream case this guards against: the pinned commit and the latest
release tag can diverge at the same engine version (a retagged or
re-published release); the previous `commit diff OR version diff` rule then
proposed a same-version "update" every single day.

## Jobs

| Job | Purpose |
| --- | --- |
| `pin` | resolve the newest stable upstream `engine-v*` release tag (or a dispatched ref), read `ENGINE_VERSION` at that commit, apply the forward-only update policy against `ENGINE-LOCK.json`, and report the decision (mode + reason) in the step summary (`contents: read`) |
| `build-and-verify` | stage a validated candidate lock, contract identity and temporary test bindings; preflight the pinned patches; build the riscv64 static engine and host comparison build with the dependency audit enabled; run adapter, contract and behaviour checks; authenticate the published baseline and select exactly one strict comparison reference (matching historical goldens or a fresh record of the digest-bound published binary); regenerate candidate-derived skill source; upload reviewer artifacts. The always-run collector preserves an already-built binary, lock and original logs even when a later gate fails (`contents: read`) |
| `open-update-pr` | stage the pin with `update_lock.py` and hand the lock to the shared `open_review_pr.py` helper, which commits with the corrected `git -c key=value` identity, pushes without force, opens or reports the **draft** PR, and refuses anything except `ENGINE_DIR/ENGINE-LOCK.json` (`contents: write` + `pull-requests: write`, default token only) |

## PR-only recovery (`impeccable-engine-review.yml`)

Use this when an updater run produced a fully verified candidate artifact but
the draft-PR tail failed (for example the 2026-10-28 run 40648648353, whose
commit was rejected by the malformed `git -c` form). Root alone dispatches it:

```sh
gh workflow run impeccable-engine-review.yml --repo JiangNanGenius/floe-skill-hub \
  -f candidate_run_id=40648648353
```

The `verify-candidate` job is read-only (`contents: read`, `actions: read`) and
calls `tools/verify_candidate_reuse.py`. It fails closed unless all of the
following hold:

* the run is from the fixed official repository and the fixed updater workflow
  path, on `main`, attempt 1, completed successfully, and its head commit is an
  immutable ancestor of the dispatch checkout;
* the specific `Build and verify the candidate engine` job really succeeded (a
  skipped/failed job is not proof), every required gate step succeeded, and
  exactly one of the two routed Needs/facts comparisons ran;
* the protected engine inputs (tracked lock, adapter, build, contract, patches,
  published dist, root `LICENSE` and the five tools the old recipe actually
  invoked) are byte-identical between the run head and the current checkout,
  and the updater recipe above `open-update-pr:` is text-identical, so a later
  PR-tail/test-fixture fix does not invalidate the native proof;
* exactly one unexpired canonical `impeccable-engine-candidate` artifact
  exists, its downloaded zip matches GitHub's digest, and it extracts safely
  (no traversal, links, devices, odd modes or unknown top-level payload);
* the compiled riscv64 ELF, build receipt, `SHA256SUMS.txt`, provenance,
  projected-test receipt, contract digests, behaviour logs, routed comparison,
  published-baseline record and derived source all bind to the candidate; and
* the current published base/adapter are still byte-identical to the ones the
  original run authenticated.

The verification job uploads only the tiny `impeccable-engine-review-payload`
JSON (lock proposal, pin/version/run/artifact identity, protected-input and
recipe digests). The separate `open-draft-pr` job fresh-checks out the current
main, downloads that payload, re-validates it against the current tree and base,
writes only `ENGINE_DIR/ENGINE-LOCK.json`, commits with the corrected identity,
pushes without force and opens a draft PR. It reports an existing matching draft
PR idempotently; a conflicting branch, a non-draft PR, a fork PR, a user file
edit or any extra path is a HOLD. No binary, source commit, descriptor or
current-main change enters the review branch. The job outputs the draft PR URL.

Before any commit, push or PR, the write job re-fetches the **live official
default branch** (the immutable dispatch checkout is not enough while a job
waits). Its `ENGINE-LOCK.json` must still produce the exact proposal from the
same published baseline, and the protected engine inputs and the updater recipe
above `open-update-pr:` must still match the proof. A newer published baseline
or any such drift is a HOLD; an unrelated main advance is allowed and the new
review branch is based on the live default branch so it does not revert it. The
normal `--lock-auto` path applies the same live check against the dispatch
baseline. A same-version **manual-review** candidate (same `ENGINE_VERSION`, a
different commit) remains valid against the same baseline; an older version is
still refused as a downgrade.

Both recovery jobs honor `FLOE_IMPECCABLE_UPDATE_PRS=enabled` and the existing
owner-approved repository setting that lets Actions create PRs. The workflow
does not approve, merge, sign, publish, install or dispatch anything else. Both
workflows set `PYTHONDONTWRITEBYTECODE=1`; `open_review_pr.py` also sets
`sys.dont_write_bytecode = True` before importing the local verifier, and the
clean-tree check deliberately does **not** ignore `__pycache__`, so the write
job cannot HOLD on its own generated bytecode files.

The tracked `ENGINE-LOCK.json`, the frozen contract, the frozen binary and
`sources/impeccable` are never modified by the workflow. The tracked
`build/build_engine.py` resolves its lock, adapter, patches and contract
module-relative to itself, so a changed candidate is built from the staged
temp tree — invoking the tracked builder on a changed candidate would fail
`verify_pin` (source HEAD vs the old lock) before any preflight.

## Tools

| Tool | Purpose |
| --- | --- |
| `tools/resolve_upstream_pin.py` | pin resolution and comparison; follows stable release tags only, never upstream `main`; shape-validates every dispatch ref (full 40-hex commit or exact `engine-v<semver>` tag, dash-leading strings rejected) and every upstream `ENGINE_VERSION` (exact dotted-semver) before any git argv, API URL or output emission; refuses a release tag that disagrees with its own tree's `ENGINE_VERSION`; applies the forward-only decision policy (strictly-newer automatic updates; same/older versions and identical pins are unchanged no-ops with a recorded reason; a dispatched ref stages `manual-review` only); writes nothing. `--releases-json` is a hermetic regression hook used by the tests in place of the GitHub API |
| `tools/compare_expected.py` | authenticate the candidate against its staged lock before comparing: four `engine.*` identity keys and the two mirrored diagnostic version/pin fields may move only after exact authentication. Diagnostic presence changes remain structural drift. Every other finding, coverage, target, ABI, adapter and diagnostic field stays strict; authenticated identity changes are recorded for review. No broad default ignores |
| `tools/verify_published_baseline.py` | bind the existing published binary and temporary baseline records to the tracked lock, digest, identity, full emulated matrix and corpus. A candidate cannot become its own baseline. Hosted emulation is not real Floe guest or App acceptance |
| `tools/update_lock.py` | rewrites the pin fields in `ENGINE-LOCK.json`, keeps the previous pin as `supersededPin`, and refuses an engine version that does not match the commit |
| `tools/verify_candidate_reuse.py` | read-only PR-recovery verifier: authenticates the completed run, its specific build job and routed comparison, the protected-input/recipe stability, the canonical artifact digest/layout, the compiled riscv64 ELF/receipts/logs/baseline/source and the current published base; emits the tiny metadata payload. Never executes artifact code or a binary |
| `tools/open_review_pr.py` | shared PR controller: validates the verified payload or the `update_lock.py` result, commits only `ENGINE-LOCK.json` with the corrected `git -c key=value` identity, pushes without force, opens/reads back the draft PR, reports an existing matching PR idempotently and holds on conflicts |
| `tools/stage_candidate_engine.py` | copy reviewed inputs into a caller-owned temporary tree, project the validated candidate identity into the contract and exact trusted-test expectations, and bind candidate host-test expectations to Cargo compile-target metadata. Exact anchors, reverse projections and per-file hashes preserve every other test byte; staging the published pin stays byte-identical. Tracked adapter, contract, goldens and published bytes remain untouched |
| `tools/tests/test_template_hardening.py` | stdlib-only regressions for the admission-review fixes and the updater-integration round: pin/ref/version shape checks (valid and hostile inputs against a temporary local git clone), the forward-only decision policy, the stable-release selector, the automatic path end to end through the hermetic `--releases-json` hook, a staged-tree integration run proving `verify_pin` passes the candidate at the patch/preflight boundary while the tracked builder fails the old pin, workflow data-flow lint (no `${{ … }}` inside `run:` blocks, actions pinned to full SHAs, every compile/audit invocation carries `--allow-network` and never skips the dependency audit, staged-builder path only, job-level read/write permission scoping), and checkout-relative redaction in `build/export_evidence.py` with normal data retained. Run: `python3 -m unittest discover -s engines/impeccable/workflows/tools/tests` |
| `tools/tests/test_engine_review_pr.py` | compact synthetic regressions for the PR-only recovery and draft-PR controller: a full positive proof and metadata payload, wrong repository/path/branch/attempt/conclusion, skipped build job, missing gate, ambiguous routed comparison, expired/extra/bad-digest artifact, wrong pin/status/native-payload zip, unsafe zip paths, wrong-machine ELF, protected-input/recipe drift, metadata tampering, a real temporary Git commit/push that changes only `ENGINE-LOCK.json`, a genuine Git failure that propagates, existing matching/conflicting/non-draft/user-edited PR handling, and workflow wiring/permission/action-pin checks |

## Action pins (verified official tag → commit SHAs)

Third-party actions are pinned to full commit SHAs, not floating major tags.
The mapping below was resolved on 2026-10-26 from the action repositories' own
refs (GitHub Git Data API `git/ref/tags/<tag>` plus `git ls-remote` on
`github.com/actions/<action>`, both returning the same objects; each commit
carries the action's `action.yml`):

| Action | Selected tag | Pinned commit SHA |
| --- | --- | --- |
| `actions/checkout` | `v4.4.0` (latest `v4.x`) | `11d5960a326750d5838078e36cf38b85af677262` |
| `actions/upload-artifact` | `v4.6.2` (latest `v4.x`) | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `actions/download-artifact` | `v4.3.0` (latest `v4.x`) | `d3f86a106a0bac45b974a628896c90dbdf5c8093` |

When installing or refreshing the template, re-verify each SHA against the
action repository's tags and update the pin deliberately; never float the tag
back. At selection time the floating `v4` tags pointed at exactly these
commits, so the pin preserves behavior.

## Workflow data flow

Upstream-controlled and dispatch values reach shell steps only through `env:`
mappings as quoted `"$VARS"` argv, and each consuming step re-asserts the
shape (40-hex sha, dotted semver, exact `engine-v<semver>` tag) before use.
Step/job outputs cross the `$GITHUB_OUTPUT` boundary only after the same shape
check inside the emitting step. No `${{ … }}` expression is interpolated into
`run:` script text.

## What this workflow must never do

* **No signing secrets.** Only the default `GITHUB_TOKEN` is used. The
  `pin` and `build-and-verify` jobs are `contents: read`; only `open-update-pr`
  gets `contents: write` and `pull-requests: write`, and nothing in the
  workflow approves or merges. The repository default workflow permission stays
  `read`. Draft PR creation requires the repository owner's explicit approval
  of GitHub's combined create-and-approve switch as well as the workflow's
  scoped write permission. This workflow never approves or merges a PR.
* **No publication.** The built binary is uploaded as a workflow artifact for
  reviewers. It is not committed, not attached to a release, and not offered to
  any client. Packaging, signing and publication stay with the release owner.
* **No automatic replacement.** A failed gate leaves the current pin and any
  installed engine untouched. The PR is a draft and needs review.
* **No rebuild in the PR-only recovery path.** `impeccable-engine-review.yml`
  reuses the exact original candidate artifact and proof; it never compiles the
  engine and never executes the artifact binary. It re-validates the current
  protected inputs and the published base before writing the lock.
* **No binary/source payload in the review branch.** Both PR paths commit only
  `engines/impeccable/ENGINE-LOCK.json`; the recovery metadata carries the lock
  proposal and identities, not the binary or source tree.
* **No unreviewed upstream tracking.** Only stable (non-draft, non-prerelease)
  `engine-v*` release tags are considered; upstream `main` is never followed,
  and same-version or older candidates are never proposed automatically.
* **No silent contract change.** If an upstream bump needs a schema, coverage or
  verb change, that is a v1 contract change and requires coordinator review plus
  a handoff to the native side — not an automated rewrite.

## Before enabling

GitHub's repository setting combines permission to create and approve PRs.
See [GitHub's settings documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#preventing-github-actions-from-creating-or-approving-pull-requests).
Do not change it implicitly or claim draft-PR automation works while it is
disabled. Keep the repository default token permissions at `read`.
Draft PR creation also requires the repository variable
`FLOE_IMPECCABLE_UPDATE_PRS=enabled`; absent or any other value skips the PR
job while checks and candidate builds remain available. Set this variable
only after explicit owner approval of the combined permission switch.

1. Confirm the runner has the pinned toolchain available: Rust `1.98.1` with the
   `riscv64gc-unknown-linux-musl` target, and zig `0.17.0` from PyPI (both are
   installed by the workflow itself, pinned by `env:`).
2. Confirm the riscv64 binfmt registration step is acceptable on the chosen
   runner (it uses `docker run --privileged` inside the job's own VM).
3. Decide where the built engine is published from, and keep that decision out of
   this workflow: the guest run in the real Floe Linux guest and the App
   acceptance are prerequisites for qualification and are owned by Main.
4. Bind the comparison reference to the current published artifact. Historical
   goldens are used only when their digest and recorded identity match that
   artifact; otherwise re-run the published binary at its own upstream pin,
   verify and record a temporary baseline, then compare the candidate strictly.
   Keep the archived goldens immutable. A changed result needs investigation;
   candidate output must never be re-recorded automatically as its own baseline.
5. The build job regenerates the derived skill source with the public stage 1
   normalizer (`engines/impeccable/build/skill-source/stage1_normalize_skill_source.py`)
   against a candidate `ENGINE-LOCK.json` staged in the runner temp — the tracked
   lock, `sources/impeccable` and the digest-bound descriptor are not modified by
   the workflow. The reviewer artifact carries the candidate-derived source next
   to the binary and logs so the regeneration diff can be reviewed without
   re-running the build.
