# Signing Bridge — DATA-ONLY Publication Signing

This document describes `scripts/sign_publication.py`: the fixed trusted
tooling that produces production signatures for review records and the
signed channel catalogs, WITHOUT ever mutating the Hub content itself. It is
preparation tooling: no production signing has been performed and the
production private key never enters this repository, this document, or any
receipt.

## Model: T, S/X, Y

| Symbol | Meaning |
| --- | --- |
| **T** | Trusted tooling: one pinned, reviewed commit of THIS repository, checked out separately and executed read-only. All imported code (`hubcore`, `build_catalog`, `runtime_dependency`) must resolve inside T. |
| **S / X** | Data checkout: a SEPARATE clean, exact Git snapshot of the official repository `JiangNanGenius/floe-skill-hub` at a claimed 40-hex commit. S is the review-record input revision, X the release input revision. |
| **Y** | The publication revision created later by the repository owner: the commit that will CONTAIN the signed feeds/archives/reviews staged by the bridge. The bridge never claims or writes Y. |

The bridge never executes, imports, installs or hooks anything from S/X:
data content is only ever hashed, parsed by trusted-T validators, and staged.

## Snapshot verification (not `git status`)

Both roots (T and S/X) are verified with read-only, argument-list-only Git
invocations with system/global config removed, an empty hooks path, no
fsmonitor, inherited Git environment redirects stripped and
`GIT_NO_REPLACE_OBJECTS=1`:

- origin must resolve to exactly `JiangNanGenius/floe-skill-hub`;
- HEAD must equal the claimed 40-hex commit;
- every tracked regular file on disk is hashed and compared against its
  HEAD blob object id, so ignored shadows, `assume-unchanged` /
  `skip-worktree` tampering and local `refs/replace` trees cannot make a
  claimed commit silently resolve to different bytes;
- any on-disk entry outside HEAD (files, directories, symlinks) and any
  tracked symlink or gitlink is rejected;
- the index is never written or refreshed.

## Modes

### `reviews` — sign approved review records (stage-honest, no promotion)

Input: clean S carrying UNSIGNED canonical approved records at
`reviews/<id>/<version>.review.json`. For every actual record the bridge:

1. validates the record against the trusted review contract
   (`hubcore.validate_review`) and rejects anything but an `approve`
   decision, non-canonical bytes, identity drift, or a status/promotion
   mismatch (a record under a registry entry that is not `reviewed` is
   refused — signing never promotes);
2. hashes the real frozen package archives at S and RECOMPUTES their ZIP
   SHA-256, manifest and contentDigest through the unchanged package gates
   (it does not rebuild archives from `sources/` — the canonical
   source-to-ZIP identity is proven separately by the repository owner),
   and joins the record to those actual archive bytes
   (`hubcore.join_review`, per channel) — digest drift, size caps and
   permission drift fail closed;
3. signs each canonical record with the production identity and round-trip
   verifies the envelope against the configured trust root.

Output (fresh `--out` directory outside T and S): the exact canonical
review bytes, a matching `*.review.json.sig` envelope per record, and the
authenticated canonical receipt `signing-receipt.json` +
`signing-receipt.json.sig` binding source commit S, data tree, tooling
commit T, tooling tree, the root key ID (`official-2026-09`), and the
SHA-256/size of every output, review record, package and signature. A
static-content-reviewed record stays static in the receipt; nothing about
the registry changes.

### `catalog` — build and sign the release feeds (launch-gated)

Input: clean X carrying ALREADY-SIGNED reviews (`record + .sig`) and the
qualified registry. The bridge invokes the EXISTING trusted `build_catalog`
release API as a data operation (per-channel package binds, signed-review
joins under T's configured trust, and the H6 runtime-descriptor/artifact
staging included), then enforces the agreed first-release launch gate
BEFORE signing:

- at least 40 unique qualified iOS-channel offers;
- the nine mandatory deep-adaptation IDs are pinned as constants inside the
  trusted tooling (registry `deepAdaptation` relabeling can never satisfy
  the gate): `algorithmic-art`, `canvas-design`,
  `exploratory-data-analysis`, `impeccable`, `literature-review`,
  `markitdown`, `scientific-visualization`, `statistical-analysis`,
  `webapp-testing` — all nine must be present and qualified in BOTH feeds;
- because all nine are real remote-script adaptations in the frozen
  contract, each mandatory slot additionally requires the actual manifest
  `scriptRuntime` remote, frozen adaptation, `status.executionVerified`
  true and a genuinely bound `guest-execution-qualified` review with
  execution `linux/riscv64/guest-verified`. A guide-only replacement of a
  mandatory slot is refused;
- every offered scripted package carries the same guest-qualified review;
  guide-only packages keep `static-content-reviewed` with
  `{os:null, arch:"n/a", evidence:"unproven"}` and no invented guest claim;
- the Android feed must be EXACTLY the set of qualified registry rows whose
  `plannedRuntime.installPlatforms` include `android` (the four builtins are
  iOS-only by contract — no partial drop, no invented rows);
- `impeccable` must retain its real embedded
  `references/engine-dependency.json`; the builder-validated 563-byte
  frozen descriptor bytes and the raw static-ELF `riscv64` engine bytes
  must be present in the output (omitting the descriptor cannot bypass H6).

Output: both canonical feeds plus their `.sig` envelopes, EXACTLY the
feed-referenced package archives and signed review records + envelopes
(re-verified against the feeds' own digests), the staged runtime
descriptor/engine bytes when present, and the authenticated canonical
`signing-receipt.json(.sig)` binding T/X, the tree hashes, the gate
summary, and the SHA-256/size of every output (excluding the receipt and
its own sidecar, so nothing is circular). The artifact is standalone: it
contains what a client needs to read at Y, with no key or Git metadata.

## Key material

- The signing key is read ONLY from the fixed environment variable
  `FLOE_SKILL_HUB_SIGNING_KEY`, decoded exactly like the legacy official
  skill-hub build: strict base64 of the raw 32-byte Ed25519 key material.
- The derived public identity must equal the configured official trust root
  in `public-key.json` inside T (key ID `official-2026-09`). Any other key,
  a missing key, a malformed key, or a drifted root fails closed before any
  file is written.
- Key values never appear in errors, logs or receipts — only the key ID.
- Tests use clearly isolated ephemeral keys inside temporary COPIED tooling
  roots that configure a fake public key; the production pinned root is
  never weakened by tests.

## Output discipline

- `--out` must be a fresh or empty directory OUTSIDE both T and S/X, not a
  symlink; the exact requested leaf is preserved (never retargeted into a
  parent).
- Every file is written with `O_CREAT|O_EXCL` (no foreign overwrite), full
  write loops and byte read-back verification; output paths are
  traversal-safe relative paths.
- The data checkout is never written to. The bridge never commits, pushes,
  opens PRs or creates releases; its output is artifact-only.

## Staging flow (branch plan)

`reviews` input S and `catalog` input X legitimately live on a
coordinator-owned NON-default branch: main-catalog integrity CI refuses
unsigned review records on the default branch, and that is correct — S is
unsigned material until the bridge signs it, and X is signed material
until Y publishes it. The production workflow fetches public 40-hex
commits only, so it can consume a staging-branch commit without promoting
unsigned content to the Hub default branch. The reviewed tooling T is
committed to the default branch first; the workflow pins T as a literal
commit.

## Legacy isolation

The legacy `skill-hub/` pipeline in the App repository and its workflow are
untouched and keep their own key handling. This bridge shares ONLY the key
encoding and envelope shape. All 43 registry entries remain unqualified in
the repository today; using this bridge to sign anything requires the
content lanes and the repository owner to advance actual review, packaging,
guest qualification and the launch gate first.
