# Android portable guides — server-side content-floor projection

Status: implemented in trusted build tooling (`scripts/build_catalog.py`,
`ANDROID_PORTABLE_GUIDE_IDS`); **inert until the coordinator publishes the
Linux-declared guide batch**. No registry, schema, record, enum, license,
permission-policy or native App change is involved, and **no validator is
relaxed**: the projected `0.0.0` floor passes the current
`hubcore.validate_catalog` and the published schema exactly as they stand.

## Why

The Android client's marketing version domain (`0.1.0-alpha.x`) is unrelated
to the iOS domain (`1.7.x`). Every curated registry row today carries an iOS
`minimumAppVersion` floor (all 28 portable guides: `1.7.59`), and the feed
build passes that floor straight through per the registry. Left unchanged,
the Android feed would force every user through a long Android-side
qualification of the whole Hub, even though the 28 basic text guides contain
no App-SDK-specific code, no scripts, no tools, no Python packages — they are
instruction-only content whose only requirement is a working
workspace-read/write grant. The user explicitly asked for a shorter Android
qualification path with many direct installs.

## The rule (Root decision, 2026-10-28, finalized)

A production Android feed entry projects
`minimumAppVersion="0.0.0"` — a valid strict `X.Y.Z` string, never `null`,
never a guessed marketing version — **only when every predicate below is
proven against the actual bound frozen package and review this same build
joined** (re-hashed against the feed's own
`package.sha256/size/contentDigest` and `review.sha256` bindings; any
disagreement aborts the build fail-closed):

1. the id is one of the **28 literal ids** frozen in trusted tooling
   (`ANDROID_PORTABLE_GUIDE_IDS`) — derived from the immutable B registry as
   exactly the optional rows whose planned `scriptRuntime` is `none`
   (43 rows = 4 App-provided builtins + 39 optional; 39 = 28 + 11 scripted).
   New or unrecognized curated ids never inherit the waiver automatically;
2. the bound package manifest (`floe.json`) declares the **linux** platform;
3. its `scriptRuntime` is `none`;
4. its `tools` list is empty;
5. its `pythonPackages` list is empty;
6. its declared `capabilities` are a subset of `{workspace.read,
   workspace.write}`;
7. its bound review record is `static-content-reviewed` and carries the
   empty unproven execution claim `{"os": null, "arch": "n/a", "evidence":
   "unproven"}`.

If any predicate is absent or points at new features, the registry floor is
retained unchanged. An entry whose floor already is the sentinel is never
re-projected. The **iOS feed entries are never touched** — the projection
runs only for the `android` channel, after the floor-retaining feed has
passed `hubcore.validate_catalog` in full, and the FINAL projected bytes are
put back through the same unchanged `validate_catalog` before emission.
Eligibility is never inferred from the mutable registry plan (`plannedRuntime`
is not consulted).

## What the 0.0.0 sentinel means, and what it does not

`minimumAppVersion="0.0.0"` is a **content-floor sentinel**: it is below
every possible client version, so it honestly encodes "every client version
is new enough for this instruction-only package — there is no SDK-specific
content floor". It is deliberately NOT the Android marketing version and it
does **not** claim that any old App build supports the Hub UI or the
installed behavior; installation still flows through the unchanged native
schema-3 verification and the unchanged platform, capability, permission,
tools and discovery validators. The existing contract requires a non-null
version string for packaged entries; the sentinel preserves that contract
without changing the validator or schema. Clients should omit a minimum-version
label when this sentinel is present. Licenses, the feed `permissionPolicy`, archive bytes,
content digests, review stages, execution claims, version, status and
platform offers are all untouched. No runtime, permission or license
relaxation is introduced anywhere.

## Effect on current and staged data

- At the reviewed baseline `3e145cd6`, the published package manifests declared `["ios"]` only, so
  predicate 2 fails for all rows: the baseline feeds rebuild
  **byte-identical** through this code (proved against the frozen audited
  source `2d131b2e…` vs the publication bytes at `3e145cd6…`, all four
  outputs). The baseline entries carry no sentinel.
- For the reviewed compatibility batch (28 packages at `1.0.1`
  declaring `["ios","linux"]`, verified against their staged review records
  with the unchanged gates): **24 ids project the `0.0.0` sentinel**, while
  four keep the `1.7.59` floor because their own frozen manifests exceed the
  capability ceiling — `a11y-audit` (browser.observe), `deep-research` and
  `research-summarizer` (network), `floe-file-organizer` (workspace.delete).
  This is the rule refusing them, not a gap in the rule.

## Activation (coordinator-owned) and honest limitations

The rule activates only when the coordinator lands and **signs** the
Linux-declared package batch plus its fresh, officially signed static machine reviews. No further validator, schema or client code change is
required for the projected bytes to pass the existing contract: the sentinel
is an ordinary strict version string for `hubcore.validate_catalog`, the
published JSON schema and the native schema-3 decoder.

Remaining acceptance limits, stated honestly:

- this is source-only evidence; no device, emulator or App run was made in
  this lane, and confirming the sentinel's effect on the real Android
  client's version comparison and install flow remains with the Android main
  owner on an actual build;
- the sentinel never grants install behavior to a build that lacks the Hub
  UI or installer route — such a build still cannot use these entries, and
  nothing here claims otherwise.

## Verification

Focused contract tests (no production data mutation, ephemeral isolated
signing keys only):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_android_guide_projection.py
```

They cover: the frozen 28-id set equals the immutable-B optional-none rows;
per-feed integration (iOS floor retained; Android `0.0.0` for a
linux-declared guide whose binding passes the full unchanged gates; the FINAL
projected bytes re-validated by the unchanged `hubcore.validate_catalog` and
the existing published schema via `jsonschema` when already installed — no
dependency is added); that a `null` floor is rejected by the unchanged
validator clause while the sentinel is accepted; projection idempotence (an
already-projected feed is never re-projected); pre-Linux payloads retain the
floor on both channels with no sentinel anywhere; unknown ids, scripted
manifests, non-empty tools/`pythonPackages`, non-basic capabilities and
missing package/review bindings keep the floor; guest-execution or
wrong-stage reviews fail the unchanged bind/join gates closed; the helper
never mutates its input and is deterministic; and the full current B release
feeds rebuild byte-identical from the frozen X snapshot against the
`3e145cd6` published bytes.
