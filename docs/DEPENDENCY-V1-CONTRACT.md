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
| `pip` | `kind,name,version,purpose,required[,lockfile]` | exact PyPI name; one exact PEP 440 version tail `[A-Za-z0-9][A-Za-z0-9.*+!_-]{0,127}` **containing at least one ASCII digit** — `latest`/`stable`/`*` are refused by the native decoder; optional package-local wheel lock under `references/….txt`. Pure `py3-none-any` wheels only — the existing install-time audit stays unchanged. |
| `apt` | `kind,name,version,purpose,required` | one Debian identity + exact Debian version `([0-9]+:)?[A-Za-z0-9][A-Za-z0-9+~:.+-]{0,127}` where **the body after the optional epoch contains at least one ASCII digit** (so `1:latest` is refused even though the epoch is a digit; `+dfsg`, `-rev`, `+repack` stay part of the pin). |
| `npm` | `kind,name,version,purpose,required` | exact `name@version` (optionally scoped), canonical exact semver `X.Y.Z[-tail]` only (no leading dash in the core, no `+` build metadata; see subsets below). A packaged `package-lock.json` is review evidence, never replayed as an install. |
| `font` | `kind,name,version,purpose,required` | exactly one Debian font identity: prefix `fonts-` with the **whole** name (prefix included) valid Debian identity grammar ≤128 bytes — `fonts-` + 123 chars is refused — **plus an exact Debian version** (same pin class as `apt`). The bare `fonts-` is grammar-valid natively (oddity pinned by probe) but is never a packageable identity; review and packaging judgment govern. |
| `runtimeComponent` | `kind,componentDescriptorPath,purpose,required` | path must be exactly `references/engine-dependency.json`; identity/version/digest come only from the pinned descriptor through the existing managed allowlist (today exactly `impeccable-engine`). The allowlist, the 16 MiB component cap and the nonblocking hook are not broadened. |

`purpose` is 1–200 **UTF-8 bytes** of model-safe text: non-empty, equal to its
own Foundation `whitespacesAndNewlines` trim (no edge whitespace; interior
whitespace is allowed — probe-confirmed e.g. interior NBSP and U+2028 pass),
and no scalar in `NSCharacterSet.controlCharacters` — probe-verified on the
real Foundation to be exactly Unicode categories **Cc ∪ Cf** (so TAB/LF/NUL
*and* ZWSP U+200B, soft hyphen U+00AD, U+061C, U+2060 etc. are all refused
even mid-string; U+200B is Foundation-edge-whitespace as well, but the Cc∪Cf
screen alone decides it);
`required` is a boolean. Limits: the raw declaration is bounded at **65 536
bytes before any parsing** (native `maximumDeclarationBytes`, mirrored with
the same fail-closed order), 1–8 profiles (unique ids), 1–32 requirements per
profile (unique `(kind,name)`), `os` exactly `"linux"`, `architectures` ⊆
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
2. **`schemaVersion`** — parser compatibility only; the producer contract is the
   literal JSON integer `1`. (The native `JSONSerialization` layer also parses
   integral numbers such as `1.0`/`1e0`; authors must write the integer — a
   documented subset below.)
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

## Mirror parity audit (2026-10-27)

The producer mirror in `scripts/dependency_declaration.py` was corrected
against an **executable component probe** of the unchanged native authority
files, not against regex guesses:

* Native source pinned read-only: `FloeAgent/Sources/FloeSkills/SkillDependency.swift`
  sha256 `da8e651e597d199d61f7dc6dafdc136fb753e343e76ad819c949ae98fe5bb65c`
  and `SkillIdentifier.swift` sha256 `4eee3b429a225fa85f22f3ea8550a720571a4f4d402c893cb36f60c3c152542e`
  (frozen Main worktree copies; neither was modified).
* Toolchain: `DEVELOPER_DIR=/Applications/Xcode-27.1.app/Contents/Developer`
  host `swiftc -swift-version 5`, isolated empty `FloeCore` module and minimal
  stubs **only** for the unexercised cross-validation surface
  (`SkillValidationError`, `SkillRuntimeDependency`). One compile-plumbing
  adaptation was required and is disclosed: the native line
  `guard let requirementArray = targetRequirements(…)` calls a `throws` helper
  without `try`, which the actual Xcode 27.1 compiler rejects — the probe copy
  (sha256 `49bf889b38043db074ced93cd4f2e5666be0808631a8ef7c2ff116692a0b2f02`)
  adds exactly that one `try` token (`diff` shows a single line); every
  classifier body is byte-identical to `da8e651e…`. The missing `try` is a
  real native-side defect (the file had only ever been grammar-parsed, never
  object-compiled) and is reported to the native owner; it changes no verdict.
* Differential: 180 classifier + 48 whole-document decode verdicts (plus 3
  cross-validation probes and a 98-scalar Foundation character-set table);
  every native verdict was compared with the mirror. Final result after the
  fix: 220 identical, 8 intentional subsets, ZERO cases where the mirror
  accepts something native rejects.

Over-acceptances fixed (mirror previously looser than native — forbidden direction):

1. `pip` version: added the native digit requirement (`latest`, `stable`, `*`
   refused); the earlier `PARITY.json` claim that "the native decoder accepts
   any tail" is corrected here — the actual Swift `isValidPipVersion` digit
   guard rejects them (probe-confirmed).
2. `apt` version: digit required in the **body after the epoch** (`latest`,
   `stable`, `1:latest`, and an all-letter body like `a`×128 refused; the old
   test expecting `a`×128 valid was wrong in both files).
3. `font` identity: the 128-byte budget applies to the WHOLE name including
   the `fonts-` prefix (previously the suffix got a fresh 128, accepting
   129–134-byte names native refuses); the bare `fonts-` is native-valid and
   the mirror now says so.
4. `purpose`: control screen widened from Cc to the probe-verified Foundation
   `controlCharacters` == Cc ∪ Cf; encode failures (lone surrogates) now fail
   closed instead of crashing.
5. `parse_declaration`: the declared `MAX_DECLARATION_BYTES = 65_536` is now
   enforced BEFORE any decode/parse (bytes and string inputs), matching the
   native `bytes.count <= maximumDeclarationBytes` guard; oversized payloads
   never reach the JSON parser.
6. Unpaired `\uDXXX` escapes: native `JSONSerialization` refuses the whole
   document; the mirror now refuses them after load with the same verdict
   (Python's `json` would otherwise hand surrogates downstream).

Documented SAFE-AUTHORING SUBSETS (mirror stricter than native — allowed
because nothing native-valid that a real author should rely on is silently
re-classified, and each is refused with a clear producer error):

* profile ids: ASCII slug only (native `SkillIdentifier` also accepts Unicode
  lowercase letters and numerals, probe-confirmed `café`/`a٣` native-valid);
* `schemaVersion`: literal integer `1` only (native also parses integral
  numbers like `1.0`/`1e0`);
* `npm` version: canonical `X.Y.Z` core (native's `split(omittingEmptySubsequences:)`
  happens to tolerate a leading dash like `-1.0.0`); the empty-string case is
  additionally refused where native would index an empty split and trap — a
  native-side robustness gap owned by Main, flagged with this audit.

The machine schema (`schema/dependencies.schema.json`, regenerated from the
corrected mirror) keeps documented approximations: `maxLength` counts
characters not UTF-8 bytes, and Cc∪Cf/trim/structural rules beyond a portable
pattern are enforced exactly only by the producer gate and the native
decoder, which remain authoritative.
