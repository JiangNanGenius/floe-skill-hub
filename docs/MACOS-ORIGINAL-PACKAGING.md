# macOS original Skill packaging and producer

Status: **author tooling only; no feed, signature, package or publication is
created by this document or by `scripts/macos_original.py`.** The channel
contract and its limits remain [MACOS-ORIGINAL-CONTRACT.md](MACOS-ORIGINAL-CONTRACT.md);
this page documents the bounded producer/validator that prepares a real
upstream candidate and the exact finalization step the release owner performs
once the capable App version is verified.

## What the tool is for

A macOS original is the upstream Skill's own files at one immutable 40-hex
commit, installed byte-for-byte with their Git modes. It is not the curated
iOS/Android adaptation, not a Linux package and not a synthetic archive. The
producer therefore fetches only the declared upstream commit and stages only
the declared subtree plus the declared license copy; it never reads Hub
`sources/`, `packages/` or review bytes.

The shared author interface is:

```python
from macos_original import canonical_manifest_digest, validate_catalog

digest = canonical_manifest_digest(entry["files"])       # four-field recipe
count = validate_catalog(document, source_root=None, previous_catalogs=())
```

* `canonical_manifest_digest(files) -> str` hashes the path-sorted list of
  `path`, `sourcePath`, `sha256` and `mode` with sorted keys, compact
  separators, unescaped Unicode and no trailing newline. `bytes` and every
  other key are excluded from the payload; extra keys are ignored so a full
  `entry["files"]` list can be passed directly.
* `validate_catalog(document, source_root=None, previous_catalogs=()) -> int`
  performs the structural, digest, staged-byte and history checks described
  below and returns the entry count. It never mutates the document or the
  previous catalogs.
* `source_root` is `Path | None`. When set, the package must be staged at
  `<source_root>/<id>/<path>`.
* `previous_catalogs` is a sequence of parsed, complete earlier feeds. A same
  `(id, version)` entry must keep its exact upstream `commit`, `repository`,
  `subdirectory` and every file's `path`, `sourcePath`, `sha256`, `bytes` and
  `mode`. A new version is permitted. The sequence must not be a single dict,
  string or `None`.

The module is stdlib-only, importable without side effects, and never signs,
installs, executes or qualifies anything.

## Prepare: real source, no capability floor

`prepare` consumes a small author spec and writes a **proposal**, not a feed:

```sh
python3 scripts/macos_original.py prepare \
  --spec <skill-spec.json> \
  --output-root <candidate-root>
```

Spec fields (exactly these; `expectAncestor` is optional):

```json
{
  "id": "example-skill",
  "name": {"en": "Example Skill", "zh-Hans": "示例技能"},
  "description": {"en": "Concise English description.", "zh-Hans": "简洁的中文说明。"},
  "category": "productivity-organization",
  "version": "1.0.0",
  "repository": "owner/repo",
  "subdirectory": "skills/example-skill",
  "commit": "<40 lowercase hex>",
  "license": "MIT",
  "licensePath": "LICENSE",
  "licenseSourcePath": "LICENSE",
  "expectAncestor": "<optional 40 lowercase hex>"
}
```

`minimumAppVersion` is deliberately **not** a spec field: prepare refuses it
so a draft can never be mistaken for a publishable feed.

Prepare performs these read-only checks before writing anything:

1. `repository`, `commit`, `subdirectory`, `id`, `version`, bilingual text and
   safe paths are validated with the same rules as the feed.
2. The commit is fetched from `https://github.com/<repository>.git` with Git
   plumbing only. Hooks, local/system Git configuration, working-tree filters
   and source execution are disabled; no checkout is created. The commit must
   be reachable from a fetched upstream branch. If `expectAncestor` is given,
   `git merge-base --is-ancestor` must prove the true ancestry.
3. `git ls-tree -r` modes are preserved. Only `100644` and `100755` regular
   blobs are accepted; symlinks (`120000`) and submodules (`160000`) fail
   closed. Every path must stay under the declared subdirectory, be NFC-safe
   UTF-8 with no traversal, control characters or empty segments, and not
   collide with a sibling prefix.
4. Every blob is read at the commit, its byte count and SHA-256 are recorded,
   and the full subtree is staged under
   `<candidate-root>/<id>/<version>/source/<id>/<path>`; the executable bit is
   set only for `100755`.
5. `SKILL.md` and the declared license file are required. A license inside the
   package must be declared by its in-package path. Otherwise
   `licenseSourcePath` is a repository-relative file (normally the root
   `LICENSE`) and its exact bytes and mode are copied to `licensePath`; this is
   the single root-license-copy exception. The license identifier itself
   (`license`) is author-declared, not inferred from a README.
6. The manifest digest is computed with the frozen recipe and the staged tree
   is checked against the declaration before the proposal is written.

Output layout:

```text
<candidate-root>/<id>/<version>/
  proposal.json     # kind=macos-original-proposal, status=awaiting-minimum-app-version
  provenance.json   # commit, commit tree, subtree tree, branch refs, per-file Git blob/mode/sha256/bytes, optional ancestry
  source/<id>/...   # byte-exact staged package
```

`proposal.json` intentionally has **no** `minimumAppVersion`. It is not a
feed, it is not signable and it must not be published. The temporary Git cache
is removed after the run; only the staged package and the two JSON records
remain.

## Finalize: only after the release owner confirms the floor

Once the release owner has verified the first capable App build, the same
tool builds the complete feed and re-runs every structural, staged-byte and
history check before writing:

```sh
python3 scripts/macos_original.py finalize \
  --proposal <candidate-root>/<id>/1.0.0/proposal.json \
  --proposal <candidate-root>/<id>/1.0.1/proposal.json \
  --minimum-app-version <verified-minimum-app-version> \
  --output-dir <candidate-root>/feeds
```

* `--minimum-app-version` is required and must be a strict `major.minor.patch`
  from a verified capable App release. `0.0.0`, a candidate build number, a
  source commit or a passing validator is refused/insufficient. The tool
  cannot verify capability; the release owner supplies and owns that value.
* All proposals in one invocation must share one Skill `id`. One feed is
  written per version (ascending), and each feed is validated against the
  previously built feeds and any `--previous` feeds.
* Nothing is written until every feed passes. A single proposal may use
  `--output <path>`; multiple proposals require `--output-dir`.
* The write is atomic (same-directory temp file + `os.replace` + `fsync`).
  The feed is compact sorted JSON with no trailing newline; those exact bytes
  are what the signing lane signs.

For a single feed the publishable file is normally
`<candidate-root>/feeds/<id>-<version>.catalog.json`; the release owner renames
or places it as `macos/catalog.json` at the immutable publication commit. The
earlier version's feed is the historical reference used to prove that a later
same-`id` publication is allowed.

## Validate: read-only preflight

```sh
python3 scripts/macos_original.py validate macos/catalog.json \
  --source-root <staged-source-root> \
  --previous <previous-macos-catalog.json>
```

The CLI caps the catalog file at 4 MiB, rejects duplicate JSON keys,
non-UTF-8 and NaN/Infinity, then applies `validate_catalog`. It prints only a
count and a reminder that no execution qualification was performed.

## Deliberately stricter than the client's minimum checks

`validate_original_catalog.py` remains the exact client-compatibility
reference and the positive/negative comparison target of the tests. This
producer adds fail-closed author gates that do not reject any conforming
positive candidate:

* a feed must contain 1..256 entries (an empty feed is refused);
* the staged package's file set must equal the declared set exactly (no
  undeclared `.DS_Store`, editor backup or extra upstream file);
* `minimumAppVersion` may not be `0.0.0`;
* paths must be NFC, control-character-free and canonical;
* duplicate JSON keys are refused;
* previous feeds are themselves structurally validated before they are used as
  history.

## History semantics

The history gate answers one question: was this exact `(id, version)` already
published with different source identity? It compares the upstream `commit`,
`repository`, `subdirectory`, `licensePath`, manifest digest and the full
file identity list (path, sourcePath, sha256, bytes, mode). It does not compare display metadata, the
license identifier or `minimumAppVersion`; changing those is a curation
decision, not an automatic history pass. A changed upstream commit, file,
path, source path, mode or license path always requires a new version. A
commit-only advance with identical bytes is honest and permitted at a new
version; its digest is recomputed and may legitimately stay identical. The
gate never rewrites, re-signs or mutates earlier feeds.

The App's local immutable check covers only identities that a client has
already observed; it is not a substitute for this publisher-side history
check.

## Licensing boundary

The declared license file must exist in the declared repository at the
declared commit. A README sentence, a package manifest field, a GitHub
metadata value or a Hub review note is not a substitute for the license file,
and this tool never copies, adapts, invents or relabels a license to make a
source pass. If the upstream commit has no license file, the producer refuses
the candidate. A source that is structurally blocked this way stays blocked
until a maintainer obtains permission or chooses a different licensed source;
it must not be staged as an installable original.

The tool preserves the license bytes and mode exactly (including the root-copy
exception) and records the declared license identifier. It does not decide
whether the license is adequate for redistribution; that remains the curation
owner's review.

## Limits checked by the author gate

| item | limit |
| --- | --- |
| feed bytes | 4,194,304 |
| entries per feed | 256 (author gate: at least 1) |
| files per entry | 2,048 |
| bytes per file | 16,777,216 |
| total declared bytes per entry | 16,777,216 |
| path / sourcePath / subdirectory / licensePath | 1..1,024 UTF-8 bytes |
| `name.en` / `name.zh-Hans` | 128 characters |
| `license` | 256 characters |

Field sets, categories, IDs, versions, repository shape, commit/digest hex and
Git modes are validated exactly as in
[MACOS-ORIGINAL-CONTRACT.md](MACOS-ORIGINAL-CONTRACT.md).

## Verification and non-claims

Focused tests:

```sh
python3 tests/test_macos_original.py
```

The suite covers the digest recipe, field/limit/path refusals, staged bytes
and modes, symlink/extra-file refusal, history immutability, commit-only
advances, the producer's no-execution and ancestry behavior, finalize's
required floor, and a positive plus targeted negatives against the exact
committed App validator. When the pinned App validator is not present the
comparison is skipped with an explicit reason; callers may set
`FLOE_MAIN_VALIDATOR` to the exact file (sha256
`72a1c570f4a5438a78aadc53dafd9e7559449b228470ff2249f951bf90f5b60b`).

Passing these checks proves only the declaration, staged bytes and history
relationship described above. It does not prove upstream availability beyond
the fetch, license adequacy, a valid signature, installation, dependency
preparation, execution or App/Mac acceptance. Signing, publication, transport
deployment and the verified capability floor remain with the release owner;
no production `macos/` feed is created by this tooling.
