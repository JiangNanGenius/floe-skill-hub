# Automatic publication pipeline

This repository publishes skill updates fully unattended through GitHub
Actions only. There is no local daemon, no scheduled task on any developer
machine, and no Mac, app or model dependency at any stage. Maintainer intervention covers deliberate policy or tooling changes, initial
activation, changes needing new runtime qualification, and exceptional
manual signing (see [docs/SIGNING_BRIDGE.md](SIGNING_BRIDGE.md)).

## Shape of the pipeline

Three narrowly scoped GitHub Actions jobs cooperate across the two
repositories. Everything they write lives on dedicated refs; the public main
branches advance only through an exact compare-and-swap.

| Stage | Where | What it does |
| --- | --- | --- |
| Scan | Hub `skill-hub-upstream-tracker.yml` | Grouped upstream check → plan → stage, then commits the minimal **unsigned** candidate `S` to a `auto/candidate-<date>-<run>-<attempt>` ref and posts a strict six-field request on the orphan control branch `auto-state`. |
| Sign | App `floe-skill-hub-auto-publication.yml` (template in `automation/workflows/`) | A read-only orchestrator re-verifies the candidate independently, two isolated sign jobs run the existing unchanged signer (`reviews`, then `catalog`) with the signing key visible in exactly one step each, and a separate metadata-only relay job publishes signatures, the authenticated receipt and bounded indexes onto the orphan branch `skill-hub-signing-relay` under the top-level `signing-relay/` prefix. Content is never relayed — it is reproducible from the immutable Hub candidate refs; binaries and packages never enter the relay. |
| Publish | Hub `skill-hub-auto-publish.yml` | Cheap polls re-derive the candidate from its own immutable selected upstream commits, restore every historical review pair into `X`, rebuild deterministic feeds into `Y`, append the cumulative ledger into `H`, and then advance Hub main exactly once from the freshly resolved live base `B` to `H` through the GraphQL `updateRefs` exact CAS (`beforeOid = B`, `force = false`). Only after the CAS does the control branch close the request as processed. |

Refs discipline: automation never force-pushes, never writes main directly,
never tags, never releases. Data branches are orphan or candidate refs only;
the control branch (`auto-state`) and the relay branch each carry one
allowlisted closed set of files, verified whole-tree (paths, modes, no
symlinks) before every push. Orphan branches are bootstrapped from the empty
tree, never by checking out an orphan branch over a working tree. Every
checkout keeps `persist-credentials: false`; pushes in mutating jobs
authenticate with the job-scoped runtime token passed strictly through the
environment into a Git credential helper. The signing key never exists in
this repository and never crosses into the Hub side.

Verification is re-derivation, not agreement: each candidate's selected
upstream commits are proven reachable on the fixed official upstream and
descendants of the previously pinned commits, the trusted tracker re-runs its
gates over exactly the touched skill ids, and committed bytes must equal that
re-derivation. Upstream moving later cannot invalidate a legitimate
candidate, and reported counts in manifests are never treated as authority.
See [docs/UPSTREAM-TRACKING.md](UPSTREAM-TRACKING.md) for the tracking model,
[docs/UPSTREAM-PIN-CONTRACT.md](UPSTREAM-PIN-CONTRACT.md) for per-entry pin
provenance, and [docs/ANDROID-PORTABLE-GUIDES.md](ANDROID-PORTABLE-GUIDES.md)
for the Android projection of the same published data.

## Cadence

- Scan: every 6 hours at 02:37, 08:37, 14:37 and 20:37 UTC (offset from the
  hourly peak), plus manual dispatch with a dry-run option.
- Sign-side poller: every 30 minutes at :17 and :47.
- Publisher poll: every 30 minutes at :21 and :51.
- Each workflow serializes its own runs. The App signer shares the existing
  signing concurrency group; stages across repositories coordinate through
  verified control/relay state and the exact compare-and-swap on main. A run
  with nothing to do exits after bounded tokenless public reads and writes
  at most one cheap daily checkpoint on the control branch.

Schedule limitations are platform realities: GitHub may delay or occasionally
drop scheduled runs under load, and schedules are automatically disabled for
repositories inactive for 60 days. Polls are idempotent and state-driven, so a later run can catch up after a
delayed tick. Re-enable an inactive workflow in the repository Actions
settings when necessary; manual dispatch can run an active workflow without
waiting for its next scheduled tick.

## Holding, recovery and stale work

- **Held drift** (a candidate that cannot be safely auto-admitted) becomes
  actionable committed state on `auto-state`; the published version stays
  intact and the reason is readable there.
- A new scan against a live base with a request still in flight never
  replaces that request (bounded busy-checkpoint).
- A request whose bound base is no longer live is superseded when a fresh
  candidate exists, or closed idempotently (archived, never re-processed) on
  the next scan or no-op checkpoint. Nothing can stall the pipeline forever.
- Crash-point recovery is part of the poll: if a previous run died after
  pushing the candidate tip but before finishing its control write or CAS,
  the tip is cryptographically proven to equal the exact expected next state
  (the original commit chain, never a freshly rebuilt substitute), and the
  run continues from there — emit the catalog request over the same `X`,
  retry the exact CAS on the same original `H`, or re-verify the public chain
  and close the request. An unexpected tip is rejected with nothing written,
  and the legacy manual signer remains available at any time.
- On the App side the two sign jobs re-resolve the live Hub base from the
  fixed origin immediately before touching the key and hold (sign nothing)
  if it moved since verification, so signatures are never issued against a
  stale ledger baseline.

## Activation variables

Both workflows stay inert until the maintainer sets repository variables:

- Hub repository variable `FLOE_SKILL_HUB_AUTO_UPDATES` = `enabled` starts
  the scan and publisher.
- App repository variable `FLOE_SKILL_HUB_AUTO_SIGNING` = `enabled` starts
  the sign-side poller — only after the App workflow copy contains the
  rendered one-time anchor commit literal (a 40-hex Hub commit reviewed to
  carry all pipeline code, policy and gates; the template placeholder fails
  closed until then). Any change to Hub scripts, trust inputs, schemas or the
  pinned policy requires an equally deliberate anchor repin.

Setting either variable back to any other value (or removing it) stops that
side immediately; data branches keep the last known-good content, and the
main publication only ever advances through the verified CAS.

## Reuse of qualification evidence — stated honestly

A candidate may reuse an earlier real qualification proof only when the
runtime, assets, dependency and permission fingerprint are unchanged and the
proof is bound to exactly those bytes. Any runtime or engine change requires
a fresh real qualification; source inspection, host execution or synthetic
fixtures are never counted as execution-verified. The bundled generic engine
remains a separately updated component, and its guest qualification is not
promised automatically by this pipeline.

## What is tracked

Current automatic tracking covers 43 skills: 30 generic upstream skills plus
1 engine managed separately, 5 watch-only references, 4 built-ins and 3
first-party items. Unlicensed replacements are never copied, and curated
admissions, licenses and notices follow the catalog contract.
