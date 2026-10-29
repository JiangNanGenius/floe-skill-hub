# macOS original Skill contract — author input

Status: **frozen author contract; the macOS original channel is not yet published.** This document defines the
package and feed contract for the reserved macOS original route used by the same-Mac
bridge. It creates no feed, signature, package, source tree, key, workflow or install
offer. No production `macos/catalog.json`, `macos/catalog.json.sig`, archive or
receipt exists today. Publication, client acceptance and App distribution remain with
the release owner. A separate implementation stage must produce a real upstream Mac
candidate and a signed candidate before App release; this author-input document
neither performs nor substitutes for that stage.

The authoritative App source for this alignment is floe-agent commit
`55457ad5ff186a3c2f46c4a7318a8ebfb9ed945e`:
`docs/FLOE_SKILL_DEPENDENCIES.md` (macOS section),
`FloeMacBridge/schema/macos-original-catalog.schema.json` and
`FloeMacBridge/scripts/validate_original_catalog.py`. That commit is not yet
published on GitHub, so these are immutable SHA + repository-relative references,
not live links. The bilingual Linux author guides linked below are public at frozen
commit `e3fc4b8ef3450c47b16338f7aa660d48886db4a5` and byte-identical at
`55457ad5ff186a3c2f46c4a7318a8ebfb9ed945e`.

Linux dependency declarations remain a separate channel; their schema and
qualification are unchanged: [DEPENDENCY-V1-CONTRACT.md](DEPENDENCY-V1-CONTRACT.md).
The bilingual Main author guides are
[English](https://github.com/JiangNanGenius/floe-agent/blob/e3fc4b8ef3450c47b16338f7aa660d48886db4a5/docs/skills/SKILL_DEPENDENCIES_AUTHOR_GUIDE.md)
and
[简体中文](https://github.com/JiangNanGenius/floe-agent/blob/e3fc4b8ef3450c47b16338f7aa660d48886db4a5/docs/skills/SKILL_DEPENDENCIES_AUTHOR_GUIDE.zh-CN.md).

## Channel shape

The eventual feed is exactly `macos/catalog.json` plus
`macos/catalog.json.sig` at an immutable publication commit. It is separate from the
curated `catalog.json` and `android/catalog.json` feeds; it does not change their
schema, offers or review records.

* `schemaVersion` is the JSON integer `1` (`1.0` and `1e0` are not the author form).
* `channel` is exactly `"macos-original"`.
* The existing production signing identity signs the **exact feed bytes** with the
  same Ed25519 trust key as the curated feeds (`official-2026-09`, published in
  [`public-key.json`](../public-key.json)). No new client trust key is introduced.
  `macos/catalog.json.sig` is the usual envelope
  `{"keyID": "<production-key-id>", "signature": "<base64 Ed25519 over the exact feed bytes>"}`;
  re-serializing the feed changes its bytes and requires a new signature.
* A client resolves a publication commit, fetches both files at that commit, verifies
  the signature before decoding, and records the feed digest and publication commit.
  A missing or invalid feed remains visibly unavailable; it never falls back to an
  adapted iOS/Android package or to Linux qualification.

Raw catalog bytes are capped at **4 MiB** (4,194,304 bytes). The feed contains at
most **256 entries** with unique `id`s.

No production file is created by this document. The default branch has no released
`macos/` feed or install offer. The [candidate producer](MACOS-ORIGINAL-PACKAGING.md)
and [data-only signer](MACOS-ORIGINAL-SIGNING.md) implement this contract without
publishing candidates or adding a trust key.

## Entry fields (exact set)

Top-level keys are exactly `schemaVersion`, `channel` and `entries`; an entry has
exactly these thirteen keys. Unknown or missing fields fail closed in both the JSON
schema and the author validator.

| field | requirement |
| --- | --- |
| `id` | lowercase slug matching `[a-z][a-z0-9-]{0,63}`; unique in the feed. The App client additionally refuses a trailing `-` and `--`, so authors must avoid both. |
| `name` | object with exactly `en` and `zh-Hans`; both strings non-empty after trimming whitespace. The client also caps each name at 128 characters. |
| `description` | object with exactly `en` and `zh-Hans`; both strings non-empty after trimming whitespace. No schema maximum; keep entries concise. |
| `category` | one of the existing seven: `office-documents`, `writing-communication`, `web-development`, `research-data`, `design-creation`, `product-requirements`, `productivity-organization`. |
| `version` | strict `major.minor.patch`, digits only, no leading zero in a component (`0` is valid; `01` is not), no pre-release or build suffix. |
| `minimumAppVersion` | same strict semantic form; filled only from the release owner's verified capable App build. See [Version and capability](#version-and-capability). |
| `repository` | upstream GitHub repository as `owner/repo`, exactly two components. The validator accepts `[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}` per component; use real GitHub names. |
| `subdirectory` | empty string for the repository root, otherwise a repository-relative POSIX path, at most 1024 UTF-8 bytes, with no leading `/`, no `\`, no NUL and no empty, `.` or `..` segment. |
| `commit` | exactly 40 lowercase hexadecimal characters: the immutable upstream commit. Never a tag, branch or abbreviated SHA. |
| `license` | non-empty license identifier or short expression. The client caps it at 256 characters; the path is declared separately in `licensePath`. |
| `licensePath` | package-relative path to the license file, using the same safe-relative rule and at most 1024 bytes; must also appear in `files`. |
| `digest` | 64 lowercase hexadecimal characters: the canonical manifest digest defined below. |
| `files` | array of 1–2048 file objects; at least `SKILL.md` and the declared `licensePath` must be present. |

`version` must be a new Skill package version whenever the upstream `commit`, a
file byte, the file set, a `sourcePath`, a mode or the license path changes. A
published `(id, version)` is immutable across all of those facts, even when an
upstream project reuses a tag. A commit-only advance still requires a new version;
recompute the digest with the frozen recipe, but do not fabricate a different digest
when the four-field file manifest is unchanged. `id` is the Skill identity and never
changes for an existing entry.

## File fields (exact set)

Each `files` object has exactly `path`, `sourcePath`, `sha256`, `bytes` and `mode`.
Unknown or missing keys are rejected.

| field | requirement |
| --- | --- |
| `path` | package-relative install path, unique within the entry, at most 1024 UTF-8 bytes, no leading `/`, no `\`, no NUL and no empty, `.` or `..` segment. It identifies the file inside the installed package. |
| `sourcePath` | repository-relative path at `commit`, subject to the same safe-relative rules. It must equal `<subdirectory>/<path>` (or `<path>` when `subdirectory` is empty), except for the declared license file described below. |
| `sha256` | 64 lowercase hexadecimal characters: SHA-256 of the exact upstream file bytes. |
| `bytes` | JSON integer, at least 0 and at most 16,777,216: the exact upstream byte count. |
| `mode` | exactly `"100644"` or `"100755"`; the declared Git mode is preserved on installation. |

The total declared `bytes` is at most **16,777,216** (16 MiB). Files are fetched at
the declared commit and installed byte-for-byte with the declared mode. Do not
declare symlinks, path traversal, absolute paths or unlisted files: the manifest has
no command, URL, install or permission field and cannot mint a command or widen an
approval. Upstream `SKILL.md` and other package content may legitimately contain
instructions or URLs; they are retained byte-for-byte, and any action they request
remains subject to the task's normal permissions.

### Root-license-copy exception

Every file except the declared license must resolve to
`<subdirectory>/<path>` in the upstream repository. The file whose `path` equals
`licensePath` may instead declare another repository-relative `sourcePath`, normally
the repository-root `LICENSE`. Its bytes are still copied to `licensePath` without
rewriting, line-ending conversion or mode changes, and it remains in the manifest,
size total and digest. This exception applies only to that one declared license file.

## Canonical manifest digest

`digest` covers the package manifest, not the whole feed. Build a list with exactly
these four keys per file — **`bytes` is deliberately excluded**:

```json
{"mode": "100644", "path": "<package path>", "sha256": "<64 hex>", "sourcePath": "<upstream path>"}
```

Then:

1. sort the list by `path` (keep package paths ASCII; the Python validator and the
   Swift client then sort them identically);
2. serialize it as UTF-8 JSON with object keys sorted, compact separators
   (`,` and `:` with no spaces), unescaped Unicode (`ensure_ascii=False`) and
   unescaped slashes;
3. SHA-256 the exact serialized bytes and encode the result as lowercase hex.

Equivalent recipe (the author validator and the native client agree on this shape):

```python
import hashlib, json

manifest = [
    {"path": f["path"], "sourcePath": f["sourcePath"],
     "sha256": f["sha256"], "mode": f["mode"]}
    for f in files
]
payload = json.dumps(
    sorted(manifest, key=lambda row: row["path"]),
    ensure_ascii=False, sort_keys=True, separators=(",", ":"),
).encode("utf-8")
digest = hashlib.sha256(payload).hexdigest()
```

No trailing newline is added. `bytes` still participates in the declaration and is
checked against the staged/upstream file, but changing only the declared `bytes`
value does not change this digest; it must still be correct. Because the digest is
over the file identity list, any path, source path, SHA-256 or mode change alters the
manifest digest and requires a new `(id, version)`. A commit-only advance requires a
new version too, but its digest can legitimately stay identical; publish the
recomputed value, never a fabricated one.

## Installation, receipts and version retention

The same-Mac companion installs each version into an immutable version directory and
atomically updates its active index. A running or checkpointed task pins the exact
original version by owner and keeps it across restarts; an update never repoints an
already-pinned task. Removing an installed Skill removes its active index entry;
versions still referenced by a task remain until they are safely unpinned.

A Mac original installation is separate from any iOS/Android adaptation, even when
both use the same upstream Skill `id` and version. They retain separate files,
installation receipts, dependency ownership, enable state and execution records. A
Mac original receipt records the target `macos-original`, Skill `id` and `version`,
the file-manifest digest, the signed catalog digest, the publication commit, the
upstream repository and 40-hex source commit, file count, total bytes and the
installed path. It intentionally omits Linux archive, review and guest-qualification
claims.

## Dependencies and runtime boundary

An original package ships no dependency bundle. Its `references/dependencies.json`
is **not** converted into a macOS install plan: a Linux/Debian/riscv64 pin or
provisioning plan must not be replayed as a Mac installation command. The original
route has no per-entry RISC-V/Linux review receipt, no guest execution qualification,
no synthetic archive and no fallback to an adapted package.

Dependencies are prepared by the model with the ordinary shell and the real Mac
task environment's normal permissions, exactly as the task runs. Mac-native
`pip`/`npm`/Homebrew-style work is allowed in that environment; it must not be
replaced by replaying a Linux dependency plan. Do not remove external system or
Homebrew packages during cleanup. The Linux dependency schema and its version
semantics remain unchanged for the Linux channel. Pinned versions stay with the
running or checkpointed task.

## Version and capability

`minimumAppVersion` is an old-client gate enforced by the App: an entry is offered
only to an App version at or above the declared floor. It must be the **first capable
App release identity verified by the release owner**.

The following are not proof of a capable App build: a candidate build number, the
source commit, a passing author validator, the schema, a signed feed, a successful
feed decode, or a green test run. This document deliberately prescribes no floor.
Do not publish an all-zero placeholder as a substitute and do not hardcode a
candidate version as usable. While drafting, leave the value unresolved and do not
sign or publish the feed; fill it from the release owner's verified capable build,
then re-run preflight.
A syntactically valid but unverified number is still an unverified capability claim.

## Validation, signing and acceptance are distinct

| layer | proves | does not prove |
| --- | --- | --- |
| Declaration validation (`validate_original_catalog.py` without `--source-root`) | exact top-level/entry/file field sets, safe relative paths, unique ids, categories, strict versions, size bounds, required `SKILL.md` and license, canonical manifest digest | actual file bytes, upstream availability, signature validity, installation or runtime |
| Staged-source validation (`--source-root`) | the staged tree under `<source-root>/<id>/<path>` has the declared byte count, SHA-256 and executable/non-executable mode; the package stays inside that directory | that the staged bytes came from the declared commit (local staging is not provenance), signature validity, installation or runtime |
| Publisher-side upstream fetch at `commit` | every file fetched at the declared 40-hex commit has the declared byte count and SHA-256; declared modes and the root-license copy can be checked against the same commit | execution, dependency preparation or App acceptance |
| Feed signature verification | the exact feed bytes were signed with the existing production key and decoded under the trusted key map | content correctness, historical publication, runtime behavior |
| Historical immutability check | the same `(id, version)` was previously published with the same commit, file set, paths, SHA-256 values and modes | future behavior, or client history the client never observed |
| macOS runtime and App acceptance | a real paired Mac bridge and App install, read and run the original, with any model-led dependency preparation, under the actual task environment | Linux/RISC-V qualification or any other OS |

The author validator is read-only and does not execute, install or qualify a Skill.
The App client's download check verifies each file's byte count and SHA-256 at the
declared commit; it likewise does not prove that instructions are correct, that
dependencies can be prepared, or that the Skill runs on a particular Mac.

## Author preflight and publication checklist

1. **Freeze the source identity.** Choose the upstream `repository`,
   `subdirectory` and full 40-hex `commit`; confirm `SKILL.md` and the declared
   license exist at that commit. Do not use a tag or branch.
2. **Choose the identity and version.** Keep the `id` stable. If the same
   `(id, version)` was already published, verify that commit, file set,
   `sourcePath` values, SHA-256 values and modes are unchanged; otherwise choose a
   new semantic `version`. A changed commit alone is enough to require a new version
   even when the recomputed digest is unchanged.
3. **Stage the exact package.** Fetch every file at the commit (not from a mutable
   branch), record exact bytes, SHA-256 and Git mode, preserve `100644`/`100755`,
   include `SKILL.md` and the license, and keep the total at or below 16 MiB. Use the
   root-license-copy exception only for the one declared license file.
4. **Build the manifest digest.** Use the exact path-sorted four-field JSON recipe
   above; never include `bytes` in the digest payload. Put the lowercase hex result
   in `digest`.
5. **Fill metadata.** Provide both `en` and `zh-Hans` names and descriptions, one of
   the seven categories, and the license identity/path. Do not add fields outside
   the exact sets.
6. **Resolve the capability floor.** Set `minimumAppVersion` from the release
   owner's verified capable App build. Do not sign or publish while it is a draft,
   an all-zero placeholder, or an unverified candidate.
7. **Run the author validator against staged bytes.** The validator lives in the
   floe-agent checkout at commit `55457ad5...`; it is not copied into this Hub:

   ```sh
   python3 <floe-agent-checkout>/FloeMacBridge/scripts/validate_original_catalog.py \
     macos/catalog.json --source-root <staged-source-root>
   ```

   `<staged-source-root>/<id>/` must contain the package at the declared paths. A
   success message means only that the declaration and staged bytes pass these
   author checks; it is not upstream, signing, installation or runtime evidence.
8. **Verify upstream and sign.** Independently fetch every file at the declared
   commit and compare size and SHA-256. Then the release owner signs the exact feed
   bytes with the existing production key and publishes `macos/catalog.json` plus
   `macos/catalog.json.sig` at the immutable publication commit. Do not create a
   feed, key or signature from an author lane.
9. **Accept the Mac bridge and App delivery.** Before the first channel release,
   the release owner validates the capable paired bridge/App with representative
   real originals, including installation, reading, update and task version retention.
   This is client integration acceptance, not a new execution-qualification gate
   for every original Skill. An original may be offered after source, signature,
   integrity, safe-path and capability checks without a per-Skill compatibility run.
   Record any actual dependency preparation or execution separately; do not invent
   Linux qualification, archives, review receipts or runtime readiness.
10. **Re-check history before the next publication.** Compare the previous signed
    Mac feed/history and refuse any same `(id, version)` with a different commit,
    manifest or modes. The App's local immutable check covers only identities that
    client has observed; it is not a substitute for the publisher's historical
    check.

Before the release owner confirms the client identity and publishes the signed
feed, this channel has no released Mac original download or install offer.
Per-Skill execution is not a publication prerequisite for originals; runtime
readiness is established in the real task environment when a Skill is used.

## Provenance

All App references below are at floe-agent commit
`55457ad5ff186a3c2f46c4a7318a8ebfb9ed945e`; the commit is not yet publicly
available, so these are source references, not live URLs.

| repository-relative path | SHA-256 |
| --- | --- |
| `docs/FLOE_SKILL_DEPENDENCIES.md` (macOS original section) | `a17ee2b0e51b68fa9244d43d9d2feed7696e6f5344233f594271954ca9f2ce6a` |
| `FloeMacBridge/schema/macos-original-catalog.schema.json` | `0c57e461c44441322b4cb124987e4c9211533ec2767eb5779482f85829e358d8` |
| `FloeMacBridge/scripts/validate_original_catalog.py` | `72a1c570f4a5438a78aadc53dafd9e7559449b228470ff2249f951bf90f5b60b` |
| `FloeAgent/Sources/FloeSkills/MacOriginalSkillCatalog.swift` (client validation) | `b3dea35f6587123f66900b842caa70e21d272e5958886508db195099db1cdfef` |
| `FloeAgent/Sources/FloeSkills/MacOriginalSkillInstall.swift` (receipt) | `707208cf43ddcdf5fbbdb0ecac7f410ded6bf6639d54530e5c1abfd84a4e1f82` |
| `docs/skills/SKILL_DEPENDENCIES_AUTHOR_GUIDE.md` | `e454e935d253d6dac181111598cea8d2ade1a25ba6b763015068c6927ff7e556` |
| `docs/skills/SKILL_DEPENDENCIES_AUTHOR_GUIDE.zh-CN.md` | `d83e16cdd62bab8a636fb6318ded21cdb00b6735d5aa1304227378f0d3125670` |
| `docs/skills/dependencies.schema.json` | `39b9204c400383637b474029e75cba20fffed1e64b7824e87deee58f9c71cf73` |

The two bilingual guides are linked above at the public frozen commit
`e3fc4b8ef3450c47b16338f7aa660d48886db4a5`; their bytes at that commit and at
`55457ad5...` are identical (hashes above). The feed envelope and signing model are
also described in [SIGNING_BRIDGE.md](SIGNING_BRIDGE.md) and
[CATALOG-CONTRACT.md](CATALOG-CONTRACT.md); the existing trust root is
[`public-key.json`](../public-key.json). The contract introduces no new trust key or Linux
qualification requirement; candidate tooling and its evidence remain separate from
production feed publication.
