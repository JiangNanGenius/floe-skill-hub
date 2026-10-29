# macOS original candidate signing

Status: **candidate-only signing tooling. It publishes nothing and proves no
macOS execution or App acceptance.** The macOS original channel remains author
input until a real upstream Mac candidate is produced, the release owner
confirms the exact minimum App version, and a signed candidate is accepted on
a real paired Mac. No production `macos/catalog.json` exists today.

This document describes `scripts/sign_macos_original.py` and the App-side
template `automation/workflows/floe-skill-hub-macos-original-signing.yml`. The
package and feed contract is [MACOS-ORIGINAL-CONTRACT.md](MACOS-ORIGINAL-CONTRACT.md).
The existing curated/Linux/Android signing bridge is unchanged:
[SIGNING_BRIDGE.md](SIGNING_BRIDGE.md).

## Trust model: T, S, B

| symbol | meaning |
| --- | --- |
| **T** | One pinned, reviewed tooling checkout of the official Hub. Every imported module resolves inside `T/scripts`: `sign_publication` (snapshot and key loading), `hubcore` (Ed25519 envelope), `build_catalog` (public trust) and the frozen macOS original producer `macos_original`. |
| **S** | A separate clean, exact snapshot of `JiangNanGenius/floe-skill-hub` at the claimed 40-hex **candidate** commit carrying `macos/catalog.json`. |
| **B** | A separate clean, exact snapshot of the **current official default branch** (`refs/heads/main`) with **full history**. |

`S` and `B` are verified with the reviewed
`sign_publication.verify_exact_snapshot`: origin must be the official Hub,
HEAD must equal the claimed commit, every tracked file is hashed against its
HEAD blob, and ignored/untracked shadows, `assume-unchanged`/`skip-worktree`
tricks, symlinks, gitlinks and replacement refs are refused. The index is
never written. Candidate code is never imported, executed, installed or
hooked: only T code runs, and only exact bytes from S are signed.

A candidate branch is **not** publication history. Only committed
`macos/catalog.json` + `macos/catalog.json.sig` pairs on **B's** official
default-branch history define previously published macOS versions.

## Why signing is separate from upstream verification

The workflow has two jobs:

1. `verify` (no secret, read-only): resolves T/S/B, fetches every declared
   upstream repository at its exact 40-hex commit with argv-only Git, checks
   the real blob SHA-256/byte count/Git mode, stages the exact package bytes,
   and writes a public-safe `verification.json` receipt. It uploads **only**
   that tiny receipt — never staged bytes or upstream source.
2. `sign` (the only step with `FLOE_SKILL_HUB_SIGNING_KEY`): downloads the
   tiny receipt outside T/S/B, requires its SHA-256 to equal the verify job's
   output, and rederives every binding from actual T/S/B/S: snapshot
   commits/trees, baseline feed presence, exact floor, exact feed hash/size/
   entry count, and every per-entry repository/commit/file count/total
   bytes/manifest hash. It also requires the receipt's explicit
   `upstreamVerification.verified == true` and matching target count/observed
   hash. A missing, tampered, stale or mismatched proof is refused **before**
   the key is read. Only then does it repeat the producer/floor/full-history
   validation, re-resolve official main once more, and sign the exact
   `macos/catalog.json` bytes from S.

The job-output digest is the workflow boundary. The signing receipt binds the
verification receipt's exact SHA-256; it never treats the receipt's assertions
as authority for the bytes. The sign job re-reads and re-validates S itself.

## Producer interface and integration status

The signer imports the producer **only from verified T**:

```python
canonical_manifest_digest(files) -> str
validate_catalog(document, source_root=None, previous_catalogs=()) -> int
```

`source_root` staging is `<root>/<id>/<path>` and `previous_catalogs` is the
oldest-first sequence of parsed signed feed documents. The producer is the
authority for the frozen schema, exact field sets, safe paths, required
`SKILL.md`/license, canonical four-field manifest digest, size caps, and
historical `(id, version)` identity.

The producer implementation is present in this checkout and the deterministic
tests exercise both it and a fixture producer with the same interface. It is
not yet part of a reviewed/committed tooling pin, so a real dispatch remains
pending Root's commit and `TOOLING_COMMIT` render. If a pinned T does not
contain `scripts/macos_original.py`, the signer fails closed with an explicit
"producer integration is still pending" message instead of inventing it.
Producer success is still not macOS execution or App acceptance.

## Exact minimum App floor

`minimum_app_version` is a dispatch input and must be the release owner's
confirmed capable App version. The signer:

- refuses a missing, non-semantic or `0.0.0` floor;
- requires **every** entry's `minimumAppVersion` to equal that exact floor;
- never infers capability from the candidate build, source commit, schema,
  signed feed, decode success or a green test.

Main has confirmed `1.7.62` as the floor for the current candidate-only
signing round (build 303 is a separate identity). That confirmation does not
authorize a live Mac feed: Main install/update/version-pin qualification is
still required. The workflow continues to require the exact confirmed value as
a dispatch input and never infers it from a candidate build.

## Publication history and immutability

For every commit on B's full official default-branch **first-parent
publication spine** that adds or changes either `macos/catalog.json` or
`macos/catalog.json.sig`, the signer reads both objects **at that commit**,
verifies the Ed25519 envelope under T's configured production trust, and
validates the feed through T's producer. Unique signed feed bytes are kept
oldest-first, so a version later removed from the current feed still
participates in the identity check. Candidate-branch intermediate commits are
not publication history just because a later merge includes the branch.

Actual publication must atomically copy the signed `macos/catalog.json` +
`macos/catalog.json.sig` pair onto official main in a first-parent commit. Do
not merge an unsigned intermediate candidate history: a first-parent merge
that brings an unsigned or wrong-key pair is a publication boundary and is
refused.

For every historical `(id, version)` and every candidate `(id, version)`, the
following are immutable: `repository`, `subdirectory`, `commit`,
`licensePath`, `digest`, and every file's `path`, `sourcePath`, `sha256`,
`bytes` and `mode`. A commit-only advance requires a new version even when the
four-field manifest digest is unchanged. An identical re-publication of the
same `(id, version)` is allowed.

Fail-closed history rules:

- a shallow B checkout is refused (history cannot be established);
- an unsigned, unreadable or unverifiable feed pair at any history commit is
  refused, not skipped;
- a previously published feed removed from official main HEAD is refused
  rather than downgraded to first publication;
- when the channel has never been published, empty history is legitimate —
  and is the only current state.

An older B, a candidate branch's own history, or a caller-supplied baseline
cannot remove or rewrite official history. The workflow always fetches B from
the live `refs/heads/main` and re-checks it immediately before signing.

## Commands

All modes are fixed argv; there is no arbitrary command input. `plan`,
`fetch` and `verify` refuse to run when the signing key is present.

```sh
python3 -I tooling/scripts/sign_macos_original.py plan \
  --tooling tooling --data data --source-commit <S> --out plan-out

python3 -I tooling/scripts/sign_macos_original.py fetch \
  --plan plan-out/plan.json --stage upstream-stage \
  --observed upstream-observed.json

python3 -I tooling/scripts/sign_macos_original.py verify \
  --tooling tooling --data data --source-commit <S> \
  --baseline baseline --baseline-commit <B> \
  --minimum-app-version <confirmed-floor> \
  --stage upstream-stage --observed upstream-observed.json \
  --out verify-out

FLOE_SKILL_HUB_SIGNING_KEY=... \
python3 -I tooling/scripts/sign_macos_original.py sign \
  --tooling tooling --data data --source-commit <S> \
  --baseline baseline --baseline-commit <B> \
  --minimum-app-version <confirmed-floor> \
  --verification-receipt <downloaded verification.json> \
  --verification-sha256 <verify-out verification.json SHA-256> \
  --out signing-out
```

`--baseline` must be a full-history clone of the official default branch at
`--baseline-commit`. `--out`, staging and observed paths must be fresh and
outside T/S/B; existing foreign files, symlinks and overwrites are refused.

## Output artifact

`sign` writes exactly:

- `macos/catalog.json` — the exact candidate feed bytes from S;
- `macos/catalog.json.sig` — canonical Ed25519 envelope under the existing
  `official-2026-09` identity;
- `macos/signing-receipt.json` + `.sig` — canonical authenticated receipt
  binding T commit/tree, S commit/tree, B commit/tree, the exact floor, the
  feed SHA-256/size/entry count, the number of signed historical feeds, every
  output SHA-256/size, the producer-history baseline, and the exact
  verification receipt SHA-256 plus verified upstream entry count and observed
  manifest hash.

The receipt explicitly records `candidateOnly: true` and
`published/installable/macExecutionVerified/linuxQualified/archiveProduced:
false`. It contains no local paths, no secret and no new trust root.

## Root deployment and dispatch recipe

This template is **not** installed on App main. Root:

1. renders `TOOLING_COMMIT` to the exact reviewed 40-hex Hub tooling commit
   containing this signer and the real `scripts/macos_original.py` producer;
2. commits the rendered file to a **dedicated immutable App transport
   commit/tag** at the existing registered path
   `.github/workflows/floe-skill-hub-signing.yml`;
3. dispatches that tag (not App main) with the exact Main-confirmed floor
   (`1.7.62` for the current candidate round):

```sh
gh workflow run .github/workflows/floe-skill-hub-signing.yml \
  --ref <dedicated-transport-tag> \
  -f data_commit=<40-hex Hub candidate commit> \
  -f minimum_app_version=<confirmed-floor>
```

The workflow uploads the tiny verify receipt (`floe-skill-hub-macos-original-verification`)
and downloads it only in the sign job, outside T/S/B. The sign job refuses a
missing/wrong-hash/mismatched proof before reading the key. The workflow uses
the existing `FLOE_SKILL_HUB_SIGNING_KEY` secret and the
`floe-skill-hub-signing` concurrency group. It has `contents: read`, writes no
repository, publishes no tag/release/feed and does not install anything. The
run artifact `floe-skill-hub-macos-original-candidate` is candidate evidence
for Root, not a released download.

## Tests

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_sign_macos_original -v
```

The deterministic suite uses only throw-away Git repositories and a public
ephemeral Ed25519 fixture identity. It covers exact-byte signing and receipt
verification, wrong key, exact floor, same-version history drift (including a
version removed from the current feed), commit-only advance with a new
version, candidate-branch history exclusion, first-parent publication spine
and merged-branch exclusion, shallow/unsigned/removed history,
untracked/assume-unchanged/symlink snapshots, candidate shadow module
execution, upstream fetch/stage byte/mode/path checks, observed/stage tamper,
missing/wrong-hash/wrong-identity/wrong-floor/unverified proof refusal before
key access, output overwrite/symlink/inside-snapshot refusal, read-only-mode
key refusal and key absence from output. When `scripts/macos_original.py` is
present, an additional test runs the real producer through the same interface.

## Provenance and limitations

The authoritative App schema/validator remain frozen at
`55457ad5ff186a3c2f46c4a7318a8ebfb9ed945e` (byte-identical at current Main)
as recorded in [MACOS-ORIGINAL-CONTRACT.md](MACOS-ORIGINAL-CONTRACT.md).
This tool adds no schema copy, package, archive, review, qualification or
production feed.

Known limitations at authoring time:

- the real `scripts/macos_original.py` producer is present but not yet in a
  reviewed/committed tooling pin; Root must commit it and render
  `TOOLING_COMMIT` before a real dispatch;
- no key has been used and no feed or signature has been produced;
- local tests do not contact GitHub; the upstream-fetch function is exercised
  against local Git repositories, while the workflow consumes real public
  GitHub repositories;
- no macOS execution, App acceptance, installation, Linux qualification or
  archive is claimed.
