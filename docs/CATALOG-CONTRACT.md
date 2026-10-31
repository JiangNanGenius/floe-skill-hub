# Floe Skill Hub catalog contract (H1)

Complete-view amendment (2026-10-31): [CATALOG-EXPANSION.md](CATALOG-EXPANSION.md) defines the four fixed complete/legacy pairs, append-only planning slots up to256, source O, and normalized immutable history. This extends the first-wave paths/counts below without changing schema3 fields, categories, permission policy or per-item qualification. Clients must activate the complete paths only after their signed bytes are published.


Status: fixed wire contract for native/website consumption. SchemaVersion 3 of
the signed channel feed is defined here; the legacy four-item feed stays
unchanged (see [LEGACY-COMPATIBILITY.md](LEGACY-COMPATIBILITY.md)). Nothing in
this repository is published or trusted until the coordinator signs and the
client verifies real bytes. Source code references: `scripts/hubcore.py` is
authoritative behaviour; `schema/*.json` are the generated contract documents.
2026-10-26 field correction (coordinator decision, see
`docs/INTEGRATION-CONTRACT.md` "Separate audited source provenance…"): the
feed field from the earlier commit-implying sketch is serialized as
**`sourceCommit`** (audited source X) per §1.1; the retrieval pin
`publicationCommit` Y is external and never appears in the feed. No content
has been published, so schemaVersion stays 3 and only fixtures/schemas/docs
were regenerated.

## 1. Files and layout

| Path | Role |
| --- | --- |
| `catalog/skills.json` | Unsigned candidate registry (source of truth, pretty JSON, 43 rows) |
| `catalog.json` + `catalog.sig` | iOS channel signed feed (canonical bytes) |
| `packages/{id}/{version}/{id}.zip` | Immutable iOS-channel archives (repo-root relative) |
| `android/catalog.json` + `android/catalog.sig` | Android channel signed feed |
| `android/packages/{id}/{version}/{id}.zip` | Immutable Android-channel archives |
| `reviews/{id}/{version}.review.json(+.sig)` | Publisher review records bound by digest |
| `sources/{id}/` | Staged package sources owned by content lanes (H2/H3/H4/H5, builtin migration) |
| `tests/catalog/fixtures/` | Fixture-only signed sample (never production, §7) |

### 1.1 Audited source (X) vs publication pin (Y)

Two different Git identities participate in every install; they must never be
conflated, and neither may be defined in terms of the other:

| Name | Where it lives | Meaning | Who resolves it |
| --- | --- | --- | --- |
| `sourceCommit` **X** | inside the signed feed (40-hex; `null` only in fixture feeds) | the audited source revision whose reviewed content the feed describes; signed provenance | the publication run builds from a frozen fetch of X (`--source-snapshot`) |
| `publicationCommit` **Y** | external — the resolved immutable repository ref/commit of the published checkout | the revision actually containing `catalog.json`/`.sig`, `android/…`, `packages/…`, `reviews/…`; every artifact path of one operation is fetched at Y | the client/store resolves the pinned ref once, then reads only at Y |

Rules: X is normally an ancestor of Y and **X ≠ Y is the normal shape**;
the feed never contains the hash of the commit that contains the feed (no Git
hash self-reference); the client never re-resolves a mutable branch per
artifact; nothing may demand X == Y; and a feed whose production status lacks
a 40-hex X is invalid. Search/read/install receipts keep both identities
separate (`publicationCommit` retrieves, `sourceCommit` explains).
Verification of a publication reads the published bytes at Y standalone —
the current candidate registry/HEAD is irrelevant to whether an existing
signed publication verifies, and must never be used to "rebuild" one.

Feeds, signatures, reviews and archives are committed and fetched as one
immutable Y snapshot (the existing resolve-commit-then-read flow), while the
website and app continue to reference that one immutable publication commit
and catalog digest.

## 2. Canonical bytes and envelope (unchanged)

* Canonical encoding: UTF-8 JSON with sorted keys and `,`/`:` separators, no
  trailing newline — identical to the legacy `skill-hub/build.py`.
* `catalog.sig` (and any `.sig`/`.review.json.sig`) envelope: exactly
  `{"keyID": <string>, "signature": <base64 Ed25519 over the exact payload bytes>}`.
* Production identity `keyID = "official-2026-09"` — the same trust root as
  today (the repo-root `public-key.json` carries exactly this approved PUBLIC
  key material and equals the compiled native trust). Workers never hold the
  private key; the publication run signs with the signing secret through the
  existing environment route only, and `build_catalog.py` first requires the
  public identity derived from the supplied signing key to equal the
  configured `public-key.json` trust, refusing otherwise.
* Trust is one-directional configuration, never data: verification loads
  `public-key.json` only. No key advertised inside a catalog, fixture file or
  package can ever join the trust map, and the fixture identity
  (`fixture-only-2026-10`) is rejected as trust material at load time.
* `contentDigest` = SHA-256 over, per file sorted by path,
  `u64be(len(path)) || path || u64(len(bytes)) || bytes` — byte-compatible
  with the native `SkillPackageValidator.canonicalDigest`.
* `sha256` = SHA-256 of the exact archive bytes. Archives are built
  ZIP_STORED, entries sorted, fixed 1980-01-01 timestamps, create_system=3,
  external_attr `0o100644<<16` — same construction as the legacy builder, so
  identical sources yield byte-identical archives.

## 3. Feed shape (`schema/catalog.schema.json`)

Top level (all keys required): `schemaVersion` (3), `publisher`
("JiangNanGenius"), `channel` ("ios"|"android"), `feedStatus`
("production"|"fixture"), `hubRepository`, `sourceCommit` (40-hex audited
source revision X per §1.1; required for production, null only in fixture
feeds — it is signed provenance and never the publication commit Y),
`permissionPolicy` (fixed constants below), `entries`, `counts` (recomputed
from entries; UI must show actual qualified/visible counts, never candidate
totals).

Each entry has exactly these keys:

| Key | Meaning |
| --- | --- |
| `id` | SkillIdentifier grammar (`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`, ≤64) |
| `planNumber` | Row number in the accepted 43-item plan table (1–43) |
| `kind` | `builtin` (the four reserved official ids) or `optional` |
| `source` | `F` Floe, `A` anthropics, `V` vercel-labs, `R` alirezarezvani, `K` K-Dense, `S` superpowers, `I` impeccable, `O` other pinned upstream (new complete-view rows only) |
| `name` / `description` | `{en, zh-Hans}` only, both non-empty; generic zh names are translated, brands (`Impeccable`, `Floe PDF`…) stay |
| `category` | one of seven ids: `office-documents`, `writing-communication`, `web-development`, `research-data`, `design-creation`, `product-requirements`, `productivity-organization` |
| `tags` | 2–12 unique lowercase slugs |
| `deepAdaptation` | exactly 9 entries are `true` (plan §3 list) |
| `upstream` | external pin block or null: `repository`, `commit` (40-hex review baseline per `docs/UPSTREAM-PINS.json`), `path`, `skillManifestPath`, `retrievedAt`, `licenseStatus` (`verified`/`pending-per-item-audit`/`blocked-no-upstream-license`), `licenseEvidencePath`, `repositoryLicense`, `licenseNote{en,zh-Hans}`. A pin is the review baseline, **not** a blanket license. |
| `firstParty` | builtin pin block (floe-agent commit + released vs staged versions) or null |
| `runtime` | `{scriptRuntime, capabilities, tools, installPlatforms, pythonPackagesPlan, execution}` — see §5. For `qualified` entries this block is the **actual reviewed manifest from the archive**, never the registry's planned placeholders. |
| `version` | strict `X.Y.Z` (the Floe adaptation version target / released version) |
| `minimumAppVersion` | strict `X.Y.Z` or null; required whenever `package` is non-null |
| `status` | `{sourcePinned, licenseChecked, adaptation, packaged, reviewed, qualified, published, executionVerified}` — distinct lifecycle flags (§6) |
| `notes` | `{en, zh-Hans}` (may be empty except when a license blocker exists) |
| `package` | null or `{path, size, sha256, contentDigest, containsScripts}` bound to the exact archive |
| `review` | null or `{path, sha256, keyID}` — digest of the canonical review record bytes |
| `installOffer` | `none` \| `qualified` \| `fixture-simulated` (§6) |

## 4. Permission policy (fixed constants in every feed)

```json
{"automaticInstallWhenReviewedAndGranted": true,
 "deltaOnlyApproval": true,
 "selfApprovalProhibited": true,
 "userDisabledAndRemovedPriority": "user",
 "temporaryTaskCeiling": "client-enforced"}
```

Semantics (implemented natively; this catalog only carries evidence):
a `qualified` entry whose `reviewedTools`/`reviewedCapabilities`/
`reviewedPythonPackages` are already covered by the user's effective grants
installs/enables/uses with **no repeated per-item confirmation**; only the
missing/revoked/expanded delta enters the existing combined permission flow
once; refusal is not re-prompted by tool retries; explicit disabled /
uninstalled / user-modified choices and the temporary-task ceiling stay
authoritative; imported metadata or model parameters can never self-approve.
This is a binding of the existing grant model — the Hub does not carry a
second permission database.

## 5. Platform, store and runtime separation

* Store channel (`channel` + entry `runtime.installPlatforms`, `ios`/`android`)
  ≠ execution OS/architecture (`runtime.execution.os/arch`, e.g.
  `linux`/`riscv64`) ≠ the packaged manifest's native `floe.json platforms`
  enum (`ios|macos|linux`). Nothing may be inferred across the three.
* `execution.evidence` is `unproven` until a real guest run lands;
  `guest-verified` requires `status.executionVerified` plus a
  `guest-execution-qualified` review. Unknown execution evidence is unproven
  — scripts are never claimed runnable from the platform name.
* An Android client whose guest architecture does not match a package's
  declared execution arch, or whose arch is unknown, must surface that as a
  distinct unavailable/unknown state — it never rewrites the manifest, never
  auto-widens an old signed manifest, and never markets an Android endpoint
  before a real signed publication and client verification. Guidance-only
  packages (no scripts, no execution claim) stay installable regardless of
  execution architecture.
* Scripts execute only through the task's Linux environment with
  `exec.shell` / existing jobs & service lifecycle; no language aliases, no
  host interpreter fallback. Engine dependencies (e.g. the Impeccable RISC-V
  engine, lane H3) are separate signed runtime dependencies with digest
  bindings — never inside the skill ZIP; ZIPs carry instructions, audited
  source scripts and resources only.

## 6. Lifecycle, install offers and fail-closed rules

States are distinct and never inferred from a build success:
`sourcePinned → licenseChecked → adaptation(frozen) → packaged → reviewed →
qualified → published`, with `executionVerified` only from real guest runs.
`reviewed ⇒ licenseChecked`; `qualified ⇒ reviewed + packaged`;
`published ⇒ qualified`; a same-version rewrite or digest change invalidates
the review binding.

Publication is a **feed-side projection, not a registry-data flip**: the
signed release feed is the publication act itself, so every qualified
download offer carries `status.published=true` in the feed (a deep-copied
status block — the builder never mutates the registry object it was given),
while the candidate registry rows keep `published=false`. The website
candidate pipeline refuses a `published` claim in registry data, and the
four App-provided builtin ids (`floe-pdf`, `floe-office`, `floe-network`,
`floe-video`) are native App features: they stay valid, reviewable registry
rows but are **never Hub download offers**, so a release feed never carries
them and never references their archives or reviews. Preview/fixture
metadata continues to describe all 43 candidates unpromoted.

Client must fail closed on any of:

1. `schemaVersion != 3`, unknown `channel`/`feedStatus`, publisher or
   `hubRepository` drift, `permissionPolicy` not equal to §4.
2. Envelope `keyID` not in the compiled trust map; signature invalid over the
   exact bytes; `feedStatus == "production"` while the verifying keyID is the
   fixture identity; `feedStatus == "fixture"` presented through a production
   channel configuration.
3. `installOffer == "qualified"` without non-null `package` **and** a `review`
   whose record signature verifies **and whose joins hold against the actual
   bytes**: `contentDigest`/`packageSha256` equal the real unpacked/downloaded
   values, `decision == "approve"`, and the reviewed capability/tool/dependency
   sets equal the manifest of this build exactly — never a subset (an omitted
   new tool is unreviewed), never a superset (a grant outside the manifest),
   never a stale valid signature over old bytes. Official ZIPs are
   authenticated by the signed catalog `sha256`/`contentDigest` chain, not by
   independent per-ZIP signatures; the native client repeats every join
   independently. Anything else shows `暂不可用 / Unavailable`, never a
   `获取 / Get`.
4. Downloaded archive `size`/`sha256` mismatch, unpacked `contentDigest`
   mismatch, or any package-gate violation (paths, `..`, absolute, backslash,
   NUL, leading dot, NFC/case duplicates, symlinks, directory entries,
   forbidden extensions `dylib|so|wasm|framework|bundle|a|o`, native magic
   `ELF|Mach-O(32/64/fat)|wasm`, >128 files, >2 MiB/file, >8 MiB total,
   `SKILL.md` >256 KiB, `floe.json` >64 KiB, top-level outside
   `SKILL.md|floe.json|scripts|references|assets|agents`, runtime/script
   mismatches, non-exact `name==version` dependency specs).
5. Same `id`+`version` published with different bytes or digests
   (`immutableVersion`): keep the installed copy, reject the feed entry; a
   lower remote version never downgrades; same-name local/user-modified skills
   never auto-overwrite.
6. Review/tool/capability sets that exceed what the entry's `runtime` block
   declares; unknown capabilities/platforms outside the native enums.

`skill.search`/`skill.read`/`skill.install` mapping (lane A1): the immutable
retrieval pin is `publicationCommit` Y — the resolved repository ref whose
tree carries the feed, signature, review records and archives; every path of
one install operation is fetched at Y. The feed's signed `sourceCommit` X is
displayed/kept in receipts as audited-source provenance and is never used to
locate artifacts or required to equal Y (`id`/`version` select the entry;
install resolves `package.path` at Y, verifies §6.4, checks the `review`
chain (§6.3), then applies the §4 grant-delta flow before staging through the
existing atomic promotion. The hub branch never accepts a model-supplied URL
or self-declared trust flags, and never bypasses the workspace-import
approval that exists today.

## 7. The fixture-only sample (already emitted)

Location: `tests/catalog/fixtures/` inside this repository — layout is
isomorphic to production (iOS feed at the bundle root: `catalog.json`,
`catalog.sig`, `packages/…`; Android under `android/…`; shared
`reviews/…`). Three entries only — `fixture-guide` (no scripts, no
execution), `fixture-script` (packaged, deliberately **unreviewed** →
`installOffer "none"`), `fixture-reviewed` (packaged + simulated signed review
→ `installOffer "fixture-simulated"`).

Verification recipe (host): `python3 scripts/make_fixture.py --check`, then
in Python: `hubcore.verify_envelope(catalog_bytes, sig, {"fixture-only-2026-10": <fixture-public-key.json>})`.
Natively: load `fixture-public-key.json` only through a test-only trust map;
`fixtureOnly/notATrustRoot` are true in that file. This key's seed is public
knowledge, so nothing here attests review, license, quality or publication,
and no fixture file may exist at production paths.

## 8. Deterministic commands

| Command | Effect |
| --- | --- |
| `python3 scripts/gen_schemas.py [--check]` | emit/verify `schema/*.json` from validator constants |
| `python3 scripts/build_catalog.py --mode preview --source-commit <X> [--out-root DIR \| --check]` | rebuild both candidate feeds from the working tree; the legacy `--hub-commit` flag remains as an exact alias for `--source-commit` |
| `python3 scripts/build_catalog.py --mode release --source-commit <X> --source-snapshot <DIR> [--out-root DIR] [--sign-env <ENV>]` | publication-path build: registry, archives and reviews are read ONLY from the frozen fetch of X, so the claimed X honestly binds the payload; includes only qualified, download-eligible entries (every genuinely qualified non-builtin row) with trust-verified signed reviews. The incremental signing policy admits the exact nonempty qualified download set in each channel — currently 30 iOS / 30 Android download offers, because the four App-provided builtin ids are native App features and never Hub download offers — and every admitted offer carries the feed-only `published=true` projection while the source registry rows stay `published=false`. It retains all per-item review, execution and runtime-dependency gates. The 40-entry selection target (which counts the qualified registry selection including the four builtins) and all nine deep adaptations are informational coverage, not a batch-release prerequisite. `--sign-env` first requires the derived public identity to match `public-key.json` |
| `python3 scripts/build_packages.py [--check]` | gate + package staged `sources/{id}` into immutable channel archives |
| `python3 scripts/make_fixture.py [--check]` | emit/verify the fixture sample |
| `python3 scripts/check_catalog.py` | read-only: registry, pins-vs-`docs/UPSTREAM-PINS.json`, schemas, fixtures, secret scan, and the standalone publication gate — once ANY production artifact exists it requires both channel feed+signature pairs, verifies every signature over the exact bytes under `public-key.json` trust, checks canonical production feed shape with a 40-hex `sourceCommit`, and re-joins every published archive and review record against the actual bytes; a valid publication is never rebuilt from or invalidated by the mutable candidate HEAD, and an absent or wrong-key signature never passes |
| `python3 -m unittest discover -s tests/catalog` | behaviour tests |

Content lanes (H2 ordinary-34, H3, H4, H5, builtin migration): stage sources
under `sources/{id}/` per schema rules, never edit `catalog/skills.json` or
`scripts/`; return per-item deltas (actual manifest tools/capabilities,
license evidence, exact pin or licensed-source replacement) to the
coordinator, who promotes registry rows and status. The publication run
(coordinator only) freezes a fetch of the audited source X
(`git archive <X> | tar -x -C DIR`), builds `--mode release` with
`--source-snapshot DIR --sign-env FLOE_SKILL_HUB_SIGNING_KEY`, commits the
resulting feeds/signatures/artifacts so Git resolves the publication commit
Y, and pins Y externally; then `check_catalog.py` verifies the published
bytes standalone at Y. `--check` remains a candidate-tree convenience only:
it compares a fresh build against committed outputs and must not be used to
re-derive a published feed from moved candidate state.

## 9. Managed raw runtime artifact binding (Impeccable engine)

The managed Impeccable RISC-V engine is a raw runtime artifact **outside**
every Skill ZIP: `engines/impeccable/dist/impeccable-{componentVersion}/
{triple}/floe-impeccable` in the same Hub repository. Its binding data is the
frozen descriptor `engines/impeccable/runtime-dependency/descriptor.v1.json`
(frozen 2026-10-26; schema in the adjacent `schema.v1.json`). The canonical
Impeccable Skill package embeds byte-identical
`references/engine-dependency.json` — data only, never a source of
permissions, and the ordinary Skill limits (2 MiB/file, 8 MiB/package, no
native payloads inside the ZIP) are unchanged.

`scripts/runtime_dependency.py` is the strict known-component validator
shared by three gates:

| Gate | Behaviour |
| --- | --- |
| `build_packages.py` (source/package production) | a staged package embedding `references/engine-dependency.json` must be byte-identical to the frozen tree descriptor and reference an existing, exact-size, exact-hash, safe static-ELF artifact in the SAME tree; otherwise the build fails closed. |
| `build_catalog.py --mode release` | the descriptor and the raw artifact are validated ONLY from the frozen `--source-snapshot` of the audited X, and the output is standalone for runtime binding: BOTH the exact validated descriptor bytes (staged at `engines/impeccable/runtime-dependency/descriptor.v1.json`) and the validated raw artifact bytes (staged at the descriptor-relative path) are written into the publication output (Y) — a fresh output root therefore binds the runtime package without any manual descriptor copy, a stale or tampered mutable-HEAD descriptor can never leak into Y, and only those two files are staged, never a recursive engine copy. |
| `check_catalog.py` (standalone publication gate) | for every published package embedding the descriptor, the published frozen descriptor at Y must match it byte-identically and the referenced artifact must exist at Y with exact size, SHA-256 and safe static-ELF shape — for BOTH channels, reading only the published bytes at Y, never the mutable candidate HEAD. |

Descriptor policy (fail closed): exactly the 7 keys
`schemaVersion/componentID/componentVersion/minimumAppVersion/target/artifact/
captureContract` with exact subkey shapes; `schemaVersion` is exactly the
integer `1` (`true`, `false` and `1.0` are rejected even though Python
compares them equal to 1); raw descriptor bytes must be the canonical UTF-8
encoding itself — re-encoding the parsed value with the hub's canonical
`encoded()` must equal the raw bytes — so UTF-16/BOM sniffing, trailing or
surrounding whitespace, key-order drift, pretty-printing and duplicate keys
silently resolved last-wins are all rejected; the frozen 563-byte canonical
descriptor is the passing shape. `componentID ==
"impeccable-engine"` (known allowlist); `componentVersion` strict
`X.Y.Z+floe.X.Y.Z`; strict `minimumAppVersion`; the fixed linux/riscv64/
`riscv64gc-unknown-linux-musl`/`elf64-little-riscv-exec-static` target;
artifact size 1..16 MiB (native hard cap for this known component only);
strict lowercase SHA-256; `captureContract` version 1 with a strict hash;
artifact path exactly
`engines/impeccable/dist/impeccable-{componentVersion}/{target.triple}/floe-impeccable`
— no URL/repository/command/approval/environment fields (unknown keys are
rejected), no traversal/absolute/backslash/NUL/empty/dot segments, no symlinks
at the artifact path or any ancestor.

Artifact policy (fail closed): bounded read, exact size+SHA-256, ELF64
little-endian RISC-V `EXEC` static only (no `PT_INTERP`, bounded
program-header table with in-file offsets). The binary is never executed on
the host and no producer code is invoked. Descriptor bytes are authenticated
indirectly: they sit inside the signed Skill ZIP, so the signed catalog →
archive `sha256`/`contentDigest` → review chain binds them; a descriptor
tamper breaks that digest chain before the runtime gate is reached.
