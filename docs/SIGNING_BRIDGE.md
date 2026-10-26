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
staging included), then enforces the launch gate BEFORE signing. The
Root-approved staged opening (2026-10-27, following the user's explicit
request to gradually open skills that are still preparing) superseded ONLY
the old batch-completeness rule (at least 40 unique qualified iOS offers
plus all nine mandatory deep IDs present in both feeds). Per-item trust is
unchanged and every gate below stays fully enforced:

- a nonempty genuinely qualified advertised set in BOTH feeds: each feed
  must be EXACTLY the qualified, download-eligible registry rows whose
  `plannedRuntime.installPlatforms` include that channel — no invented
  rows, no partial drop, no duplicates. The four App-provided builtin ids
  are native App features and never Hub download offers, so they are
  excluded by exact ID pinned in the trusted tooling (a `kind`/display/source
  relabel can never hide an arbitrary mandatory ID behind the builtin name);
  the builtins are iOS-only by contract and the iOS exactness is checked
  explicitly, where the old gate had only implied it; an empty feed is
  always refused;
- every offered scripted package still requires `status.executionVerified`
  true, frozen adaptation, and its actually bound review
  `guest-execution-qualified` with execution `linux/riscv64/guest-verified`;
  guide-only packages keep `static-content-reviewed` with
  `{os:null, arch:"n/a", evidence:"unproven"}` and no invented guest claim;
- the nine mandatory deep-adaptation IDs remain pinned as constants inside
  the trusted tooling (registry `deepAdaptation` relabeling can never
  satisfy the gate): `algorithmic-art`, `canvas-design`,
  `exploratory-data-analysis`, `impeccable`, `literature-review`,
  `markitdown`, `scientific-visualization`, `statistical-analysis`,
  `webapp-testing`. Whenever one of them is ACTUALLY offered it must be
  present and qualified in BOTH feeds — a mandatory slot can never be
  advertised on a single channel — and, because all nine are real
  remote-script adaptations in the frozen contract, ship with the actual
  manifest `scriptRuntime` remote, frozen adaptation,
  `status.executionVerified` true and a genuinely bound
  guest-execution-qualified review. A guide-only replacement of a mandatory
  slot is refused;
- `impeccable`, when offered, must retain its real embedded
  `references/engine-dependency.json`; the builder-validated 563-byte
  frozen descriptor bytes and the raw static-ELF `riscv64` engine bytes
  must be present in the output (omitting the descriptor cannot bypass H6);
- a held-back (not yet admitted) mandatory ID no longer blocks unrelated
  qualified offers;
- the retired 40/all-nine batch rule survives ONLY as informational
  complete-selection coverage metadata in the gate summary
  (`completeSelectionCoverage` with `informationalOnly: true`), computed
  honestly from what is actually offered, so a partial feed can never claim
  all-nine or 40 completeness. The 40 target counts the QUALIFIED REGISTRY
  SELECTION (including the four App-provided builtins, reported separately
  as `builtinProvided`); the actual download offers are the qualified
  non-builtin rows (`iosQualified`/`androidQualified`, with
  `downloadEligible = selectionQualified - builtinProvided`). There is no
  option, flag or environment value that disables any part of this gate.

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
encoding and envelope shape. The bridge has now run for real in reviews mode:
the first production signing run (workflow run 40316068787) signed exactly the
43 canonical review records staged at source revision
`0d590bc3d4e17f7559aef2dcdb508d92417488b5` under the official trust key
`official-2026-09` with tooling pinned at
`647d8a7e59c8020d297a01a8c42382bcde46fb2c`; the signed pair
`signing-receipt.json(+.sig)` is retained unmodified under
`docs/provenance/review-signing-run-40316068787/` and every record and
signature in this repository re-verifies against `public-key.json`. With
those signatures verified, the registry admits 34 qualified entries — the 28
optional guide-only rows holding static-content-reviewed approvals plus the 2
rows (citation-management, sympy) holding genuine guest receipts and the 4
App-provided builtin rows, of which only the 30 optional rows are ever Hub
download offers; the other 9 scripted rows, including all nine mandatory deep
adaptations, stay unqualified and unproven. Under the old batch rule that
state was honestly refused; on 2026-10-27 Root adopted the incremental
publication policy above, so today's admitted state is publishable as-is:
the gate accepts the EXACT 30-iOS / 30-Android qualified download feeds with
all nine mandatory IDs and the four App-provided builtins held out of the
download offers (the builtins stay qualified registry data, never download
offers), and the complete-selection coverage metadata faithfully reports
selection 34/40 with `builtinProvided` 4, `downloadEligible` 30 and 0/9
mandatory offered — never complete. No production channel feed has been
signed or published yet: publication stays a coordinator-dispatched act
through this bridge with the real key, and every per-item trust requirement
(signatures, guest-execution evidence, exact advertised download-eligible
sets, H6 whenever impeccable is offered, both-channel presence for offered
mandatory IDs, empty-feed refusal) remains enforced unchanged.
