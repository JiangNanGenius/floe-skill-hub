# Official Skill dependency declarations — Hub author contract (schemaVersion 1)

Audience: authors and reviewers of **official, reviewed and signed** Floe Skill Hub
packages, and the Hub producer/publication tooling.

The authority is the native strict decoder
`FloeAgent/Sources/FloeSkills/SkillDependency.swift` in the floe-agent repository
(mirroring the frozen `SkillRuntimeDependency` descriptor pattern). This document is
the Hub-side operational contract; the machine-readable mirror generated from the
producer validator lives at `schema/dependencies.schema.json`, and worked examples
live at `docs/dependency-examples/`. The canonical author guide copy lives in the
floe-agent repository under `docs/skills/`.

## What the file is

`references/dependencies.json` inside a canonical Skill package declares the
resources the official Hub installation flow may automatically prepare and install
into the task's resolved Linux guest environment. The channel is reviewed/signed
only: the bytes live inside the canonical package, so the package `contentDigest`
and the review `.sig` binding already cover the declaration and every referenced
lock — no external hashes exist in this file's trust path.

The declaration is **data, never authority**: it can never mint a shell command,
redirect a download or widen an approval. There is no URL, command, script,
environment, registry/index, permission or approval field anywhere in the schema;
unknown fields fail closed in the native decoder.

## Frozen schema (v1)

Top-level keys are exactly `schemaVersion` and `profiles`; a profile is exactly
`id`, `target` (`os` + `architectures`) and `requirements`; every requirement is
tagged by `kind` and carries exactly the key set of its kind:

| kind | keys | rules |
| --- | --- | --- |
| `pip` | `kind,name,version,purpose,required[,lockfile]` | exact PyPI name; one exact PEP 440 version; optional package-local wheel lock under `references/…​.txt`. Pure `py3-none-any` wheels only — the existing install-time audit stays unchanged. |
| `apt` | `kind,name,version,purpose,required` | one Debian identity + exact Debian version (epoch, `+dfsg`, `-rev`, `+repack` stay part of the pin). |
| `npm` | `kind,name,version,purpose,required` | exact `name@version` (optionally scoped), exact semver only; no `+` build metadata. A packaged `package-lock.json` is review evidence, never replayed as an install. |
| `font` | `kind,name,version,purpose,required` | exactly one Debian font identity (`fonts-…`) **plus an exact Debian version** (same pin class as `apt`). |
| `runtimeComponent` | `kind,componentDescriptorPath,purpose,required` | path must be exactly `references/engine-dependency.json`; identity/version/digest come only from the pinned descriptor through the existing managed allowlist (today exactly `impeccable-engine`). The allowlist, the 16 MiB component cap and the nonblocking hook are not broadened. |

`purpose` is 1–200 bytes of model-safe text; `required` is a boolean. Limits:
≤64 KiB file, 1–8 profiles (unique ids), 1–32 requirements per profile
(unique `(kind,name)`), `os` exactly `"linux"`, `architectures` ⊆
`{riscv64, arm64, x86_64, any}`.

A skill with no dependencies ships **no** `dependencies.json` at all: zero profiles
or an empty `requirements` array is invalid and fails closed.

## Version management (frozen distinctions)

The Skill package `id`/`version` (`floe.json`) stays the single user-visible
package authority. Four frozen version concepts, no fifth:

1. **Skill package version** — released bytes are immutable. Any change to
   scripts, dependency declarations or permissions requires a NEW package version
   and a NEW signed digest. Publisher tooling MUST refuse a publication that
   reuses an already-published `id`+`version` with a different `contentDigest`,
   even when the publisher could re-sign the new bytes (the client-side receipt
   digest alone cannot prove historical publication immutability). Enforced at
   the publishing boundary by `scripts/publication_immutability.py`.
2. **`schemaVersion`** — parser compatibility only; this build accepts exactly `1`.
3. **Exact resource pins + locks** — what gets installed and read back; never
   ranges, never `latest`, never silent downgrade/uninstall.
4. **`minimumAppVersion`** — the existing old-client gate. A curated entry whose
   package carries a dependency declaration needs the new native provisioning
   behavior, so the publisher raises the entry's existing `minimumAppVersion` to
   the first capable build (candidate `1.7.60`). Enforced at the package
   preflight and release boundary by `scripts/dependency_declaration.py`.

Rollback binds the exact published version + digest, never "latest". Uninstalling
a skill removes ownership records only — declared packages stay in the
environment untouched.

## Tooling map

| concern | location |
| --- | --- |
| strict decoder mirror (grammar/limits/cross-validation) | `scripts/dependency_declaration.py` |
| staged-source preflight (package build) | `scripts/build_packages.py` (`assert_declaration_gates`) |
| release-boundary re-check + minApp gate | `scripts/build_catalog.py` (`bind_package`) |
| published-history immutability guard | `scripts/publication_immutability.py` (release mode) |
| machine schema (generated, byte-stable) | `schema/dependencies.schema.json` via `scripts/gen_schemas.py` |
| worked examples (native-valid) | `docs/dependency-examples/` |
| mirror-accuracy + gate tests | `tests/catalog/test_dependency_declaration.py`, `tests/catalog/test_publication_immutability.py` |

Examples pin exact upstream versions for authoring clarity only; they are not a
claim that a specific guest image or fresh repository carries those versions
until separately verified against real guest evidence.

## Publication workflow

The production signer runs from an immutable, reviewed tooling commit T, with a
separate immutable data snapshot X. Before signing, the workflow independently
resolves the current official Hub publication commit Y and passes `--published-y`.
Once any publication history exists, omitting that input is an error. The signer
never treats the frozen tooling checkout as evidence of the latest publication.

The cumulative ledger must use exactly `catalog/publication-ledger.json` inside T.
Each row records a publication commit, channel, feed hash and the complete set of
packaged offers; its actual feed bytes and signature are verified under the
configured production key. Historical rows cannot be removed or rewritten, even
after an offer leaves the latest feed. Git environment redirects and replacement
refs do not affect these object reads. Ledger ancestry comparison reads only the
two most recent commits changing the ledger.

After a publication, derive and append its verified channel rows before the next
publication, review the updated tooling and advance the workflow's literal T pin.
If the pinned ledger does not cover the independently resolved current offers,
signing fails closed until the ledger and tooling pin are refreshed. Unchanged
package bytes may be republished; changed bytes require a new Skill version.
